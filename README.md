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
| 4 | Supply Risk Forecast assistant (Genie space): tables, instructions, trusted functions, sample questions, benchmarks | `src/genie/space_setup.md`, `src/sql/genie/` | configured, 87% benchmark |
| 5 | Bundle: setup job + 30-minute refresh job | `databricks.yml` | ready to deploy |
| 6 | Swap sample data for real POs, inventory, BOM, suppliers | `ops.*`, `ref.*` views | next |
| 7 | Databricks App: 2D map / 3D globe + Genie chat with charts + KPI strip | `app/`, `docs/deploy-app.md` | built, tested locally with mocked Genie |

## Quick start without the CLI (Free Edition, browser only)
1. Create a catalog in the SQL editor: `CREATE CATALOG IF NOT EXISTS supply_risk_dev;`
2. Pull this repo into a Databricks Git folder.
3. Open `notebooks/01_setup_and_run.py` and click **Run all** (serverless). It loads the sample data, runs the engine, creates the Genie functions and shows the KPIs.

## Deploy (Steps 1–5)
```bash
databricks auth login --host https://adb-<id>.<n>.azuredatabricks.net
# create the catalog once (or ask your admin): CREATE CATALOG supply_risk_dev;
databricks bundle deploy -t dev
databricks bundle run supply_risk_setup -t dev      # sample data + first engine run + Genie functions
databricks bundle run supply_risk_refresh -t dev    # pulls live USGS / GDACS hazards, recomputes
```
Then create the Supply Risk Forecast assistant (a Genie space) with `src/genie/space_setup.md`.

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

## Step I · The app (God's Eye View console)
`app/` is a Databricks App: animated 2D map / 3D globe of plants, suppliers, ports, lanes and live hazards,
a KPI strip, and a chat panel that asks the **Supply Risk Forecast** Genie agent. Answers come back as text plus an
automatic chart (bar, Pareto, pie, line or KPI tiles) and the places named in the answer light up on the map.

Deploy it with clicks only: see [docs/deploy-app.md](docs/deploy-app.md). Local test: `python tests/test_app.py`.
