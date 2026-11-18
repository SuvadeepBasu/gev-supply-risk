"""Run Step 1 + Step 2 end to end on a local Spark session and print the results.

    python tests/run_local_pipeline.py [--as-of 2026-11-18]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.spark import get_spark  # noqa: E402
from common.sql_runner import RISK_FILES, run_sql_file  # noqa: E402
from jobs import load_sample_data  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-11-18")
    a = ap.parse_args()
    import shutil
    shutil.rmtree("/tmp/supply-risk-warehouse", ignore_errors=True)
    spark = get_spark(local=True)
    spark.sparkContext.setLogLevel("ERROR")
    print("Step 1: sample data")
    load_sample_data.main(["--local", "--as-of", a.as_of])
    print("Step 2: risk engine")
    for f in RISK_FILES:
        run_sql_file(spark, f, "local", a.as_of, local=True)
    return spark


if __name__ == "__main__":
    s = main()
    import pandas as pd
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
    k = s.table("gold.risk_kpis").toPandas().T
    print("\nKPIs\n", k)
    print("\nEvents\n", s.table("gold.event_impact").toPandas())
    print("\nPlants\n", s.table("gold.plant_risk_summary").orderBy("margin_at_risk_usd", ascending=False).toPandas()[
        ["plant_id", "risk_level", "delayed_po_lines", "materials_with_new_shortage", "earliest_new_stockout_date",
         "cases_at_risk", "revenue_at_risk_usd", "margin_at_risk_usd"]])
    print("\nActions\n", s.sql("select recommended_action, count(*) n, round(sum(margin_at_risk_usd)) margin_at_risk, round(sum(action_cost_usd)) cost, round(sum(margin_protected_usd)) protected from gold.po_actions group by 1").toPandas())
