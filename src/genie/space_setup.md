# Genie space: Supply Risk (Step 4)

Create it in the workspace UI (Genie → New), then paste the pieces below.

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
- "Stockout date" = disrupted_stockout_date in gold.plant_material_impact.
- PO value is what we pay the supplier; margin at risk is what we lose in sales. Do not add them together.
- Recommended actions: Re-source (buy from an approved alternate), Expedite (faster freight), Monitor (hurts but no option pays back), No action (stock covers the delay).

Rules
- Money is USD. Round to whole dollars and show thousands separators.
- When asked "why", use disruption_drivers and disrupted_stages, and gold.po_milestone_exposure for the stage-level detail.
- For plant questions prefer gold.fn_plant_disruption; for PO lists prefer gold.fn_delayed_pos; for supplier questions prefer gold.fn_supplier_exposure.
- If the user names a city, match it to ref.plants.city or ref.suppliers.city.
- Always state the as_of_date from gold.risk_kpis when giving totals.
```

## 3. Sample questions
- What is the total margin at risk this week, and which hazard drives most of it?
- Which plants will run out of a material because of the cyclone, and when?
- Show delayed POs for Kolkata with the recommended action.
- Which suppliers are inside an active hazard right now?
- How much would re-sourcing cost versus the margin it protects?
- Which delayed POs need no action because stock covers the delay?

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

## 5. Benchmarks
Use the sample questions above as benchmark questions, with the example SQL as the expected answers, and re-run them after any change to instructions or tables.
