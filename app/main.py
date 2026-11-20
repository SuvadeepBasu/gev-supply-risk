"""God's Eye View · Supply Risk Forecast — Databricks App backend.

  GET  /            the console (static/index.html)
  GET  /api/map     plants, suppliers, ports, lanes, hazards, KPIs (from the gold tables)
  POST /api/ask     {question, conversation_id?} -> Genie answer with rows
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import data
import genie

log = logging.getLogger("gev")
STATIC = Path(__file__).parent / "static"
app = FastAPI(title="God's Eye View · Supply Risk Forecast")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
_cache = data.Cache(ttl=60)
_w = None


def workspace():
    global _w
    if _w is None:
        from databricks.sdk import WorkspaceClient
        _w = WorkspaceClient()  # inside Databricks Apps this authenticates as the app's service principal
    return _w


def run_sql(sql: str) -> list[dict]:
    wid = os.getenv("WAREHOUSE_ID")
    if not wid:
        raise HTTPException(500, "WAREHOUSE_ID is not set. Add the SQL warehouse as an app resource.")
    resp = workspace().statement_execution.execute_statement(warehouse_id=wid, statement=sql, wait_timeout="50s")
    state = getattr(getattr(resp.status, "state", None), "value", str(getattr(resp.status, "state", "")))
    if state != "SUCCEEDED":
        err = getattr(resp.status, "error", None)
        raise HTTPException(502, f"SQL failed ({state}): {getattr(err, 'message', err)}")
    cols, rows = genie.statement_rows(resp)
    return [dict(zip([c["name"] for c in cols], r)) for r in rows]


class Ask(BaseModel):
    question: str
    conversation_id: str | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "warehouse": bool(os.getenv("WAREHOUSE_ID")), "genie": bool(os.getenv("GENIE_SPACE_ID")), "catalog": data.CATALOG}


@app.get("/api/map")
def map_data():
    try:
        return _cache.get(lambda: data.build_map_data(run_sql))
    except HTTPException:
        raise
    except Exception as e:  # surface permission problems clearly in the UI
        log.exception("map data failed")
        raise HTTPException(502, f"Could not read {data.CATALOG} tables: {e}")


@app.post("/api/ask")
def ask(body: Ask):
    space = os.getenv("GENIE_SPACE_ID")
    if not space:
        raise HTTPException(500, "GENIE_SPACE_ID is not set. Add the Genie agent as an app resource.")
    if not body.question.strip():
        raise HTTPException(400, "Empty question")
    try:
        return genie.ask(workspace(), space, body.question.strip(), body.conversation_id)
    except Exception as e:
        log.exception("genie failed")
        raise HTTPException(502, f"Genie request failed: {e}")
