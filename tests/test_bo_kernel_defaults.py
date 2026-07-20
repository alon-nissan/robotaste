"""
Bayesian Optimization Kernel Default Tests

Regression tests for the GP length-scale collapse bug found after the
normalization-frame fix (see test_bo_normalization.py): even with training
and candidates sharing one normalization frame, the fitted length scale (ℓ)
collapsed to the bounds floor (0.031, just above the old default of 0.01) on
real session data, because ℓ isn't reliably identifiable from a handful of
clustered, noisy human ratings with near-duplicate inputs and conflicting
outputs. This produced a near-flat UCB acquisition surface, so BO clustered
suggestions in a narrow band instead of exploring the configured range.

This was verified empirically: the log marginal likelihood for the real data
genuinely peaks at ℓ≈0.03 (the optimizer wasn't misbehaving), and raising
`alpha` alone barely moved that peak (1e-3 -> 0.4 only shifted argmax ℓ from
0.02 to 0.05). The fix instead raises the length_scale_bounds floor (which
IS the decisive lever) together with alpha (to keep predictive uncertainty
bounded rather than blowing up), and adds validation so a protocol override
can't reintroduce the pathological floor.

These tests confirm: the new defaults, the validation clamps, and the
seed-diversity diagnostic added alongside them.
"""

import logging

import numpy as np
import pytest
from unittest.mock import patch

from robotaste.config.bo_config import (
    DEFAULT_BO_CONFIG,
    get_default_bo_config,
    validate_bo_config,
)
from robotaste.core.bo_engine import RoboTasteBO, generate_candidate_grid_2d
from robotaste.core.bo_utils import get_ingredient_ranges_for_training
import robotaste.core.bo_utils as bo_utils


# Real recorded samples from the sugar-NaCl protocol run that surfaced this
# bug (session c825484a-..., cycles 1-6, used to train the cycle-7 suggestion).
REAL_SEED_X = np.array(
    [
        [120.0, 0.0],
        [120.0, 10.0],
        [122.0, 12.0],
        [119.47, 0.0],
        [120.53, 0.0],
        [119.47, 9.47],
    ]
)
REAL_SEED_Y = np.array([5.67, 6.12, 4.75, 4.79, 5.85, 6.13])
REAL_RANGES = {"Sucrose": (110.0, 130.0), "NaCl": (0.0, 20.0)}


def test_default_config_has_safe_kernel_bounds():
    """The floor must be raised well above the value that let ℓ collapse to
    0.031 on real data, and alpha raised so bounded uncertainty doesn't
    require a near-zero noise term."""
    assert DEFAULT_BO_CONFIG["length_scale_bounds"][0] >= 0.3
    assert DEFAULT_BO_CONFIG["length_scale_initial"] >= DEFAULT_BO_CONFIG["length_scale_bounds"][0]
    assert DEFAULT_BO_CONFIG["alpha"] >= 0.05


def test_validate_clamps_pathological_length_scale_floor():
    """A protocol override can't reintroduce the collapse-prone floor."""
    config = {**get_default_bo_config(), "length_scale_bounds": [0.001, 10.0]}
    validated = validate_bo_config(config)
    assert validated["length_scale_bounds"][0] == pytest.approx(0.05)


def test_validate_allows_smaller_but_not_pathological_floor():
    """A deliberately smaller floor (e.g. for a high-sample-count protocol)
    above the hard safety minimum should pass through untouched."""
    config = {**get_default_bo_config(), "length_scale_bounds": [0.08, 10.0]}
    validated = validate_bo_config(config)
    assert validated["length_scale_bounds"][0] == pytest.approx(0.08)


def test_validate_clamps_length_scale_initial_into_bounds():
    config = {
        **get_default_bo_config(),
        "length_scale_bounds": [0.5, 10.0],
        "length_scale_initial": 0.1,
    }
    validated = validate_bo_config(config)
    assert validated["length_scale_initial"] == pytest.approx(0.5)


def test_validate_invalid_bounds_falls_back_to_safe_default():
    config = {**get_default_bo_config(), "length_scale_bounds": [5.0, 1.0]}  # min >= max
    validated = validate_bo_config(config)
    assert validated["length_scale_bounds"] == [0.3, 10.0]


def test_real_data_no_longer_collapses_length_scale():
    """Refit the GP on the actual samples that produced ℓ=0.031 under the old
    defaults; with the new defaults ℓ must not collapse to the old floor."""
    config = validate_bo_config(get_default_bo_config())
    bo = RoboTasteBO(["Sucrose", "NaCl"], REAL_RANGES, config=config)
    bo.fit(REAL_SEED_X, REAL_SEED_Y)

    fitted_ls = float(bo.gp.kernel_.k2.length_scale)
    assert fitted_ls >= config["length_scale_bounds"][0]
    # Must not have collapsed anywhere near the OLD pathological value.
    assert fitted_ls > 0.1


def test_real_data_uncertainty_stays_bounded():
    """With the new floor+alpha together, predictive sigma across the full
    candidate grid must stay bounded (the floor-only change, without raising
    alpha, let sigma blow up to ~9 in testing)."""
    config = validate_bo_config(get_default_bo_config())
    bo = RoboTasteBO(["Sucrose", "NaCl"], REAL_RANGES, config=config)
    bo.fit(REAL_SEED_X, REAL_SEED_Y)

    candidates = generate_candidate_grid_2d((110, 130), (0, 20), n_points=20)
    _, sigma = bo.predict(candidates, return_std=True)
    assert sigma.max() < 3.0


def test_real_data_suggestions_spread_toward_range_extremes():
    """End-to-end: reproduce the cycle 4 suggestion (trained on the first 3
    real samples) and confirm BO reaches toward the configured range rather
    than clustering within ~2mM of the seed cluster, as it did before this fix."""
    config = validate_bo_config(get_default_bo_config())
    config["acquisition_function"] = "ucb"
    config["adaptive_acquisition"] = True
    config["exploration_budget"] = 0.6
    config["kappa_exploration"] = 4
    config["kappa_exploitation"] = 1.5

    X, y = REAL_SEED_X[:3], REAL_SEED_Y[:3]
    bo = RoboTasteBO(["Sucrose", "NaCl"], REAL_RANGES, config=config)
    bo.fit(X, y)

    candidates = generate_candidate_grid_2d((110, 130), (0, 20), n_points=20)
    suggestion = bo.suggest_next_sample(candidates, current_cycle=4, max_cycles=8)
    suc = suggestion["best_candidate_dict"]["Sucrose"]

    # Before this fix, cycle-4 landed at Sucrose=119.47 (essentially inside
    # the 118-122 seed cluster). The new defaults should reach meaningfully
    # further toward the configured [110, 130] extremes.
    assert suc <= 115.0 or suc >= 125.0


def test_seed_diversity_warning_for_clustered_samples(caplog):
    """Seed samples spanning only a small slice of the configured range must
    trigger a diagnostic warning naming the ingredient."""
    session = {
        "experiment_config": {
            "ingredients": [
                {"name": "Sucrose", "min_concentration": 110, "max_concentration": 130},
            ]
        }
    }
    # 2 mM of observed span inside a 20 mM configured range = 10% coverage.
    X = np.array([[120.0], [121.0], [122.0]])

    with patch.object(bo_utils.sql, "get_session", return_value=session):
        with caplog.at_level(logging.WARNING):
            get_ingredient_ranges_for_training("fake-session", ["Sucrose"], X)

    assert any("Sucrose" in r.message and "coverage" in r.message for r in caplog.records)


def test_no_seed_diversity_warning_for_well_spread_samples(caplog):
    session = {
        "experiment_config": {
            "ingredients": [
                {"name": "Sucrose", "min_concentration": 110, "max_concentration": 130},
            ]
        }
    }
    # 18 mM of observed span inside a 20 mM configured range = 90% coverage.
    X = np.array([[111.0], [120.0], [129.0]])

    with patch.object(bo_utils.sql, "get_session", return_value=session):
        with caplog.at_level(logging.WARNING):
            get_ingredient_ranges_for_training("fake-session", ["Sucrose"], X)

    assert not any("coverage" in r.message for r in caplog.records)
