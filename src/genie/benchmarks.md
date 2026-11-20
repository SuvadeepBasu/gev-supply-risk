# Benchmarks for the Supply Risk Forecast Genie agent

Add each question in the agent's **Benchmark** tab with its SQL as the ground-truth answer, then click **Run all**.
Expected results below come from the sample data with as-of date 2026-11-18. If you rerun the setup with another date, the dates shift but the numbers stay the same.

## 1. What is the total margin at risk?
*Totals*

```sql
SELECT as_of_date, margin_at_risk_usd FROM supply_risk_dev.gold.risk_kpis
```

Expected result:

```
as_of_date  margin_at_risk_usd
2026-11-18         1,163,072.0
```

## 2. How many open PO lines are delayed, and what is their value?
*Totals*

```sql
SELECT delayed_po_lines, open_po_lines, delayed_po_value_usd FROM supply_risk_dev.gold.risk_kpis
```

Expected result:

```
 delayed_po_lines  open_po_lines  delayed_po_value_usd
               18            308           1,717,237.0
```

## 3. What is the average delay of the delayed POs in days?
*Totals*

```sql
SELECT avg_delay_days FROM supply_risk_dev.gold.risk_kpis
```

Expected result:

```
 avg_delay_days
            4.6
```

## 4. Show margin at risk by hazard
*Hazards*

```sql
SELECT event_name, margin_at_risk_usd FROM supply_risk_dev.gold.event_impact ORDER BY margin_at_risk_usd DESC
```

Expected result:

```
             event_name  margin_at_risk_usd
           Storm BOB-07         1,143,038.0
Chennai port congestion            20,034.0
   M5.6 central Myanmar                 0.0
```

## 5. How many PO lines are delayed by the Chennai port congestion?
*Hazards*

```sql
SELECT po_lines_hit FROM supply_risk_dev.gold.event_impact WHERE event_name = 'Chennai port congestion'
```

Expected result:

```
 po_lines_hit
            4
```

## 6. Which plants will run out of a material because of the storm, and when?
*Hazards*

```sql
SELECT plant_name, material_name, new_stockout_date FROM supply_risk_dev.gold.plant_material_impact WHERE has_new_shortage AND caused_by LIKE '%Storm BOB-07%' ORDER BY new_stockout_date
```

Expected result:

```
                       plant_name     material_name new_stockout_date
  Kolkata beverage & snacks plant      PET preforms        2026-11-24
  Kolkata beverage & snacks plant Corrugate cartons        2026-11-25
       Bhubaneswar beverage plant    Aluminium cans        2026-11-25
Hyderabad snacks & beverage plant    Food-grade CO2        2026-11-25
                              ...               ...               ...
Hyderabad snacks & beverage plant          Potatoes        2026-11-29
Delhi NCR beverage & snacks plant Corrugate cartons        2026-11-30
       Bhubaneswar beverage plant             Sugar        2026-11-30
Delhi NCR beverage & snacks plant          Potatoes        2026-12-01
```

## 7. Which plant runs out first, and of what?
*Plants*

```sql
SELECT plant_name, material_name, new_stockout_date FROM supply_risk_dev.gold.plant_material_impact WHERE has_new_shortage ORDER BY new_stockout_date, margin_at_risk_usd DESC LIMIT 1
```

Expected result:

```
                     plant_name material_name new_stockout_date
Kolkata beverage & snacks plant  PET preforms        2026-11-24
```

## 8. What is the margin at risk at the Delhi plant?
*Plants*

```sql
SELECT plant_name, margin_at_risk_usd FROM supply_risk_dev.gold.plant_risk_summary WHERE plant_id = 'PLT-DEL'
```

Expected result:

```
                       plant_name  margin_at_risk_usd
Delhi NCR beverage & snacks plant           404,719.0
```

## 9. Which material contributes the most margin at risk across all plants?
*Plants*

```sql
SELECT material_name, sum(margin_at_risk_usd) AS margin_at_risk_usd FROM supply_risk_dev.gold.plant_material_impact GROUP BY material_name ORDER BY margin_at_risk_usd DESC LIMIT 1
```

Expected result:

```
    material_name  margin_at_risk_usd
Corrugate cartons           585,391.0
```

## 10. Show a Pareto of margin at risk by plant and material
*Pareto*

```sql
SELECT plant_name, material_name, margin_at_risk_usd, round(100 * sum(margin_at_risk_usd) OVER (ORDER BY margin_at_risk_usd DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / sum(margin_at_risk_usd) OVER (), 1) AS cumulative_pct FROM supply_risk_dev.gold.plant_material_impact WHERE has_new_shortage ORDER BY margin_at_risk_usd DESC
```

Expected result:

```
                       plant_name     material_name  margin_at_risk_usd  cumulative_pct
Delhi NCR beverage & snacks plant Corrugate cartons           359,185.0            30.9
  Kolkata beverage & snacks plant Corrugate cartons           215,865.0            49.5
       Bhubaneswar beverage plant            Labels           131,283.0            60.8
             Dhaka beverage plant      PET preforms           111,045.0            70.3
                              ...               ...                 ...             ...
       Bhubaneswar beverage plant             Sugar            35,033.0            97.2
       Bhubaneswar beverage plant      PET preforms            13,040.0            98.3
           Chennai beverage plant Corrugate cartons            10,341.0            99.2
           Chennai beverage plant      PET preforms             9,693.0           100.0
```

## 11. What should procurement do about the delayed POs, and what does it cost?
*Actions*

```sql
SELECT recommended_action, count(*) AS po_lines, sum(action_cost_usd) AS action_cost_usd, sum(margin_protected_usd) AS margin_protected_usd FROM supply_risk_dev.gold.po_actions GROUP BY recommended_action ORDER BY margin_protected_usd DESC
```

Expected result:

```
recommended_action  po_lines  action_cost_usd  margin_protected_usd
         Re-source        11         57,486.0             946,813.0
          Expedite         1         32,510.0              53,091.0
         No action         4              0.0                   0.0
           Monitor         2              0.0                   0.0
```

## 12. Show delayed POs for the Kolkata plant with the recommended action
*Actions*

```sql
SELECT po_id, material_name, supplier_name, delay_days, recommended_action FROM supply_risk_dev.gold.po_actions WHERE plant_id = 'PLT-KOL' ORDER BY margin_at_risk_usd DESC
```

Expected result:

```
  po_id     material_name     supplier_name  delay_days recommended_action
PO-1202 Corrugate cartons Kalinga Packaging           7          Re-source
PO-1223      PET preforms   Haldia Polymers           4            Monitor
PO-1208    Laminated film   Haldia Polymers           4            Monitor
```

## 13. Which delayed POs need no action because stock covers the delay?
*Actions*

```sql
SELECT po_id, plant_name, material_name, delay_days FROM supply_risk_dev.gold.po_actions WHERE recommended_action = 'No action' ORDER BY po_id
```

Expected result:

```
  po_id             plant_name  material_name  delay_days
PO-1243 Chennai beverage plant Aluminium cans           2
PO-1254 Chennai beverage plant Food-grade CO2           2
PO-1270 Chennai beverage plant         Labels           3
PO-1290      Pune snacks plant Laminated film           3
```

## 14. Which suppliers sit inside an active hazard?
*Suppliers*

```sql
SELECT supplier_name, country, site_hazards FROM supply_risk_dev.gold.supplier_risk_summary WHERE site_exposed ORDER BY delayed_po_value_usd DESC
```

Expected result:

```
          supplier_name country         site_hazards
        Haldia Polymers   India         Storm BOB-07
   Bengal Agro Potatoes   India         Storm BOB-07
      Kalinga Packaging   India         Storm BOB-07
    Eastern Sugar Mills   India         Storm BOB-07
     Mandalay Packaging Myanmar M5.6 central Myanmar
Odisha Industrial Gases   India         Storm BOB-07
```

## 15. Which supplier has the most delayed PO value?
*Suppliers*

```sql
SELECT supplier_name, delayed_po_value_usd FROM supply_risk_dev.gold.supplier_risk_summary ORDER BY delayed_po_value_usd DESC LIMIT 1
```

Expected result:

```
  supplier_name  delayed_po_value_usd
Haldia Polymers             391,816.0
```
