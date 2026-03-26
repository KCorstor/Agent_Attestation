"""
In-memory session store for the multi-step attestation flow.

Step 1 creates a session holding the access_token so Step 3 can send it to Plaid
without the client retransmitting the token in the browser if you prefer.

Production: replace with Redis/DB, encrypt tokens at rest, and enforce TTL.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AttestationSession:
    session_id: str
    wallet_address: str
    access_token: str
    created_at: datetime
    plaid_item_id: str | None = None
    plaid_institution_id: str | None = None
    account_count: int = 0
    plaid_raw_summary: dict[str, Any] = field(default_factory=dict)
    # Step 2: wallet signing challenge (set on first GET /challenge, then frozen)
    challenge_nonce: str | None = None
    challenge_message: str | None = None
    challenge_timestamp: datetime | None = None
    # Step 3: user-provided signature over the challenge message
    challenge_signature: str | None = None
    signature_submitted_at: datetime | None = None
    signature_verified: bool | None = None
    signature_recovered_address: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AttestationSession] = {}

    def create(
        self,
        *,
        wallet_address: str,
        access_token: str,
        plaid_item_id: str | None,
        plaid_institution_id: str | None,
        account_count: int,
        plaid_raw_summary: dict[str, Any],
    ) -> AttestationSession:
        sid = str(uuid.uuid4())
        sess = AttestationSession(
            session_id=sid,
            wallet_address=wallet_address,
            access_token=access_token,
            created_at=datetime.now(timezone.utc),
            plaid_item_id=plaid_item_id,
            plaid_institution_id=plaid_institution_id,
            account_count=account_count,
            plaid_raw_summary=plaid_raw_summary,
        )
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> AttestationSession | None:
        return self._sessions.get(session_id)


# Single process-wide store (swap for DI in tests if needed)
store = SessionStore()
