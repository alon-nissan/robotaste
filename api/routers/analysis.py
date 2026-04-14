"""
Analysis Endpoints — Dose-response data for visualization dashboards.

Provides endpoints to query completed experiment data across sessions
and return structured results for charting (dose-response curves, etc.).
"""

import json
import logging
import re
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from robotaste.data.database import get_database_connection

logger = logging.getLogger("robotaste.api.analysis")
router = APIRouter()


@router.get("/dose-response")
def get_dose_response_data(
    protocol_id: Optional[str] = Query(None, description="Filter by protocol ID"),
):
    """
    Return dose-response data: per-subject concentration vs questionnaire response.

    Groups samples by session (subject) and returns:
    - Individual subject data points
    - Aggregated mean/std per concentration level
    - Protocol and ingredient metadata
    """
    try:
        with get_database_connection() as conn:
            # Fetch all samples joined with session/protocol info
            query = """
                SELECT
                    s.sample_id,
                    s.session_id,
                    s.cycle_number,
                    s.ingredient_concentration,
                    s.questionnaire_answer,
                    s.selection_mode,
                    s.created_at,
                    ses.session_code,
                    ses.protocol_id,
                    ses.user_id,
                    u.name as subject_name,
                    pl.name as protocol_name,
                    pl.protocol_json
                FROM samples s
                JOIN sessions ses ON s.session_id = ses.session_id
                LEFT JOIN users u ON ses.user_id = u.id
                LEFT JOIN protocol_library pl ON ses.protocol_id = pl.protocol_id
                WHERE s.questionnaire_answer IS NOT NULL
                  AND ses.deleted_at IS NULL
                  AND s.deleted_at IS NULL
            """
            params = []
            if protocol_id:
                query += " AND ses.protocol_id = ?"
                params.append(protocol_id)

            query += " ORDER BY ses.session_code, s.cycle_number"

            rows = conn.execute(query, params).fetchall()

        if not rows:
            return {
                "protocols": [],
                "subjects": [],
                "data_points": [],
                "aggregated": [],
                "ingredients": [],
                "response_variables": [],
            }

        # Collect unique protocols, subjects, ingredients, response variables
        protocols_map: dict = {}
        subjects_map: dict = {}
        ingredients_set: set = set()
        response_vars_set: set = set()
        ingredient_units: dict = {}  # ingredient name → unit string
        data_points = []

        skip_keys = {"questionnaire_type", "participant_id", "timestamp", "is_final"}

        for row in rows:
            conc = json.loads(row["ingredient_concentration"]) if isinstance(row["ingredient_concentration"], str) else row["ingredient_concentration"]
            answer = json.loads(row["questionnaire_answer"]) if isinstance(row["questionnaire_answer"], str) else row["questionnaire_answer"]

            # Track protocols
            pid = row["protocol_id"]
            if pid and pid not in protocols_map:
                protocols_map[pid] = {
                    "protocol_id": pid,
                    "name": row["protocol_name"] or pid[:8],
                }
                # Extract ingredient units from the protocol JSON
                if row["protocol_json"]:
                    try:
                        proto_data = json.loads(row["protocol_json"])
                        for ing in proto_data.get("ingredients", []):
                            name = ing.get("name")
                            unit = ing.get("unit")
                            if name and unit and name not in ingredient_units:
                                ingredient_units[name] = unit
                    except Exception:
                        pass

            # Track subjects
            sid = row["session_id"]
            if sid not in subjects_map:
                subjects_map[sid] = {
                    "session_id": sid,
                    "session_code": row["session_code"],
                    "subject_name": row["subject_name"] or row["session_code"],
                    "protocol_id": pid,
                }

            # Track ingredients and response variables
            for ing in conc:
                ingredients_set.add(ing)
            for key in answer:
                if key not in skip_keys:
                    response_vars_set.add(key)

            # Build data point
            data_points.append({
                "session_id": sid,
                "session_code": row["session_code"],
                "subject_name": row["subject_name"] or row["session_code"],
                "cycle_number": row["cycle_number"],
                "concentrations": conc,
                "responses": {k: v for k, v in answer.items() if k not in skip_keys},
            })

        # Aggregate: mean and std per unique concentration level
        from collections import defaultdict
        import math

        conc_groups: dict = defaultdict(list)
        ingredients_list = sorted(ingredients_set)
        response_vars_list = sorted(response_vars_set)

        for dp in data_points:
            conc_key = tuple(dp["concentrations"].get(ing, 0) for ing in ingredients_list)
            conc_groups[conc_key].append(dp["responses"])

        aggregated = []
        for conc_key, response_list in sorted(conc_groups.items()):
            entry: dict = {
                "concentrations": {ing: val for ing, val in zip(ingredients_list, conc_key)},
                "n": len(response_list),
                "stats": {},
            }
            for var in response_vars_list:
                values = [r[var] for r in response_list if var in r and r[var] is not None]
                if values:
                    numeric = [float(v) for v in values]
                    mean = sum(numeric) / len(numeric)
                    variance = sum((x - mean) ** 2 for x in numeric) / len(numeric) if len(numeric) > 1 else 0
                    std = math.sqrt(variance)
                    sem = std / math.sqrt(len(numeric)) if len(numeric) > 1 else 0
                    entry["stats"][var] = {
                        "mean": round(mean, 3),
                        "std": round(std, 3),
                        "sem": round(sem, 3),
                        "min": round(min(numeric), 3),
                        "max": round(max(numeric), 3),
                        "n": len(numeric),
                    }
            aggregated.append(entry)

        return {
            "protocols": list(protocols_map.values()),
            "subjects": list(subjects_map.values()),
            "data_points": data_points,
            "aggregated": aggregated,
            "ingredients": ingredients_list,
            "response_variables": response_vars_list,
            "ingredient_units": ingredient_units,
        }

    except Exception as e:
        logger.error("Error fetching dose-response data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── ANALYSIS HUB ─────────────────────────────────────────────────────────────

# Table allowlist — maps API keys to SQL table names, PKs, and visible columns.
TABLE_CONFIG: dict[str, dict[str, Any]] = {
    "sessions": {
        "table": "sessions",
        "pk": "session_id",
        "columns": [
            {"key": "session_id", "label": "Session ID", "type": "text"},
            {"key": "session_code", "label": "Code", "type": "text"},
            {"key": "state", "label": "State", "type": "text"},
            {"key": "current_phase", "label": "Phase", "type": "text"},
            {"key": "current_cycle", "label": "Cycle", "type": "number"},
            {"key": "protocol_id", "label": "Protocol ID", "type": "text"},
            {"key": "user_id", "label": "User ID", "type": "text"},
            {"key": "created_at", "label": "Created", "type": "date"},
            {"key": "deleted_at", "label": "Deleted At", "type": "date"},
        ],
    },
    "samples": {
        "table": "samples",
        "pk": "sample_id",
        "columns": [
            {"key": "sample_id", "label": "Sample ID", "type": "text"},
            {"key": "session_id", "label": "Session ID", "type": "text"},
            {"key": "cycle_number", "label": "Cycle", "type": "number"},
            {"key": "selection_mode", "label": "Mode", "type": "text"},
            {"key": "ingredient_concentration", "label": "Concentrations", "type": "json"},
            {"key": "questionnaire_answer", "label": "Response", "type": "json"},
            {"key": "created_at", "label": "Created", "type": "date"},
        ],
    },
    "users": {
        "table": "users",
        "pk": "id",
        "columns": [
            {"key": "id", "label": "User ID", "type": "text"},
            {"key": "name", "label": "Name", "type": "text"},
            {"key": "gender", "label": "Gender", "type": "text"},
            {"key": "age", "label": "Age", "type": "number"},
            {"key": "created_at", "label": "Created", "type": "date"},
        ],
    },
    "protocols": {
        "table": "protocol_library",
        "pk": "protocol_id",
        "columns": [
            {"key": "protocol_id", "label": "Protocol ID", "type": "text"},
            {"key": "name", "label": "Name", "type": "text"},
            {"key": "description", "label": "Description", "type": "text"},
            {"key": "version", "label": "Version", "type": "text"},
            {"key": "created_by", "label": "Created By", "type": "text"},
            {"key": "created_at", "label": "Created", "type": "date"},
            {"key": "is_archived", "label": "Archived", "type": "number"},
        ],
    },
}

# Pre-built lookup maps derived from the static allowlist.
_SAFE_SQL_TABLE: dict[str, str] = {k: v["table"] for k, v in TABLE_CONFIG.items()}
_SAFE_PK: dict[str, str] = {k: v["pk"] for k, v in TABLE_CONFIG.items()}
_SAFE_COLUMNS: dict[str, list[str]] = {
    k: [c["key"] for c in v["columns"]] for k, v in TABLE_CONFIG.items()
}

ALLOWED_SORT_DIRS = {"asc", "desc"}
BLOCKED_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA)\b",
    re.IGNORECASE,
)


def _resolve_sql_table(key: str) -> str:
    """Return a hardcoded SQL table name for a validated allowlist key."""
    if key == "sessions":
        return "sessions"
    if key == "samples":
        return "samples"
    if key == "users":
        return "users"
    if key == "protocols":
        return "protocol_library"
    raise ValueError(f"Unresolvable table key: {key}")  # unreachable after allowlist check


def _resolve_pk(key: str) -> str:
    """Return a hardcoded primary-key column name for a validated allowlist key."""
    if key == "sessions":
        return "session_id"
    if key == "samples":
        return "sample_id"
    if key == "users":
        return "id"
    if key == "protocols":
        return "protocol_id"
    raise ValueError(f"Unresolvable pk key: {key}")  # unreachable after allowlist check


# ─── PYDANTIC REQUEST MODELS ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    sql: str


class ArchiveRequest(BaseModel):
    restore: bool = False


class BatchRequest(BaseModel):
    action: str  # "archive" | "delete" | "restore"
    session_ids: list[str]


# ─── DASHBOARD STATS ─────────────────────────────────────────────────────────

@router.get("/dashboard-stats")
def get_dashboard_stats():
    """Return at-a-glance statistics for the analysis hub dashboard."""
    try:
        with get_database_connection() as conn:
            total_sessions = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE deleted_at IS NULL"
            ).fetchone()[0]
            total_subjects = conn.execute(
                "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL"
            ).fetchone()[0]
            total_samples = conn.execute(
                "SELECT COUNT(*) FROM samples WHERE deleted_at IS NULL"
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE state = 'completed' AND deleted_at IS NULL"
            ).fetchone()[0]
            completion_rate = round(completed / total_sessions * 100, 1) if total_sessions else 0.0

        return {
            "total_sessions": total_sessions,
            "total_subjects": total_subjects,
            "total_samples": total_samples,
            "completion_rate": completion_rate,
        }
    except Exception as e:
        logger.error("Error fetching dashboard stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── DATA EXPLORER ───────────────────────────────────────────────────────────

@router.get("/explorer/{table_name}")
def explore_table(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_column: Optional[str] = Query(None),
    sort_dir: str = Query("asc"),
    filters: Optional[str] = Query(None, description="JSON array of {column, operator, value}"),
):
    """Browse a whitelisted table with pagination, sorting, and filtering."""
    if table_name not in TABLE_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found. Allowed: {list(TABLE_CONFIG.keys())}",
        )

    cfg = TABLE_CONFIG[table_name]
    sql_table = _resolve_sql_table(table_name)
    allowed_col_list = _SAFE_COLUMNS[table_name]
    allowed_keys = set(allowed_col_list)

    # Validate sort direction; re-derive column from config list to break taint chain.
    safe_sort_col: Optional[str] = None
    if sort_column and sort_column in allowed_keys:
        safe_sort_col = next((c for c in allowed_col_list if c == sort_column), None)
    if sort_dir not in ALLOWED_SORT_DIRS:
        sort_dir = "asc"

    # Parse and validate filters — re-derive column name from allowlist.
    filter_clauses: list[str] = []
    filter_params: list = []
    if filters:
        try:
            for f in json.loads(filters):
                col = f.get("column")
                op = f.get("operator", "contains")
                val = f.get("value", "")
                if col not in allowed_keys or val == "":
                    continue
                safe_col = next((c for c in allowed_col_list if c == col), None)
                if safe_col is None:
                    continue
                if op == "contains":
                    filter_clauses.append(f"{safe_col} LIKE ?")
                    filter_params.append(f"%{val}%")
                elif op == "starts_with":
                    filter_clauses.append(f"{safe_col} LIKE ?")
                    filter_params.append(f"{val}%")
                elif op in ("=", "!=", ">", "<", ">=", "<="):
                    filter_clauses.append(f"{safe_col} {op} ?")
                    filter_params.append(val)
                elif op == "before":
                    filter_clauses.append(f"{safe_col} < ?")
                    filter_params.append(val)
                elif op == "after":
                    filter_clauses.append(f"{safe_col} > ?")
                    filter_params.append(val)
        except Exception:
            pass

    where_sql = ("WHERE " + " AND ".join(filter_clauses)) if filter_clauses else ""
    safe_sort_dir = "ASC" if sort_dir == "asc" else "DESC"
    order_sql = f"ORDER BY {safe_sort_col} {safe_sort_dir}" if safe_sort_col else ""
    col_names = ", ".join(allowed_col_list)
    offset = (page - 1) * page_size

    try:
        with get_database_connection() as conn:
            count_row = conn.execute(
                f"SELECT COUNT(*) FROM {sql_table} {where_sql}", filter_params
            ).fetchone()
            total = count_row[0] if count_row else 0

            rows = conn.execute(
                f"SELECT {col_names} FROM {sql_table} {where_sql} {order_sql} LIMIT ? OFFSET ?",
                filter_params + [page_size, offset],
            ).fetchall()

        return {
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "columns": cfg["columns"],
        }
    except Exception as e:
        logger.error("Error in explorer for table %s: %s", table_name, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explorer/{table_name}/{record_id}")
def explore_record(table_name: str, record_id: str):
    """Return a single record from a whitelisted table, with JSON fields parsed."""
    if table_name not in TABLE_CONFIG:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

    cfg = TABLE_CONFIG[table_name]
    sql_table = _resolve_sql_table(table_name)
    pk = _resolve_pk(table_name)
    json_cols = {c["key"] for c in cfg["columns"] if c.get("type") == "json"}

    try:
        with get_database_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {sql_table} WHERE {pk} = ?", [record_id]
            ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Record not found.")

        record = dict(row)
        for key in json_cols:
            if key in record and isinstance(record[key], str):
                try:
                    record[key] = json.loads(record[key])
                except Exception:
                    pass
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching record %s/%s: %s", table_name, record_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── QUERY BUILDER ───────────────────────────────────────────────────────────

@router.post("/query")
def run_query(body: QueryRequest):
    """
    Execute a read-only SQL query with safety checks.
    Only SELECT and WITH queries are permitted; DDL/DML keywords are blocked.
    """
    sql = body.sql.strip().rstrip(";")

    upper = sql.upper().lstrip()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise HTTPException(status_code=400, detail="Only SELECT or WITH queries are allowed.")
    if ";" in sql:
        raise HTTPException(status_code=400, detail="Multi-statement queries are not allowed.")
    if BLOCKED_SQL_PATTERN.search(sql):
        raise HTTPException(status_code=400, detail="Query contains disallowed SQL keywords.")

    # Enforce a hard row cap
    if "LIMIT" not in upper:
        sql = f"{sql} LIMIT 1000"

    try:
        start = time.perf_counter()
        with get_database_connection() as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            cursor = conn.execute(sql)
            column_names = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        return {
            "columns": column_names,
            "rows": [list(r) for r in rows],
            "row_count": len(rows),
            "execution_time_ms": elapsed_ms,
        }
    except Exception as e:
        logger.warning("Query error: %s | SQL: %s", e, sql[:200])
        raise HTTPException(status_code=400, detail=f"Query error: {e}")


# ─── SESSION MANAGER ─────────────────────────────────────────────────────────

@router.get("/sessions")
def list_sessions_for_manager(
    state: Optional[str] = Query(None),
    protocol_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """List sessions for the session manager with optional filters and pagination."""
    clauses: list[str] = []
    params: list = []

    if not include_archived:
        clauses.append("ses.deleted_at IS NULL")
    if state:
        clauses.append("ses.state = ?")
        params.append(state)
    if protocol_id:
        clauses.append("ses.protocol_id = ?")
        params.append(protocol_id)
    if date_from:
        clauses.append("ses.created_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("ses.created_at <= ?")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    offset = (page - 1) * page_size

    base_query = """
        SELECT
            ses.session_id,
            ses.session_code,
            pl.name AS protocol_name,
            u.name  AS subject_name,
            ses.state,
            ses.current_phase,
            ses.current_cycle,
            ses.created_at,
            ses.deleted_at
        FROM sessions ses
        LEFT JOIN protocol_library pl ON ses.protocol_id = pl.protocol_id
        LEFT JOIN users u ON ses.user_id = u.id
    """

    try:
        with get_database_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM sessions ses {where_sql}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"{base_query} {where_sql} ORDER BY ses.created_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()

        return {
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("Error listing sessions for manager: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{session_id}/archive")
def archive_session(session_id: str, body: ArchiveRequest):
    """Soft-delete (archive) or restore a session."""
    try:
        with get_database_connection() as conn:
            row = conn.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?", [session_id]
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found.")

            if body.restore:
                conn.execute(
                    "UPDATE sessions SET deleted_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                    [session_id],
                )
            else:
                conn.execute(
                    "UPDATE sessions SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                    [session_id],
                )
            conn.commit()
        return {"success": True, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error archiving session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
def delete_session_hard(session_id: str):
    """Hard-delete a session and all related child records in one transaction."""
    try:
        with get_database_connection() as conn:
            row = conn.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?", [session_id]
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found.")

            conn.execute("DELETE FROM samples WHERE session_id = ?", [session_id])
            conn.execute("DELETE FROM bo_configuration WHERE session_id = ?", [session_id])
            conn.execute("DELETE FROM pump_operations WHERE session_id = ?", [session_id])
            conn.execute("DELETE FROM session_sample_bank_state WHERE session_id = ?", [session_id])
            conn.execute("DELETE FROM sessions WHERE session_id = ?", [session_id])
            conn.commit()
        return {"success": True, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error hard-deleting session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/batch")
def batch_session_action(body: BatchRequest):
    """Perform archive / delete / restore on multiple sessions."""
    if body.action not in ("archive", "delete", "restore"):
        raise HTTPException(status_code=400, detail="Invalid action. Use archive, delete, or restore.")
    if not body.session_ids:
        raise HTTPException(status_code=400, detail="No session IDs provided.")

    affected = 0
    try:
        with get_database_connection() as conn:
            for sid in body.session_ids:
                row = conn.execute(
                    "SELECT session_id FROM sessions WHERE session_id = ?", [sid]
                ).fetchone()
                if not row:
                    continue
                if body.action == "archive":
                    conn.execute(
                        "UPDATE sessions SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                        [sid],
                    )
                    affected += 1
                elif body.action == "restore":
                    conn.execute(
                        "UPDATE sessions SET deleted_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                        [sid],
                    )
                    affected += 1
                elif body.action == "delete":
                    conn.execute("DELETE FROM samples WHERE session_id = ?", [sid])
                    conn.execute("DELETE FROM bo_configuration WHERE session_id = ?", [sid])
                    conn.execute("DELETE FROM pump_operations WHERE session_id = ?", [sid])
                    conn.execute("DELETE FROM session_sample_bank_state WHERE session_id = ?", [sid])
                    conn.execute("DELETE FROM sessions WHERE session_id = ?", [sid])
                    affected += 1
            conn.commit()
        return {"success": True, "affected": affected}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in batch session action: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
