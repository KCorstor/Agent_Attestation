/**
 * Minimal MPP agent — pays GET /paid using Tempo (pathUSD on Moderato testnet).
 *
 * 402 intercept: when the merchant returns HTTP 402, `onChallenge` runs before the
 * wallet signs. We snapshot the Payment challenge + headers into a bundle.
 *
 * Required: MPP_AUCTION_TERMS_FILE — the agent never pays until that path contains JSON
 * (e.g. npm run auction:release). See auction_gate.mjs.
 *
 * Prerequisites:
 *   1. Server running: npm start (same repo folder)
 *   2. A funded Tempo Moderato wallet for the payer:
 *        npx mppx account create
 *        npx mppx account fund   # testnet faucet via mppx CLI
 *      Then set TEMPO_PRIVATE_KEY in .env to that account's private key.
 *   3. Same .env as server for MPP_PAID_URL if you change port.
 *
 * Run: npm run agent
 */

// Load variables from `.env` into `process.env` so we can read keys and URLs.
import "dotenv/config";

// Tool to turn a hex private key string into a viem `account` object (address + signing).
import { privateKeyToAccount } from "viem/accounts";

// `Mppx` = payment-aware HTTP client; `tempo.charge` = pay with Tempo for one-shot charges.
import { Mppx, tempo } from "mppx/client";

// Writes the JSON “payment bundle” to disk when `MPP_BUNDLE_OUT` is set.
import { writeBundleFile } from "./payment_bundle.mjs";

// `createAuctionGate` builds `fetch` + `onChallenge`; `waitForTermsFile` polls until JSON exists.
import {
  createAuctionGate,
  defaultAcceptTerms,
  waitForTermsFile,
} from "./auction_gate.mjs";

// Secret key for the wallet that will pay (string from `.env`, may be empty).
const keyRaw = process.env.TEMPO_PRIVATE_KEY?.trim();

// URL we request; default is this repo’s demo server `/paid` on port 4243.
const paidUrl = (process.env.MPP_PAID_URL || "http://127.0.0.1:4243/paid").trim();

// If set, path to a JSON file where we save the bundle right after a 402.
const bundleOut = process.env.MPP_BUNDLE_OUT?.trim();

// Required: path to JSON terms; the agent blocks after 402 until this file is readable (never skips).
const termsFile = process.env.MPP_AUCTION_TERMS_FILE?.trim();

// Cannot pay without a private key; exit early with a helpful message.
if (!keyRaw) {
  console.error("Set TEMPO_PRIVATE_KEY in .env (payer wallet on Tempo Moderato).");
  console.error("Create/fund: npx mppx account create && npx mppx account fund");
  process.exit(1);
}

if (!termsFile) {
  console.error("Set MPP_AUCTION_TERMS_FILE in .env (path to JSON terms the agent must wait for).");
  console.error("Example: MPP_AUCTION_TERMS_FILE=./terms.json then run npm run auction:release in another terminal.");
  process.exit(1);
}

// viem expects `0x` prefix; add it if the user pasted hex without it.
const pk = keyRaw.startsWith("0x") ? keyRaw : `0x${keyRaw}`;

// Account object used by `tempo.charge` to sign the Tempo payment.
const account = privateKeyToAccount(pk);

// One object that wraps `fetch` and always waits for terms JSON before allowing payment.
const gate = createAuctionGate({
  // Blocks until `termsFile` has JSON that `defaultAcceptTerms` accepts (not pending/rejected).
  // Pings on a timer while waiting; see MPP_AUCTION_PING_INTERVAL_MS / MPP_AUCTION_QUIET.
  waitForTerms: () =>
    waitForTermsFile(termsFile, {
      acceptTerms: defaultAcceptTerms,
      onPing: ({ elapsedMs, phase, detail }) => {
        if (process.env.MPP_AUCTION_QUIET === "1") return;
        const s = (elapsedMs / 1000).toFixed(1);
        console.log(`[auction ping ${s}s] ${phase}${detail ? ` — ${detail}` : ""}`);
      },
    }),

  // Runs once we have a 402 and a parsed bundle (before waiting / paying).
  onBundle: async (bundle) => {
    console.log("\n--- 402 intercepted: payment bundle (for auction / audit) ---");
    // Pretty-print the whole bundle so you can see amount, recipient, challenge id, etc.
    console.log(JSON.stringify(bundle, null, 2));

    // Optionally persist the bundle for another process (e.g. auction:release).
    if (bundleOut) {
      await writeBundleFile(bundleOut, bundle);
      console.log(`\nWrote bundle to ${bundleOut}`);
    }

    console.log(
      `\nWaiting for auction terms (poll ${process.env.MPP_AUCTION_POLL_MS || "500"}ms): ${termsFile}`,
    );
    console.log("Release with: npm run auction:release   (set MPP_BUNDLE_OUT or pass bundle path to that script)\n");
  },

  // Runs only after terms were read (file appeared); then mppx will proceed to sign and pay.
  onTerms: async (_bundle, terms) => {
    console.log("\n--- auction terms received (proceeding to pay) ---");
    console.log(JSON.stringify(terms, null, 2));
  },
});

// Create the payment client: Tempo charge only, custom fetch from the gate, shared onChallenge.
const mppx = Mppx.create({
  // Do not replace global `fetch`; we only use `mppx.fetch` below.
  polyfill: false,
  // Wrapped fetch: captures 402 metadata, then mppx adds payment retry logic on top.
  fetch: gate.fetch,
  // `tempo.charge` only — not `tempo()`, which also adds `session` (see README.md).
  methods: [tempo.charge({ account })],
  // Called on 402: implemented by the gate (bundle → wait for terms file → then pay).
  onChallenge: gate.onChallenge,
});

// Main routine: one paid HTTP GET and print the result.
async function main() {
  console.log("MPP Tempo agent");
  console.log("  payer:", account.address);
  console.log("  url:  ", paidUrl);
  if (bundleOut) console.log("  bundle out:", bundleOut);
  console.log("  auction terms file (required wait):", termsFile);
  console.log("");

  // This may do: GET → 402 → onChallenge (bundle/wait) → pay → GET again with Authorization.
  const res = await mppx.fetch(paidUrl);
  // Read body as text (demo server returns JSON string).
  const body = await res.text();

  console.log("\nFinal status:", res.status);
  // Server may attach a receipt header after successful payment.
  console.log("Payment-Receipt:", res.headers.get("Payment-Receipt") || "(none)");
  // Truncate so a huge body doesn’t flood the terminal.
  console.log("Body:", body.slice(0, 4000));
}

// Run `main`; if anything throws, print it and exit with failure code 1.
main().catch((err) => {
  console.error(err);
  process.exit(1);
});
