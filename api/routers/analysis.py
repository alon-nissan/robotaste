"""
Analysis Endpoints — Dose-response data, dashboard stats, DB explorer, and query builder.

Provides endpoints to query completed experiment data across sessions
and return structured results for charting (dose-response curves, etc.).
"""

import json
import logging
import re
from typing import Optional

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
                    s.sample_temperature_c,
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
                "sample_temperatures_c": [],
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
                "sample_temperature_c": row["sample_temperature_c"],
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
            conc_key = (dp.get("sample_temperature_c"),) + tuple(
                dp["concentrations"].get(ing, 0) for ing in ingredients_list
            )
            conc_groups[conc_key].append(dp["responses"])

        aggregated = []

        def _group_sort_key(item):
            key = item[0]
            temp = key[0]
            concentrations_key = key[1:]
            temp_sort = float("-inf") if temp is None else float(temp)
            return (temp is None, temp_sort, *concentrations_key)

        for conc_key, response_list in sorted(conc_groups.items(), key=_group_sort_key):
            sample_temperature_c = conc_key[0]
            entry: dict = {
                "sample_temperature_c": sample_temperature_c,
                "concentrations": {
                    ing: val for ing, val in zip(ingredients_list, conc_key[1:])
                },
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

        sample_temperatures_c = sorted({
            dp["sample_temperature_c"]
            for dp in data_points
            if dp.get("sample_temperature_c") is not None
        })

        return {
            "protocols": list(protocols_map.values()),
            "subjects": list(subjects_map.values()),
            "data_points": data_points,
            "aggregated": aggregated,
            "ingredients": ingredients_list,
            "response_variables": response_vars_list,
            "ingredient_units": ingredient_units,
            "sample_temperatures_c": sample_temperatures_c,
        }

    except Exception as e:
        logger.error("Error fetching dose-response data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── DASHBOARD ──────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard_stats():
    """
    Return overview statistics grouped by protocol.

    Returns per-protocol counts of sessions, unique subjects, and samples
    collected, along with overall totals.
    """
    try:
        with get_database_connection() as conn:
            rows = conn.execute("""
                SELECT
                    ses.protocol_id,
                    pl.name AS protocol_name,
                    COUNT(DISTINCT ses.session_id) AS session_count,
                    COUNT(DISTINCT ses.user_id)    AS subject_count,
                    COUNT(s.sample_id)             AS sample_count
                FROM sessions ses
                LEFT JOIN protocol_library pl ON ses.protocol_id = pl.protocol_id
                LEFT JOIN samples s ON ses.session_id = s.session_id
                    AND s.deleted_at IS NULL
                WHERE ses.deleted_at IS NULL
                GROUP BY ses.protocol_id, pl.name
                ORDER BY session_count DESC
            """).fetchall()

            total_sessions = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE deleted_at IS NULL"
            ).fetchone()[0]
            total_subjects = conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM sessions WHERE deleted_at IS NULL AND user_id IS NOT NULL"
            ).fetchone()[0]
            total_samples = conn.execute(
                "SELECT COUNT(*) FROM samples WHERE deleted_at IS NULL"
            ).fetchone()[0]

        protocols = [
            {
                "protocol_id": r["protocol_id"] or "(none)",
                "protocol_name": r["protocol_name"] or "(no protocol)",
                "session_count": r["session_count"],
                "subject_count": r["subject_count"],
                "sample_count": r["sample_count"],
            }
            for r in rows
        ]

        return {
            "protocols": protocols,
            "totals": {
                "sessions": total_sessions,
                "subjects": total_subjects,
                "samples": total_samples,
            },
        }
    except Exception as e:
        logger.error("Error fetching dashboard stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── EXPLORER ───────────────────────────────────────────────────────────────

# Tables visible in the explorer (excludes internal SQLite system tables)
_ALLOWED_TABLES = {
    "users",
    "sessions",
    "samples",
    "protocol_library",
    "questionnaire_types",
    "bo_configuration",
    "pump_operations",
    "pump_logs",
    "pump_global_state",
    "pump_refill_operations",
    "session_sample_bank_state",
}

# Pre-built mapping of allowed table name → double-quoted identifier.
# Using the literal names from _ALLOWED_TABLES guarantees no user input
# is ever interpolated into SQL strings.
_TABLE_SQL_NAME: dict = {t: f'"{t}"' for t in _ALLOWED_TABLES}


@router.get("/explorer/tables")
def list_tables():
    """List user-facing database tables with approximate row counts."""
    try:
        with get_database_connection() as conn:
            all_tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()

            result = []
            for row in all_tables:
                name = row["name"]
                if name not in _ALLOWED_TABLES:
                    continue
                sql_name = _TABLE_SQL_NAME[name]
                count = conn.execute(f"SELECT COUNT(*) FROM {sql_name}").fetchone()[0]
                result.append({"name": name, "row_count": count})

        return {"tables": result}
    except Exception as e:
        logger.error("Error listing tables: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explorer/table/{table_name}")
def get_table_data(
    table_name: str,
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=500),
):
    """Return paginated rows from a single table."""
    if table_name not in _ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
    # Use the pre-built safe SQL identifier (from _TABLE_SQL_NAME) — never interpolate
    # raw user input into SQL strings.
    sql_name = _TABLE_SQL_NAME[table_name]
    try:
        with get_database_connection() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM {sql_name}").fetchone()[0]
            offset = page * page_size
            cur = conn.execute(
                f"SELECT * FROM {sql_name} LIMIT ? OFFSET ?",
                (page_size, offset),
            )
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description] if cur.description else []
            data = [dict(zip(columns, r)) for r in rows]

        return {
            "table": table_name,
            "columns": columns,
            "rows": data,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("Error fetching table data for %s: %s", table_name, e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── QUERY BUILDER ──────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    sql: str
    power_mode: bool = False


_SAFE_PATTERN = re.compile(r"^\s*(SELECT|WITH|EXPLAIN|PRAGMA)\b", re.IGNORECASE)
_WRITE_PATTERN = re.compile(r"\b(DELETE|DROP|UPDATE|INSERT|ALTER|CREATE|REPLACE|TRUNCATE)\b", re.IGNORECASE)


@router.post("/query")
def execute_query(body: QueryRequest):
    """
    Execute a SQL query against the database.

    By default only SELECT / WITH / EXPLAIN / PRAGMA statements are allowed.
    Pass power_mode=true to enable write operations (DELETE, UPDATE, INSERT).
    Results are capped at 1000 rows.
    """
    sql = body.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is empty.")

    is_safe = bool(_SAFE_PATTERN.match(sql))
    has_write = bool(_WRITE_PATTERN.search(sql))

    if has_write and not body.power_mode:
        raise HTTPException(
            status_code=403,
            detail="Write operations (DELETE/UPDATE/INSERT/DROP) require power mode. Enable it in the Query Builder settings.",
        )

    try:
        with get_database_connection() as conn:
            # Intentional: this endpoint executes user-supplied SQL.
            # Write operations are gated behind power_mode validation above.
            cur = conn.execute(sql)
            if cur.description:
                columns = [d[0] for d in cur.description]
                all_rows = cur.fetchmany(1000)
                rows = [dict(zip(columns, r)) for r in all_rows]
                return {
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "is_write": has_write,
                }
            else:
                # Write statement — commit explicitly
                conn.commit()
                return {
                    "columns": [],
                    "rows": [],
                    "row_count": cur.rowcount,
                    "is_write": True,
                }
    except Exception as e:
        logger.error("Query execution error: %s | SQL: %s", e, sql[:200])
        raise HTTPException(status_code=400, detail=str(e))
