"""
Moderator Metrics Calculator

Calculates metrics for different selection modes with graceful fallbacks
for missing data (trajectory_clicks, reaction_time_ms, etc.).

Author: RoboTaste Team
Version: 1.0
"""

import logging
from typing import Dict, Any, List, Optional
import json
import numpy as np

from robotaste.data.database import (
    get_session,
    get_session_samples,
    get_current_cycle,
)
from robotaste.core.trials import get_selection_mode_for_cycle_runtime
from robotaste.config.protocol_schema import get_selection_mode_for_cycle

logger = logging.getLogger(__name__)


# =============================================================================
# Mode Detection
# =============================================================================

def get_current_mode_info(session_id: str) -> Dict[str, Any]:
    """
    Get information about current and overall protocol modes.

    Args:
        session_id: Session UUID

    Returns:
        {
            "current_cycle": int,
            "current_mode": str,  # "predetermined_absolute", "predetermined_randomized", "user_selected", "bo_selected"
            "is_mixed_mode": bool,
            "all_modes": List[str],  # Unique modes in protocol
            "schedule": List[Dict]  # Full schedule from protocol
        }
    """
    try:
        current_cycle = get_current_cycle(session_id)
        current_mode = get_selection_mode_for_cycle_runtime(session_id, current_cycle)

        # Get protocol schedule
        session = get_session(session_id)
        if not session:
            return {
                "current_cycle": current_cycle,
                "current_mode": current_mode,
                "is_mixed_mode": False,
                "all_modes": [current_mode],
                "schedule": []
            }

        experiment_config = session.get("experiment_config", {})

        # Check for embedded protocol or referenced protocol
        protocol = None
        if "sample_selection_schedule" in experiment_config:
            protocol = experiment_config
        else:
            protocol_id = experiment_config.get("protocol_id")
            if protocol_id:
                from robotaste.data import protocol_repo
                protocol_obj = protocol_repo.get_protocol_by_id(protocol_id)
                if protocol_obj:
                    protocol = protocol_obj.get("protocol_json", {})

        schedule = protocol.get("sample_selection_schedule", []) if protocol else []

        # Determine all unique modes
        all_modes = list(set(entry.get("mode", "user_selected") for entry in schedule))
        is_mixed_mode = len(all_modes) > 1

        return {
            "current_cycle": current_cycle,
            "current_mode": current_mode,
            "is_mixed_mode": is_mixed_mode,
            "all_modes": all_modes,
            "schedule": schedule
        }

    except Exception as e:
        logger.error(f"Error getting mode info: {e}", exc_info=True)
        return {
            "current_cycle": 0,
            "current_mode": "user_selected",
            "is_mixed_mode": False,
            "all_modes": ["user_selected"],
            "schedule": []
        }


# =============================================================================
# Predetermined Mode Metrics
# =============================================================================

def get_predetermined_metrics(session_id: str) -> Dict[str, Any]:
    """
    Calculate metrics for predetermined mode.

    Returns:
        {
            "total_predetermined_cycles": int,
            "completed_predetermined": int,
            "adherence_rate": float,  # % of cycles that matched protocol
            "samples": List[Dict]  # All predetermined cycle data (protocol + completed samples merged)
        }
    """
    try:
        session = get_session(session_id)
        if not session:
            return _empty_predetermined_metrics()

        experiment_config = session.get("experiment_config", {})

        # Get protocol
        protocol = None
        if "sample_selection_schedule" in experiment_config:
            protocol = experiment_config
        else:
            protocol_id = experiment_config.get("protocol_id")
            if protocol_id:
                from robotaste.data import protocol_repo
                protocol_obj = protocol_repo.get_protocol_by_id(protocol_id)
                if protocol_obj:
                    protocol = protocol_obj.get("protocol_json", {})

        if not protocol:
            return _empty_predetermined_metrics()

        from robotaste.config.protocol_schema import get_predetermined_sample

        # Get all predetermined cycles from protocol schedule
        schedule = protocol.get("sample_selection_schedule", [])
        predetermined_cycles = []

        for entry in schedule:
            mode = entry.get("mode")
            # Support all predetermined modes (legacy and new)
            if mode in ["predetermined", "predetermined_absolute", "predetermined_randomized"]:
                cycle_range = entry.get("cycle_range", {})
                start = cycle_range.get("start", 0)
                end = cycle_range.get("end", 0)
                for cycle_num in range(start, end + 1):
                    predetermined_cycles.append(cycle_num)

        total_predetermined = len(predetermined_cycles)

        # Get completed samples from database
        all_samples = get_session_samples(session_id, only_final=False)
        completed_samples_dict = {s.get("cycle_number"): s for s in all_samples}

        # Build merged sample list: protocol cycles + completed data
        merged_samples = []
        completed = 0

        for cycle_num in predetermined_cycles:
            # Get expected concentrations from protocol
            # Try to get from predetermined_samples first (for predetermined_absolute mode)
            expected_conc = get_predetermined_sample(protocol, cycle_num)

            # If not found, try to get from sample bank (for predetermined_randomized mode)
            if expected_conc is None:
                from robotaste.config.protocol_schema import get_sample_bank_config, get_schedule_index_for_cycle
                from robotaste.core.sample_bank import get_next_sample_from_bank

                bank_config = get_sample_bank_config(protocol, cycle_num)
                schedule_index = get_schedule_index_for_cycle(protocol, cycle_num)

                if bank_config and schedule_index >= 0:
                    try:
                        # Get cycle_range_start
                        schedule_entry = schedule[schedule_index]
                        cycle_range_start = schedule_entry.get("cycle_range", {}).get("start", 1)

                        expected_conc = get_next_sample_from_bank(
                            session_id,
                            schedule_index,
                            bank_config,
                            cycle_num,
                            cycle_range_start
                        )
                    except Exception as e:
                        logger.warning(f"Could not get sample from bank for cycle {cycle_num}: {e}")
                        expected_conc = None

            # Check if this cycle has been completed
            completed_sample = completed_samples_dict.get(cycle_num)

            if completed_sample:
                # Merge protocol info with completed sample data
                sample_data = completed_sample.copy()
                sample_data["expected_concentration"] = expected_conc
                sample_data["is_completed"] = True
                completed += 1
            else:
                # Create placeholder entry for not-yet-completed cycle
                sample_data = {
                    "cycle_number": cycle_num,
                    "expected_concentration": expected_conc,
                    "ingredient_concentration": expected_conc,  # Show expected as current
                    "questionnaire_answer": {},
                    "is_completed": False,
                    "created_at": None
                }

            merged_samples.append(sample_data)

        # Calculate adherence (for now, assume 100% since predetermined samples are enforced)
        adherence = 1.0 if completed > 0 else 0.0

        return {
            "total_predetermined_cycles": total_predetermined,
            "completed_predetermined": completed,
            "adherence_rate": adherence,
            "samples": merged_samples
        }

    except Exception as e:
        logger.error(f"Error calculating predetermined metrics: {e}", exc_info=True)
        return _empty_predetermined_metrics()


def _empty_predetermined_metrics() -> Dict[str, Any]:
    return {
        "total_predetermined_cycles": 0,
        "completed_predetermined": 0,
        "adherence_rate": 0.0,
        "samples": []
    }


# =============================================================================
# User Selection Mode Metrics
# =============================================================================

def get_user_selection_metrics(session_id: str) -> Dict[str, Any]:
    """
    Calculate metrics for user_selected mode with graceful fallbacks.

    NOTE: trajectory_clicks and reaction_time_ms are NOT currently being collected.
    This function provides informational messages when data is unavailable.

    Returns:
        {
            "total_user_cycles": int,
            "completed_user_cycles": int,
            "has_trajectory_data": bool,
            "avg_trajectory_length": float | None,
            "avg_reaction_time_ms": float | None,
            "exploration_coverage": float | None,  # % of space explored
            "samples": List[Dict],
            "data_availability": {
                "trajectory_clicks": bool,
                "reaction_time_ms": bool,
                "heatmap_data": bool
            }
        }
    """
    try:
        session = get_session(session_id)
        if not session:
            return _empty_user_selection_metrics()

        # Get samples for this mode
        samples = get_session_samples(session_id, only_final=False)
        user_samples = [s for s in samples if s.get("selection_mode") == "user_selected"]

        completed = len(user_samples)

        # Count total user_selected cycles from protocol
        experiment_config = session.get("experiment_config", {})
        protocol = None
        if "sample_selection_schedule" in experiment_config:
            protocol = experiment_config
        else:
            protocol_id = experiment_config.get("protocol_id")
            if protocol_id:
                from robotaste.data import protocol_repo
                protocol_obj = protocol_repo.get_protocol_by_id(protocol_id)
                if protocol_obj:
                    protocol = protocol_obj.get("protocol_json", {})

        total_user = 0
        if protocol:
            schedule = protocol.get("sample_selection_schedule", [])
            for entry in schedule:
                if entry.get("mode") == "user_selected":
                    cycle_range = entry.get("cycle_range", {})
                    total_user += cycle_range.get("end", 0) - cycle_range.get("start", 0) + 1

        # Check for trajectory data (graceful fallback if missing)
        has_trajectory = False
        avg_trajectory_length = None
        avg_reaction_time = None

        for sample in user_samples:
            selection_data = sample.get("selection_data", {})
            if selection_data and "trajectory_clicks" in selection_data:
                has_trajectory = True
                break

        if has_trajectory:
            # Calculate trajectory metrics if data exists
            trajectory_lengths = []
            reaction_times = []

            for sample in user_samples:
                selection_data = sample.get("selection_data", {})
                trajectory = selection_data.get("trajectory_clicks", [])
                if trajectory:
                    trajectory_lengths.append(len(trajectory))

                reaction_time = selection_data.get("reaction_time_ms")
                if reaction_time is not None:
                    reaction_times.append(reaction_time)

            if trajectory_lengths:
                avg_trajectory_length = np.mean(trajectory_lengths)
            if reaction_times:
                avg_reaction_time = np.mean(reaction_times)

        # Exploration coverage (simplified - just counts unique samples)
        unique_samples = len(set(
            json.dumps(s.get("ingredient_concentration", {}), sort_keys=True)
            for s in user_samples
        ))
        exploration_coverage = unique_samples / max(1, completed) if completed > 0 else 0.0

        return {
            "total_user_cycles": total_user,
            "completed_user_cycles": completed,
            "has_trajectory_data": has_trajectory,
            "avg_trajectory_length": avg_trajectory_length,
            "avg_reaction_time_ms": avg_reaction_time,
            "exploration_coverage": exploration_coverage,
            "samples": user_samples,
            "data_availability": {
                "trajectory_clicks": has_trajectory,
                "reaction_time_ms": avg_reaction_time is not None,
                "heatmap_data": False  # Not currently collected
            }
        }

    except Exception as e:
        logger.error(f"Error calculating user selection metrics: {e}", exc_info=True)
        return _empty_user_selection_metrics()


def _empty_user_selection_metrics() -> Dict[str, Any]:
    return {
        "total_user_cycles": 0,
        "completed_user_cycles": 0,
        "has_trajectory_data": False,
        "avg_trajectory_length": None,
        "avg_reaction_time_ms": None,
        "exploration_coverage": None,
        "samples": [],
        "data_availability": {
            "trajectory_clicks": False,
            "reaction_time_ms": False,
            "heatmap_data": False
        }
    }


# =============================================================================
# BO Mode Metrics (Reuses existing bo_utils functions)
# =============================================================================

def get_bo_mode_metrics(session_id: str) -> Dict[str, Any]:
    """
    Calculate metrics for bo_selected mode.

    Reuses existing functions from bo_utils.py:
    - get_convergence_metrics()
    - check_convergence()

    Returns:
        {
            "total_bo_cycles": int,
            "completed_bo_cycles": int,
            "convergence_status": Dict,  # From check_convergence()
            "convergence_metrics": Dict,  # From get_convergence_metrics()
            "samples": List[Dict]
        }
    """
    try:
        from robotaste.core.bo_utils import get_convergence_metrics, check_convergence

        session = get_session(session_id)
        if not session:
            return _empty_bo_metrics()

        # Get samples for this mode
        samples = get_session_samples(session_id, only_final=False)
        bo_samples = [s for s in samples if s.get("selection_mode") == "bo_selected"]

        completed = len(bo_samples)

        # Count total BO cycles from protocol
        experiment_config = session.get("experiment_config", {})
        protocol = None
        if "sample_selection_schedule" in experiment_config:
            protocol = experiment_config
        else:
            protocol_id = experiment_config.get("protocol_id")
            if protocol_id:
                from robotaste.data import protocol_repo
                protocol_obj = protocol_repo.get_protocol_by_id(protocol_id)
                if protocol_obj:
                    protocol = protocol_obj.get("protocol_json", {})

        total_bo = 0
        if protocol:
            schedule = protocol.get("sample_selection_schedule", [])
            for entry in schedule:
                if entry.get("mode") == "bo_selected":
                    cycle_range = entry.get("cycle_range", {})
                    total_bo += cycle_range.get("end", 0) - cycle_range.get("start", 0) + 1

        # Get convergence data (reuse existing functions)
        convergence_metrics = get_convergence_metrics(session_id)

        bo_config = experiment_config.get("bayesian_optimization", {})
        stopping_criteria = bo_config.get("stopping_criteria")
        convergence_status = check_convergence(session_id, stopping_criteria)

        return {
            "total_bo_cycles": total_bo,
            "completed_bo_cycles": completed,
            "convergence_status": convergence_status,
            "convergence_metrics": convergence_metrics,
            "samples": bo_samples
        }

    except Exception as e:
        logger.error(f"Error calculating BO metrics: {e}", exc_info=True)
        return _empty_bo_metrics()


def _empty_bo_metrics() -> Dict[str, Any]:
    return {
        "total_bo_cycles": 0,
        "completed_bo_cycles": 0,
        "convergence_status": {},
        "convergence_metrics": {},
        "samples": []
    }
