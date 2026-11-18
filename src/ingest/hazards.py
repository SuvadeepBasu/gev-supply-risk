"""Step 3: land live hazard feeds into bronze and normalise them into silver.hazard_events.

Feeds (public, no key):
  USGS  earthquakes  https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson
  GDACS cyclones     https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=TC
                     + per-event geometry (forecast track points)
  Port congestion    no free source: drop a CSV (port_id, avg_wait_hours, as_of) in the
                     Volume /Volumes/<catalog>/ref/inputs/port_congestion.csv, or wire a
                     commercial AIS feed later.

Each run replaces that source's rows in silver.hazard_events (feeds are snapshots).
Sample rows (source = 'sample') are kept unless --drop-sample is passed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
GDACS_LIST_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=TC&fromDate={frm}&toDate={to}"
GDACS_GEOM_URL = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid={eid}&episodeid={ep}"

COLUMNS = ["event_id", "hazard_type", "event_name", "severity", "lat", "lon", "radius_km",
           "window_start", "window_end", "source", "ingested_at"]


def _get(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "supply-risk-ingest/1.0", "Accept": "application/json"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------- USGS ----------
def quake_radius_km(mag: float) -> float:
    """Impact radius used for supply exposure: ~160 km at M5, 250 km at M6, 350 km at M7."""
    return round(max(50.0, 60 + 95 * (mag - 4.0)), 0)


def parse_usgs(doc: dict, now: datetime) -> list[dict]:
    rows = []
    for f in doc.get("features", []):
        p, g = f.get("properties", {}), f.get("geometry", {})
        mag = p.get("mag")
        if mag is None or mag < 5.0 or not g or g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][0], g["coordinates"][1]  # GeoJSON order: lon, lat, depth
        t = datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc).date()  # epoch milliseconds
        rows.append(dict(
            event_id=f"USGS-{f.get('id')}", hazard_type="earthquake",
            event_name=f"M{mag:.1f} {p.get('place') or ''}".strip(), severity=float(mag),
            lat=float(lat), lon=float(lon), radius_km=quake_radius_km(mag),
            window_start=t, window_end=t + timedelta(days=10 if mag >= 6 else 5),
            source="usgs", ingested_at=now))
    return rows


# ---------- GDACS ----------
def wind_to_category(kmh: float) -> float:
    """Saffir-Simpson style bands; tropical storms are treated as category 1 for supply impact."""
    if kmh >= 178:
        return 3.0
    if kmh >= 154:
        return 2.0
    return 1.0


def cyclone_radius_km(cat: float) -> float:
    return {1.0: 180.0, 2.0: 240.0, 3.0: 300.0}.get(cat, 180.0)


def _date(v) -> date | None:
    if not v:
        return None
    s = str(v)[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def parse_gdacs_event_list(doc: dict) -> list[dict]:
    out = []
    for f in doc.get("features", []):
        p = f.get("properties", {})
        sev = p.get("severitydata") or {}
        out.append(dict(eventid=p.get("eventid"), episodeid=p.get("episodeid"), name=p.get("name") or p.get("eventname"),
                        fromdate=_date(p.get("fromdate")), todate=_date(p.get("todate")),
                        wind_kmh=float(sev.get("severity") or 0), iscurrent=str(p.get("iscurrent", "true")).lower() == "true",
                        centroid=(f.get("geometry") or {}).get("coordinates")))
    return out


def parse_gdacs_track(event: dict, geom: dict | None, now: datetime) -> list[dict]:
    """One row per forecast/track point. Falls back to the event centroid if no track is published."""
    pts = []
    for f in (geom or {}).get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        p = f.get("properties", {})
        d = _date(p.get("trackdate") or p.get("polygondate") or p.get("todate") or p.get("fromdate"))
        wind = float(p.get("windspeed") or p.get("wind_speed") or event["wind_kmh"] or 0)
        pts.append((g["coordinates"][1], g["coordinates"][0], d, wind))
    if not pts and event.get("centroid"):
        lon, lat = event["centroid"][0], event["centroid"][1]
        pts = [(lat, lon, event["todate"] or now.date(), event["wind_kmh"])]
    rows = []
    for i, (lat, lon, d, wind) in enumerate(pts):
        cat = wind_to_category(wind)
        d = d or event["fromdate"] or now.date()
        rows.append(dict(
            event_id=f"GDACS-TC-{event['eventid']}-{i}", hazard_type="cyclone",
            event_name=f"Cyclone {event['name']}", severity=cat, lat=float(lat), lon=float(lon),
            radius_km=cyclone_radius_km(cat), window_start=d, window_end=d + timedelta(days=2),
            source="gdacs", ingested_at=now))
    return rows


def fetch_gdacs(now: datetime) -> tuple[list[dict], list[dict]]:
    frm, to = (now.date() - timedelta(days=7)).isoformat(), (now.date() + timedelta(days=1)).isoformat()
    lst = _get(GDACS_LIST_URL.format(frm=frm, to=to))
    raw, rows = [lst], []
    for ev in parse_gdacs_event_list(lst):
        if not ev["iscurrent"]:
            continue
        geom = None
        try:
            geom = _get(GDACS_GEOM_URL.format(eid=ev["eventid"], ep=ev["episodeid"]))
            raw.append(geom)
        except Exception as e:  # geometry is optional; keep the centroid
            print(f"  GDACS geometry unavailable for {ev['eventid']}: {e}")
        rows += parse_gdacs_track(ev, geom, now)
    return raw, rows


# ---------- port congestion ----------
def read_port_congestion(spark, catalog: str, now: datetime) -> list[dict]:
    path = f"/Volumes/{catalog}/ref/inputs/port_congestion.csv"
    try:
        df = spark.read.option("header", True).option("inferSchema", True).csv(path)
    except Exception:
        print(f"  no port congestion file at {path}; skipping")
        return []
    ports = {r.port_id: r for r in spark.table(f"{catalog}.ref.ports").collect()}
    rows = []
    for r in df.collect():
        p = ports.get(r.port_id)
        if not p or float(r.avg_wait_hours) < 12:
            continue
        rows.append(dict(event_id=f"PC-{r.port_id}", hazard_type="port_congestion",
                         event_name=f"{p.port_name} port congestion", severity=float(r.avg_wait_hours),
                         lat=p.lat, lon=p.lon, radius_km=30.0, window_start=now.date(),
                         window_end=now.date() + timedelta(days=7), source="port_feed", ingested_at=now))
    return rows


def main(argv=None):
    from common.spark import get_spark
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="supply_risk_dev")
    ap.add_argument("--drop-sample", action="store_true")
    a = ap.parse_args(argv)
    spark = get_spark()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    usgs_doc = _get(USGS_URL)
    gdacs_raw, gdacs_rows = fetch_gdacs(now)
    rows = parse_usgs(usgs_doc, now) + gdacs_rows + read_port_congestion(spark, a.catalog, now)
    print(f"  usgs={sum(r['source'] == 'usgs' for r in rows)} gdacs={len(gdacs_rows)} total={len(rows)}")

    # bronze: raw payloads, append-only
    raw = [("usgs", json.dumps(usgs_doc), now)] + [("gdacs", json.dumps(d), now) for d in gdacs_raw]
    spark.createDataFrame(raw, "source string, payload string, ingested_at timestamp") \
        .write.mode("append").saveAsTable(f"{a.catalog}.bronze.hazard_feeds")

    # silver: replace this run's sources
    sources = ["usgs", "gdacs", "port_feed"] + (["sample"] if a.drop_sample else [])
    spark.sql(f"DELETE FROM {a.catalog}.silver.hazard_events WHERE source IN ({', '.join(repr(s) for s in sources)})")
    if rows:
        spark.createDataFrame([tuple(r[c] for c in COLUMNS) for r in rows],
                              spark.table(f"{a.catalog}.silver.hazard_events").select(*COLUMNS).schema) \
            .write.mode("append").saveAsTable(f"{a.catalog}.silver.hazard_events")


if __name__ == "__main__":
    main()
