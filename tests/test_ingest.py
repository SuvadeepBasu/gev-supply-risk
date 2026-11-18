"""Parser tests for the hazard feeds, using payloads shaped like the published formats."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ingest.hazards import parse_gdacs_event_list, parse_gdacs_track, parse_usgs, quake_radius_km  # noqa: E402

NOW = datetime(2026, 11, 18, 6, 0)

usgs = {"type": "FeatureCollection", "features": [
    {"id": "us7000abcd", "type": "Feature", "properties": {"mag": 5.6, "place": "45 km NW of Mandalay, Myanmar", "time": 1794873600000},
     "geometry": {"type": "Point", "coordinates": [95.9, 21.2, 10.0]}},
    {"id": "us7000small", "type": "Feature", "properties": {"mag": 4.6, "place": "small one", "time": 1794873600000},
     "geometry": {"type": "Point", "coordinates": [10, 10, 5]}},
]}
rows = parse_usgs(usgs, NOW)
assert len(rows) == 1, rows
r = rows[0]
assert (r["lat"], r["lon"]) == (21.2, 95.9), "GeoJSON is lon,lat order"
assert r["severity"] == 5.6 and r["hazard_type"] == "earthquake"
assert r["radius_km"] == quake_radius_km(5.6) == 212
assert str(r["window_start"]) == "2026-11-17"

gdacs_list = {"features": [{"geometry": {"type": "Point", "coordinates": [87.6, 10.8]},
               "properties": {"eventid": 1001350, "episodeid": 7, "name": "BOB-07", "fromdate": "2026-11-16T00:00:00",
                              "todate": "2026-11-21T00:00:00", "iscurrent": "true", "severitydata": {"severity": 185.2}}}]}
ev = parse_gdacs_event_list(gdacs_list)[0]
assert ev["eventid"] == 1001350 and ev["wind_kmh"] == 185.2
geom = {"features": [
    {"geometry": {"type": "Point", "coordinates": [87.0, 13.4]}, "properties": {"trackdate": "2026-11-19T00:00:00", "windspeed": 190}},
    {"geometry": {"type": "Point", "coordinates": [87.3, 21.0]}, "properties": {"trackdate": "2026-11-22T00:00:00", "windspeed": 140}},
    {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}, "properties": {}},
]}
t = parse_gdacs_track(ev, geom, NOW)
assert [x["severity"] for x in t] == [3.0, 1.0], t
assert t[0]["lat"] == 13.4 and str(t[1]["window_start"]) == "2026-11-22"
fallback = parse_gdacs_track(ev, None, NOW)
assert len(fallback) == 1 and fallback[0]["lat"] == 10.8
print("ingest parser tests passed")
