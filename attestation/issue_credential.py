"""Step 4: issue a signed credential after verification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from attestation.canonical_json import canonical_json_bytes
from attestation.claims_provider import ClaimsProvider, MockClaimsProvider
from attestation.ed25519_keys import load_or_generate_private_key, public_key_raw_32
from attestation.issuer_config import issuer_did, verification_method_id
from attestation.multibase import mb58_encode
from attestation.schemas import IssueAttestationRequest, IssueAttestationResponse
from attestation.step3_create import create_attestation_request


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CredentialIssuer:
    def __init__(
        self,
        *,
        signing_key: Ed25519PrivateKey | None = None,
        claims_provider: ClaimsProvider | None = None,
    ) -> None:
        self._sk = signing_key or load_or_generate_private_key()
        self._claims = claims_provider or MockClaimsProvider()

    def public_key_raw(self) -> bytes:
        return public_key_raw_32(self._sk)

    async def issue(
        self,
        body: IssueAttestationRequest,
        *,
        transport: httpx.BaseTransport | None = None,
        issued_at: datetime | None = None,
    ) -> IssueAttestationResponse:
        # Reuse Step 3 verification path (Plaid token + wallet signature).
        verified = await create_attestation_request(
            body,  # compatible fields
            transport=transport,
        )

        now = issued_at or datetime.now(timezone.utc)
        exp = body.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            raise ValueError("expires_at must be after issuance time")

        claims = self._claims.derive_claims(
            plaid_accounts_summary={
                "plaid_item_id": verified.plaid_item_id,
                "plaid_institution_id": verified.plaid_institution_id,
                "account_count": verified.account_count,
            }
        ).to_dict()

        unsigned: dict[str, Any] = {
            "walletAddress": body.wallet_address,
            "issuedBy": issuer_did(),
            "issuanceDate": _iso_z(now),
            "expiryDate": _iso_z(exp),
            "claims": claims,
        }

        sig = self._sk.sign(canonical_json_bytes(unsigned))
        credential = {
            **unsigned,
            "proof": {
                "type": "Ed25519Signature2020",
                "verificationMethod": verification_method_id(),
                "proofValue": mb58_encode(sig),
            },
        }
        return IssueAttestationResponse(credential=credential)

