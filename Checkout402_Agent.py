"""
LLM agent that explains HTTP 402 / x402 and completes a real paid checkout via tool call.

Same shape as Tv_Agent.py: PREFERENCES, build_system_prompt(), run_agent() with an
agentic tool loop. Uses web_search for context, then execute_x402_checkout (custom tool)
to sign and pay with EVM_PRIVATE_KEY.

Run:
  export ANTHROPIC_API_KEY=...
  export EVM_PRIVATE_KEY=...   # Base Sepolia ETH + USDC for default URL
  python Checkout402_Agent.py

For checkout-only (no Claude), use x402_agent.py instead.
"""

from __future__ import annotations

import asyncio
import json
import os

import anthropic

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from x402_checkout import DEFAULT_X402_PAID_URL, fetch_paid_url

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip() or None
MODEL = "claude-sonnet-4-20250514"

# Demo context passed into the system prompt (like TV preferences).
PREFERENCES = {
    "target_url": DEFAULT_X402_PAID_URL,
    "network": "Base Sepolia (testnet)",
    "typical_asset": "USDC",
    "note": "Echo endpoint; ~$0.01 USDC + gas per successful checkout",
}
# ─────────────────────────────────────────────────────────────────────────────


def build_system_prompt(prefs: dict) -> str:
    pref_lines = "\n".join(f"- **{k}:** {v}" for k, v in prefs.items())
    return f"""You are an expert agent demonstrating **HTTP 402 Payment Required** and the **x402** protocol for machine-native stablecoin checkout.

## Demo configuration (fixed for this run)
{pref_lines}

## Your job

1. **Educate briefly** using web search when helpful: what HTTP 402 means, how x402 uses it, the role of facilitators and signed payment payloads, and why agents use this instead of traditional API keys for some APIs. Cite current public sources when you search.

2. **Outline a clear briefing** for the human with these sections (use markdown headings):
   - **What is 402 in this context?** — server refuses content until payment terms are met.
   - **What happens in one successful checkout?** — request → 402 + requirements → client pays → retry with payment proof → 200 + resource.
   - **What the wallet needs** — correct chain native token for gas + the asset the resource asks for (here: Base Sepolia ETH + USDC on Base Sepolia for the default URL).
   - **Risks / caveats** — testnet vs mainnet, real funds on mainnet, key safety.

3. **Complete the demonstration** by calling the tool **`execute_x402_checkout`** exactly once when you are ready, with:
   - `url`: use the **target_url** from the demo configuration unless the user clearly specified another x402 URL in the conversation.
   - `reasoning_summary`: one short sentence on why you are triggering checkout now.

After the tool returns, **interpret the JSON result** for the user: HTTP status, whether the body looks like success, and any `settlement` fields. If the tool reports an error, explain what likely went wrong (funds, network, RPC) and what to try next.

Keep the tone direct and practical. Do not claim you paid before the tool has run."""


def run_agent(prefs: dict) -> str:
    if not API_KEY:
        raise SystemExit(
            "Set ANTHROPIC_API_KEY in your environment (export ANTHROPIC_API_KEY=sk-ant-...)."
        )
    pk = os.environ.get("EVM_PRIVATE_KEY", "").strip()
    if not pk:
        raise SystemExit(
            "Set EVM_PRIVATE_KEY in .env so execute_x402_checkout can sign the payment.\n"
            "See x402_checkout.py for faucet hints (Base Sepolia ETH + USDC)."
        )

    client = anthropic.Anthropic(api_key=API_KEY)
    system = build_system_prompt(prefs)
    pref_str = ", ".join(f"{k}={v}" for k, v in prefs.items())

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Walk me through x402 / HTTP 402 checkout as a demo. "
                f"Use this configuration: {pref_str}. "
                "Search the web if it helps you explain accurately, then run the checkout tool once."
            ),
        }
    ]

    tools: list[dict] = [
        {"type": "web_search_20250305", "name": "web_search"},
        {
            "name": "execute_x402_checkout",
            "description": (
                "Perform a real x402 flow: GET the URL, handle 402, sign stablecoin payment, "
                "retry, return final status and response body preview. Requires EVM_PRIVATE_KEY on server."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full https URL of the x402-protected resource.",
                    },
                    "reasoning_summary": {
                        "type": "string",
                        "description": "One sentence: why checkout is being executed now.",
                    },
                },
                "required": ["url", "reasoning_summary"],
            },
        },
    ]

    print("Running checkout-402 agent...\n")

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=system,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            break

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        tool_results: list[dict] = []

        for tu in tool_uses:
            if tu.name == "web_search":
                print(f"  Agent: web_search ({getattr(tu, 'id', '')[:8]}…)")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": "search completed",
                    }
                )
            elif tu.name == "execute_x402_checkout":
                inp = tu.input if isinstance(tu.input, dict) else {}
                url = (inp.get("url") or "").strip() or prefs.get("target_url", DEFAULT_X402_PAID_URL)
                why = inp.get("reasoning_summary", "")
                print(f"  Agent: execute_x402_checkout → {url[:64]}…")
                print(f"       ({why[:120]}{'…' if len(str(why)) > 120 else ''})")
                try:
                    resp, settle = asyncio.run(
                        fetch_paid_url(url, evm_private_key=pk, timeout=120.0)
                    )
                    payload = {
                        "ok": resp.status_code == 200,
                        "status_code": resp.status_code,
                        "body_preview": resp.text[:4000],
                        "body_truncated": len(resp.text) > 4000,
                        "settlement": settle,
                    }
                except Exception as e:
                    payload = {
                        "ok": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(payload, indent=2),
                    }
                )
            else:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps({"error": f"unknown tool: {tu.name}"}),
                    }
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    final = "\n".join(
        block.text for block in response.content if block.type == "text"
    )
    return final


if __name__ == "__main__":
    result = run_agent(PREFERENCES)
    print("\n── x402 checkout demonstration ─────────────────────────────────────\n")
    print(result)
