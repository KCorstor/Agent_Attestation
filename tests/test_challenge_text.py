from datetime import datetime, timezone

from attestation.challenge_text import build_challenge_message, format_challenge_timestamp


def test_timestamp_format() -> None:
    dt = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    assert format_challenge_timestamp(dt) == "2026-03-25T12:00:00Z"


def test_message_includes_nonce_and_wallet() -> None:
    dt = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    m = build_challenge_message(
        wallet_address="0x0000000000000000000000000000000000000001",
        nonce="8f3a92b1",
        timestamp_utc=dt,
    )
    assert "8f3a92b1" in m
    assert "0x0000000000000000000000000000000000000001" in m
    assert "2026-03-25T12:00:00Z" in m
    assert "Plaid" in m
