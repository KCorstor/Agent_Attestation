"""Call Plaid to prove an access_token is valid (Step 1 gate)."""

from __future__ import annotations

from typing import Any

import httpx

from attestation.config import is_demo_mode


def _demo_accounts_get_payload() -> dict[str, Any]:
    """Fake Plaid /accounts/get — used only when DEMO_MODE=1."""
    return {
        "accounts": [
            {"account_id": "acc_demo_checking", "name": "Demo Checking"},
            {"account_id": "acc_demo_savings", "name": "Demo Savings"},
        ],
        "item": {
            "item_id": "item_demo_001",
            "institution_id": "ins_demo_bank",
        },
    }


class PlaidApiError(Exception):
    """Plaid returned a non-success response."""

    def __init__(self, status_code: int, body: dict[str, Any] | None) -> None:
        self.status_code = status_code
        self.body = body or {}
        msg = self.body.get("error_message") or self.body.get("error_code") or "plaid_error"
        super().__init__(msg)


async def verify_access_token(
    *,
    base_url: str,
    client_id: str,
    secret: str,
    access_token: str,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """
    POST /accounts/get — confirms the Item exists and the token works.

    This does not prove KYC by itself; your product setup (Identity, etc.) does.
    Step 1 uses this as a minimal "bank still linked" check before binding.
    """
    if is_demo_mode():
        return _demo_accounts_get_payload()

    url = f"{base_url.rstrip('/')}/accounts/get"
    payload = {
        "client_id": client_id,
        "secret": secret,
        "access_token": access_token,
    }
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post(url, json=payload, timeout=30.0)

    try:
        data = response.json()
    except Exception:  # noqa: BLE001 — surface raw text
        data = {"raw": response.text}

    if response.status_code != 200:
        raise PlaidApiError(response.status_code, data if isinstance(data, dict) else None)

    return data if isinstance(data, dict) else {}
