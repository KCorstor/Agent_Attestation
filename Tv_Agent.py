import os

import anthropic

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip() or None
MODEL   = "claude-sonnet-4-20250514"

PREFERENCES = {
    "budget": "$500–$1000",
    "size":   "55 inch",
    "use":    "movies and streaming",
    "panel":  "any panel type",
}
# ─────────────────────────────────────────────────────────────────────────────


def build_system_prompt(prefs: dict) -> str:
    pref_str = ", ".join(f"{k}: {v}" for k, v in prefs.items())
    return f"""You are an expert TV buying agent. The user has these preferences: {pref_str}.

Your job is to research the current TV market and create a detailed, actionable buying plan. Use web search to find:
1. The best TVs currently on sale that match the user's budget and preferences
2. Current prices and where to buy (Amazon, Best Buy, Costco, etc.)
3. Any major sales events happening soon (e.g. Memorial Day, Prime Day)
4. A head-to-head comparison of the top 2-3 options

Then write a clear buying plan with these sections:
- Top pick: model name, price, where to buy, and why it fits
- Runner-up: a solid alternative with trade-offs explained
- Key specs to verify before purchasing
- When to buy: buy now or wait for a better deal
- Where to buy: best retailer(s) and any active promo codes or cashback offers

Be specific with model names, prices, and URLs when available. Keep the tone direct and practical."""


def run_agent(prefs: dict) -> str:
    if not API_KEY:
        raise SystemExit(
            "Set ANTHROPIC_API_KEY in your environment (export ANTHROPIC_API_KEY=sk-ant-...)."
        )
    client = anthropic.Anthropic(api_key=API_KEY)

    system  = build_system_prompt(prefs)
    pref_str = ", ".join(f"{k}: {v}" for k, v in prefs.items())

    messages = [
        {
            "role": "user",
            "content": (
                f"Find me the best TV on sale right now. "
                f"My preferences: {pref_str}. "
                "Search the web for current deals and give me a complete buying plan."
            ),
        }
    ]

    tools = [{"type": "web_search_20250305", "name": "web_search"}]

    print("Running agent...\n")

    # Agentic loop
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=system,
            tools=tools,
            messages=messages,
        )

        # Collect any text streamed so far
        for block in response.content:
            if block.type == "text" and response.stop_reason != "tool_use":
                pass  # final answer handled after loop

        # If the model is done, break
        if response.stop_reason != "tool_use":
            break

        # Otherwise, handle tool calls and loop
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        print(f"  Agent is searching... ({len(tool_uses)} query/queries)")

        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": "search completed",   # Anthropic fills real results internally
            }
            for tu in tool_uses
        ]

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user",      "content": tool_results})

    # Extract final text answer
    final = "\n".join(
        block.text for block in response.content if block.type == "text"
    )
    return final


if __name__ == "__main__":
    result = run_agent(PREFERENCES)
    print("\n── Buying Plan ──────────────────────────────────────────────────────\n")
    print(result)