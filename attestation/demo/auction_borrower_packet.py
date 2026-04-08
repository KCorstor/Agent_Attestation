"""
Sketch: versioned JSON shape for lender auction inputs.

Aligns with:
  - `TierClaims` / credential `claims` (issuer-signed coarse signals)
  - `TransactionIntent` + `BidRfpRequest` (demo bid rails)

This is a design artifact, not a compliance guarantee. Field subsets and
redaction per bidder should be enforced by your gateway, not only by type hints.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from attestation.issuer.claims_provider import TierClaims
from attestation.schemas import TransactionIntent


class TierClaimsSnapshot(BaseModel):
    """Same keys as credential `claims` from `TierClaims.to_dict()`."""

    identityVerified: bool
    kycStatus: str
    incomeRange: str
    liquidBalanceRange: str
    authorizedSpendingLimit: str
    authorizedSpendingWindow: str

    @classmethod
    def from_tier_claims(cls, claims: TierClaims) -> TierClaimsSnapshot:
        return cls.model_validate(claims.to_dict())

    @classmethod
    def from_credential_claims(cls, claims: dict[str, Any]) -> TierClaimsSnapshot:
        return cls.model_validate(claims)


class AuctionSubjectV1(BaseModel):
    """Who the auction is for (crypto / agent handle)."""

    wallet_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    agent_id: str | None = Field(default=None, description="Optional stable agent id in your system.")
    credential_ref: str | None = Field(
        default=None,
        description="Hash or URI of issued VC; avoid embedding full credential in pre-bid fanout.",
    )


class AuctionDealV1(BaseModel):
    """Cart / intent lenders price against."""

    transaction: TransactionIntent
    country_subdivision: str | None = Field(
        default=None,
        description="ISO 3166-2 or similar, e.g. US-CA — drives licensing.",
    )
    requested_term_months: int | None = Field(default=None, ge=1, le=120)
    product_type: Literal["pay_in_4", "installment", "loc_draw", "other"] = "installment"


class IdentityFraudV1(BaseModel):
    """KYC / fraud bucket — use bands and flags, not raw PII, for broad fanout."""

    id_verification_method: str | None = Field(
        default=None,
        description="e.g. document_plus_selfie, data_only",
    )
    address_match_confidence: Literal["low", "medium", "high"] | None = None
    pep_or_sanctions_hit: bool = False
    fraud_score_band: str | None = Field(default=None, description="Vendor bucket, e.g. low_risk")


class CreditSummaryV1(BaseModel):
    """Bureau-derived or platform-derived credit signals (minimized)."""

    score_band: str | None = Field(default=None, description="e.g. 680-719 — not raw score if avoidable.")
    delinquent_tradeline: bool = False
    utilization_band: str | None = None
    inquiry_count_30d_band: str | None = None


class IncomeLiquidityV1(BaseModel):
    """Cash-flow / income — often overlaps TierClaims bands; can add Plaid-derived features."""

    income_range: str | None = None
    liquid_balance_range: str | None = None
    payroll_verified: bool = False
    dti_band: str | None = None


class AuctionPolicyHintsV1(BaseModel):
    """What the router / merchant will accept."""

    max_fee_bps: int | None = Field(default=None, ge=0, le=10_000)
    preferred_rails: list[str] = Field(default_factory=list)
    visibility: Literal["pre_bid_public", "post_win_only"] = Field(
        default="pre_bid_public",
        description="Document intent; enforcement is out of band.",
    )


class AuctionBorrowerPacketV1(BaseModel):
    """
    Single JSON-friendly object you can hash, log (redacted), or attach to an RFP.

    Typical use:
      - `pre_bid_public`: subject + deal + TierClaimsSnapshot + coarse credit/fraud bands.
      - `post_win_only`: append bureau attributes, employer name, etc. (legal review required).
    """

    schema_version: Literal["auction.borrower_packet.v1"] = "auction.borrower_packet.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    subject: AuctionSubjectV1
    deal: AuctionDealV1
    attestation_claims: TierClaimsSnapshot
    identity_fraud: IdentityFraudV1 = Field(default_factory=IdentityFraudV1)
    credit: CreditSummaryV1 = Field(default_factory=CreditSummaryV1)
    income_liquidity: IncomeLiquidityV1 = Field(default_factory=IncomeLiquidityV1)
    policy_hints: AuctionPolicyHintsV1 = Field(default_factory=AuctionPolicyHintsV1)

    def model_dump_json_sorted(self) -> str:
        """Stable JSON for hashing / `credential_ref`-style digests."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def into_bid_rfp_request_fields(self) -> dict[str, Any]:
        """
        Map into optional fields on `BidRfpRequest` + body keys `bid_rails` already reads.

        Caller still supplies `resource_url`, `protocol_hints`, `expires_at`, etc.
        """
        return {
            "wallet_address": self.subject.wallet_address,
            "agent_id": self.subject.agent_id,
            "transaction": self.deal.transaction.model_dump(exclude_none=True),
            "credit_score_band": self.credit.score_band,
            "attestation_claims": self.attestation_claims.model_dump(),
            "underwriting_notes": None,
            "max_fee_bps": self.policy_hints.max_fee_bps,
            "preferred_rails": list(self.policy_hints.preferred_rails),
        }


def build_minimal_packet(
    *,
    wallet_address: str,
    transaction: TransactionIntent,
    claims: TierClaims,
    credit_score_band: str | None = None,
    agent_id: str | None = None,
    credential_ref: str | None = None,
) -> AuctionBorrowerPacketV1:
    """Happy-path builder: TierClaims + deal + wallet; other sections default empty."""
    return AuctionBorrowerPacketV1(
        subject=AuctionSubjectV1(
            wallet_address=wallet_address,
            agent_id=agent_id,
            credential_ref=credential_ref,
        ),
        deal=AuctionDealV1(transaction=transaction),
        attestation_claims=TierClaimsSnapshot.from_tier_claims(claims),
        credit=CreditSummaryV1(score_band=credit_score_band),
        income_liquidity=IncomeLiquidityV1(
            income_range=claims.incomeRange,
            liquid_balance_range=claims.liquidBalanceRange,
        ),
    )
