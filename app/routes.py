"""Draws sea lanes around land instead of straight across it (approximate shipping routes)."""
FAR_EAST = {"PRT-SHA": [(119.5, 22.5), (110.5, 9.5), (104.6, 1.6)], "PRT-LCH": [(102.8, 8.0), (104.6, 1.6)],
            "PRT-SIN": [], "PRT-PKL": [], "PRT-BLW": []}
MALACCA_N = (97.2, 6.2)
SL_S = (80.6, 5.3)
EAST_APP = (82.6, 8.4)
WEST_APP = [(76.6, 7.4), (73.6, 11.5)]
WEST = {"PRT-JNP", "PRT-MUN", "PRT-JEA"}


def sea_path(op, dp, ports):
    xy = lambda pid: (ports[pid]["lon"], ports[pid]["lat"])
    pts, side = [xy(op)], "east"
    if op in FAR_EAST:
        pts += FAR_EAST[op] + ([(103.4, 2.0)] if op != "PRT-BLW" else []) + [MALACCA_N]
    elif op == "PRT-JEA":
        pts += [(57.6, 24.6), (61.5, 22.0)]
        side = "west"
    elif op in WEST:
        side = "west"
    elif op == "PRT-CMB":
        side = "south"
    if op == "PRT-RGN":
        pts.append((95.0, 14.5))
    if dp in WEST:
        if side == "east":
            pts += [EAST_APP, SL_S] + WEST_APP
        elif side == "south":
            pts += WEST_APP
    else:
        if side == "west":
            pts += WEST_APP[::-1] + [SL_S, EAST_APP]
        elif side == "south":
            pts += [SL_S, EAST_APP]
    pts.append(xy(dp))
    return pts


def lane_path(lane, suppliers, plants, ports):
    s, p = suppliers[lane["s"]], plants[lane["p"]]
    path = [(s["lon"], s["lat"])]
    if lane["mode"] == "sea" and lane.get("op") in ports and lane.get("dp") in ports:
        path += sea_path(lane["op"], lane["dp"], ports)
    path.append((p["lon"], p["lat"]))
    return [[round(a, 2), round(b, 2)] for a, b in path]
