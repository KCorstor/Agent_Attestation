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
from fastapi.responses import FileResponse

from attestation.schemas import (
    ChallengeResponse,
    CreateAttestationRequest,
    CreateAttestationResponse,
    DevSandboxTokenRequest,
    DevSandboxTokenResponse,
    InitAttestationRequest,
    InitAttestationResponse,
    IssueAttestationRequest,
    IssueAttestationResponse,
)
from attestation.step1 import initiate_attestation
from attestation.step2 import get_or_create_challenge
from attestation.step3_create import create_attestation_request
from attestation.issue_credential import CredentialIssuer
from attestation.did import build_did_document
from attestation.dev_plaid_sandbox import create_sandbox_access_token

app = FastAPI(title="Agent Attestation", version="0.1.0")

# Single issuer instance (key generated/loaded once at startup).
issuer = CredentialIssuer()


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


@app.post("/agent_attestation/create", response_model=CreateAttestationResponse)
async def agent_attestation_create(body: CreateAttestationRequest) -> CreateAttestationResponse:
    """
    Step 3: developer sends Plaid token + wallet signature to *this* attestation service.
    """
    try:
        return await create_attestation_request(body)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/agent_attestation/issue", response_model=IssueAttestationResponse)
async def agent_attestation_issue(body: IssueAttestationRequest) -> IssueAttestationResponse:
    """
    Step 4: Issue a signed credential after verifying Plaid token + wallet signature.
    """
    try:
        return await issuer.issue(body)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/.well-known/did.json")
def did_document() -> dict:
    """Public key for verifiers (did:web document)."""
    return build_did_document(issuer.public_key_raw())


@app.get("/")
def dev_ui() -> FileResponse:
    """Serve a tiny local UI for testing Steps 1–4."""
    return FileResponse("frontend/index.html")


@app.post("/dev/plaid/sandbox/token", response_model=DevSandboxTokenResponse)
async def dev_create_sandbox_token(body: DevSandboxTokenRequest) -> DevSandboxTokenResponse:
    """
    Dev-only helper: mint a Plaid Sandbox access_token for local testing.
    Requires PLAID_ENV=sandbox and valid API keys.
    """
    try:
        out = await create_sandbox_access_token(
            institution_id=body.institution_id,
            initial_products=body.initial_products,
        )
        return DevSandboxTokenResponse(**out)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
