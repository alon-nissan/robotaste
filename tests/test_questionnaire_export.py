"""
Tests for analysis/export support of the multi-scale questionnaire types:
flatten_answers(), the Excel and CSV exports, the dose-response endpoint,
the bo_cycle_analysis view and the example protocols that use scale presets.
"""

import copy
import io
import json
import os
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import pytest

from robotaste.config.protocols import validate_protocol
from robotaste.config.questionnaire import flatten_answers

QUESTIONS = [
    {"id": "sweetness", "label": "How sweet?", "preset": "glms", "required": True},
    {"id": "tastes", "label": "Which tastes?", "preset": "cata_basic_tastes"},
    {
        "id": "rank",
        "label": "Rank",
        "type": "ranking",
        "options": [{"value": "juice", "label": "Juice"}, {"value": "soda", "label": "Soda"}],
    },
    {"id": "comment", "label": "Comments", "type": "text_area"},
]


# ─── flatten_answers ────────────────────────────────────────────────────────


def test_flatten_expands_cata_ranking_and_meta():
    flat = flatten_answers(
        {
            "sweetness": 17.0,
            "tastes": ["sweet", "bitter"],
            "rank": ["soda", "juice"],
            "comment": "nice",
            "is_final": True,
            "legacy_key": [1, 2],
        },
        QUESTIONS,
        {"sweetness": {"interacted": True, "rt_ms": 1200, "n_changes": 2}},
    )
    assert flat["sweetness"] == 17.0
    # Every configured CATA option gets a column, selected or not
    assert flat["tastes__sweet"] == 1 and flat["tastes__bitter"] == 1
    assert flat["tastes__sour"] == 0 and flat["tastes__umami"] == 0
    assert flat["tastes__n_selected"] == 2
    assert flat["rank__rank__juice"] == 2 and flat["rank__rank__soda"] == 1
    assert flat["comment"] == "nice"
    assert flat["sweetness__interacted"] == 1
    assert flat["sweetness__rt_ms"] == 1200
    assert flat["sweetness__n_changes"] == 2
    assert "is_final" not in flat
    assert flat["legacy_key"] == "1; 2"  # unknown list answers pass through joined
    # Column order follows the questionnaire
    keys = list(flat)
    assert keys.index("sweetness") < keys.index("tastes__sweet") < keys.index("rank__rank__juice")


def test_flatten_empty_cata_and_without_meta():
    flat = flatten_answers({"sweetness": 1, "tastes": []}, QUESTIONS, {"sweetness": {"rt_ms": 5}}, include_meta=False)
    assert flat["tastes__n_selected"] == 0
    assert all(flat[f"tastes__{t}"] == 0 for t in ["sweet", "sour", "salty", "bitter", "umami"])
    assert not any(k.endswith("__rt_ms") for k in flat)


def test_flatten_without_questionnaire_passes_through():
    assert flatten_answers({"overall_liking": 6, "timestamp": "x"}, None) == {"overall_liking": 6}


# ─── Example protocols ──────────────────────────────────────────────────────

PROTOCOLS = Path(__file__).resolve().parent.parent / "protocols"


@pytest.mark.parametrize("name", ["glms_sweetness_example.json", "vas_liking_bo_example.json"])
def test_example_protocols_validate(name):
    ok, errors = validate_protocol(json.loads((PROTOCOLS / name).read_text()))
    assert ok, errors


# ─── Exports & analysis on a real session ───────────────────────────────────


@pytest.fixture
def test_db(monkeypatch):
    import robotaste.data.database as database

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    monkeypatch.setattr(database, "DB_PATH", tmp.name)
    database.init_database()
    yield tmp.name
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


def _run_session(answers_per_cycle, target="sweetness"):
    from robotaste.data.database import create_session
    from robotaste.data.protocol_repo import create_protocol_in_db
    from api.routers import sessions as api

    protocol = {
        "protocol_id": str(uuid.uuid4()),
        "name": f"Export test {uuid.uuid4().hex[:6]}",
        "version": "1.0",
        "ingredients": [{"name": "Sugar", "min_concentration": 0, "max_concentration": 100}],
        "sample_selection_schedule": [
            {"cycle_range": {"start": 1, "end": len(answers_per_cycle)}, "mode": "user_selected"}
        ],
        "stopping_criteria": {"max_cycles": len(answers_per_cycle), "min_cycles": 1},
        "questionnaire": {
            "questions": copy.deepcopy(QUESTIONS),
            "bayesian_target": {"variable": target, "higher_is_better": True},
        },
    }
    protocol_id = create_protocol_in_db(protocol)
    session_id, _ = create_session("Moderator")
    api.start_session(session_id, api.StartSessionRequest(protocol_id=protocol_id))
    for i, answers in enumerate(answers_per_cycle):
        api.submit_selection(session_id, api.SelectionRequest(concentrations={"Sugar": 10.0 * (i + 1)}))
        api.submit_response(
            session_id,
            api.ResponseRequest(
                answers=answers,
                answer_meta={"sweetness": {"interacted": True, "rt_ms": 1000 + i, "n_changes": 1}},
                is_final=False,
            ),
        )
    return protocol_id, session_id


ANSWERS = [
    {"sweetness": 6.0, "tastes": ["sweet"], "rank": ["juice", "soda"], "comment": "ok"},
    {"sweetness": 35.0, "tastes": ["sweet", "bitter"], "rank": ["soda", "juice"]},
]


async def _read_stream(response) -> bytes:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
    return b"".join(chunks)


def test_excel_export_expands_columns(test_db):
    import asyncio
    from api.routers.analysis import export_samples_excel

    protocol_id, session_id = _run_session(ANSWERS)
    response = export_samples_excel(protocol_id=protocol_id)
    df = pd.read_excel(io.BytesIO(asyncio.run(_read_stream(response))))

    for col in [
        "session_id",
        "selection_mode",
        "Sugar_concentration",
        "sweetness_rating",
        "tastes__sweet",
        "tastes__bitter",
        "tastes__n_selected",
        "rank__rank__juice",
        "comment_rating",
        "sweetness__rt_ms",
        "sweetness__interacted",
    ]:
        assert col in df.columns, f"missing {col}: {list(df.columns)}"
    assert list(df["tastes__bitter"]) == [0, 1]
    assert list(df["rank__rank__juice"]) == [1, 2]
    assert list(df["sweetness__rt_ms"]) == [1000, 1001]
    assert set(df["session_id"]) == {session_id}


def test_csv_export_uses_flattened_columns(test_db):
    from robotaste.data.database import export_session_csv

    _, session_id = _run_session(ANSWERS)
    df = pd.read_csv(io.StringIO(export_session_csv(session_id)))
    assert "q_tastes__sweet" in df.columns
    assert "q_sweetness__rt_ms" in df.columns
    assert list(df["q_sweetness"]) == [6.0, 35.0]


def test_dose_response_offers_numeric_and_cata_proportions(test_db):
    from api.routers.analysis import get_dose_response_data

    protocol_id, _ = _run_session(ANSWERS)
    data = get_dose_response_data(protocol_id=protocol_id)
    variables = data["response_variables"]
    assert "sweetness" in variables
    assert "tastes__sweet" in variables and "rank__rank__soda" in variables
    assert "comment" not in variables  # text is not a numeric response
    assert not any(v.endswith("__rt_ms") for v in variables)
    by_conc = {entry["concentrations"]["Sugar"]: entry["stats"] for entry in data["aggregated"]}
    assert by_conc[20.0]["tastes__bitter"]["mean"] == 1.0
    assert by_conc[10.0]["tastes__bitter"]["mean"] == 0.0


def test_bo_cycle_view_uses_session_target(test_db):
    from robotaste.data.database import get_database_connection

    _, session_id = _run_session(ANSWERS)
    with get_database_connection() as conn:
        # The view only lists BO cycles; mark the samples as such for the test.
        conn.execute(
            "UPDATE samples SET acquisition_function = 'ucb', predicted_value = 10 WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT target_variable, observed_rating, prediction_error FROM bo_cycle_analysis "
            "WHERE session_id = ? ORDER BY cycle_number",
            (session_id,),
        ).fetchall()
    assert [r["target_variable"] for r in rows] == ["sweetness", "sweetness"]
    assert [r["observed_rating"] for r in rows] == [6.0, 35.0]
    assert [r["prediction_error"] for r in rows] == [-4.0, 25.0]
