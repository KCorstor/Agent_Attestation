/**
 * Creates or updates .env with a Tempo Moderato (testnet) payer wallet and
 * requests test tokens from the chain faucet (same RPC as `mppx account fund`).
 *
 * Run:  npm run wallet:setup
 *
 * Existing wallet in .env is kept (no new key) unless you pass --force.
 * Testnet faucet runs only when a new key was created, or when you pass --fund.
 *
 * Re-generate key (destructive):  npm run wallet:setup -- --force
 * Top up from faucet (same key):   npm run wallet:setup -- --fund
 */
import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createClient, http } from "viem";
import { tempoModerato } from "viem/chains";
import { Actions } from "viem/tempo";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const envPath = resolve(__dirname, ".env");
const examplePath = resolve(__dirname, ".env.example");
const force = process.argv.includes("--force");
const fundFlag = process.argv.includes("--fund");

console.log("setup-wallet: writing", envPath);

function upsertEnv(filePath, updates) {
  const text = existsSync(filePath) ? readFileSync(filePath, "utf8") : "";
  const lines = text.split(/\r?\n/);
  const keys = new Set(Object.keys(updates));
  const out = [];
  const seen = new Set();

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("#") || trimmed === "") {
      out.push(line);
      continue;
    }
    const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (m && keys.has(m[1])) {
      out.push(`${m[1]}=${updates[m[1]]}`);
      seen.add(m[1]);
    } else {
      out.push(line);
    }
  }

  for (const k of keys) {
    if (!seen.has(k)) {
      out.push(`${k}=${updates[k]}`);
    }
  }

  writeFileSync(filePath, out.join("\n").replace(/\n+$/, "\n"), "utf8");
}

function readEnvValue(key) {
  if (!existsSync(envPath)) return "";
  const text = readFileSync(envPath, "utf8");
  const re = new RegExp(`^${key}=(.*)$`, "m");
  const m = text.match(re);
  if (!m) return "";
  let v = m[1].trim();
  if (
    (v.startsWith('"') && v.endsWith('"')) ||
    (v.startsWith("'") && v.endsWith("'"))
  ) {
    v = v.slice(1, -1).trim();
  }
  return v;
}

/** Non-empty 32-byte hex private key (with or without 0x). */
function isValidPrivateKeyHex(v) {
  if (!v) return false;
  const s = v.startsWith("0x") ? v.slice(2) : v;
  return /^[a-fA-F0-9]{64}$/.test(s);
}

if (!existsSync(envPath) && existsSync(examplePath)) {
  copyFileSync(examplePath, envPath);
  console.log("Created .env from .env.example");
}

let existingPk = readEnvValue("TEMPO_PRIVATE_KEY");
if (!isValidPrivateKeyHex(existingPk)) {
  if (existingPk) {
    console.log("TEMPO_PRIVATE_KEY in .env is missing or not a valid 64-char hex key — generating a new one.");
  }
  existingPk = "";
}
let mppSecret = readEnvValue("MPP_SECRET_KEY");

if (!mppSecret) {
  const { randomBytes } = await import("node:crypto");
  mppSecret = randomBytes(32).toString("base64url");
}

let pk;
let generatedNewKey = false;
if (force) {
  pk = generatePrivateKey();
  generatedNewKey = true;
  console.log("(--force) Generating a new TEMPO_PRIVATE_KEY.");
} else if (existingPk) {
  pk = existingPk.startsWith("0x") ? existingPk : `0x${existingPk}`;
  console.log("Keeping existing TEMPO_PRIVATE_KEY from .env (omit --force to preserve; use --force to replace).");
} else {
  pk = generatePrivateKey();
  generatedNewKey = true;
  console.log("No TEMPO_PRIVATE_KEY in .env — generating one and saving to .env.");
}

const account = privateKeyToAccount(pk);

// Demo default: merchant recipient = payer (you pay yourself on testnet).
upsertEnv(envPath, {
  MPP_SECRET_KEY: mppSecret,
  TEMPO_PRIVATE_KEY: pk,
  TEMPO_ADDRESS: account.address,
  TEMPO_RECIPIENT_ADDRESS: account.address,
});

const verifyPk = readEnvValue("TEMPO_PRIVATE_KEY");
if (!isValidPrivateKeyHex(verifyPk)) {
  console.error("");
  console.error("ERROR: TEMPO_PRIVATE_KEY was not written correctly to .env");
  console.error("  File:", envPath);
  console.error("  Try: run this command from the mpp_tempo_example folder:");
  console.error('    cd mpp_tempo_example && node setup-wallet.mjs');
  process.exit(1);
}

console.log("");
console.log("Tempo Moderato (testnet) wallet");
console.log("  address:        ", account.address);
console.log("  saved in .env:  ", envPath);
console.log("  (TEMPO_PRIVATE_KEY + TEMPO_ADDRESS + TEMPO_RECIPIENT_ADDRESS)");
console.log("");

const client = createClient({
  chain: tempoModerato,
  transport: http(),
});

const runFaucet = generatedNewKey || fundFlag;
if (runFaucet) {
  try {
    console.log("Requesting testnet funds from faucet (tempo_fundAddress)…");
    const receipts = await Actions.faucet.fundSync(client, { account, timeout: 60_000 });
    console.log("Funded:", receipts.length, "tx(s)");
    for (const r of receipts) {
      console.log("  ", r.transactionHash);
    }
  } catch (e) {
    console.warn("Faucet failed (you can retry later):", e instanceof Error ? e.message : e);
    console.warn("Fund manually: send testnet pathUSD to", account.address);
  }
} else {
  console.log("Skipping faucet (wallet already in .env). To top up: npm run wallet:setup -- --fund");
}

console.log("");
console.log("Next: npm start   then   npm run agent");
