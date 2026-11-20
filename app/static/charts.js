// Picks a chart for a Genie result (columns + rows) and draws it as SVG. No libraries.
(() => {
// Palette: validated categorical dark steps (all checks pass on #0B1118).
const CAT = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"];
const MUTED = "#3A4A58", INK = "#E6EDF3", INK2 = "#9FB0C0", GRID = "rgba(159,176,192,0.12)";
const NUM = new Set(["INT", "LONG", "BIGINT", "SHORT", "BYTE", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL"]);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pretty = (n) => n.replace(/_usd$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace(/\b(Po|Id|Eta|Kpi)\b/g, (w) => w.toUpperCase());
const isMoney = (n) => /usd|margin|revenue|value|cost|protected/i.test(n);
const isPct = (n) => /pct|percent|share/i.test(n);
function fmt(v, col) {
  if (v === null || v === undefined) return "—";
  if (typeof v !== "number") return String(v);
  if (col && isPct(col)) return v.toFixed(1) + "%";
  const a = Math.abs(v), m = col && isMoney(col) ? "$" : "";
  if (a >= 999500) return m + (v / 1e6).toFixed(2) + "M";
  if (a >= 1e4) return m + (v / 1e3).toFixed(0) + "K";
  if (a >= 1e3) return m + (v / 1e3).toFixed(1) + "K";
  return m + (Number.isInteger(v) ? v : v.toFixed(1));
}
const isDate = (v) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v);

function analyse(cols, rows, question) {
  const q = (question || "").toLowerCase();
  const nums = cols.map((c, i) => ({ ...c, i })).filter((c) => NUM.has(String(c.type).toUpperCase()) || rows.every((r) => typeof r[c.i] === "number" || r[c.i] === null));
  const dates = cols.map((c, i) => ({ ...c, i })).filter((c) => rows.length && rows.every((r) => r[c.i] === null || isDate(r[c.i])));
  const labels = cols.map((c, i) => ({ ...c, i })).filter((c) => !nums.some((n) => n.i === c.i) && !dates.some((d) => d.i === c.i));
  if (!rows.length || !nums.length) return { kind: "none" };
  if (rows.length === 1) return { kind: "tiles", nums };
  const measure = nums.find((n) => isMoney(n.name)) || nums[nums.length - 1];
  if (dates.length && rows.length >= 3 && /trend|over time|daily|day|week|timeline|cumulative|line|build/.test(q + " " + dates[0].name))
    return { kind: "line", x: dates[0], ys: nums.filter((n) => !/id$/.test(n.name)).slice(0, 4) };
  if (dates.length && rows.length >= 4 && !labels.length) return { kind: "line", x: dates[0], ys: nums.slice(0, 4) };
  const label = labels[0] || dates[0];
  if (!label) return { kind: "none" };
  const allPos = rows.every((r) => (r[measure.i] ?? 0) >= 0);
  if (/pareto|80|vital few|contribut/.test(q) && rows.length >= 3 && allPos) return { kind: "pareto", label, measure };
  if (/pie|donut|share|split|breakdown|by hazard|which hazard|mix|driv/.test(q) && rows.length <= 8 && allPos) return { kind: "donut", label, measure };
  return { kind: "bar", label, measure };
}

function tiles(cols, rows, a) {
  return `<div class="tiles">${a.nums.slice(0, 6).map((n) => `<div class="tile"><div class="tv">${esc(fmt(rows[0][n.i], n.name))}</div><div class="tl">${esc(pretty(n.name))}</div></div>`).join("")}</div>`;
}

function bars(rows, a, pareto) {
  let data = rows.map((r) => ({ k: String(r[a.label.i]), v: Number(r[a.measure.i]) || 0 }));
  if (pareto) data.sort((x, y) => y.v - x.v);
  const extra = Math.max(0, data.length - 14); if (extra) data = data.slice(0, 14);
  const total = pareto ? rows.reduce((s, r) => s + (Number(r[a.measure.i]) || 0), 0) : 0;
  const max = Math.max(...data.map((d) => d.v), 1), min = Math.min(0, ...data.map((d) => d.v));
  const W = 380, lw = 128, rw = pareto ? 78 : 56, bh = 18, gap = 6, H = data.length * (bh + gap) + 22;
  const x = (v) => lw + ((v - min) / (max - min)) * (W - lw - rw);
  let cum = 0, vital = 0;
  const marks = data.map((d, i) => {
    cum += d.v; const pct = total ? (100 * cum) / total : 0, isVital = pareto && (pct - (100 * d.v) / total) < 80; if (isVital) vital++;
    const y = 4 + i * (bh + gap), x0 = x(Math.min(0, d.v)), w = Math.max(2, Math.abs(x(d.v) - x(0)));
    const color = pareto ? (isVital ? CAT[0] : MUTED) : CAT[0];
    return `<g class="mk"><title>${esc(d.k)}: ${esc(fmt(d.v, a.measure.name))}${pareto ? ` · cumulative ${pct.toFixed(0)}%` : ""}</title>
      <rect x="0" y="${y - 2}" width="${W}" height="${bh + 4}" fill="transparent"/>
      <text x="${lw - 8}" y="${y + bh / 2}" text-anchor="end" class="lab">${esc(d.k.length > 18 ? d.k.slice(0, 17) + "…" : d.k)}</text>
      <path d="M${x0},${y} h${w - 4} a4,4 0 0 1 4,4 v${bh - 8} a4,4 0 0 1 -4,4 h-${w - 4} z" fill="${color}"/>
      <text x="${x0 + w + 6}" y="${y + bh / 2}" class="val">${esc(fmt(d.v, a.measure.name))}</text>
      ${pareto ? `<text x="${W - 2}" y="${y + bh / 2}" text-anchor="end" class="cum">${pct.toFixed(0)}%</text>` : ""}</g>`;
  }).join("");
  const head = pareto ? `<text x="${W - 2}" y="${H - 4}" text-anchor="end" class="axis">cumulative share</text>` : "";
  const svg = `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="${esc(pretty(a.measure.name))} by ${esc(pretty(a.label.name))}">${marks}${head}</svg>`;
  const note = pareto ? `<div class="chart-note"><span class="sw" style="background:${CAT[0]}"></span>The top ${vital} of ${rows.length} make up about 80% of the total ${esc(fmt(total, a.measure.name))}.${extra ? ` Showing the top 14.` : ""}</div>`
    : extra ? `<div class="chart-note">Showing the first 14 of ${rows.length}.</div>` : "";
  return svg + note;
}

function donut(rows, a) {
  const data = rows.map((r) => ({ k: String(r[a.label.i]), v: Number(r[a.measure.i]) || 0 })).sort((x, y) => y.v - x.v);
  const total = data.reduce((s, d) => s + d.v, 0) || 1, cx = 80, cy = 80, R = 70, r = 44;
  let ang = -Math.PI / 2;
  const seg = data.map((d, i) => {
    const a0 = ang, a1 = ang + (2 * Math.PI * d.v) / total; ang = a1;
    const gapA = data.length > 1 ? 0.012 : 0, s = a0 + gapA, e = Math.max(s + 0.001, a1 - gapA), large = e - s > Math.PI ? 1 : 0;
    const P = (rad, t) => `${cx + rad * Math.cos(t)},${cy + rad * Math.sin(t)}`;
    const path = data.length === 1 ? `M${cx - R},${cy} a${R},${R} 0 1,0 ${2 * R},0 a${R},${R} 0 1,0 -${2 * R},0 M${cx - r},${cy} a${r},${r} 0 1,1 ${2 * r},0 a${r},${r} 0 1,1 -${2 * r},0`
      : `M${P(R, s)} A${R},${R} 0 ${large} 1 ${P(R, e)} L${P(r, e)} A${r},${r} 0 ${large} 0 ${P(r, s)} Z`;
    return `<path class="mk" d="${path}" fill="${CAT[i % CAT.length]}" fill-rule="evenodd"><title>${esc(d.k)}: ${esc(fmt(d.v, a.measure.name))} (${((100 * d.v) / total).toFixed(0)}%)</title></path>`;
  }).join("");
  const legend = data.map((d, i) => `<div class="lg"><span class="sw" style="background:${CAT[i % CAT.length]}"></span><span class="lk">${esc(d.k)}</span><span class="lv">${((100 * d.v) / total).toFixed(0)}% · ${esc(fmt(d.v, a.measure.name))}</span></div>`).join("");
  return `<div class="donut"><svg viewBox="0 0 160 160" class="chart" role="img" aria-label="Share of ${esc(pretty(a.measure.name))}">${seg}
    <text x="80" y="76" text-anchor="middle" class="dv">${esc(fmt(total, a.measure.name))}</text><text x="80" y="94" text-anchor="middle" class="axis">total</text></svg><div class="legend">${legend}</div></div>`;
}

function line(rows, a) {
  const pts = rows.map((r) => ({ x: r[a.x.i], ys: a.ys.map((y) => (r[y.i] === null ? null : Number(r[y.i]))) })).sort((p, q) => (p.x < q.x ? -1 : 1));
  const W = 380, H = 190, L = 46, Rm = 10, T = 10, B = 26;
  const all = pts.flatMap((p) => p.ys.filter((v) => v !== null)), max = Math.max(...all, 0), min = Math.min(...all, 0), span = max - min || 1;
  const X = (i) => L + (i / Math.max(1, pts.length - 1)) * (W - L - Rm), Y = (v) => T + (1 - (v - min) / span) * (H - T - B);
  const ticks = [0, 0.5, 1].map((f) => min + f * span);
  const grid = ticks.map((v) => `<line x1="${L}" x2="${W - Rm}" y1="${Y(v)}" y2="${Y(v)}" stroke="${GRID}"/><text x="${L - 6}" y="${Y(v)}" text-anchor="end" class="axis">${esc(fmt(v, a.ys[0].name))}</text>`).join("");
  const xl = [0, Math.floor((pts.length - 1) / 2), pts.length - 1].map((i) => `<text x="${X(i)}" y="${H - 8}" text-anchor="middle" class="axis">${esc(String(pts[i].x).slice(5, 10))}</text>`).join("");
  const series = a.ys.map((y, k) => { let d = "", pen = false; pts.forEach((p, i) => { const v = p.ys[k]; if (v === null) { pen = false; return; } d += (pen ? "L" : "M") + X(i).toFixed(1) + "," + Y(v).toFixed(1); pen = true; }); return `<path d="${d}" fill="none" stroke="${CAT[k]}" stroke-width="2" stroke-linejoin="round"/>`; }).join("");
  const hits = pts.map((p, i) => `<g class="hit"><rect x="${X(i) - (W - L) / pts.length / 2}" y="${T}" width="${(W - L) / pts.length}" height="${H - T - B}" fill="transparent"/><line x1="${X(i)}" x2="${X(i)}" y1="${T}" y2="${H - B}" class="xh"/><title>${esc(p.x)}\n${a.ys.map((y, k) => `${pretty(y.name)}: ${fmt(p.ys[k], y.name)}`).join("\n")}</title></g>`).join("");
  const legend = a.ys.length > 1 ? `<div class="legend row">${a.ys.map((y, k) => `<div class="lg"><span class="sw ln" style="background:${CAT[k]}"></span><span class="lk">${esc(pretty(y.name))}</span></div>`).join("")}</div>` : "";
  return `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="${esc(a.ys.map((y) => pretty(y.name)).join(", "))} over time">${grid}${xl}${series}${hits}</svg>${legend}`;
}

function table(cols, rows) {
  const head = cols.map((c) => `<th>${esc(pretty(c.name))}</th>`).join("");
  const body = rows.slice(0, 50).map((r) => `<tr>${r.map((v, i) => `<td class="${typeof v === "number" ? "n" : ""}">${esc(fmt(v, cols[i].name))}</td>`).join("")}</tr>`).join("");
  return `<div class="tbl"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>${rows.length > 50 ? `<div class="chart-note">First 50 of ${rows.length} rows.</div>` : ""}</div>`;
}

function renderResult(cols, rows, question) {
  const a = analyse(cols, rows, question);
  let chart = "";
  if (a.kind === "tiles") chart = tiles(cols, rows, a);
  else if (a.kind === "bar") chart = bars(rows, a, false);
  else if (a.kind === "pareto") chart = bars(rows, a, true);
  else if (a.kind === "donut") chart = donut(rows, a);
  else if (a.kind === "line") chart = line(rows, a);
  const title = { bar: `${pretty(a.measure?.name || "")} by ${pretty(a.label?.name || "")}`, pareto: `Pareto · ${pretty(a.measure?.name || "")}`, donut: `Share of ${pretty(a.measure?.name || "")}`,
    line: `${(a.ys || []).map((y) => pretty(y.name)).join(" vs ")} over time`, tiles: "", none: "" }[a.kind];
  return { kind: a.kind, title, chart, table: rows.length ? table(cols, rows) : "" };
}
window.Charts = { renderResult, fmt, esc };
})();
