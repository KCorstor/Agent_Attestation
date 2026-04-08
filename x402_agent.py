#!/usr/bin/env python3
"""
Single-purpose agent: pay an x402-protected URL and print the response.

No TV research, no Anthropic — only:
  GET → 402 → sign + USDC payment (via Coinbase x402 SDK) → retry → 200.

For the same payment with Claude + web search + narrated demo, use Checkout402_Agent.py.

Env (.env):
  EVM_PRIVATE_KEY  — required; wallet with gas + USDC on the chain the resource uses
  X402_PAID_URL    — optional default target if you omit --url

Run:
  python x402_agent.py
  python x402_agent.py --url https://x402.payai.network/api/base-sepolia/paid-content

Faucets / defaults: see x402_checkout.py module docstring.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from x402_checkout import DEFAULT_X402_PAID_URL, fetch_paid_url


def main() -> None:
    p = argparse.ArgumentParser(
        description="x402-only agent: checkout at a paid HTTP endpoint (stablecoin).",
    )
    p.add_argument(
        "--url",
        default=None,
        help=f"402-gated URL (default: X402_PAID_URL env or {DEFAULT_X402_PAID_URL})",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout seconds (default: 120)",
    )
    args = p.parse_args()

    url = (args.url or os.environ.get("X402_PAID_URL") or DEFAULT_X402_PAID_URL).strip()
    pk = os.environ.get("EVM_PRIVATE_KEY", "").strip()
    if not pk:
        print(
            "Missing EVM_PRIVATE_KEY in environment (.env).\n"
            "Use a wallet funded on the network required by the resource (e.g. Base Sepolia ETH + USDC for default echo).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"x402 agent → GET {url}\n", flush=True)

    async def run() -> None:
        resp, settle = await fetch_paid_url(url, evm_private_key=pk, timeout=args.timeout)
        print(f"Final status: {resp.status_code}\n")
        body = resp.text
        print(body[:8000] + ("…" if len(body) > 8000 else ""))
        if settle:
            print("\n── Settlement ──\n")
            print(json.dumps(settle, indent=2))

    asyncio.run(run())


if __name__ == "__main__":
    main()
