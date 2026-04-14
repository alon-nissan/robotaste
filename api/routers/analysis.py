"""
Analysis Endpoints — Dose-response data for visualization dashboards.

Provides endpoints to query completed experiment data across sessions
and return structured results for charting (dose-response curves, etc.).
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
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
