"""
Bayesian Optimization Utilities

Database-coupled BO functions for training, status monitoring, and convergence checking.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import numpy as np
import logging
import json
from typing import Dict, Any, Optional

from robotaste.core.bo_engine import RoboTasteBO
from robotaste.config.bo_config import (
    get_default_bo_config,
    validate_bo_config,
)
from robotaste.data import database as sql

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Model Training
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
        ...     from robotaste.core.bo_engine import generate_candidate_grid_2d
        ...     candidates = generate_candidate_grid_2d((0.73, 73.0), (0.10, 10.0))
        ...     suggestion = bo_model.suggest_next_sample(candidates)
    """
    from robotaste.data.database import get_training_data

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


# ============================================================================
# Status Monitoring
# ============================================================================


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
    from robotaste.data.database import get_session, get_current_cycle, get_training_data

    try:
        # Get session and config
        session = get_session(session_id)
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
        current_cycle = get_current_cycle(session_id)
        min_samples = bo_config.get("min_samples_for_bo", 3)
        is_enabled = bo_config.get("enabled", True)
        is_active = is_enabled and (current_cycle >= min_samples)

        # Get training data to count samples
        training_df = get_training_data(
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


# ============================================================================
# Convergence Analysis
# ============================================================================


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
    from robotaste.data.database import get_database_connection, get_training_data, get_current_cycle

    try:
        # Get all samples with BO metadata
        with get_database_connection() as conn:
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
        training_df = get_training_data(session_id, only_final=False)
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
        current_cycle = get_current_cycle(session_id)
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
    from robotaste.data.database import get_session

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
        session = get_session(session_id)
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
