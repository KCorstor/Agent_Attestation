"""Step 1 handler: verify Plaid token + create session."""

from __future__ import annotations

from typing import Any

import httpx

from attestation.schemas import InitAttestationRequest, InitAttestationResponse
from attestation.plaid.settings import load_plaid_settings
from attestation.plaid.verify import PlaidApiError, verify_access_token
from attestation.steps import session_store as sessions_module
from attestation.steps.session_store import SessionStore


def _summarize_plaid_accounts_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Strip PII-heavy fields for the API response; keep ids/counts for debugging."""
    accounts = data.get("accounts")
    n = len(accounts) if isinstance(accounts, list) else 0
    item = data.get("item") if isinstance(data.get("item"), dict) else {}
    return {
        "account_count": n,
        "item_id": item.get("item_id"),
        "institution_id": item.get("institution_id"),
    }


async def initiate_attestation(
    body: InitAttestationRequest,
    *,
    session_store: SessionStore | None = None,
    transport: httpx.BaseTransport | None = None,
) -> InitAttestationResponse:
    store = session_store if session_store is not None else sessions_module.store
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

    summary = _summarize_plaid_accounts_payload(plaid_data)
    sess = store.create(
        wallet_address=body.wallet_address,
        access_token=body.access_token,
        plaid_item_id=summary.get("item_id"),
        plaid_institution_id=summary.get("institution_id"),
        account_count=int(summary.get("account_count") or 0),
        plaid_raw_summary=summary,
    )

    return InitAttestationResponse(
        session_id=sess.session_id,
        wallet_address=sess.wallet_address,
        plaid_verified=True,
        plaid_item_id=sess.plaid_item_id,
        plaid_institution_id=sess.plaid_institution_id,
        account_count=sess.account_count,
        created_at=sess.created_at,
    )
