"""
completion_screens.py - Session completion UI for RoboTaste

Provides completion screens for both subject and moderator interfaces
when a session transitions to the COMPLETE phase.

Author: RoboTaste Team
Date: November 2025
"""

import streamlit as st
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

from robotaste.data.database import (
    get_session,
    get_session_samples,
    get_session_stats,
)
from robotaste.config.questionnaire import get_questionnaire_metadata

logger = logging.getLogger(__name__)


def show_subject_completion_screen():
    """
    Display completion screen for subjects.

    Shows thank you message with basic session statistics and
    option to return to landing page.
    """
    try:
        # Get session data
        session_id = st.session_state.get("session_id")
        if not session_id:
            st.error("Session not found. Please return to the home page.")
            if st.button("Return to Home"):
                st.query_params.clear()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            return

        session = get_session(session_id)
        stats = get_session_stats(session_id)

        # Calculate session duration
        duration_str = "Unknown"
        if stats.get("created_at") and stats.get("last_cycle_at"):
            try:
                start = datetime.fromisoformat(stats["created_at"])
                end = datetime.fromisoformat(stats["last_cycle_at"])
                duration = end - start
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                duration_str = f"{minutes} min {seconds} sec"
            except Exception as e:
                logger.warning(f"Could not calculate duration: {e}")

        # Display completion message
        st.markdown("# 🎉 Session Complete!")
        st.markdown("---")

        st.success("### Thank you for participating in this taste experiment!")

        st.markdown(
            """
        Your responses have been successfully recorded and will contribute
        to understanding taste preferences.
        """
        )

        # Session summary
        st.markdown("### Session Summary")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Samples Tasted", stats.get("total_cycles", 0))

        with col2:
            st.metric("Session Duration", duration_str)

        st.markdown("---")

        # Return button
        if st.button("🏠 Return to Home", type="primary", width='stretch'):
            # Clear session state
            st.query_params.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    except Exception as e:
        logger.error(f"Error displaying subject completion screen: {e}", exc_info=True)
        st.error("An error occurred while displaying the completion screen.")
        if st.button("Return to Home"):
            st.query_params.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def show_moderator_completion_summary():
    """
    Display comprehensive session summary for moderators.

    Shows detailed statistics, optimal solution, convergence analysis,
    and provides data export and session reset options.
    """
    try:
        session_id = st.session_state.get("session_id")
        if not session_id:
            st.error("Session not found.")
            if st.button("Return to Setup"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            return

        # Load session data
        session = get_session(session_id)
        if not session:
            st.error("Session data not found. Data may have been deleted.")
            if st.button("Return to Setup"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            return

        samples = get_session_samples(session_id)
        stats = get_session_stats(session_id)

        # Header
        st.markdown("# ✅ Session Complete")
        st.markdown("---")

        # Session Information Section
        st.markdown("### Session Information")

        info_col1, info_col2, info_col3 = st.columns(3)

        with info_col1:
            st.metric("Session Code", session.get("session_code", "N/A"))
            st.metric("Participant ID", session.get("user_id", "N/A"))

        with info_col2:
            created_at = session.get("created_at", "Unknown")
            if created_at != "Unknown":
                try:
                    dt = datetime.fromisoformat(created_at)
                    created_at = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            st.metric("Created", created_at)
            st.metric("Status", "✅ Completed")

        with info_col3:
            # Calculate duration
            duration_str = "Unknown"
            if stats.get("created_at") and stats.get("last_cycle_at"):
                try:
                    start = datetime.fromisoformat(stats["created_at"])
                    end = datetime.fromisoformat(stats["last_cycle_at"])
                    duration = end - start
                    minutes = int(duration.total_seconds() // 60)
                    seconds = int(duration.total_seconds() % 60)
                    duration_str = f"{minutes} min {seconds} sec"
                except Exception as e:
                    logger.warning(f"Could not calculate duration: {e}")

            st.metric("Duration", duration_str)
            st.metric("Questionnaire", session.get("questionnaire_name", "N/A"))

        st.markdown("---")

        # Performance Metrics Section
        st.markdown("### Performance Metrics")

        metric_col1, metric_col2, metric_col3 = st.columns(3)

        total_cycles = stats.get("total_cycles", 0)
        total_samples = len(samples)

        with metric_col1:
            st.metric("Total Cycles", total_cycles)

        with metric_col2:
            st.metric("Total Samples", total_samples)

        # Find best rating
        best_rating = None
        best_sample = None
        target_var = None

        try:
            questionnaire_name = session.get("questionnaire_name")
            if questionnaire_name:
                metadata = get_questionnaire_metadata(questionnaire_name)
                target_var = metadata.get("target_variable")

                if target_var:
                    ratings = []
                    for sample in samples:
                        answer = sample.get("questionnaire_answer", {})
                        if target_var in answer:
                            ratings.append(answer[target_var])

                    if ratings:
                        best_rating = max(ratings)
                        best_idx = ratings.index(best_rating)
                        best_sample = samples[best_idx]

        except Exception as e:
            logger.warning(f"Could not determine best rating: {e}")

        with metric_col3:
            if best_rating is not None:
                st.metric("Best Rating", f"{best_rating:.2f}")
            else:
                st.metric("Best Rating", "N/A")

        st.markdown("---")

        # Optimal Solution Section
        if best_sample:
            st.markdown("### Optimal Solution")

            concentrations = best_sample.get("ingredient_concentration", {})

            if concentrations:
                # Get ingredient ranges from experiment config
                experiment_config = session.get("experiment_config", {})
                ingredients = experiment_config.get("ingredients", [])

                # Create a mapping of ingredient names to their ranges
                ingredient_ranges = {}
                for ing in ingredients:
                    name = ing.get("name")
                    min_c = ing.get("min_concentration_mM", 0)
                    max_c = ing.get("max_concentration_mM", 100)
                    ingredient_ranges[name] = (min_c, max_c)

                # Display each ingredient with progress bar
                for ingredient_name, concentration in concentrations.items():
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        # Calculate percentage if range is available
                        if ingredient_name in ingredient_ranges:
                            min_c, max_c = ingredient_ranges[ingredient_name]
                            if max_c > min_c:
                                percentage = (concentration - min_c) / (max_c - min_c)
                                st.progress(
                                    percentage,
                                    text=f"{ingredient_name}: {concentration:.2f} mM",
                                )
                            else:
                                st.write(f"{ingredient_name}: {concentration:.2f} mM")
                        else:
                            st.write(f"{ingredient_name}: {concentration:.2f} mM")

                    with col2:
                        if ingredient_name in ingredient_ranges:
                            min_c, max_c = ingredient_ranges[ingredient_name]
                            if max_c > min_c:
                                percentage = int(
                                    (concentration - min_c) / (max_c - min_c) * 100
                                )
                                st.metric("", f"{percentage}%")

                if best_rating is not None:
                    st.info(f"**Optimal Rating:** {best_rating:.2f}")

            st.markdown("---")

        # Convergence Analysis (if BO was used)
        experiment_config = session.get("experiment_config", {})
        bo_config = experiment_config.get("bayesian_optimization", {})

        if bo_config.get("enabled", False):
            st.markdown("### Convergence Analysis")

            try:
                from robotaste.core.bo_utils import check_convergence

                stopping_criteria = bo_config.get("stopping_criteria")
                convergence = check_convergence(session_id, stopping_criteria)

                status_emoji = convergence.get("status_emoji", "🔴")
                reason = convergence.get("reason", "Unknown")
                confidence = convergence.get("confidence", 0.0)

                st.markdown(f"**Status:** {status_emoji} {reason}")
                st.markdown(f"**Confidence:** {confidence*100:.1f}%")

                # Show criteria
                with st.expander("Convergence Details", expanded=False):
                    criteria_met = convergence.get("criteria_met", [])
                    criteria_failed = convergence.get("criteria_failed", [])

                    if criteria_met:
                        st.markdown("**Criteria Met:**")
                        for criterion in criteria_met:
                            st.markdown(f"- ✅ {criterion}")

                    if criteria_failed:
                        st.markdown("**Criteria Not Met:**")
                        for criterion in criteria_failed:
                            st.markdown(f"- ❌ {criterion}")

            except Exception as e:
                logger.warning(f"Could not load convergence analysis: {e}")
                st.info("Convergence analysis not available")

            st.markdown("---")

        # Action Buttons
        st.markdown("### Actions")

        action_col1, action_col2, action_col3 = st.columns(3)

        with action_col1:
            # Download CSV
            if st.button("📥 Download CSV", width='stretch'):
                try:
                    # Create DataFrame from samples
                    data = []
                    for sample in samples:
                        row = {
                            "cycle": sample.get("cycle_number"),
                            "created_at": sample.get("created_at"),
                        }

                        # Add ingredient concentrations
                        concentrations = sample.get("ingredient_concentration", {})
                        for ing_name, conc in concentrations.items():
                            row[f"{ing_name}_mM"] = conc

                        # Add questionnaire answer
                        answer = sample.get("questionnaire_answer", {})
                        if target_var and target_var in answer:
                            row[target_var] = answer[target_var]

                        data.append(row)

                    df = pd.DataFrame(data)
                    csv = df.to_csv(index=False)

                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"session_{session.get('session_code', session_id)}.csv",
                        mime="text/csv",
                    )

                except Exception as e:
                    logger.error(f"Error creating CSV: {e}", exc_info=True)
                    st.error("Failed to create CSV export")

        with action_col2:
            # Download JSON
            if st.button("📥 Download JSON", width='stretch'):
                try:
                    import json

                    export_data = {
                        "session": session,
                        "samples": samples,
                        "statistics": stats,
                    }

                    json_str = json.dumps(export_data, indent=2, default=str)

                    st.download_button(
                        label="Download JSON",
                        data=json_str,
                        file_name=f"session_{session.get('session_code', session_id)}.json",
                        mime="application/json",
                    )

                except Exception as e:
                    logger.error(f"Error creating JSON: {e}", exc_info=True)
                    st.error("Failed to create JSON export")

        with action_col3:
            # Start New Session
            if st.button(
                "🔄 Start New Session", type="primary", width='stretch'
            ):
                # Clear session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            # Return button
        if st.button("🏠 Return to Home", type="primary", width='stretch'):
            # Clear session state
            st.query_params.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    except Exception as e:
        logger.error(
            f"Error displaying moderator completion summary: {e}", exc_info=True
        )
        st.error("An error occurred while displaying the completion summary.")
        if st.button("Return to Setup"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
