-- Table and column comments. Genie reads these, so keep them business-friendly.
COMMENT ON TABLE ${catalog}.ref.plants IS 'Manufacturing plants. import_port_id is the sea port used for imported materials.';
COMMENT ON TABLE ${catalog}.ref.suppliers IS 'Approved suppliers with location. sourcing = domestic or international.';
COMMENT ON TABLE ${catalog}.ref.materials IS 'Raw and packaging materials bought for manufacturing, with standard unit cost in USD.';
COMMENT ON TABLE ${catalog}.ref.lanes IS 'Supplier-to-plant routes. mode = road or sea, and sea lanes pass an origin and a destination port. transit_days is door to door.';
COMMENT ON TABLE ${catalog}.ref.supplier_materials IS 'Approved source list per plant and material. is_primary marks the default supplier and price_premium_pct is the extra cost of using an alternate.';
COMMENT ON TABLE ${catalog}.ref.plant_products IS 'Which materials each product line consumes per case, planned cases per day, and revenue and margin per case.';
COMMENT ON TABLE ${catalog}.ref.delay_rules IS 'Delay in days a hazard adds at a supplier or port, by hazard type and severity band. Port congestion delay = ceil(wait hours / 24).';
COMMENT ON TABLE ${catalog}.ref.expedite_rules IS 'Expedite option per transport mode and its cost as a share of PO value.';
COMMENT ON TABLE ${catalog}.ops.purchase_orders IS 'Open purchase order lines. status OPEN = not yet shipped, IN_TRANSIT = shipped. plant_eta_date is the promised arrival at the plant.';
COMMENT ON TABLE ${catalog}.ops.inventory IS 'Inventory snapshot per plant and material: on hand, safety stock and average daily usage.';
COMMENT ON TABLE ${catalog}.silver.hazard_events IS 'Active hazards: cyclones (severity = category, one row per forecast point), earthquakes (severity = magnitude), port congestion (severity = average wait hours). radius_km is the impact radius.';
