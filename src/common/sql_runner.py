"""Run the project's .sql files on Databricks or on a local Spark session.

Files use two placeholders:
  ${catalog}  Unity Catalog name (e.g. supply_risk_dev)
  ${as_of}    snapshot date, YYYY-MM-DD

On Databricks every statement runs as written (tables are Delta by default).
Locally there is no Unity Catalog, so `${catalog}.` is dropped and
CREATE OR REPLACE TABLE becomes DROP + CREATE ... USING parquet.
"""
from __future__ import annotations

import re
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def _statements(text: str):
    text = re.sub(r"--[^\n]*", "", text)
    for stmt in text.split(";"):
        if stmt.strip():
            yield stmt.strip()


def render(text: str, catalog: str, as_of: str, local: bool) -> str:
    text = text.replace("${as_of}", as_of)
    return text.replace("${catalog}.", "") if local else text.replace("${catalog}", catalog)


def run_sql_file(spark, path: str | Path, catalog: str, as_of: str, local: bool = False, verbose: bool = True):
    path = Path(path)
    if not path.is_absolute():
        path = SQL_DIR / path
    for stmt in _statements(render(path.read_text(), catalog, as_of, local)):
        if local:
            m = re.match(r"CREATE\s+OR\s+REPLACE\s+TABLE\s+(\S+)\s+AS\s", stmt, re.I)
            if m:
                spark.sql(f"DROP TABLE IF EXISTS {m.group(1)}")
                stmt = re.sub(r"CREATE\s+OR\s+REPLACE\s+TABLE\s+(\S+)\s+AS\s", r"CREATE TABLE \1 USING parquet AS ", stmt, count=1, flags=re.I)
            stmt = re.sub(r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+(\S+).*", r"CREATE SCHEMA IF NOT EXISTS \1", stmt, flags=re.I | re.S)
        if verbose:
            first = stmt.splitlines()[0][:90]
            print(f"  [{path.name}] {first}")
        spark.sql(stmt)


RISK_FILES = [
    "risk/10_node_exposure.sql",
    "risk/20_po_delay.sql",
    "risk/30_inventory_impact.sql",
    "risk/40_po_actions.sql",
    "risk/50_kpis.sql",
]
