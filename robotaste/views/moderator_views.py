"""
Mode-Specific View Renderers for Moderator Monitoring

Renders visualizations for predetermined, user_selected, and bo_selected modes.

Author: RoboTaste Team
Version: 1.0
"""

import streamlit as st
import pandas as pd
import logging
from typing import Dict, Any

from robotaste.core.moderator_metrics import (
    get_predetermined_metrics,
    get_user_selection_metrics,
    get_bo_mode_metrics
)
from robotaste.utils.visualization_helpers import (
    create_empty_state_message,
    create_timeline_chart,
    create_scatter_plot,
    create_bar_chart,
    create_protocol_schedule_gantt
)

logger = logging.getLogger(__name__)


# =============================================================================
# Overview Tab (for mixed-mode protocols)
# =============================================================================

def render_overview_tab(session_id: str, mode_info: Dict[str, Any]):
    """
    Render overview tab showing protocol structure and overall progress.

    Args:
        session_id: Session UUID
        mode_info: Output from get_current_mode_info()
    """
    st.markdown("### Protocol Overview")

    # Current cycle status
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current Cycle", mode_info["current_cycle"])
    with col2:
        mode_display = mode_info["current_mode"].replace("_", " ").title()
        st.metric("Current Mode", mode_display)
    with col3:
        mode_type = "Mixed-Mode" if mode_info["is_mixed_mode"] else "Single-Mode"
        st.metric("Protocol Type", mode_type)

    st.markdown("---")

    # Protocol schedule visualization
    schedule = mode_info.get("schedule", [])
    if schedule:
        st.markdown("### Schedule")
        fig = create_protocol_schedule_gantt(schedule)
        st.plotly_chart(fig, use_container_width=True)

        # Schedule details table
        with st.expander("📋 Schedule Details", expanded=False):
            for i, entry in enumerate(schedule, 1):
                cycle_range = entry.get("cycle_range", {})
                mode = entry.get("mode", "user_selected")
                start = cycle_range.get("start", 0)
                end = cycle_range.get("end", 0)

                st.markdown(f"**Block {i}:** Cycles {start}-{end} ({end - start + 1} cycles)")
                st.markdown(f"- **Mode:** {mode.replace('_', ' ').title()}")

                config = entry.get("config", {})
                if config:
                    st.markdown("- **Config:**")
                    for key, value in config.items():
                        st.markdown(f"  - {key}: {value}")

                if mode in ["predetermined", "predetermined_absolute"]:
                    predetermined_samples = entry.get("predetermined_samples", [])
                    st.markdown(f"  - Predetermined samples: {len(predetermined_samples)}")
                elif mode == "predetermined_randomized":
                    sample_bank = entry.get("sample_bank", {})
                    samples = sample_bank.get("samples", [])
                    design_type = sample_bank.get("design_type", "randomized")
                    st.markdown(f"  - Sample bank: {len(samples)} samples ({design_type})")

                st.markdown("")
    else:
        st.info("No protocol schedule available. This session may be using manual configuration.")

    st.markdown("---")

    # Mode-specific progress metrics
    st.markdown("### Progress by Mode")

    metrics = {}
    if "predetermined" in mode_info["all_modes"]:
        metrics["Predetermined"] = get_predetermined_metrics(session_id)
    if "user_selected" in mode_info["all_modes"]:
        metrics["User Selected"] = get_user_selection_metrics(session_id)
    if "bo_selected" in mode_info["all_modes"]:
        metrics["BO Selected"] = get_bo_mode_metrics(session_id)

    if metrics:
        cols = st.columns(len(metrics))
        for i, (mode_name, mode_metrics) in enumerate(metrics.items()):
            with cols[i]:
                if mode_name == "Predetermined":
                    total = mode_metrics["total_predetermined_cycles"]
                    completed = mode_metrics["completed_predetermined"]
                elif mode_name == "User Selected":
                    total = mode_metrics["total_user_cycles"]
                    completed = mode_metrics["completed_user_cycles"]
                else:  # BO
                    total = mode_metrics["total_bo_cycles"]
                    completed = mode_metrics["completed_bo_cycles"]

                progress_pct = (completed / total * 100) if total > 0 else 0
                st.metric(mode_name, f"{completed}/{total}", f"{progress_pct:.0f}%")


# =============================================================================
# Predetermined Mode View
# =============================================================================

def render_predetermined_view(session_id: str):
    """
    Render predetermined mode view showing protocol compliance.

    Args:
        session_id: Session UUID
    """
    st.markdown("### Predetermined Mode")
    st.caption("Showing samples delivered according to protocol specifications")

    metrics = get_predetermined_metrics(session_id)

    # Metrics cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Predetermined", metrics["total_predetermined_cycles"])
    with col2:
        st.metric("Completed", metrics["completed_predetermined"])
    with col3:
        adherence_pct = metrics["adherence_rate"] * 100
        st.metric("Adherence", f"{adherence_pct:.0f}%")

    st.markdown("---")

    # Samples table
    samples = metrics["samples"]
    if samples:
        st.markdown("### Predetermined Samples")

        rows = []
        for sample in samples:
            is_completed = sample.get("is_completed", False)

            row = {
                "Cycle": sample.get("cycle_number", "?"),
                "Status": "✅ Completed" if is_completed else "⏳ Pending",
                "Timestamp": sample.get("created_at", "")[:19] if sample.get("created_at") else "-",
            }

            # Add concentrations
            conc = sample.get("ingredient_concentration", {})
            if conc:  # Only iterate if conc is not None
                for ing_name, conc_val in conc.items():
                    row[f"{ing_name} (mM)"] = f"{conc_val:.2f}"

            # Add questionnaire response (only for completed samples)
            if is_completed:
                quest = sample.get("questionnaire_answer", {})
                for q_key, q_val in quest.items():
                    # Initialize column if not exists
                    col_name = q_key.replace("_", " ").title()
                    if col_name not in row:
                        row[col_name] = q_val
                    else:
                        row[col_name] = q_val
            else:
                # Add empty values for questionnaire columns (will be filled as samples complete)
                # We'll add columns dynamically based on first completed sample
                pass

            rows.append(row)

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Timeline of responses (only for completed samples)
        completed_samples = [s for s in samples if s.get("is_completed", False)]
        if len(completed_samples) > 1:
            st.markdown("### Response Timeline")

            cycles = [s["cycle_number"] for s in completed_samples]

            # Extract target variable (assume first questionnaire key is target)
            if completed_samples[0].get("questionnaire_answer"):
                target_key = list(completed_samples[0]["questionnaire_answer"].keys())[0]
                values = [s["questionnaire_answer"].get(target_key, 0) for s in completed_samples]

                fig = create_timeline_chart(
                    cycles,
                    values,
                    "Predetermined Samples - Response Over Time",
                    target_key.replace("_", " ").title(),
                    color="#A855F7"
                )
                st.plotly_chart(fig, use_container_width=True)
        elif len(completed_samples) == 1:
            st.info("Complete at least 2 samples to see the response timeline.")
    else:
        st.info("No predetermined cycles in protocol.")


# =============================================================================
# User Selection Mode View
# =============================================================================

def render_user_selection_view(session_id: str):
    """
    Render user_selected mode view with trajectory and exploration metrics.

    Args:
        session_id: Session UUID
    """
    st.markdown("### User Selection Mode")
    st.caption("Showing user-driven exploration patterns")

    metrics = get_user_selection_metrics(session_id)

    # Metrics cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total User Cycles", metrics["total_user_cycles"])
    with col2:
        st.metric("Completed", metrics["completed_user_cycles"])
    with col3:
        coverage_pct = (metrics["exploration_coverage"] or 0) * 100
        st.metric("Exploration", f"{coverage_pct:.0f}%")
    with col4:
        traj_len = metrics["avg_trajectory_length"]
        if traj_len is not None:
            st.metric("Avg Trajectory", f"{traj_len:.1f} clicks")
        else:
            st.metric("Avg Trajectory", "N/A")

    st.markdown("---")

    # Data availability notice
    data_avail = metrics["data_availability"]
    if not data_avail["trajectory_clicks"]:
        st.info(
            "ℹ️ **Trajectory data not currently collected.** "
            "To enable trajectory tracking, ensure `trajectory_clicks` is being stored in `selection_data`."
        )

    if not data_avail["reaction_time_ms"]:
        st.info(
            "ℹ️ **Reaction time data not currently collected.** "
            "To enable reaction time tracking, ensure `reaction_time_ms` is being stored in `selection_data`."
        )

    # Samples visualization
    samples = metrics["samples"]
    if samples and len(samples) > 1:
        st.markdown("### Exploration Pattern")

        # Extract concentration space (for 2D visualization)
        conc_data = [s.get("ingredient_concentration", {}) for s in samples]
        if conc_data and len(conc_data[0]) == 2:
            # Binary mixture - scatter plot
            ingredient_names = list(conc_data[0].keys())
            x_values = [c[ingredient_names[0]] for c in conc_data]
            y_values = [c[ingredient_names[1]] for c in conc_data]
            cycle_labels = [s["cycle_number"] for s in samples]

            # Color by response if available
            color_values = None
            if samples[0].get("questionnaire_answer"):
                target_key = list(samples[0]["questionnaire_answer"].keys())[0]
                color_values = [s["questionnaire_answer"].get(target_key, 0) for s in samples]

            fig = create_scatter_plot(
                x_values,
                y_values,
                "User Selection - Concentration Space",
                f"{ingredient_names[0]} (mM)",
                f"{ingredient_names[1]} (mM)",
                cycle_labels,
                color_values,
                "Rating"
            )
            st.plotly_chart(fig, use_container_width=True)

        # Timeline of responses
        st.markdown("### Response Timeline")
        cycles = [s["cycle_number"] for s in samples]

        if samples[0].get("questionnaire_answer"):
            target_key = list(samples[0]["questionnaire_answer"].keys())[0]
            values = [s["questionnaire_answer"].get(target_key, 0) for s in samples]

            fig = create_timeline_chart(
                cycles,
                values,
                "User Selection - Response Over Time",
                target_key.replace("_", " ").title(),
                color="#14B8A6"
            )
            st.plotly_chart(fig, use_container_width=True)

    elif samples and len(samples) == 1:
        st.info("Only one sample completed. Need at least 2 samples for visualization.")
    else:
        st.info("No user-selected samples completed yet.")


# =============================================================================
# BO Mode View
# =============================================================================

def render_bo_view(session_id: str):
    """
    Render bo_selected mode view with convergence analysis.

    Reuses existing BO visualization components from moderator.py
    (single_bo and binary_bo functions).

    Args:
        session_id: Session UUID
    """
    from robotaste.data.database import get_session
    from robotaste.views.moderator import single_bo, binary_bo

    st.markdown("### Bayesian Optimization Mode")
    st.caption("Showing BO convergence and predictions")

    metrics = get_bo_mode_metrics(session_id)

    # Metrics cards
    convergence_status = metrics.get("convergence_status", {})
    convergence_metrics = metrics.get("convergence_metrics", {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total BO Cycles", metrics["total_bo_cycles"])
    with col2:
        st.metric("Completed", metrics["completed_bo_cycles"])
    with col3:
        best_values = convergence_metrics.get("best_values", [])
        best_value = max(best_values) if best_values else 0
        st.metric("Best Observed", f"{best_value:.2f}")
    with col4:
        status_emoji = convergence_status.get("status_emoji", "🔴")
        recommendation = convergence_status.get("recommendation", "continue")

        if "stop" in recommendation:
            status_text = "Converged"
            status_color = "#10B981"
        elif "consider" in recommendation:
            status_text = "Nearing"
            status_color = "#F59E0B"
        else:
            status_text = "Optimizing"
            status_color = "#6B7280"

        st.markdown("**Status**")
        st.markdown(
            f'<h3 style="color: {status_color}; margin: 0;">{status_emoji} {status_text}</h3>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # BO Visualizations (reuse existing functions)
    session = get_session(session_id)
    if session:
        experiment_config = session.get("experiment_config", {})
        num_ingredients = experiment_config.get("num_ingredients", 2)

        st.markdown("### BO Predictions")

        if num_ingredients == 1:
            single_bo()
        elif num_ingredients == 2:
            binary_bo()
        else:
            st.warning(f"⚠️ BO visualizations not available for {num_ingredients} ingredients")

    # Convergence details
    with st.expander("📊 Convergence Details", expanded=False):
        criteria_met = convergence_status.get("criteria_met", [])
        criteria_failed = convergence_status.get("criteria_failed", [])
        confidence = convergence_status.get("confidence", 0.0)

        if criteria_met:
            st.markdown("**✅ Criteria Met:**")
            for criterion in criteria_met:
                st.markdown(f"- {criterion}")

        if criteria_failed:
            st.markdown("**❌ Criteria Not Met:**")
            for criterion in criteria_failed:
                st.markdown(f"- {criterion}")

        st.markdown(f"**Confidence:** {confidence*100:.1f}%")
