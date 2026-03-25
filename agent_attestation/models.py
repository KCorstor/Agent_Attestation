"""Request/response and domain models."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from agent_attestation.constants import MAX_ATTESTATION_DAYS

_ETH_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")


class AttestationScope(str, Enum):
    identity = "identity"
    income_tier = "income_tier"
    balance_tier = "balance_tier"
    spending_authority = "spending_authority"


class CreateAttestationRequest(BaseModel):
    """HTTP body for POST /agent_attestation/create."""

    access_tokens: list[str] = Field(
        ...,
        min_length=1,
        description="Plaid access token(s) from Link (not validated against Plaid in this service).",
    )
    wallet_address: str = Field(..., description="EVM-style address bound to this attestation.")
    scopes: list[AttestationScope] = Field(
        ...,
        min_length=1,
        description="Which claim groups to include.",
    )
    expires_at: datetime = Field(
        ...,
        description="Credential expiry (must be after issuance and within max TTL).",
    )

    @field_validator("access_tokens")
    @classmethod
    def non_blank_tokens(cls, v: list[str]) -> list[str]:
        if any(not (t and t.strip()) for t in v):
            raise ValueError("access_tokens must be non-empty strings")
        return v

    @field_validator("wallet_address")
    @classmethod
    def wallet_format(cls, v: str) -> str:
        if not _ETH_ADDRESS.match(v):
            raise ValueError("wallet_address must match 0x + 40 hex characters")
        return v

    @field_validator("scopes")
    @classmethod
    def unique_scopes(cls, v: list[AttestationScope]) -> list[AttestationScope]:
        seen: set[str] = set()
        out: list[AttestationScope] = []
        for s in v:
            key = s.value
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
        return out


class VerifiedFinancialProfile(BaseModel):
    """Result of Plaid-side verification (mocked here)."""

    identity_verified: bool
    kyc_status: str
    income_range: str
    liquid_balance_range: str
    authorized_spending_limit: str
    authorized_spending_window: str


def validate_expiry(
    issued_at: datetime,
    expires_at: datetime,
    *,
    max_days: int = MAX_ATTESTATION_DAYS,
) -> None:
    if expires_at <= issued_at:
        raise ValueError("expires_at must be after issuance time")
    max_seconds = max_days * 86400
    if (expires_at - issued_at).total_seconds() > max_seconds:
        raise ValueError(f"attestation TTL cannot exceed {max_days} days")
