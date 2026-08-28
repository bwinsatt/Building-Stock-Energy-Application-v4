"""
Summarize the phase 2 output: accuracy by input tier, and the worst cases.

    python testcases/summarize_results.py [-i out/assessment_results.csv]

Reports median and mean signed error plus median absolute error per variant.
Median is the headline because a single badly-mapped building would drag a mean
around and hide the shape of the distribution.

`with_utility` is reported but flagged: supplying measured consumption puts the
pipeline on its calibration path, so its ~0% error is by construction and is not
an accuracy measurement.
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_IN = HERE.parent / "results" / "multifamily" / "assessment_results.csv"

ORDER = ["required_only", "with_basics", "advanced", "with_utility"]


def f(v):
    try:
        s = str(v).strip()
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def variant_table(ok: list[dict], title: str) -> None:
    print(f"\n{title}")
    print(f"{'variant':16} {'n':>5} {'median':>9} {'mean':>9} {'med|err|':>9} "
          f"{'min':>8} {'max':>8} {'under':>7}")
    print("-" * 76)
    for v in ORDER:
        vals = [f(r["site_eui_pct_error"]) for r in ok if r["variant"] == v]
        vals = [x for x in vals if x is not None]
        if not vals:
            print(f"{v:16} {0:>5}")
            continue
        under = sum(1 for x in vals if x < 0)
        tag = "  <- calibrated, not an accuracy measure" if v == "with_utility" else ""
        print(f"{v:16} {len(vals):>5} {st.median(vals):>8.1f}% {st.mean(vals):>8.1f}% "
              f"{st.median([abs(x) for x in vals]):>8.1f}% "
              f"{min(vals):>7.1f}% {max(vals):>7.1f}% {under:>4}/{len(vals)}{tag}")


def is_headline(r: dict) -> bool:
    missing = (r.get("missing_required") or "").strip()
    completeness = (r.get("truth_utility_data_completeness") or "").strip()
    return not missing and completeness == "whole_property_full_year"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default=str(DEFAULT_IN))
    a = ap.parse_args()

    rows = list(csv.DictReader(Path(a.input).open(newline="", encoding="utf-8-sig")))
    ok = [r for r in rows if r["status"] == "ok"]
    err = [r for r in rows if r["status"] != "ok"]

    print(f"{len(rows)} rows: {len(ok)} ran, {len(err)} errored")
    if err:
        jobs = sorted({r["job_number"] for r in err})
        print(f"  errored jobs: {len(jobs)} ({', '.join(jobs[:12])}{'...' if len(jobs) > 12 else ''})")
        print(f"  reason: {err[0].get('error','')[:120]}")

    headline = [r for r in ok if is_headline(r)]
    incomplete_cov = [r for r in rows if (r.get("missing_required") or "").strip()]
    not_stated = [
        r for r in ok
        if not (r.get("missing_required") or "").strip()
        and (r.get("truth_utility_data_completeness") or "").strip() == "not_stated"
    ]

    print(f"\nHEADLINE = empty missing_required AND whole_property_full_year")
    print(f"  headline ok rows: {len(headline)}  "
          f"({len({r['job_number'] for r in headline})} jobs)")
    print(f"  rows with missing_required (coverage/error, not headline): {len(incomplete_cov)}")
    print(f"  ok not_stated with required fields (coverage, not headline): {len(not_stated)}")

    variant_table(headline, "HEADLINE site EUI % error")
    if not_stated:
        variant_table(not_stated, "not_stated (required present) — coverage, not headline")
    if err:
        print(f"\nincomplete / validation errors: {len(err)} rows "
              f"({len({r['job_number'] for r in err})} jobs) — not in headline median")

    # Per-project, comparing the tiers that actually measure prediction.
    by_job: dict[str, dict] = {}
    for r in headline:
        by_job.setdefault(r["job_number"], {})[r["variant"]] = r
    worse = better = 0
    n_compare = 0
    for job in sorted(by_job):
        v = by_job[job]
        if not all(k in v for k in ("required_only", "advanced")):
            continue
        req = f(v["required_only"]["site_eui_pct_error"])
        adv = f(v["advanced"]["site_eui_pct_error"])
        if req is None or adv is None:
            continue
        n_compare += 1
        delta = abs(adv) - abs(req)
        worse += delta > 0.5
        better += delta < -0.5

    print(f"\nheadline advanced vs required-only: worse on {worse}, better on {better} "
          f"(n={n_compare} jobs)")

    if len(by_job) <= 40:
        print(f"\n{'job':8} {'property':26} {'req':>8} {'basics':>8} {'adv':>8}  advanced vs required")
        print("-" * 82)
        for job in sorted(by_job):
            v = by_job[job]
            if not all(k in v for k in ("required_only", "advanced")):
                continue
            req = f(v["required_only"]["site_eui_pct_error"])
            bas = f(v.get("with_basics", {}).get("site_eui_pct_error"))
            adv = f(v["advanced"]["site_eui_pct_error"])
            if req is None or adv is None:
                continue
            delta = abs(adv) - abs(req)
            mark = "worse" if delta > 0.5 else ("better" if delta < -0.5 else "same")
            name = v["required_only"].get("property_name", "")[:26]
            print(f"{job:8} {name:26} {req:>7.1f}% "
                  f"{(f'{bas:.1f}%' if bas is not None else '-'):>8} {adv:>7.1f}%  "
                  f"{delta:+.1f} pts {mark}")

    per_fuel_report(headline)


def per_fuel_report(ok: list[dict]) -> None:
    """Accuracy split by fuel.

    The workbooks carry only electricity and natural gas, and across all 20
    golden projects those two reconstruct the delivered site EUI exactly -- so
    the truth-side fuel split is unambiguous and the comparison is like-for-like.

    Percent error is reported for both fuels, but absolute kBtu/sf is the
    honest number for gas: several buildings sit near 9 kBtu/sf of gas, where a
    5-point absolute miss reads as a 50%+ error and swamps the median. Both are
    shown so neither framing stands alone.
    """
    print("\n" + "=" * 92)
    print("PER-FUEL SITE EUI  (kBtu/sf)")
    print("=" * 92)

    FUELS = (
        ("electricity", "elec_eui_pct_error", "elec_eui_abs_error_kbtu_sf",
         "pred_elec_eui_kbtu_sf", "truth_elec_eui_kbtu_sf"),
        ("natural gas", "gas_eui_pct_error", "gas_eui_abs_error_kbtu_sf",
         "pred_gas_eui_kbtu_sf", "truth_gas_eui_kbtu_sf"),
    )

    for v in ORDER:
        if v == "with_utility":
            continue  # calibrated: reproduces the supplied fuels by construction
        rows = [r for r in ok if r["variant"] == v]
        if not rows:
            continue
        print("\n" + v)
        print(f"  {'fuel':13} {'n':>3} {'med %':>8} {'med|%|':>8} {'med abs':>9} "
              f"{'med pred':>9} {'med truth':>9} {'under':>8}")
        for fuel, pc, ac, pk, tk in FUELS:
            pv = [f(r.get(pc)) for r in rows]
            pv = [x for x in pv if x is not None]
            av = [f(r.get(ac)) for r in rows]
            av = [x for x in av if x is not None]
            pkv = [f(r.get(pk)) for r in rows]
            pkv = [x for x in pkv if x is not None]
            tkv = [f(r.get(tk)) for r in rows]
            tkv = [x for x in tkv if x is not None]
            if not pv:
                continue
            print(f"  {fuel:13} {len(pv):>3} {st.median(pv):>7.1f}% "
                  f"{st.median([abs(x) for x in pv]):>7.1f}% "
                  f"{st.median(av):>+9.2f} {st.median(pkv):>9.2f} "
                  f"{st.median(tkv):>9.2f} {sum(1 for x in pv if x < 0):>5}/{len(pv)}")

        # Fuel mix on its own terms: a building can have the right total and
        # still be predicted as the wrong kind of building.
        sh = [f(r.get("gas_share_error_pts")) for r in rows]
        sh = [x for x in sh if x is not None]
        if sh:
            print(f"  {'gas share':13} {len(sh):>3} median {st.median(sh):>+6.1f} pts, "
                  f"median abs {st.median([abs(x) for x in sh]):>5.1f} pts, "
                  f"range {min(sh):+.1f} .. {max(sh):+.1f}")

        # Fuels none of these buildings actually burn.
        oth = [f(r.get("pred_other_eui_kbtu_sf")) or 0.0 for r in rows]
        nz = [x for x in oth if x > 0.05]
        if nz:
            print(f"  {'other fuels':13} {len(nz):>3} rows predict non-zero fuel oil / "
                  f"propane / district (max {max(nz):.2f}); no golden project burns these")

    # Per-project detail on the tier with the fewest confounds.
    base = [r for r in ok if r["variant"] == "required_only"]
    if not base or len(base) > 40:
        return
    print(f"\n{'job':8} {'property':24} {'e pred':>8} {'e true':>7} {'e err':>7}  "
          f"{'g pred':>8} {'g true':>7} {'g err':>7}  {'share':>7}")
    print("-" * 92)
    for r in sorted(base, key=lambda x: x["job_number"]):
        def g(k, w=7, d=2, suf=""):
            x = f(r.get(k))
            return (f"{x:>{w}.{d}f}" if x is not None else f"{'-':>{w}}") + suf
        print(f"{r['job_number']:8} {r.get('property_name', '')[:24]:24} "
              f"{g('pred_elec_eui_kbtu_sf', 8)} {g('truth_elec_eui_kbtu_sf')} "
              f"{g('elec_eui_pct_error', 6, 1, '%')}  "
              f"{g('pred_gas_eui_kbtu_sf', 8)} {g('truth_gas_eui_kbtu_sf')} "
              f"{g('gas_eui_pct_error', 6, 1, '%')}  {g('gas_share_error_pts', 7, 1)}")


if __name__ == "__main__":
    main()
