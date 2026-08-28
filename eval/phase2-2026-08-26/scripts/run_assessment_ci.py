"""
PHASE 2 of 2 -- C&I bulk analysis.

Reads the compiled test-case CSV, runs every row through the assessment
pipeline, and writes per-row predictions vs consumed-site-EUI ground truth.

    python testcases/commercial_industrial/run_assessment.py
    python testcases/commercial_industrial/run_assessment.py -i <csv> -o <csv>
    python testcases/commercial_industrial/run_assessment.py --job 221051

CSV only -- never walks project folders or the share. Score consumed
`truth_site_eui` (not purchased). `with_utility` is calibration, not accuracy.

Join compile_log.missing_required onto every row: it is not a testcases.csv
column. Do not load a second ModelManager while a multifamily run is in memory.
"""

from __future__ import annotations

import argparse
import atexit
import csv
import faulthandler
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE.parent
REPO = HERE.parents[2]  # eval/phase2-.../scripts -> repo root
sys.path.insert(0, str(REPO / "backend"))

from app.inference.imputation_service import ImputationService  # noqa: E402
from app.inference.model_manager import ModelManager  # noqa: E402
from app.schemas.request import BuildingInput  # noqa: E402
from app.services.assessment import _assess_single  # noqa: E402
from app.services.cost_calculator import CostCalculatorService  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

DEFAULT_IN = SNAP / "freeze" / "commercial_industrial" / "testcases.csv"
DEFAULT_OUT = SNAP / "results" / "commercial_industrial" / "assessment_results.csv"
DEFAULT_LOG = SNAP / "freeze" / "commercial_industrial" / "compile_log.csv"

INT_FIELDS = {"num_stories", "year_built"}
FLOAT_FIELDS = {
    "sqft", "operating_hours", "annual_electricity_kwh", "annual_natural_gas_therms",
    "annual_fuel_oil_gallons", "annual_propane_gallons", "annual_district_heating_kbtu",
}

INPUT_FIELDS = [
    "building_type", "sqft", "num_stories", "zipcode", "year_built",
    "heating_fuel", "dhw_fuel", "hvac_system_type", "wall_construction",
    "window_type", "window_to_wall_ratio", "lighting_type", "operating_hours",
    "hvac_heating_efficiency", "hvac_cooling_efficiency", "water_heater_efficiency",
    "insulation_wall", "infiltration",
    "annual_electricity_kwh", "annual_natural_gas_therms", "annual_fuel_oil_gallons",
    "annual_propane_gallons", "annual_district_heating_kbtu",
    "thermostat_heating_setpoint", "thermostat_cooling_setpoint",
    "thermostat_heating_setback", "thermostat_cooling_setback",
    "weekend_operating_hours",
]

OUT_COLS = [
    "job", "variant", "project_name", "field_count", "status", "error",
    "pred_site_eui", "truth_site_eui", "site_eui_pct_error",
    "pred_elec_eui", "truth_elec_eui", "elec_eui_pct_error", "elec_eui_abs_error",
    "pred_gas_eui", "truth_gas_eui", "gas_eui_pct_error", "gas_eui_abs_error",
    "pred_other_eui",
    "pred_gas_share_pct", "truth_gas_share_pct", "gas_share_error_pts",
    "pred_measure_count", "imputed_field_count", "calibrated",
    "utility_data_completeness", "missing_required", "narrative_filled",
    "has_onsite_solar", "truth_eui_convention",
]


def build_input(row: dict, input_fields: list[str]) -> dict:
    payload = {}
    for f in input_fields:
        if f not in row:
            continue
        raw = (row.get(f) or "").strip()
        if raw == "":
            continue
        try:
            if f in INT_FIELDS:
                payload[f] = int(float(raw))
            elif f in FLOAT_FIELDS:
                payload[f] = float(raw)
            else:
                payload[f] = raw
        except ValueError:
            continue
    return payload


def to_float(v) -> float | None:
    try:
        s = str(v).strip()
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def pct_err(pred, actual) -> float | None:
    p, a = to_float(pred), to_float(actual)
    return None if p is None or not a else (p - a) / a * 100.0


def share_pct(part: float | None, total: float | None) -> float | None:
    if part is None or not total:
        return None
    return part / total * 100.0


def rss_mb() -> str:
    """Working-set MB, or '?' if unavailable."""
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        if not ok:
            return "?"
        return f"{counters.WorkingSetSize / (1024 * 1024):.0f}"
    except Exception:
        return "?"


def setup_crash_logging(dest: Path) -> Path:
    """Append-only run log + faulthandler file (better than stdout on a native kill)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_log = dest.with_name(dest.stem + ".run.log")
    fault_fh = dest.with_name(dest.stem + ".fault.log").open("ab")
    faulthandler.enable(file=fault_fh, all_threads=True)

    def _atexit() -> None:
        try:
            with run_log.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"{datetime.now(timezone.utc).isoformat()} pid={os.getpid()} "
                    f"atexit rss_mb={rss_mb()}\n"
                )
                fh.flush()
        except OSError:
            pass

    atexit.register(_atexit)

    def _excepthook(exc_type, exc, tb) -> None:
        with run_log.open("a", encoding="utf-8") as fh:
            fh.write(
                f"{datetime.now(timezone.utc).isoformat()} UNCAUGHT "
                f"{exc_type.__name__}: {exc}\n"
            )
            traceback.print_exception(exc_type, exc, tb, file=fh)
            fh.flush()
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook
    return run_log


def runlog(path: Path, msg: str) -> None:
    line = (
        f"{datetime.now(timezone.utc).isoformat()} pid={os.getpid()} "
        f"rss_mb={rss_mb()} {msg}\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    print(msg, flush=True)


def load_missing_required(log_path: Path) -> dict[str, str]:
    if not log_path.exists():
        return {}
    with log_path.open(newline="", encoding="utf-8-sig") as fh:
        return {
            r["job"]: (r.get("missing_required") or "").strip()
            for r in csv.DictReader(fh)
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default=str(DEFAULT_IN))
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    ap.add_argument("--compile-log", default=str(DEFAULT_LOG))
    ap.add_argument("--variant", action="append")
    ap.add_argument("--job", action="append")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    dest = Path(a.out)
    rlog = setup_crash_logging(dest)
    runlog(rlog, f"start argv={sys.argv} cwd={os.getcwd()}")

    src = Path(a.input)
    if not src.exists():
        raise SystemExit(f"{src} not found")

    with src.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"{src} has no rows")

    missing_by_job = load_missing_required(Path(a.compile_log))
    input_fields = [c for c in INPUT_FIELDS if c in rows[0]]

    if a.variant:
        rows = [r for r in rows if r["variant"] in set(a.variant)]
    if a.job:
        rows = [r for r in rows if r["job"] in set(a.job)]
    runlog(rlog, f"loaded {len(rows)} rows from {src}")

    runlog(rlog, "loading models")
    model_dir = os.environ.get("MODEL_DIR", str(REPO / "XGB_Models"))
    mm = ModelManager(model_dir=model_dir)
    mm.index_all()
    cc = CostCalculatorService()
    imp = ImputationService(str(Path(model_dir) / "Imputation"))
    imp.load()
    runlog(rlog, f"models loaded MODEL_DIR={model_dir}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    results = []
    if a.resume and dest.exists():
        with dest.open(newline="", encoding="utf-8-sig") as fh:
            results = list(csv.DictReader(fh))
        done = {(r["job"], r["variant"]) for r in results}
        rows = [r for r in rows if (r["job"], r["variant"]) not in done]
        runlog(rlog, f"resume already={len(done)} remaining={len(rows)}")

    def flush() -> None:
        with dest.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=OUT_COLS, extrasaction="ignore")
            w.writeheader()
            for r in results:
                w.writerow({k: ("" if r.get(k) is None else r.get(k, "")) for k in OUT_COLS})

    for i, row in enumerate(rows, 1):
        payload = build_input(row, input_fields)
        job = row["job"]
        label = f"{job}/{row['variant']}"
        runlog(
            rlog,
            f"BEGIN [{i}/{len(rows)}] {label} fields={len(payload)} "
            f"completeness={row.get('utility_data_completeness','')} "
            f"missing_required={missing_by_job.get(job, '')!r}",
        )
        t0 = time.perf_counter()

        t_site = to_float(row.get("truth_site_eui"))
        t_elec = to_float(row.get("truth_elec_eui"))
        t_gas = to_float(row.get("truth_gas_eui"))
        t_share = share_pct(t_gas, t_site)

        out = {
            "job": job,
            "variant": row["variant"],
            "project_name": row.get("project_name", ""),
            "field_count": len(payload),
            "truth_site_eui": None if t_site is None else round(t_site, 4),
            "truth_elec_eui": None if t_elec is None else round(t_elec, 4),
            "truth_gas_eui": None if t_gas is None else round(t_gas, 4),
            "truth_gas_share_pct": None if t_share is None else round(t_share, 2),
            "utility_data_completeness": row.get("utility_data_completeness", ""),
            "missing_required": missing_by_job.get(job, ""),
            "narrative_filled": row.get("narrative_filled", ""),
            "has_onsite_solar": row.get("has_onsite_solar", ""),
            "truth_eui_convention": row.get("truth_eui_convention", ""),
        }

        try:
            result = _assess_single(BuildingInput(**payload), 0, mm, cc, imputation_service=imp)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            out.update(status="error", error=f"{type(exc).__name__}: {exc}")
            results.append(out)
            runlog(rlog, f"ERROR [{i}/{len(rows)}] {label} {elapsed:.1f}s {type(exc).__name__}: {exc}")
            flush()
            continue

        measures = [m for m in (result.measures or []) if m.applicable]
        bf = result.baseline.eui_by_fuel
        p_elec, p_gas = bf.electricity, bf.natural_gas
        p_other = bf.fuel_oil + bf.propane + bf.district_heating
        p_site = result.baseline.total_eui_kbtu_sf
        p_share = share_pct(p_gas, p_site)

        out.update(
            status="ok",
            error="",
            pred_site_eui=round(p_site, 4),
            imputed_field_count=len(result.input_summary.imputed_fields or []),
            calibrated=result.calibrated,
            pred_measure_count=len(measures),
            pred_elec_eui=round(p_elec, 4),
            pred_gas_eui=round(p_gas, 4),
            pred_other_eui=round(p_other, 4),
            elec_eui_pct_error=pct_err(p_elec, t_elec),
            gas_eui_pct_error=pct_err(p_gas, t_gas),
            elec_eui_abs_error=None if t_elec is None else round(p_elec - t_elec, 4),
            gas_eui_abs_error=None if t_gas is None else round(p_gas - t_gas, 4),
            pred_gas_share_pct=None if p_share is None else round(p_share, 2),
            gas_share_error_pts=(
                None if p_share is None or t_share is None else round(p_share - t_share, 2)
            ),
            site_eui_pct_error=pct_err(p_site, t_site),
        )
        results.append(out)
        elapsed = time.perf_counter() - t0
        runlog(
            rlog,
            f"END [{i}/{len(rows)}] {label} {elapsed:.1f}s status=ok "
            f"calibrated={out.get('calibrated')} pred_site_eui={out.get('pred_site_eui')}",
        )
        flush()

    n_ok = sum(1 for r in results if r.get("status") == "ok")
    if len(results) <= 20:
        print(f"\n{'job/variant':30} {'fields':>6} {'EUI':>8} {'truth':>8} {'err %':>8}")
        for r in results:
            if r["status"] != "ok":
                print(f"{r['job'] + '/' + r['variant']:30} ERROR")
                continue
            err = r.get("site_eui_pct_error")
            print(
                f"{r['job'] + '/' + r['variant']:30} {r['field_count']:>6} "
                f"{r['pred_site_eui']:>8.2f} "
                f"{(to_float(r['truth_site_eui']) or 0):>8.2f} "
                f"{(f'{err:+.1f}' if err is not None else '-'):>8}"
            )
    else:
        print(f"\n{n_ok} ok / {len(results) - n_ok} error of {len(results)} rows")
    runlog(rlog, f"finished ok={n_ok} error={len(results) - n_ok} total={len(results)} wrote={dest}")


if __name__ == "__main__":
    main()
