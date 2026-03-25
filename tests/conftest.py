"""Ensure deterministic issuer key and reset singleton between tests."""

from __future__ import annotations

import os

import pytest

# Fixed Ed25519 seed (32 bytes) — tests only; never use in production.
# Set at import time so `import agent_attestation.api` in test modules sees it.
_TEST_SEED_HEX = "00" * 32
os.environ["PLAID_ATTESTATION_ED25519_SEED_HEX"] = _TEST_SEED_HEX


@pytest.fixture(autouse=True)
def reset_cached_issuer() -> None:
    from agent_attestation.api import reset_issuer_singleton

    reset_issuer_singleton()
    yield
    reset_issuer_singleton()
