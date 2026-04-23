// Vanilla JS labeler — no framework.
// State lives in the DOM for the form; a tiny module-level cache
// holds the loaded articles and autocomplete.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  source: "nugget_bridge",
  format: "",
  statusFilter: "",
  triageFilter: "has_sets",
  articles: [],
  current: null,   // {article, state, label}
  autocomplete: null,
  dirty: false,
  prefill: { name: "stub", available: false },
  prefillSnapshot: null, // list of pre-filled set dicts for current article (frozen at pre-fill time)
  triage: { name: "stub", available: false },
};

// Fields we diff between pre-fill and save for the correction dashboard.
const DIFF_FIELDS = [
  "pokemon", "ability", "item", "nature", "tera_type",
  "move1", "move2", "move3", "move4",
  "ev_hp", "ev_atk", "ev_def", "ev_spa", "ev_spd", "ev_spe", "level",
];

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`${r.status} ${r.statusText}: ${body}`);
  }
  return r.json();
}

async function init() {
  const [sources, formats, ac, prefill, triage] = await Promise.all([
    fetchJSON("/api/sources"),
    fetchJSON("/api/formats"),
    fetchJSON("/api/autocomplete"),
    fetchJSON("/api/prefill").catch(() => ({ name: "stub", available: false })),
    fetchJSON("/api/triage").catch(() => ({ name: "stub", available: false })),
  ]);
  state.prefill = prefill;
  state.triage = triage;
  const sourceSel = $("#source");
  sources.forEach(s => sourceSel.add(new Option(s, s)));
  sourceSel.value = state.source;

  const fmtSel = $("#format");
  formats.forEach(f => fmtSel.add(new Option(f.name, f.code)));

  state.autocomplete = ac;
  fillDatalist("dl-pokemon", ac.pokemon);
  fillDatalist("dl-moves", ac.moves);
  fillDatalist("dl-abilities", ac.abilities);
  fillDatalist("dl-items", ac.items);
  fillDatalist("dl-natures", ac.natures);

  sourceSel.addEventListener("change", e => { state.source = e.target.value; loadArticles(); });
  fmtSel.addEventListener("change", e => { state.format = e.target.value; loadArticles(); });
  $("#status-filter").addEventListener("change", e => { state.statusFilter = e.target.value; renderList(); });
  $("#triage-filter").addEventListener("change", e => { state.triageFilter = e.target.value; renderList(); });
  $("#add-set").addEventListener("click", () => { addSet(); markDirty(); });
  $("#save").addEventListener("click", saveLabel);
  $("#prev-unlabeled").addEventListener("click", () => stepUnlabeled(-1));
  $("#next-unlabeled").addEventListener("click", () => stepUnlabeled(+1));
  $("#run-prefill").addEventListener("click", runPrefill);
  $("#run-triage").addEventListener("click", runTriage);
  $("#stats-toggle").addEventListener("click", toggleStats);
  window.addEventListener("beforeunload", e => {
    if (state.dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  const prefillBtn = $("#run-prefill");
  prefillBtn.disabled = !state.prefill.available;
  prefillBtn.title = state.prefill.available
    ? `Ask ${state.prefill.name} to pre-fill this article`
    : `Pre-fill unavailable (${state.prefill.name}) — set ANTHROPIC_API_KEY`;

  const triageBtn = $("#run-triage");
  triageBtn.disabled = !state.triage.available;
  triageBtn.title = state.triage.available
    ? `Batch-triage untriaged articles via ${state.triage.name}`
    : `Triage unavailable (${state.triage.name}) — set ANTHROPIC_API_KEY`;

  await loadArticles();
}

function fillDatalist(id, values) {
  const dl = document.getElementById(id);
  dl.innerHTML = "";
  (values || []).forEach(v => dl.appendChild(new Option(v)));
}

async function loadArticles() {
  const qs = new URLSearchParams({ source: state.source, limit: "200" });
  if (state.format) qs.set("format", state.format);
  const data = await fetchJSON(`/api/articles?${qs}`);
  state.articles = data.items;
  renderList();
}

function renderList() {
  const list = $("#article-list");
  list.innerHTML = "";
  const filtered = state.articles.filter(a => {
    if (state.statusFilter && a.status !== state.statusFilter) return false;
    if (state.triageFilter === "has_sets" && a.triage_result !== "has_sets" && a.triage_result != null) return false;
    if (state.triageFilter === "no_sets" && a.triage_result !== "no_sets") return false;
    if (state.triageFilter === "untriaged" && a.triage_result != null) return false;
    return true;
  });
  filtered.forEach(a => {
    const el = document.createElement("div");
    el.className = "article-item" + (state.current?.article.article_id === a.article_id ? " active" : "");
    const triageBadge = a.triage_result
      ? `<span class="badge triage-${a.triage_result}">${a.triage_result === "has_sets" ? "sets" : "no sets"}</span>`
      : "";
    el.innerHTML = `<span class="badge ${a.status}">${a.status.replace("_", " ")}</span>${triageBadge}
      <span class="title"></span>
      <span class="meta"></span>`;
    el.querySelector(".title").textContent = a.title;
    el.querySelector(".meta").textContent =
      [a.format, a.published_at?.slice(0, 10)].filter(Boolean).join(" · ");
    el.addEventListener("click", () => loadArticle(a.article_id));
    list.appendChild(el);
  });

  const total = state.articles.length;
  const labeled = state.articles.filter(a => a.status === "labeled").length;
  $("#progress").textContent = `${labeled}/${total} labeled`;
}

async function loadArticle(articleId) {
  if (state.dirty && !confirm("Unsaved changes — discard?")) return;
  const data = await fetchJSON(`/api/articles/${state.source}/${articleId}`);
  state.current = data;
  state.prefillSnapshot = null;
  renderArticle();
  renderLabel();
  state.dirty = false;
  renderList();
}

function renderArticle() {
  const { article, state: st } = state.current;
  $("#editor-title").textContent = article.title;
  const when = article.published_at ? article.published_at.slice(0, 10) : "—";
  const statusBits = [
    `format: ${article.format || "—"}`,
    `published: ${when}`,
    `status: ${(st || {}).status || "unlabeled"}`,
  ];
  $("#editor-status").textContent = statusBits.join(" · ");
  $("#article-meta").innerHTML =
    `<a href="${article.url}" target="_blank" rel="noopener">${article.url}</a>`;
  const iframe = $("#article-body");
  iframe.srcdoc = wrapArticleHtml(article.content_html);
}

function wrapArticleHtml(html) {
  // Sandboxed iframe (allow-same-origin only, no scripts) with minimal styling.
  return `<!doctype html><html><head><meta charset="utf-8">
    <style>
      body { font-family: -apple-system, sans-serif; max-width: 42rem; margin: 1rem auto; padding: 0 1rem; color: #1f2328; line-height: 1.5; }
      img, iframe, video { max-width: 100%; height: auto; }
      pre { white-space: pre-wrap; word-wrap: break-word; background: #f6f8fa; padding: 0.5rem; border-radius: 4px; }
      table { border-collapse: collapse; } td, th { border: 1px solid #d0d7de; padding: 0.25rem 0.5rem; }
      a { color: #0969da; }
    </style></head><body>${html || ""}</body></html>`;
}

function renderLabel() {
  const container = $("#sets-container");
  container.innerHTML = "";
  const existing = state.current?.label?.sets || [];
  if (existing.length === 0) {
    addSet();
  } else {
    existing.forEach(s => addSet(s));
  }
}

function addSet(data = {}, { prefilled = false } = {}) {
  const tmpl = $("#set-template").content.cloneNode(true);
  const card = tmpl.querySelector(".set-card");
  card.querySelector(".f-pokemon").value = data.pokemon || "";
  card.querySelector(".f-ability").value = data.ability || "";
  card.querySelector(".f-item").value = data.item || "";
  card.querySelector(".f-nature").value = data.nature || "";
  card.querySelector(".f-tera").value = data.tera_type || "";
  card.querySelector(".f-level").value = data.level ?? 50;
  const moveInputs = card.querySelectorAll(".f-move");
  ["move1", "move2", "move3", "move4"].forEach((k, i) => { moveInputs[i].value = data[k] || ""; });
  card.querySelectorAll(".f-ev").forEach(inp => {
    const stat = inp.dataset.stat;
    inp.value = data[`ev_${stat}`] ?? "";
  });
  card.querySelector(".f-snippet").value = data.raw_snippet || "";
  card.querySelector(".remove-set").addEventListener("click", () => {
    card.remove(); markDirty();
  });
  card.querySelector(".parse-paste").addEventListener("click", () => {
    const text = card.querySelector(".f-showdown-paste").value;
    const parsed = parseShowdownImport(text);
    if (parsed) { applyShowdownToCard(card, parsed); markDirty(); }
  });

  if (prefilled) {
    card.dataset.prefilled = "true";
    card.querySelectorAll("input, textarea").forEach(inp => {
      if (inp.value !== "" && inp.value != null) inp.classList.add("prefilled");
    });
  }

  card.querySelectorAll("input, textarea").forEach(inp => {
    inp.addEventListener("input", () => {
      markDirty();
      // First edit after pre-fill = labeler correction. Flip tint and record.
      if (inp.classList.contains("prefilled")) {
        inp.classList.remove("prefilled");
        inp.classList.add("corrected");
      }
      if (inp.classList.contains("f-ev")) updateEvTotal(card);
    });
  });

  $("#sets-container").appendChild(card);
  updateEvTotal(card);
  return card;
}

function parseShowdownImport(text) {
  const lines = text.trim().split("\n").map(l => l.trim()).filter(Boolean);
  if (lines.length === 0) return null;
  const result = {
    pokemon: null, item: null, ability: null, nature: null, level: 50,
    tera_type: null, moves: [], evs: {},
  };

  // Line 1: "Pokemon @ Item" or just "Pokemon"
  const first = lines[0];
  const atIdx = first.lastIndexOf(" @ ");
  if (atIdx !== -1) {
    result.pokemon = first.slice(0, atIdx).trim();
    result.item = first.slice(atIdx + 3).trim();
  } else {
    result.pokemon = first.trim();
  }
  // Strip gender suffix like " (M)" or " (F)"
  result.pokemon = result.pokemon.replace(/\s*\([MF]\)\s*$/, "").trim();

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("Ability:")) {
      result.ability = line.slice(8).trim();
    } else if (line.startsWith("Level:")) {
      result.level = parseInt(line.slice(6).trim(), 10) || 50;
    } else if (line.startsWith("Tera Type:")) {
      result.tera_type = line.slice(10).trim();
    } else if (line.startsWith("EVs:")) {
      const evStr = line.slice(4).trim();
      for (const part of evStr.split("/")) {
        const m = part.trim().match(/^(\d+)\s+(HP|Atk|Def|SpA|SpD|Spe)$/i);
        if (m) result.evs[m[2].toLowerCase()] = parseInt(m[1], 10);
      }
      // Normalize stat names
      const map = { hp: "hp", atk: "atk", def: "def", spa: "spa", spd: "spd", spe: "spe" };
      const normalized = {};
      for (const [k, v] of Object.entries(result.evs)) {
        const key = map[k] || k;
        normalized[key] = v;
      }
      result.evs = normalized;
    } else if (line.endsWith("Nature")) {
      result.nature = line.replace(/\s*Nature$/, "").trim();
    } else if (line.startsWith("- ") || line.startsWith("–")) {
      const move = line.replace(/^[-–]\s*/, "").trim();
      if (move && result.moves.length < 4) result.moves.push(move);
    }
  }
  return result;
}

function applyShowdownToCard(card, parsed) {
  if (!parsed) return;
  if (parsed.pokemon) card.querySelector(".f-pokemon").value = parsed.pokemon;
  if (parsed.ability) card.querySelector(".f-ability").value = parsed.ability;
  if (parsed.item) card.querySelector(".f-item").value = parsed.item;
  if (parsed.nature) card.querySelector(".f-nature").value = parsed.nature;
  if (parsed.tera_type) card.querySelector(".f-tera").value = parsed.tera_type;
  if (parsed.level) card.querySelector(".f-level").value = parsed.level;
  const moveInputs = card.querySelectorAll(".f-move");
  parsed.moves.forEach((m, i) => { if (moveInputs[i]) moveInputs[i].value = m; });
  card.querySelectorAll(".f-ev").forEach(inp => {
    const stat = inp.dataset.stat;
    if (parsed.evs[stat] != null) inp.value = parsed.evs[stat];
  });
  updateEvTotal(card);
}

function updateEvTotal(card) {
  const total = [...card.querySelectorAll(".f-ev")]
    .map(i => parseInt(i.value, 10) || 0)
    .reduce((a, b) => a + b, 0);
  const el = card.querySelector(".ev-total");
  el.textContent = `Σ ${total}`;
  el.classList.toggle("over", total > 508);
}

function markDirty() {
  state.dirty = true;
  $("#save-feedback").textContent = "";
  $("#save-feedback").className = "";
}

function collectSets() {
  return $$(".set-card").map(card => {
    const g = sel => card.querySelector(sel).value.trim() || null;
    const gNum = sel => { const v = card.querySelector(sel).value; return v === "" ? null : parseInt(v, 10); };
    const moves = [...card.querySelectorAll(".f-move")].map(i => i.value.trim() || null);
    const evs = {};
    card.querySelectorAll(".f-ev").forEach(i => {
      evs[`ev_${i.dataset.stat}`] = i.value === "" ? null : parseInt(i.value, 10);
    });
    return {
      pokemon: g(".f-pokemon") || "",
      ability: g(".f-ability"),
      item: g(".f-item"),
      nature: g(".f-nature"),
      tera_type: g(".f-tera"),
      level: gNum(".f-level") ?? 50,
      move1: moves[0], move2: moves[1], move3: moves[2], move4: moves[3],
      ...evs,
      raw_snippet: g(".f-snippet"),
    };
  }).filter(s => s.pokemon);
}

function diffAgainstPrefill(sets) {
  // Compare collected sets to the snapshot the prefiller returned,
  // index-aligned. Returns {count, fields: {field: totalCorrectedAcrossSets}}
  // and set_count for denominator in the dashboard.
  const snapshot = state.prefillSnapshot;
  if (!snapshot || snapshot.length === 0) return null;

  const fields = Object.fromEntries(DIFF_FIELDS.map(f => [f, 0]));
  let count = 0;
  const maxLen = Math.max(sets.length, snapshot.length);
  for (let i = 0; i < maxLen; i++) {
    const a = sets[i] || {};
    const b = snapshot[i] || {};
    for (const field of DIFF_FIELDS) {
      const av = a[field] ?? null;
      const bv = b[field] ?? null;
      if (av !== bv) { fields[field] += 1; count += 1; }
    }
  }
  return { count, fields, set_count: Math.max(sets.length, snapshot.length) };
}

async function runPrefill() {
  if (!state.current || !state.prefill.available) return;
  const { article } = state.current;
  const btn = $("#run-prefill");
  btn.disabled = true;
  btn.textContent = "✨ Pre-filling…";
  try {
    const r = await fetchJSON(`/api/prefill/${state.source}/${article.article_id}`, {
      method: "POST",
    });
    state.prefillSnapshot = r.sets.map(s => ({ ...s }));
    $("#sets-container").innerHTML = "";
    if (r.sets.length === 0) {
      addSet();
      $("#save-feedback").textContent = "Pre-fill returned no sets — label from scratch.";
    } else {
      r.sets.forEach(s => addSet(s, { prefilled: true }));
      $("#save-feedback").textContent =
        `Pre-filled ${r.sets.length} set(s) via ${r.prefiller}. Corrections are tracked for dashboard stats.`;
    }
    $("#save-feedback").className = "";
    state.dirty = false;
  } catch (e) {
    $("#save-feedback").textContent = `Pre-fill failed: ${e.message}`;
    $("#save-feedback").className = "error";
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ Pre-fill";
  }
}

async function saveLabel() {
  if (!state.current) return;
  const { article } = state.current;
  const sets = collectSets();
  const diff = diffAgainstPrefill(sets);
  const payload = {
    status: $("#save-status").value,
    sets,
    prefill_used: Boolean(state.prefillSnapshot),
    fields_corrected_count: diff?.count ?? 0,
    fields_corrected: diff ?? null,
  };
  const fb = $("#save-feedback");
  try {
    const r = await fetchJSON(`/api/labels/${state.source}/${article.article_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    fb.textContent = `Saved → ${r.output_path}`;
    fb.className = "ok";
    state.dirty = false;
    // Refresh list + current state
    await loadArticles();
    const match = state.articles.find(a => a.article_id === article.article_id);
    if (match) {
      state.current.state = { status: match.status, labeled_at: match.labeled_at, prefill_used: match.prefill_used ? 1 : 0 };
      renderArticle();
      renderList();
    }
  } catch (e) {
    fb.textContent = `Save failed: ${e.message}`;
    fb.className = "error";
  }
}

function stepUnlabeled(dir) {
  const list = state.articles;
  const curId = state.current?.article.article_id;
  const curIdx = curId ? list.findIndex(a => a.article_id === curId) : (dir > 0 ? -1 : list.length);
  let i = curIdx + dir;
  while (i >= 0 && i < list.length) {
    if (list[i].status !== "labeled") { loadArticle(list[i].article_id); return; }
    i += dir;
  }
}

async function runTriage() {
  if (!state.triage.available) return;
  const btn = $("#run-triage");
  btn.disabled = true;
  btn.textContent = "🔍 Triaging…";
  const fb = $("#save-feedback");
  try {
    const r = await fetchJSON(`/api/triage/${state.source}?limit=200`, { method: "POST" });
    const hasSets = r.results.filter(x => x.triage_result === "has_sets").length;
    const noSets = r.results.filter(x => x.triage_result === "no_sets").length;
    fb.textContent = `Triaged ${r.triaged} articles: ${hasSets} with sets, ${noSets} without.`;
    fb.className = "ok";
    await loadArticles();
  } catch (e) {
    fb.textContent = `Triage failed: ${e.message}`;
    fb.className = "error";
  } finally {
    btn.disabled = false;
    btn.textContent = "🔍 Triage";
  }
}

async function toggleStats() {
  const panel = $("#stats-panel");
  if (!panel.hidden) { panel.hidden = true; return; }
  const summary = $("#stats-summary");
  summary.textContent = "Loading…";
  try {
    const qs = new URLSearchParams({ source: state.source });
    const data = await fetchJSON(`/api/stats/correction-rate?${qs}`);
    summary.textContent =
      `${data.prefilled_count} pre-filled of ${data.labeled_count} labeled articles (source: ${state.source})`;
    const table = $("#stats-table");
    table.innerHTML = "<tr><th>Field</th><th>Corrected</th><th>Sets</th><th>Rate</th></tr>";
    Object.entries(data.fields).forEach(([field, s]) => {
      const tr = document.createElement("tr");
      const rate = s.rate == null ? "—" : `${(s.rate * 100).toFixed(1)}%`;
      const cls = s.rate == null ? "" : s.rate >= 0.3 ? "hi" : s.rate >= 0.1 ? "md" : "lo";
      tr.innerHTML = `<td></td><td>${s.corrected}</td><td>${s.total_sets}</td><td class="rate ${cls}">${rate}</td>`;
      tr.querySelector("td").textContent = field;
      table.appendChild(tr);
    });
    panel.hidden = false;
  } catch (e) {
    summary.textContent = `Stats failed: ${e.message}`;
    panel.hidden = false;
  }
}

init().catch(e => {
  document.body.innerHTML = `<pre style="padding:1rem;color:#cf222e">Init failed: ${e.message}</pre>`;
});
