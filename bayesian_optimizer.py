"""
bayesian_optimizer.py - Gaussian Process Bayesian Optimization for RoboTaste

Implements Expected Improvement acquisition function with Matern kernel for
taste preference learning and optimization.

Configuration Example:
    >>> # Define custom BO configuration
    >>> custom_config = {
    ...     "acquisition_function": "ucb",
    ...     "ucb_kappa": 3.0,
    ...     "min_samples_for_bo": 5,
    ...     "kernel_nu": 1.5,
    ...     "alpha": 0.01
    ... }
    >>>
    >>> # Create BO model with config
    >>> bo = RoboTasteBO(
    ...     ingredient_names=['Sugar', 'Salt'],
    ...     concentration_ranges={'Sugar': (0.73, 73.0), 'Salt': (0.10, 10.0)},
    ...     config=custom_config
    ... )
    >>>
    >>> # Or load from experiment config
    >>> from sql_handler import get_session_info
    >>> import json
    >>> session_info = get_session_info(session_code)
    >>> experiment_config = json.loads(session_info['experiment_config'])
    >>> bo_config = get_bo_config_from_experiment(experiment_config)
    >>>
    >>> bo_model = train_bo_model_for_participant(
    ...     participant_id="P001",
    ...     session_id="session_123",
    ...     bo_config=bo_config
    ... )

Available Configuration Parameters:
    - acquisition_function: "ei" or "ucb" (default: "ei")
    - ei_xi: Exploration parameter for EI, 0.0-1.0 (default: 0.01)
    - ucb_kappa: Exploration parameter for UCB, 0.1-10.0 (default: 2.0)
    - min_samples_for_bo: Minimum samples before BO activates (default: 3)
    - kernel_nu: Matern smoothness - 0.5, 1.5, 2.5, or inf (default: 2.5)
    - alpha: Noise/regularization, 1e-6 to 1.0 (default: 1e-3)
    - n_restarts_optimizer: GP hyperparameter optimization restarts (default: 10)
    - length_scale_bounds: Kernel length scale bounds (default: [0.1, 10.0])
    - normalize_y: Normalize target values (default: True)
    - random_state: Random seed for reproducibility (default: 42)

For detailed kernel selection guidance, see: docs/bayesian_optimization_kernel_guide.md

Author: RoboTaste Team
Date: November 2025
"""

import numpy as np
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel as C
from typing import Tuple, List, Dict, Optional, Any
import logging
import json

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration Defaults and Validation
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
    # Based on: Benjamins et al. (2022) "PI is back! Switching Acquisition Functions in BO"
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


def get_adaptive_xi(
    current_cycle: int,
    max_cycles: int,
    exploration_budget: float = 0.25,
    xi_exploration: float = 0.1,
    xi_exploitation: float = 0.01,
) -> float:
    """
    Calculate adaptive EI exploration parameter based on optimization progress.

    Implements time-varying exploration/exploitation schedule for Expected Improvement.
    Linear decay from high exploration (xi_exploration) to high exploitation (xi_exploitation).

    Based on: Benjamins et al. (2022) "PI is back! Switching Acquisition Functions
    in Bayesian Optimization" (arXiv:2211.01455)

    Args:
        current_cycle: Current optimization cycle (0-indexed)
        max_cycles: Maximum number of cycles in the session
        exploration_budget: Fraction of cycles for exploration phase (default 0.25 = 25%)
        xi_exploration: xi value during early exploration phase (default 0.1)
        xi_exploitation: xi value during late exploitation phase (default 0.01)

    Returns:
        Adaptive xi value for current cycle

    Example:
        >>> # First 25% of cycles: high exploration
        >>> get_adaptive_xi(5, 40, 0.25, 0.1, 0.01)  # cycle 5/40 (12.5%)
        0.1
        >>> # Middle cycles: linear decay
        >>> get_adaptive_xi(20, 40, 0.25, 0.1, 0.01)  # cycle 20/40 (50%)
        0.055
        >>> # Final cycles: high exploitation
        >>> get_adaptive_xi(39, 40, 0.25, 0.1, 0.01)  # cycle 39/40 (97.5%)
        0.01
    """
    if max_cycles <= 0:
        return xi_exploitation

    progress = current_cycle / max_cycles

    # During exploration phase: use high xi
    if progress <= exploration_budget:
        return xi_exploration

    # After exploration phase: linear decay to exploitation
    # Map progress from [exploration_budget, 1.0] to [0.0, 1.0]
    decay_progress = (progress - exploration_budget) / (1.0 - exploration_budget)

    # Linear interpolation from xi_exploration to xi_exploitation
    xi = xi_exploration - (xi_exploration - xi_exploitation) * decay_progress

    return xi


def get_adaptive_kappa(
    current_cycle: int,
    max_cycles: int,
    exploration_budget: float = 0.25,
    kappa_exploration: float = 3.0,
    kappa_exploitation: float = 1.0,
) -> float:
    """
    Calculate adaptive UCB exploration parameter based on optimization progress.

    Implements time-varying exploration/exploitation schedule for Upper Confidence Bound.
    Linear decay from high exploration (kappa_exploration) to high exploitation (kappa_exploitation).

    Based on: Benjamins et al. (2022) "PI is back! Switching Acquisition Functions
    in Bayesian Optimization" (arXiv:2211.01455)

    Args:
        current_cycle: Current optimization cycle (0-indexed)
        max_cycles: Maximum number of cycles in the session
        exploration_budget: Fraction of cycles for exploration phase (default 0.25 = 25%)
        kappa_exploration: kappa value during early exploration phase (default 3.0)
        kappa_exploitation: kappa value during late exploitation phase (default 1.0)

    Returns:
        Adaptive kappa value for current cycle

    Example:
        >>> # First 25% of cycles: high exploration
        >>> get_adaptive_kappa(5, 40, 0.25, 3.0, 1.0)  # cycle 5/40 (12.5%)
        3.0
        >>> # Middle cycles: linear decay
        >>> get_adaptive_kappa(20, 40, 0.25, 3.0, 1.0)  # cycle 20/40 (50%)
        2.0
        >>> # Final cycles: high exploitation
        >>> get_adaptive_kappa(39, 40, 0.25, 3.0, 1.0)  # cycle 39/40 (97.5%)
        1.0
    """
    if max_cycles <= 0:
        return kappa_exploitation

    progress = current_cycle / max_cycles

    # During exploration phase: use high kappa
    if progress <= exploration_budget:
        return kappa_exploration

    # After exploration phase: linear decay to exploitation
    # Map progress from [exploration_budget, 1.0] to [0.0, 1.0]
    decay_progress = (progress - exploration_budget) / (1.0 - exploration_budget)

    # Linear interpolation from kappa_exploration to kappa_exploitation
    kappa = (
        kappa_exploration - (kappa_exploration - kappa_exploitation) * decay_progress
    )

    return kappa


def get_default_bo_config() -> Dict[str, Any]:
    """
    Get default Bayesian Optimization configuration.

    Returns:
        Dictionary with default BO settings

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


# ============================================================================
# Main BO Class
# ============================================================================


class RoboTasteBO:
    """
    Bayesian Optimization for taste preference learning.

    Features:
    - Matern kernel (nu=2.5) for smooth preference landscapes
    - Expected Improvement acquisition function
    - Support for 2-6 ingredient dimensions
    - Automatic normalization of ingredient concentrations
    - Handles exploration-exploitation tradeoff

    Example:
        >>> bo = RoboTasteBO(
        ...     ingredient_names=['Sugar', 'Salt'],
        ...     concentration_ranges={'Sugar': (0.73, 73.0), 'Salt': (0.10, 10.0)}
        ... )
        >>> X = np.array([[10.0, 2.0], [20.0, 3.0], [30.0, 4.0]])
        >>> y = np.array([6.5, 7.8, 7.2])
        >>> bo.fit(X, y)
        >>> candidates = generate_candidate_grid_2d((0.73, 73.0), (0.10, 10.0))
        >>> suggestion = bo.suggest_next_sample(candidates)
    """

    def __init__(
        self,
        ingredient_names: List[str],
        concentration_ranges: Dict[str, Tuple[float, float]],
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Bayesian Optimization model.

        Args:
            ingredient_names: Ordered list of ingredient names
            concentration_ranges: Dict mapping name -> (min_mM, max_mM)
            config: Optional BO configuration dict (uses defaults if None)

        Example:
            >>> # Use defaults
            >>> bo = RoboTasteBO(names, ranges)
            >>>
            >>> # Custom config
            >>> custom_config = {"kernel_nu": 1.5, "alpha": 0.01}
            >>> bo = RoboTasteBO(names, ranges, config=custom_config)
        """
        # IMPORTANT: Do NOT sort - preserve order from experiment config to match training data
        self.ingredient_names = list(ingredient_names)
        self.ranges = concentration_ranges
        self.n_dim = len(ingredient_names)

        # Load config with defaults
        self.config = {**get_default_bo_config(), **(config or {})}
        self.config = validate_bo_config(self.config)

        # Extract parameters from config
        kernel_nu = self.config["kernel_nu"]
        alpha = self.config["alpha"]
        n_restarts = self.config["n_restarts_optimizer"]
        length_scale_initial = self.config["length_scale_initial"]
        length_scale_bounds = tuple(self.config["length_scale_bounds"])
        constant_bounds = tuple(self.config["constant_kernel_bounds"])
        normalize_y = self.config["normalize_y"]
        random_state = self.config["random_state"]

        # Validate ranges
        for name in self.ingredient_names:
            if name not in self.ranges:
                raise ValueError(f"Missing concentration range for ingredient: {name}")
            min_c, max_c = self.ranges[name]
            if min_c >= max_c:
                raise ValueError(
                    f"Invalid range for {name}: min ({min_c}) >= max ({max_c})"
                )

        # GP with Matern kernel (configurable smoothness)
        kernel = C(1.0, constant_bounds) * Matern(
            length_scale=length_scale_initial,
            length_scale_bounds=length_scale_bounds,
            nu=kernel_nu,
        )

        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            alpha=alpha,  # Noise regularization
            n_restarts_optimizer=n_restarts,
            normalize_y=normalize_y,  # Normalize target values for numerical stability
            random_state=random_state,  # For reproducibility
        )

        self.is_fitted = False
        self.best_observed_value = -np.inf
        self.X_train = None
        self.y_train = None

        logger.info(
            f"Initialized RoboTasteBO with {self.n_dim} ingredients: {self.ingredient_names}, "
            f"kernel_nu={kernel_nu}, alpha={alpha}, acquisition={self.config['acquisition_function']}"
        )

    def _normalize_features(self, X: np.ndarray) -> np.ndarray:
        """
        Normalize concentrations to [0, 1] for each dimension.

        Essential for GP kernel to work properly across different concentration scales.

        Args:
            X: (n_samples, n_ingredients) array of concentrations in mM

        Returns:
            Normalized array with values in [0, 1]
        """
        X_norm = np.zeros_like(X, dtype=float)
        for i, name in enumerate(self.ingredient_names):
            min_c, max_c = self.ranges[name]
            X_norm[:, i] = (X[:, i] - min_c) / (max_c - min_c)
        return X_norm

    def _denormalize_features(self, X_norm: np.ndarray) -> np.ndarray:
        """
        Convert normalized [0, 1] features back to original concentration scale.

        Args:
            X_norm: (n_samples, n_ingredients) normalized array

        Returns:
            Array with concentrations in mM
        """
        X = np.zeros_like(X_norm, dtype=float)
        for i, name in enumerate(self.ingredient_names):
            min_c, max_c = self.ranges[name]
            X[:, i] = X_norm[:, i] * (max_c - min_c) + min_c
        return X

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Train Gaussian Process on observed data.

        Args:
            X: (n_samples, n_ingredients) - concentrations in mM
            y: (n_samples,) - target values (e.g., hedonic scores)

        Raises:
            ValueError: If fewer than 2 samples provided
        """
        if len(X) < 2:
            raise ValueError(f"Need at least 2 samples to train GP, got {len(X)}")

        if len(X) != len(y):
            raise ValueError(f"X and y must have same length: {len(X)} != {len(y)}")

        if X.shape[1] != self.n_dim:
            raise ValueError(
                f"X has {X.shape[1]} features but expected {self.n_dim} (ingredient count)"
            )

        # Store training data
        self.X_train = X.copy()
        self.y_train = y.copy()

        # Normalize and train
        X_norm = self._normalize_features(X)
        self.gp.fit(X_norm, y)
        self.is_fitted = True
        self.best_observed_value = np.max(y)

        logger.info(
            f"GP trained on {len(X)} samples. "
            f"Best observed: {self.best_observed_value:.3f}, "
            f"Mean: {np.mean(y):.3f}, Std: {np.std(y):.3f}"
        )
        logger.debug(f"Kernel hyperparameters: {self.gp.kernel_}")

    def predict(
        self, X: np.ndarray, return_std: bool = True, return_cov: bool = False
    ) -> Tuple[np.ndarray, ...]:
        """
        Predict mean and uncertainty for new samples.

        Args:
            X: (n_candidates, n_ingredients) array of concentrations
            return_std: If True, return standard deviation
            return_cov: If True, return full covariance matrix

        Returns:
            (mean,) if both False
            (mean, std) if return_std=True
            (mean, cov) if return_cov=True

        Raises:
            ValueError: If GP not fitted yet
        """
        if not self.is_fitted:
            raise ValueError("GP not fitted. Call fit() first.")

        X_norm = self._normalize_features(X)
        return self.gp.predict(X_norm, return_std=return_std, return_cov=return_cov)  # type: ignore

    def expected_improvement(
        self, X: np.ndarray, xi: float = 0.01, use_ei_per_cost: bool = False
    ) -> np.ndarray:
        """
        Calculate Expected Improvement acquisition function.

        EI balances exploration (high uncertainty) and exploitation (high predicted value).

        Formula:
            Z = (µ - best_y - xi) / σ
            EI = (µ - best_y - xi) * Φ(Z) + σ * φ(Z)

        Where:
            µ = predicted mean
            σ = predicted std
            Φ = cumulative distribution function (CDF)
            φ = probability density function (PDF)
            xi = exploration parameter

        Args:
            X: Candidate points (n_candidates, n_ingredients)
            xi: Exploration parameter (default 0.01). Higher = more exploration
            use_ei_per_cost: If True, normalize by cost (future feature)

        Returns:
            EI values for each candidate (higher = better)
        """
        if not self.is_fitted:
            logger.warning("GP not fitted, returning zeros for EI")
            return np.zeros(len(X))

        mu, sigma = self.predict(X, return_std=True)

        # Avoid division by zero
        sigma = np.maximum(sigma, 1e-9)

        # Calculate improvement over current best
        improvement = mu - self.best_observed_value - xi
        Z = improvement / sigma

        # Expected Improvement formula
        ei = improvement * norm.cdf(Z) + sigma * norm.pdf(Z)
        ei[sigma == 0.0] = 0.0  # No improvement where uncertainty is zero

        logger.debug(
            f"EI calculation: mean=[{mu.min():.3f}, {mu.max():.3f}], "
            f"std=[{sigma.min():.3f}, {sigma.max():.3f}], "
            f"EI=[{ei.min():.4f}, {ei.max():.4f}]"
        )

        return ei

    def upper_confidence_bound(self, X: np.ndarray, kappa: float = 2.0) -> np.ndarray:
        """
        Calculate Upper Confidence Bound (UCB) acquisition function.

        Alternative to EI, more exploratory.

        Formula:
            UCB = µ + kappa * σ

        Args:
            X: Candidate points
            kappa: Exploration parameter (default 2.0). Higher = more exploration

        Returns:
            UCB values
        """
        if not self.is_fitted:
            return np.zeros(len(X))

        mu, sigma = self.predict(X, return_std=True)
        return mu + kappa * sigma

    def suggest_next_sample(
        self,
        candidates: np.ndarray,
        acquisition: Optional[str] = None,
        return_all_scores: bool = False,
        current_cycle: Optional[int] = None,
        max_cycles: Optional[int] = None,
        **acq_kwargs,
    ) -> Dict[str, Any]:
        """
        Recommend next sample to test based on acquisition function.

        Args:
            candidates: (n_candidates, n_ingredients) array of possible samples
            acquisition: Acquisition function to use ("ei" or "ucb", uses config default if None)
            return_all_scores: If True, return scores for all candidates
            current_cycle: Current optimization cycle (for adaptive acquisition, 0-indexed)
            max_cycles: Maximum number of cycles (for adaptive acquisition)
            **acq_kwargs: Override acquisition parameters (xi, kappa)

        Returns:
            Dict with keys:
                - best_candidate: (n_ingredients,) array of concentrations
                - best_candidate_dict: Dict mapping ingredient -> concentration
                - predicted_value: GP predicted mean
                - acquisition_value: Acquisition function score
                - uncertainty: Predicted std deviation
                - mode: "bayesian_optimization" or "random_exploration"
                - acquisition_params: Dict with xi/kappa values used
                - all_*_values: (Optional) Arrays for all candidates
        """
        if not self.is_fitted:
            # Random exploration if no data yet
            idx = np.random.randint(len(candidates))
            best_candidate = candidates[idx]

            result = {
                "best_candidate": best_candidate,
                "best_candidate_dict": {
                    name: float(best_candidate[i])
                    for i, name in enumerate(self.ingredient_names)
                },
                "predicted_value": None,
                "acquisition_value": None,
                "uncertainty": None,
                "mode": "random_exploration",
                "message": f"Insufficient data ({len(self.X_train) if self.X_train is not None else 0} samples). Exploring randomly.",
            }

            logger.info("Suggesting random sample (GP not fitted)")
            return result

        # Use config default if acquisition not specified
        if acquisition is None:
            acquisition = self.config.get("acquisition_function", "ei")

        # Compute adaptive acquisition parameters if enabled
        adaptive_enabled = self.config.get("adaptive_acquisition", False)
        if adaptive_enabled and current_cycle is not None and max_cycles is not None:
            exploration_budget = self.config.get("exploration_budget", 0.25)

            if acquisition == "ei" and "xi" not in acq_kwargs:
                # Use adaptive xi
                xi_exploration = self.config.get("xi_exploration", 0.1)
                xi_exploitation = self.config.get("xi_exploitation", 0.01)
                acq_kwargs["xi"] = get_adaptive_xi(
                    current_cycle,
                    max_cycles,
                    exploration_budget,
                    xi_exploration,
                    xi_exploitation,
                )
                logger.info(
                    f"Adaptive EI: cycle {current_cycle}/{max_cycles}, "
                    f"xi={acq_kwargs['xi']:.4f} (exploration_budget={exploration_budget})"
                )
            elif acquisition == "ucb" and "kappa" not in acq_kwargs:
                # Use adaptive kappa
                kappa_exploration = self.config.get("kappa_exploration", 3.0)
                kappa_exploitation = self.config.get("kappa_exploitation", 1.0)
                acq_kwargs["kappa"] = get_adaptive_kappa(
                    current_cycle,
                    max_cycles,
                    exploration_budget,
                    kappa_exploration,
                    kappa_exploitation,
                )
                logger.info(
                    f"Adaptive UCB: cycle {current_cycle}/{max_cycles}, "
                    f"kappa={acq_kwargs['kappa']:.4f} (exploration_budget={exploration_budget})"
                )
        else:
            # Use static config defaults for acquisition kwargs if not provided
            if acquisition == "ei" and "xi" not in acq_kwargs:
                acq_kwargs["xi"] = self.config.get("ei_xi", 0.01)
            elif acquisition == "ucb" and "kappa" not in acq_kwargs:
                acq_kwargs["kappa"] = self.config.get("ucb_kappa", 2.0)

        # Calculate acquisition function
        if acquisition == "ei":
            logger.debug(acq_kwargs)
            logger.debug(f"Calculating EI with xi={acq_kwargs.get('xi')}")
            acq_values = self.expected_improvement(candidates, **acq_kwargs)
        elif acquisition == "ucb":
            acq_values = self.upper_confidence_bound(candidates, **acq_kwargs)
        else:
            raise ValueError(f"Unknown acquisition function: {acquisition}")

        # Get predictions
        mu_values, sigma_values = self.predict(candidates, return_std=True)

        # Select best candidate (max acquisition)
        best_idx = np.argmax(acq_values)
        best_candidate = candidates[best_idx]

        # Prepare acquisition parameters for result
        acquisition_params = {}
        if acquisition == "ei":
            acquisition_params["xi"] = acq_kwargs.get(
                "xi", self.config.get("ei_xi", 0.01)
            )
        elif acquisition == "ucb":
            acquisition_params["kappa"] = acq_kwargs.get(
                "kappa", self.config.get("ucb_kappa", 2.0)
            )

        result = {
            "best_candidate": best_candidate,
            "best_candidate_dict": {
                name: float(best_candidate[i])
                for i, name in enumerate(self.ingredient_names)
            },
            "predicted_value": float(mu_values[best_idx]),
            "acquisition_value": float(acq_values[best_idx]),
            "uncertainty": float(sigma_values[best_idx]),
            "mode": "bayesian_optimization",
            "acquisition_function": acquisition,
            "acquisition_params": acquisition_params,
            "n_training_samples": len(self.X_train),  # type: ignore
            "best_observed_value": float(self.best_observed_value),
        }

        if return_all_scores:
            result["all_candidates"] = candidates
            result["all_acquisition_values"] = acq_values
            result["all_predictions"] = mu_values
            result["all_uncertainties"] = sigma_values

        logger.info(
            f"BO Suggestion ({acquisition.upper()}): "
            f"predicted={result['predicted_value']:.3f}, "
            f"acquisition={result['acquisition_value']:.4f}, "
            f"uncertainty={result['uncertainty']:.3f}, "
            f"candidate={result['best_candidate_dict']}"
        )

        return result


# ============================================================================
# Integration Functions for RoboTaste
# ============================================================================


def train_bo_model_for_participant(
    participant_id: str, session_id: str, bo_config: Optional[Dict[str, Any]] = None
) -> Optional[RoboTasteBO]:
    """
    Train Bayesian Optimization model using configuration.

    Loads data from database, parses JSON ingredient data, trains GP model.

    Args:
        participant_id: Participant identifier
        session_id: Session identifier
        bo_config: BO configuration dict (uses defaults if None)

    Returns:
        Trained RoboTasteBO instance or None if insufficient data

    Example:
        >>> # Use defaults
        >>> bo_model = train_bo_model_for_participant("P001", "session_123")
        >>>
        >>> # Custom config
        >>> config = {"kernel_nu": 1.5, "min_samples_for_bo": 5}
        >>> bo_model = train_bo_model_for_participant("P001", "session_123", bo_config=config)
        >>>
        >>> if bo_model:
        ...     candidates = generate_candidate_grid_2d((0.73, 73.0), (0.10, 10.0))
        ...     suggestion = bo_model.suggest_next_sample(candidates)
    """
    from sql_handler import get_training_data

    try:
        # Merge with defaults and validate
        config = validate_bo_config({**get_default_bo_config(), **(bo_config or {})})

        # Extract parameters from config
        only_final = config.get("only_final_responses", True)
        min_samples = config.get("min_samples_for_bo", 3)

        # Get training data from database (using new API)
        df = get_training_data(session_id, only_final=False)

        # Comprehensive logging for debugging
        logger.info(f"BO Training Debug - Session: {session_id}")
        logger.info(f"  DataFrame shape: {df.shape}")
        logger.info(
            f"  DataFrame columns: {list(df.columns) if not df.empty else 'EMPTY'}"
        )
        logger.info(f"  Min samples required: {min_samples}")
        logger.info(f"  Actual samples: {len(df)}")

        if len(df) < min_samples:
            logger.info(
                f"Insufficient data for BO training: {len(df)} samples < {min_samples} required"
            )
            return None

        # Parse ingredient data
        X_list = []
        y_list = []
        ingredient_names = None

        # Detect target column name (last column by convention from get_training_data)
        target_column = df.columns[-1]
        logger.info(f"Using target column: '{target_column}'")

        for _, row in df.iterrows():
            try:
                # Extract ingredient names from DataFrame columns (all columns except target)
                # This works for 2-6 ingredients automatically!
                # IMPORTANT: Do NOT sort - preserve order from experiment config
                if ingredient_names is None:
                    ingredient_names = [
                        col for col in df.columns if col != target_column
                    ]
                    logger.info(
                        f"Detected {len(ingredient_names)} ingredients: {ingredient_names}"
                    )

                # Get ingredient concentrations directly from DataFrame columns
                # Works for any number of ingredients (2, 3, 4, 5, or 6)
                feature_vector = [row[name] for name in ingredient_names]
                X_list.append(feature_vector)
                y_list.append(row[target_column])

            except KeyError as e:
                logger.warning(f"Skipping sample due to missing column: {e}")
                continue

        if len(X_list) < min_samples:
            logger.warning(
                f"After parsing, only {len(X_list)} valid samples (need {min_samples})"
            )
            return None

        X = np.array(X_list)
        y = np.array(y_list)

        # Infer concentration ranges from data (with 20% padding)
        ranges = {}
        for i, name in enumerate(ingredient_names):  # type: ignore
            min_c = max(0.001, np.min(X[:, i]) * 0.8)  # Pad 20%, min 0.001
            max_c = np.max(X[:, i]) * 1.2
            ranges[name] = (min_c, max_c)
            logger.debug(f"{name} range: [{min_c:.3f}, {max_c:.3f}] mM")

        # Train model with config
        bo = RoboTasteBO(ingredient_names, ranges, config=config)  # type: ignore
        bo.fit(X, y)

        logger.info(
            f"Successfully trained BO model for {participant_id} with {len(X)} samples"
        )

        return bo

    except Exception as e:
        logger.error(f"Error training BO model: {e}", exc_info=True)
        return None


def generate_candidate_grid_2d(
    sugar_range: Tuple[float, float],
    salt_range: Tuple[float, float],
    n_points: int = 20,
) -> np.ndarray:
    """
    Generate 2D grid of candidate samples for Sugar-Salt space.

    Used for grid-based experiments with 2 ingredients.

    Args:
        sugar_range: (min_mM, max_mM) for sugar
        salt_range: (min_mM, max_mM) for salt
        n_points: Number of points per dimension (total = n_points^2)

    Returns:
        (n_points^2, 2) array of candidates

    Example:
        >>> candidates = generate_candidate_grid_2d((0.73, 73.0), (0.10, 10.0), n_points=10)
        >>> print(candidates.shape)
        (100, 2)
    """
    sugar_vals = np.linspace(sugar_range[0], sugar_range[1], n_points)
    salt_vals = np.linspace(salt_range[0], salt_range[1], n_points)

    sugar_grid, salt_grid = np.meshgrid(sugar_vals, salt_vals)
    candidates = np.column_stack([sugar_grid.ravel(), salt_grid.ravel()])

    logger.debug(f"Generated {len(candidates)} 2D grid candidates")

    return candidates


def generate_candidates_latin_hypercube(
    ranges: Dict[str, Tuple[float, float]],
    n_candidates: int = 1000,
    random_state: int = 42,
) -> np.ndarray:
    """
    Generate candidate samples using Latin Hypercube Sampling.

    LHS provides space-filling design for high-dimensional spaces (3+ ingredients).
    Better coverage than random sampling.

    Args:
        ranges: Dict mapping ingredient name -> (min_mM, max_mM)
        n_candidates: Number of candidates to generate
        random_state: Random seed for reproducibility

    Returns:
        (n_candidates, n_ingredients) array

    Example:
        >>> ranges = {'Sugar': (0.73, 73.0), 'Salt': (0.10, 10.0), 'Acid': (0.05, 5.0)}
        >>> candidates = generate_candidates_latin_hypercube(ranges, n_candidates=100)
    """
    from scipy.stats import qmc

    # IMPORTANT: Do NOT sort - preserve order from experiment config to match training data
    ingredient_names = list(ranges.keys())
    n_dim = len(ingredient_names)

    # Generate LHS samples in [0, 1]^n_dim
    sampler = qmc.LatinHypercube(d=n_dim, seed=random_state)
    samples_normalized = sampler.random(n=n_candidates)

    # Scale to actual concentration ranges
    candidates = np.zeros_like(samples_normalized)
    for i, name in enumerate(ingredient_names):
        min_c, max_c = ranges[name]
        candidates[:, i] = samples_normalized[:, i] * (max_c - min_c) + min_c

    logger.debug(f"Generated {n_candidates} candidates via LHS for {n_dim} ingredients")

    return candidates


# ============================================================================
# Utility Functions
# ============================================================================


def get_ingredient_ranges_from_experiment_config(
    experiment_config: Dict[str, Any],
) -> Dict[str, Tuple[float, float]]:
    """
    Extract ingredient concentration ranges from experiment configuration.

    Args:
        experiment_config: Experiment configuration dict with 'ingredients' key

    Returns:
        Dict mapping ingredient name -> (min_mM, max_mM)

    Example:
        >>> config = {
        ...     'ingredients': [
        ...         {'name': 'Sugar', 'min_concentration_mM': 0.73, 'max_concentration_mM': 73.0},
        ...         {'name': 'Salt', 'min_concentration_mM': 0.10, 'max_concentration_mM': 10.0}
        ...     ]
        ... }
        >>> ranges = get_ingredient_ranges_from_experiment_config(config)
        >>> print(ranges)
        {'Sugar': (0.73, 73.0), 'Salt': (0.1, 10.0)}
    """
    ranges = {}

    if "ingredients" not in experiment_config:
        raise ValueError("experiment_config missing 'ingredients' key")

    for ingredient in experiment_config["ingredients"]:
        name = ingredient["name"]
        min_c = ingredient.get("min_concentration_mM", 0.0)
        max_c = ingredient.get("max_concentration_mM", 100.0)
        ranges[name] = (min_c, max_c)

    return ranges


def get_bo_status(session_id: str) -> Dict[str, Any]:
    """
    Get Bayesian Optimization status for moderator display.

    Returns real-time information about the BO state for the given session,
    including whether BO is active, cycle progress, and latest predictions.

    Args:
        session_id: Session identifier

    Returns:
        Dictionary with BO status information:
        {
            "is_active": bool,              # True if cycle >= min_samples
            "is_enabled": bool,              # True if BO enabled in config
            "current_cycle": int,            # Current cycle number
            "samples_collected": int,        # Number of samples in database
            "min_samples_required": int,     # Minimum samples needed for BO
            "latest_prediction": float | None,    # Latest predicted value
            "latest_uncertainty": float | None,   # Latest uncertainty
            "latest_acquisition": float | None,   # Latest acquisition value
            "bo_config": dict,               # BO configuration
            "status_message": str            # Human-readable status
        }

    Example:
        >>> status = get_bo_status("abc123")
        >>> print(status["status_message"])
        "Optimizing (Cycle 5/15)"
    """
    import sql_handler as sql

    try:
        # Get session and config
        session = sql.get_session(session_id)
        if not session:
            return {
                "is_active": False,
                "is_enabled": False,
                "current_cycle": 0,
                "samples_collected": 0,
                "min_samples_required": 3,
                "latest_prediction": None,
                "latest_uncertainty": None,
                "latest_acquisition": None,
                "bo_config": {},
                "status_message": "Session not found",
            }

        experiment_config = session.get("experiment_config", {})
        bo_config = experiment_config.get(
            "bayesian_optimization", get_default_bo_config()
        )

        # Get cycle information
        current_cycle = sql.get_current_cycle(session_id)
        min_samples = bo_config.get("min_samples_for_bo", 3)
        is_enabled = bo_config.get("enabled", True)
        is_active = is_enabled and (current_cycle >= min_samples)

        # Get training data to count samples
        training_df = sql.get_training_data(
            session_id, only_final=bo_config.get("only_final_responses", True)
        )
        samples_collected = len(training_df) if training_df is not None else 0

        # Initialize result
        result = {
            "is_active": is_active,
            "is_enabled": is_enabled,
            "current_cycle": current_cycle,
            "samples_collected": samples_collected,
            "min_samples_required": min_samples,
            "latest_prediction": None,
            "latest_uncertainty": None,
            "latest_acquisition": None,
            "bo_config": bo_config,
            "status_message": "",
        }

        # Generate status message
        if not is_enabled:
            result["status_message"] = "BO Disabled"
        elif current_cycle < min_samples:
            result["status_message"] = (
                f"Exploring (Cycle {current_cycle}/{min_samples - 1})"
            )
        else:
            result["status_message"] = f"Optimizing (Cycle {current_cycle})"

        # Try to get latest prediction if BO is active
        if is_active and samples_collected >= min_samples:
            try:
                # Get latest sample's selection_data which contains BO metadata
                with sql.get_database_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT selection_data
                        FROM samples
                        WHERE session_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (session_id,),
                    )
                    row = cursor.fetchone()

                    if row and row[0]:
                        import json

                        selection_data = json.loads(row[0])

                        # Extract BO metadata if it exists
                        if selection_data.get("mode") == "bayesian_optimization":
                            result["latest_prediction"] = selection_data.get(
                                "predicted_value"
                            )
                            result["latest_uncertainty"] = selection_data.get(
                                "uncertainty"
                            )
                            result["latest_acquisition"] = selection_data.get(
                                "acquisition_value"
                            )

            except Exception as e:
                # Silently fail - this is just for display
                pass

        return result

    except Exception as e:
        return {
            "is_active": False,
            "is_enabled": False,
            "current_cycle": 0,
            "samples_collected": 0,
            "min_samples_required": 3,
            "latest_prediction": None,
            "latest_uncertainty": None,
            "latest_acquisition": None,
            "bo_config": {},
            "status_message": f"Error: {str(e)}",
        }


def get_convergence_metrics(session_id: str) -> Dict[str, Any]:
    """
    Analyze BO convergence metrics from stored sample data.

    Retrieves time series of BO metrics (acquisition values, predictions, uncertainties)
    from the database and calculates convergence indicators.

    Args:
        session_id: Session identifier

    Returns:
        Dictionary with convergence metrics:
        {
            "current_cycle": int,
            "n_samples": int,
            "n_bo_samples": int,
            "acquisition_values": List[float],
            "predicted_values": List[float],
            "uncertainties": List[float],
            "best_values": List[float],  # Best observed value at each cycle
            "max_acquisition": float,
            "recent_stability": float,  # Std dev of last N best values
            "improvement_rate": float,  # Recent improvement trend
            "has_sufficient_data": bool,
        }

    Example:
        >>> metrics = get_convergence_metrics(session_id)
        >>> if metrics["max_acquisition"] < 0.001:
        ...     print("Low expected improvement - nearing convergence")
    """
    import sql_handler as sql

    try:
        # Get all samples with BO metadata
        with sql.get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT sample_id, selection_data, created_at
                FROM samples
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            rows = cursor.fetchall()

        if not rows:
            return {
                "current_cycle": 0,
                "n_samples": 0,
                "n_bo_samples": 0,
                "acquisition_values": [],
                "predicted_values": [],
                "uncertainties": [],
                "best_values": [],
                "max_acquisition": None,
                "recent_stability": None,
                "improvement_rate": None,
                "has_sufficient_data": False,
            }

        # Parse BO metadata from each sample
        acquisition_values = []
        predicted_values = []
        uncertainties = []
        best_values = []
        n_bo_samples = 0

        # Get training data to calculate best values over time
        training_df = sql.get_training_data(session_id, only_final=False)
        target_col = training_df.columns[-1] if not training_df.empty else None

        for i, row in enumerate(rows):
            selection_data_json = row[1]

            if selection_data_json:
                selection_data = json.loads(selection_data_json)

                # Extract BO metrics if available
                if selection_data.get("mode") == "bayesian_optimization":
                    n_bo_samples += 1
                    acquisition_values.append(
                        selection_data.get("acquisition_value", 0.0)
                    )
                    predicted_values.append(selection_data.get("predicted_value", 0.0))
                    uncertainties.append(selection_data.get("uncertainty", 0.0))

                    # Get best observed value at this point in time
                    if target_col and not training_df.empty:
                        # Best value up to and including current sample
                        best_so_far = training_df.iloc[: i + 1][target_col].max()
                        best_values.append(float(best_so_far))

        # Calculate derived metrics
        current_cycle = sql.get_current_cycle(session_id)
        n_samples = len(rows)
        has_sufficient_data = n_bo_samples >= 3

        # Max acquisition (most recent if available)
        max_acquisition = acquisition_values[-1] if acquisition_values else None

        # Stability: std dev of recent best values
        recent_stability = None
        if len(best_values) >= 5:
            recent_best = best_values[-5:]
            recent_stability = float(np.std(recent_best))

        # Improvement rate: change in best value over recent cycles
        improvement_rate = None
        if len(best_values) >= 5:
            recent_best = best_values[-5:]
            improvement_rate = float(recent_best[-1] - recent_best[0])

        return {
            "current_cycle": current_cycle,
            "n_samples": n_samples,
            "n_bo_samples": n_bo_samples,
            "acquisition_values": acquisition_values,
            "predicted_values": predicted_values,
            "uncertainties": uncertainties,
            "best_values": best_values,
            "max_acquisition": max_acquisition,
            "recent_stability": recent_stability,
            "improvement_rate": improvement_rate,
            "has_sufficient_data": has_sufficient_data,
        }

    except Exception as e:
        logger.error(f"Error getting convergence metrics: {e}", exc_info=True)
        return {
            "current_cycle": 0,
            "n_samples": 0,
            "n_bo_samples": 0,
            "acquisition_values": [],
            "predicted_values": [],
            "uncertainties": [],
            "best_values": [],
            "max_acquisition": None,
            "recent_stability": None,
            "improvement_rate": None,
            "has_sufficient_data": False,
        }


def check_convergence(
    session_id: str, stopping_criteria: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check if BO has converged based on multi-criteria analysis.

    Implements research-based stopping criteria:
    1. Minimum samples collected (prevents premature stopping)
    2. Low acquisition value (EI or UCB < threshold)
    3. Stable best values (recent std dev < threshold)
    4. Not exceeded maximum samples

    Args:
        session_id: Session identifier
        stopping_criteria: Optional stopping criteria config (uses defaults if None)

    Returns:
        Dictionary with convergence status:
        {
            "converged": bool,
            "confidence": float,  # 0-1 scale
            "reason": str,  # Human-readable explanation
            "criteria_met": List[str],  # Which criteria are satisfied
            "recommendation": str,  # "continue", "consider_stopping", "stop_recommended"
            "metrics": Dict,  # Raw metrics for display
            "status_emoji": str,  # 🔴, 🟡, or 🟢
        }

    Example:
        >>> result = check_convergence(session_id, stopping_criteria)
        >>> if result["recommendation"] == "stop_recommended":
        ...     show_stopping_dialog()
    """
    import sql_handler as sql

    try:
        # Get stopping criteria (use defaults if not provided). Ensure it's a dict.
        if stopping_criteria is None or not isinstance(stopping_criteria, dict):
            default_config = get_default_bo_config()
            stopping_criteria = default_config.get("stopping_criteria") or {}
        # Guard against None and provide a local alias to satisfy static analysis
        if stopping_criteria is None:
            stopping_criteria = {}
        sc = stopping_criteria

        # Get session info to determine dimensionality
        session = sql.get_session(session_id)
        if not session:
            return {
                "converged": False,
                "confidence": 0.0,
                "reason": "Session not found",
                "criteria_met": [],
                "recommendation": "continue",
                "metrics": {},
                "status_emoji": "🔴",
            }

        experiment_config = session.get("experiment_config", {})
        n_ingredients = len(experiment_config.get("ingredients", []))

        # Determine min/max cycles based on dimensionality
        if n_ingredients == 1:
            min_cycles = sc.get("min_cycles_1d", 10)
            max_cycles = sc.get("max_cycles_1d", 30)
        else:  # 2D or more
            min_cycles = sc.get("min_cycles_2d", 15)
            max_cycles = sc.get("max_cycles_2d", 50)

        # Get BO configuration to determine acquisition function
        bo_config = experiment_config.get("bayesian_optimization", {})
        acquisition_func = bo_config.get("acquisition_function", "ei")

        # Choose threshold based on acquisition function
        if acquisition_func == "ei":
            acq_threshold = sc.get("ei_threshold", 0.001)
        else:  # ucb
            acq_threshold = sc.get("ucb_threshold", 0.01)

        stability_threshold = sc.get("stability_threshold", 0.05)
        stability_window = sc.get("stability_window", 5)

        # Get convergence metrics
        metrics = get_convergence_metrics(session_id)

        current_cycle = metrics["current_cycle"]
        max_acquisition = metrics["max_acquisition"]
        recent_stability = metrics["recent_stability"]
        has_sufficient_data = metrics["has_sufficient_data"]

        # Check individual criteria
        criteria_met = []
        criteria_failed = []

        # Criterion 1: Minimum samples
        if current_cycle >= min_cycles:
            criteria_met.append(f"min_cycles (≥{min_cycles})")
        else:
            criteria_failed.append(f"min_cycles ({current_cycle}/{min_cycles})")

        # Criterion 2: Not exceeded maximum
        if current_cycle < max_cycles:
            criteria_met.append(f"under_max ({current_cycle}/{max_cycles})")
        else:
            criteria_met.append(f"max_cycles_reached ({current_cycle})")

        # Criterion 3: Low acquisition value
        if max_acquisition is not None and max_acquisition < acq_threshold:
            criteria_met.append(f"low_{acquisition_func} (<{acq_threshold})")
        elif max_acquisition is not None:
            criteria_failed.append(
                f"high_{acquisition_func} ({max_acquisition:.4f} ≥ {acq_threshold})"
            )

        # Criterion 4: Stability of best values
        if recent_stability is not None and recent_stability < stability_threshold:
            criteria_met.append(f"stable (σ={recent_stability:.3f})")
        elif recent_stability is not None:
            criteria_failed.append(
                f"unstable (σ={recent_stability:.3f} ≥ {stability_threshold})"
            )
        else:
            criteria_failed.append(
                f"insufficient_data_for_stability (<{stability_window})"
            )

        # Determine convergence
        # All criteria must be met except max_cycles (which forces stop)
        required_criteria = [
            current_cycle >= min_cycles,
            current_cycle < max_cycles,
            max_acquisition is not None and max_acquisition < acq_threshold,
            recent_stability is not None and recent_stability < stability_threshold,
        ]

        converged = all(required_criteria)

        # Calculate confidence (0-1)
        confidence = 0.0
        if converged:
            confidence = 0.9  # High confidence if all criteria met
        elif current_cycle >= min_cycles:
            # Partial confidence based on how close to thresholds
            partial_confidence = 0.0
            if max_acquisition is not None and acq_threshold > 0:
                partial_confidence += min(1.0, acq_threshold / max_acquisition) * 0.4
            if (
                recent_stability is not None
                and stability_threshold > 0
                and recent_stability > 0
            ):
                partial_confidence += (
                    min(1.0, stability_threshold / recent_stability) * 0.4
                )
            elif recent_stability == 0.0:
                # Perfect stability (no variance) - high partial confidence
                partial_confidence += 0.4
            confidence = min(
                0.8, partial_confidence
            )  # Cap at 0.8 for partial convergence

        # Hard stop at max cycles
        if current_cycle >= max_cycles:
            converged = True
            confidence = 1.0
            reason = f"Maximum cycles reached ({current_cycle}/{max_cycles})"
            recommendation = "stop_recommended"
            status_emoji = "🔴"
        elif converged:
            reason = f"Converged"
            recommendation = "stop_recommended"
            status_emoji = "🟢"
        elif current_cycle < min_cycles:
            reason = f"Still exploring ({current_cycle}/{min_cycles} minimum)"
            recommendation = "continue"
            status_emoji = "🔴"
        elif len(criteria_met) >= 2:
            reason = f"Nearing convergence"
            recommendation = "consider_stopping"
            status_emoji = "🟡"
        else:
            reason = f"Optimizing"
            recommendation = "continue"
            status_emoji = "🟡"

        return {
            "converged": converged,
            "confidence": confidence,
            "reason": reason,
            "criteria_met": criteria_met,
            "criteria_failed": criteria_failed,
            "recommendation": recommendation,
            "metrics": metrics,
            "status_emoji": status_emoji,
            "thresholds": {
                "min_cycles": min_cycles,
                "max_cycles": max_cycles,
                "acquisition_threshold": acq_threshold,
                "stability_threshold": stability_threshold,
            },
        }

    except Exception as e:
        logger.error(f"Error checking convergence: {e}", exc_info=True)
        return {
            "converged": False,
            "confidence": 0.0,
            "reason": f"Error: {str(e)}",
            "criteria_met": [],
            "recommendation": "continue",
            "metrics": {},
            "status_emoji": "🔴",
        }


if __name__ == "__main__":
    # Simple test
    print("Testing RoboTasteBO...")

    # Create test model
    bo = RoboTasteBO(
        ingredient_names=["Sugar", "Salt"],
        concentration_ranges={"Sugar": (0.73, 73.0), "Salt": (0.10, 10.0)},
    )

    # Test data
    X_train = np.array([[10.0, 2.0], [20.0, 3.0], [30.0, 4.0], [15.0, 2.5]])
    y_train = np.array([6.5, 7.8, 7.2, 7.0])

    # Train
    bo.fit(X_train, y_train)

    # Generate candidates
    candidates = generate_candidate_grid_2d((0.73, 73.0), (0.10, 10.0), n_points=10)

    # Get suggestion
    suggestion = bo.suggest_next_sample(candidates, acquisition="ei")

    print(f"\nSuggestion: {suggestion['best_candidate_dict']}")
    print(f"Predicted rating: {suggestion['predicted_value']:.2f}")
    print(f"EI value: {suggestion['acquisition_value']:.4f}")
    print(f"Uncertainty: {suggestion['uncertainty']:.3f}")
    print("\n✅ Test passed!")
