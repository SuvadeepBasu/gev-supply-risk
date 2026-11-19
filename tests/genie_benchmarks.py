"""Benchmark questions for the Supply Risk Forecast Genie space.

Each entry: question, ground-truth SQL (with ${catalog}), and what the answer
should show. Running this file executes every SQL locally on the sample data,
prints the results, and rewrites src/genie/benchmarks.md.
"""
BENCHMARKS = [
 ("Totals", "What is the total margin at risk?",
  "SELECT as_of_date, margin_at_risk_usd FROM ${catalog}.gold.risk_kpis"),
 ("Totals", "How many open PO lines are delayed, and what is their value?",
  "SELECT delayed_po_lines, open_po_lines, delayed_po_value_usd FROM ${catalog}.gold.risk_kpis"),
 ("Totals", "What is the average delay of the delayed POs in days?",
  "SELECT avg_delay_days FROM ${catalog}.gold.risk_kpis"),
 ("Hazards", "Show margin at risk by hazard",
  "SELECT event_name, margin_at_risk_usd FROM ${catalog}.gold.event_impact ORDER BY margin_at_risk_usd DESC"),
 ("Hazards", "How many PO lines are delayed by the Chennai port congestion?",
  "SELECT po_lines_hit FROM ${catalog}.gold.event_impact WHERE event_name = 'Chennai port congestion'"),
 ("Hazards", "Which plants will run out of a material because of the storm, and when?",
  "SELECT plant_name, material_name, disrupted_stockout_date FROM ${catalog}.gold.plant_material_impact WHERE has_new_shortage AND caused_by LIKE '%Storm BOB-07%' ORDER BY disrupted_stockout_date"),
 ("Plants", "Which plant runs out first, and of what?",
  "SELECT plant_name, material_name, disrupted_stockout_date FROM ${catalog}.gold.plant_material_impact WHERE has_new_shortage ORDER BY disrupted_stockout_date, margin_at_risk_usd DESC LIMIT 1"),
 ("Plants", "What is the margin at risk at the Delhi plant?",
  "SELECT plant_name, margin_at_risk_usd FROM ${catalog}.gold.plant_risk_summary WHERE plant_id = 'PLT-DEL'"),
 ("Plants", "Which material contributes the most margin at risk across all plants?",
  "SELECT material_name, sum(margin_at_risk_usd) AS margin_at_risk_usd FROM ${catalog}.gold.plant_material_impact GROUP BY material_name ORDER BY margin_at_risk_usd DESC LIMIT 1"),
 ("Pareto", "Show a Pareto of margin at risk by plant and material",
  "SELECT plant_name, material_name, margin_at_risk_usd, round(100 * sum(margin_at_risk_usd) OVER (ORDER BY margin_at_risk_usd DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / sum(margin_at_risk_usd) OVER (), 1) AS cumulative_pct FROM ${catalog}.gold.plant_material_impact WHERE has_new_shortage ORDER BY margin_at_risk_usd DESC"),
 ("Actions", "What should procurement do about the delayed POs, and what does it cost?",
  "SELECT recommended_action, count(*) AS po_lines, sum(action_cost_usd) AS action_cost_usd, sum(margin_protected_usd) AS margin_protected_usd FROM ${catalog}.gold.po_actions GROUP BY recommended_action ORDER BY margin_protected_usd DESC"),
 ("Actions", "Show delayed POs for the Kolkata plant with the recommended action",
  "SELECT po_id, material_name, supplier_name, delay_days, recommended_action FROM ${catalog}.gold.po_actions WHERE plant_id = 'PLT-KOL' ORDER BY margin_at_risk_usd DESC"),
 ("Actions", "Which delayed POs need no action because stock covers the delay?",
  "SELECT po_id, plant_name, material_name, delay_days FROM ${catalog}.gold.po_actions WHERE recommended_action = 'No action' ORDER BY po_id"),
 ("Suppliers", "Which suppliers sit inside an active hazard?",
  "SELECT supplier_name, country, site_hazards FROM ${catalog}.gold.supplier_risk_summary WHERE site_exposed ORDER BY delayed_po_value_usd DESC"),
 ("Suppliers", "Which supplier has the most delayed PO value?",
  "SELECT supplier_name, delayed_po_value_usd FROM ${catalog}.gold.supplier_risk_summary ORDER BY delayed_po_value_usd DESC LIMIT 1"),
]

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_local_pipeline
    spark = run_local_pipeline.main()
    out = ["# Benchmarks for the Supply Risk Forecast Genie agent",
           "",
           "Add each question in the agent's **Benchmark** tab with its SQL as the ground-truth answer, then click **Run all**.",
           "Expected results below come from the sample data with as-of date 2026-11-18. If you rerun the setup with another date, the dates shift but the numbers stay the same.",
           ""]
    for i, (group, q, sql) in enumerate(BENCHMARKS, 1):
        df = spark.sql(sql.replace("${catalog}.", "")).toPandas()
        show = df.to_string(index=False, max_rows=8, float_format=lambda v: f"{v:,.1f}")
        print(f"\n[{i}] {q}\n{show}")
        out += [f"## {i}. {q}", f"*{group}*", "", "```sql", sql.replace("${catalog}", "supply_risk_dev"), "```", "",
                "Expected result:", "", "```", show, "```", ""]
    Path(__file__).resolve().parents[1].joinpath("src/genie/benchmarks.md").write_text("\n".join(out))
