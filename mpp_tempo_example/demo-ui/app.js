const stepsList = document.getElementById("stepsList");
const jsonOut = document.getElementById("jsonOut");
const runAllBtn = document.getElementById("runAllBtn");
const resetBtn = document.getElementById("resetBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const statusHint = document.getElementById("statusHint");
const detailMeta = document.getElementById("detailMeta");
const stepBadge = document.getElementById("stepBadge");

/** @type {{ id: string; title: string; does: string; doesNot?: string; runnable?: boolean }[]} */
let meta = [];
/** @type {Record<string, { ok: boolean; output?: unknown; error?: string; at: string }>} */
let stepResults = {};
let selectedIndex = 0;

function isRunnable(m) {
  return m.runnable === true;
}

async function loadMeta() {
  const r = await fetch("/api/meta");
  meta = await r.json();
}

async function loadState() {
  const r = await fetch("/api/state");
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
    li.dataset.index = String(i);
    li.innerHTML = `
      <span class="step__idx">${i + 1}</span>
      <div class="step__body">
        <p class="step__title">${escapeHtml(m.title)}</p>
        <p class="step__detail">${ran ? "Captured in last run" : "Not yet in this session"}</p>
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

  stepBadge.textContent = m.id;
  const notBlock =
    m.doesNot && m.doesNot.trim()
      ? `<p class="detail-label">What it does not do</p>
    <p class="detail-text detail-text--muted">${escapeHtml(m.doesNot)}</p>`
      : "";
  detailMeta.innerHTML = `
    <h3 class="detail-title">${escapeHtml(m.title)}</h3>
    <p class="detail-label">What happens in this phase</p>
    <p class="detail-text">${escapeHtml(m.does)}</p>
    ${notBlock}
  `;

  const canRun = isRunnable(m);
  const sr = stepResults[m.id];
  if (!sr) {
    showJson({
      message: canRun
        ? "This step has not been run yet. Use Run all steps (or Reset, then Run all steps)."
        : "This phase is filled in when you run “Agent starts checkout” (one agent process).",
    });
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
  resetBtn.disabled = busy;
}

async function runStep(id) {
  statusHint.textContent = `Running ${id}…`;
  setBusy(true);
  try {
    const r = await fetch(`/api/step/${encodeURIComponent(id)}`, { method: "POST" });
    const j = await r.json();
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
  } finally {
    setBusy(false);
    updateNav();
  }
}

runAllBtn.addEventListener("click", async () => {
  statusHint.textContent = "Running reset → server → agent…";
  setBusy(true);
  try {
    const r = await fetch("/api/run-all", { method: "POST" });
    const j = await r.json();
    showJson(j);
    statusHint.textContent = j.ok ? "All steps finished." : j.error || "Error";
    await loadState();
    selectedIndex = meta.length - 1;
    renderStepList();
    renderDetail();
    updateNav();
  } finally {
    setBusy(false);
  }
});

resetBtn.addEventListener("click", () => runStep("reset"));

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
