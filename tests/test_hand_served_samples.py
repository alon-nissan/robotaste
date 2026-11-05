"""
Tests for hand-served (no-pump) predetermined samples:
cup id/label propagation through cycle-info → selection → samples.selection_data,
and the moderator serving-plan endpoint.
"""

import copy
import os
import tempfile
import uuid

import pytest

from robotaste.config.protocol_schema import (
    get_predetermined_sample,
    get_predetermined_sample_entry,
)

INGREDIENTS = [
    {"name": "Sugar", "min_concentration": 0.0, "max_concentration": 100.0, "unit": "mM"},
]

QUESTIONNAIRE = {
    "name": "Sweetness",
    "questions": [
        {"id": "sweetness", "type": "slider", "label": "How sweet?", "min": 1, "max": 9, "default": 5}
    ],
    "bayesian_target": {"variable": "sweetness", "higher_is_better": True},
}


def _protocol(schedule, num_cycles):
    return {
        "protocol_id": str(uuid.uuid4()),
        "name": f"Hand served {uuid.uuid4().hex[:6]}",
        "version": "1.0",
        "ingredients": INGREDIENTS,
        "questionnaire": QUESTIONNAIRE,
        "sample_selection_schedule": schedule,
        "stopping_criteria": {"max_cycles": num_cycles, "min_cycles": num_cycles},
        "pump_config": {"enabled": False},
        "tasting_screen": {"enabled": True, "title": "Please taste cup {sample_id}"},
    }


ABSOLUTE_SCHEDULE = [
    {
        "cycle_range": {"start": 1, "end": 2},
        "mode": "predetermined_absolute",
        "predetermined_samples": [
            {"cycle": 1, "id": "372", "label": "Sugar low", "concentrations": {"Sugar": 10.0}},
            {"cycle": 2, "concentrations": {"Sugar": 50.0}},
        ],
    }
]

BANK_SAMPLES = [
    {"id": "A", "label": "No sugar", "concentrations": {"Sugar": 0.0}},
    {"id": "B", "label": "Low sugar", "concentrations": {"Sugar": 25.0}},
    {"id": "C", "label": "High sugar", "concentrations": {"Sugar": 75.0}},
]

BANK_SCHEDULE = [
    {
        "cycle_range": {"start": 1, "end": 3},
        "mode": "predetermined_randomized",
        "sample_bank": {"samples": BANK_SAMPLES, "design_type": "latin_square"},
    }
]


def test_predetermined_entry_carries_id_and_label():
    protocol = _protocol(ABSOLUTE_SCHEDULE, 2)
    entry = get_predetermined_sample_entry(protocol, 1)
    assert entry == {"id": "372", "label": "Sugar low", "concentrations": {"Sugar": 10.0}}
    # id/label are optional
    entry2 = get_predetermined_sample_entry(protocol, 2)
    assert entry2["id"] is None and entry2["concentrations"] == {"Sugar": 50.0}
    # Legacy helper still returns concentrations only
    assert get_predetermined_sample(protocol, 1) == {"Sugar": 10.0}
    assert get_predetermined_sample_entry(protocol, 3) is None


def test_protocol_with_ids_and_tasting_screen_validates():
    from robotaste.config.protocols import validate_protocol

    ok, errors = validate_protocol(_protocol(ABSOLUTE_SCHEDULE, 2))
    assert ok, errors


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


def _start_session(protocol):
    from robotaste.data.database import create_session
    from robotaste.data.protocol_repo import create_protocol_in_db
    from api.routers import sessions as api

    protocol_id = create_protocol_in_db(copy.deepcopy(protocol))
    assert protocol_id
    session_id, _ = create_session("Moderator")
    api.start_session(session_id, api.StartSessionRequest(protocol_id=protocol_id))
    return session_id


def _run_cycle(session_id, is_final=False):
    """Mimic the frontend: cycle-info → auto-submit selection → submit response."""
    from api.routers import sessions as api

    info = api.get_cycle_info(session_id)
    api.submit_selection(
        session_id,
        api.SelectionRequest(
            concentrations=info["concentrations"],
            selection_mode=info["mode"],
            selection_data=info.get("selection_data"),
        ),
    )
    api.submit_response(session_id, api.ResponseRequest(answers={"sweetness": 5.0}, is_final=is_final))
    return info


@pytest.mark.parametrize("schedule,num_cycles", [(ABSOLUTE_SCHEDULE, 2), (BANK_SCHEDULE, 3)])
def test_serving_plan_matches_served_cups_and_ids_are_persisted(test_db, schedule, num_cycles):
    from api.routers import sessions as api
    from robotaste.data.database import get_session_samples

    session_id = _start_session(_protocol(schedule, num_cycles))

    plan = api.get_serving_plan(session_id)
    assert plan["pump_enabled"] is False
    assert plan["total_cycles"] == num_cycles
    assert [e["status"] for e in plan["entries"]][0] == "current"
    planned = [(e["sample_id"], e["concentrations"]) for e in plan["entries"]]

    served = []
    for _ in range(num_cycles):
        info = _run_cycle(session_id)
        served.append((info["metadata"].get("sample_id"), info["concentrations"]))

    assert served == planned
    if schedule is BANK_SCHEDULE:
        assert sorted(sid for sid, _ in served) == ["A", "B", "C"]

    samples = get_session_samples(session_id)
    assert len(samples) == num_cycles
    for row, (sid, conc) in zip(samples, served):
        assert row["ingredient_concentration"] == conc
        assert row["selection_data"].get("sample_id") == sid

    plan_after = api.get_serving_plan(session_id)
    assert all(e["status"] == "done" for e in plan_after["entries"])
