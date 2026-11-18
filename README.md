# God's Eye View: supply risk on Databricks

Live hazards (cyclones, earthquakes, port congestion) → which suppliers and ports
are hit → how late each purchase order will be → which plants run out → cases,
revenue and margin at risk → what procurement should do about it. Genie answers
questions over the results; the Databricks App (next step) puts them on a globe.

All data in `src/seed/` is **sample data**. Replace it with your SAP / procurement
tables (Step 6).

## Build steps

| Step | What | Where | Status |
|---|---|---|---|
| 1 | Unity Catalog schemas, master data, open POs, inventory, sample hazards | `src/sql/setup/`, `src/seed/`, `src/jobs/load_sample_data.py` | done, tested locally |
| 2 | Disruption & delay engine: exposure → delay → shortage → $ at risk → actions → KPIs | `src/sql/risk/` | done, tested locally |
| 3 | Live hazard feeds: USGS quakes, GDACS cyclones, port congestion CSV | `src/ingest/hazards.py` | parsers tested; first live run on Databricks |
| 4 | Genie space: tables, instructions, trusted functions, sample questions | `src/genie/space_setup.md`, `src/sql/genie/` | ready to configure |
| 5 | Bundle: setup job + 30-minute refresh job | `databricks.yml` | ready to deploy |
| 6 | Swap sample data for real POs, inventory, BOM, suppliers | `ops.*`, `ref.*` views | next |
| 7 | Databricks App: Cesium globe + Genie chat + KPI strip | `app/` | next |

## Deploy (Steps 1–5)
```bash
databricks auth login --host https://adb-<id>.<n>.azuredatabricks.net
# create the catalog once (or ask your admin): CREATE CATALOG supply_risk_dev;
databricks bundle deploy -t dev
databricks bundle run supply_risk_setup -t dev      # sample data + first engine run + Genie functions
databricks bundle run supply_risk_refresh -t dev    # pulls live USGS / GDACS hazards, recomputes
```
Then create the Genie space with `src/genie/space_setup.md`.

## Run locally (no workspace needed)
```bash
pip install pyspark pandas pyarrow    # needs Java 17+
python tests/run_local_pipeline.py    # Steps 1-2 on local Spark, prints KPIs
python tests/test_engine.py           # checks SQL against an independent Python simulation
python tests/test_ingest.py           # hazard feed parsers
```

## Output tables (gold)
`risk_kpis`, `event_impact`, `plant_risk_summary`, `supplier_risk_summary`,
`plant_material_impact`, `po_actions`, `po_delay`, `po_milestone_exposure`, `node_exposure`.

How the numbers are calculated: [docs/delay-model.md](docs/delay-model.md).
