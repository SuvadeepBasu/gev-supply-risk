-- Step 2e: rollups for Genie, the KPI strip and the globe.
CREATE OR REPLACE TABLE ${catalog}.gold.risk_kpis AS
SELECT
  CAST('${as_of}' AS DATE)                                                   AS as_of_date,
  count(*)                                                                   AS open_po_lines,
  round(sum(po_value_usd), 0)                                                AS open_po_value_usd,
  sum(CASE WHEN is_delayed THEN 1 ELSE 0 END)                                AS delayed_po_lines,
  round(sum(CASE WHEN is_delayed THEN po_value_usd ELSE 0 END), 0)           AS delayed_po_value_usd,
  round(100 * sum(CASE WHEN is_delayed THEN po_value_usd ELSE 0 END) / sum(po_value_usd), 1) AS pct_value_delayed,
  round(avg(CASE WHEN is_delayed THEN delay_days END), 1)                    AS avg_delay_days,
  max(delay_days)                                                            AS max_delay_days,
  (SELECT count(DISTINCT plant_id) FROM ${catalog}.gold.plant_material_impact WHERE has_new_shortage) AS plants_with_new_shortage,
  (SELECT count(*) FROM ${catalog}.gold.plant_material_impact WHERE has_new_shortage)                AS materials_with_new_shortage,
  (SELECT round(sum(cases_at_risk), 0) FROM ${catalog}.gold.plant_material_impact)                   AS cases_at_risk,
  (SELECT round(sum(revenue_at_risk_usd), 0) FROM ${catalog}.gold.plant_material_impact)             AS revenue_at_risk_usd,
  (SELECT round(sum(margin_at_risk_usd), 0) FROM ${catalog}.gold.plant_material_impact)              AS margin_at_risk_usd,
  (SELECT round(sum(action_cost_usd), 0) FROM ${catalog}.gold.po_actions)                            AS recommended_action_cost_usd,
  (SELECT round(sum(margin_protected_usd), 0) FROM ${catalog}.gold.po_actions)                       AS margin_protected_usd
FROM ${catalog}.gold.po_delay;

CREATE OR REPLACE TABLE ${catalog}.gold.plant_risk_summary AS
WITH delayed AS (
  SELECT plant_id, count(*) AS delayed_po_lines,
         round(sum(po_value_usd), 0) AS delayed_po_value_usd
  FROM ${catalog}.gold.po_delay WHERE is_delayed GROUP BY plant_id
),
impact AS (
  SELECT plant_id, plant_name,
         count(*)                                                     AS materials_tracked,
         sum(CASE WHEN has_new_shortage THEN 1 ELSE 0 END)            AS materials_with_new_shortage,
         min(CASE WHEN has_new_shortage THEN disrupted_stockout_date END) AS earliest_new_stockout_date,
         round(sum(production_days_lost), 1)                          AS material_production_days_lost,
         round(sum(cases_at_risk), 0)                                 AS cases_at_risk,
         round(sum(revenue_at_risk_usd), 0)                           AS revenue_at_risk_usd,
         round(sum(margin_at_risk_usd), 0)                            AS margin_at_risk_usd
  FROM ${catalog}.gold.plant_material_impact GROUP BY plant_id, plant_name
)
SELECT i.*, pl.lat, pl.lon,
       coalesce(d.delayed_po_lines, 0)     AS delayed_po_lines,
       coalesce(d.delayed_po_value_usd, 0) AS delayed_po_value_usd,
       CASE WHEN i.margin_at_risk_usd >= 50000 THEN 'High'
            WHEN i.margin_at_risk_usd > 0 THEN 'Medium'
            WHEN coalesce(d.delayed_po_lines, 0) > 0 THEN 'Low'
            ELSE 'None' END AS risk_level
FROM impact i
JOIN ${catalog}.ref.plants pl ON pl.plant_id = i.plant_id
LEFT JOIN delayed d ON d.plant_id = i.plant_id;

CREATE OR REPLACE TABLE ${catalog}.gold.supplier_risk_summary AS
WITH site AS (
  SELECT node_id AS supplier_id, concat_ws(', ', array_sort(collect_set(event_name))) AS site_hazards
  FROM ${catalog}.gold.node_exposure WHERE node_type = 'supplier' GROUP BY node_id
),
po AS (
  SELECT supplier_id,
         count(*)                                                      AS open_po_lines,
         sum(CASE WHEN is_delayed THEN 1 ELSE 0 END)                   AS delayed_po_lines,
         round(sum(CASE WHEN is_delayed THEN po_value_usd ELSE 0 END), 0) AS delayed_po_value_usd,
         max(delay_days)                                               AS max_delay_days,
         concat_ws(', ', array_sort(collect_set(disruption_drivers)))  AS disruption_drivers
  FROM ${catalog}.gold.po_delay GROUP BY supplier_id
)
SELECT s.supplier_id, s.supplier_name, s.country, s.lat, s.lon,
       coalesce(po.open_po_lines, 0) AS open_po_lines, coalesce(po.delayed_po_lines, 0) AS delayed_po_lines,
       coalesce(po.delayed_po_value_usd, 0) AS delayed_po_value_usd, coalesce(po.max_delay_days, 0) AS max_delay_days,
       po.disruption_drivers, site.site_hazards,
       site.site_hazards IS NOT NULL AS site_exposed
FROM ${catalog}.ref.suppliers s
LEFT JOIN po   ON po.supplier_id = s.supplier_id
LEFT JOIN site ON site.supplier_id = s.supplier_id;

CREATE OR REPLACE TABLE ${catalog}.gold.event_impact AS
WITH share AS (
  SELECT po_id, event_name, hazard_type, sum(delay_days) AS event_delay_days
  FROM ${catalog}.gold.po_milestone_exposure
  GROUP BY po_id, event_name, hazard_type
),
tot AS (
  SELECT po_id, sum(event_delay_days) AS all_delay_days FROM share GROUP BY po_id
),
nodes AS (
  SELECT event_name,
         sum(CASE WHEN node_type = 'supplier' THEN 1 ELSE 0 END) AS suppliers_exposed,
         sum(CASE WHEN node_type = 'port' THEN 1 ELSE 0 END)     AS ports_exposed
  FROM ${catalog}.gold.node_exposure GROUP BY event_name
),
po AS (
  SELECT s.event_name, s.hazard_type,
         count(DISTINCT s.po_id)                                                        AS po_lines_hit,
         round(sum(d.po_value_usd), 0)                                                  AS po_value_hit_usd,
         round(avg(s.event_delay_days), 1)                                              AS avg_delay_days_added,
         round(sum(coalesce(a.margin_at_risk_usd, 0)  * s.event_delay_days / t.all_delay_days), 0) AS margin_at_risk_usd,
         round(sum(coalesce(a.revenue_at_risk_usd, 0) * s.event_delay_days / t.all_delay_days), 0) AS revenue_at_risk_usd
  FROM share s
  JOIN tot t ON t.po_id = s.po_id
  JOIN ${catalog}.gold.po_delay d ON d.po_id = s.po_id
  LEFT JOIN ${catalog}.gold.po_actions a ON a.po_id = s.po_id
  GROUP BY s.event_name, s.hazard_type
)
SELECT n.event_name, coalesce(po.hazard_type, h.hazard_type) AS hazard_type,
       n.suppliers_exposed, n.ports_exposed,
       coalesce(po.po_lines_hit, 0) AS po_lines_hit, coalesce(po.po_value_hit_usd, 0) AS po_value_hit_usd,
       po.avg_delay_days_added,
       coalesce(po.margin_at_risk_usd, 0) AS margin_at_risk_usd, coalesce(po.revenue_at_risk_usd, 0) AS revenue_at_risk_usd
FROM nodes n
LEFT JOIN po ON po.event_name = n.event_name
LEFT JOIN (SELECT DISTINCT event_name, hazard_type FROM ${catalog}.gold.node_exposure) h ON h.event_name = n.event_name;
