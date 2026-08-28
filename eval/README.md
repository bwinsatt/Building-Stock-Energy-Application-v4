# Held-out model eval

Partner-audit buildings scored against the production XGBoost pipeline.
Use this snapshot when retraining ComStock / ResStock models — not the local
`testcases_raw/` working tree (reports, LLM extract, unfrozen CSVs).

| Snapshot | What it is |
|---|---|
| [phase2-2026-08-26](phase2-2026-08-26/) | Harvest freeze + Phase 2 predictions vs consumed site EUI |

Do not mix multifamily (ResStock) and C&I (ComStock). Do not load two
ModelManagers at once. `with_utility` is calibration, not accuracy.
