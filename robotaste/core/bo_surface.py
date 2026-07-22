"""
Post-hoc BO response-surface computation.

Shared by the live BO model endpoint (api/routers/sessions.py::get_bo_model)
and the Analysis Hub's post-hoc "BO Surfaces" tab (api/routers/analysis.py).

Unlike the live endpoint, callers here can request the surface as it existed
after only the first N cycles (`up_to_cycle`), by training on a truncated,
chronologically-ordered slice of the session's training data. Ranges are
always frozen from the FULL session (protocol-configured ingredient ranges,
or a data-derived fallback spanning all cycles) so every partial-cycle
surface — and every participant's surface, when they share a protocol — is
normalized on the exact same grid. That's what makes replay animations and
cross-participant comparisons valid instead of comparing apples to oranges.

Author: RoboTaste Team
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from robotaste.data.database import get_training_data, get_bo_config
from robotaste.core.bo_engine import train_bo_model
from robotaste.core.bo_utils import get_ingredient_ranges_for_training

logger = logging.getLogger(__name__)

# Points per dimension for the visualization grid (25x25 = 625 candidates).
# Matches api/routers/sessions.py::get_bo_model so live and post-hoc surfaces
# render at the same resolution.
GP_GRID_SIZE = 25

# A GP needs at least this many points to fit; below it train_bo_model()
# itself refuses (min_samples_for_bo default), so replay never goes lower.
MIN_SAMPLES_FOR_SURFACE = 3


def compute_bo_surface_2d(
    session_id: str,
    experiment_config: Dict[str, Any],
    up_to_cycle: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Compute a 2D GP response surface for a session, optionally truncated to
    the first `up_to_cycle` chronological samples (post-hoc "replay" mode).

    Returns None if the session isn't a 2-ingredient BO experiment, or there
    isn't enough data to train even at full cycle count. Otherwise returns a
    dict shaped like BOModel2D (frontend/src/types/index.ts) plus:
      - ingredient_names, target_column
      - n_cycles_total: total trainable samples available for this session
      - n_cycles_used: samples actually used to train this surface
      - mean_sigma: grid-average predicted uncertainty (a scalar summary)

    Args:
        session_id: Session UUID.
        experiment_config: The session's experiment_config dict. Callers
            already have this from get_session(), so it isn't refetched here.
        up_to_cycle: If given, train only on the first N chronological
            samples instead of all of them (post-hoc replay). Clamped to
            [MIN_SAMPLES_FOR_SURFACE, n_cycles_total].
    """
    ingredients = experiment_config.get("ingredients", [])
    if len(ingredients) != 2:
        return None

    training_data = get_training_data(session_id)
    if training_data is None or len(training_data) < MIN_SAMPLES_FOR_SURFACE:
        return None

    ingredient_names = [ing.get("name", "") for ing in ingredients]
    target_column = training_data.columns[-1]
    n_cycles_total = len(training_data)

    # Freeze the normalization frame from the FULL dataset before truncating,
    # so every up_to_cycle slice (and every other session sharing this
    # protocol) trains and predicts on identical axes.
    X_full = training_data[ingredient_names].to_numpy()
    ranges = get_ingredient_ranges_for_training(session_id, ingredient_names, X_full)

    df = training_data
    if up_to_cycle is not None:
        n = max(MIN_SAMPLES_FOR_SURFACE, min(up_to_cycle, n_cycles_total))
        df = training_data.iloc[:n]
    n_cycles_used = len(df)

    if n_cycles_used < MIN_SAMPLES_FOR_SURFACE:
        return None

    bo_config = get_bo_config(session_id)
    model = train_bo_model(
        df,
        ingredient_names,
        target_column,
        bo_config=bo_config,
        concentration_ranges=ranges,
    )
    if model is None:
        return None

    acquisition_fn_name = (bo_config or {}).get("acquisition_function", "ei")

    def acquisition(candidates: np.ndarray) -> np.ndarray:
        if acquisition_fn_name == "ucb":
            return model.upper_confidence_bound(candidates)
        return model.expected_improvement(candidates)

    name_x, name_y = ingredient_names[0], ingredient_names[1]
    range_x, range_y = ranges[name_x], ranges[name_y]

    x_vals = np.linspace(range_x[0], range_x[1], GP_GRID_SIZE)
    # y descending so grid row 0 is the top of the rendered heatmap/surface,
    # matching the live BOVisualization2D convention (HeatmapPanel is
    # row-major).
    y_vals = np.linspace(range_y[1], range_y[0], GP_GRID_SIZE)
    xv, yv = np.meshgrid(x_vals, y_vals)
    candidates = np.column_stack([xv.ravel(), yv.ravel()])

    mu, sigma = model.predict(candidates, return_std=True)
    acq = acquisition(candidates)

    return {
        "predictions": {
            "x": x_vals.tolist(),
            "y": y_vals.tolist(),
            "mean": mu.reshape(GP_GRID_SIZE, GP_GRID_SIZE).tolist(),
            "std": sigma.reshape(GP_GRID_SIZE, GP_GRID_SIZE).tolist(),
            "acquisition": acq.reshape(GP_GRID_SIZE, GP_GRID_SIZE).tolist(),
        },
        "observations": {
            "x": df[name_x].tolist(),
            "y": df[name_y].tolist(),
            "z": df[target_column].tolist(),
        },
        "ingredient_names": [name_x, name_y],
        "target_column": target_column,
        "n_cycles_total": n_cycles_total,
        "n_cycles_used": n_cycles_used,
        "mean_sigma": float(np.mean(sigma)),
    }


def compute_bo_calibration(
    session_id: str,
    experiment_config: Dict[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    """
    Walk a 2-ingredient BO session's samples in chronological order, training
    a fresh GP on cycles 1..N and predicting the response at the point
    actually sampled next (cycle N+1). Powers the post-hoc "predicted vs.
    observed" calibration scatter and per-cycle summary table in the
    Analysis Hub's BO Surfaces tab.

    Returns None if the session isn't a 2-ingredient BO experiment or there
    isn't at least one cycle beyond the minimum trainable set. Otherwise
    returns one row per cycle N+1 in [MIN_SAMPLES_FOR_SURFACE + 1, n_cycles]:
        {
          "cycle": int,                        # the cycle being predicted
          "point": {ingredient_name: value},    # the point actually sampled
          "observed": float,                    # actual response at that cycle
          "predicted": float,                   # GP mean, trained on cycles < N
          "uncertainty": float,                 # GP sigma at that point
          "abs_error": float,
        }
    Cycles that fail to train (e.g. a transient data issue) are skipped
    rather than aborting the whole walk.
    """
    ingredients = experiment_config.get("ingredients", [])
    if len(ingredients) != 2:
        return None

    training_data = get_training_data(session_id)
    if training_data is None or len(training_data) < MIN_SAMPLES_FOR_SURFACE + 1:
        return None

    ingredient_names = [ing.get("name", "") for ing in ingredients]
    target_column = training_data.columns[-1]
    n_total = len(training_data)

    # Same frozen normalization frame as compute_bo_surface_2d, so calibration
    # predictions are made in the same coordinate system as the surfaces.
    X_full = training_data[ingredient_names].to_numpy()
    ranges = get_ingredient_ranges_for_training(session_id, ingredient_names, X_full)
    bo_config = get_bo_config(session_id)

    rows: List[Dict[str, Any]] = []
    for n in range(MIN_SAMPLES_FOR_SURFACE, n_total):
        df_train = training_data.iloc[:n]
        model = train_bo_model(
            df_train,
            ingredient_names,
            target_column,
            bo_config=bo_config,
            concentration_ranges=ranges,
        )
        if model is None:
            continue

        next_row = training_data.iloc[n]
        next_point = next_row[ingredient_names].to_numpy(dtype=float).reshape(1, -1)
        mu, sigma = model.predict(next_point, return_std=True)
        observed = float(next_row[target_column])
        predicted = float(mu[0])

        rows.append({
            "cycle": n + 1,
            "point": {name: float(next_row[name]) for name in ingredient_names},
            "observed": observed,
            "predicted": predicted,
            "uncertainty": float(sigma[0]),
            "abs_error": abs(observed - predicted),
        })

    return rows
