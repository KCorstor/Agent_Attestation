"""Step 2: expose the signing challenge for a session."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from attestation import sessions as sessions_module
from attestation.challenge_text import build_challenge_message, format_challenge_timestamp
from attestation.schemas import ChallengeResponse
from attestation.sessions import SessionStore


def get_or_create_challenge(
    session_id: str,
    *,
    session_store: SessionStore | None = None,
    now: datetime | None = None,
) -> ChallengeResponse:
    """
    Return the message the end user must sign with their wallet.

    The first call generates a random nonce and freezes `message` on the session.
    Later calls return the same values so retries and page reloads stay consistent.
    """
    store = session_store if session_store is not None else sessions_module.store
    sess = store.get(session_id)
    if sess is None:
        raise LookupError("unknown session")

    if sess.challenge_message is not None:
        assert sess.challenge_nonce is not None
        assert sess.challenge_timestamp is not None
        ts_str = format_challenge_timestamp(sess.challenge_timestamp)
        return ChallengeResponse(
            session_id=sess.session_id,
            wallet_address=sess.wallet_address,
            nonce=sess.challenge_nonce,
            timestamp=ts_str,
            message=sess.challenge_message,
        )

    when = now or datetime.now(timezone.utc)
    nonce = secrets.token_hex(8)
    message = build_challenge_message(
        wallet_address=sess.wallet_address,
        nonce=nonce,
        timestamp_utc=when,
    )
    sess.challenge_nonce = nonce
    sess.challenge_message = message
    sess.challenge_timestamp = when

    return ChallengeResponse(
        session_id=sess.session_id,
        wallet_address=sess.wallet_address,
        nonce=nonce,
        timestamp=format_challenge_timestamp(when),
        message=message,
    )
