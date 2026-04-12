// Vanilla JS labeler — no framework.
// State lives in the DOM for the form; a tiny module-level cache
// holds the loaded articles and autocomplete.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  source: "nugget_bridge",
  format: "",
  statusFilter: "",
  articles: [],
  current: null,   // {article, state, label}
  autocomplete: null,
  dirty: false,
};

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`${r.status} ${r.statusText}: ${body}`);
  }
  return r.json();
}

async function init() {
  const [sources, formats, ac] = await Promise.all([
    fetchJSON("/api/sources"),
    fetchJSON("/api/formats"),
    fetchJSON("/api/autocomplete"),
  ]);
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
  $("#add-set").addEventListener("click", () => { addSet(); markDirty(); });
  $("#save").addEventListener("click", saveLabel);
  $("#prev-unlabeled").addEventListener("click", () => stepUnlabeled(-1));
  $("#next-unlabeled").addEventListener("click", () => stepUnlabeled(+1));
  window.addEventListener("beforeunload", e => {
    if (state.dirty) { e.preventDefault(); e.returnValue = ""; }
  });

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
  const filtered = state.articles.filter(a =>
    !state.statusFilter || a.status === state.statusFilter
  );
  filtered.forEach(a => {
    const el = document.createElement("div");
    el.className = "article-item" + (state.current?.article.article_id === a.article_id ? " active" : "");
    el.innerHTML = `<span class="badge ${a.status}">${a.status.replace("_", " ")}</span>
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

function addSet(data = {}) {
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
  card.querySelectorAll("input, textarea").forEach(inp => {
    inp.addEventListener("input", () => { markDirty(); if (inp.classList.contains("f-ev")) updateEvTotal(card); });
  });
  $("#sets-container").appendChild(card);
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

async function saveLabel() {
  if (!state.current) return;
  const { article } = state.current;
  const sets = collectSets();
  const payload = {
    status: $("#save-status").value,
    sets,
    prefill_used: Boolean(state.current?.label?.prefill_used),
    fields_corrected_count: 0,
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

init().catch(e => {
  document.body.innerHTML = `<pre style="padding:1rem;color:#cf222e">Init failed: ${e.message}</pre>`;
});
