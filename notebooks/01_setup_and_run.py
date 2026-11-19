# Databricks notebook source
# MAGIC %md
# MAGIC # Step E · Set up the Supply Risk Forecast project
# MAGIC
# MAGIC This notebook does everything in one go. Click **Run all** at the top.
# MAGIC
# MAGIC 1. Creates the schemas `ref`, `ops`, `bronze`, `silver` and `gold` inside the catalog below.
# MAGIC 2. Loads the **sample data**: 7 plants, 23 suppliers, 12 materials, 308 open purchase orders, inventory, and 3 sample hazards.
# MAGIC 3. Runs the **risk engine**: which suppliers and ports are hit → how late each PO is → which plants run short → money at risk → recommended action.
# MAGIC 4. Creates the 3 trusted functions the Genie space will use.
# MAGIC 5. Shows the headline numbers.
# MAGIC
# MAGIC It takes about 3–5 minutes on serverless compute. Everything here is made-up sample data.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Settings
# MAGIC Leave these as they are unless you want a different catalog or snapshot date.

# COMMAND ----------

CATALOG = "supply_risk_dev"   # the catalog you created in Step D
AS_OF = "2026-11-18"          # snapshot date the sample data and engine run for

# COMMAND ----------

# MAGIC %md
# MAGIC ### Make the project code importable
# MAGIC The Python code lives in the `src` folder of this Git folder.

# COMMAND ----------

import os, sys
SRC = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
print("Project code folder:", SRC)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1–2 · Create schemas and load sample data

# COMMAND ----------

from jobs import load_sample_data
load_sample_data.main(["--catalog", CATALOG, "--as-of", AS_OF])

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3–4 · Run the risk engine and create the Genie functions

# COMMAND ----------

from jobs import run_risk_engine
run_risk_engine.main(["--catalog", CATALOG, "--as-of", AS_OF, "--with-genie-functions"])

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5 · Headline numbers
# MAGIC You should see 18 of 308 PO lines delayed, 6 plants with a new shortage, and about $1.16M margin at risk.

# COMMAND ----------

display(spark.table(f"{CATALOG}.gold.risk_kpis"))

# COMMAND ----------

display(spark.table(f"{CATALOG}.gold.event_impact"))

# COMMAND ----------

display(spark.sql(f"""
  SELECT recommended_action, count(*) AS po_lines,
         round(sum(margin_at_risk_usd)) AS margin_at_risk_usd,
         round(sum(action_cost_usd)) AS action_cost_usd,
         round(sum(margin_protected_usd)) AS margin_protected_usd
  FROM {CATALOG}.gold.po_actions
  GROUP BY recommended_action ORDER BY margin_at_risk_usd DESC"""))
