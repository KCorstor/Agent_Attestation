/**
 * Build a serializable "payment transaction bundle" from an MPP 402 challenge.
 *
 * Integration: the Tempo agent uses `Mppx.create({ onChallenge, fetch })`. When the
 * server returns HTTP 402, mppx parses `WWW-Authenticate: Payment …` into a
 * `challenge` object; this module turns that (+ optional raw 402 capture) into JSON
 * you can POST to an auction or other downstream service later.
 */

import { Challenge } from "mppx";

/** JSON.stringify helper — BigInt-safe for any nested values. */
export function jsonSafe(value) {
  return JSON.parse(
    JSON.stringify(value, (_, v) => (typeof v === "bigint" ? v.toString() : v)),
  );
}

/**
 * Wraps `fetch` so the latest HTTP 402 response metadata is available to `onChallenge`.
 * mppx calls this fetch first (unauthenticated), gets 402, runs `onChallenge`, then
 * retries with `Authorization`. Single-flight demo only — concurrent requests share one slot.
 *
 * @param {typeof fetch} [underlying=globalThis.fetch]
 */
export function createCapture402Fetch(underlying = globalThis.fetch) {
  /** @type {null | { requestUrl: string; requestMethod: string; status: number; headers: Record<string, string>; wwwAuthenticate: string | null }} */
  let last = null;

  /** @param {RequestInfo | URL} input */
  async function wrapped(input, init) {
    const requestUrl =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
    const requestMethod = (init?.method ?? "GET").toUpperCase();
    const res = await underlying(input, init);
    if (res.status === 402) {
      const headers = Object.fromEntries(res.headers.entries());
      last = {
        requestUrl,
        requestMethod,
        status: res.status,
        headers,
        wwwAuthenticate: res.headers.get("WWW-Authenticate"),
      };
    }
    return res;
  }

  return {
    fetch: wrapped,
    getLast402: () => last,
    clearLast402: () => {
      last = null;
    },
  };
}

/**
 * @param {object} opts
 * @param {import('mppx').Challenge.Challenge} opts.challenge - Parsed challenge from mppx (same object passed to `onChallenge`).
 * @param {ReturnType<createCapture402Fetch> extends { getLast402: () => infer R } ? R : never} [opts.capture402] - From `getLast402()` after the 402 response.
 */
export function buildPaymentBundle({ challenge, capture402 }) {
  const serializedChallenge = jsonSafe(challenge);
  const wwwAuthenticate =
    capture402?.wwwAuthenticate ?? Challenge.serialize(challenge);

  return {
    schemaVersion: 1,
    capturedAt: new Date().toISOString(),
    purpose: "mpp_payment_required_bundle_for_downstream_auction",
    request: capture402
      ? {
          url: capture402.requestUrl,
          method: capture402.requestMethod,
        }
      : undefined,
    http402: capture402
      ? {
          status: capture402.status,
          headers: jsonSafe(capture402.headers),
          wwwAuthenticate: capture402.wwwAuthenticate,
        }
      : {
          wwwAuthenticate,
        },
    /** Normalized payment demand — amount, currency, recipient, chain, etc. for tempo.charge */
    challenge: serializedChallenge,
    /** Canonical Payment header line (recomputable from `challenge` via mppx) */
    wwwAuthenticateSerialized: wwwAuthenticate,
  };
}

/**
 * @param {string} path
 * @param {unknown} bundle
 */
export async function writeBundleFile(path, bundle) {
  const { writeFile } = await import("node:fs/promises");
  await writeFile(path, `${JSON.stringify(bundle, null, 2)}\n`, "utf8");
}
