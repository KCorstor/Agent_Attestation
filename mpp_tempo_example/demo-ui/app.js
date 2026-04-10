const stepsList = document.getElementById("stepsList");
const jsonOut = document.getElementById("jsonOut");
const jsonPayloadBlock = document.getElementById("jsonPayloadBlock");
const runAllBtn = document.getElementById("runAllBtn");
const detailActions = document.getElementById("detailActions");
const runSelectedStepBtn = document.getElementById("runSelectedStepBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const statusHint = document.getElementById("statusHint");
const detailMeta = document.getElementById("detailMeta");

/** @type {{ id: string; title: string; does: string; doesNot?: string; runnable?: boolean; informational?: boolean; listDetail?: string; detailLabel?: string; snippets?: { file: string; code: string }[] }[]} */
let meta = [];
/** @type {Record<string, { ok: boolean; output?: unknown; error?: string; at: string }>} */
let stepResults = {};
let selectedIndex = 0;

function isRunnable(m) {
  return m.runnable === true;
}

async function loadMeta() {
  const r = await fetch("/api/meta", { cache: "no-store" });
  meta = await r.json();
}

async function loadState() {
  const r = await fetch("/api/state", { cache: "no-store" });
  const s = await r.json();
  stepResults = s.stepResults || {};
}

function showJson(obj) {
  const code = jsonOut.querySelector("code");
  code.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

function renderStepList() {
  stepsList.innerHTML = "";
  meta.forEach((m, i) => {
    const li = document.createElement("li");
    li.className = "step";
    if (i === selectedIndex) li.classList.add("step--active");
    const ran = Boolean(stepResults[m.id]?.ok || stepResults[m.id]?.error);
    if (ran) li.classList.add("step--done");
    const sub = m.listDetail
      ? m.listDetail
      : m.informational === true
        ? "How the code fits together"
        : ran
          ? "Captured in last run"
          : "Not yet in this session";
    li.dataset.index = String(i);
    li.innerHTML = `
      <span class="step__idx">${i}</span>
      <div class="step__body">
        <p class="step__title">${escapeHtml(m.title)}</p>
        <p class="step__detail">${sub}</p>
      </div>
    `;
    li.addEventListener("click", () => {
      selectedIndex = i;
      renderStepList();
      renderDetail();
      updateNav();
    });
    stepsList.appendChild(li);
  });
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderDetail() {
  const m = meta[selectedIndex];
  if (!m) return;

  const canRun = isRunnable(m);
  if (detailActions) {
    detailActions.hidden = !canRun;
  }

  const notBlock =
    m.doesNot && m.doesNot.trim()
      ? `<p class="detail-label">What it does not do</p>
    <p class="detail-text detail-text--muted">${escapeHtml(m.doesNot)}</p>`
      : "";
  const phaseLabel =
    m.detailLabel ||
    (m.informational === true ? "How it works" : "What happens in this phase");
  const snippetsBlock = Array.isArray(m.snippets)
    ? m.snippets
        .map(
          (s) =>
            `<p class="detail-label detail-label--file">${escapeHtml(s.file)}</p><pre class="detail-code"><code>${escapeHtml(s.code)}</code></pre>`,
        )
        .join("")
    : "";
  detailMeta.innerHTML = `
    <h3 class="detail-title">${escapeHtml(m.title)}</h3>
    <p class="detail-label">${escapeHtml(phaseLabel)}</p>
    <p class="detail-text">${escapeHtml(m.does)}</p>
    ${snippetsBlock}
    ${notBlock}
  `;

  const sr = stepResults[m.id];
  if (jsonPayloadBlock) {
    jsonPayloadBlock.hidden = m.informational === true;
  }
  if (m.informational === true) {
    return;
  }

  if (!sr) {
    let message;
    if (m.id === "demo-setup") {
      message =
        "This happens automatically when you click “Run all steps” (clears artifacts, starts the merchant server, then runs the agent).";
    } else if (canRun) {
      message =
        "This step has not been run yet. Click “Run this step” below, or use “Run all steps” to reset, start the server, and run the agent.";
    } else {
      message =
        "This phase is filled in when you run “Agent starts checkout” (one agent process), usually via “Run all steps”.";
    }
    showJson({ message });
    return;
  }
  if (sr.ok) {
    showJson({ step: m.id, at: sr.at, output: sr.output });
  } else {
    showJson({ step: m.id, at: sr.at, error: sr.error });
  }
}

function updateNav() {
  prevBtn.disabled = selectedIndex <= 0;
  nextBtn.disabled = selectedIndex >= meta.length - 1;
}

function setBusy(busy) {
  runAllBtn.disabled = busy;
  if (runSelectedStepBtn) runSelectedStepBtn.disabled = busy;
}

async function runStep(id) {
  statusHint.textContent = `Running ${id}…`;
  setBusy(true);
  try {
    const r = await fetch(`/api/step/${encodeURIComponent(id)}`, {
      method: "POST",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const raw = await r.text();
    let j;
    try {
      j = raw ? JSON.parse(raw) : {};
    } catch {
      throw new Error(
        r.status
          ? `Bad response (${r.status}): ${raw.slice(0, 200)}`
          : "Response was not JSON — is the demo dashboard running? Try: npm run demo:ui",
      );
    }
    if (!r.ok) {
      showJson(j);
      statusHint.textContent = j.error || "Error";
      await loadState();
      renderStepList();
      renderDetail();
      return;
    }
    showJson(j);
    statusHint.textContent = `Done: ${id}`;
    await loadState();
    renderStepList();
    renderDetail();
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    statusHint.textContent = msg;
    showJson({ error: msg });
  } finally {
    setBusy(false);
    updateNav();
  }
}

runAllBtn.addEventListener("click", async () => {
  statusHint.textContent = "Running full demo (setup + agent)…";
  setBusy(true);
  try {
    const r = await fetch("/api/run-all", {
      method: "POST",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const raw = await r.text();
    let j;
    try {
      j = raw ? JSON.parse(raw) : {};
    } catch {
      throw new Error("Run all failed: response was not JSON. Restart the dashboard (npm run demo:ui).");
    }
    showJson(j);
    statusHint.textContent = j.ok ? "All steps finished." : j.error || "Error";
    await loadState();
    selectedIndex = meta.length - 1;
    renderStepList();
    renderDetail();
    updateNav();
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    statusHint.textContent = msg;
    showJson({ error: msg });
  } finally {
    setBusy(false);
  }
});

if (runSelectedStepBtn) {
  runSelectedStepBtn.addEventListener("click", () => {
    const m = meta[selectedIndex];
    if (m && isRunnable(m)) runStep(m.id);
  });
}

prevBtn.addEventListener("click", () => {
  selectedIndex = Math.max(0, selectedIndex - 1);
  renderStepList();
  renderDetail();
  updateNav();
});

nextBtn.addEventListener("click", () => {
  selectedIndex = Math.min(meta.length - 1, selectedIndex + 1);
  renderStepList();
  renderDetail();
  updateNav();
});

async function init() {
  await loadMeta();
  await loadState();
  renderStepList();
  renderDetail();
  updateNav();
}

init().catch((e) => {
  statusHint.textContent = String(e.message);
  showJson({ error: String(e) });
});
