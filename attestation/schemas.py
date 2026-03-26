"""Pydantic schemas for Step 1 API."""

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
