// God's Eye View map engine: 2D tactical map (Mercator) + 3D globe (orthographic), plain canvas, no libraries.
(() => {
const RAD = Math.PI / 180;
const RISK_COLOR = { High: "#FF6B4A", Medium: "#F0A63C", Low: "#4FE3FF", None: "#4FE3FF" };
const HOME3D = { lon: 84, lat: 17, zoom: 1.15 };
const HOME2D = { lon: 83.5, lat: 17.5, zoom: 2.7 };
const mercY = (lat) => { const f = Math.max(-80, Math.min(80, lat)) * RAD; return Math.log(Math.tan(Math.PI / 4 + f / 2)) / RAD; };
const vec = (p) => { const l = p[0] * RAD, f = p[1] * RAD, c = Math.cos(f); return [c * Math.cos(l), c * Math.sin(l), Math.sin(f)]; };
const ll = (v) => [Math.atan2(v[1], v[0]) / RAD, Math.asin(Math.max(-1, Math.min(1, v[2]))) / RAD];
const arc = (a, b) => { const u = vec(a), w = vec(b); return Math.acos(Math.max(-1, Math.min(1, u[0] * w[0] + u[1] * w[1] + u[2] * w[2]))); };
function slerp(a, b) {
  const u = vec(a), w = vec(b), om = arc(a, b), s = Math.sin(om);
  return (t) => { if (s < 1e-9) return a; const k1 = Math.sin((1 - t) * om) / s, k2 = Math.sin(t * om) / s; return ll([u[0] * k1 + w[0] * k2, u[1] * k1 + w[1] * k2, u[2] * k1 + w[2] * k2]); };
}
function densify(pts, step) {
  const out = [pts[0]];
  for (let i = 0; i < pts.length - 1; i++) { const n = Math.max(1, Math.ceil(arc(pts[i], pts[i + 1]) / RAD / step)), f = slerp(pts[i], pts[i + 1]); for (let k = 1; k <= n; k++) out.push(f(k / n)); }
  return out;
}
function circle(c, rDeg, step) {
  const f1 = c[1] * RAD, l1 = c[0] * RAD, d = rDeg * RAD, out = [];
  for (let b = 0; b <= 360; b += step || 8) {
    const br = b * RAD, f2 = Math.asin(Math.sin(f1) * Math.cos(d) + Math.cos(f1) * Math.sin(d) * Math.cos(br));
    out.push([(l1 + Math.atan2(Math.sin(br) * Math.sin(d) * Math.cos(f1), Math.cos(d) - Math.sin(f1) * Math.sin(f2))) / RAD, f2 / RAD]);
  }
  return out;
}
function hull(points) {
  const p = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]); if (p.length < 3) return null;
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]), lo = [], up = [];
  for (const q of p) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
  up.pop(); lo.pop(); return lo.concat(up);
}
const ease = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
function track(pts) { const segs = []; let total = 0; for (let j = 0; j < pts.length - 1; j++) { const len = arc(pts[j], pts[j + 1]); segs.push({ start: total, len, f: slerp(pts[j], pts[j + 1]) }); total += len; } return { path: pts, segs, total }; }
function pointAt(l, f) { const d = f * l.total; for (const s of l.segs) if (d <= s.start + s.len || s === l.segs[l.segs.length - 1]) return s.f(s.len ? Math.min(1, (d - s.start) / s.len) : 0); return l.path[0]; }

class GeoMap {
  constructor(canvas, host, geo, onTick) {
    this.canvas = canvas; this.host = host; this.ctx = canvas.getContext("2d"); this.onTick = onTick || (() => {});
    this.mode = "2d"; this.cam = { lon: 78, lat: 19, zoom: 1.6 }; this.fly = null; this.drag = null; this.lastInteract = -1e9;
    this.layers = { nodes: true, lanes: true, air: true, cyclone: true, quake: true, congestion: true };
    this.focus = null; this.playing = true; this.hourF = 0; this.maxHour = 120;
    this.landRings = []; for (const f of geo.land.features) { const g = f.geometry; for (const poly of g.type === "Polygon" ? [g.coordinates] : g.coordinates) for (const r of poly) this.landRings.push(r); }
    this.base2d = geo.base2d; this.places = geo.places;
    this.grat = [];
    for (let lat = -80; lat <= 80; lat += 10) { const r = []; for (let lon = -180; lon <= 180; lon += 3) r.push([lon, lat]); this.grat.push(r); }
    for (let lon = -180; lon < 180; lon += 10) { const r = []; for (let lat = -80; lat <= 80; lat += 3) r.push([lon, lat]); this.grat.push(r); }
    let s = 7; const r = () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; };
    this.stars = Array.from({ length: 280 }, () => ({ x: r(), y: r(), s: r() < 0.9 ? 1 : 1.8, a: 0.15 + r() * 0.6 }));
    this.bind(); this.resize();
    new ResizeObserver(() => this.resize()).observe(host);
    this.prev = performance.now();
    const loop = (t) => { try { this.frame(t); } catch (e) { console.error("[map]", e); } requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }
  setData(d) {
    this.data = d;
    this.byId = {}; for (const k of ["plants", "suppliers", "ports"]) for (const n of d[k]) this.byId[n.id] = n;
    this.lanes = d.lanes.map((l, i) => Object.assign({}, l, track(l.path), { dense: densify(l.path, 1.5), off: (i * 0.618) % 1 }));
    this.alts = d.alts.map(([s, p], i) => { const a = [this.byId[s].lon, this.byId[s].lat], b = [this.byId[p].lon, this.byId[p].lat]; return { s, p, dense: densify([a, b], 1.5), f: slerp(a, b), off: i * 0.3 }; });
    this.storms = d.cyclones.map((c) => ({ name: c.name, pts: c.pts, line: densify(c.pts.map((p) => [p[0], p[1]]), 1) }));
    this.maxHour = Math.max(24, ...d.cyclones.map((c) => c.pts[c.pts.length - 1][4]));
    this.movers = []; let nt = 0, ns = 0, na = 0; const pad = (n) => String(n).padStart(2, "0");
    this.lanes.forEach((l, i) => {
      if (!(l.delayed || i % 4 === 0)) return;
      if (l.mode === "road") this.movers.push(Object.assign(track(l.path), { kind: "truck", id: "TRK-" + pad(++nt), lane: l, period: 42000, off: (i * 0.37) % 1 }));
      else if (l.path.length > 3) this.movers.push(Object.assign(track(l.path.slice(1, -1)), { kind: "ship", id: "SEA-" + pad(++ns), lane: l, period: 300000, off: (i * 0.37) % 1 }));
      if (l.mode === "sea" && l.delayed) {
        const pl = this.byId[l.p], a = l.path[1], b = [pl.lon, pl.lat];
        this.movers.push(Object.assign(track([a, b]), { kind: "plane", id: "AIR-" + pad(++na), lane: l, period: 30000, off: (i * 0.53) % 1, dense: densify([a, b], 1) }));
      }
    });
    if (!this.started) { this.started = true; this.flyTo(HOME2D, 2600); }
  }
  bind() {
    const c = this.canvas;
    c.addEventListener("pointerdown", (e) => { this.drag = { x: e.clientX, y: e.clientY, lon: this.cam.lon, lat: this.cam.lat }; this.fly = null; this.lastInteract = performance.now(); try { c.setPointerCapture(e.pointerId); } catch (_) {} });
    c.addEventListener("pointermove", (e) => {
      if (!this.drag) return;
      if (this.mode === "2d") { const S = this.scale2d(); this.cam.lon = Math.max(40, Math.min(130, this.drag.lon - (e.clientX - this.drag.x) / S)); this.cam.lat = Math.max(-12, Math.min(45, this.drag.lat + (e.clientY - this.drag.y) / S * Math.cos(this.cam.lat * RAD))); }
      else { const k = 0.3 / this.cam.zoom; this.cam.lon = this.drag.lon - (e.clientX - this.drag.x) * k; this.cam.lat = Math.max(-75, Math.min(75, this.drag.lat + (e.clientY - this.drag.y) * k)); }
      this.lastInteract = performance.now();
    });
    const up = () => { this.drag = null; }; c.addEventListener("pointerup", up); c.addEventListener("pointercancel", up);
    c.addEventListener("wheel", (e) => { e.preventDefault(); this.fly = null; this.lastInteract = performance.now(); this.cam.zoom = Math.max(0.75, Math.min(14, this.cam.zoom * Math.exp(-e.deltaY * 0.0015))); }, { passive: false });
  }
  resize() {
    const w = Math.max(1, this.host.clientWidth), h = Math.max(1, this.host.clientHeight), dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.W = w; this.H = h; this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr); this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  setMode(m) {
    if (m === this.mode) return; this.mode = m;
    if (m === "2d") this.flyTo(this.focus && this.focus.cam ? this.focus.cam : HOME2D, 1500); else { this.lastInteract = -1e9; this.flyTo({ lon: this.cam.lon, lat: this.cam.lat, zoom: this.focus ? 2 : HOME3D.zoom }, 1500); }
  }
  home() { this.focus = null; this.lastInteract = -1e9; this.flyTo(this.mode === "2d" ? HOME2D : HOME3D, 2000); }
  zoomBy(f) { this.lastInteract = performance.now(); this.flyTo({ lon: this.cam.lon, lat: this.cam.lat, zoom: Math.max(0.75, Math.min(14, this.cam.zoom * f)) }, 450); }
  flyTo(to, dur) { const from = Object.assign({}, this.cam); this.fly = { from, to, dl: ((to.lon - from.lon + 540) % 360) - 180, t0: performance.now(), dur: dur || 2200 }; }
  // focus = {plants:Set, suppliers:Set, ports:Set, labels:{id:text}, delayedOnly, alts}
  setFocus(f) {
    this.focus = f; if (!f) return;
    const pts = [...f.plants, ...f.suppliers, ...f.ports].map((id) => this.byId[id]).filter(Boolean);
    if (!pts.length) return;
    const lons = pts.map((p) => p.lon), lats = pts.map((p) => p.lat);
    const lon = (Math.min(...lons) + Math.max(...lons)) / 2, lat = (Math.min(...lats) + Math.max(...lats)) / 2;
    const span = Math.max(4, Math.max(...lons) - Math.min(...lons), (Math.max(...lats) - Math.min(...lats)) * 1.3);
    const z2 = Math.max(1.6, Math.min(9, 2.7 * 22 / span)), z3 = Math.max(1, Math.min(6, 1.15 * 30 / span));
    f.cam = { lon, lat, zoom: z2 };
    this.flyTo(this.mode === "2d" ? f.cam : { lon, lat, zoom: z3 }, 2200);
  }
  scale2d() { return Math.min(this.W || 1000, this.H || 820) * 0.42 * this.cam.zoom / 57.3; }
  pr(p) {
    const P = this.P;
    if (P.flat) return [P.cx + (p[0] - P.l0) * P.S, P.cy - (mercY(p[1]) - P.m0) * P.S, true];
    const l = (p[0] - P.l0) * RAD, f = p[1] * RAD, cf = Math.cos(f), sl = Math.sin(l), cl = Math.cos(l), sf = Math.sin(f);
    let x = P.R * cf * sl, y = P.R * (P.cp * sf - P.sp * cf * cl); const vis = P.sp * sf + P.cp * cf * cl > 0;
    if (!vis) { const m = Math.hypot(x, y) || 1; x = x / m * P.R; y = y / m * P.R; }
    return [P.cx + x, P.cy - y, vis];
  }
  line(pts) { const ctx = this.ctx; let pen = false; for (const p of pts) { const q = this.pr(p); if (!q[2]) { pen = false; continue; } if (pen) ctx.lineTo(q[0], q[1]); else { ctx.moveTo(q[0], q[1]); pen = true; } } }
  ring(pts) { const ctx = this.ctx, q = pts.map((p) => this.pr(p)); if (!q.some((v) => v[2])) return; ctx.moveTo(q[0][0], q[0][1]); for (let i = 1; i < q.length; i++) ctx.lineTo(q[i][0], q[i][1]); ctx.closePath(); }
  frame(t) {
    const dt = Math.min(50, t - this.prev); this.prev = t; const cam = this.cam;
    if (this.fly) {
      const f = this.fly, p = Math.min(1, (t - f.t0) / f.dur), e = ease(p);
      cam.lon = f.from.lon + f.dl * e; cam.lat = f.from.lat + (f.to.lat - f.from.lat) * e;
      const z = f.from.zoom + (f.to.zoom - f.from.zoom) * e, hop = Math.max(0, Math.min(f.from.zoom, f.to.zoom) - 0.9) * 0.55 + 0.12;
      cam.zoom = Math.max(0.75, z - hop * Math.sin(Math.PI * p) * Math.min(1, z)); if (p >= 1) this.fly = null;
    } else if (this.mode === "3d" && !this.focus && !this.drag && t - this.lastInteract > 3500) cam.lon += dt * 0.0015;
    cam.lon = ((cam.lon + 540) % 360) - 180;
    if (this.playing) this.hourF = (this.hourF + dt * this.maxHour / 60000) % this.maxHour;
    this.draw(t); this.onTick(this);
  }
  drawGlobeBase(t) {
    const ctx = this.ctx, W = this.W, H = this.H, cam = this.cam, { R, cx, cy } = this.P;
    ctx.fillStyle = "#02040A"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#CFE7FF";
    for (const s of this.stars) { const x = (((s.x * W - cam.lon * 1.2) % W) + W) % W, y = (((s.y * H + cam.lat * 1.2) % H) + H) % H; ctx.globalAlpha = s.a * (0.7 + 0.3 * Math.sin(t / 900 + s.x * 40)); ctx.fillRect(x, y, s.s, s.s); }
    ctx.globalAlpha = 1;
    const glow = ctx.createRadialGradient(cx, cy, R * 0.94, cx, cy, R * 1.16); glow.addColorStop(0, "rgba(79,227,255,0.30)"); glow.addColorStop(1, "rgba(79,227,255,0)");
    ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(cx, cy, R * 1.16, 0, Math.PI * 2); ctx.fill();
    const og = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.05, cx, cy, R); og.addColorStop(0, "#0E2A44"); og.addColorStop(1, "#030A13");
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fillStyle = og; ctx.fill();
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
    ctx.beginPath(); for (const g of this.grat) this.line(g); ctx.strokeStyle = "rgba(79,227,255,0.08)"; ctx.lineWidth = 0.6; ctx.stroke();
    ctx.beginPath(); for (const r of this.landRings) this.ring(r); ctx.fillStyle = "#1D3649"; ctx.fill("evenodd");
    ctx.beginPath(); for (const r of this.landRings) this.line(r); ctx.strokeStyle = "rgba(160,210,240,0.55)"; ctx.lineWidth = 0.8; ctx.stroke();
  }
  drawMapBase() {
    const ctx = this.ctx, W = this.W, H = this.H, z = this.cam.zoom;
    ctx.fillStyle = "#0B171D"; ctx.fillRect(0, 0, W, H);
    ctx.beginPath(); for (const r of this.base2d.land) this.ring(r); ctx.fillStyle = "#1A2327"; ctx.fill("evenodd"); ctx.strokeStyle = "rgba(110,150,165,0.45)"; ctx.lineWidth = 0.8; ctx.stroke();
    ctx.setLineDash([3, 3]); ctx.beginPath(); for (const b of this.base2d.borders) this.line(b); ctx.strokeStyle = "rgba(150,165,175,0.45)"; ctx.stroke(); ctx.setLineDash([]);
    const text = (str, lat, lon, font, color, halo) => {
      const v = this.pr([lon, lat]); if (v[0] < -80 || v[0] > W + 80 || v[1] < -20 || v[1] > H + 20) return;
      ctx.font = font; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      if (halo) { ctx.lineWidth = 3; ctx.strokeStyle = "rgba(11,20,25,0.9)"; ctx.strokeText(str, v[0], v[1]); }
      ctx.fillStyle = color; ctx.fillText(str, v[0], v[1]);
    };
    const P = this.places;
    for (const s of P.seas) text(s[0], s[1], s[2], "italic 13px Inter, system-ui, sans-serif", "#3F7383", false);
    if (z <= 6) for (const c of P.countries) text(c[0], c[1], c[2], "600 13px Inter, system-ui, sans-serif", "#8D9AA0", true);
    if (z >= 3 && z <= 9) for (const s of P.states) text(s[0], s[1], s[2], "italic 11px Inter, system-ui, sans-serif", "#66767D", true);
    const minRank = z >= 5 ? 3 : z >= 3.2 ? 2 : 1;
    for (const c of P.cities) if (c[3] <= minRank) text(c[0], c[1], c[2], "12px Inter, system-ui, sans-serif", "#C7CFD2", true);
    ctx.textAlign = "start";
  }
  spiral(x, y, r, t) {
    const ctx = this.ctx; ctx.save(); ctx.translate(x, y); ctx.rotate(-t / 420); ctx.shadowColor = "rgba(110,120,255,0.8)"; ctx.shadowBlur = 10;
    ctx.strokeStyle = "#6E7BFF"; ctx.lineWidth = Math.max(2.5, r * 0.18); ctx.lineCap = "round";
    for (let arm = 0; arm < 2; arm++) { ctx.beginPath(); for (let k = 0; k <= 40; k++) { const th = k / 40 * Math.PI * 2.2, rr = r * (0.18 + 0.82 * k / 40), a = th + arm * Math.PI; k ? ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr) : ctx.moveTo(Math.cos(a) * rr, Math.sin(a) * rr); } ctx.stroke(); }
    ctx.shadowBlur = 0; ctx.fillStyle = "#B9C2FF"; ctx.beginPath(); ctx.arc(0, 0, r * 0.18, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  }
  truck(x, y, k, flip) {
    const c = this.ctx; c.save(); c.translate(x, y); c.scale(flip ? -k : k, k); c.fillStyle = "#C9F7E6"; c.strokeStyle = "#1E8C75"; c.lineWidth = 1;
    c.beginPath(); c.rect(-11, -8, 13, 10); c.fill(); c.stroke();
    c.fillStyle = "#7FE0C2"; c.beginPath(); c.moveTo(2, -5); c.lineTo(7, -5); c.lineTo(10, -1); c.lineTo(10, 2); c.lineTo(2, 2); c.closePath(); c.fill(); c.stroke();
    c.fillStyle = "#0B1418"; c.fillRect(3.5, -4, 3, 2.5);
    for (const wx of [-7, 6]) { c.beginPath(); c.arc(wx, 3, 2.4, 0, Math.PI * 2); c.fillStyle = "#0B1418"; c.fill(); c.strokeStyle = "#7FE0C2"; c.stroke(); }
    c.restore();
  }
  ship(x, y, k, t, off) {
    const c = this.ctx; c.save(); c.translate(x, y + Math.sin(t / 500 + off * 9) * 0.8); c.scale(k, k);
    c.fillStyle = "#F0A63C"; c.fillRect(-8, -6, 4, 5); c.fillStyle = "#E26D5A"; c.fillRect(-4, -6, 4, 5); c.fillStyle = "#F5C26B"; c.fillRect(0, -5, 4, 4); c.fillStyle = "#DDE8EE"; c.fillRect(5, -9, 3.5, 8);
    c.fillStyle = "#EAF2F6"; c.strokeStyle = "#5C8FB0"; c.lineWidth = 1; c.beginPath(); c.moveTo(-12, -1); c.lineTo(12, -1); c.lineTo(8.5, 5); c.lineTo(-8.5, 5); c.closePath(); c.fill(); c.stroke();
    c.strokeStyle = "#4FB7E8"; c.lineWidth = 1.4; c.beginPath(); for (let i = -12; i <= 12; i++) { const yy = 8 + Math.sin(i * 0.8 + t / 300); i === -12 ? c.moveTo(i, yy) : c.lineTo(i, yy); } c.stroke(); c.restore();
  }
  plane(x, y, k, ang) {
    const c = this.ctx; c.save(); c.translate(x, y); c.rotate(ang); c.scale(k, k); c.fillStyle = "#E3EEF8"; c.strokeStyle = "#7FB8D8"; c.lineWidth = 0.8; c.beginPath();
    [[12, 0], [9, -1.6], [2, -1.6], [-3, -10], [-6, -10], [-3, -1.6], [-9, -1.6], [-11, -5], [-13, -5], [-11.5, 0], [-13, 5], [-11, 5], [-9, 1.6], [-3, 1.6], [-6, 10], [-3, 10], [2, 1.6], [9, 1.6]].forEach((p, i) => (i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])));
    c.closePath(); c.fill(); c.stroke(); c.restore();
  }
  tag(x, y, text, color) {
    const c = this.ctx; c.font = "600 10px 'JetBrains Mono', ui-monospace, monospace"; const w = c.measureText(text).width + 10, h = 16, lx = x - w / 2;
    c.fillStyle = "rgba(6,12,16,0.9)"; c.fillRect(lx, y, w, h); c.strokeStyle = color; c.lineWidth = 1; c.strokeRect(lx + 0.5, y + 0.5, w - 1, h - 1);
    c.fillStyle = "#DDEBEA"; c.textBaseline = "middle"; c.fillText(text, lx + 5, y + h / 2 + 0.5);
  }
  label(x, y, text, color, dx, left) {
    const ctx = this.ctx; ctx.font = "500 12px Inter, system-ui, sans-serif";
    const w = ctx.measureText(text).width + 14, h = 22, ox = dx === undefined ? 12 : dx; let lx = left ? x - ox - w : x + ox; const ly = y - h / 2;
    if (lx + w > this.W - 8) lx = x - ox - w; if (lx < 8) lx = x + ox;
    ctx.fillStyle = "rgba(2,4,10,0.86)"; ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(lx, ly, w, h, 6); else ctx.rect(lx, ly, w, h); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#E6EDF3"; ctx.textBaseline = "middle"; ctx.fillText(text, lx + 7, ly + h / 2 + 0.5);
  }
  laneDim(l) { const f = this.focus; if (!f) return false; if (f.delayedOnly && !l.delayed) return true; if (f.plants.size && !f.plants.has(l.p) && !f.suppliers.has(l.s)) return true; return false; }
  draw(t) {
    const ctx = this.ctx, W = this.W, H = this.H, cam = this.cam, flat = this.mode === "2d", L = this.layers, f = this.focus, d = this.data;
    this.P = { R: Math.min(W, H) * 0.42 * cam.zoom, cx: W / 2, cy: H / 2, l0: cam.lon, sp: Math.sin(cam.lat * RAD), cp: Math.cos(cam.lat * RAD), flat, S: this.scale2d(), m0: mercY(cam.lat) };
    ctx.clearRect(0, 0, W, H);
    if (flat) this.drawMapBase(); else this.drawGlobeBase(t);
    if (!d) { if (!flat) ctx.restore(); return; }
    const labels = [];
    if (L.cyclone) for (const st of this.storms) {
      const pts = st.pts, pool = [];
      for (const p of pts) for (const q of circle([p[0], p[1]], p[2] / 111.2, 10)) { const v = this.pr(q); if (v[2]) pool.push([v[0], v[1]]); }
      const hl = hull(pool);
      if (hl) { ctx.beginPath(); hl.forEach((q, k) => (k ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]))); ctx.closePath(); ctx.fillStyle = "rgba(240,166,60,0.14)"; ctx.fill(); ctx.setLineDash([5, 5]); ctx.strokeStyle = "rgba(240,166,60,0.55)"; ctx.lineWidth = 1; ctx.stroke(); ctx.setLineDash([]); }
      ctx.setLineDash([2, 6]); ctx.lineCap = "round"; ctx.beginPath(); this.line(st.line); ctx.strokeStyle = "rgba(240,166,60,0.8)"; ctx.lineWidth = 1.6; ctx.stroke(); ctx.setLineDash([]);
      if (pts.length < 2) continue;
      const h = this.hourF; let i = 0; while (i < pts.length - 2 && pts[i + 1][4] <= h) i++;
      const fr = Math.max(0, Math.min(1, (h - pts[i][4]) / Math.max(1, pts[i + 1][4] - pts[i][4])));
      const pos = slerp([pts[i][0], pts[i][1]], [pts[i + 1][0], pts[i + 1][1]])(fr), rad = pts[i][2] + (pts[i + 1][2] - pts[i][2]) * fr;
      ctx.beginPath(); this.line(densify(pts.slice(0, i + 1).map((p) => [p[0], p[1]]).concat([pos]), 1)); ctx.strokeStyle = "#F0A63C"; ctx.lineWidth = 2.2; ctx.stroke();
      ctx.beginPath(); this.ring(circle(pos, rad / 111.2, 8)); ctx.fillStyle = "rgba(240,166,60,0.12)"; ctx.fill(); ctx.strokeStyle = "rgba(240,166,60,0.9)"; ctx.lineWidth = 1.2; ctx.stroke();
      const v = this.pr(pos);
      if (v[2]) { const s = Math.min(24, 9 + 3 * cam.zoom); this.spiral(v[0], v[1], Math.max(14, s * 1.15), t); labels.push([v[0], v[1], `${st.name.toUpperCase()} · CAT ${Math.round(pts[i][3])} · T+${Math.round(h)} h`, "#F0A63C", false, s + 8]); }
    }
    if (L.quake) for (const q of d.quakes) {
      const c = [q.lon, q.lat], rd = q.radius / 111.2;
      ctx.setLineDash([4, 4]); ctx.beginPath(); this.line(circle(c, rd, 6)); ctx.strokeStyle = "rgba(255,95,95,0.8)"; ctx.lineWidth = 1.4; ctx.stroke(); ctx.setLineDash([]);
      ctx.beginPath(); this.ring(circle(c, rd, 6)); ctx.fillStyle = "rgba(255,80,80,0.12)"; ctx.fill();
      for (let k = 0; k < 3; k++) { const ph = ((t / 2600) + k / 3) % 1; ctx.beginPath(); this.line(circle(c, Math.max(0.05, rd * ph), 8)); ctx.strokeStyle = `rgba(255,110,110,${(1 - ph) * 0.8})`; ctx.lineWidth = 1.6; ctx.stroke(); }
      const v = this.pr(c); if (v[2]) { ctx.fillStyle = "#FF6B6B"; ctx.beginPath(); ctx.arc(v[0], v[1], 3.5, 0, Math.PI * 2); ctx.fill(); if (flat) labels.push([v[0], v[1], q.name, "#FF6B6B", false]); }
    }
    if (L.congestion) for (const cg of d.congestion) {
      for (let k = 0; k < 2; k++) { const ph = ((t / 2200) + k / 2) % 1; ctx.beginPath(); this.line(circle([cg.lon, cg.lat], 0.08 + 0.55 * ph, 10)); ctx.strokeStyle = `rgba(240,166,60,${(1 - ph) * 0.7})`; ctx.lineWidth = 1.4; ctx.stroke(); }
      const n = Math.min(14, Math.max(4, Math.round(cg.hours / 3.5)));
      for (let k = 0; k < n; k++) {
        const a = t / 40000 + k * 0.52, rr = 0.3 + (k % 4) * 0.16, v = this.pr([cg.lon + 0.95 + Math.cos(a) * rr, cg.lat + Math.sin(a) * rr * 0.8]); if (!v[2]) continue;
        if (flat) { this.ship(v[0], v[1], 0.55, t, k); continue; }
        ctx.save(); ctx.translate(v[0], v[1]); ctx.rotate(a + 1.57); ctx.fillStyle = "#E6EDF3"; ctx.beginPath(); ctx.moveTo(0, -5); ctx.lineTo(2.6, 3); ctx.lineTo(-2.6, 3); ctx.closePath(); ctx.fill(); ctx.restore();
      }
    }
    if (L.lanes) {
      for (const l of this.lanes) {
        const dim = this.laneDim(l);
        ctx.strokeStyle = dim ? "rgba(79,227,255,0.05)" : l.delayed ? "rgba(240,166,60,0.8)" : flat ? "rgba(63,214,181,0.45)" : "rgba(79,227,255,0.16)";
        ctx.lineWidth = dim ? 0.7 : l.delayed ? 1.5 : 0.8; if (flat) ctx.setLineDash(l.delayed ? [5, 4] : [3, 5]);
        ctx.beginPath(); this.line(l.dense); ctx.stroke(); ctx.setLineDash([]);
      }
      if (!flat) for (const l of this.lanes) {
        if (this.laneDim(l) || l.delayed) continue;
        const v = this.pr(pointAt(l, ((t / (l.mode === "sea" ? 54000 : 27000)) + l.off) % 1)); if (!v[2]) continue;
        ctx.fillStyle = "#9AF0FF"; ctx.beginPath(); ctx.arc(v[0], v[1], 1.7, 0, Math.PI * 2); ctx.fill();
      }
      if (f && f.alts) {
        const alts = this.alts.filter((a) => !f.plants.size || f.plants.has(a.p) || f.suppliers.has(a.s));
        ctx.setLineDash([7, 6]); ctx.lineDashOffset = -t / 40; ctx.strokeStyle = "#5EE6A8"; ctx.lineWidth = 2;
        for (const a of alts) { ctx.beginPath(); this.line(a.dense); ctx.stroke(); }
        ctx.setLineDash([]); ctx.lineDashOffset = 0;
        for (const a of alts) { const v = this.pr(a.f(((t / 15000) + a.off) % 1)); if (v[2]) { ctx.fillStyle = "#5EE6A8"; ctx.beginPath(); ctx.arc(v[0], v[1], 3, 0, Math.PI * 2); ctx.fill(); } }
      }
    }
    if (!flat) ctx.restore();
    if (L.lanes || L.air) {
      const z = cam.zoom, k = flat ? Math.max(0.85, Math.min(1.35, 0.85 + (z - 2.7) * 0.08)) : 0.75, tags = [];
      for (const m of this.movers) {
        const l = m.lane; if (m.kind === "plane" ? !L.air : !L.lanes) continue; if (this.laneDim(l)) continue;
        if (m.kind === "plane") { ctx.setLineDash([2, 4]); ctx.strokeStyle = "rgba(156,201,240,0.45)"; ctx.lineWidth = 1; ctx.beginPath(); this.line(m.dense); ctx.stroke(); ctx.setLineDash([]); }
        const speed = l.delayed && m.kind !== "plane" ? 0.45 : 1, fr = ((t / (m.period / speed)) + m.off) % 1;
        const a = this.pr(pointAt(m, fr)), b = this.pr(pointAt(m, Math.min(0.999, fr + 0.003)));
        if (!a[2] || a[0] < -30 || a[0] > W + 30 || a[1] < -30 || a[1] > H + 30) continue;
        const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
        if (m.kind === "truck") this.truck(a[0], a[1], k, Math.cos(ang) < 0); else if (m.kind === "ship") this.ship(a[0], a[1], k, t, m.off); else this.plane(a[0], a[1], k, ang);
        if ((l.delayed && (flat || z >= 2.2)) || (flat && z >= 3.6)) tags.push([a[0], a[1] + 12 * k, m.id + (l.delayed && m.kind !== "plane" ? ` +${l.delay}d` : ""), m.kind === "plane" ? "#9CC9F0" : l.delayed ? "#F0A63C" : "#3FD6B5"]);
      }
      for (const g of tags) this.tag(g[0], g[1], g[2], g[3]);
    }
    if (L.nodes) {
      const hp = f ? f.plants : new Set(), hs = f ? f.suppliers : new Set(), ho = f ? f.ports : new Set(), lab = f ? f.labels : {};
      for (const p of d.ports) {
        const v = this.pr([p.lon, p.lat]); if (!v[2]) continue; const s = ho.has(p.id) ? 6 : 3.8;
        ctx.fillStyle = p.exposed ? "#F0A63C" : "#6E8499"; ctx.beginPath(); ctx.moveTo(v[0], v[1] - s); ctx.lineTo(v[0] + s, v[1]); ctx.lineTo(v[0], v[1] + s); ctx.lineTo(v[0] - s, v[1]); ctx.closePath(); ctx.fill();
        if (lab[p.id]) labels.push([v[0], v[1], lab[p.id], "#F0A63C", true]);
      }
      for (const s of d.suppliers) {
        const v = this.pr([s.lon, s.lat]); if (!v[2]) continue; const hl = hs.has(s.id);
        if (hl) { ctx.beginPath(); ctx.arc(v[0], v[1], 7 + 3 * Math.sin(t / 300), 0, Math.PI * 2); ctx.strokeStyle = s.exposed ? "rgba(240,166,60,0.7)" : "rgba(94,230,168,0.8)"; ctx.lineWidth = 1.5; ctx.stroke(); }
        ctx.fillStyle = s.exposed ? "#F0A63C" : hl ? "#5EE6A8" : "#4FE3FF"; ctx.beginPath(); ctx.arc(v[0], v[1], hl ? 4.2 : 3, 0, Math.PI * 2); ctx.fill();
        if (lab[s.id]) labels.push([v[0], v[1], lab[s.id], s.exposed ? "#F0A63C" : "#5EE6A8", false]);
      }
      for (const p of d.plants) {
        const v = this.pr([p.lon, p.lat]); if (!v[2]) continue; const col = RISK_COLOR[p.risk] || "#4FE3FF", hl = hp.has(p.id);
        if (hl || p.risk === "High") { const ph = (t / 1600 + p.lat) % 1; ctx.beginPath(); ctx.arc(v[0], v[1], 6 + 14 * ph, 0, Math.PI * 2); ctx.strokeStyle = col; ctx.globalAlpha = (1 - ph) * 0.8; ctx.lineWidth = 1.5; ctx.stroke(); ctx.globalAlpha = 1; }
        const s = hl ? 9 : 7; ctx.fillStyle = col; ctx.fillRect(v[0] - s / 2, v[1] - s / 2, s, s); ctx.strokeStyle = "#02040A"; ctx.lineWidth = 1.5; ctx.strokeRect(v[0] - s / 2, v[1] - s / 2, s, s);
        if (lab[p.id]) labels.push([v[0], v[1], lab[p.id], col, false]);
        else if (!f && !flat && cam.zoom > 1.7) labels.push([v[0], v[1], p.name, "#2A3A4A", false]);
      }
    }
    for (const l of labels) this.label(l[0], l[1], l[2], l[3], l[5], l[4]);
  }
}
window.GeoMap = GeoMap;
})();
