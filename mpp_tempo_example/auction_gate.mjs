/**
 * Reusable "pause for auction terms" layer for any mppx-based agent.
 *
 * Drop-in pattern (other agents copy the same three lines):
 *   const gate = createAuctionGate({ ... });
 *   Mppx.create({ fetch: gate.fetch, onChallenge: gate.onChallenge, methods, ... })
 *
 * No payment is signed until `waitForTerms(bundle)` resolves. Default integration is a
 * JSON file on disk (poll) so a separate process can "release" the agent.
 */

import { buildPaymentBundle, createCapture402Fetch } from "./payment_bundle.mjs";

/**
 * @param {object} config
 * @param {typeof fetch} [config.underlyingFetch]
 * @param {(bundle: object) => void | Promise<void>} [config.onBundle] - Runs after building the bundle; log, enqueue auction, etc.
 * @param {(bundle: object, terms: unknown) => void | Promise<void>} [config.onTerms] - Runs after terms arrive (before paying).
 * @param {(bundle: object) => void | Promise<void>} [config.waitForTerms] - If omitted, no pause (same as immediate pay).
 */
export function createAuctionGate(config) {
  const {
    underlyingFetch = globalThis.fetch,
    onBundle,
    onTerms,
    waitForTerms,
  } = config;

  const { fetch, getLast402, clearLast402 } = createCapture402Fetch(underlyingFetch);

  async function onChallenge(challenge, _helpers) {
    const bundle = buildPaymentBundle({
      challenge,
      capture402: getLast402(),
    });

    if (onBundle) await onBundle(bundle);

    if (waitForTerms) {
      const terms = await waitForTerms(bundle);
      if (onTerms) await onTerms(bundle, terms);
    }

    return undefined;
  }

  return { fetch, getLast402, clearLast402, onChallenge };
}

/**
 * Poll until `path` exists and contains JSON (auction / mock issuer wrote the file).
 *
 * @param {string} path
 * @param {{ pollMs?: number; timeoutMs?: number }} [opts]
 */
export async function waitForTermsFile(path, opts = {}) {
  const pollMs = opts.pollMs ?? Number(process.env.MPP_AUCTION_POLL_MS || 500);
  const timeoutMs = opts.timeoutMs ?? Number(process.env.MPP_AUCTION_TIMEOUT_MS || 0);
  const { access, readFile } = await import("node:fs/promises");
  const start = Date.now();

  for (;;) {
    try {
      await access(path);
      const raw = await readFile(path, "utf8").then((s) => s.trim());
      if (!raw) {
        await sleep(pollMs);
        continue;
      }
      return JSON.parse(raw);
    } catch (e) {
      if (e && typeof e === "object" && "code" in e && e.code === "ENOENT") {
        if (timeoutMs > 0 && Date.now() - start > timeoutMs) {
          throw new Error(`Timed out waiting for auction terms file: ${path}`);
        }
        await sleep(pollMs);
        continue;
      }
      if (e instanceof SyntaxError) {
        await sleep(pollMs);
        continue;
      }
      throw e;
    }
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Compose multiple `onChallenge` handlers (runs in order). First non-undefined return wins.
 * Use this to overlay auction pause on an agent that already has `onChallenge`.
 */
export function chainOnChallenge(...handlers) {
  return async (challenge, helpers) => {
    for (const h of handlers) {
      if (!h) continue;
      const out = await h(challenge, helpers);
      if (out !== undefined) return out;
    }
    return undefined;
  };
}

/**
 * Build `waitForTerms` from env (zero code changes in the agent besides importing this).
 * Set `MPP_AUCTION_TERMS_FILE` to a path; when unset, returns `undefined` (no pause).
 */
export function waitForTermsFromEnv() {
  const p = process.env.MPP_AUCTION_TERMS_FILE?.trim();
  if (!p) return undefined;
  return (bundle) => waitForTermsFile(p, {});
}
