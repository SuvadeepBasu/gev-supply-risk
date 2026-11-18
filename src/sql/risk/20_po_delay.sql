-- Step 2b: delay per open PO line.
-- Each PO passes up to three nodes on future dates: pickup at the supplier
-- (only if not yet shipped), the origin port and the destination port (sea
-- lanes). A node adds delay when its milestone date falls inside the hazard
-- window (+/- 1 day). Delays at successive nodes add up, capped at 21 days.
CREATE OR REPLACE TABLE ${catalog}.gold.po_milestone_exposure AS
WITH po AS (
  SELECT p.*, l.mode, l.origin_port_id, l.dest_port_id
  FROM ${catalog}.ops.purchase_orders p
  JOIN ${catalog}.ref.lanes l ON p.lane_id = l.lane_id
),
milestones AS (
  SELECT po_id, 'supplier' AS node_type, supplier_id AS node_id, ship_date AS milestone_date, 'Pickup at supplier' AS stage
  FROM po WHERE status = 'OPEN'
  UNION ALL
  SELECT po_id, 'port', origin_port_id, port_departure_date, 'Origin port'
  FROM po WHERE mode = 'sea' AND port_departure_date >= CAST('${as_of}' AS DATE)
  UNION ALL
  SELECT po_id, 'port', dest_port_id, port_arrival_date, 'Destination port'
  FROM po WHERE mode = 'sea' AND port_arrival_date >= CAST('${as_of}' AS DATE)
)
SELECT
  m.po_id, m.stage, m.node_type, m.node_id, x.node_name, m.milestone_date,
  x.event_id, x.event_name, x.hazard_type, x.severity, x.distance_km,
  CAST(coalesce(r.delay_days, ceil(x.severity / 24)) AS INT) AS delay_days,
  r.note AS delay_reason
FROM milestones m
JOIN ${catalog}.gold.node_exposure x
  ON  m.node_type = x.node_type
  AND m.node_id = x.node_id
  AND m.milestone_date BETWEEN date_sub(x.window_start, 1) AND date_add(x.window_end, 1)
JOIN ${catalog}.ref.delay_rules r
  ON  r.hazard_type = x.hazard_type
  AND r.node_type = m.node_type
  AND x.severity >= r.severity_min
  AND x.severity <  r.severity_max;

CREATE OR REPLACE TABLE ${catalog}.gold.po_delay AS
WITH agg AS (
  SELECT
    po_id,
    sum(delay_days)                                              AS raw_delay_days,
    sum(CASE WHEN node_type = 'supplier' THEN delay_days ELSE 0 END) AS supplier_delay_days,
    sum(CASE WHEN node_type = 'port' THEN delay_days ELSE 0 END)     AS port_delay_days,
    concat_ws(', ', array_sort(collect_set(event_name)))         AS disruption_drivers,
    concat_ws(', ', array_sort(collect_set(stage)))              AS disrupted_stages
  FROM ${catalog}.gold.po_milestone_exposure
  GROUP BY po_id
)
SELECT
  p.po_id, p.po_line, p.supplier_id, s.supplier_name, p.material_id, m.material_name,
  p.plant_id, pl.plant_name, p.lane_id, l.mode, p.status, p.qty, m.uom, p.po_value_usd,
  p.order_date, p.ship_date, p.plant_eta_date,
  CAST(least(coalesce(a.raw_delay_days, 0), 21) AS INT)  AS delay_days,
  CAST(coalesce(a.supplier_delay_days, 0) AS INT)        AS supplier_delay_days,
  CAST(coalesce(a.port_delay_days, 0) AS INT)            AS port_delay_days,
  date_add(p.plant_eta_date, CAST(least(coalesce(a.raw_delay_days, 0), 21) AS INT)) AS new_eta_date,
  coalesce(a.raw_delay_days, 0) > 0                      AS is_delayed,
  a.disruption_drivers, a.disrupted_stages
FROM ${catalog}.ops.purchase_orders p
JOIN ${catalog}.ref.lanes l      ON p.lane_id = l.lane_id
JOIN ${catalog}.ref.suppliers s  ON p.supplier_id = s.supplier_id
JOIN ${catalog}.ref.materials m  ON p.material_id = m.material_id
JOIN ${catalog}.ref.plants pl    ON p.plant_id = pl.plant_id
LEFT JOIN agg a                  ON p.po_id = a.po_id;
