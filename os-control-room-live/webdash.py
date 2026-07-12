"""
webdash.py - the WALL DISPLAY: a read-only browser dashboard for a projector.

It serves one self-contained HTML page (no CDNs, no frameworks) plus a JSON
snapshot endpoint. The page polls /data.json once a second and draws live
CPU meters, a rolling %CPU line chart, RSS bars and the kernel-news feed.

Everything shown comes from the same source as the terminal: /proc, read at
request time. The terminal stays mission control; this is just a window.
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ui
import procinfo as pi


def start(cr, port=8000):
    """Start the wall-display server for a ControlRoom; returns the server."""
    meter = pi.CpuMeter()               # its own meter -> its own %CPU sampling

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):      # keep the cockpit's terminal clean
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            if self.path.startswith("/data.json"):
                self._send(200, "application/json", json.dumps(snapshot()))
            elif self.path in ("/", "/index.html"):
                self._send(200, "text/html", PAGE)
            else:
                self._send(404, "text/plain", "not found")

    def snapshot():
        workers = []
        for pid, w in sorted(list(cr.workers.items())):
            s = pi.snapshot(pid, meter)
            if not s:
                continue
            workers.append({
                "pid": pid,
                "name": w.display,
                "state": s["state"],
                "cpu": s["cpu"],
                "rss_mb": round(s["rss_kb"] / 1024, 1),
                "nice": s["nice"],
                "core": s["psr"],
                "wchan": s["wchan"] or "",
            })
        _, _, cyc = cr._find_deadlock()
        return {
            "cores": os.cpu_count() or 1,
            "deadlock": cyc,
            "workers": workers,
            "events": [[ts, ui._strip(msg)] for ts, msg in cr.events],
        }

    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# The page: dark mission-control theme. Colors are the validated dark-mode
# palette steps (categorical slots 1-8 + status) on surface #1a1a19.
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OS Control Room — wall display</title>
<style>
  :root {
    --page: #0d0d0d; --surface: #1a1a19;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
    --good: #0ca30c; --critical: #d03b3b;
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    background: var(--page); color: var(--ink-2);
    font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
    padding: 18px; min-height: 100vh;
  }
  h1 { font-size: 17px; color: var(--ink); font-weight: 650; letter-spacing: .2px; }
  h1 small { color: var(--muted); font-weight: 400; margin-left: 10px; font-size: 12px; }
  .sub { color: var(--muted); font-size: 12px; margin-top: 2px; }
  #alarm {
    display: none; margin: 14px 0 0; padding: 10px 14px; border-radius: 8px;
    background: var(--critical); color: #fff; font-weight: 650;
    animation: throb 1.1s ease-in-out infinite;
  }
  #alarm.on { display: block; }
  @keyframes throb { 50% { opacity: .55; } }
  .grid { display: grid; grid-template-columns: minmax(340px, 5fr) 7fr; gap: 14px; margin-top: 14px; }
  .card {
    background: var(--surface); border: 1px solid var(--ring);
    border-radius: 10px; padding: 14px 16px; min-width: 0;
  }
  .card h2 {
    font-size: 11px; font-weight: 650; letter-spacing: .8px;
    text-transform: uppercase; color: var(--muted); margin-bottom: 10px;
  }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 5px 8px 5px 0; font-size: 13px; white-space: nowrap; }
  th { color: var(--muted); font-weight: 500; font-size: 11px; border-bottom: 1px solid var(--grid); }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  td.name { color: var(--ink); max-width: 150px; overflow: hidden; text-overflow: ellipsis; }
  .chip { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 7px; }
  .meter { width: 110px; height: 8px; background: var(--grid); border-radius: 4px; overflow: hidden; }
  .meter i { display: block; height: 100%; border-radius: 4px; transition: width .6s ease; }
  .state { font-size: 11px; padding: 1px 7px; border-radius: 9px; border: 1px solid var(--grid); }
  .state.Z { color: #d55181; border-color: #d55181; }
  .state.T { color: #c98500; border-color: #c98500; }
  .state.R { color: var(--good); border-color: var(--good); }
  canvas { width: 100%; display: block; }
  #feed { list-style: none; font-size: 13px; }
  #feed li { padding: 4px 0; border-bottom: 1px solid var(--grid); }
  #feed time { color: var(--muted); font-variant-numeric: tabular-nums; margin-right: 10px; font-size: 12px; }
  #tip {
    position: fixed; display: none; pointer-events: none; z-index: 9;
    background: var(--page); border: 1px solid var(--ring); border-radius: 7px;
    padding: 7px 10px; font-size: 12px; color: var(--ink-2);
  }
  #tip b { color: var(--ink); font-variant-numeric: tabular-nums; }
  .empty { color: var(--muted); padding: 18px 0; font-size: 13px; }
</style>
</head>
<body>
  <h1>OS CONTROL ROOM <small>wall display · live from /proc · read-only</small></h1>
  <div class="sub" id="meta">connecting…</div>
  <div id="alarm">⚠ DEADLOCK — a real wait-for cycle is stuck in the kernel. Resolve it from the cockpit: kill a victim.</div>

  <div class="grid">
    <div>
      <div class="card">
        <h2>Managed processes</h2>
        <div id="procs"><div class="empty">no managed workers yet — spawn some from the terminal</div></div>
      </div>
      <div class="card" style="margin-top:14px">
        <h2>Kernel news</h2>
        <ul id="feed"><li class="empty">no events yet</li></ul>
      </div>
    </div>
    <div>
      <div class="card">
        <h2>%CPU — rolling 90 s</h2>
        <canvas id="cpu" height="260"></canvas>
      </div>
      <div class="card" style="margin-top:14px">
        <h2>Resident memory (RSS, MB)</h2>
        <canvas id="mem" height="150"></canvas>
      </div>
    </div>
  </div>
  <div id="tip"></div>

<script>
"use strict";
/* validated dark-mode categorical slots, assigned to pids in fixed order */
const SLOTS = ["#3987e5","#199e70","#c98500","#008300","#9085e9","#e66767","#d55181","#d95926"];
const OTHER = "#898781";
const series = new Map();   /* pid -> {name, color, hist: [{t, cpu}]} */
let nextSlot = 0, lastData = null;

function colorFor(pid, name) {
  if (!series.has(pid)) {
    series.set(pid, { name, color: nextSlot < SLOTS.length ? SLOTS[nextSlot++] : OTHER, hist: [] });
  }
  const s = series.get(pid); s.name = name; return s;
}

async function tick() {
  let d;
  try { d = await (await fetch("data.json")).json(); }
  catch (e) { document.getElementById("meta").textContent = "cockpit offline — waiting…"; return; }
  lastData = d;
  const now = Date.now() / 1000;
  document.getElementById("meta").textContent =
    `host cores: ${d.cores} · managed processes: ${d.workers.length} · updated ${new Date().toLocaleTimeString()}`;
  document.getElementById("alarm").classList.toggle("on", d.deadlock);

  const live = new Set();
  for (const w of d.workers) {
    const s = colorFor(w.pid, w.name);
    live.add(w.pid);
    s.hist.push({ t: now, cpu: w.cpu });
    while (s.hist.length && now - s.hist[0].t > 92) s.hist.shift();
  }
  for (const [pid, s] of series) {          /* age out processes gone > 92 s */
    if (!live.has(pid) && (!s.hist.length || now - s.hist[s.hist.length-1].t > 92)) series.delete(pid);
  }
  renderTable(d);
  drawCpu(now);
  drawMem(d);
  renderFeed(d);
}

function renderTable(d) {
  const el = document.getElementById("procs");
  if (!d.workers.length) {
    el.innerHTML = '<div class="empty">no managed workers yet — spawn some from the terminal</div>'; return;
  }
  let h = '<table><tr><th></th><th>worker</th><th class="num">pid</th><th>state</th><th>%cpu</th><th class="num">rss</th><th class="num">ni</th><th class="num">core</th></tr>';
  for (const w of d.workers) {
    const s = colorFor(w.pid, w.name);
    const cpu = w.cpu == null ? 0 : w.cpu;
    const cpuTxt = w.cpu == null ? "—" : cpu.toFixed(0) + "%";
    h += `<tr>
      <td><span class="chip" style="background:${s.color}"></span></td>
      <td class="name" title="${w.name}">${w.name}</td>
      <td class="num">${w.pid}</td>
      <td><span class="state ${w.state}">${w.state}</span></td>
      <td><div class="meter"><i style="width:${Math.min(100,cpu)}%;background:${s.color}"></i></div>
          <span style="font-variant-numeric:tabular-nums">${cpuTxt}</span></td>
      <td class="num">${w.rss_mb.toFixed(1)}</td>
      <td class="num">${w.nice}</td>
      <td class="num">${w.core}</td></tr>`;
  }
  el.innerHTML = h + "</table>";
}

function setupCanvas(cv) {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = parseInt(cv.getAttribute("height"));
  cv.width = w * dpr; cv.height = h * dpr; cv.style.height = h + "px";
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, w, h];
}
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function drawCpu(now) {
  const cv = document.getElementById("cpu");
  const [ctx, W, H] = setupCanvas(cv);
  const L = 38, R = 86, T = 8, B = 22;
  const pw = W - L - R, ph = H - T - B, SPAN = 90;
  ctx.clearRect(0, 0, W, H);
  ctx.font = "11px system-ui, sans-serif";
  /* grid + one y-axis (0-100%) */
  for (const v of [0, 25, 50, 75, 100]) {
    const y = T + ph - (v / 100) * ph;
    ctx.strokeStyle = v === 0 ? css("--axis") : css("--grid");
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(L + pw, y); ctx.stroke();
    ctx.fillStyle = css("--muted"); ctx.textAlign = "right";
    ctx.fillText(v + "%", L - 6, y + 4);
  }
  ctx.textAlign = "center";
  for (const s of [60, 30, 0]) {
    const x = L + pw - (s / SPAN) * pw;
    ctx.fillText(s ? "-" + s + "s" : "now", x, H - 6);
  }
  /* 2px series lines + direct label at the line's right end */
  const labels = [];
  for (const [pid, s] of series) {
    if (s.hist.length < 2) continue;
    ctx.strokeStyle = s.color; ctx.lineWidth = 2;
    ctx.lineJoin = "round"; ctx.beginPath();
    let first = true, lastY = null;
    for (const p of s.hist) {
      if (p.cpu == null) continue;
      const x = L + pw - ((now - p.t) / SPAN) * pw;
      const y = T + ph - (Math.min(p.cpu, 100) / 100) * ph;
      if (x < L) continue;
      first ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      first = false; lastY = y;
    }
    ctx.stroke();
    if (lastY != null) labels.push({ y: lastY, color: s.color, text: s.name.split(" ")[0] + " " + pid });
  }
  /* collision-nudge the direct labels, text in ink (not series color) */
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++)
    if (labels[i].y - labels[i - 1].y < 13) labels[i].y = labels[i - 1].y + 13;
  ctx.textAlign = "left";
  for (const lb of labels) {
    ctx.fillStyle = lb.color; ctx.fillRect(L + pw + 6, lb.y - 4, 8, 3);
    ctx.fillStyle = css("--ink-2"); ctx.fillText(lb.text, L + pw + 18, lb.y);
  }
  cv._geom = { L, T, pw, ph, SPAN, now };
}

function drawMem(d) {
  const cv = document.getElementById("mem");
  const [ctx, W, H] = setupCanvas(cv);
  ctx.clearRect(0, 0, W, H);
  ctx.font = "11px system-ui, sans-serif";
  const rows = d.workers.slice(0, 6);
  if (!rows.length) {
    ctx.fillStyle = css("--muted"); ctx.fillText("nothing resident yet", 8, 20); return;
  }
  const max = Math.max(...rows.map(w => w.rss_mb), 1);
  const bh = 12, gap = Math.max((H - 16 - rows.length * bh) / rows.length, 6);
  const L = 130, R = 64, pw = W - L - R;
  rows.forEach((w, i) => {
    const s = colorFor(w.pid, w.name);
    const y = 10 + i * (bh + gap);
    ctx.fillStyle = css("--ink-2"); ctx.textAlign = "right";
    ctx.fillText(w.name.split(" ")[0] + " " + w.pid, L - 8, y + bh - 2);
    ctx.fillStyle = css("--grid");
    ctx.beginPath(); ctx.roundRect(L, y, pw, bh, 4); ctx.fill();
    ctx.fillStyle = s.color;
    ctx.beginPath(); ctx.roundRect(L, y, Math.max(pw * w.rss_mb / max, 2), bh, 4); ctx.fill();
    ctx.fillStyle = css("--ink"); ctx.textAlign = "left";
    ctx.fillText(w.rss_mb.toFixed(1) + " MB", L + pw + 8, y + bh - 2);
  });
}

function renderFeed(d) {
  const el = document.getElementById("feed");
  if (!d.events.length) { el.innerHTML = '<li class="empty">no events yet</li>'; return; }
  el.innerHTML = d.events.slice().reverse()
    .map(([t, m]) => `<li><time>${t}</time>${m.replace(/&/g,"&amp;").replace(/</g,"&lt;")}</li>`).join("");
}

/* crosshair tooltip on the line chart */
const tip = document.getElementById("tip");
document.getElementById("cpu").addEventListener("mousemove", ev => {
  const cv = ev.currentTarget, g = cv._geom;
  if (!g || !lastData) return;
  const r = cv.getBoundingClientRect();
  const x = ev.clientX - r.left;
  if (x < g.L || x > g.L + g.pw) { tip.style.display = "none"; return; }
  const at = g.now - ((g.L + g.pw - x) / g.pw) * g.SPAN;
  let rows = "";
  for (const [pid, s] of series) {
    let best = null;
    for (const p of s.hist)
      if (p.cpu != null && (!best || Math.abs(p.t - at) < Math.abs(best.t - at))) best = p;
    if (best && Math.abs(best.t - at) < 2.5)
      rows += `<div><span class="chip" style="background:${s.color}"></span>${s.name.split(" ")[0]} ${pid} — <b>${best.cpu.toFixed(0)}%</b></div>`;
  }
  if (!rows) { tip.style.display = "none"; return; }
  tip.innerHTML = rows;
  tip.style.display = "block";
  tip.style.left = Math.min(ev.clientX + 14, innerWidth - 190) + "px";
  tip.style.top = (ev.clientY + 14) + "px";
});
document.getElementById("cpu").addEventListener("mouseleave", () => tip.style.display = "none");

tick();
setInterval(tick, 1000);
</script>
</body>
</html>
"""
