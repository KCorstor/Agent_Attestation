import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Mock "auction result" + mock bank issuing terms layered on top of a payment bundle.
 *
 * This does NOT talk to Tempo or sign transactions — it is a stub you can replace with:
 *   bundle → real auction → real issuer → (later) feed credentials back into mppx.
 *
 * Typical flow after your auction exists:
 *   1. Agent or proxy sends `buildPaymentBundle(...)` JSON to the auction.
 *   2. Auction returns approval + issuer terms (this file mocks that response shape).
 *   3. Your code completes payment using `mppx.createCredential(response)` or the
 *      `createCredential` helper from `onChallenge` — same as the stock Tempo agent.
 */

/**
 * @param {object} bundle - Output of `buildPaymentBundle()` (or compatible JSON).
 * @param {object} [options]
 * @param {string} [options.auctionId]
 */
export function attachMockIssuingTerms(bundle, options = {}) {
  const auctionId = options.auctionId ?? `mock-auction-${Date.now()}`;
  const challenge = bundle.challenge;

  return {
    ...bundle,
    mockAuction: {
      auctionId,
      status: "cleared_for_issuance",
      settledAt: new Date().toISOString(),
      note: "Replace with real auction result payload when wired up.",
    },
    mockBank: {
      issuerId: "mock-bank-moderato-demo",
      issuerName: "Mock Issuer (replace with your bank)",
      programId: "mock-pathusd-program",
      /** Terms you might merge into a real issuer workflow */
      issuingTerms: {
        asset: "pathUSD",
        network: "Tempo Moderato (testnet)",
        maxAmountMinorUnits: challenge?.request?.amount ?? null,
        currencyContract: challenge?.request?.currency ?? null,
        validHours: 24,
        aprPercent: "0.00",
      },
      /** Placeholder attestation your real bank might attach */
      attestation: {
        format: "mock-jwt-placeholder",
        token: "eyJhbGciOiJub25lIn0.eyJtb2NrIjp0cnVlfQ.",
      },
    },
    /** How this connects back to the existing agent */
    integration: {
      mppChallengeId: challenge?.id ?? null,
      nextStep:
        "To finish the HTTP transaction on-device, call the mppx `createCredential` path with the original 402 challenge (see agent.mjs onChallenge). Mock bank terms are parallel metadata until you implement issuer-driven credentials.",
    },
  };
}

/** CLI: `node mock_auction_issuer.mjs < bundle.json` — prints mock-wrapped JSON to stdout */
async function main() {
  const path = process.argv[2];
  if (!path) {
    console.error("Usage: node mock_auction_issuer.mjs <bundle.json>");
    process.exit(1);
  }
  const { readFile } = await import("node:fs/promises");
  const raw = await readFile(path, "utf8");
  const bundle = JSON.parse(raw);
  const out = attachMockIssuingTerms(bundle);
  process.stdout.write(`${JSON.stringify(out, null, 2)}\n`);
}

const isMain =
  resolve(fileURLToPath(import.meta.url)) === resolve(process.argv[1] ?? "");
if (isMain && process.argv[2]) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
