"""
PHASE 2 of 2 -- bulk analysis.

Read the compiled test-case CSV, run every row through the real assessment
pipeline, and write per-row predictions and errors against the audited ground
truth.

    python testcases/run_assessment.py                          # out/testcases.csv
    python testcases/run_assessment.py -i <csv> -o <csv>
    python testcases/run_assessment.py --variant required_only  # one tier only
    python testcases/run_assessment.py --job 260571             # one project

This phase never touches a project folder -- it reads only the CSV that phase 1
(`compile_dataset.py`) produced. So the slow, network-bound compilation and the
model-bound analysis can be re-run independently of each other.

Because the CSV carries one row per (job, variant), the output directly answers
what the variants are for: how much accuracy each extra tier of user input buys.

Two caveats when reading the output CSV:

  * `with_utility` is NOT an accuracy measurement. Supplying measured
    consumption puts the pipeline on its calibration path (`calibrated=true`),
    so predicted EUI is derived from the input and lands on ~0% error by
    construction. Compare the other three tiers to judge predictive accuracy.
  * The cost and measure-count columns are not like-for-like. The app scores
    every applicable measure in the NREL catalog; the audit reports only the
    handful the engineer selected and priced. Comparing the totals is
    meaningless -- use measures.csv to match individual measures instead.

Calls the service layer in-process (no HTTP, no server), the same way
scripts/validate_espm_buildings.py does.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
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

DEFAULT_IN = SNAP / "freeze" / "multifamily" / "testcases.csv"
DEFAULT_OUT = SNAP / "results" / "multifamily" / "assessment_results.csv"

INT_FIELDS = {"num_stories", "year_built"}
FLOAT_FIELDS = {
    "sqft", "operating_hours", "annual_electricity_kwh", "annual_natural_gas_therms",
    "annual_fuel_oil_gallons", "annual_propane_gallons", "annual_district_heating_kbtu",
}

KBTU_PER_KWH = 3.412
KBTU_PER_THERM = 100.0

OUT_COLS = [
    "job_number", "variant", "property_name", "field_count", "status", "error",
    "pred_site_eui_kbtu_sf", "truth_site_eui_kbtu_sf", "site_eui_pct_error",
    # per-fuel site EUI, kBtu/sf. The workbooks only ever carry electricity and
    # natural gas -- across all 20 golden projects those two reconstruct the
    # delivered site EUI to 0.0%, so there is no third fuel to account for.
    # pred_other_eui_kbtu_sf is therefore a pure false-positive check: anything
    # the model puts in fuel oil / propane / district heating is fuel the
    # building does not burn.
    "pred_elec_eui_kbtu_sf", "truth_elec_eui_kbtu_sf",
    "elec_eui_pct_error", "elec_eui_abs_error_kbtu_sf",
    "pred_gas_eui_kbtu_sf", "truth_gas_eui_kbtu_sf",
    "gas_eui_pct_error", "gas_eui_abs_error_kbtu_sf",
    "pred_other_eui_kbtu_sf",
    "pred_gas_share_pct", "truth_gas_share_pct", "gas_share_error_pts",
    "pred_measure_count", "truth_measure_count",
    "pred_installed_cost_usd", "truth_installed_cost_usd", "installed_cost_pct_error",
    "pred_annual_savings_usd", "truth_annual_savings_usd", "annual_savings_pct_error",
    "imputed_field_count", "calibrated", "low_confidence_fields", "building_type_note",
    "missing_required", "truth_utility_data_completeness",
]


def build_input(row: dict, input_fields: list[str]) -> dict:
    """Rebuild a BuildingInput payload from a CSV row, preserving blank = absent."""
    payload = {}
    for f in input_fields:
        raw = (row.get(f) or "").strip()
        if raw == "":
            continue  # blank means this variant deliberately omits the field
        try:
            if f in INT_FIELDS:
                payload[f] = int(float(raw))
            elif f in FLOAT_FIELDS:
                payload[f] = float(raw)
            else:
                payload[f] = raw
        except ValueError:
            # Narrative ranges like "1981 - 1982" are not a year; omit the
            # field (same as blank) so BuildingInput validation records a
            # row error instead of killing the whole run.
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


def truth_fuel_eui(row: dict, sqft: float | None) -> tuple[float | None, float | None]:
    """Delivered per-fuel site EUI (kBtu/sf) from the workbook's annual totals.

    Uses the same sqft the prediction used -- the workbook area -- so the two
    sides share a denominator. Returns (electricity, natural_gas); either is
    None when the workbook recorded no total for that fuel.
    """
    if not sqft:
        return None, None
    kwh = to_float(row.get("truth_annual_electricity_kwh"))
    therms = to_float(row.get("truth_annual_gas_therms"))
    elec = kwh * KBTU_PER_KWH / sqft if kwh is not None else None
    gas = therms * KBTU_PER_THERM / sqft if therms is not None else None
    return elec, gas


def share_pct(part: float | None, total: float | None) -> float | None:
    """Gas share of site energy, in percent."""
    if part is None or not total:
        return None
    return part / total * 100.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default=str(DEFAULT_IN))
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    ap.add_argument("--variant", action="append", help="only these variants")
    ap.add_argument("--job", action="append", help="only these job numbers")
    ap.add_argument(
        "--resume",
        action="store_true",
        help="skip (job_number, variant) already in the output CSV",
    )
    a = ap.parse_args()

    src = Path(a.input)
    if not src.exists():
        raise SystemExit(f"{src} not found -- run compile_dataset.py first (phase 1)")

    with src.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"{src} has no rows")

    # Input columns are everything between the metadata block and truth_*.
    header = list(rows[0].keys())
    meta_end = header.index("area_conflict") + 1
    input_fields = [c for c in header[meta_end:] if not c.startswith("truth_")]

    if a.variant:
        rows = [r for r in rows if r["variant"] in set(a.variant)]
    if a.job:
        rows = [r for r in rows if r["job_number"] in set(a.job)]
    print(f"{len(rows)} rows from {src.name}")

    print("loading models ...")
    model_dir = os.environ.get("MODEL_DIR", str(REPO / "XGB_Models"))
    mm = ModelManager(model_dir=model_dir)
    mm.index_all()
    cc = CostCalculatorService()
    imp = ImputationService(str(Path(model_dir) / "Imputation"))
    imp.load()

    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    results = []
    done: set[tuple[str, str]] = set()
    if a.resume and dest.exists():
        with dest.open(newline="", encoding="utf-8-sig") as fh:
            results = list(csv.DictReader(fh))
        done = {(r["job_number"], r["variant"]) for r in results}
        rows = [r for r in rows if (r["job_number"], r["variant"]) not in done]
        print(f"resume: {len(done)} already written, {len(rows)} remaining")

    def flush() -> None:
        with dest.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=OUT_COLS, extrasaction="ignore")
            w.writeheader()
            for r in results:
                w.writerow({k: ("" if r.get(k) is None else r.get(k, "")) for k in OUT_COLS})

    for i, row in enumerate(rows, 1):
        payload = build_input(row, input_fields)
        label = f"{row['job_number']}/{row['variant']}"
        print(f"  [{i}/{len(rows)}] {label} ({len(payload)} fields)")

        out = {
            "job_number": row["job_number"],
            "variant": row["variant"],
            "property_name": row.get("property_name", ""),
            "field_count": len(payload),
            "low_confidence_fields": row.get("low_confidence_fields", ""),
            "building_type_note": row.get("building_type_note", ""),
            "missing_required": row.get("missing_required", ""),
            "truth_utility_data_completeness": row.get("truth_utility_data_completeness", ""),
            "truth_site_eui_kbtu_sf": row.get("truth_site_eui_kbtu_sf", ""),
            "truth_measure_count": row.get("truth_measure_count", ""),
            "truth_installed_cost_usd": row.get("truth_total_installed_cost_usd", ""),
            "truth_annual_savings_usd": row.get("truth_total_annual_savings_usd", ""),
        }

        truth_sqft = to_float(row.get("sqft"))
        t_elec, t_gas = truth_fuel_eui(row, truth_sqft)
        t_total = to_float(row.get("truth_site_eui_kbtu_sf"))
        out["truth_elec_eui_kbtu_sf"] = None if t_elec is None else round(t_elec, 3)
        out["truth_gas_eui_kbtu_sf"] = None if t_gas is None else round(t_gas, 3)
        t_share = share_pct(t_gas, t_total)
        out["truth_gas_share_pct"] = None if t_share is None else round(t_share, 2)

        try:
            result = _assess_single(BuildingInput(**payload), 0, mm, cc, imputation_service=imp)
        except Exception as exc:  # a failing row is a finding, not a crash
            out.update(status="error", error=f"{type(exc).__name__}: {exc}")
            results.append(out)
            print(f"        ERROR {exc}")
            if i % 10 == 0 or i == len(rows):
                flush()
            continue

        measures = [m for m in (result.measures or []) if m.applicable]
        sqft = payload.get("sqft") or 0
        # utility_bill_savings_per_sf is per square foot; scale to whole-building
        # dollars so it is comparable with the workbook's annual savings.
        out.update(
            status="ok",
            error="",
            pred_site_eui_kbtu_sf=round(result.baseline.total_eui_kbtu_sf, 3),
            imputed_field_count=len(result.input_summary.imputed_fields or []),
            calibrated=result.calibrated,
            pred_measure_count=len(measures),
            pred_installed_cost_usd=round(
                sum((m.cost.installed_cost_total if m.cost else 0) for m in measures), 2
            ),
            pred_annual_savings_usd=round(
                sum((m.utility_bill_savings_per_sf or 0) * sqft for m in measures), 2
            ),
        )
        # Per-fuel baseline. eui_by_fuel is already kBtu/sf, same units as the
        # workbook truth, so no conversion on this side.
        bf = result.baseline.eui_by_fuel
        p_elec, p_gas = bf.electricity, bf.natural_gas
        p_other = bf.fuel_oil + bf.propane + bf.district_heating
        out["pred_elec_eui_kbtu_sf"] = round(p_elec, 3)
        out["pred_gas_eui_kbtu_sf"] = round(p_gas, 3)
        out["pred_other_eui_kbtu_sf"] = round(p_other, 3)
        out["elec_eui_pct_error"] = pct_err(p_elec, out["truth_elec_eui_kbtu_sf"])
        out["gas_eui_pct_error"] = pct_err(p_gas, out["truth_gas_eui_kbtu_sf"])
        te = to_float(out["truth_elec_eui_kbtu_sf"])
        tg = to_float(out["truth_gas_eui_kbtu_sf"])
        out["elec_eui_abs_error_kbtu_sf"] = None if te is None else round(p_elec - te, 3)
        out["gas_eui_abs_error_kbtu_sf"] = None if tg is None else round(p_gas - tg, 3)
        # Share is the mix question on its own terms: a building can have the
        # right total and still be predicted as the wrong kind of building.
        p_share = share_pct(p_gas, out["pred_site_eui_kbtu_sf"])
        out["pred_gas_share_pct"] = None if p_share is None else round(p_share, 2)
        ts = to_float(out["truth_gas_share_pct"])
        out["gas_share_error_pts"] = (
            None if p_share is None or ts is None else round(p_share - ts, 2)
        )

        out["site_eui_pct_error"] = pct_err(out["pred_site_eui_kbtu_sf"], out["truth_site_eui_kbtu_sf"])
        out["installed_cost_pct_error"] = pct_err(out["pred_installed_cost_usd"], out["truth_installed_cost_usd"])
        out["annual_savings_pct_error"] = pct_err(out["pred_annual_savings_usd"], out["truth_annual_savings_usd"])
        results.append(out)
        if i % 10 == 0 or i == len(rows):
            flush()

    if len(results) <= 20:
        print(f"\n{'job/variant':30} {'fields':>6} {'EUI':>8} {'truth':>8} {'err %':>8}")
        for r in results:
            if r["status"] != "ok":
                print(f"{r['job_number'] + '/' + r['variant']:30} ERROR")
                continue
            err = r.get("site_eui_pct_error")
            print(
                f"{r['job_number'] + '/' + r['variant']:30} {r['field_count']:>6} "
                f"{r['pred_site_eui_kbtu_sf']:>8.2f} "
                f"{to_float(r['truth_site_eui_kbtu_sf']) or 0:>8.2f} "
                f"{(f'{err:+.1f}' if err is not None else '-'):>8}"
            )
    else:
        n_ok = sum(1 for r in results if r.get("status") == "ok")
        print(f"\n{n_ok} ok / {len(results) - n_ok} error of {len(results)} rows")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
