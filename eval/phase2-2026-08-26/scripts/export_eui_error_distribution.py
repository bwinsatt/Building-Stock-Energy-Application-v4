"""Build C&I / MF EUI error-distribution HTML (and C&I canvas JSON).

    python testcases/export_eui_error_distribution.py
"""

from __future__ import annotations

import csv
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = Path(__file__).resolve().parents[1]

VARIANTS = ("required_only", "with_basics", "advanced")
HIST_LO, HIST_HI, HIST_W = -70.0, 130.0, 10.0
HIST_CATS = [str(int(x)) for x in range(int(HIST_LO), int(HIST_HI) + int(HIST_W), int(HIST_W))]
DENSITY_CATS = [str(x) for x in range(-70, 145, 5)]
DENSITY_GRID = [float(x) for x in range(-70, 145, 5)]
KDE_CLIP = 150.0


def f(v):
    try:
        s = str(v).strip()
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def quantiles(vals: list[float]) -> tuple[float, float]:
    if len(vals) < 2:
        return vals[0], vals[0]
    qs = st.quantiles(vals, n=4)
    return qs[0], qs[2]


def hist_counts(vals: list[float]) -> list[int]:
    n_bins = int((HIST_HI - HIST_LO) / HIST_W) + 1
    counts = [0] * n_bins
    for x in vals:
        xx = min(max(x, HIST_LO), HIST_HI + HIST_W - 0.0001)
        i = int((xx - HIST_LO) // HIST_W)
        i = min(max(i, 0), n_bins - 1)
        counts[i] += 1
    return counts


def kde_curve(vals: list[float], clip: float | None) -> tuple[list[float], int]:
    x = [v for v in vals if clip is None or abs(v) <= clip]
    if len(x) < 2:
        return [0.0] * len(DENSITY_GRID), len(x)
    n = len(x)
    std = st.stdev(x) if n > 1 else 0.0
    q1, q3 = quantiles(x)
    iqr = q3 - q1
    sigma = min(std, iqr / 1.34) if iqr > 0 and std > 0 else (std or 1.0)
    if sigma <= 0:
        sigma = 1.0
    bw = 0.9 * sigma * n ** (-0.2)
    out = []
    inv = 1.0 / (bw * math.sqrt(2 * math.pi))
    for g in DENSITY_GRID:
        s = 0.0
        for xi in x:
            z = (g - xi) / bw
            s += math.exp(-0.5 * z * z)
        dens = (s / n) * inv
        out.append(round(dens * 100.0, 3))
    return out, n


def r1(x: float | None) -> float | None:
    return None if x is None else round(x, 1)


def r2(x: float | None) -> float | None:
    return None if x is None else round(x, 2)


def fuel_stats(pcts: list[float], kbtus: list[float] | None, clip_hist_outliers: bool) -> dict:
    raw = [x for x in pcts if x is not None]
    if not raw:
        empty_hist = [0] * (int((HIST_HI - HIST_LO) / HIST_W) + 1)
        return {
            "n": 0, "min": 0, "q1": 0, "median": 0, "mean": 0, "q3": 0, "max": 0,
            "sd": 0, "iqr": 0, "abs_med": 0, "abs_mean": 0, "abs_q1": 0, "abs_q3": 0,
            "abs_iqr": 0, "abs_sd": 0, "abs_max": 0, "under": 0, "within10": 0,
            "within20": 0, "gt50": 0, "hist": empty_hist, "kde": [0.0] * len(DENSITY_GRID),
            "n_clip": 0, "kbtu_med": None, "kbtu_med_abs": None,
        }
    absv = [abs(x) for x in raw]
    q1, q3 = quantiles(raw)
    aq1, aq3 = quantiles(absv)
    hist_src = [x for x in raw if not clip_hist_outliers or abs(x) <= KDE_CLIP]
    kde, n_clip = kde_curve(raw, KDE_CLIP)
    kb = [x for x in (kbtus or []) if x is not None]
    return {
        "n": len(raw),
        "min": r1(min(raw)),
        "q1": r1(q1),
        "median": r1(st.median(raw)),
        "mean": r1(st.mean(raw)),
        "q3": r1(q3),
        "max": r1(max(raw)),
        "sd": r1(st.pstdev(raw) if len(raw) > 1 else 0.0),
        "iqr": r1(q3 - q1),
        "abs_med": r1(st.median(absv)),
        "abs_mean": r1(st.mean(absv)),
        "abs_q1": r1(aq1),
        "abs_q3": r1(aq3),
        "abs_iqr": r1(aq3 - aq1),
        "abs_sd": r1(st.pstdev(absv) if len(absv) > 1 else 0.0),
        "abs_max": r1(max(absv)),
        "under": sum(1 for x in raw if x < 0),
        "within10": sum(1 for x in absv if x <= 10),
        "within20": sum(1 for x in absv if x <= 20),
        "gt50": sum(1 for x in absv if x > 50),
        "hist": hist_counts(hist_src),
        "kde": kde,
        "n_clip": n_clip,
        "kbtu_med": r2(st.median(kb) if kb else None),
        "kbtu_med_abs": r2(st.median([abs(x) for x in kb]) if kb else None),
    }


def bundle_for(rows: list[dict], cmap: dict) -> dict:
    out = {}
    for v in VARIANTS:
        chunk = [r for r in rows if r["variant"] == v]
        site, elec, gas, share, sk, ek, gk = [], [], [], [], [], [], []
        for r in chunk:
            site.append(f(r[cmap["site_pct"]]))
            elec.append(f(r[cmap["elec_pct"]]))
            gas.append(f(r[cmap["gas_pct"]]))
            share.append(f(r[cmap["share"]]))
            pred_s, tru_s = f(r[cmap["pred_site"]]), f(r[cmap["truth_site"]])
            if pred_s is not None and tru_s is not None:
                sk.append(pred_s - tru_s)
            ek.append(f(r[cmap["elec_abs"]]))
            gk.append(f(r[cmap["gas_abs"]]))
        sh = [x for x in share if x is not None]
        out[v] = {
            "site": fuel_stats(site, sk, clip_hist_outliers=False),
            "elec": fuel_stats([x for x in elec if x is not None], ek, True),
            "gas": fuel_stats([x for x in gas if x is not None], gk, True),
            "share_med": r1(st.median(sh) if sh else 0.0),
            "share_med_abs": r1(st.median([abs(x) for x in sh]) if sh else 0.0),
        }
    return out


def load_ci():
    res = list(csv.DictReader((SNAP / "results/commercial_industrial/assessment_results.csv").open(encoding="utf-8-sig", newline="")))
    tc = list(csv.DictReader((SNAP / "freeze/commercial_industrial/testcases.csv").open(encoding="utf-8-sig", newline="")))
    bt = {(r["job"], r["variant"]): (r.get("building_type") or "").strip() or "(blank)" for r in tc}
    rows = []
    for r in res:
        if r["status"] != "ok":
            continue
        if (r.get("missing_required") or "").strip():
            continue
        if r.get("utility_data_completeness") != "whole_property_full_year":
            continue
        if r["variant"] not in VARIANTS:
            continue
        if f(r.get("site_eui_pct_error")) is None:
            continue
        rec = dict(r)
        rec["_type"] = bt.get((r["job"], r["variant"]), "(blank)")
        rows.append(rec)
    cmap = {
        "site_pct": "site_eui_pct_error", "elec_pct": "elec_eui_pct_error",
        "gas_pct": "gas_eui_pct_error", "share": "gas_share_error_pts",
        "pred_site": "pred_site_eui", "truth_site": "truth_site_eui",
        "elec_abs": "elec_eui_abs_error", "gas_abs": "gas_eui_abs_error",
    }
    return rows, cmap, "job"


def load_mf():
    res = list(csv.DictReader((SNAP / "results/multifamily/assessment_results.csv").open(encoding="utf-8-sig", newline="")))
    tc = list(csv.DictReader((SNAP / "freeze/multifamily/testcases.csv").open(encoding="utf-8-sig", newline="")))
    bt = {(r["job_number"], r["variant"]): (r.get("building_type") or "").strip() or "(blank)" for r in tc}
    rows = []
    for r in res:
        if r["status"] != "ok":
            continue
        if (r.get("missing_required") or "").strip():
            continue
        if r.get("truth_utility_data_completeness") != "whole_property_full_year":
            continue
        if r["variant"] not in VARIANTS:
            continue
        if f(r.get("site_eui_pct_error")) is None:
            continue
        rec = dict(r)
        rec["_type"] = bt.get((r["job_number"], r["variant"]), "(blank)")
        rows.append(rec)
    cmap = {
        "site_pct": "site_eui_pct_error", "elec_pct": "elec_eui_pct_error",
        "gas_pct": "gas_eui_pct_error", "share": "gas_share_error_pts",
        "pred_site": "pred_site_eui_kbtu_sf", "truth_site": "truth_site_eui_kbtu_sf",
        "elec_abs": "elec_eui_abs_error_kbtu_sf", "gas_abs": "gas_eui_abs_error_kbtu_sf",
    }
    return rows, cmap, "job_number"


def grouped_payload(rows, cmap, job_key: str) -> dict:
    by_type: dict[str, list] = defaultdict(list)
    for r in rows:
        by_type[r["_type"]].append(r)
    jobs_all = len({r[job_key] for r in rows})
    types = sorted(by_type, key=lambda t: (-len({r[job_key] for r in by_type[t]}), t))
    keys = ["All"] + types
    labels = {"All": f"All ({jobs_all} job{'s' if jobs_all != 1 else ''})"}
    for t in types:
        nj = len({r[job_key] for r in by_type[t]})
        labels[t] = f"{t} ({nj} job{'s' if nj != 1 else ''})"
    data = {"All": bundle_for(rows, cmap)}
    for t in types:
        data[t] = bundle_for(by_type[t], cmap)
    return {"keys": keys, "labels": labels, "data": data, "n_all": jobs_all}


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__TITLE__</title>
<style>
  :root {
    --bg: #1b1d21; --fg: #eceef1; --muted: #9aa3ad; --line: #2c3138;
    --card: #23262b; --accent: #6ea8fe; --warn: #e8b86d; --info: #7dc4e0;
    --danger: #e09090; --plot: #121417;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f6f7f8; --fg: #1b1d21; --muted: #5c6570; --line: #d7dbe0;
      --card: #fff; --accent: #2f6feb; --warn: #b7791f; --info: #1d7a96;
      --danger: #b42318; --plot: #fff;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.45 system-ui, Segoe UI, sans-serif; background: var(--bg); color: var(--fg); }
  main { max-width: 1100px; margin: 0 auto; padding: 28px 20px 48px; }
  h1 { font-size: 22px; font-weight: 650; margin: 0 0 6px; }
  h2 { font-size: 16px; font-weight: 650; margin: 28px 0 8px; }
  p { color: var(--muted); margin: 0 0 12px; }
  .callout { background: var(--card); border: 1px solid var(--line); padding: 12px 14px; margin: 16px 0; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 12px 0; }
  label { color: var(--muted); font-size: 13px; }
  select, button {
    background: var(--card); color: var(--fg); border: 1px solid var(--line);
    padding: 6px 10px; font: inherit; border-radius: 0;
  }
  button.on { background: var(--accent); color: #111; border-color: var(--accent); }
  .stats { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; margin: 12px 0; }
  .stat { background: var(--card); border: 1px solid var(--line); padding: 10px 12px; }
  .stat b { display: block; font-size: 18px; font-weight: 650; }
  .stat span { color: var(--muted); font-size: 12px; }
  svg { width: 100%; height: auto; background: var(--plot); border: 1px solid var(--line); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--line); }
  th { color: var(--muted); font-weight: 550; }
  .cap { font-size: 12px; color: var(--muted); margin-top: 6px; }
  @media print { body { background: #fff; color: #111; } .callout, .stat, svg { border-color: #ccc; } }
</style>
</head>
<body>
<main>
  <h1>__TITLE__</h1>
  <p>__INTRO__</p>
  <div class="callout" id="note"></div>
  <div class="row">
    <label for="ptype">Property type</label>
    <select id="ptype"></select>
  </div>
  <div class="row" id="variants"></div>
  <h2>Fuel overlay — signed % error density</h2>
  <p>Three kernel densities on the same axis. |error| &gt; 150% is dropped from the curves (not from medians) so near-zero truth cannot flatten the plot.</p>
  <div id="density"></div>
  <p class="cap" id="density-cap"></p>
  <div class="row" id="fuels"></div>
  <div class="stats" id="stats1"></div>
  <div class="stats" id="stats2"></div>
  <h2 id="hist-title">Histogram</h2>
  <p>10-point bins of signed % error. Labels are the left edge of each bin. Values outside −70% to 140% clip into the end bins. Gas/electricity histograms exclude |error| &gt; 150%.</p>
  <div id="hist"></div>
  <p class="cap" id="hist-cap"></p>
  <h2>Fuel comparison</h2>
  <table id="cmp"></table>
  <p class="cap">Source: 2026-08-26 freeze, Phase 2. Headline = required fields present and whole_property_full_year. Signed error = (predicted − consumed truth) / truth.</p>
</main>
<script>
const PAYLOAD = __PAYLOAD__;
const HIST_CATS = __HIST__;
const DENSITY_CATS = __DENS__;
const FUELS = {site:"Site total", elec:"Electricity", gas:"Natural gas"};
const VARIANTS = ["required_only","with_basics","advanced"];
let ptype = "All", variant = "required_only", fuel = "site";

function fmt(n){ if(n==null) return "—"; return (n>0?"+":"")+n.toFixed(1)+"%"; }
function pct(n,d){ return d? Math.round(100*n/d)+"%" : "—"; }
function bundle(){ return PAYLOAD.data[ptype][variant]; }
function d(){ return bundle()[fuel]; }

function svgLine(series, cats, h){
  const w=1000, pad=48, H=h, innerW=w-pad*2, innerH=H-pad*1.6;
  const all=series.flatMap(s=>s.data);
  const ymax=Math.max(...all, 0.05);
  const x=i=> pad + i*(innerW/(cats.length-1));
  const y=v=> pad*0.6 + innerH*(1-v/ymax);
  const colors={neutral:"#9aa3ad", info:"#7dc4e0", warning:"#e8b86d"};
  let paths="";
  for(const s of series){
    const pts=s.data.map((v,i)=>`${i?"L":"M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const fill=s.data.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const base=`${x(0)},${y(0)}`;
    const last=`${x(s.data.length-1)},${y(0)}`;
    paths += `<polygon fill="${colors[s.tone]}" fill-opacity="0.12" points="${base} ${fill} ${last}"/>`;
    paths += `<path d="${pts}" fill="none" stroke="${colors[s.tone]}" stroke-width="2"/>`;
  }
  const xt=[0,7,14,21,28,35,42].filter(i=>i<cats.length).map(i=>
    `<text x="${x(i)}" y="${H-10}" fill="#9aa3ad" font-size="11" text-anchor="middle">${cats[i]}</text>`).join("");
  const legend=series.map((s,i)=>`<rect x="${pad+i*160}" y="8" width="12" height="12" fill="${colors[s.tone]}"/><text x="${pad+18+i*160}" y="18" fill="#eceef1" font-size="12">${s.name}</text>`).join("");
  return `<svg viewBox="0 0 ${w} ${H}" role="img">${legend}${paths}${xt}</svg>`;
}
function svgBars(data, cats, h, color){
  const w=1000, pad=48, H=h, innerW=w-pad*2, innerH=H-pad*1.6;
  const ymax=Math.max(...data, 1);
  const bw=innerW/data.length;
  let bars="";
  data.forEach((v,i)=>{
    const bh=innerH*(v/ymax);
    const x=pad+i*bw+1;
    const y=pad*0.5+innerH-bh;
    bars += `<rect x="${x}" y="${y}" width="${Math.max(bw-2,1)}" height="${bh}" fill="${color}"/>`;
  });
  const xt=[0,5,10,14,20].filter(i=>i<cats.length).map(i=>
    `<text x="${pad+i*bw+bw/2}" y="${H-10}" fill="#9aa3ad" font-size="11" text-anchor="middle">${cats[i]}</text>`).join("");
  return `<svg viewBox="0 0 ${w} ${H}" role="img">${bars}${xt}</svg>`;
}
function stat(html){ return html; }
function render(){
  const b=bundle(), cur=d(), isGas=fuel==="gas";
  document.getElementById("note").textContent = __NOTE__;
  document.getElementById("density").innerHTML = svgLine([
    {name:"Site total", data:b.site.kde, tone:"neutral"},
    {name:"Electricity", data:b.elec.kde, tone:"info"},
    {name:"Natural gas", data:b.gas.kde, tone:"warning"},
  ], DENSITY_CATS, 300);
  document.getElementById("density-cap").textContent =
    `X: signed % error · Y: density × 100 · ${variant} · ${PAYLOAD.labels[ptype]} · gas curve uses ${b.gas.n_clip}/${b.gas.n} jobs with |error| ≤ 150%`;
  document.getElementById("stats1").innerHTML = `
    <div class="stat"><b>${cur.n}</b><span>${FUELS[fuel]} n</span></div>
    <div class="stat"><b>${fmt(cur.median)}</b><span>Median signed %</span></div>
    <div class="stat"><b>${cur.abs_med.toFixed(1)}%</b><span>Median |error|</span></div>
    <div class="stat"><b>${pct(cur.under, cur.n)}</b><span>Under-predicted</span></div>`;
  const extra = isGas || fuel==="elec"
    ? `<div class="stat"><b>${cur.kbtu_med_abs ?? "—"} kBtu/sf</b><span>Median |${fuel} error|</span></div>`
    : `<div class="stat"><b>${fmt(cur.mean)}</b><span>Mean signed % (unstable if outliers)</span></div>`;
  document.getElementById("stats2").innerHTML = `
    <div class="stat"><b>${pct(cur.within20, cur.n)}</b><span>|error| ≤ 20%</span></div>
    <div class="stat"><b>${cur.gt50}</b><span>Jobs |error| &gt; 50%</span></div>
    ${extra}
    <div class="stat"><b>${b.share_med_abs.toFixed(1)} pts</b><span>Median |gas-share error|</span></div>`;
  document.getElementById("hist-title").textContent = "Histogram — "+FUELS[fuel];
  document.getElementById("hist").innerHTML = svgBars(cur.hist, HIST_CATS, 240, isGas ? "#e8b86d" : "#7dc4e0");
  document.getElementById("hist-cap").textContent = `X: bin start (signed % error) · Y: jobs · ${variant} · ${FUELS[fuel]}`;
  const row=(name,s,kb,share)=>{
    return `<tr><td>${name}</td><td>${s.n}</td><td>${fmt(s.median)}</td><td>${s.abs_med}%</td><td>${s.iqr.toFixed(1)}</td><td>${s.within20}/${s.n}</td><td>${kb}</td><td>${share}</td></tr>`;
  };
  document.getElementById("cmp").innerHTML = `<thead><tr><th>Output</th><th>n</th><th>Median %</th><th>Med |%|</th><th>IQR pp</th><th>≤20%</th><th>Med kBtu/sf |err|</th><th>Gas share |pts|</th></tr></thead><tbody>
    ${row("Site total", b.site, "—", "—")}
    ${row("Electricity", b.elec, b.elec.kbtu_med_abs, "—")}
    ${row("Natural gas", b.gas, b.gas.kbtu_med_abs, b.share_med_abs)}
  </tbody>`;
}
function btnRow(id, items, get, set){
  const el=document.getElementById(id);
  el.innerHTML="";
  items.forEach(([val,label])=>{
    const b=document.createElement("button");
    b.textContent=label; b.className=get()===val?"on":"";
    b.onclick=()=>{ set(val); document.querySelectorAll("#"+id+" button").forEach(x=>x.classList.remove("on")); b.classList.add("on"); render(); };
    el.appendChild(b);
  });
}
PAYLOAD.keys.forEach(k=>{
  const o=document.createElement("option");
  o.value=k; o.textContent=PAYLOAD.labels[k];
  document.getElementById("ptype").appendChild(o);
});
document.getElementById("ptype").onchange=e=>{ ptype=e.target.value; render(); };
btnRow("variants", VARIANTS.map(v=>[v,v]), ()=>variant, v=>variant=v);
btnRow("fuels", Object.entries(FUELS), ()=>fuel, v=>fuel=v);
render();
</script>
</body>
</html>
"""


def write_html(path: Path, title: str, intro: str, note: str, payload: dict) -> None:
    html = (
        HTML.replace("__TITLE__", title)
        .replace("__INTRO__", intro)
        .replace("__NOTE__", json.dumps(note))
        .replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
        .replace("__HIST__", json.dumps(HIST_CATS))
        .replace("__DENS__", json.dumps(DENSITY_CATS))
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def write_ci_canvas(payload: dict) -> None:
    dest = Path.home() / ".cursor/projects/c-Python-Building-Stock-Energy-Estimator-v4-Application/canvases/ci-eui-error-distribution.canvas.tsx"
    body = CANVAS.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
    dest.write_text(body, encoding="utf-8")


CANVAS = r'''import {
  BarChart,
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Grid,
  H1,
  H2,
  LineChart,
  Row,
  Select,
  Stack,
  Stat,
  Table,
  Text,
  useCanvasState,
} from "cursor/canvas";

type Variant = "required_only" | "with_basics" | "advanced";
type Fuel = "site" | "elec" | "gas";
type FuelStats = {
  n: number; min: number; q1: number; median: number; mean: number; q3: number;
  max: number; sd: number; iqr: number; abs_med: number; abs_mean: number;
  abs_q1: number; abs_q3: number; abs_iqr: number; abs_sd: number; abs_max: number;
  under: number; within10: number; within20: number; gt50: number;
  hist: number[]; kde: number[]; n_clip?: number;
  kbtu_med?: number | null; kbtu_med_abs?: number | null;
};
type VariantBundle = {
  site: FuelStats; elec: FuelStats; gas: FuelStats;
  share_med: number; share_med_abs: number;
};

const VARIANT_LABELS: Record<Variant, string> = {
  required_only: "required_only",
  with_basics: "with_basics",
  advanced: "advanced",
};
const FUEL_LABELS: Record<Fuel, string> = {
  site: "Site total",
  elec: "Electricity",
  gas: "Natural gas",
};
const HIST_CATS = [
  "-70", "-60", "-50", "-40", "-30", "-20", "-10", "0", "10", "20", "30",
  "40", "50", "60", "70", "80", "90", "100", "110", "120", "130",
];
const DENSITY_CATS = [
  "-70", "-65", "-60", "-55", "-50", "-45", "-40", "-35", "-30", "-25",
  "-20", "-15", "-10", "-5", "0", "5", "10", "15", "20", "25", "30", "35",
  "40", "45", "50", "55", "60", "65", "70", "75", "80", "85", "90", "95",
  "100", "105", "110", "115", "120", "125", "130", "135", "140",
];

const PAYLOAD: {
  keys: string[];
  labels: Record<string, string>;
  data: Record<string, Record<Variant, VariantBundle>>;
  n_all: number;
} = __PAYLOAD__;

function pct(n: number, d: number): string {
  return d ? `${((100 * n) / d).toFixed(0)}%` : "—";
}
function fmt(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export default function CiEuiErrorDistribution() {
  const [ptype, setPtype] = useCanvasState<string>("ptype", "All");
  const [variant, setVariant] = useCanvasState<Variant>("variant", "required_only");
  const [fuel, setFuel] = useCanvasState<Fuel>("fuel", "site");
  const typeKey = PAYLOAD.data[ptype] ? ptype : "All";
  const bundle = PAYLOAD.data[typeKey][variant];
  const d = bundle[fuel];
  const isGas = fuel === "gas";
  const small = d.n > 0 && d.n < 8;

  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>C&amp;I EUI error — site total and fuel split</H1>
        <Text tone="secondary">
          Headline set: required fields present and whole_property_full_year.
          Signed error = (predicted − truth) / truth. Negative = under-prediction.
          Density curves drop |error| &gt; 150% so near-zero truth cannot flatten
          the plot. Medians use the full sample. Filter by ComStock property type
          (All is the headline 130 jobs). Source: 2026-08-26 freeze, Phase 2.
        </Text>
      </Stack>

      <Callout tone="warning">
        Typical |error| is about 45% on All / required_only — roughly twice
        multifamily. Extra fields shrink median bias, not typical |error|. Mean
        % is not usable: a few near-zero truth EUIs explode it. Quote medians
        and kBtu/sf. Gas % is worse than site total.
      </Callout>

      <Row gap={12} align="center" wrap>
        <Text>Property type</Text>
        <Select
          value={typeKey}
          onChange={setPtype}
          options={PAYLOAD.keys.map((k) => ({ value: k, label: PAYLOAD.labels[k] }))}
        />
      </Row>

      {small ? (
        <Callout tone="info">
          n = {d.n} for this type. Density and histogram are noisy; treat the
          median as a sketch, not a stable property-type result.
        </Callout>
      ) : null}

      <Row gap={8} wrap>
        {(Object.keys(VARIANT_LABELS) as Variant[]).map((v) => (
          <span key={v}>
            <Button
              variant={variant === v ? "primary" : "secondary"}
              onClick={() => setVariant(v)}
            >
              {VARIANT_LABELS[v]}
            </Button>
          </span>
        ))}
      </Row>

      <H2>Fuel overlay — signed % error density</H2>
      <Text tone="secondary" size="small">
        Three kernel densities on the same axis. Gas usually peaks further left.
      </Text>
      <LineChart
        height={300}
        fill
        beginAtZero
        categories={DENSITY_CATS}
        series={[
          { name: "Site total", data: bundle.site.kde, tone: "neutral" },
          { name: "Electricity", data: bundle.elec.kde, tone: "info" },
          { name: "Natural gas", data: bundle.gas.kde, tone: "warning" },
        ]}
      />
      <Text tone="tertiary" size="small">
        X: signed % error · Y: density × 100 · {VARIANT_LABELS[variant]} ·{" "}
        {PAYLOAD.labels[typeKey]} · gas curve uses {bundle.gas.n_clip}/{bundle.gas.n}{" "}
        jobs with |error| ≤ 150%
      </Text>

      <Row gap={8} wrap>
        {(Object.keys(FUEL_LABELS) as Fuel[]).map((k) => (
          <span key={k}>
            <Button
              variant={fuel === k ? "primary" : "secondary"}
              onClick={() => setFuel(k)}
            >
              {FUEL_LABELS[k]}
            </Button>
          </span>
        ))}
      </Row>

      <Grid columns={4} gap={12}>
        <Stat value={String(d.n)} label={`${FUEL_LABELS[fuel]} n`} />
        <Stat value={fmt(d.median)} label="Median signed %" tone="warning" />
        <Stat value={`${d.abs_med.toFixed(1)}%`} label="Median |error|" />
        <Stat value={pct(d.under, d.n)} label="Under-predicted" tone="warning" />
      </Grid>
      <Grid columns={4} gap={12}>
        <Stat value={pct(d.within20, d.n)} label="|error| ≤ 20%" />
        <Stat value={String(d.gt50)} label="Jobs |error| > 50%" tone="danger" />
        {isGas || fuel === "elec" ? (
          <Stat
            value={`${d.kbtu_med_abs ?? "—"} kBtu/sf`}
            label={`Median |${fuel} error|`}
          />
        ) : (
          <Stat value={fmt(d.mean)} label="Mean signed %" />
        )}
        <Stat
          value={`${bundle.share_med_abs.toFixed(1)} pts`}
          label="Median |gas-share error|"
        />
      </Grid>

      <Stack gap={8}>
        <H2>Histogram — {FUEL_LABELS[fuel]}</H2>
        <Text tone="secondary" size="small">
          10-point bins of signed % error. Labels are the left edge of each bin.
        </Text>
        <BarChart
          height={240}
          categories={HIST_CATS}
          series={[{ name: "Jobs", data: d.hist, tone: isGas ? "warning" : "info" }]}
          showValues={false}
        />
        <Text tone="tertiary" size="small">
          X: bin start (signed % error) · Y: jobs · {VARIANT_LABELS[variant]} ·{" "}
          {FUEL_LABELS[fuel]}
        </Text>
      </Stack>

      <Card>
        <CardHeader>Signed % error — {FUEL_LABELS[fuel]}</CardHeader>
        <CardBody>
          <Grid columns={4} gap={12}>
            <Stat value={fmt(d.min)} label="Min" />
            <Stat value={fmt(d.q1)} label="Q1" />
            <Stat value={fmt(d.median)} label="Median" />
            <Stat value={fmt(d.q3)} label="Q3" />
            <Stat value={isGas ? "n/a" : fmt(d.max)} label={isGas ? "Max (explodes)" : "Max"} />
            <Stat value={`${d.iqr.toFixed(1)} pp`} label="IQR" />
            <Stat value={isGas ? "n/a" : fmt(d.mean)} label="Mean" />
            <Stat value={isGas ? "n/a" : `${d.sd.toFixed(1)} pp`} label="SD" />
          </Grid>
        </CardBody>
      </Card>

      <H2>Fuel comparison — {VARIANT_LABELS[variant]}</H2>
      <Table
        headers={[
          "Output", "n", "Median %", "Med |%|", "IQR pp", "≤20%",
          "Med kBtu/sf |err|", "Gas share |pts|",
        ]}
        rows={[
          [
            "Site total", String(bundle.site.n), fmt(bundle.site.median),
            `${bundle.site.abs_med}%`, bundle.site.iqr.toFixed(1),
            `${bundle.site.within20}/${bundle.site.n}`, "—", "—",
          ],
          [
            "Electricity", String(bundle.elec.n), fmt(bundle.elec.median),
            `${bundle.elec.abs_med}%`, bundle.elec.iqr.toFixed(1),
            `${bundle.elec.within20}/${bundle.elec.n}`,
            String(bundle.elec.kbtu_med_abs ?? "—"), "—",
          ],
          [
            "Natural gas", String(bundle.gas.n), fmt(bundle.gas.median),
            `${bundle.gas.abs_med}%`, bundle.gas.iqr.toFixed(1),
            `${bundle.gas.within20}/${bundle.gas.n}`,
            String(bundle.gas.kbtu_med_abs ?? "—"),
            String(bundle.share_med_abs),
          ],
        ]}
      />
    </Stack>
  );
}
'''


def main() -> None:
    charts = SNAP / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    ci_rows, ci_map, ci_key = load_ci()
    ci = grouped_payload(ci_rows, ci_map, ci_key)
    write_html(
        charts / "ci_eui_error_distribution.html",
        "C&I EUI error — site total and fuel split",
        "Headline: required fields present and whole_property_full_year. "
        "Use Property type to slice (All is the 130-job headline). "
        "with_utility is omitted — it is calibration, not accuracy.",
        "Typical |error| is about 45% on All / required_only — roughly twice "
        "multifamily. Extra fields shrink median bias, not typical |error|. "
        "Mean % is not usable when truth EUI is near zero. Quote medians and kBtu/sf.",
        ci,
    )
    write_ci_canvas(ci)

    mf_rows, mf_map, mf_key = load_mf()
    mf = grouped_payload(mf_rows, mf_map, mf_key)
    write_html(
        charts / "mf_eui_error_distribution.html",
        "Multifamily EUI error — site total and fuel split",
        "Headline: required fields present and whole_property_full_year. "
        "Property type is almost entirely Multi-Family; All is the 302-job headline.",
        "Site total (~21% median |error|) hides a fuel-mix problem. Electricity is "
        "closer; gas is worse and extra inputs make gas worse, not better. Mean gas "
        "% error is not usable — quote gas as median |error| and kBtu/sf.",
        mf,
    )
    print("wrote", charts / "ci_eui_error_distribution.html")
    print("wrote", charts / "mf_eui_error_distribution.html")
    print("ci types", ci["labels"])
    print("mf types", mf["labels"])
    print("ci all required_only site n", ci["data"]["All"]["required_only"]["site"]["n"],
          "med", ci["data"]["All"]["required_only"]["site"]["median"],
          "abs", ci["data"]["All"]["required_only"]["site"]["abs_med"])
    print("mf all required_only site n", mf["data"]["All"]["required_only"]["site"]["n"],
          "med", mf["data"]["All"]["required_only"]["site"]["median"],
          "abs", mf["data"]["All"]["required_only"]["site"]["abs_med"])


if __name__ == "__main__":
    main()
