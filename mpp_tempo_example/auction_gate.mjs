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
 * Decide whether parsed JSON from the terms file allows the transaction to continue.
 * - `proceed` — return this object and move on to payment.
 * - `wait` — keep polling (e.g. auction still pending).
 * - `abort` — throw; payment will not run.
 *
 * Default rules (mock issuer friendly):
 * - `mockAuction.status === "pending"` → wait
 * - `mockAuction.status === "rejected"` or `proceed === false` → abort
 * - `mockAuction.status === "cleared_for_issuance"` or missing mockAuction → proceed
 *
 * @param {unknown} terms
 * @returns {"proceed" | "wait" | "abort"}
 */
export function defaultAcceptTerms(terms) {
  if (!terms || typeof terms !== "object") return "proceed";
  const t = /** @type {Record<string, unknown>} */ (terms);
  if (t.proceed === false) return "abort";
  const st = t.mockAuction && typeof t.mockAuction === "object"
    ? /** @type {Record<string, unknown>} */ (t.mockAuction).status
    : undefined;
  if (st === "pending") return "wait";
  if (st === "rejected") return "abort";
  return "proceed";
}

/**
 * @param {object} config
 * @param {typeof fetch} [config.underlyingFetch]
 * @param {(bundle: object) => void | Promise<void>} [config.onBundle]
 * @param {(bundle: object, terms: unknown) => void | Promise<void>} [config.onTerms]
 * @param {(bundle: object) => void | Promise<void>} [config.waitForTerms] - If omitted, no pause.
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
 * Poll `path` until JSON exists and `acceptTerms` returns `proceed`.
 * Time-based pings: `onPing` is called at most every `pingIntervalMs` while waiting.
 *
 * @param {string} path
 * @param {{
 *   pollMs?: number;
 *   timeoutMs?: number;
 *   pingIntervalMs?: number;
 *   acceptTerms?: (parsed: unknown) => "proceed" | "wait" | "abort";
 *   onPing?: (info: { elapsedMs: number; attempt: number; phase: string; detail?: string }) => void;
 * }} [opts]
 */
export async function waitForTermsFile(path, opts = {}) {
  const pollMs = opts.pollMs ?? Number(process.env.MPP_AUCTION_POLL_MS || 500);
  const timeoutMs = opts.timeoutMs ?? Number(process.env.MPP_AUCTION_TIMEOUT_MS || 0);
  const pingIntervalMs =
    opts.pingIntervalMs ?? Number(process.env.MPP_AUCTION_PING_INTERVAL_MS || 2000);
  const acceptTerms = opts.acceptTerms ?? defaultAcceptTerms;
  const onPing = opts.onPing;

  const { access, readFile } = await import("node:fs/promises");
  const start = Date.now();
  let attempt = 0;
  let lastPingAt = 0;

  function maybePing(phase, detail) {
    attempt += 1;
    const elapsedMs = Date.now() - start;
    if (!onPing) return;
    if (pingIntervalMs <= 0 || Date.now() - lastPingAt >= pingIntervalMs) {
      lastPingAt = Date.now();
      onPing({ elapsedMs, attempt, phase, detail });
    }
  }

  for (;;) {
    if (timeoutMs > 0 && Date.now() - start > timeoutMs) {
      throw new Error(`Timed out waiting for auction terms file: ${path}`);
    }

    try {
      await access(path);
    } catch (e) {
      if (e && typeof e === "object" && "code" in e && e.code === "ENOENT") {
        maybePing("file_missing", path);
        await sleep(pollMs);
        continue;
      }
      throw e;
    }

    let raw;
    try {
      raw = await readFile(path, "utf8").then((s) => s.trim());
    } catch (e) {
      maybePing("read_error", String(e));
      await sleep(pollMs);
      continue;
    }

    if (!raw) {
      maybePing("file_empty", path);
      await sleep(pollMs);
      continue;
    }

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      maybePing("invalid_json", "waiting for complete JSON");
      await sleep(pollMs);
      continue;
    }

    const decision = acceptTerms(parsed);
    if (decision === "wait") {
      maybePing("terms_pending", "mockAuction.status=pending or equivalent");
      await sleep(pollMs);
      continue;
    }
    if (decision === "abort") {
      throw new Error(
        `Auction terms rejected or declined the transaction (file: ${path})`,
      );
    }

    if (onPing) {
      onPing({
        elapsedMs: Date.now() - start,
        attempt,
        phase: "terms_accepted",
        detail: "proceeding to payment",
      });
    }
    return parsed;
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Compose multiple `onChallenge` handlers (runs in order). First non-undefined return wins.
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
 * Build `waitForTerms` from env. When `MPP_AUCTION_TERMS_FILE` is unset, returns `undefined` (no pause).
 */
export function waitForTermsFromEnv() {
  const p = process.env.MPP_AUCTION_TERMS_FILE?.trim();
  if (!p) return undefined;
  return (bundle) => waitForTermsFile(p, {});
}
