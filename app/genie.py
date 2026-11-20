"""Thin wrapper around the Genie Conversation API (databricks-sdk)."""
from __future__ import annotations

import datetime as dt
import json
import logging

log = logging.getLogger("gev.genie")


def _val(v, type_name):
    if v is None:
        return None
    t = (type_name or "").upper()
    try:
        if t in ("INT", "LONG", "BIGINT", "SHORT", "BYTE", "INTEGER"):
            return int(v)
        if t in ("DOUBLE", "FLOAT", "DECIMAL"):
            return float(v)
        if t == "BOOLEAN":
            return str(v).lower() == "true"
    except ValueError:
        return v
    return v


def statement_rows(resp) -> tuple[list[dict], list[list]]:
    """Columns [{name, type}] and rows from a StatementResponse."""
    manifest, result = getattr(resp, "manifest", None), getattr(resp, "result", None)
    cols = []
    if manifest and manifest.schema and manifest.schema.columns:
        for c in manifest.schema.columns:
            tn = getattr(c, "type_name", None)
            cols.append({"name": c.name, "type": getattr(tn, "value", tn) or getattr(c, "type_text", "")})
    data = (result.data_array if result and result.data_array else []) or []
    rows = [[_val(v, cols[i]["type"] if i < len(cols) else "") for i, v in enumerate(r)] for r in data]
    return cols, rows


def ask(w, space_id: str, question: str, conversation_id: str | None = None, max_rows: int = 200) -> dict:
    timeout = dt.timedelta(minutes=3)
    if conversation_id:
        msg = w.genie.create_message_and_wait(space_id, conversation_id, question, timeout=timeout)
    else:
        msg = w.genie.start_conversation_and_wait(space_id, question, timeout=timeout)
    mid = getattr(msg, "message_id", None) or msg.id
    # the waiter can return before attachments are filled in; re-read the finished message once
    if not msg.attachments:
        try:
            msg = w.genie.get_message(space_id, msg.conversation_id, mid)
        except Exception as e:  # noqa: BLE001
            log.warning("get_message failed: %s", e)
    status = getattr(getattr(msg, "status", None), "value", str(getattr(msg, "status", "")))
    out = {"conversation_id": msg.conversation_id, "message_id": mid, "status": status,
           "text": "", "sql": None, "description": None, "columns": [], "rows": [], "suggestions": [], "notes": []}
    texts = []
    for att in msg.attachments or []:
        txt = getattr(att, "text", None)
        if txt is not None and getattr(txt, "content", None):
            texts.append(txt.content)
        q = getattr(att, "query", None)
        if q is not None:
            out["sql"] = getattr(q, "query", None)
            out["description"] = getattr(q, "description", None) or getattr(q, "title", None)
            att_id = getattr(att, "attachment_id", None) or getattr(q, "id", None)
            try:
                res = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id, mid, att_id)
                cols, rows = statement_rows(res.statement_response)
                out["columns"], out["rows"] = cols, rows[:max_rows]
            except Exception as e:  # noqa: BLE001
                log.exception("query result failed")
                out["notes"].append(f"Genie wrote a query but its result could not be read: {e}")
        sq = getattr(att, "suggested_questions", None)
        if sq is not None and getattr(sq, "questions", None):
            out["suggestions"] = list(sq.questions)[:3]
    out["text"] = "\n\n".join(texts) or (out["description"] or "")
    err = getattr(msg, "error", None)
    if err:
        out["notes"].append(f"Genie error: {getattr(err, 'error', None) or err}")
    if status and status != "COMPLETED":
        out["notes"].append(f"Genie finished with status {status}.")
    if not out["text"] and not out["rows"]:
        try:
            raw = msg.as_dict()
        except Exception:  # noqa: BLE001
            raw = {"repr": repr(msg)[:4000]}
        out["raw"] = raw
        log.warning("empty Genie answer: %s", json.dumps(raw, default=str)[:4000])
    return out
