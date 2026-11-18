"""Step 2 job: recompute exposure, delays, production impact, actions and KPIs.

Databricks: Python script task, --catalog <name> [--as-of YYYY-MM-DD]
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.spark import get_spark  # noqa: E402
from common.sql_runner import RISK_FILES, run_sql_file  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="supply_risk_dev")
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--with-genie-functions", action="store_true")
    a = ap.parse_args(argv)
    spark = get_spark()
    for f in RISK_FILES:
        run_sql_file(spark, f, a.catalog, a.as_of)
    if a.with_genie_functions:
        run_sql_file(spark, "genie/60_genie_functions.sql", a.catalog, a.as_of)
    k = spark.table(f"{a.catalog}.gold.risk_kpis").first()
    print(f"as of {k.as_of_date}: {k.delayed_po_lines}/{k.open_po_lines} PO lines delayed, "
          f"margin at risk ${k.margin_at_risk_usd:,.0f}, protected by actions ${k.margin_protected_usd:,.0f}")


if __name__ == "__main__":
    main()
