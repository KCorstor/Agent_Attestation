/**
 * MPP Tempo demo dashboard — run checkout steps individually or all at once.
 *
 * Run from mpp_tempo_example/:
 *   node demo_dashboard.mjs
 * Open http://127.0.0.1:3333
 */
import "./load-env.mjs";
import { spawn } from "node:child_process";
import { access, readFile, unlink } from "node:fs/promises";
import http from "node:http";
import { createInterface } from "node:readline";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import express from "express";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;
/** Merchant HTTP port (server.mjs); agent must use the same host:port in MPP_PAID_URL. */
const MERCHANT_PORT = Number(process.env.PORT || 4243);
const PAID_URL = (
  process.env.MPP_PAID_URL || `http://127.0.0.1:${MERCHANT_PORT}/paid`
).trim();
const BUNDLE_REL = "demo-ui-bundle.json";
const TERMS_REL = "demo-ui-terms.json";
const BUNDLE = join(ROOT, BUNDLE_REL);
const TERMS = join(ROOT, TERMS_REL);

/** @type {import('node:child_process').ChildProcess | null} */
let serverProcess = null;
/** @type {import('node:child_process').ChildProcess | null} */
let agentProcess = null;
/** @type {Record<string, { ok: boolean; output?: unknown; error?: string; at: string }>} */
const stepResults = {};

const CHECKOUT_STEPS = [
  "demo-setup",
  "agent_start",
  "checkout_402",
  "waiting_terms",
  "lender_terms_written",
  "terms_accepted",
  "paid",
];

/** Steps the user can invoke via POST /api/step/:id (reset/start-server kept for older clients). */
const RUNNABLE_STEP_IDS = new Set(["demo-setup", "agent_start", "reset", "start-server"]);

let demoRunning = false;

function stamp(stepId, payload) {
  stepResults[stepId] = { ok: true, output: payload, at: new Date().toISOString() };
}

function fail(stepId, message) {
  stepResults[stepId] = { ok: false, error: message, at: new Date().toISOString() };
}

/** Loopback probe without `fetch` (avoids generic “fetch failed” / proxy quirks on 127.0.0.1). */
function httpGetLocal(urlStr) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const port = u.port ? Number(u.port) : u.protocol === "https:" ? 443 : 80;
    const req = http.request(
      {
        hostname: u.hostname,
        port,
        path: `${u.pathname}${u.search}`,
        method: "GET",
        timeout: 10_000,
      },
      (res) => {
        res.resume();
        resolve(res);
      },
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("connect timeout"));
    });
    req.end();
  });
}

async function stepReset() {
  if (agentProcess && !agentProcess.killed) {
    try {
      agentProcess.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    agentProcess = null;
  }
  if (serverProcess) {
    serverProcess.kill("SIGTERM");
    serverProcess = null;
    await new Promise((r) => setTimeout(r, 200));
  }
  await unlink(BUNDLE).catch(() => {});
  await unlink(TERMS).catch(() => {});
  for (const k of Object.keys(stepResults)) delete stepResults[k];
  stamp("reset", { cleared: [BUNDLE_REL, TERMS_REL], serverStopped: true });
  return stepResults.reset.output;
}

async function stepStartServer() {
  if (serverProcess) {
    throw new Error("Demo server already running. Use “Run all steps” to reset and restart cleanly.");
  }
  let serverStderr = "";
  let serverStdout = "";
  serverProcess = spawn(process.execPath, ["server.mjs"], {
    cwd: ROOT,
    env: { ...process.env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  serverProcess.stdout?.on("data", (c) => {
    serverStdout += c.toString();
    if (serverStdout.length > 4000) serverStdout = serverStdout.slice(-4000);
  });
  serverProcess.stderr?.on("data", (c) => {
    serverStderr += c.toString();
    if (serverStderr.length > 4000) serverStderr = serverStderr.slice(-4000);
  });
  await new Promise((r) => setTimeout(r, 300));
  let probe;
  let lastErr = "";
  for (let i = 0; i < 30; i++) {
    if (serverProcess.exitCode != null && serverProcess.exitCode !== 0) {
      throw new Error(
        `server.mjs exited ${serverProcess.exitCode}: ${serverStderr.trim() || "check .env (MPP_SECRET_KEY, TEMPO_RECIPIENT_ADDRESS)"}`,
      );
    }
    try {
      probe = await httpGetLocal(PAID_URL);
      break;
    } catch (e) {
      const err = /** @type {NodeJS.ErrnoException} */ (e);
      const code = err.code ? ` [${err.code}]` : "";
      lastErr = `${err.message || String(e)}${code}`;
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  if (!probe) {
    if (serverProcess.exitCode != null && serverProcess.exitCode !== 0) {
      throw new Error(
        `server.mjs exited ${serverProcess.exitCode}: ${serverStderr.trim() || lastErr}`,
      );
    }
    const hint =
      lastErr.includes("ECONNREFUSED") || lastErr.includes("EADDRINUSE")
        ? " Another process may be using this PORT, or server.mjs failed before listen()."
        : "";
    const out = serverStdout.trim();
    const err = serverStderr.trim();
    const logHint =
      err || out
        ? ` Output: ${out ? `${out.slice(0, 800)}${out.length > 800 ? "…" : ""}` : ""}${err ? ` | Errors: ${err.slice(0, 800)}${err.length > 800 ? "…" : ""}` : ""}`
        : "";
    throw new Error(`Cannot reach ${PAID_URL}: ${lastErr || "no response"}.${hint}${logHint}`);
  }
  stamp("start-server", { listening: true, url: PAID_URL, probeStatus: probe.statusCode });
  return stepResults["start-server"].output;
}

/** Reset workspace + start merchant server (one UI phase). */
async function stepDemoSetup() {
  await stepReset();
  await stepStartServer();
  const out = {
    workspace: stepResults.reset.output,
    merchant: stepResults["start-server"].output,
  };
  delete stepResults.reset;
  delete stepResults["start-server"];
  stamp("demo-setup", out);
  return out;
}

/** After agent wrote demo-ui-bundle.json — same script as manual `npm run auction:release` for this path. */
async function runReleaseMockAuction() {
  try {
    await access(BUNDLE);
  } catch {
    throw new Error(`Missing ${BUNDLE_REL}; agent should write it on 402 before release.`);
  }
  const release = spawn(process.execPath, ["release_mock_auction.mjs"], {
    cwd: ROOT,
    env: {
      ...process.env,
      MPP_BUNDLE_OUT: BUNDLE_REL,
      MPP_AUCTION_TERMS_FILE: TERMS_REL,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let err = "";
  release.stderr.on("data", (c) => {
    err += c.toString();
  });
  const code = await new Promise((resolve) => release.on("close", resolve));
  if (code !== 0) {
    throw new Error(`release_mock_auction exited ${code}: ${err}`);
  }
  const terms = JSON.parse(await readFile(TERMS, "utf8"));
  return {
    path: TERMS_REL,
    mockAuction: terms.mockAuction,
    mockBank: terms.mockBank,
  };
}

/**
 * Spawn agent.mjs (MPP_DEMO_EVENT=1); on checkout_402 run release_mock_auction; wait for exit.
 * Requires merchant server already up (after “Run all steps” or a prior setup).
 */
async function runAgentCheckoutPipeline() {
  if (demoRunning) {
    throw new Error("A checkout run is already in progress.");
  }
  if (!serverProcess) {
    throw new Error("Merchant server is not running. Use “Run all steps” first (it starts the server).");
  }

  demoRunning = true;
  try {
    const agent = spawn(process.execPath, ["agent.mjs"], {
      cwd: ROOT,
      env: {
        ...process.env,
        MPP_PAID_URL: PAID_URL,
        MPP_DEMO_EVENT: "1",
        MPP_BUNDLE_OUT: BUNDLE_REL,
        MPP_AUCTION_TERMS_FILE: TERMS_REL,
        MPP_AUCTION_QUIET: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    agentProcess = agent;

    agent.stderr.on("data", (c) => {
      process.stderr.write(c);
    });

    const rl = createInterface({ input: agent.stdout, crlfDelay: Infinity });
    let released = false;

    /** @type {Promise<void>} */
    let chain = Promise.resolve();

    rl.on("line", (line) => {
      chain = chain.then(async () => {
        if (!line.startsWith("MPP_DEMO_EVENT:")) return;
        let payload;
        try {
          payload = JSON.parse(line.slice("MPP_DEMO_EVENT:".length));
        } catch {
          return;
        }
        const step = payload.step;
        if (typeof step === "string") {
          stamp(step, payload);
        }

        if (step === "checkout_402" && !released) {
          released = true;
          const out = await runReleaseMockAuction();
          stamp("lender_terms_written", out);
        }
      });
    });

    const exitCode = await new Promise((resolve) => {
      agent.once("close", (code) => resolve(code ?? 1));
    });
    await chain;

    if (exitCode !== 0) {
      const msg = `agent exited ${exitCode}`;
      fail("paid", msg);
      throw new Error(msg);
    }
    return { stepResults, order: CHECKOUT_STEPS };
  } finally {
    agentProcess = null;
    demoRunning = false;
  }
}

const app = express();
app.use(express.json());
app.use("/api", (_req, res, next) => {
  res.set("Cache-Control", "no-store");
  next();
});

app.get("/api/meta", async (_req, res) => {
  const raw = await readFile(join(ROOT, "demo-ui", "steps.json"), "utf8");
  res.type("application/json").send(raw);
});

app.get("/api/state", (_req, res) => {
  res.json({
    paidUrl: PAID_URL,
    serverRunning: Boolean(serverProcess),
    demoRunning,
    stepResults,
    order: CHECKOUT_STEPS,
  });
});

app.post("/api/step/:id", async (req, res) => {
  const id = req.params.id;
  if (!RUNNABLE_STEP_IDS.has(id)) {
    res.status(400).json({
      ok: false,
      error: `Step “${id}” is not runnable from the API (only agent-driven phases). Runnable: demo-setup, agent_start.`,
    });
    return;
  }
  try {
    let output;
    switch (id) {
      case "demo-setup":
        output = await stepDemoSetup();
        break;
      case "reset":
        output = await stepReset();
        break;
      case "start-server":
        output = await stepStartServer();
        break;
      case "agent_start":
        output = await runAgentCheckoutPipeline();
        break;
      default:
        throw new Error("unreachable");
    }
    res.json({ ok: true, step: id, output });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    if (id === "demo-setup") {
      fail("demo-setup", message);
      delete stepResults.reset;
      delete stepResults["start-server"];
    } else if (id === "reset" || id === "start-server") {
      fail(id, message);
    }
    res.status(400).json({ ok: false, step: id, error: message, stepResults });
  }
});

/** Full demo: workspace + server (demo-setup) → agent checkout. */
app.post("/api/run-all", async (_req, res) => {
  if (demoRunning) {
    res.status(429).json({ error: "Checkout demo already running" });
    return;
  }
  try {
    await stepDemoSetup();
    const output = await runAgentCheckoutPipeline();
    res.json({ ok: true, steps: ["demo-setup", "agent_start"], output });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    res.status(400).json({ ok: false, error: message, stepResults });
  }
});

app.use(express.static(join(ROOT, "demo-ui")));

const port = Number(process.env.DEMO_UI_PORT || 3333);
app.listen(port, () => {
  console.log(`MPP demo dashboard → http://127.0.0.1:${port}`);
});
