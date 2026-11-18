-- Step 2d: recommended action per delayed PO.
-- Impact at a plant/material is shared across its delayed POs by delay x qty.
-- Options:
--   Expedite  : faster mode for the same PO. Recovers only port/transit delay,
--               not a supplier outage. Cost = premium % of PO value.
--   Re-source : an approved alternate supplier that is not exposed and can
--               deliver before the delayed ETA. Cost = its price premium.
-- The action with the best net benefit (margin protected - cost) wins;
-- otherwise Monitor (delay hurts but no option pays) or No action (stock covers it).
CREATE OR REPLACE TABLE ${catalog}.gold.po_actions AS
WITH delayed AS (
  SELECT d.*, d.delay_days * d.qty AS weight
  FROM ${catalog}.gold.po_delay d
  WHERE d.is_delayed
),
attributed AS (
  SELECT
    d.*,
    i.disrupted_stockout_date,
    coalesce(i.margin_at_risk_usd  * d.weight / sum(d.weight) OVER (PARTITION BY d.plant_id, d.material_id), 0) AS margin_at_risk_usd,
    coalesce(i.revenue_at_risk_usd * d.weight / sum(d.weight) OVER (PARTITION BY d.plant_id, d.material_id), 0) AS revenue_at_risk_usd,
    coalesce(i.cases_at_risk       * d.weight / sum(d.weight) OVER (PARTITION BY d.plant_id, d.material_id), 0) AS cases_at_risk
  FROM delayed d
  LEFT JOIN ${catalog}.gold.plant_material_impact i
    ON i.plant_id = d.plant_id AND i.material_id = d.material_id
),
exposed_suppliers AS (
  SELECT DISTINCT node_id AS supplier_id FROM ${catalog}.gold.node_exposure WHERE node_type = 'supplier'
),
exposed_ports AS (
  SELECT DISTINCT node_id AS port_id FROM ${catalog}.gold.node_exposure WHERE node_type = 'port'
),
alternates AS (
  SELECT a.po_id, sm.supplier_id AS alt_supplier_id, s.supplier_name AS alt_supplier_name,
         sm.lead_time_days AS alt_lead_time_days, sm.price_premium_pct AS alt_premium_pct,
         row_number() OVER (PARTITION BY a.po_id ORDER BY sm.lead_time_days, sm.price_premium_pct) AS rn
  FROM attributed a
  JOIN ${catalog}.ref.supplier_materials sm
    ON sm.material_id = a.material_id AND sm.plant_id = a.plant_id AND sm.supplier_id <> a.supplier_id
  JOIN ${catalog}.ref.suppliers s ON s.supplier_id = sm.supplier_id
  JOIN ${catalog}.ref.lanes l     ON l.supplier_id = sm.supplier_id AND l.plant_id = a.plant_id
  LEFT JOIN exposed_suppliers es  ON es.supplier_id = sm.supplier_id
  LEFT JOIN exposed_ports op      ON op.port_id = l.origin_port_id
  LEFT JOIN exposed_ports dp      ON dp.port_id = l.dest_port_id
  WHERE es.supplier_id IS NULL AND op.port_id IS NULL AND dp.port_id IS NULL
    AND date_add(CAST('${as_of}' AS DATE), CAST(sm.lead_time_days AS INT)) < a.new_eta_date
),
options AS (
  SELECT
    a.*,
    x.expedite_option,
    round(a.po_value_usd * x.premium_pct_of_value, 0)                         AS expedite_cost_usd,
    round(a.margin_at_risk_usd * a.port_delay_days / greatest(a.delay_days, 1), 0) AS expedite_margin_protected_usd,
    alt.alt_supplier_id, alt.alt_supplier_name, alt.alt_lead_time_days,
    round(a.po_value_usd * alt.alt_premium_pct, 0)                            AS resource_cost_usd,
    round(a.margin_at_risk_usd * least(greatest(
      datediff(a.new_eta_date, date_add(CAST('${as_of}' AS DATE), CAST(alt.alt_lead_time_days AS INT))) / greatest(a.delay_days, 1), 0), 1), 0)
                                                                              AS resource_margin_protected_usd
  FROM attributed a
  JOIN ${catalog}.ref.expedite_rules x ON x.mode = a.mode
  LEFT JOIN alternates alt ON alt.po_id = a.po_id AND alt.rn = 1
),
scored AS (
  SELECT *,
    CASE WHEN expedite_margin_protected_usd > 0 THEN expedite_margin_protected_usd - expedite_cost_usd END AS expedite_net_usd,
    CASE WHEN alt_supplier_id IS NOT NULL AND resource_margin_protected_usd > 0 THEN resource_margin_protected_usd - resource_cost_usd END AS resource_net_usd
  FROM options
)
SELECT
  po_id, plant_id, plant_name, material_id, material_name, supplier_id, supplier_name, mode, status,
  qty, uom, po_value_usd, plant_eta_date, new_eta_date, delay_days, supplier_delay_days, port_delay_days,
  disruption_drivers, disrupted_stages, disrupted_stockout_date,
  round(cases_at_risk, 0) AS cases_at_risk, round(revenue_at_risk_usd, 0) AS revenue_at_risk_usd,
  round(margin_at_risk_usd, 0) AS margin_at_risk_usd,
  expedite_option, expedite_cost_usd, expedite_margin_protected_usd, expedite_net_usd,
  alt_supplier_id, alt_supplier_name, alt_lead_time_days, resource_cost_usd, resource_margin_protected_usd, resource_net_usd,
  CASE
    WHEN margin_at_risk_usd < 1 THEN 'No action'
    WHEN coalesce(resource_net_usd, -1) > 0 AND coalesce(resource_net_usd, -1) >= coalesce(expedite_net_usd, -1) THEN 'Re-source'
    WHEN coalesce(expedite_net_usd, -1) > 0 THEN 'Expedite'
    ELSE 'Monitor'
  END AS recommended_action,
  CASE
    WHEN margin_at_risk_usd < 1 THEN 'Stock on hand covers the delay.'
    WHEN coalesce(resource_net_usd, -1) > 0 AND coalesce(resource_net_usd, -1) >= coalesce(expedite_net_usd, -1)
      THEN concat('Order from ', alt_supplier_name, ' (', alt_lead_time_days, ' days lead time).')
    WHEN coalesce(expedite_net_usd, -1) > 0 THEN concat(expedite_option, ' recovers the port delay.')
    WHEN supplier_delay_days >= delay_days THEN 'Supplier outage: no faster route and no unexposed alternate in time.'
    ELSE 'No option pays back. Watch the hazard and stock.'
  END AS action_rationale,
  CASE
    WHEN margin_at_risk_usd < 1 THEN 0
    WHEN coalesce(resource_net_usd, -1) > 0 AND coalesce(resource_net_usd, -1) >= coalesce(expedite_net_usd, -1) THEN resource_cost_usd
    WHEN coalesce(expedite_net_usd, -1) > 0 THEN expedite_cost_usd
    ELSE 0
  END AS action_cost_usd,
  CASE
    WHEN margin_at_risk_usd < 1 THEN 0
    WHEN coalesce(resource_net_usd, -1) > 0 AND coalesce(resource_net_usd, -1) >= coalesce(expedite_net_usd, -1) THEN resource_margin_protected_usd
    WHEN coalesce(expedite_net_usd, -1) > 0 THEN expedite_margin_protected_usd
    ELSE 0
  END AS margin_protected_usd
FROM scored;
