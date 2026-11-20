-- Descriptions on gold tables and columns. Genie reads these, so they must be
-- applied after the engine has rebuilt the tables (CREATE OR REPLACE drops them).
COMMENT ON TABLE ${catalog}.gold.plant_material_impact IS 'One row per plant and material: days of cover, stockout dates with promised vs delayed deliveries, production days, cases, revenue and margin lost. caused_by lists the hazards behind the delay. has_new_shortage marks shortages caused by hazards.';
ALTER TABLE ${catalog}.gold.plant_material_impact ALTER COLUMN has_new_shortage COMMENT 'TRUE only when hazard delays cause a shortage that would not happen with promised deliveries. Use this to answer "which plants run out".';
ALTER TABLE ${catalog}.gold.plant_material_impact ALTER COLUMN new_stockout_date COMMENT 'Date the plant runs out of this material because of hazard delays. NULL when there is no new shortage. Use this for "when does it run out" questions.';
ALTER TABLE ${catalog}.gold.plant_material_impact ALTER COLUMN disrupted_stockout_date COMMENT 'First day stock hits zero with delayed deliveries, including shortages that would happen anyway. Do not use alone to decide which plants run out: use new_stockout_date or has_new_shortage.';
ALTER TABLE ${catalog}.gold.plant_material_impact ALTER COLUMN baseline_stockout_date COMMENT 'First day stock hits zero with promised deliveries (no hazards).';
ALTER TABLE ${catalog}.gold.plant_material_impact ALTER COLUMN caused_by COMMENT 'Hazards that delayed POs for this plant and material, e.g. Storm BOB-07.';
ALTER TABLE ${catalog}.gold.plant_material_impact ALTER COLUMN margin_at_risk_usd COMMENT 'Margin lost because of hazard delays, in USD. Already zero when there is no new shortage.';
