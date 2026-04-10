/**
 * Writes mock auction winner terms to the same file the agent is waiting on.
 *
 * Terminal A: MPP_AUCTION_TERMS_FILE=./terms.json npm run agent   (blocks after 402)
 * Terminal B: MPP_BUNDLE_OUT=./bundle.json MPP_AUCTION_TERMS_FILE=./terms.json npm run auction:release
 *   (or pass bundle path: node release_mock_auction.mjs ./bundle.json)
 */
import "./load-env.mjs";
import { readFile, writeFile } from "node:fs/promises";
import { attachMockIssuingTerms } from "./mock_auction_issuer.mjs";

const outPath = process.env.MPP_AUCTION_TERMS_FILE?.trim();
const bundlePath = process.argv[2]?.trim() || process.env.MPP_BUNDLE_OUT?.trim();

if (!outPath) {
  console.error("Set MPP_AUCTION_TERMS_FILE to where the agent is polling (e.g. ./terms.json).");
  process.exit(1);
}
if (!bundlePath) {
  console.error("Pass bundle JSON path or set MPP_BUNDLE_OUT (from agent).");
  process.exit(1);
}

const raw = await readFile(bundlePath, "utf8");
const bundle = JSON.parse(raw);
const terms = attachMockIssuingTerms(bundle);
await writeFile(outPath, `${JSON.stringify(terms, null, 2)}\n`, "utf8");
console.log(`Wrote mock auction terms → ${outPath}`);
