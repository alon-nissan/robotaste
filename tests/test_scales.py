"""
Tests for the scale registry (robotaste/config/scales.py) and the multi-scale
questionnaire support built on it: preset resolution, per-type config
validation, answer validation, BO target transforms, protocol validation,
and the /response endpoint (server-side validation, answer_meta, survey phases).
"""

import copy
import math
import os
import tempfile
import uuid

import pytest
from fastapi import HTTPException

from robotaste.config.scales import (
    SCALE_PRESETS,
    QUESTION_TYPES,
    resolve_question,
    resolve_questionnaire,
    validate_question_config,
    validate_answer,
)
from robotaste.config.questionnaire import (
    extract_target_variable,
    validate_questionnaire_response,
)
from robotaste.config.protocols import validate_protocol


# ─── Presets & resolution ───────────────────────────────────────────────────


@pytest.mark.parametrize("preset_id", sorted(SCALE_PRESETS))
def test_every_preset_is_a_valid_question(preset_id):
    question = {"id": "q", "label": "Rate", "preset": preset_id}
    assert validate_question_config(question) == []
    resolved = resolve_question(question)
    assert resolved["type"] in QUESTION_TYPES
    assert resolved["preset_version"] == SCALE_PRESETS[preset_id]["version"]


def test_glms_anchor_positions():
    anchors = resolve_question({"id": "q", "label": "x", "preset": "glms"})["anchors"]
    assert [(a["value"], a["label"]) for a in anchors] == [
        (0, "No sensation"),
        (1.4, "Barely detectable"),
        (6, "Weak"),
        (17, "Moderate"),
        (35, "Strong"),
        (53, "Very strong"),
        (100, "Strongest imaginable sensation of any kind"),
    ]


def test_resolve_applies_type_defaults_and_question_overrides():
    q = resolve_question(
        {
            "id": "sweet",
            "label": "Sweetness",
            "preset": "vas",
            "orientation": "vertical",
            "anchors": [
                {"value": 0, "label": "Not sweet"},
                {"value": 100, "label": "Extremely sweet"},
            ],
        }
    )
    assert q["type"] == "line_scale"
    assert q["orientation"] == "vertical"  # override wins
    assert q["anchors"][1]["label"] == "Extremely sweet"
    assert q["start_unmarked"] is True  # type default
    assert q["show_value"] is False
    assert q["inset_anchors"] is True  # preset value


def test_resolve_does_not_mutate_registry():
    q = resolve_question({"id": "q", "label": "x", "preset": "glms"})
    q["anchors"][0]["label"] = "changed"
    assert SCALE_PRESETS["glms"]["question"]["anchors"][0]["label"] == "No sensation"


def test_resolve_normalizes_string_options():
    q = resolve_question({"id": "q", "label": "x", "type": "multi_select", "options": ["a", "b"]})
    assert q["options"] == [{"value": "a", "label": "a"}, {"value": "b", "label": "b"}]


def test_legacy_slider_unchanged():
    raw = {"id": "s", "type": "slider", "label": "x", "min": 1, "max": 9, "default": 5}
    assert resolve_question(raw) == raw


def test_resolve_questionnaire_freezes_presets():
    resolved = resolve_questionnaire(
        {"questions": [{"id": "q", "label": "x", "preset": "gvas"}]}
    )
    assert resolved["questions"][0]["type"] == "line_scale"
    assert len(resolved["questions"][0]["anchors"]) == 2


# ─── Config validation ──────────────────────────────────────────────────────


def _errors(**question):
    return validate_question_config({"id": "q", "label": "x", **question})


def test_unknown_preset_and_type_rejected():
    assert any("unknown scale preset" in e for e in _errors(preset="nope"))
    assert any("unknown type" in e for e in _errors(type="nope"))
    assert any("missing 'type'" in e for e in _errors())


def test_line_scale_anchor_validation():
    assert any("outside" in e for e in _errors(
        type="line_scale", min=0, max=100, anchors=[{"value": 120, "label": "too high"}]
    ))
    assert any("increasing" in e for e in _errors(
        type="line_scale", min=0, max=100,
        anchors=[{"value": 50, "label": "a"}, {"value": 10, "label": "b"}],
    ))
    assert any("orientation" in e for e in _errors(preset="vas", orientation="diagonal"))
    assert any("min must be < max" in e for e in _errors(preset="vas", min=100, max=0))


def test_category_scale_validation():
    assert any("unique" in e for e in _errors(
        type="category_scale",
        options=[{"value": 1, "label": "a"}, {"value": 1, "label": "b"}],
    ))
    assert any("at least 2" in e for e in _errors(type="category_scale", options=[{"value": 1, "label": "a"}]))
    assert any("ideal_value" in e for e in _errors(preset="jar_5", ideal_value=9))


def test_multi_select_and_ranking_validation():
    assert any("max_selected" in e for e in _errors(type="multi_select", options=["a", "b"], max_selected=5))
    assert any("at least 2" in e for e in _errors(type="ranking", options=["a"]))
    assert _errors(type="multi_select", options=["a", "b"], min_selected=1, max_selected=2) == []


# ─── Answer validation ──────────────────────────────────────────────────────


def _answer_error(question, value):
    return validate_answer(resolve_question({"id": "q", "label": "x", **question}), value)


def test_answer_validation_per_type():
    glms = {"preset": "glms"}
    assert _answer_error(glms, 42.5) is None
    assert "out of range" in _answer_error(glms, 101)
    assert "number" in _answer_error(glms, "high")
    assert "number" in _answer_error(glms, True)

    assert _answer_error({"preset": "hedonic_9pt"}, 7) is None
    assert "not one of" in _answer_error({"preset": "hedonic_9pt"}, 7.5)

    me = {"preset": "magnitude_estimation"}
    assert _answer_error(me, 12.3) is None
    assert "positive" in _answer_error(me, 0)
    assert _answer_error({**me, "allow_zero": True}, 0) is None

    cata = {"preset": "cata_basic_tastes", "max_selected": 2}
    assert _answer_error(cata, ["sweet", "bitter"]) is None
    assert _answer_error(cata, []) is None
    assert "unknown option" in _answer_error(cata, ["spicy"])
    assert "at most" in _answer_error(cata, ["sweet", "sour", "salty"])

    rank = {"type": "ranking", "options": ["a", "b", "c"]}
    assert _answer_error(rank, ["c", "a", "b"]) is None
    assert "exactly once" in _answer_error(rank, ["a", "b"])

    assert _answer_error({"type": "dropdown", "options": ["x", "y"]}, "x") is None
    assert "not one of" in _answer_error({"type": "dropdown", "options": ["x", "y"]}, "z")


def test_validate_questionnaire_response_collects_errors():
    questionnaire = {
        "questions": [
            {"id": "intensity", "label": "How strong?", "preset": "glms", "required": True},
            {"id": "liking", "label": "Liking", "preset": "hedonic_9pt", "required": True},
            {"id": "notes", "label": "Notes", "type": "text_area"},
        ]
    }
    ok, err = validate_questionnaire_response({"intensity": 20, "liking": 6}, questionnaire)
    assert ok and err is None

    ok, err = validate_questionnaire_response({"intensity": 500, "notes": ""}, questionnaire)
    assert not ok
    assert "out of range" in err and "'liking' not answered" in err

    # Extra keys (e.g. metadata the client adds) are ignored
    ok, _ = validate_questionnaire_response(
        {"intensity": 1, "liking": 5, "participant_id": "p1"}, questionnaire
    )
    assert ok


# ─── BO target transforms ───────────────────────────────────────────────────


def _target_config(question, **target):
    return {
        "questions": [{"id": "t", "label": "x", **question}],
        "bayesian_target": {"variable": "t", "higher_is_better": True, **target},
    }


def test_glms_target_defaults_to_log10p1():
    value = extract_target_variable({"t": 99}, _target_config({"preset": "glms"}))
    assert value == pytest.approx(2.0)


def test_explicit_transform_overrides_preset_default():
    cfg = _target_config({"preset": "glms"}, transform="identity")
    assert extract_target_variable({"t": 35}, cfg) == pytest.approx(35)


def test_ideal_point_transform_uses_preset_ideal():
    cfg = _target_config({"preset": "jar_5"}, transform="ideal_point")
    assert extract_target_variable({"t": 3}, cfg) == 0
    assert extract_target_variable({"t": 5}, cfg) == -2
    assert extract_target_variable({"t": 1}, cfg) == -2


def test_log10_and_minimize_and_non_numeric():
    cfg = _target_config({"preset": "vas"}, transform="log10", higher_is_better=False)
    assert extract_target_variable({"t": 100}, cfg) == pytest.approx(-2.0)
    assert extract_target_variable({"t": 0}, cfg) is None
    assert extract_target_variable({"t": "abc"}, _target_config({"preset": "vas"})) is None


def test_legacy_slider_target_unchanged():
    cfg = _target_config({"type": "slider", "min": 1, "max": 9})
    assert extract_target_variable({"t": 7.5}, cfg) == 7.5


# ─── Protocol validation ────────────────────────────────────────────────────


def _protocol(questionnaire, mode="user_selected"):
    protocol = {
        "protocol_id": str(uuid.uuid4()),
        "name": f"Scale test {uuid.uuid4().hex[:6]}",
        "version": "1.0",
        "ingredients": [{"name": "Sugar", "min_concentration": 0, "max_concentration": 100}],
        "sample_selection_schedule": [{"cycle_range": {"start": 1, "end": 3}, "mode": mode}],
        "stopping_criteria": {"max_cycles": 3, "min_cycles": 3},
        "questionnaire": questionnaire,
    }
    if mode == "bo_selected":
        protocol["bayesian_optimization"] = {"enabled": True}
    return protocol


SCALE_QUESTIONNAIRE = {
    "questions": [
        {"id": "sweetness", "label": "How sweet?", "preset": "glms", "required": True},
        {"id": "liking", "label": "How much do you like it?", "preset": "hedonic_9pt", "required": True},
        {"id": "tastes", "label": "Which tastes do you notice?", "preset": "cata_basic_tastes"},
    ],
}


def test_protocol_without_target_valid_when_not_using_bo():
    ok, errors = validate_protocol(_protocol(copy.deepcopy(SCALE_QUESTIONNAIRE)))
    assert ok, errors


def test_protocol_using_bo_requires_numeric_target():
    q = copy.deepcopy(SCALE_QUESTIONNAIRE)
    ok, errors = validate_protocol(_protocol(q, mode="bo_selected"))
    assert not ok and any("bayesian_target" in e for e in errors)

    q["bayesian_target"] = {"variable": "tastes", "higher_is_better": True}
    ok, errors = validate_protocol(_protocol(q, mode="bo_selected"))
    assert not ok and any("numeric" in e for e in errors)

    q["bayesian_target"] = {"variable": "liking", "higher_is_better": True, "transform": "bogus"}
    ok, errors = validate_protocol(_protocol(q, mode="bo_selected"))
    assert not ok and any("transform" in e for e in errors)


def test_protocol_reports_bad_preset_question():
    q = copy.deepcopy(SCALE_QUESTIONNAIRE)
    q["questions"].append({"id": "bad", "label": "x", "preset": "glms", "min": 50, "max": 10})
    ok, errors = validate_protocol(_protocol(q))
    assert not ok and any("'bad'" in e for e in errors)


# ─── API: /response ─────────────────────────────────────────────────────────


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


def test_session_stores_resolved_questionnaire(test_db):
    from robotaste.data.database import get_session

    session_id = _start_session(_protocol(copy.deepcopy(SCALE_QUESTIONNAIRE)))
    questions = get_session(session_id)["experiment_config"]["questionnaire"]["questions"]
    assert questions[0]["type"] == "line_scale"
    assert questions[0]["anchors"][5]["value"] == 53
    assert questions[1]["type"] == "category_scale"


def test_response_validation_and_answer_meta(test_db):
    from api.routers import sessions as api
    from robotaste.data.database import get_session_samples, get_current_cycle

    session_id = _start_session(_protocol(copy.deepcopy(SCALE_QUESTIONNAIRE)))

    with pytest.raises(HTTPException) as exc:
        api.submit_response(
            session_id, api.ResponseRequest(answers={"sweetness": 150, "liking": 6})
        )
    assert exc.value.status_code == 422
    assert get_session_samples(session_id) == []

    meta = {"sweetness": {"interacted": True, "rt_ms": 3120, "preset": "glms"}}
    api.submit_response(
        session_id,
        api.ResponseRequest(
            answers={"sweetness": 17.0, "liking": 7, "tastes": ["sweet"]},
            answer_meta=meta,
            is_final=False,
        ),
    )
    samples = get_session_samples(session_id)
    assert len(samples) == 1
    assert samples[0]["questionnaire_answer"]["tastes"] == ["sweet"]
    assert samples[0]["answer_meta"] == meta
    assert get_current_cycle(session_id) == 2


def test_survey_phase_response_does_not_create_sample(test_db):
    from api.routers import sessions as api
    from robotaste.data.database import get_session, get_session_samples, get_current_cycle

    session_id = _start_session(_protocol(copy.deepcopy(SCALE_QUESTIONNAIRE)))
    cycle_before = get_current_cycle(session_id)

    result = api.submit_response(
        session_id,
        api.ResponseRequest(answers={"age_group": "25-34"}, phase_id="demographics"),
    )
    assert result["phase_id"] == "demographics"
    assert get_session_samples(session_id) == []
    assert get_current_cycle(session_id) == cycle_before
    stored = get_session(session_id)["experiment_config"]["_survey_responses"]["demographics"]
    assert stored[0]["answers"] == {"age_group": "25-34"}


def test_training_data_uses_glms_log_target(test_db):
    from api.routers import sessions as api
    from robotaste.data.database import get_training_data

    q = copy.deepcopy(SCALE_QUESTIONNAIRE)
    q["bayesian_target"] = {"variable": "sweetness", "higher_is_better": True}
    session_id = _start_session(_protocol(q))
    api.submit_selection(session_id, api.SelectionRequest(concentrations={"Sugar": 40.0}))
    api.submit_response(
        session_id,
        api.ResponseRequest(answers={"sweetness": 99, "liking": 5}, is_final=False),
    )
    df = get_training_data(session_id)
    assert list(df.columns)[-1] == "sweetness"
    assert df["sweetness"].iloc[0] == pytest.approx(math.log10(100))


def test_scale_presets_endpoint():
    from api.routers.protocols import get_scale_presets

    payload = get_scale_presets()
    ids = {p["id"] for p in payload["presets"]}
    assert {"vas", "gvas", "glms", "hedonic_9pt"} <= ids
    assert "line_scale" in payload["question_types"]
    assert "log10p1" in payload["target_transforms"]
