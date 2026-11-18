"""Step 1 job: load the sample master data, POs, inventory and hazards.

Databricks: run as a Python script task with --catalog <name>.
Local:      python src/jobs/load_sample_data.py --local
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.sql_runner import run_sql_file  # noqa: E402
from common.spark import get_spark  # noqa: E402
from seed.sample_data import generate  # noqa: E402


def _py(v):
    """pandas/numpy scalars -> plain Python, NaN/NA -> None (so Spark infers clean types)."""
    import pandas as pd
    if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
        return None
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    return v


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="supply_risk_dev")
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--local", action="store_true")
    a = ap.parse_args(argv)
    spark = get_spark(a.local)
    run_sql_file(spark, "setup/00_schemas.sql", a.catalog, a.as_of, a.local)
    for name, pdf in generate(date.fromisoformat(a.as_of)).items():
        table = name if a.local else f"{a.catalog}.{name}"
        records = [{k: _py(v) for k, v in r.items()} for r in pdf.to_dict("records")]
        df = spark.createDataFrame(records)
        writer = df.write.mode("overwrite")
        if not a.local:
            writer = writer.option("overwriteSchema", "true")
        else:
            writer = writer.format("parquet")
        writer.saveAsTable(table)
        print(f"  loaded {table:32s} {len(pdf):5d} rows")
    if not a.local:
        run_sql_file(spark, "setup/90_comments.sql", a.catalog, a.as_of)


if __name__ == "__main__":
    main()
