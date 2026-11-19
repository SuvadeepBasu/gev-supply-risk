-- Step 4: trusted functions for the Genie space.
-- Add these to the space as "SQL functions" so Genie answers the core
-- procurement questions with vetted logic instead of writing it from scratch.

CREATE OR REPLACE FUNCTION ${catalog}.gold.fn_plant_disruption(p_plant_id STRING)
RETURNS TABLE (plant_id STRING, plant_name STRING, material_name STRING, product_lines STRING, caused_by STRING,
               days_of_cover DOUBLE, disrupted_stockout_date DATE, production_days_lost DOUBLE,
               cases_at_risk DOUBLE, revenue_at_risk_usd DOUBLE, margin_at_risk_usd DOUBLE)
COMMENT 'Materials at a plant whose delayed POs cause a new shortage, with the hazards that caused it (caused_by) and lost cases, revenue and margin. Pass NULL for all plants.'
RETURN
  SELECT plant_id, plant_name, material_name, product_lines, caused_by, days_of_cover, disrupted_stockout_date,
         production_days_lost, cases_at_risk, revenue_at_risk_usd, margin_at_risk_usd
  FROM ${catalog}.gold.plant_material_impact
  WHERE has_new_shortage AND (p_plant_id IS NULL OR plant_id = p_plant_id)
  ORDER BY margin_at_risk_usd DESC;

CREATE OR REPLACE FUNCTION ${catalog}.gold.fn_delayed_pos(p_event_name STRING)
RETURNS TABLE (po_id STRING, plant_name STRING, material_name STRING, supplier_name STRING, po_value_usd DOUBLE,
               plant_eta_date DATE, new_eta_date DATE, delay_days INT, disruption_drivers STRING,
               margin_at_risk_usd DOUBLE, recommended_action STRING, action_rationale STRING)
COMMENT 'Delayed PO lines with new ETA, margin at risk and the recommended action. Optionally filter to one hazard event name (partial match), or pass NULL.'
RETURN
  SELECT po_id, plant_name, material_name, supplier_name, po_value_usd, plant_eta_date, new_eta_date, delay_days,
         disruption_drivers, margin_at_risk_usd, recommended_action, action_rationale
  FROM ${catalog}.gold.po_actions
  WHERE p_event_name IS NULL OR lower(disruption_drivers) LIKE concat('%', lower(p_event_name), '%')
  ORDER BY margin_at_risk_usd DESC, delay_days DESC;

CREATE OR REPLACE FUNCTION ${catalog}.gold.fn_supplier_exposure(p_country STRING)
RETURNS TABLE (supplier_name STRING, country STRING, site_hazards STRING, open_po_lines BIGINT,
               delayed_po_lines BIGINT, delayed_po_value_usd DOUBLE, max_delay_days INT)
COMMENT 'Suppliers whose site sits inside an active hazard or whose POs are delayed. Optionally filter by country, or pass NULL.'
RETURN
  SELECT supplier_name, country, site_hazards, open_po_lines, delayed_po_lines, delayed_po_value_usd, max_delay_days
  FROM ${catalog}.gold.supplier_risk_summary
  WHERE (site_exposed OR delayed_po_lines > 0) AND (p_country IS NULL OR lower(country) = lower(p_country))
  ORDER BY delayed_po_value_usd DESC;
