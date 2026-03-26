"""
Agent attestation API — Steps 1–2.

Run (after exporting PLAID_* or using a .env file):
  uvicorn main:app --reload --port 8000

Load .env automatically if python-dotenv is installed.
"""

from __future__ import annotations

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException

from attestation.schemas import ChallengeResponse, InitAttestationRequest, InitAttestationResponse
from attestation.step1 import initiate_attestation
from attestation.step2 import get_or_create_challenge

app = FastAPI(title="Agent Attestation", version="0.1.0")


@app.post("/attestation/init", response_model=InitAttestationResponse)
async def attestation_init(body: InitAttestationRequest) -> InitAttestationResponse:
    """
    Step 1: Developer initiates binding verified Plaid identity to a wallet address.

    - Confirms the Plaid `access_token` works via `/accounts/get`.
    - Creates a server session for later steps (wallet signature, full Plaid request).
    """
    try:
        return await initiate_attestation(body)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get(
    "/attestation/sessions/{session_id}/challenge",
    response_model=ChallengeResponse,
)
def attestation_challenge(session_id: str) -> ChallengeResponse:
    """
    Step 2: Return the exact message the user must sign with their wallet.

    Idempotent: the same session always receives the same `message` after the first call.
    """
    try:
        return get_or_create_challenge(session_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
