// UI wiring: KPIs, layers, hazards list, timeline and the chat that talks to the Genie agent.
const $ = (id) => document.getElementById(id);
const { fmt, esc, renderResult } = window.Charts;
const LAYERS = [
  ["nodes", "Plants, suppliers & ports", "#4FE3FF"], ["lanes", "Road & sea shipments", "#3FD6B5"], ["air", "Air freight options", "#9CC9F0"],
  ["cyclone", "Cyclone forecast", "#F0A63C"], ["quake", "Earthquakes", "#FF6B6B"], ["congestion", "Port congestion", "#F0A63C"],
];
const STARTERS = [
  ["Which plants run out of materials first because of the disruptions?", "Shortage forecast"],
  ["What should procurement do for each delayed purchase order, and what does it cost?", "Action plan"],
  ["Show a Pareto of margin at risk by plant and material", "Pareto"],
  ["What share of delayed PO value does each hazard cause?", "Pie"],
  ["Which suppliers are inside a hazard zone right now?", "Supplier exposure"],
];
let map, DATA, conversationId = null, busy = false;

async function loadGeo() {
  const [land, base2d, places] = await Promise.all(["land110", "base2d", "places"].map((n) => fetch(`/static/geo/${n}.json`).then((r) => r.json())));
  return { land, base2d, places };
}

function kpis(k) {
  const tiles = k ? [
    ["Margin at risk", fmt(k.margin_at_risk_usd, "usd"), `${fmt(k.revenue_at_risk_usd, "usd")} revenue · ${fmt(k.cases_at_risk)} cases`, "#FF8A6B"],
    ["Delayed PO lines", `${k.delayed_po_lines} / ${k.open_po_lines}`, `${fmt(k.delayed_po_value_usd, "usd")} · ${k.pct_value_delayed}% of open value`, "#F0A63C"],
    ["Avg delay", `${k.avg_delay_days} days`, `worst ${k.max_delay_days} days`, "#E6EDF3"],
    ["Plants with new shortage", `${k.plants_with_new_shortage}`, `${k.materials_with_new_shortage} plant-materials run out`, "#FF8A6B"],
    ["Recommended action cost", fmt(k.recommended_action_cost_usd, "usd"), "re-source + expedite", "#E6EDF3"],
    ["Margin protected", fmt(k.margin_protected_usd, "usd"), k.recommended_action_cost_usd ? `${(k.margin_protected_usd / k.recommended_action_cost_usd).toFixed(1)}× return on action cost` : "", "#5EE6A8"],
  ] : Array(6).fill(["", "·", "", ""]);
  $("kpis").innerHTML = tiles.map(([l, v, s, c]) => `<div class="kpi${k ? "" : " skel"}"><div class="kv" style="color:${c}">${esc(v)}</div><div class="kl">${esc(l)}</div><div class="ks">${esc(s)}</div></div>`).join("");
}

function layers() {
  const box = $("layers");
  box.innerHTML = `<div class="ph">Layers</div>` + LAYERS.map(([id, name, color]) =>
    `<button class="layer" data-id="${id}" aria-pressed="${map.layers[id]}"><span>${name}</span><span class="sw" style="${map.layers[id] ? `background:${color}` : ""}"></span></button>`).join("");
  box.querySelectorAll(".layer").forEach((b) => b.onclick = () => { map.layers[b.dataset.id] = !map.layers[b.dataset.id]; layers(); $("timeline").hidden = !map.layers.cyclone || !DATA?.cyclones.length; });
}

function events(d) {
  const color = { cyclone: "#F0A63C", earthquake: "#FF6B6B", port_congestion: "#F0A63C" };
  $("eventList").innerHTML = d.events.map((e, i) => `<button class="ev" data-i="${i}" style="border-color:${color[e.hazard_type] || "#F0A63C"}">
    <div class="en">${esc(e.event_name)}</div><div class="ei">${e.po_lines_hit} PO lines · ${fmt(e.margin_at_risk_usd, "usd")} margin at risk · +${e.avg_delay_days_added} d</div></button>`).join("")
    || `<div class="ei">No active hazards near the network.</div>`;
  $("eventList").querySelectorAll(".ev").forEach((b) => b.onclick = () => { const e = d.events[+b.dataset.i]; ask(`Which plants and suppliers are affected by ${e.event_name}, and how much margin is at risk?`); });
}

// ---- map focus from an answer: any plant / supplier / port named in the text or the result rows lights up
function focusFrom(text, rows, question) {
  const hay = [text, ...rows.flat().map((v) => (v === null ? "" : String(v)))].join(" | ").toLowerCase();
  const f = { plants: new Set(), suppliers: new Set(), ports: new Set(), labels: {}, delayedOnly: /delay|storm|cyclone|hazard|disrupt|late/i.test(question), alts: /re-?source|procure|action|alternate|should/i.test(question + " " + text) };
  const hit = (n) => hay.includes(n.id.toLowerCase()) || (n.name && n.name.length > 3 && hay.includes(n.name.toLowerCase()));
  for (const p of DATA.plants) if (hit(p)) { f.plants.add(p.id); f.labels[p.id] = `${p.name}${p.stockout ? " · runs short " + p.stockout.slice(5) : ""}`; }
  for (const s of DATA.suppliers) if (hit(s)) { f.suppliers.add(s.id); f.labels[s.id] = s.name; }
  const plantNames = new Set(DATA.plants.filter((p) => f.plants.has(p.id)).map((p) => p.name.toLowerCase()));
  for (const p of DATA.ports) if (hit(p)) { f.ports.add(p.id); if (!plantNames.has(p.name.toLowerCase().replace(/ port$/, ""))) f.labels[p.id] = p.name; }
  const n = f.plants.size + f.suppliers.size + f.ports.size;
  if (n > 14) for (const k of Object.keys(f.labels)) if (!f.plants.has(k)) delete f.labels[k];
  return n ? f : null;
}
function applyFocus(f) {
  map.setFocus(f);
}

// ---- chat
function md(s) {
  const lines = esc(s || "").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>").split(/\n/);
  let html = "", list = false;
  for (const l of lines) {
    const m = l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
    if (m) { if (!list) { html += "<ul>"; list = true; } html += `<li>${m[1]}</li>`; continue; }
    if (list) { html += "</ul>"; list = false; }
    if (l.trim()) html += `<p>${l}</p>`;
  }
  return html + (list ? "</ul>" : "");
}
function bubble(cls, html) { $("welcome")?.remove(); const d = document.createElement("div"); d.className = cls; d.innerHTML = html; $("msgs").appendChild(d); $("msgs").scrollTop = $("msgs").scrollHeight; return d; }
const THINK = ["Reading the risk tables…", "Writing the query…", "Checking the numbers…"];

async function ask(question) {
  question = (question || "").trim(); if (!question || busy) return;
  busy = true; $("send").disabled = true; $("q").value = ""; autosize();
  bubble("me", esc(question));
  const b = bubble("bot", `<div class="thinking"><i></i><i></i><i></i><span>${THINK[0]}</span></div>`);
  let k = 0; const tick = setInterval(() => { const s = b.querySelector(".thinking span"); if (s) s.textContent = THINK[++k % THINK.length]; }, 2500);
  try {
    const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, conversation_id: conversationId }) });
    const j = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    conversationId = j.conversation_id;
    const res = j.columns.length ? renderResult(j.columns, j.rows, question) : null;
    const f = focusFrom(j.text, j.rows, question);
    let html = `<div class="txt">${md(j.text || (j.rows.length ? "Here is what I found." : "Genie didn't return an answer for this one."))}</div>`;
    if (j.notes?.length) html += `<div class="notes">${j.notes.map((n) => `<div>${esc(n)}</div>`).join("")}</div>`;
    if (j.raw) html += `<details class="raw"><summary>What Genie returned (for troubleshooting)</summary><pre>${esc(JSON.stringify(j.raw, null, 2).slice(0, 6000))}</pre></details>`;
    if (res && res.chart) html += `<div class="card"><div class="cth"><span>${esc(res.title)}</span><button class="tt">Show table</button></div>${res.chart}<div class="tw" hidden>${res.table}</div></div>`;
    else if (res && res.table) html += `<div class="card">${res.table}</div>`;
    if (f) html += `<div class="mapnote">◉ Highlighted on the map</div>`;
    if (j.suggestions?.length) html += `<div class="sugg">${j.suggestions.map((s) => `<button>${esc(s)}</button>`).join("")}</div>`;
    b.innerHTML = html;
    b.querySelector(".tt")?.addEventListener("click", (e) => { const t = b.querySelector(".tw"); t.hidden = !t.hidden; e.target.textContent = t.hidden ? "Show table" : "Hide table"; });
    b.querySelectorAll(".sugg button").forEach((s) => s.onclick = () => ask(s.textContent));
    if (f) applyFocus(f);
  } catch (e) {
    b.innerHTML = `<div class="err">Sorry, that didn't work: ${esc(e.message)}</div>`;
  } finally {
    clearInterval(tick); busy = false; $("send").disabled = false; $("msgs").scrollTop = $("msgs").scrollHeight;
  }
}
function autosize() { const t = $("q"); t.style.height = "auto"; t.style.height = Math.min(120, t.scrollHeight) + "px"; }

function starters() {
  $("starters").innerHTML = STARTERS.map(([q, tag]) => `<button class="chip">${esc(q)}<small>${esc(tag)}</small></button>`).join("");
  $("starters").querySelectorAll(".chip").forEach((c, i) => c.onclick = () => ask(STARTERS[i][0]));
}

function hud(m) {
  const now = performance.now(); if (now - (hud.t || 0) < 250) return; hud.t = now;
  const c = m.cam;
  $("hud").textContent = `${Math.abs(c.lat).toFixed(2)}°${c.lat >= 0 ? "N" : "S"}  ${Math.abs(c.lon).toFixed(2)}°${c.lon >= 0 ? "E" : "W"}  ·  ALT ${Math.round(12000 / c.zoom).toLocaleString("en-US")} km`;
  if (DATA) {
    const h = Math.round(m.hourF), d = new Date(Date.parse(DATA.as_of + "T00:00:00Z") + h * 3600000);
    $("hourLabel").textContent = `T+${h} h · ${d.toUTCString().slice(5, 11)} ${String(d.getUTCHours()).padStart(2, "0")}:00`;
    if (document.activeElement !== $("scrub")) $("scrub").value = h;
  }
}

async function boot() {
  kpis(null); starters();
  map = new GeoMap($("map"), $("mapHost"), await loadGeo(), hud);
  layers();
  $("btn2d").onclick = () => { map.setMode("2d"); $("btn2d").className = "on"; $("btn3d").className = ""; $("btn2d").setAttribute("aria-pressed", "true"); $("btn3d").setAttribute("aria-pressed", "false"); };
  $("btn3d").onclick = () => { map.setMode("3d"); $("btn3d").className = "on"; $("btn2d").className = ""; $("btn3d").setAttribute("aria-pressed", "true"); $("btn2d").setAttribute("aria-pressed", "false"); };
  $("zin").onclick = () => map.zoomBy(1.5); $("zout").onclick = () => map.zoomBy(1 / 1.5); $("home").onclick = () => applyFocus(null) || map.home();
  document.addEventListener("keydown", (e) => { if (e.altKey && e.code === "KeyN") { e.preventDefault(); $("newChat").click(); } });
  $("play").onclick = () => { map.playing = !map.playing; $("play").textContent = map.playing ? "❚❚" : "▶"; $("play").setAttribute("aria-label", map.playing ? "Pause forecast" : "Play forecast"); };
  $("scrub").oninput = (e) => { map.hourF = +e.target.value; map.playing = false; $("play").textContent = "▶"; };
  $("askForm").onsubmit = (e) => { e.preventDefault(); ask($("q").value); };
  $("q").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask($("q").value); } });
  $("q").addEventListener("input", autosize);
  $("newChat").onclick = () => { conversationId = null; $("msgs").innerHTML = `<div class="welcome" id="welcome"><div class="wt">New conversation</div><div class="wsub">Ask anything about delays, shortages and actions.</div><div class="starters" id="starters"></div></div>`; starters(); applyFocus(null); map.home(); };
  try {
    const r = await fetch("/api/map"), j = await r.json();
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    DATA = j; map.setData(j); kpis(j.kpi); events(j);
    $("scrub").max = map.maxHour; $("timeline").hidden = !j.cyclones.length;
    $("asOf").textContent = `Live · risk as of ${new Date(j.as_of + "T00:00:00Z").toUTCString().slice(5, 16)}`; $("liveDot").className = "dot live";
  } catch (e) {
    $("asOf").textContent = "Not connected"; $("banner").hidden = false;
    $("banner").innerHTML = `<strong>Couldn't load the risk tables.</strong> ${esc(e.message)}<br>Check that the app has the SQL warehouse resource and SELECT access to the <code>supply_risk_dev</code> catalog.`;
  }
}
boot();
