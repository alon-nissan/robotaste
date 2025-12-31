"""
Bayesian Optimization Configuration

Centralized BO configuration with defaults, validation, and extraction utilities.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import logging
import numpy as np
from typing import Dict, Any

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# DEFAULT CONFIGURATION
# ============================================================================

DEFAULT_BO_CONFIG = {
    # Core BO parameters
    "enabled": True,
    "min_samples_for_bo": 3,
    "acquisition_function": "ei",  # "ei" or "ucb"
    # Acquisition function parameters
    "ei_xi": 0.01,  # Exploration parameter for EI (static, overridden if adaptive enabled)
    "ucb_kappa": 2.0,  # Exploration parameter for UCB (static, overridden if adaptive enabled)
    # Adaptive acquisition parameters (time-varying exploration/exploitation)
    "adaptive_acquisition": True,  # Enable time-varying xi/kappa
    "exploration_budget": 0.25,  # Fraction of cycles for high exploration (0.25 = first 25%)
    "xi_exploration": 0.1,  # EI xi during exploration phase (high exploration)
    "xi_exploitation": 0.01,  # EI xi during exploitation phase (low exploration)
    "kappa_exploration": 3.0,  # UCB kappa during exploration phase (high exploration)
    "kappa_exploitation": 1.0,  # UCB kappa during exploitation phase (low exploration)
    # Gaussian Process kernel parameters
    "kernel_nu": 2.5,  # Matern smoothness: 0.5, 1.5, 2.5, or inf
    "length_scale_initial": 1.0,
    "length_scale_bounds": [0.1, 10.0],
    "constant_kernel_bounds": [1e-3, 1e3],
    # GP training parameters
    "alpha": 1e-3,  # Noise/regularization (changed from 1e-6 to 1e-3 for human data)
    "n_restarts_optimizer": 10,
    "normalize_y": True,
    "random_state": 42,
    # Advanced parameters
    "only_final_responses": True,  # Use only final responses for training
    "candidate_sampling_method": "auto",  # "grid", "lhs", or "auto"
    "n_candidates_grid": 400,  # For 2D grid (20*20)
    "n_candidates_lhs": 1000,  # For N-D Latin Hypercube
    # Stopping criteria (for session ending logic)
    "stopping_criteria": {
        "enabled": True,  # Enable convergence detection
        "min_cycles_1d": 10,  # Minimum cycles for 1D optimization
        "min_cycles_2d": 15,  # Minimum cycles for 2D optimization
        "max_cycles_1d": 30,  # Maximum cycles for 1D optimization
        "max_cycles_2d": 50,  # Maximum cycles for 2D optimization
        "ei_threshold": 0.001,  # EI below this indicates convergence
        "ucb_threshold": 0.01,  # UCB decrease threshold
        "stability_window": 5,  # Number of recent cycles to check for stability
        "stability_threshold": 0.05,  # Std dev of best values for stability
        "consecutive_required": 2,  # Require N consecutive converged detections
        "stopping_mode": "suggest_auto",  # "manual_only", "suggest_auto", "auto_with_minimum"
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_default_bo_config() -> Dict[str, Any]:
    """
    Get default BO configuration.

    Returns:
        Deep copy of DEFAULT_BO_CONFIG

    Example:
        >>> config = get_default_bo_config()
        >>> config["kernel_nu"]
        2.5
    """
    return DEFAULT_BO_CONFIG.copy()


def validate_bo_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize BO configuration.

    Corrects invalid values and warns about changes.

    Args:
        config: BO configuration dictionary

    Returns:
        Validated configuration (corrected if needed)

    Example:
        >>> bad_config = {"ei_xi": 5.0, "kernel_nu": 7.0}
        >>> validated = validate_bo_config(bad_config)
        >>> validated["ei_xi"]  # Will be clamped to valid range
        0.5
    """
    validated = config.copy()

    # Validate acquisition function
    if validated.get("acquisition_function") not in ["ei", "ucb"]:
        logger.warning(
            f"Invalid acquisition function: {validated.get('acquisition_function')}, using 'ei'"
        )
        validated["acquisition_function"] = "ei"

    # Validate numeric ranges
    if validated.get("ei_xi", 0) < 0 or validated.get("ei_xi", 0) > 1.0:
        clamped = np.clip(validated.get("ei_xi", 0.01), 0, 1)
        logger.warning(f"ei_xi out of range [0, 1], clamping to {clamped}")
        validated["ei_xi"] = float(clamped)

    if validated.get("ucb_kappa", 0) < 0.1 or validated.get("ucb_kappa", 0) > 10.0:
        clamped = np.clip(validated.get("ucb_kappa", 2.0), 0.1, 10)
        logger.warning(f"ucb_kappa out of range [0.1, 10], clamping to {clamped}")
        validated["ucb_kappa"] = float(clamped)

    if validated.get("min_samples_for_bo", 0) < 2:
        logger.warning("min_samples_for_bo must be >= 2, setting to 2")
        validated["min_samples_for_bo"] = 2

    if validated.get("kernel_nu") not in [0.5, 1.5, 2.5, float("inf")]:
        logger.warning(f"kernel_nu must be 0.5, 1.5, 2.5, or inf, using 2.5")
        validated["kernel_nu"] = 2.5

    if validated.get("alpha", 0) <= 0 or validated.get("alpha", 0) > 1.0:
        clamped = np.clip(validated.get("alpha", 1e-3), 1e-6, 1.0)
        logger.warning(f"alpha out of range (0, 1], clamping to {clamped}")
        validated["alpha"] = float(clamped)

    if validated.get("n_restarts_optimizer", 0) < 1:
        validated["n_restarts_optimizer"] = 1

    # Validate length scale bounds
    if len(validated.get("length_scale_bounds", [])) != 2:
        validated["length_scale_bounds"] = [0.1, 10.0]
    else:
        bounds = validated["length_scale_bounds"]
        if bounds[0] >= bounds[1]:
            logger.warning("Invalid length_scale_bounds, using defaults [0.1, 10.0]")
            validated["length_scale_bounds"] = [0.1, 10.0]

    return validated


def get_bo_config_from_experiment(experiment_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract BO configuration from experiment config.

    Args:
        experiment_config: Full experiment configuration

    Returns:
        BO configuration dict (with defaults if missing)

    Example:
        >>> experiment_config = {
        ...     "ingredients": [...],
        ...     "questionnaire_type": "hedonic",
        ...     "bayesian_optimization": {
        ...         "acquisition_function": "ucb",
        ...         "ucb_kappa": 3.0
        ...     }
        ... }
        >>> bo_config = get_bo_config_from_experiment(experiment_config)
        >>> bo_config["acquisition_function"]
        'ucb'
    """
    # Get BO section or use empty dict
    bo_section = experiment_config.get("bayesian_optimization", {})

    # Merge with defaults
    config = {**get_default_bo_config(), **bo_section}

    # Validate
    config = validate_bo_config(config)

    logger.info(
        f"Loaded BO config: acquisition={config['acquisition_function']}, "
        f"min_samples={config['min_samples_for_bo']}, kernel_nu={config['kernel_nu']}"
    )

    return config
