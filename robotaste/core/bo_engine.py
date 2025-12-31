"""
RoboTaste Bayesian Optimization Engine

Pure Python Gaussian Process Bayesian Optimization.
NO external dependencies (no Streamlit, no SQL).

Features:
- Matern kernel with configurable smoothness
- Expected Improvement (EI) and Upper Confidence Bound (UCB) acquisition
- Adaptive acquisition parameters (exploration → exploitation schedule)
- Support for 2-6 ingredient dimensions
- Automatic feature normalization

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture - SQL-free)
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel as C
from typing import Tuple, List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ADAPTIVE ACQUISITION FUNCTIONS
# ============================================================================


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
        >>> get_adaptive_xi(5, 40, 0.25, 0.1, 0.01)  # Early cycle
        0.1
        >>> get_adaptive_xi(20, 40, 0.25, 0.1, 0.01)  # Middle
        0.055
        >>> get_adaptive_xi(39, 40, 0.25, 0.1, 0.01)  # Late cycle
        0.01
    """
    if max_cycles <= 0:
        return xi_exploitation

    progress = current_cycle / max_cycles

    # During exploration phase: use high xi
    if progress <= exploration_budget:
        return xi_exploration

    # After exploration phase: linear decay to exploitation
    decay_progress = (progress - exploration_budget) / (1.0 - exploration_budget)
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

    Args:
        current_cycle: Current optimization cycle (0-indexed)
        max_cycles: Maximum number of cycles in the session
        exploration_budget: Fraction of cycles for exploration phase (default 0.25 = 25%)
        kappa_exploration: kappa value during early exploration phase (default 3.0)
        kappa_exploitation: kappa value during late exploitation phase (default 1.0)

    Returns:
        Adaptive kappa value for current cycle

    Example:
        >>> get_adaptive_kappa(5, 40, 0.25, 3.0, 1.0)  # Early cycle
        3.0
        >>> get_adaptive_kappa(20, 40, 0.25, 3.0, 1.0)  # Middle
        2.0
        >>> get_adaptive_kappa(39, 40, 0.25, 3.0, 1.0)  # Late cycle
        1.0
    """
    if max_cycles <= 0:
        return kappa_exploitation

    progress = current_cycle / max_cycles

    # During exploration phase: use high kappa
    if progress <= exploration_budget:
        return kappa_exploration

    # After exploration phase: linear decay to exploitation
    decay_progress = (progress - exploration_budget) / (1.0 - exploration_budget)
    kappa = kappa_exploration - (kappa_exploration - kappa_exploitation) * decay_progress

    return kappa


# ============================================================================
# BAYESIAN OPTIMIZATION CLASS
# ============================================================================


class RoboTasteBO:
    """
    Bayesian Optimization for taste preference learning.

    Features:
    - Matern kernel (nu=2.5 default) for smooth preference landscapes
    - Expected Improvement and Upper Confidence Bound acquisition functions
    - Support for 2-6 ingredient dimensions
    - Automatic normalization of ingredient concentrations
    - Adaptive exploration/exploitation schedule

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
        """
        # Import here to avoid circular dependency
        from config import DEFAULT_BO_CONFIG

        # IMPORTANT: Do NOT sort - preserve order from experiment config to match training data
        self.ingredient_names = list(ingredient_names)
        self.ranges = concentration_ranges
        self.n_dim = len(ingredient_names)

        # Load config with defaults
        self.config = {**DEFAULT_BO_CONFIG, **(config or {})}

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
            normalize_y=normalize_y,
            random_state=random_state,
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
        """
        X_norm = np.zeros_like(X, dtype=float)
        for i, name in enumerate(self.ingredient_names):
            min_c, max_c = self.ranges[name]
            X_norm[:, i] = (X[:, i] - min_c) / (max_c - min_c)
        return X_norm

    def _denormalize_features(self, X_norm: np.ndarray) -> np.ndarray:
        """Convert normalized [0, 1] features back to original concentration scale."""
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
            Dict with suggestion details
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
                    f"xi={acq_kwargs['xi']:.4f}"
                )
            elif acquisition == "ucb" and "kappa" not in acq_kwargs:
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
                    f"kappa={acq_kwargs['kappa']:.4f}"
                )
        else:
            # Use static config defaults
            if acquisition == "ei" and "xi" not in acq_kwargs:
                acq_kwargs["xi"] = self.config.get("ei_xi", 0.01)
            elif acquisition == "ucb" and "kappa" not in acq_kwargs:
                acq_kwargs["kappa"] = self.config.get("ucb_kappa", 2.0)

        # Calculate acquisition function
        if acquisition == "ei":
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
            "acquisition_params": acq_kwargs,
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
            f"uncertainty={result['uncertainty']:.3f}"
        )

        return result


# ============================================================================
# TRAINING FUNCTION (REFACTORED - SQL-FREE)
# ============================================================================


def train_bo_model(
    training_data: pd.DataFrame,
    ingredient_names: List[str],
    target_column: str,
    bo_config: Optional[Dict[str, Any]] = None,
    infer_ranges: bool = True,
    concentration_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Optional[RoboTasteBO]:
    """
    Train Bayesian Optimization model from DataFrame (SQL-free version).

    This is the REFACTORED version that accepts data directly instead of fetching from SQL.

    Args:
        training_data: DataFrame with ingredient concentrations and target values
        ingredient_names: List of ingredient column names (in correct order)
        target_column: Name of the target variable column
        bo_config: BO configuration dict (uses defaults if None)
        infer_ranges: If True, infer concentration ranges from data (recommended)
        concentration_ranges: Optional manual ranges {ingredient: (min, max)}

    Returns:
        Trained RoboTasteBO instance or None if insufficient data

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'Sugar': [10.0, 20.0, 30.0, 15.0],
        ...     'Salt': [2.0, 3.0, 4.0, 2.5],
        ...     'hedonic_score': [6.5, 7.8, 7.2, 7.0]
        ... })
        >>> bo_model = train_bo_model(
        ...     training_data=df,
        ...     ingredient_names=['Sugar', 'Salt'],
        ...     target_column='hedonic_score'
        ... )
    """
    from config import DEFAULT_BO_CONFIG

    try:
        # Merge with defaults
        config = {**DEFAULT_BO_CONFIG, **(bo_config or {})}
        min_samples = config.get("min_samples_for_bo", 3)

        logger.info(f"BO Training - Received {len(training_data)} samples")

        if len(training_data) < min_samples:
            logger.info(
                f"Insufficient data for BO training: {len(training_data)} samples < {min_samples} required"
            )
            return None

        # Extract features and target
        X_list = []
        y_list = []

        for _, row in training_data.iterrows():
            try:
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

        # Determine concentration ranges
        if infer_ranges:
            ranges = {}
            for i, name in enumerate(ingredient_names):
                min_c = max(0.001, np.min(X[:, i]) * 0.8)  # Pad 20%, min 0.001
                max_c = np.max(X[:, i]) * 1.2
                ranges[name] = (min_c, max_c)
                logger.debug(f"{name} range: [{min_c:.3f}, {max_c:.3f}] mM")
        else:
            if concentration_ranges is None:
                raise ValueError(
                    "Must provide concentration_ranges if infer_ranges=False"
                )
            ranges = concentration_ranges

        # Train model
        bo = RoboTasteBO(ingredient_names, ranges, config=config)
        bo.fit(X, y)

        logger.info(f"Successfully trained BO model with {len(X)} samples")

        return bo

    except Exception as e:
        logger.error(f"Error training BO model: {e}", exc_info=True)
        return None


# ============================================================================
# CANDIDATE GENERATION FUNCTIONS
# ============================================================================


def generate_candidate_grid_2d(
    sugar_range: Tuple[float, float],
    salt_range: Tuple[float, float],
    n_points: int = 20,
) -> np.ndarray:
    """
    Generate 2D grid of candidate samples for Sugar-Salt space.

    Args:
        sugar_range: (min_mM, max_mM) for sugar
        salt_range: (min_mM, max_mM) for salt
        n_points: Number of points per dimension (total = n_points^2)

    Returns:
        (n_points^2, 2) array of candidates
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

    Args:
        ranges: Dict mapping ingredient name -> (min_mM, max_mM)
        n_candidates: Number of candidates to generate
        random_state: Random seed for reproducibility

    Returns:
        (n_candidates, n_ingredients) array
    """
    from scipy.stats import qmc

    # IMPORTANT: Do NOT sort - preserve order from experiment config
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
