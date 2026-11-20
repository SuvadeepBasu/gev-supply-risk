-- Step 2c: what the delays do to production.
-- For every plant and material, simulate the next 60 days twice: with the
-- promised ETAs (baseline) and with the delayed ETAs (disrupted). Each day:
-- receive, then consume daily usage. Inventory cannot go below zero; usage
-- that cannot be met is lost production (lost-sales, not back-ordered).
-- The difference between the two runs is the impact of the disruption.
-- Losses are counted only up to the day the last delayed PO for that plant and
-- material arrives (the "evaluation window"). After that both runs have received
-- the same goods, so any later shortage comes from orders not yet placed, not
-- from the hazard. Without this cut-off, late gaps in the order book get netted
-- against the real loss and understate it.
CREATE OR REPLACE TABLE ${catalog}.gold.plant_material_impact AS
-- Losses below the new-shortage threshold are set to zero, so every total
-- matches whether it is filtered on has_new_shortage or on margin > 0.
SELECT * EXCEPT (incremental_lost_qty, production_days_lost, cases_at_risk, revenue_at_risk_usd, margin_at_risk_usd),
       CASE WHEN has_new_shortage THEN incremental_lost_qty ELSE 0D END AS incremental_lost_qty,
       CASE WHEN has_new_shortage THEN production_days_lost ELSE 0D END AS production_days_lost,
       CASE WHEN has_new_shortage THEN cases_at_risk        ELSE 0D END AS cases_at_risk,
       CASE WHEN has_new_shortage THEN revenue_at_risk_usd  ELSE 0D END AS revenue_at_risk_usd,
       CASE WHEN has_new_shortage THEN margin_at_risk_usd   ELSE 0D END AS margin_at_risk_usd
FROM (
WITH days AS (
  SELECT explode(sequence(0, 59)) AS d
),
rcv AS (
  SELECT plant_id, material_id, CAST(qty AS DOUBLE) AS qty,
         greatest(datediff(plant_eta_date, CAST('${as_of}' AS DATE)), 0) AS d_base,
         greatest(datediff(new_eta_date,   CAST('${as_of}' AS DATE)), 0) AS d_dis
  FROM ${catalog}.gold.po_delay
),
daily AS (
  SELECT i.plant_id, i.material_id, days.d,
         coalesce(sum(CASE WHEN r.d_base = days.d THEN r.qty END), 0D) AS rb,
         coalesce(sum(CASE WHEN r.d_dis  = days.d THEN r.qty END), 0D) AS rd
  FROM ${catalog}.ops.inventory i
  CROSS JOIN days
  LEFT JOIN rcv r ON r.plant_id = i.plant_id AND r.material_id = i.material_id
  GROUP BY i.plant_id, i.material_id, days.d
),
eval AS (
  SELECT plant_id, material_id,
         coalesce(max(CASE WHEN is_delayed THEN greatest(datediff(new_eta_date, CAST('${as_of}' AS DATE)), 0) END), 59) AS eval_day
  FROM ${catalog}.gold.po_delay
  GROUP BY plant_id, material_id
),
arrays AS (
  SELECT plant_id, material_id,
         transform(array_sort(collect_list(struct(d, rb))), x -> x.rb) AS rb_arr,
         transform(array_sort(collect_list(struct(d, rd))), x -> x.rd) AS rd_arr
  FROM daily
  GROUP BY plant_id, material_id
),
sim AS (
  SELECT
    i.plant_id, i.material_id,
    CAST(i.on_hand_qty AS DOUBLE) AS on_hand_qty, CAST(i.safety_stock_qty AS DOUBLE) AS safety_stock_qty,
    CAST(i.daily_usage_qty AS DOUBLE) AS daily_usage_qty,
    aggregate(a.rb_arr,
      named_struct('inv', CAST(i.on_hand_qty AS DOUBLE), 'lost', 0D, 'first_out', -1, 'day', 0),
      (acc, r) -> named_struct(
        'inv', greatest(acc.inv + r - i.daily_usage_qty, 0D),
        'lost', acc.lost + CASE WHEN acc.day <= coalesce(ev.eval_day, 59) THEN greatest(i.daily_usage_qty - (acc.inv + r), 0D) ELSE 0D END,
        'first_out', CASE WHEN acc.first_out < 0 AND acc.inv + r < i.daily_usage_qty THEN acc.day ELSE acc.first_out END,
        'day', acc.day + 1)) AS base_sim,
    aggregate(a.rd_arr,
      named_struct('inv', CAST(i.on_hand_qty AS DOUBLE), 'lost', 0D, 'first_out', -1, 'day', 0),
      (acc, r) -> named_struct(
        'inv', greatest(acc.inv + r - i.daily_usage_qty, 0D),
        'lost', acc.lost + CASE WHEN acc.day <= coalesce(ev.eval_day, 59) THEN greatest(i.daily_usage_qty - (acc.inv + r), 0D) ELSE 0D END,
        'first_out', CASE WHEN acc.first_out < 0 AND acc.inv + r < i.daily_usage_qty THEN acc.day ELSE acc.first_out END,
        'day', acc.day + 1)) AS dis_sim
  FROM ${catalog}.ops.inventory i
  JOIN arrays a ON a.plant_id = i.plant_id AND a.material_id = i.material_id
  LEFT JOIN eval ev ON ev.plant_id = i.plant_id AND ev.material_id = i.material_id
),
drivers AS (
  -- which hazards delayed the POs for this plant and material (for "because of the storm" questions)
  SELECT plant_id, material_id,
         concat_ws(', ', array_sort(array_distinct(flatten(collect_list(split(disruption_drivers, ', ')))))) AS caused_by
  FROM ${catalog}.gold.po_delay
  WHERE is_delayed
  GROUP BY plant_id, material_id
),
econ AS (
  -- revenue and margin lost per unit of this material, from the product lines that consume it
  SELECT plant_id, material_id,
         sum(cases_per_day * qty_per_case) AS planned_usage,
         sum(cases_per_day * net_revenue_per_case_usd) / sum(cases_per_day * qty_per_case) AS revenue_per_material_unit,
         sum(cases_per_day * margin_per_case_usd)      / sum(cases_per_day * qty_per_case) AS margin_per_material_unit,
         sum(cases_per_day) / sum(cases_per_day * qty_per_case)                            AS cases_per_material_unit,
         concat_ws(', ', array_sort(collect_set(product_line)))                             AS product_lines
  FROM ${catalog}.ref.plant_products
  GROUP BY plant_id, material_id
)
SELECT
  s.plant_id, pl.plant_name, s.material_id, m.material_name, m.uom, e.product_lines, dr.caused_by,
  s.on_hand_qty, s.safety_stock_qty, s.daily_usage_qty,
  round(s.on_hand_qty / s.daily_usage_qty, 1)                                    AS days_of_cover,
  CASE WHEN s.base_sim.first_out >= 0 THEN date_add(CAST('${as_of}' AS DATE), s.base_sim.first_out) END AS baseline_stockout_date,
  CASE WHEN s.dis_sim.first_out  >= 0 THEN date_add(CAST('${as_of}' AS DATE), s.dis_sim.first_out)  END AS disrupted_stockout_date,
  round(s.base_sim.lost, 0)                                                       AS baseline_lost_qty,
  round(s.dis_sim.lost, 0)                                                        AS disrupted_lost_qty,
  round(greatest(s.dis_sim.lost - s.base_sim.lost, 0D), 0)                        AS incremental_lost_qty,
  round(greatest(s.dis_sim.lost - s.base_sim.lost, 0D) / s.daily_usage_qty, 1)    AS production_days_lost,
  round(greatest(s.dis_sim.lost - s.base_sim.lost, 0D) * e.cases_per_material_unit, 0)   AS cases_at_risk,
  round(greatest(s.dis_sim.lost - s.base_sim.lost, 0D) * e.revenue_per_material_unit, 0) AS revenue_at_risk_usd,
  round(greatest(s.dis_sim.lost - s.base_sim.lost, 0D) * e.margin_per_material_unit, 0)  AS margin_at_risk_usd,
  -- material shortage of at least a tenth of a production day counts as a new shortage
  s.dis_sim.lost - s.base_sim.lost >= 0.1 * s.daily_usage_qty                     AS has_new_shortage,
  -- the date the plant runs out BECAUSE OF the hazards; empty when there is no new shortage
  CASE WHEN s.dis_sim.lost - s.base_sim.lost >= 0.1 * s.daily_usage_qty AND s.dis_sim.first_out >= 0
       THEN date_add(CAST('${as_of}' AS DATE), s.dis_sim.first_out) END        AS new_stockout_date
FROM sim s
JOIN econ e              ON e.plant_id = s.plant_id AND e.material_id = s.material_id
JOIN ${catalog}.ref.plants pl    ON pl.plant_id = s.plant_id
JOIN ${catalog}.ref.materials m  ON m.material_id = s.material_id
LEFT JOIN drivers dr             ON dr.plant_id = s.plant_id AND dr.material_id = s.material_id
);
