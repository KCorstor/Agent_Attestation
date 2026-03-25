# Agent Attestation — Design

## End-to-end flow (what you are building)

1. **Bank connection (existing Plaid Link)** — User completes Link; your backend stores Plaid `access_token`(s). No code in this repo calls Plaid Link; that lives in your app.
2. **Create attestation** — Your backend calls `POST /agent_attestation/create` with access tokens, wallet address, requested **scopes**, and **expiry**. This service (or a future Plaid product) runs verification and returns a signed credential.
3. **Verification (Plaid-internal today)** — Income, identity, balances are computed with Plaid’s existing products. **This repository does not call Plaid HTTP APIs**; it defines an interface and ships a **mock provider** so logic and tests run without secrets.
4. **Output** — A JSON object shaped like your spec, with `proof.type` = `Ed25519Signature2020` and a `proofValue` that covers the payload without `proof`.
5. **Consumption** — Downstream systems (KYAPay, AgentKit, x402, etc.) verify signature, expiry, wallet match, and policy against **claims**.

## What cannot be completed in this repo (external resources)

| Requirement | Status |
|-------------|--------|
| Real Plaid verification (Identity, Income, Balance, etc.) | **Not included.** Needs Plaid API keys, approved products, and server-side calls to Plaid endpoints using stored `access_token`s. The mock provider simulates outcomes only. |
| Hosting `did:web:attestation.plaid.com` with a real HTTPS DID document | **Not included.** Resolution is implemented as a **local static DID document** served by this app at `GET /.well-known/did.json` for development; production would use Plaid’s domain and TLS. |
| Full W3C Verifiable Credentials Data Model + RDF Dataset Canonicalization | **Simplified.** Production VC-LD often uses RDFC for signing. This project uses **deterministic JSON** (sorted keys, compact separators) over the credential **minus `proof`**, documented below. Upgrading to RDFC or **VC-JWT** is an explicit migration path. |
| ZK / selective disclosure | **Out of scope**; ranges are plain JSON tiers (privacy-preserving by bucket, not cryptographic ZK). |

## Design decisions (and why)

### Ranges instead of exact balances/income

**Decision:** Claims use string tiers (e.g. `50k-100k`) from a fixed catalog.

**Why:** Matches your privacy model; verifiers only need risk bands. Exact values never appear in the credential.

### Wallet binding

**Decision:** `walletAddress` is required at creation and embedded in the credential; verifiers must compare it to the transacting wallet.

**Why:** This is the anchor between off-chain identity/financial signals and on-chain or agent identity.

### Scopes

**Decision:** Request body lists `scopes`; the issuer includes only claims the provider can satisfy under policy.

**Why:** Prevents over-claiming; mirrors OAuth-style scoping and keeps the API explicit.

### Ed25519 + `Ed25519Signature2020`-style proof

**Decision:** Sign a canonical UTF-8 JSON string of the document **without** `proof`, using Ed25519; `proofValue` is **multibase** (`z` + base58btc of raw 64-byte signature).

**Why:** Ed25519 is standard, fast, and fits DID `Ed25519VerificationKey2020`. Multibase matches common VC examples. **Caveat:** This is a deliberate simplification vs full VC-LD RDF signing.

### Single credential JSON (not nested `credentialSubject` only)

**Decision:** The HTTP response matches your flat example (`walletAddress`, `claims`, …) for easy embedding in other JWT stacks.

**Why:** Interop with partners that want one JSON blob; you can map to full VC-LD later without changing verifier logic much.

## API

### `POST /agent_attestation/create`

**Request (JSON):**

- `access_tokens` (array of strings, required): Plaid access tokens from Link (validated non-empty; **not** verified against Plaid in this repo).
- `wallet_address` (string, required): e.g. Ethereum `0x` + 40 hex.
- `scopes` (array of enum strings, required): subset of `identity`, `income_tier`, `balance_tier`, `spending_authority`.
- `expires_at` (ISO 8601 datetime, required): must be after `issued_at` and within configured max TTL.

**Response:** Credential JSON including `proof`.

### `GET /.well-known/did.json`

Returns a `did:web`-style document with `verificationMethod` for `#key-1` so verifiers can load the public key (when this service is the trust anchor).

## Code map

| Module | Role |
|--------|------|
| `agent_attestation/models.py` | Request validation, expiry/TTL rules, wallet format |
| `agent_attestation/claims_builder.py` | Scope → `claims` object (camelCase) |
| `agent_attestation/verification_provider.py` | `MockVerificationProvider` (no network) |
| `agent_attestation/plaid_live.py` | **Stub** documenting a future Plaid-backed provider |
| `agent_attestation/issuer.py` | Build unsigned credential + Ed25519 sign |
| `agent_attestation/verifier.py` | Signature, expiry, optional wallet match |
| `agent_attestation/did_document.py` | `did.json` for key discovery |
| `agent_attestation/api.py` | `POST /agent_attestation/create`, `GET /.well-known/did.json` |

## Reflection (coherence checks)

- **Same key for signing and DID:** The issuer’s Ed25519 public key is exposed at `/.well-known/did.json` so verifiers can obtain the key without a proprietary registry — tests assert multibase coherence.
- **Scopes reduce leakage:** Claims are filtered server-side so the credential never contains tiers the integrator did not request (aligns with selective disclosure goals, pre-ZK).
- **Canonical bytes:** Issuer and verifier share one function for the signed payload; tampering any field invalidates the signature.
- **Mock vs Plaid:** Only `VerificationProvider.verify()` swaps; HTTP API and crypto stay unchanged when Plaid is wired in.

## Running tests

```bash
cd /Users/kevincorstorphine/Desktop/Agent_Attestation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Running the API locally

```bash
uvicorn agent_attestation.api:app --reload --port 8000
```

Create attestation (example):

```bash
curl -s -X POST http://127.0.0.1:8000/agent_attestation/create \
  -H "Content-Type: application/json" \
  -d '{"access_tokens":["access-sandbox-xxx"],"wallet_address":"0x0000000000000000000000000000000000000001","scopes":["identity","income_tier","balance_tier","spending_authority"],"expires_at":"2026-06-25T00:00:00Z"}'
```
