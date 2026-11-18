"""Deterministic sample data for the supply-risk model.

Everything here is illustrative: the plants, suppliers, volumes and prices are
made up so the engine can be built and demoed before real SAP / procurement
data is connected. Swap each frame for a view over your own tables in Step 6.
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

import pandas as pd

SEED = 42

PLANTS = [
    # plant_id, name, city, country, lat, lon, nearest import port
    ("PLT-KOL", "Kolkata beverage & snacks plant", "Kolkata", "India", 22.57, 88.36, "PRT-HAL"),
    ("PLT-BBS", "Bhubaneswar beverage plant", "Bhubaneswar", "India", 20.30, 85.82, "PRT-PAR"),
    ("PLT-HYD", "Hyderabad snacks & beverage plant", "Hyderabad", "India", 17.39, 78.47, "PRT-VTZ"),
    ("PLT-MAA", "Chennai beverage plant", "Chennai", "India", 13.08, 80.27, "PRT-MAA"),
    ("PLT-PNQ", "Pune snacks plant", "Pune", "India", 18.52, 73.86, "PRT-JNP"),
    ("PLT-DEL", "Delhi NCR beverage & snacks plant", "Gurugram", "India", 28.46, 77.03, "PRT-MUN"),
    ("PLT-DAC", "Dhaka beverage plant", "Dhaka", "Bangladesh", 23.81, 90.41, "PRT-CGP"),
]

PORTS = [
    ("PRT-HAL", "Haldia", "India", 22.03, 88.10),
    ("PRT-PAR", "Paradip", "India", 20.26, 86.68),
    ("PRT-VTZ", "Visakhapatnam", "India", 17.69, 83.30),
    ("PRT-MAA", "Chennai", "India", 13.10, 80.30),
    ("PRT-JNP", "Nhava Sheva (JNPT)", "India", 18.95, 72.95),
    ("PRT-MUN", "Mundra", "India", 22.75, 69.70),
    ("PRT-CGP", "Chattogram", "Bangladesh", 22.33, 91.80),
    ("PRT-CMB", "Colombo", "Sri Lanka", 6.95, 79.85),
    ("PRT-RGN", "Yangon", "Myanmar", 16.77, 96.20),
    ("PRT-PKL", "Port Klang", "Malaysia", 3.00, 101.39),
    ("PRT-SIN", "Singapore", "Singapore", 1.26, 103.80),
    ("PRT-LCH", "Laem Chabang", "Thailand", 13.08, 100.88),
    ("PRT-SHA", "Shanghai", "China", 31.20, 121.50),
    ("PRT-JEA", "Jebel Ali", "UAE", 25.00, 55.03),
    ("PRT-BLW", "Belawan", "Indonesia", 3.78, 98.68),
]

MATERIALS = [
    # id, name, category, uom, unit cost usd
    ("M-SUG", "Sugar", "Sweetener", "kg", 0.55),
    ("M-PET", "PET preforms", "Packaging", "kg", 1.40),
    ("M-CAN", "Aluminium cans", "Packaging", "each", 0.09),
    ("M-CON", "Flavour concentrate", "Concentrate", "L", 14.00),
    ("M-CO2", "Food-grade CO2", "Gas", "kg", 0.20),
    ("M-CLS", "Closures", "Packaging", "each", 0.012),
    ("M-LBL", "Labels", "Packaging", "each", 0.006),
    ("M-COR", "Corrugate cartons", "Packaging", "each", 0.45),
    ("M-POT", "Potatoes", "Agri", "kg", 0.22),
    ("M-OIL", "Palm oil", "Edible oil", "kg", 1.00),
    ("M-SEA", "Seasoning blend", "Ingredient", "kg", 4.50),
    ("M-FLM", "Laminated film", "Packaging", "kg", 3.20),
]

# Product lines: qty of each material per case, cases/day per plant, economics per case
PRODUCTS = {
    "Cola 600 ml PET (24)": dict(bom={"M-SUG": 1.4, "M-PET": 0.6, "M-CON": 0.05, "M-CO2": 0.15, "M-CLS": 24, "M-LBL": 24, "M-COR": 1},
                                 rev=6.5, margin=1.6),
    "Cola 330 ml can (24)": dict(bom={"M-SUG": 0.8, "M-CAN": 24, "M-CON": 0.03, "M-CO2": 0.08, "M-COR": 1},
                                 rev=7.2, margin=1.9),
    "Potato chips 52 g (48)": dict(bom={"M-POT": 9.0, "M-OIL": 0.9, "M-SEA": 0.15, "M-FLM": 0.25, "M-COR": 1},
                                   rev=9.0, margin=2.6),
}
PLANT_PRODUCTS = {
    "PLT-KOL": {"Cola 600 ml PET (24)": 18000, "Potato chips 52 g (48)": 6000},
    "PLT-BBS": {"Cola 600 ml PET (24)": 14000, "Cola 330 ml can (24)": 6000},
    "PLT-HYD": {"Potato chips 52 g (48)": 8000, "Cola 600 ml PET (24)": 12000},
    "PLT-MAA": {"Cola 600 ml PET (24)": 16000, "Cola 330 ml can (24)": 8000},
    "PLT-PNQ": {"Potato chips 52 g (48)": 10000},
    "PLT-DEL": {"Cola 600 ml PET (24)": 22000, "Cola 330 ml can (24)": 9000, "Potato chips 52 g (48)": 9000},
    "PLT-DAC": {"Cola 600 ml PET (24)": 10000},
}

SUPPLIERS = [
    # id, name, city, country, lat, lon, origin port (None = domestic road only), materials
    ("SUP-01", "Eastern Sugar Mills", "Kolkata", "India", 22.70, 88.30, None, ["M-SUG"]),
    ("SUP-02", "Haldia Polymers", "Haldia", "India", 22.06, 88.07, None, ["M-PET", "M-FLM"]),
    ("SUP-03", "Kalinga Packaging", "Bhubaneswar", "India", 20.35, 85.80, None, ["M-COR", "M-LBL", "M-CLS"]),
    ("SUP-04", "Bengal Agro Potatoes", "Hooghly", "India", 22.90, 88.39, None, ["M-POT"]),
    ("SUP-05", "Deccan Sugar Co.", "Kolhapur", "India", 16.70, 74.24, None, ["M-SUG"]),
    ("SUP-06", "Andhra Cartons", "Visakhapatnam", "India", 17.72, 83.25, None, ["M-COR", "M-LBL"]),
    ("SUP-07", "Coromandel Gases", "Chennai", "India", 13.10, 80.20, None, ["M-CO2"]),
    ("SUP-08", "Western Polymers", "Vapi", "India", 20.37, 72.90, None, ["M-PET", "M-CLS", "M-FLM"]),
    ("SUP-09", "Punjab Agri Fresh", "Jalandhar", "India", 31.33, 75.58, None, ["M-POT"]),
    ("SUP-10", "Gujarat Edible Oils", "Kandla", "India", 23.03, 70.22, None, ["M-OIL"]),
    ("SUP-11", "Hyderabad Flavours", "Hyderabad", "India", 17.45, 78.38, None, ["M-SEA", "M-CON"]),
    ("SUP-12", "NCR Gas & Packaging", "Faridabad", "India", 28.41, 77.31, None, ["M-CO2", "M-COR", "M-LBL"]),
    ("SUP-13", "Odisha Industrial Gases", "Paradip", "India", 20.30, 86.60, None, ["M-CO2"]),
    ("SUP-14", "Chattogram Packaging", "Chattogram", "Bangladesh", 22.36, 91.78, None, ["M-COR", "M-LBL", "M-CO2", "M-SUG"]),
    ("SUP-15", "Siam Cane Sugar", "Chonburi", "Thailand", 13.36, 100.98, "PRT-LCH", ["M-SUG"]),
    ("SUP-16", "Selangor Palm Refinery", "Klang", "Malaysia", 3.04, 101.45, "PRT-PKL", ["M-OIL"]),
    ("SUP-17", "Sumatra Palm Oils", "Medan", "Indonesia", 3.59, 98.67, "PRT-BLW", ["M-OIL"]),
    ("SUP-18", "Shanghai Can Works", "Shanghai", "China", 31.10, 121.40, "PRT-SHA", ["M-CAN", "M-CLS"]),
    ("SUP-19", "Gulf Aluminium Cans", "Dubai", "UAE", 25.01, 55.10, "PRT-JEA", ["M-CAN"]),
    ("SUP-20", "Singapore Flavour House", "Singapore", "Singapore", 1.33, 103.75, "PRT-SIN", ["M-CON"]),
    ("SUP-21", "Mandalay Packaging", "Mandalay", "Myanmar", 21.96, 96.08, "PRT-RGN", ["M-FLM", "M-LBL"]),
    ("SUP-22", "Colombo Spice Blends", "Colombo", "Sri Lanka", 6.93, 79.86, "PRT-CMB", ["M-SEA"]),
    ("SUP-23", "Yangon Preforms", "Yangon", "Myanmar", 16.85, 96.15, "PRT-RGN", ["M-PET"]),
]


def km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def _road_days(km_):
    return max(1, math.ceil(km_ * 1.3 / 450))  # 1.3 road factor, ~450 km per truck-day


def _sea_days(km_):
    return max(2, math.ceil(km_ * 1.25 / 500)) + 1  # ~11 knots incl. routing, +1 day port handling


def generate(as_of: date) -> dict[str, pd.DataFrame]:
    rnd = random.Random(SEED)
    plants = pd.DataFrame(PLANTS, columns=["plant_id", "plant_name", "city", "country", "lat", "lon", "import_port_id"])
    ports = pd.DataFrame(PORTS, columns=["port_id", "port_name", "country", "lat", "lon"])
    port_xy = {p[0]: (p[3], p[4]) for p in PORTS}
    materials = pd.DataFrame(MATERIALS, columns=["material_id", "material_name", "category", "uom", "unit_cost_usd"])
    cost = {m[0]: m[4] for m in MATERIALS}

    suppliers = pd.DataFrame(
        [(s[0], s[1], s[2], s[3], s[4], s[5], s[6], "international" if s[6] else "domestic") for s in SUPPLIERS],
        columns=["supplier_id", "supplier_name", "city", "country", "lat", "lon", "origin_port_id", "sourcing"],
    )

    # Plant products and material demand
    pp_rows, usage = [], {}
    for plant_id, lines in PLANT_PRODUCTS.items():
        for prod, cases in lines.items():
            spec = PRODUCTS[prod]
            for mat, q in spec["bom"].items():
                pp_rows.append((plant_id, prod, mat, q, cases, spec["rev"], spec["margin"]))
                usage[(plant_id, mat)] = usage.get((plant_id, mat), 0) + q * cases
    plant_products = pd.DataFrame(pp_rows, columns=["plant_id", "product_line", "material_id", "qty_per_case",
                                                     "cases_per_day", "net_revenue_per_case_usd", "margin_per_case_usd"])

    plant_xy = {p[0]: (p[4], p[5]) for p in PLANTS}
    plant_port = {p[0]: p[6] for p in PLANTS}
    sup = {s[0]: s for s in SUPPLIERS}

    # Lanes: every supplier to every plant that uses one of its materials
    lanes, lane_of = [], {}
    for s in SUPPLIERS:
        sid, _, _, country, slat, slon, oport, mats = s
        for plant_id in PLANT_PRODUCTS:
            if not any((plant_id, m) in usage for m in mats):
                continue
            plat, plon = plant_xy[plant_id]
            pcountry = next(p[3] for p in PLANTS if p[0] == plant_id)
            if oport is None and country == pcountry:
                d = _road_days(km(slat, slon, plat, plon))
                row = (f"LN-{sid}-{plant_id}", sid, plant_id, "road", None, None, d, d, 0, 0)
            else:
                op = oport or min(port_xy, key=lambda k: km(slat, slon, *port_xy[k]))
                dp = plant_port[plant_id]
                a = _road_days(km(slat, slon, *port_xy[op]))
                b = _sea_days(km(*port_xy[op], *port_xy[dp]))
                c = _road_days(km(*port_xy[dp], plat, plon))
                row = (f"LN-{sid}-{plant_id}", sid, plant_id, "sea", op, dp, a + b + c, a, b, c)
            lanes.append(row)
            lane_of[(sid, plant_id)] = row
    lanes_df = pd.DataFrame(lanes, columns=["lane_id", "supplier_id", "plant_id", "mode", "origin_port_id", "dest_port_id",
                                            "transit_days", "days_supplier_to_port", "days_port_to_port", "days_port_to_plant"])

    # Approved sources: primary = closest domestic where possible
    sm_rows = []
    for (plant_id, mat) in sorted(usage):
        cands = [s for s in SUPPLIERS if mat in s[7] and (s[0], plant_id) in lane_of]
        cands.sort(key=lambda s: lane_of[(s[0], plant_id)][6])
        for rank, s in enumerate(cands):
            ln = lane_of[(s[0], plant_id)]
            lead = ln[6] + rnd.randint(3, 8)  # production / order processing + transit
            premium = 0.0 if rank == 0 else round(0.04 + 0.03 * rank + rnd.random() * 0.04, 3)
            sm_rows.append((s[0], mat, plant_id, lead, rank == 0, premium))
    supplier_materials = pd.DataFrame(sm_rows, columns=["supplier_id", "material_id", "plant_id", "lead_time_days",
                                                        "is_primary", "price_premium_pct"])

    # Inventory and open POs
    inv_rows, po_rows = [], []
    po_n = 1000
    for (plant_id, mat), daily in sorted(usage.items()):
        cover = rnd.uniform(6, 16)  # days of cover on hand
        on_hand = round(daily * cover)
        safety = round(daily * 3)
        inv_rows.append((plant_id, mat, on_hand, safety, round(daily, 2), as_of))
        srcs = supplier_materials[(supplier_materials.plant_id == plant_id) & (supplier_materials.material_id == mat)]
        primary = srcs[srcs.is_primary].supplier_id.iloc[0]
        others = list(srcs[~srcs.is_primary].supplier_id)
        eta_day = max(1, int(cover) - rnd.randint(1, 3))
        while eta_day < 45:
            sid = primary if (not others or rnd.random() < 0.65) else rnd.choice(others)
            ln = lane_of[(sid, plant_id)]
            days = rnd.uniform(7, 12)
            qty = round(daily * days)
            eta = as_of + timedelta(days=eta_day)
            ship = eta - timedelta(days=ln[6])
            if ln[3] == "sea":
                dep = ship + timedelta(days=ln[7])
                arr = dep + timedelta(days=ln[8])
            else:
                dep = arr = None
            order_date = ship - timedelta(days=rnd.randint(5, 20))
            status = "OPEN" if ship > as_of else "IN_TRANSIT"
            po_rows.append((f"PO-{po_n}", 10, sid, mat, plant_id, ln[0], qty, round(qty * cost[mat], 2),
                            order_date, ship, dep, arr, eta, status))
            po_n += 1
            eta_day += max(4, int(days) - rnd.randint(0, 2))
    inventory = pd.DataFrame(inv_rows, columns=["plant_id", "material_id", "on_hand_qty", "safety_stock_qty",
                                                "daily_usage_qty", "as_of_date"])
    pos = pd.DataFrame(po_rows, columns=["po_id", "po_line", "supplier_id", "material_id", "plant_id", "lane_id", "qty",
                                         "po_value_usd", "order_date", "ship_date", "port_departure_date",
                                         "port_arrival_date", "plant_eta_date", "status"])

    # Sample hazards, shaped like the ingested feeds (source = 'sample')
    t0 = as_of
    storm_track = [  # day offset, lat, lon, category, radius km
        (0, 10.8, 87.6, 2, 150), (1, 13.4, 87.0, 3, 180), (2, 16.0, 86.6, 3, 220),
        (3, 18.6, 86.7, 3, 260), (4, 21.0, 87.3, 2, 300), (5, 23.6, 88.4, 1, 300),
    ]
    hz = []
    for i, (d, la, lo, cat, r) in enumerate(storm_track):
        hz.append((f"SAMPLE-TC-BOB07-{i}", "cyclone", "Storm BOB-07", float(cat), la, lo, float(r),
                   t0 + timedelta(days=d), t0 + timedelta(days=d + 2), "sample"))
    hz.append(("SAMPLE-EQ-MMR-1", "earthquake", "M5.6 central Myanmar", 5.6, 21.20, 95.90, 210.0,
               t0 - timedelta(days=1), t0 + timedelta(days=10), "sample"))
    hz.append(("SAMPLE-PC-MAA-1", "port_congestion", "Chennai port congestion", 41.0, 13.10, 80.30, 30.0,
               t0, t0 + timedelta(days=12), "sample"))
    hazards = pd.DataFrame(hz, columns=["event_id", "hazard_type", "event_name", "severity", "lat", "lon", "radius_km",
                                        "window_start", "window_end", "source"])
    hazards["ingested_at"] = pd.Timestamp(as_of)

    delay_rules = pd.DataFrame([
        # hazard_type, node_type, severity_min (incl), severity_max (excl), delay_days (None = derive), note
        ("cyclone", "supplier", 1, 2, 2, "Cat 1: road closures, power cuts"),
        ("cyclone", "supplier", 2, 3, 4, "Cat 2: site shutdown 2-4 days"),
        ("cyclone", "supplier", 3, 99, 7, "Cat 3+: damage, extended shutdown"),
        ("cyclone", "port", 1, 2, 3, "Cat 1: berthing suspended"),
        ("cyclone", "port", 2, 3, 5, "Cat 2: port closed, backlog"),
        ("cyclone", "port", 3, 99, 7, "Cat 3+: port closed, backlog clearance"),
        ("earthquake", "supplier", 5.0, 6.0, 3, "Inspections, minor damage"),
        ("earthquake", "supplier", 6.0, 7.0, 10, "Structural checks, partial outage"),
        ("earthquake", "supplier", 7.0, 99, 21, "Major damage"),
        ("earthquake", "port", 5.0, 6.0, 1, "Crane / quay inspections"),
        ("earthquake", "port", 6.0, 7.0, 4, "Quay damage"),
        ("earthquake", "port", 7.0, 99, 10, "Port out of service"),
        ("port_congestion", "port", 0, 9999, None, "Delay = ceil(wait hours / 24)"),
    ], columns=["hazard_type", "node_type", "severity_min", "severity_max", "delay_days", "note"])
    delay_rules["severity_min"] = delay_rules["severity_min"].astype(float)
    delay_rules["severity_max"] = delay_rules["severity_max"].astype(float)
    delay_rules["delay_days"] = delay_rules["delay_days"].astype("Int64")

    expedite_rules = pd.DataFrame([
        ("sea", "Air freight", 0.30, "Bypasses port delays; cannot fix a supplier outage"),
        ("road", "Dedicated express truck", 0.08, "Bypasses road / port-side delays; cannot fix a supplier outage"),
    ], columns=["mode", "expedite_option", "premium_pct_of_value", "note"])

    return {
        "ref.plants": plants, "ref.ports": ports, "ref.materials": materials, "ref.suppliers": suppliers,
        "ref.lanes": lanes_df, "ref.supplier_materials": supplier_materials, "ref.plant_products": plant_products,
        "ref.delay_rules": delay_rules, "ref.expedite_rules": expedite_rules,
        "ops.inventory": inventory, "ops.purchase_orders": pos, "silver.hazard_events": hazards,
    }


if __name__ == "__main__":
    for name, df in generate(date(2026, 11, 18)).items():
        print(f"{name:28s} {len(df):5d} rows")
