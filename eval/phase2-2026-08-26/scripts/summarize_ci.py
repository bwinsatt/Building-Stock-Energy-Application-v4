"""
Summarize C&I phase 2 output, split by utility_data_completeness.

    python testcases/commercial_industrial/summarize_results.py

Headline default is whole_property_full_year only. Owner-paid full year is a
separate qualified table. unverified_narrative_pending is unknown, not a pass.
Never pool completeness classes. with_utility is calibration, not accuracy.
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_IN = HERE.parent / "results" / "commercial_industrial" / "assessment_results.csv"

ORDER = ["required_only", "with_basics", "advanced", "with_utility"]

HEADLINE = "whole_property_full_year"
QUALIFIED = "owner_paid_full_year"
PENDING = "unverified_narrative_pending"

COMPLETENESS_ORDER = [
    "whole_property_full_year",
    "owner_paid_full_year",
    "whole_property_partial",
    "owner_paid_partial",
    "modelled_only",
    "unverified_narrative_pending",
]


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


def fuel_table(ok: list[dict], title: str) -> None:
    rows = [r for r in ok if r["variant"] != "with_utility"]
    if not rows:
        return
    print(f"\n{title}")
    print(f"  {'variant':16} {'fuel':12} {'n':>4} {'med %':>8} {'med|%|':>8} {'med abs':>9}")
    fuels = (
        ("electricity", "elec_eui_pct_error", "elec_eui_abs_error"),
        ("natural gas", "gas_eui_pct_error", "gas_eui_abs_error"),
    )
    for v in ORDER:
        if v == "with_utility":
            continue
        chunk = [r for r in rows if r["variant"] == v]
        for fuel, pc, ac in fuels:
            pv = [x for x in (f(r.get(pc)) for r in chunk) if x is not None]
            av = [x for x in (f(r.get(ac)) for r in chunk) if x is not None]
            if not pv:
                continue
            print(f"  {v:16} {fuel:12} {len(pv):>4} {st.median(pv):>7.1f}% "
                  f"{st.median([abs(x) for x in pv]):>7.1f}% "
                  f"{(st.median(av) if av else 0):>+9.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default=str(DEFAULT_IN))
    a = ap.parse_args()

    rows = list(csv.DictReader(Path(a.input).open(newline="", encoding="utf-8-sig")))
    ok = [r for r in rows if r["status"] == "ok"]
    err = [r for r in rows if r["status"] != "ok"]

    print(f"{len(rows)} rows: {len(ok)} ran, {len(err)} errored")
    if err:
        jobs = sorted({r["job"] for r in err})
        print(f"  errored jobs: {len(jobs)}")
        print(f"  reason: {err[0].get('error','')[:140]}")

    required_ok = [r for r in ok if not (r.get("missing_required") or "").strip()]
    missing = [r for r in rows if (r.get("missing_required") or "").strip()]
    print(f"  compile_log missing_required rows: {len(missing)} "
          f"({len({r['job'] for r in missing})} jobs)")

    by_c: dict[str, list[dict]] = {}
    for r in required_ok:
        by_c.setdefault(r.get("utility_data_completeness") or "(blank)", []).append(r)

    headline = by_c.get(HEADLINE, [])
    owner = by_c.get(QUALIFIED, [])
    pending = by_c.get(PENDING, [])

    print("\n=== HEADLINE: whole_property_full_year, required fields present ===")
    print(f"  n rows={len(headline)} jobs={len({r['job'] for r in headline})}")
    variant_table(headline, "site EUI % error (consumed truth_site_eui)")
    fuel_table(headline, "per-fuel vs truth_elec_eui / truth_gas_eui")

    print("\n=== QUALIFIED: owner_paid_full_year (do not pool with headline) ===")
    print(f"  n rows={len(owner)} jobs={len({r['job'] for r in owner})}")
    if owner:
        variant_table(owner, "owner-paid full year site EUI % error")

    print("\n=== UNKNOWN: unverified_narrative_pending (not a pass) ===")
    print(f"  n rows={len(pending)} jobs={len({r['job'] for r in pending})}")

    print("\n=== ALL completeness classes (required present; never pooled) ===")
    seen = set()
    for key in COMPLETENESS_ORDER + sorted(by_c):
        if key in seen or key not in by_c:
            continue
        seen.add(key)
        chunk = by_c[key]
        jobs = len({r["job"] for r in chunk})
        variant_table(chunk, f"{key}  ({len(chunk)} rows / {jobs} jobs)")

    if err:
        print(f"\nvalidation/runtime errors: {len(err)} rows "
              f"({len({r['job'] for r in err})} jobs) — excluded from accuracy tables")


if __name__ == "__main__":
    main()
