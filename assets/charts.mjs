// Small SVG charts, drawn by hand so the site needs no outside library (it works offline).
// Marks follow the dataviz rules: 2px lines, 8px+ markers with a surface ring, thin bars with a
// rounded data end, hairline grid, text in ink colours, a tooltip on hover/focus, and a table view.

import { el } from "./ui.mjs";

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}, ...kids) => {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid != null) node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return node;
};

export const SERIES_COLORS = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`);

// "Nice" axis ticks: round numbers covering [lo, hi].
export function niceTicks(lo, hi, count = 5) {
  if (hi === lo) { hi = lo + 1; }
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const start = Math.floor(lo / step) * step;
  const n = Math.ceil((hi - start) / step - 1e-9); // the last tick must reach the highest value
  const ticks = Array.from({ length: n + 1 }, (_, i) => Number((start + i * step).toPrecision(12)));
  return ticks;
}

function tooltipFor(host) {
  const tip = el("div", { class: "tooltip", role: "status" });
  tip.hidden = true;
  host.append(tip);
  return {
    show(x, y, head, rows) {
      tip.replaceChildren(
        head ? el("div", { class: "t-head" }, head) : null,
        rows.map((r) => el("div", { class: "t-row" },
          r.color ? el("span", { class: "t-key", style: `background:${r.color}` }) : null,
          el("span", { class: "t-name" }, r.name),
          el("span", { class: "t-value" }, r.value))));
      tip.hidden = false;
      const w = tip.offsetWidth, h = tip.offsetHeight, max = host.clientWidth;
      tip.style.left = `${Math.max(0, Math.min(x + 14, max - w))}px`;
      tip.style.top = `${Math.max(0, y - h - 10)}px`;
      if (y - h - 10 < 0) tip.style.top = `${y + 16}px`;
    },
    hide() { tip.hidden = true; },
  };
}

// Redraw when the width changes (phone turned, window resized).
function redrawOnResize(host, draw) {
  let width = 0;
  const run = () => { if (host.clientWidth && host.clientWidth !== width) { width = host.clientWidth; draw(width); } };
  new ResizeObserver(run).observe(host);
  run();
}

function legend(items) {
  return el("div", { class: "legend" }, items.map((s) => el("span", {}, el("i", { style: `background:${s.color}` }), s.label)));
}

// ----- line chart: one line per series, one point per day -----
// options: days[], series[{label,color,values[]}], format(v), axisFormat(v), dayLabel(day), height
export function lineChart(host, { days, series, format, axisFormat = format, dayLabel = (d) => d, height = 320, name = "Line chart" }) {
  host.replaceChildren();
  host.classList.add("chart");
  const body = el("div");
  host.append(body);
  const tip = tooltipFor(host);
  if (!series.length) { body.replaceWith(el("div", { class: "empty" }, "Pick at least one club to draw the chart.")); return; }

  redrawOnResize(body, (W) => {
    const direct = series.length <= 4;
    const m = { top: 12, right: direct ? 120 : 16, bottom: 30, left: 58 };
    const all = series.flatMap((s) => s.values).filter((v) => v != null);
    let lo = Math.min(...all), hi = Math.max(...all);
    if (lo >= 0 && lo < hi * 0.5) lo = 0;
    const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.1 || 0.01;
    const ticks = niceTicks(lo >= 0 && lo === 0 ? 0 : lo - pad, hi + pad);
    const yLo = ticks[0], yHi = ticks.at(-1);
    const x = (i) => (days.length === 1 ? m.left + (W - m.left - m.right) / 2 : m.left + (i * (W - m.left - m.right)) / (days.length - 1));
    const y = (v) => height - m.bottom - ((v - yLo) / (yHi - yLo)) * (height - m.top - m.bottom);

    const root = svg("svg", { viewBox: `0 0 ${W} ${height}`, role: "img", tabindex: 0, "aria-label": `${name}. Use the left and right arrow keys to move between days.` });
    root.append(svg("g", { class: "grid" }, ticks.map((t) => svg("line", { x1: m.left, x2: W - m.right, y1: y(t), y2: y(t) }))));
    root.append(svg("g", { class: "axis" }, ticks.map((t) => svg("text", { x: m.left - 8, y: y(t) + 4, "text-anchor": "end" }, axisFormat(t)))));
    const every = Math.ceil(days.length / Math.max(2, Math.floor((W - m.left - m.right) / 70)));
    root.append(svg("g", { class: "axis" }, days.map((d, i) => (i % every === 0
      ? svg("text", { x: x(i), y: height - 8, "text-anchor": "middle" }, dayLabel(d)) : null))));

    for (const s of series) {
      let d = "", pen = false;
      s.values.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? "L" : "M"}${x(i)},${y(v)}`; pen = true; });
      root.append(svg("path", { class: "line", d, stroke: s.color }));
      const last = s.values.map((v, i) => [v, i]).filter(([v]) => v != null).at(-1);
      if (last) root.append(svg("circle", { cx: x(last[1]), cy: y(last[0]), r: 4, fill: s.color, stroke: "var(--surface)", "stroke-width": 2 }));
    }

    // Direct labels at the line ends (4 series or fewer), skipped if they would collide.
    if (direct) {
      const ends = series.map((s) => { const l = s.values.map((v, i) => [v, i]).filter(([v]) => v != null).at(-1); return l ? { s, y: y(l[0]), x: x(l[1]) } : null; }).filter(Boolean).sort((a, b) => a.y - b.y);
      if (ends.every((e, i) => i === 0 || e.y - ends[i - 1].y >= 14)) {
        for (const e of ends) root.append(svg("text", { class: "label", x: e.x + 10, y: e.y + 4 }, e.s.label.length > 18 ? `${e.s.label.slice(0, 17)}…` : e.s.label));
      }
    }

    // Hover / keyboard layer: a hairline snaps to the nearest day, markers show that day's values.
    const cross = svg("g", { visibility: "hidden" }, svg("line", { class: "crosshair", y1: m.top, y2: height - m.bottom }));
    const dots = series.map((s) => svg("circle", { r: 4, fill: s.color, stroke: "var(--surface)", "stroke-width": 2, visibility: "hidden" }));
    cross.append(...dots);
    root.append(cross);
    const focusDay = (i, px, py) => {
      cross.setAttribute("visibility", "visible");
      cross.firstChild.setAttribute("x1", x(i)); cross.firstChild.setAttribute("x2", x(i));
      series.forEach((s, k) => {
        const v = s.values[i];
        dots[k].setAttribute("visibility", v == null ? "hidden" : "visible");
        if (v != null) { dots[k].setAttribute("cx", x(i)); dots[k].setAttribute("cy", y(v)); }
      });
      tip.show(px ?? x(i), py ?? m.top + 20, dayLabel(days[i]), series.map((s) => ({ color: s.color, name: s.label, value: s.values[i] == null ? "–" : format(s.values[i]) })));
    };
    const overlay = svg("rect", { x: m.left, y: m.top, width: W - m.left - m.right, height: height - m.top - m.bottom, fill: "transparent" });
    const nearest = (event) => {
      const box = root.getBoundingClientRect();
      const px = ((event.clientX - box.left) / box.width) * W;
      return days.length === 1 ? 0 : Math.max(0, Math.min(days.length - 1, Math.round(((px - m.left) / (W - m.left - m.right)) * (days.length - 1))));
    };
    overlay.addEventListener("pointermove", (e) => { const i = nearest(e); const box = body.getBoundingClientRect(); focusDay(i, ((x(i) / W) * box.width), e.clientY - box.top); });
    overlay.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); tip.hide(); });
    let index = days.length - 1;
    root.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") index = Math.max(0, index - 1);
      else if (e.key === "ArrowRight") index = Math.min(days.length - 1, index + 1);
      else return;
      e.preventDefault();
      focusDay(index, (x(index) / W) * body.clientWidth, 30);
    });
    root.addEventListener("blur", () => { cross.setAttribute("visibility", "hidden"); tip.hide(); });
    root.append(overlay);
    body.replaceChildren(root);
  });
  if (series.length > 1) host.append(legend(series)); // one line needs no legend: the heading names it
}

// ----- horizontal bars: one bar per row. rows: [{label, value, color, detail}] -----
// signed=true draws bars on both sides of a zero line.
export function barChart(host, { rows, format, signed = false, name = "Bar chart", legendItems = null }) {
  host.replaceChildren();
  host.classList.add("chart");
  const body = el("div");
  host.append(body);
  const tip = tooltipFor(host);
  if (!rows.length) { host.replaceChildren(el("div", { class: "empty" }, "Nothing to show yet.")); return; }

  redrawOnResize(body, (W) => {
    const rowH = 30, barH = 16, labelW = Math.min(180, Math.max(90, Math.max(...rows.map((r) => r.label.length)) * 7)), right = 76;
    const H = rows.length * rowH + 8;
    const maxAbs = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
    const plotL = labelW + 8 + (signed ? 64 : 0), plotR = W - right; // room for a value label left of a negative bar
    const negMax = signed ? Math.max(0, ...rows.map((r) => -r.value)) : 0;
    const posMax = Math.max(0, ...rows.map((r) => r.value));
    const span = (posMax + negMax) || maxAbs;
    const zero = plotL + ((plotR - plotL) * negMax) / span;
    const scale = (plotR - plotL) / span;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": name });
    rows.forEach((r, i) => {
      const cy = i * rowH + rowH / 2 + 4, top = cy - barH / 2;
      root.append(svg("text", { class: "label", x: labelW, y: cy + 4, "text-anchor": "end" }, r.label.length > 24 ? `${r.label.slice(0, 23)}…` : r.label));
      const w = Math.max(Math.abs(r.value) * scale, 0);
      const dir = r.value < 0 ? -1 : 1;
      const rad = Math.min(4, w);
      const x0 = zero;
      const path = w === 0 ? "" : dir > 0
        ? `M${x0},${top}H${x0 + w - rad}A${rad},${rad} 0 0 1 ${x0 + w},${top + rad}V${top + barH - rad}A${rad},${rad} 0 0 1 ${x0 + w - rad},${top + barH}H${x0}Z`
        : `M${x0},${top}H${x0 - w + rad}A${rad},${rad} 0 0 0 ${x0 - w},${top + rad}V${top + barH - rad}A${rad},${rad} 0 0 0 ${x0 - w + rad},${top + barH}H${x0}Z`;
      const mark = svg("path", { class: "mark", d: path || `M${x0},${top}h1v${barH}h-1z`, fill: r.color ?? SERIES_COLORS[0], tabindex: 0, role: "img", "aria-label": `${r.label}: ${format(r.value)}` });
      const show = () => { const b = body.getBoundingClientRect(), m = mark.getBoundingClientRect(); tip.show(m.right - b.left, m.top - b.top + 8, null, [{ name: r.label, value: format(r.value) }, ...(r.detail ? [{ name: r.detail, value: "" }] : [])]); };
      mark.addEventListener("pointerenter", show); mark.addEventListener("focus", show);
      mark.addEventListener("pointerleave", () => tip.hide()); mark.addEventListener("blur", () => tip.hide());
      root.append(mark);
      const tipX = dir > 0 ? x0 + w + 6 : x0 - w - 6;
      root.append(svg("text", { class: "value-label", x: tipX, y: cy + 4, "text-anchor": dir > 0 ? "start" : "end" }, format(r.value)));
    });
    if (signed) root.append(svg("line", { class: "zero", x1: zero, x2: zero, y1: 0, y2: H }));
    body.replaceChildren(root);
  });
  if (legendItems) host.append(legend(legendItems));
}

// ----- columns: one column per label along the bottom (used for "per day" charts) -----
export function columnChart(host, { rows, format, name = "Column chart", legendItems = null, height = 260 }) {
  host.replaceChildren();
  host.classList.add("chart");
  const body = el("div");
  host.append(body);
  const tip = tooltipFor(host);
  if (!rows.length) { host.replaceChildren(el("div", { class: "empty" }, "Nothing to show yet.")); return; }

  redrawOnResize(body, (W) => {
    const m = { top: 16, right: 12, bottom: 30, left: 58 };
    const max = Math.max(...rows.map((r) => r.value), 1e-9);
    const ticks = niceTicks(0, max, 4);
    const yHi = ticks.at(-1);
    const y = (v) => height - m.bottom - (v / yHi) * (height - m.top - m.bottom);
    const slot = (W - m.left - m.right) / rows.length;
    const barW = Math.min(24, slot - 2);
    const root = svg("svg", { viewBox: `0 0 ${W} ${height}`, role: "img", "aria-label": name });
    root.append(svg("g", { class: "grid" }, ticks.map((t) => svg("line", { x1: m.left, x2: W - m.right, y1: y(t), y2: y(t) }))));
    root.append(svg("g", { class: "axis" }, ticks.map((t) => svg("text", { x: m.left - 8, y: y(t) + 4, "text-anchor": "end" }, format(t)))));
    const every = Math.ceil(rows.length / Math.max(2, Math.floor((W - m.left - m.right) / 60)));
    rows.forEach((r, i) => {
      const cx = m.left + slot * i + slot / 2, h = Math.max(1, height - m.bottom - y(r.value)), top = height - m.bottom - h, rad = Math.min(4, barW / 2, h);
      const path = `M${cx - barW / 2},${height - m.bottom}V${top + rad}A${rad},${rad} 0 0 1 ${cx - barW / 2 + rad},${top}H${cx + barW / 2 - rad}A${rad},${rad} 0 0 1 ${cx + barW / 2},${top + rad}V${height - m.bottom}Z`;
      const mark = svg("path", { class: "mark", d: path, fill: r.color ?? SERIES_COLORS[0], tabindex: 0, role: "img", "aria-label": `${r.label}: ${format(r.value)}` });
      const show = () => { const b = body.getBoundingClientRect(), mb = mark.getBoundingClientRect(); tip.show(mb.left - b.left + mb.width / 2 - 80, mb.top - b.top, r.label, [{ name: r.detail ?? "", value: format(r.value) }]); };
      mark.addEventListener("pointerenter", show); mark.addEventListener("focus", show);
      mark.addEventListener("pointerleave", () => tip.hide()); mark.addEventListener("blur", () => tip.hide());
      root.append(mark);
      if (i % every === 0) root.append(svg("g", { class: "axis" }, svg("text", { x: cx, y: height - 8, "text-anchor": "middle" }, r.axis ?? r.label)));
    });
    body.replaceChildren(root);
  });
  if (legendItems) host.append(legend(legendItems));
}

// "Show the numbers": the table behind a chart, for keyboard and screen-reader users.
export function tableView(headers, rows, summary = "Show the numbers behind this chart") {
  return el("details", { class: "numbers" }, el("summary", {}, summary),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, headers.map((h, i) => el("th", { class: i > 0 ? "num" : null, scope: "col" }, h)))),
      el("tbody", {}, rows.map((r) => el("tr", {}, r.map((cell, i) => el("td", { class: i > 0 ? "num" : null }, cell))))))));
}
