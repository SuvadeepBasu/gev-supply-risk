"""Reads the engine's gold tables and shapes them for the map, the KPI strip and the side panel."""
from __future__ import annotations

import datetime as dt
import os
import time
from typing import Callable

from routes import lane_path

CATALOG = os.getenv("CATALOG", "supply_risk_dev")

QUERIES = {
    "kpi": "SELECT * FROM {c}.gold.risk_kpis",
    "plants": """SELECT p.plant_id AS id, p.city AS name, p.lat, p.lon, s.risk_level AS risk,
                        s.margin_at_risk_usd AS margin, s.earliest_new_stockout_date AS stockout
                 FROM {c}.ref.plants p JOIN {c}.gold.plant_risk_summary s ON s.plant_id = p.plant_id""",
    "suppliers": """SELECT supplier_id AS id, supplier_name AS name, lat, lon, site_exposed AS exposed,
                           delayed_po_lines AS delayed, site_hazards
                    FROM {c}.gold.supplier_risk_summary""",
    "ports": """SELECT p.port_id AS id, p.port_name AS name, p.lat, p.lon, x.node_id IS NOT NULL AS exposed
                FROM {c}.ref.ports p
                LEFT JOIN (SELECT DISTINCT node_id FROM {c}.gold.node_exposure WHERE node_type = 'port') x ON x.node_id = p.port_id""",
    "lanes": """SELECT l.lane_id AS id, l.supplier_id AS s, l.plant_id AS p, l.mode, l.origin_port_id AS op, l.dest_port_id AS dp,
                       max(CASE WHEN d.is_delayed THEN 1 ELSE 0 END) AS delayed, max(d.delay_days) AS delay
                FROM {c}.gold.po_delay d JOIN {c}.ref.lanes l ON l.lane_id = d.lane_id
                GROUP BY l.lane_id, l.supplier_id, l.plant_id, l.mode, l.origin_port_id, l.dest_port_id""",
    "hazards": """SELECT event_id, hazard_type, event_name, severity, lat, lon, radius_km, window_start
                  FROM {c}.silver.hazard_events
                  WHERE window_end >= date_sub((SELECT as_of_date FROM {c}.gold.risk_kpis), 1)
                  ORDER BY event_name, window_start, event_id""",
    "events": "SELECT * FROM {c}.gold.event_impact ORDER BY margin_at_risk_usd DESC, po_lines_hit DESC",
    "alts": """SELECT alt_supplier_id AS s, plant_id AS p FROM {c}.gold.po_actions
               WHERE recommended_action = 'Re-source' AND alt_supplier_id IS NOT NULL""",
}


def _clean(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    if isinstance(v, float):
        return round(v, 2)
    return v


def build_map_data(run: Callable[[str], list[dict]]) -> dict:
    """run(sql) returns rows as dicts. Works with the SQL warehouse or with local Spark in tests."""
    q = {k: [{a: _clean(b) for a, b in r.items()} for r in run(v.format(c=CATALOG))] for k, v in QUERIES.items()}
    sup = {s["id"]: s for s in q["suppliers"]}
    pl = {p["id"]: p for p in q["plants"]}
    po = {p["id"]: p for p in q["ports"]}
    lanes = []
    for l in q["lanes"]:
        if l["s"] in sup and l["p"] in pl:
            lanes.append({"id": l["id"], "s": l["s"], "p": l["p"], "mode": l["mode"], "delayed": bool(int(l["delayed"] or 0)),
                          "delay": int(l["delay"] or 0), "path": lane_path(l, sup, pl, po)})
    as_of = dt.date.fromisoformat(str(q["kpi"][0]["as_of_date"])[:10]) if q["kpi"] else dt.date.today()
    cyclones, quakes, congestion = {}, [], []
    for h in q["hazards"]:
        if h["hazard_type"] == "cyclone":
            hours = (dt.date.fromisoformat(str(h["window_start"])[:10]) - as_of).days * 24
            cyclones.setdefault(h["event_name"], []).append([h["lon"], h["lat"], h["radius_km"], h["severity"], hours])
        elif h["hazard_type"] == "earthquake":
            quakes.append({"name": h["event_name"], "lon": h["lon"], "lat": h["lat"], "radius": h["radius_km"], "mag": h["severity"]})
        elif h["hazard_type"] == "port_congestion":
            congestion.append({"name": h["event_name"], "lon": h["lon"], "lat": h["lat"], "hours": h["severity"]})
    return {
        "as_of": as_of.isoformat(),
        "kpi": q["kpi"][0] if q["kpi"] else {},
        "plants": q["plants"], "suppliers": q["suppliers"], "ports": q["ports"], "lanes": lanes,
        "cyclones": [{"name": n, "pts": sorted(p, key=lambda x: x[4])} for n, p in cyclones.items()],
        "quakes": quakes, "congestion": congestion,
        "events": q["events"], "alts": [[a["s"], a["p"]] for a in q["alts"] if a["s"] in sup and a["p"] in pl],
    }


class Cache:
    def __init__(self, ttl=60):
        self.ttl, self.value, self.at = ttl, None, 0.0

    def get(self, loader):
        if self.value is None or time.time() - self.at > self.ttl:
            self.value, self.at = loader(), time.time()
        return self.value
