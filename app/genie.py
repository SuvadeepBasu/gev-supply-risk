"""Thin wrapper around the Genie Conversation API (databricks-sdk)."""
from __future__ import annotations

import datetime as dt


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
    out = {"conversation_id": msg.conversation_id, "message_id": getattr(msg, "message_id", None) or msg.id,
           "text": "", "sql": None, "description": None, "columns": [], "rows": [], "suggestions": [],
           "status": str(getattr(msg, "status", ""))}
    texts = []
    for att in msg.attachments or []:
        if getattr(att, "text", None) and att.text.content:
            texts.append(att.text.content)
        if getattr(att, "query", None):
            out["sql"] = att.query.query
            out["description"] = getattr(att.query, "description", None)
            att_id = getattr(att, "attachment_id", None) or getattr(att, "id", None)
            res = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id, out["message_id"], att_id)
            cols, rows = statement_rows(res.statement_response)
            out["columns"], out["rows"] = cols, rows[:max_rows]
        sq = getattr(att, "suggested_questions", None)
        if sq and getattr(sq, "questions", None):
            out["suggestions"] = list(sq.questions)[:3]
    out["text"] = "\n\n".join(texts) or (out["description"] or "")
    if not out["text"] and getattr(msg, "error", None):
        out["text"] = f"Genie could not answer: {msg.error}"
    return out
