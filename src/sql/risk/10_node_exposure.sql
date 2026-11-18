-- Step 2a: which suppliers and ports sit inside an active hazard.
-- A cyclone has one row per forecast point; a node is exposed if any point's
-- impact radius covers it. Severity = worst point that covers the node, and
-- the exposure window spans every covering point.
CREATE OR REPLACE TABLE ${catalog}.gold.node_exposure AS
WITH nodes AS (
  SELECT 'supplier' AS node_type, supplier_id AS node_id, supplier_name AS node_name, lat, lon
  FROM ${catalog}.ref.suppliers
  UNION ALL
  SELECT 'port', port_id, port_name, lat, lon
  FROM ${catalog}.ref.ports
),
active AS (
  SELECT *
  FROM ${catalog}.silver.hazard_events
  WHERE window_end >= date_sub(CAST('${as_of}' AS DATE), 1)
),
hits AS (
  SELECT
    n.node_type, n.node_id, n.node_name, n.lat AS node_lat, n.lon AS node_lon,
    e.event_id, e.event_name, e.hazard_type, e.severity, e.radius_km,
    e.window_start, e.window_end, e.source,
    2 * 6371 * asin(sqrt(
      pow(sin(radians(e.lat - n.lat) / 2), 2) +
      cos(radians(n.lat)) * cos(radians(e.lat)) * pow(sin(radians(e.lon - n.lon) / 2), 2)
    )) AS distance_km
  FROM nodes n
  CROSS JOIN active e
)
SELECT
  node_type, node_id, node_name, node_lat, node_lon,
  event_name, hazard_type, source,
  -- one exposure per node and named event (a cyclone's forecast points collapse into one)
  min(event_id)                AS event_id,
  max(severity)                AS severity,
  round(min(distance_km), 1)   AS distance_km,
  min(window_start)            AS window_start,
  max(window_end)              AS window_end
FROM hits
WHERE distance_km <= radius_km
  -- congestion is a port problem; it does not shut down a supplier that happens to be nearby
  AND NOT (hazard_type = 'port_congestion' AND node_type = 'supplier')
GROUP BY node_type, node_id, node_name, node_lat, node_lon, event_name, hazard_type, source;
