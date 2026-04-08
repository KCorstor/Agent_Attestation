"""Dev-only helpers to create Sandbox tokens for local testing."""

from __future__ import annotations

from typing import Any

import httpx

from attestation.plaid.settings import load_plaid_settings


async def create_sandbox_access_token(
    *,
    institution_id: str,
    initial_products: list[str],
) -> dict[str, Any]:
    """
    Creates a Sandbox access_token by calling:
    - /sandbox/public_token/create
    - /item/public_token/exchange

    This is intended ONLY for local testing; real apps should use Plaid Link.
    """
    settings = load_plaid_settings()
    base = settings.base_url.rstrip("/")
    if "sandbox" not in base:
        raise ValueError("Sandbox token helper requires PLAID_ENV=sandbox")

    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            f"{base}/sandbox/public_token/create",
            json={
                "client_id": settings.client_id,
                "secret": settings.secret,
                "institution_id": institution_id,
                "initial_products": initial_products,
            },
        )
        data = r.json()
        if r.status_code != 200:
            msg = data.get("error_message") or data.get("error_code") or "plaid_error"
            raise ValueError(msg)
        public_token = data["public_token"]

        r2 = await c.post(
            f"{base}/item/public_token/exchange",
            json={
                "client_id": settings.client_id,
                "secret": settings.secret,
                "public_token": public_token,
            },
        )
        data2 = r2.json()
        if r2.status_code != 200:
            msg = data2.get("error_message") or data2.get("error_code") or "plaid_error"
            raise ValueError(msg)

        return {
            "public_token": public_token,
            "access_token": data2["access_token"],
            "item_id": data2.get("item_id"),
        }

