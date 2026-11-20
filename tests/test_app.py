"""Tests the Databricks App backend locally: real gold tables on local Spark, mocked Genie.

    python tests/test_app.py           # writes app/static/demo/map.json as a side effect (used for UI checks)
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tests"))

import run_local_pipeline  # noqa: E402
spark = run_local_pipeline.main()

import data  # noqa: E402
import genie  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def local_run(sql):
    df = spark.sql(sql.replace(data.CATALOG + ".", ""))
    return [r.asDict() for r in df.collect()]


m = data.build_map_data(local_run)
assert len(m["plants"]) == 7 and len(m["suppliers"]) == 23 and len(m["ports"]) == 15, (len(m["plants"]), len(m["suppliers"]))
assert m["kpi"]["margin_at_risk_usd"] > 1_000_000
assert m["cyclones"] and len(m["cyclones"][0]["pts"]) == 6 and m["quakes"] and m["congestion"]
assert any(l["delayed"] for l in m["lanes"]) and all(len(l["path"]) >= 2 for l in m["lanes"])
assert any(p["exposed"] for p in m["ports"]) and any(s["exposed"] for s in m["suppliers"])
assert {p["risk"] for p in m["plants"]} <= {"High", "Medium", "Low", "None"}
out = ROOT / "app" / "static" / "demo"
out.mkdir(exist_ok=True)
(out / "map.json").write_text(json.dumps(m, default=str, separators=(",", ":")))
print("map data ok:", {k: len(v) if isinstance(v, list) else "·" for k, v in m.items()})

# ---- API with the warehouse swapped for local Spark and Genie mocked
main.run_sql = local_run
c = TestClient(main.app)
assert c.get("/").status_code == 200 and "Supply Risk Forecast" in c.get("/").text
assert c.get("/api/map").json()["kpi"]["delayed_po_lines"] == m["kpi"]["delayed_po_lines"]


class FakeGenie:
    def __init__(self):
        self.calls = []

    def _msg(self, conv, q):
        rows = local_run("SELECT plant_id, round(sum(margin_at_risk_usd),0) AS margin FROM supply_risk_dev.gold.plant_material_impact "
                         "WHERE has_new_shortage GROUP BY plant_id ORDER BY margin DESC")
        self.rows = rows
        return NS(conversation_id=conv, message_id="m1", id="m1", status="COMPLETED", error=None,
                  attachments=[NS(text=NS(content="Kolkata is most exposed."), query=None, suggested_questions=None, attachment_id="a0"),
                               NS(text=None, query=NS(query="SELECT ...", description="Margin by plant"), suggested_questions=None, attachment_id="a1"),
                               NS(text=None, query=None, attachment_id="a2", suggested_questions=NS(questions=["What should procurement do?"]))])

    def start_conversation_and_wait(self, space, q, timeout=None):
        self.calls.append(("start", q)); return self._msg("c1", q)

    def create_message_and_wait(self, space, conv, q, timeout=None):
        self.calls.append(("follow", conv, q)); return self._msg(conv, q)

    def get_message_attachment_query_result(self, space, conv, mid, aid):
        assert aid == "a1" and space == "space1"
        cols = [NS(name="plant_id", type_name=NS(value="STRING")), NS(name="margin", type_name=NS(value="DOUBLE"))]
        return NS(statement_response=NS(manifest=NS(schema=NS(columns=cols)),
                                        result=NS(data_array=[[r["plant_id"], str(r["margin"])] for r in self.rows])))


fake = FakeGenie()
main._w = NS(genie=fake)
import os
main._w.genie.list_spaces = lambda page_size=None, page_token=None: NS(spaces=[NS(title="Other", space_id="x"), NS(title="Supply Risk Forecast", space_id="space1")], next_page_token=None)
r = c.post("/api/ask", json={"question": "Which plants lose the most margin?"}).json()
assert r["conversation_id"] == "c1" and r["text"].startswith("Kolkata") and r["columns"][1]["name"] == "margin"
assert isinstance(r["rows"][0][1], float) and r["suggestions"] == ["What should procurement do?"]
r2 = c.post("/api/ask", json={"question": "and suppliers?", "conversation_id": "c1"}).json()
assert fake.calls[-1] == ("follow", "c1", "and suppliers?") and r2["conversation_id"] == "c1"
assert c.post("/api/ask", json={"question": "  "}).status_code == 400
print("api ok:", r["rows"][:3])
print("ALL APP TESTS PASSED")
