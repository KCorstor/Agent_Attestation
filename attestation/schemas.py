"""Pydantic schemas for steps 1–3."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_WALLET = re.compile(r"^0x[a-fA-F0-9]{40}$")


class InitAttestationRequest(BaseModel):
    """Developer starts binding: user already completed Link + KYC in your product."""

    access_token: str = Field(..., min_length=1, description="Plaid access_token from Link.")
    wallet_address: str = Field(
        ...,
        description="EVM address to bind after wallet proves control (Step 2).",
    )

    @field_validator("wallet_address")
    @classmethod
    def wallet_ok(cls, v: str) -> str:
        if not _WALLET.match(v):
            raise ValueError("wallet_address must be 0x followed by 40 hex characters")
        return v


class InitAttestationResponse(BaseModel):
    session_id: str
    status: str = "awaiting_wallet_signature"
    wallet_address: str
    plaid_verified: bool = True
    plaid_item_id: str | None = None
    plaid_institution_id: str | None = None
    account_count: int = 0
    created_at: datetime


class ChallengeResponse(BaseModel):
    """Payload for the browser / wallet: sign `message` with the bound address."""

    session_id: str
    wallet_address: str
    nonce: str
    timestamp: str = Field(
        ...,
        description="UTC time embedded in the message (same format as in message body).",
    )
    message: str = Field(
        ...,
        description="UTF-8 string to pass to the wallet (e.g. eth_personalSign).",
    )
    signing_note: str = Field(
        default=(
            "MetaMask and most EVM wallets apply EIP-191 when using personal_sign. "
            "Use this exact `message` string; verification must recover with the same scheme."
        ),
        description="Implementation hint for integrators (not part of the signed bytes).",
    )


_EVM_SIG_0X = re.compile(r"^0x[a-fA-F0-9]{130}$")
_EVM_SIG_NO0X = re.compile(r"^[a-fA-F0-9]{130}$")


class CreateAttestationRequest(BaseModel):
    """
    Step 3: developer sends everything to the *attestation service we are building*.

    This replaces the earlier assumption that Plaid would expose an attestation endpoint.
    """

    access_token: str = Field(..., min_length=1, description="Plaid access_token proving bank connection.")
    wallet_address: str
    message: str = Field(..., min_length=1, description="Exact challenge string the wallet signed.")
    signature: str = Field(..., description="65-byte EVM signature hex (0x prefix optional).")

    @field_validator("wallet_address")
    @classmethod
    def wallet_ok2(cls, v: str) -> str:
        if not _WALLET.match(v):
            raise ValueError("wallet_address must be 0x followed by 40 hex characters")
        return v

    @field_validator("signature")
    @classmethod
    def sig_ok(cls, v: str) -> str:
        raw = v.strip()
        if _EVM_SIG_0X.match(raw):
            return raw
        if _EVM_SIG_NO0X.match(raw):
            return "0x" + raw
        raise ValueError("signature must be 65 bytes hex (130 chars), with optional 0x prefix")


class CreateAttestationResponse(BaseModel):
    status: str = "attestation_request_verified"
    wallet_address: str
    verified_wallet_signature: bool
    recovered_address: str
    plaid_item_id: str | None = None
    plaid_institution_id: str | None = None
    account_count: int | None = None


class IssueAttestationRequest(BaseModel):
    """
    Step 4: after Step 3 verification, issue a signed credential.

    For now we only support a fixed claims set (mock tiers) because real income/identity
    products require additional Plaid endpoints and permissions beyond /accounts/get.
    """

    access_token: str = Field(..., min_length=1)
    wallet_address: str
    message: str = Field(..., min_length=1)
    signature: str
    expires_at: datetime = Field(..., description="Credential expiry (ISO8601).")

    @field_validator("wallet_address")
    @classmethod
    def wallet_ok3(cls, v: str) -> str:
        if not _WALLET.match(v):
            raise ValueError("wallet_address must be 0x followed by 40 hex characters")
        return v

    @field_validator("signature")
    @classmethod
    def sig_ok2(cls, v: str) -> str:
        raw = v.strip()
        if _EVM_SIG_0X.match(raw):
            return raw
        if _EVM_SIG_NO0X.match(raw):
            return "0x" + raw
        raise ValueError("signature must be 65 bytes hex (130 chars), with optional 0x prefix")


class IssueAttestationResponse(BaseModel):
    credential: dict


class DevSandboxTokenRequest(BaseModel):
    institution_id: str = Field(..., min_length=1)
    initial_products: list[str] = Field(default_factory=lambda: ["transactions"])


class DevSandboxTokenResponse(BaseModel):
    access_token: str
    public_token: str
    item_id: str | None = None


class TransactionIntent(BaseModel):
    """Proposed payment the issuer may bid to process (demo)."""

    amount_cents: int = Field(..., ge=1)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    merchant_id: str | None = None
    mcc: str | None = Field(default=None, description="Merchant category code")
    description: str | None = None
    idempotency_key: str | None = None


class BidRfpRequest(BaseModel):
    """Build a broadcastable RFP package (demo — not a real issuer auction)."""

    resource_url: str | None = Field(default=None, description="URL that returned HTTP 402.")
    transaction: TransactionIntent
    wallet_address: str | None = None
    agent_id: str | None = None
    credential: dict | None = Field(default=None, description="Issued credential JSON from /agent_attestation/issue.")
    include_full_credential: bool = False
    credit_score_band: str | None = None
    attestation_claims: dict | None = None
    underwriting_notes: str | None = None
    max_fee_bps: int | None = Field(default=None, ge=0, le=10_000)
    preferred_rails: list[str] = Field(default_factory=list)
    protocol_hints: list[str] = Field(default_factory=lambda: ["before_mpp_facilitator"])
    expires_at: str | None = Field(default=None, description="ISO8601 RFP expiry.")


class BidRecord(BaseModel):
    issuer_id: str
    issuer_label: str
    fee_bps: int
    estimated_settlement_ms: int
    score: float
    note: str


class BidRfpResponse(BaseModel):
    rfp_id: str
    package: dict
    bids: list[BidRecord]
