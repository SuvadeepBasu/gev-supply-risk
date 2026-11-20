# Genie space: "Supply Risk Forecast" (Step 4)

Create it in the workspace UI (Genie → New), name it **Supply Risk Forecast**, then paste the pieces below.

## 1. Data
Warehouse: a Pro or Serverless SQL warehouse.

Add these tables (catalog = `supply_risk_dev` or your own):

| Table | Why Genie needs it |
|---|---|
| `gold.risk_kpis` | Headline numbers for "how bad is it" questions |
| `gold.po_actions` | Delayed PO lines with new ETA, margin at risk and recommended action |
| `gold.po_delay` | Every open PO line, delayed or not |
| `gold.plant_material_impact` | Stockout dates and lost cases / revenue / margin by plant and material |
| `gold.plant_risk_summary` | One row per plant with risk level |
| `gold.supplier_risk_summary` | One row per supplier with site hazards and delayed value |
| `gold.event_impact` | One row per hazard event with POs hit and margin at risk |
| `gold.po_milestone_exposure` | Which stage (supplier, origin port, destination port) each delay comes from |
| `ref.plants`, `ref.suppliers`, `ref.materials` | Names and locations |

SQL functions (from `src/sql/genie/60_genie_functions.sql`):
`gold.fn_plant_disruption`, `gold.fn_delayed_pos`, `gold.fn_supplier_exposure`.

## 2. General instructions (paste as-is)

```
You answer procurement and manufacturing questions about supply disruptions.

Definitions
- "Delayed PO" = a row in gold.po_delay where is_delayed = true. delay_days is the extra days added by hazards.
- "Margin at risk" / "revenue at risk" = production lost because a delayed PO arrives after the plant runs out of a material. Always use the *_at_risk_usd columns; never estimate from PO value.
- A plant "runs out" of a material only where gold.plant_material_impact.has_new_shortage = true. The "stockout date" is new_stockout_date. Never use disrupted_stockout_date IS NOT NULL to decide which plants run out: it also includes shortages that would happen anyway.
- PO value is what we pay the supplier; margin at risk is what we lose in sales. Do not add them together.
- Recommended actions: Re-source (buy from an approved alternate), Expedite (faster freight), Monitor (hurts but no option pays back), No action (stock covers the delay).

Rules
- Money is USD. Round to whole dollars and show thousands separators.
- When asked "why", use disruption_drivers and disrupted_stages, and gold.po_milestone_exposure for the stage-level detail.
- For plant questions prefer gold.fn_plant_disruption; for PO lists prefer gold.fn_delayed_pos; for supplier questions prefer gold.fn_supplier_exposure.
- If the user names a city, match it to ref.plants.city or ref.suppliers.city.
- If the user names a hazard ("storm", "cyclone", "BOB-07", "Chennai congestion", "port", "earthquake", "quake", "Myanmar"), filter gold.plant_material_impact on caused_by and gold.po_delay / gold.po_actions on disruption_drivers with LIKE, e.g. caused_by LIKE '%Storm BOB-07%'. Do not include shortages caused by other hazards.
- When a question asks for the single top, first, most, biggest or highest item, return only that one row (ORDER BY ... LIMIT 1) with just the name and the metric asked for.
- For headline totals (total margin at risk, number and value of delayed PO lines, open PO lines, average delay), read them directly from gold.risk_kpis instead of recomputing them.
- For "Pareto" questions, sort by margin_at_risk_usd descending and add a cumulative percentage column.
- Always state the as_of_date from gold.risk_kpis when giving totals.
```

## 3. Sample questions
- What is the total margin at risk this week, and which hazard drives most of it?
- Which plants will run out of a material because of the cyclone, and when?
- Show delayed POs for Kolkata with the recommended action.
- Which suppliers are inside an active hazard right now?
- How much would re-sourcing cost versus the margin it protects?
- Which delayed POs need no action because stock covers the delay?
- Which plant-materials make up 80% of the margin at risk? (Pareto)
- What share of delayed PO value does each hazard cause? (pie)

## 4. Example SQL (add as trusted queries)

**Margin at risk by hazard**
```sql
SELECT event_name, po_lines_hit, po_value_hit_usd, margin_at_risk_usd
FROM gold.event_impact ORDER BY margin_at_risk_usd DESC;
```

**Action plan with payback**
```sql
SELECT recommended_action, count(*) AS po_lines,
       sum(margin_at_risk_usd) AS margin_at_risk_usd,
       sum(action_cost_usd) AS action_cost_usd,
       sum(margin_protected_usd) - sum(action_cost_usd) AS net_benefit_usd
FROM gold.po_actions GROUP BY recommended_action ORDER BY margin_at_risk_usd DESC;
```

**Plants that stock out, earliest first**
```sql
SELECT plant_name, material_name, disrupted_stockout_date, production_days_lost, margin_at_risk_usd
FROM gold.plant_material_impact WHERE has_new_shortage ORDER BY disrupted_stockout_date;
```

**Pareto of margin at risk** (Genie draws this as a bar chart; ask for a combo chart with the cumulative share)
```sql
SELECT concat(plant_name, ' · ', material_name) AS item, margin_at_risk_usd,
       round(100 * sum(margin_at_risk_usd) OVER (ORDER BY margin_at_risk_usd DESC)
             / sum(margin_at_risk_usd) OVER (), 1) AS cumulative_pct
FROM gold.plant_material_impact WHERE has_new_shortage
ORDER BY margin_at_risk_usd DESC;
```

**Delayed PO value by hazard** (pie)
```sql
SELECT event_name, po_value_hit_usd, margin_at_risk_usd
FROM gold.event_impact ORDER BY po_value_hit_usd DESC;
```

## 5. Benchmarks
15 benchmark questions with ground-truth SQL and expected results are in [benchmarks.md](benchmarks.md).
Add them in the agent's **Benchmark** tab, run them, and re-run after any change to instructions or tables.
To regenerate the expected results: `python tests/genie_benchmarks.py`.
