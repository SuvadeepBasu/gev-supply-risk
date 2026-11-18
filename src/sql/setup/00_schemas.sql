-- Step 1: Unity Catalog layout. Run once per environment (dev / prod).
-- ref    = master data (plants, suppliers, materials, lanes, rules)
-- ops    = transactional procurement data (open POs, inventory)
-- bronze = raw hazard feeds, silver = normalised hazard events
-- gold   = engine outputs that Genie and the App read
CREATE SCHEMA IF NOT EXISTS ${catalog}.ref COMMENT 'Master data for supply-risk: plants, suppliers, materials, lanes and rules';
CREATE SCHEMA IF NOT EXISTS ${catalog}.ops COMMENT 'Procurement transactions: open purchase orders and inventory snapshots';
CREATE SCHEMA IF NOT EXISTS ${catalog}.bronze COMMENT 'Raw hazard feeds as received';
CREATE SCHEMA IF NOT EXISTS ${catalog}.silver COMMENT 'Normalised hazard events';
CREATE SCHEMA IF NOT EXISTS ${catalog}.gold COMMENT 'Disruption, delay and impact outputs for Genie and the app';
