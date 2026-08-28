# Model eval ledger

Append-only notes from test-case scoring. Not a spec and not a license to ship a post-hoc clamp.

## 2026-08-27 — MF all-electric gas false positive (do not zero-out)

**Harvest:** freeze `2026-08-26`, Phase 2 `assessment_results.csv`.
**Set:** headline = required fields present and `whole_property_full_year`.

When `heating_fuel` and `dhw_fuel` are both `Electricity` (`with_basics` / `advanced`):

- **98 / 98** headline jobs still get predicted natural gas.
- Typical false gas is **~14 kBtu/sf** (with_basics median 13.6, range ~10–17; advanced median 11.9).
- Oil / propane / district is only a dusting (median `pred_other` 0.03, max 0.14 kBtu/sf). Not the issue.

**Do not fix with a conditional floor** (if both fuels electric → set gas EUI to 0). The ~14 kBtu/sf is inside the **total** site EUI, not a leftover bucket. Zeroing it would drop site EUI by ~14 kBtu/sf instead of moving that energy to electricity. That would look “all-electric” and be **more** wrong on total.

Needs a training / architecture change (fuel-conditional targets, hard constraint with reallocation, or a mix model), not an inference if-statement.

`required_only` does not send fuel fields, so inventing gas there is expected. `with_utility` zeros gas when billed therms are ~0; that is calibration, not fuel-input skill.

## 2026-08-27 — C&I Phase 2 (do not pool completeness)

**Harvest:** freeze `2026-08-26`, `eval/phase2-2026-08-26/results/commercial_industrial/assessment_results.csv`.
**Set:** required present and `whole_property_full_year` (130 jobs).

Site EUI required_only: median **−14.4%**, med |err| **44.8%** (28/130 within 20%). Extra fields shrink median bias (advanced −3.8%) but not typical |error|. Mean % is unusable (near-zero truth EUI, e.g. job 221288). Electricity med |%| ~40%; gas ~77–83%. Owner-paid full year (n=7) is a separate table (median ~+63%). Typical |error| is about twice the MF headline.

