# Issuing-bank bid rail — plan & what the first milestone delivers

## What you are trying to build

A **pre-rail negotiation layer**: when a payment flow hits **HTTP 402** (payment required), your system **captures intent + agent trust signals** before a generic facilitator (e.g. MPP, a wallet rail, or a merchant PSP) locks routing. **Issuing banks** (or their programs / BIN sponsors) submit **bids** (fee, SLA, limits) to **win the right to process** that transaction on their network.

Attestation fits as **one trust input** among several (credit tier, velocity limits, merchant category, etc.).

## Critical constraints (be explicit early)

1. **402 is not a payment protocol by itself** — it signals “pay to continue.” Who interprets `WWW-Authenticate`, `Payment-Required`, or x402 bodies is **your client + server contract**. You must define a **machine-readable payment request** (amount, payee, asset, deadline, idempotency key).
2. **“Before MPP”** means your agent/runtime must **call your orchestrator first** when it sees 402 — not after another library claims the flow. That is a **product integration** choice (SDK hook, middleware, reverse proxy), not something HTTP guarantees globally.
3. **Issuing banks do not typically “bid” in public auctions** in production without **legal, scheme rules, sponsor bank contracts, and PCI boundaries**. The MVP simulates **bidders**; production needs **entitled counterparties** (whitelisted issuers, RTP/FedNow program participants, card program BIN ranges, etc.).
4. **Underwriting data** is regulated: credit scores, cash flow, identity — you need **consent**, **purpose limitation**, **retention policy**, and often **direct issuer relationships** — not just a pretty JSON package.

## Phased build (recommended)

### Phase A — “402 intercept + RFP package” (initial milestone — **this repo’s MVP demo**)

**Outcome:** A **standardized Request-for-Proposal (RFP)** object you can log, sign, broadcast to a topic, and display in a UI.

Includes:

- **Transaction intent** (amount, currency, merchant id/MCC, idempotency key, expiry)
- **402 context** (resource URL, optional x402 / facilitator hints)
- **Agent identity** (wallet address, optional DID)
- **Trust bundle**:
  - Your **Plaid-backed attestation credential** (or reference + hash)
  - **Credit tier** (mock band in MVP; real bureau later)
  - Optional **velocity / limits** (mock)

**Not required yet:** real money movement, settlement, BIN routing, compliance sign-off.

### Phase B — “Broadcast + bid ingestion”

**Outcome:** A **message bus** (Kafka/SQS/NATS) or **signed webhook fan-out** where issuers consume RFPs and POST bids back.

- Define **bid schema**: fee (bps), SLA, max amount, settlement rail, risk tier accepted.
- Add **authentication** for bidders (mTLS, signed JWTs, API keys per issuer sandbox).

### Phase C — “Selection + execution handoff”

**Outcome:** Pick a winning bid under policy (lowest fee, best SLA, issuer preference), then **hand off** to execution:

- Card: tokenization / SCIM / network routing (scheme-dependent)
- RTP/FedNow: receive-only vs push payment APIs
- Crypto: facilitator / x402 completion

### Phase D — “Production governance”

- Audit logs, dispute hooks, issuer onboarding, kill switches, fraud monitoring.

## What you will have after the **initial milestone** (Phase A) is finalized

You will have:

1. A **canonical RFP JSON shape** your team agrees on.
2. A **demo server endpoint** that accepts transaction + trust fields and returns an **RFP id** + **package** ready to broadcast.
3. A **demo UI** showing: simulated **402** → **package** → **mock bids** (educational, not production banking).
4. Clear **seams** where attestation plugs in (credential embedded or referenced).

This is enough to pitch the **orchestration story** and to align engineers on data contracts before you invest in real issuer integrations.

## MVP pages in this repo

After `uvicorn main:app`:

- **`GET /demo/story`** — full pipeline with **fake Plaid + fake wallet** (`DEMO_MODE`, no API keys).
- **`GET /demo/bid-rails`** — 402 → RFP → mock bids only.
- **`GET /demo/full-flow`** — JSON for the same story (used by `/demo/story`).
