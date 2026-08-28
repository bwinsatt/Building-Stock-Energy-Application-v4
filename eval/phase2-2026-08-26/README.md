# Phase 2 eval — 2026-08-26 harvest

Frozen compile CSVs plus in-process assessment scores. Local harvest work
lives in `testcases_raw/` and is gitignored.

## Headline definition

Accuracy tables use rows where **required fields are present** and
`utility_data_completeness` / `truth_utility_data_completeness` is
`whole_property_full_year`. Do not pool completeness classes. Owner-paid
full year is a separate, small set. `unverified_narrative_pending` is
unknown, not a pass. Quote **median** and **median |error|**; means explode
when truth EUI is near zero.

| Sector | Compiled jobs | Headline jobs | required_only median | required_only med \|err\| |
|---|---|---|---|---|
| Multifamily (ResStock) | 854 | 302 | −13.1% | 21.3% |
| C&I (ComStock) | 248 | 130 | −14.4% | 44.8% |

Interactive charts (open in a browser, File → Save if you need a copy):

- [charts/mf_eui_error_distribution.html](charts/mf_eui_error_distribution.html)
- [charts/ci_eui_error_distribution.html](charts/ci_eui_error_distribution.html) (property-type filter includes All)

## What to change in training

From [ledger.md](ledger.md) and the Phase 2 scores:

1. **All-electric MF still predicts ~14 kBtu/sf gas** when heating + DHW fuels
   are both `Electricity` (98/98 headline jobs). Do **not** zero gas at
   inference — that energy is inside total site EUI; clamping would drop total
   instead of reallocating to electricity. Needs a fuel-conditional target,
   mix model, or hard constraint **with reallocation**.
2. **Extra building fields do not help MF site EUI** (required_only is as
   good as advanced). They shrink C&I *bias* but not typical |error| (~45%).
3. **Gas mix is worse than electricity** on both sectors. Prefer kBtu/sf for
   gas; % error is unstable at low therms.
4. **C&I typical |error| is about 2× multifamily.** Watch Office vs Warehouse
   in the C&I chart; small types (n &lt; 8) are noisy.
5. MF `year_built` ranges (`1981 - 1982`) must be parsed or dropped before
   scoring. Puerto Rico zips (`006xx`) fail US zip lookup.

## Layout

```
freeze/multifamily|commercial_industrial/
  testcases.csv      inputs by variant (required_only / with_basics / advanced / with_utility)
  compile_log.csv    missing_required, compile status
  measures.csv       audit measures (not like-for-like with model catalog)
results/.../assessment_results.csv
scripts/             re-score and summarize against this freeze
```

Re-score after a new model bundle (one sector at a time):

```bash
python eval/phase2-2026-08-26/scripts/run_assessment_mf.py
python eval/phase2-2026-08-26/scripts/summarize_mf.py
python eval/phase2-2026-08-26/scripts/run_assessment_ci.py
python eval/phase2-2026-08-26/scripts/summarize_ci.py
```

Defaults read and write this snapshot. Pass `-o` to a new file if you must
not overwrite the Phase 2 baseline.
