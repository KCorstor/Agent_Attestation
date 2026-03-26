from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def deterministic_issuer_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fixed 32-byte seed for tests only.
    monkeypatch.setenv("ATTESTATION_ED25519_SEED_HEX", "00" * 32)
    monkeypatch.setenv("ATTESTATION_ISSUER_DID", "did:web:attestation.local")

