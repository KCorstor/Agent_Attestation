"""
Real HTTP 402 (x402) checkout using Coinbase's Python SDK.

Default resource (Base Sepolia testnet, ~$0.01 USDC):
  https://x402.palpaxai.network/api/base-sepolia/paid-content

That endpoint returns JSON with x402Version 1 and X-PAYMENT flow; the SDK handles
both v1 and v2. Alternatives with the same pattern:
  https://x402.payai.network/api/base-sepolia/paid-content

Wallet setup (testnet — real on-chain tx, tiny cost):
  - Create / import an EVM wallet; export private key as EVM_PRIVATE_KEY in .env
  - Get Base Sepolia ETH: https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet
  - Get Base Sepolia USDC (same chain the echo uses): use a Base Sepolia USDC faucet
    or bridge from testnet sources; you need enough for maxAmountRequired (~0.01 USDC)
    plus gas.

Production / mainnet: use CDP facilitator + Base mainnet USDC; see:
  https://docs.base.org/ai-agents/payments/pay-for-services-with-x402
  https://github.com/coinbase/x402/tree/main/examples/python/clients/httpx

Facilitator (reference): https://x402.org/facilitator
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from eth_account import Account

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEFAULT_X402_PAID_URL = (
    "https://402payment-test.com/api/x402"
)


async def fetch_paid_url(
    url: str,
    *,
    evm_private_key: str,
    timeout: float = 120.0,
) -> tuple[httpx.Response, dict[str, Any] | None]:
    """
    GET ``url``; on 402, sign and pay via x402, retry automatically.

    Returns (final_response, settlement_dict_or_none).
    """
    from x402 import x402Client
    from x402.http import x402HTTPClient
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    raw = evm_private_key.strip()
    if raw.startswith("0x"):
        raw = raw[2:]
    account = Account.from_key("0x" + raw)

    client = x402Client()
    register_exact_evm_client(client, EthAccountSigner(account))
    http_helper = x402HTTPClient(client)

    async with x402HttpxClient(client) as http:
        response = await http.get(url, timeout=timeout)
        await response.aread()

    settle: dict[str, Any] | None = None
    try:
        sr = http_helper.get_payment_settle_response(lambda name: response.headers.get(name))
        settle = sr.model_dump()
    except ValueError:
        pass

    return response, settle


async def _cli_main() -> None:
    import json
    import sys

    url = (os.environ.get("X402_PAID_URL") or DEFAULT_X402_PAID_URL).strip()
    pk = os.environ.get("EVM_PRIVATE_KEY", "").strip()
    if not pk:
        print(
            "Set EVM_PRIVATE_KEY in .env (wallet with gas + USDC for the resource's chain).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"GET {url}\n", flush=True)
    resp, settle = await fetch_paid_url(url, evm_private_key=pk)
    print(f"Status: {resp.status_code}\n")
    body = resp.text
    print(body[:8000] + ("…" if len(body) > 8000 else ""))
    if settle:
        print("\n── Settlement ──\n")
        print(json.dumps(settle, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(_cli_main())
