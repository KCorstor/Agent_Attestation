# MPP Tempo example (no Stripe)

Minimal [Machine Payments Protocol](https://mpp.dev) **server + agent** using **Tempo** (pathUSD on **Tempo Moderato** testnet) via [`mppx`](https://www.npmjs.com/package/mppx). No Stripe or Shared Payment Tokens.

## Why `tempo.charge` and not `tempo()`?

This server uses **`tempo.charge` only**, not **`tempo()`**. The full **`tempo()`** helper also registers **`session`** (streaming / payment-channel flows). **`tempo.session()`** on the server requires a **signing account** (`privateKeyToAccount(...)`), not just a recipient address — so for a small demo we register **one-shot TIP-20 charges** only.

The agent matches that: **`tempo.charge({ account })`**, not the full client **`tempo()`** bundle.

## Prerequisites

- **Node.js 22+** (recommended; `mppx` may warn on older Node)
- **`mpp_tempo_example/.env`** with at least **`MPP_SECRET_KEY`**, **`TEMPO_PRIVATE_KEY`**, **`TEMPO_RECIPIENT_ADDRESS`**, and **`MPP_AUCTION_TERMS_FILE`** (see **`.env.example`**). The payer wallet should hold testnet **pathUSD** on **Moderato**.
- Nothing from Stripe

## Setup and run

```bash
cd mpp_tempo_example
npm install
```

Ensure **`.env`** is filled (copy from **`.env.example`** if needed). Then:

**Terminal 1 — server**

```bash
npm start
```

Default: `http://127.0.0.1:4243`

**Terminal 2 — agent** (needs **`MPP_AUCTION_TERMS_FILE`** in **`.env`**; see below)

```bash
npm run agent
```

The agent calls **`mppx.fetch`** on **`GET /paid`**. After **402**, it **waits** until the terms JSON file exists, then **`mppx`** pays and retries.

### 402 intercept → bundle (auction prep)

When the server returns **402**, **`mppx`** parses the **`Payment`** challenge from **`WWW-Authenticate`**, then (by default) builds a credential and retries. This demo hooks that path in **`agent.mjs`**:

1. **`createCapture402Fetch()`** (`payment_bundle.mjs`) wraps the underlying **`fetch`** so the raw **402** response headers are captured.
2. **`Mppx.create({ fetch, onChallenge })`** — on the first **402**, **`onChallenge(challenge)`** runs with the parsed **`challenge`** (amount, currency, recipient, `id`, etc.).
3. **`buildPaymentBundle({ challenge, capture402 })`** turns that into JSON you can send to an auction later.
4. **`attachMockIssuingTerms(bundle)`** (`mock_auction_issuer.mjs`) is a **separate** stub that layers mock auction + mock bank metadata on the bundle; replace it with your real auction/issuer response.
5. Returning **`undefined`** from **`onChallenge`** keeps the stock behavior: **`mppx`** creates the Tempo credential and completes the request.

Optional: set **`MPP_BUNDLE_OUT=./last-bundle.json`** in **`.env`** to write the bundle to disk.

Replay mock issuer on a saved file:

```bash
node mock_auction_issuer.mjs ./last-bundle.json
```

### Auction terms file (required before payment)

**`MPP_AUCTION_TERMS_FILE`** must point to a path where **valid JSON** will appear. The agent **never** signs until that file can be read and **`defaultAcceptTerms()`** says the deal may proceed (see **`auction_gate.mjs`**).

- **Time-based pings:** while waiting, the agent logs **`[auction ping …]`** at most every **`MPP_AUCTION_PING_INTERVAL_MS`** (default **2000**). Set **`MPP_AUCTION_QUIET=1`** to silence pings.
- **Continue vs wait vs abort:** parsed JSON is checked each poll. If **`mockAuction.status`** is **`pending`**, the agent keeps waiting. If **`rejected`** or **`proceed: false`**, it **aborts** (throws). If **`cleared_for_issuance`** (or no mock blockers), it **pays**.

Example shape (also committed as **`examples/terms.json`** — copy to your **`./terms.json`** path if you want a static sample; **`npm run auction:release`** normally generates it from the real bundle):

`mpp_tempo_example/examples/terms.json`

Two-terminal demo (same `.env` keys):

```bash
# Terminal A — blocks after 402 until terms file exists (set paths in .env or here)
MPP_BUNDLE_OUT=./bundle.json MPP_AUCTION_TERMS_FILE=./terms.json npm run agent

# Terminal B — writes mock winner JSON to the path the agent waits on
MPP_BUNDLE_OUT=./bundle.json MPP_AUCTION_TERMS_FILE=./terms.json npm run auction:release
```

**Other agents:** use **`createAuctionGate`** with your own **`waitForTerms`** (HTTP, queue, etc.), or **`waitForTermsFromEnv()`** if you want the wait to be optional. If the agent already has **`onChallenge`**, use **`chainOnChallenge(gate.onChallenge, yourHandler)`** — keep **`gate.onChallenge` first.

## Quick test (402 only)

```bash
curl -i http://127.0.0.1:4243/paid
```

Expect **HTTP 402** with `WWW-Authenticate: Payment ... method="tempo" ...`.

## Optional: generate wallet and faucet (first time)

If you **don’t** have a **`TEMPO_PRIVATE_KEY`** yet, from **`mpp_tempo_example`** run:

```bash
npm run wallet:setup
```

Or: `node setup-wallet.mjs`

That creates/updates **`.env`** with **`MPP_SECRET_KEY`**, **`TEMPO_PRIVATE_KEY`**, **`TEMPO_ADDRESS`**, **`TEMPO_RECIPIENT_ADDRESS`**, and hits the **Moderato faucet** when it creates a new key. You do **not** need to run this every time — **`.env`** is the source of truth (gitignored; back it up locally).

- **Top up testnet funds:** `npm run wallet:setup -- --fund`
- **New key (destructive):** `npm run wallet:setup -- --force`

**Alternative (manual):** `npx mppx account create` and `npx mppx account fund`, then put that account’s private key in **`TEMPO_PRIVATE_KEY`**.

**Seeing an empty `TEMPO_PRIVATE_KEY` in the editor?** Reload **`.env`** from disk. **`TEMPO_ADDRESS`** is the public address (safe to read).

### Troubleshooting `wallet:setup`

1. Run **inside** **`mpp_tempo_example/`** — there is no `wallet:setup` at the repo root.
2. Check the path printed as `setup-wallet: writing …` — it must be **`mpp_tempo_example/.env`**.
3. Faucet needs network; if it fails, the key may still be written — use **`--fund`** later.

## Amount encoding

The **`/paid`** route uses **`amount: "0.1"`** with **`decimals: 6`** (human-style amount). Do not pass smallest-unit strings like `"100000"` here — `mppx` applies **`parseUnits(amount, decimals)`**, which would mis-scale raw integers.
