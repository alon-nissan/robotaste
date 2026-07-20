"""
Bayesian Optimization Normalization Tests

Regression tests for the feature-normalization frame used by the BO engine.

Background: the GP used to normalize training points to a range INFERRED from
observed data each cycle (`min(X)*0.8`, `max(X)*1.2`), while candidate points
were generated over the PROTOCOL'S CONFIGURED ingredient ranges. Because both
were pushed through the same [0,1] normalization using the (mismatched)
inferred range, candidates could land outside [0,1] (the GP extrapolating
beyond its training support), a tightly-clustered set of training points
could get crushed into a near-zero-width slice of the axis, the frame shifted
every cycle as more data arrived, and a constant-valued column (e.g. a
diluent, or an ingredient pinned at 0 in early cycles) could produce a
zero-width or inverted range and crash `RoboTasteBO.__init__`.

These tests confirm the fix: training now normalizes in the same frame as
candidate generation (the protocol's configured ranges), with a safe additive
fallback when no configured range is available.
"""

import numpy as np
import pytest
from unittest.mock import patch

from robotaste.core.bo_engine import (
    RoboTasteBO,
    generate_candidate_grid_2d,
    infer_range_with_padding,
)
from robotaste.core.bo_utils import get_ingredient_ranges_for_training
import robotaste.core.bo_utils as bo_utils


# Reproduces the first 3 cycles of the sugar-NaCl protocol run that surfaced
# this bug: protocols/sugar-nacl_mixture_concentration_test.json /
# protocols/NaCLSucroseBOTest.xlsx
SUGAR_NACL_PROTOCOL_INGREDIENTS = [
    {"name": "Sucrose", "min_concentration": 110, "max_concentration": 130},
    {"name": "NaCl", "min_concentration": 0, "max_concentration": 20},
    {"name": "Water", "min_concentration": 0, "max_concentration": 0, "is_diluent": True},
]
SEED_X = np.array(
    [
        [120.0, 0.0],
        [120.0, 10.0],
        [122.0, 12.0],
    ]
)
SEED_Y = np.array([5.67, 6.12, 4.75])


def _fake_session(ingredients):
    return {"experiment_config": {"ingredients": ingredients}}


def test_training_uses_configured_ranges_not_inferred():
    """Training range should come from the protocol config, matching candidates."""
    with patch.object(
        bo_utils.sql,
        "get_session",
        return_value=_fake_session(SUGAR_NACL_PROTOCOL_INGREDIENTS),
    ):
        ranges = get_ingredient_ranges_for_training(
            "fake-session", ["Sucrose", "NaCl"], SEED_X
        )

    assert ranges["Sucrose"] == (110.0, 130.0)
    assert ranges["NaCl"] == (0.0, 20.0)


def test_candidates_normalize_within_unit_interval():
    """Candidates generated over configured ranges must land in [0,1] after
    the model normalizes them for training — this is the core bug: previously
    candidates were normalized against a data-inferred range and could exceed
    1.0 (e.g. NaCl reached ~1.39 in the real run)."""
    with patch.object(
        bo_utils.sql,
        "get_session",
        return_value=_fake_session(SUGAR_NACL_PROTOCOL_INGREDIENTS),
    ):
        ranges = get_ingredient_ranges_for_training(
            "fake-session", ["Sucrose", "NaCl"], SEED_X
        )

    bo = RoboTasteBO(["Sucrose", "NaCl"], ranges)
    bo.fit(SEED_X, SEED_Y)

    candidates = generate_candidate_grid_2d((110, 130), (0, 20), n_points=20)
    normalized = bo._normalize_features(candidates)

    assert normalized.min() >= 0.0
    assert normalized.max() <= 1.0


def test_training_points_map_to_expected_configured_frame_positions():
    """Sucrose=120 in [110,130] -> 0.5; NaCl=10 in [0,20] -> 0.5."""
    with patch.object(
        bo_utils.sql,
        "get_session",
        return_value=_fake_session(SUGAR_NACL_PROTOCOL_INGREDIENTS),
    ):
        ranges = get_ingredient_ranges_for_training(
            "fake-session", ["Sucrose", "NaCl"], SEED_X
        )

    bo = RoboTasteBO(["Sucrose", "NaCl"], ranges)
    normalized = bo._normalize_features(SEED_X)

    assert normalized[0, 0] == pytest.approx(0.5)  # Sucrose 120
    assert normalized[1, 1] == pytest.approx(0.5)  # NaCl 10


def test_constant_column_with_no_configured_range_does_not_crash():
    """An ingredient absent from protocol config and constant across samples
    (e.g. a diluent, or salt pinned at 0 in early cycles) must not raise
    ValueError('min_c >= max_c') during RoboTasteBO construction/fit."""
    session = _fake_session(
        [{"name": "Sucrose", "min_concentration": 110, "max_concentration": 130}]
    )
    X = np.array([[120.0, 0.0], [120.0, 0.0], [122.0, 0.0]])  # NaCl constant, unconfigured

    with patch.object(bo_utils.sql, "get_session", return_value=session):
        ranges = get_ingredient_ranges_for_training(
            "fake-session", ["Sucrose", "NaCl"], X
        )

    assert ranges["NaCl"][0] < ranges["NaCl"][1]  # never zero/inverted span

    bo = RoboTasteBO(["Sucrose", "NaCl"], ranges)
    bo.fit(X, SEED_Y)  # must not raise
    assert bo.is_fitted


def test_degenerate_configured_range_falls_back_to_data():
    """A configured range with min >= max (e.g. a misconfigured diluent with
    min=max=0) must fall back to the data-derived range, not be used as-is."""
    session = _fake_session(
        [{"name": "Water", "min_concentration": 0, "max_concentration": 0}]
    )
    X = np.array([[5.0], [5.0], [5.0]])

    with patch.object(bo_utils.sql, "get_session", return_value=session):
        ranges = get_ingredient_ranges_for_training("fake-session", ["Water"], X)

    lo, hi = ranges["Water"]
    assert lo < hi
    bo = RoboTasteBO(["Water"], ranges)
    bo.fit(X, SEED_Y)  # must not raise


def test_infer_range_with_padding_never_zero_span():
    """The additive-padding fallback must never return a zero-width range,
    including for an all-zero column (the old multiplicative x0.8/x1.2 scheme
    produced (0.001, 0.0) here — an inverted range)."""
    lo, hi = infer_range_with_padding(np.array([0.0, 0.0, 0.0]))
    assert lo < hi

    lo, hi = infer_range_with_padding(np.array([120.0, 120.0]))
    assert lo < hi

    # Non-constant column: pad should be modest relative to span, not the old
    # magnitude-scaled 20%.
    lo, hi = infer_range_with_padding(np.array([110.0, 130.0]))
    assert lo < 110.0 < 130.0 < hi
    assert (hi - lo) < 30  # sane, not blown up by magnitude-based padding
