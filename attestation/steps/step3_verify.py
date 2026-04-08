"""Step 3: create (verify) an attestation request on our service."""

from __future__ import annotations

from typing import Any

import httpx

from attestation.crypto.evm_personal_sign import addresses_match, recover_personal_sign_address
from attestation.plaid.settings import load_plaid_settings
from attestation.plaid.verify import PlaidApiError, verify_access_token
from attestation.schemas import CreateAttestationRequest, CreateAttestationResponse


def _summarize_plaid_accounts_payload(data: dict[str, Any]) -> dict[str, Any]:
    accounts = data.get("accounts")
    n = len(accounts) if isinstance(accounts, list) else 0
    item = data.get("item") if isinstance(data.get("item"), dict) else {}
    return {
        "account_count": n,
        "item_id": item.get("item_id"),
        "institution_id": item.get("institution_id"),
    }


async def create_attestation_request(
    body: CreateAttestationRequest,
    *,
    transport: httpx.BaseTransport | None = None,
) -> CreateAttestationResponse:
    """
    Verifies:
    - Plaid `access_token` works (via /accounts/get)
    - Signature recovers the claimed `wallet_address` (EVM personal_sign / EIP-191)

    Returns a verified response suitable to feed into an issuance step (Step 5).
    """
    settings = load_plaid_settings()
    try:
        plaid_data = await verify_access_token(
            base_url=settings.base_url,
            client_id=settings.client_id,
            secret=settings.secret,
            access_token=body.access_token,
            transport=transport,
        )
    except PlaidApiError as e:
        raise ValueError(f"Plaid rejected access_token: {e}") from e

    recovered = recover_personal_sign_address(message=body.message, signature=body.signature)
    verified = addresses_match(recovered, body.wallet_address)
    if not verified:
        raise ValueError("wallet signature does not match wallet_address")

    summary = _summarize_plaid_accounts_payload(plaid_data)
    return CreateAttestationResponse(
        wallet_address=body.wallet_address,
        verified_wallet_signature=True,
        recovered_address=recovered,
        plaid_item_id=summary.get("item_id"),
        plaid_institution_id=summary.get("institution_id"),
        account_count=int(summary.get("account_count") or 0),
    )

