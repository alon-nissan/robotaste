"""
Moderator Interface (minimal placeholder)

This file provides a concise, organized moderator UI with three tabs:
- Live Monitor: real-time sample / session view (placeholder)
- Analytics: summary statistics and visualizations (placeholder)
- Settings: session controls and export (placeholder)

These are intentionally lightweight placeholders to make the UI easy to extend later.
"""

from typing import Optional
import time

import streamlit as st

# Local imports (used by real implementation; kept here for later expansion)
from callback import (
    INTERFACE_2D_GRID,
    INTERFACE_SLIDERS,
    MultiComponentMixture,
    start_trial,
    calculate_stock_volumes,
)
from session_manager import display_session_qr_code, get_session_info
from sql_handler import (
    get_session,
    get_session_samples,
    export_session_csv,
    get_session_stats,
    get_latest_sample_concentrations,
)
from state_machine import ExperimentPhase, ExperimentStateMachine


def render_live_monitor(session_id: Optional[str]) -> None:
    """Placeholder for live monitoring UI.

    - Shows latest sample concentrations (if available).
    - Provides a refresh button and simple status indicators.
    """
    st.subheader("Live Monitor")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Refresh"):
            st.experimental_rerun()

    try:
        if session_id:
            latest = get_latest_sample_concentrations(session_id)
        else:
            latest = None
    except Exception:
        latest = None

    if latest:
        st.markdown("**Latest concentrations (mM)**")
        st.table(latest)
    else:
        st.info("No recent samples available. Waiting for participant data...")

    st.markdown("---")
    st.caption("This view will show live streamed values and quick warnings (e.g., out-of-range concentrations)")


def render_analytics(session_id: Optional[str]) -> None:
    """Placeholder for analytics UI.

    - Displays simple summary metrics and notes where plots will be.
    """
    st.subheader("Analytics")

    try:
        stats = get_session_stats(session_id) if session_id else None
    except Exception:
        stats = None

    if stats:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Samples", stats.get("total_samples", "—"))
        with col2:
            st.metric("Unique Participants", stats.get("participants", "—"))
        with col3:
            st.metric("BO Active", "Yes" if stats.get("bo_active") else "No")

        st.markdown("---")
        st.info("Detailed plots (response landscape, BO acquisition, variance maps) will appear here.")
    else:
        st.info("Analytics are not available yet. Run an experiment session to populate analytics.")


def render_settings(session_id: Optional[str]) -> None:
    """Placeholder for moderator settings and session management.

    - Toggles for auto-refresh, dark-mode hints, and an export button.
    """
    st.subheader("Settings")

    auto_refresh = st.checkbox("Auto-refresh live monitor", value=False, key="mod_auto_refresh")
    if auto_refresh:
        st.info("Auto-refresh enabled (placeholder).")

    if st.button("Export Session CSV"):
        try:
            if not session_id:
                st.warning("No session selected to export.")
            else:
                path = export_session_csv(session_id)
                st.success(f"Exported session CSV to: {path}")
        except Exception as e:
            st.error(f"Failed to export session: {e}")

    st.markdown("---")
    st.caption("More settings (BO tuning, participant management, session reset) will be added here.")
                        max_value=5.0,
# Tail content removed. The moderator interface is intentionally minimal here.
                    success_db = update_session_with_config(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.participant,
                        num_ingredients=num_ingredients,
                        interface_type=interface_type,
                        method=method,
                        ingredients=ingredients_for_db,
                        question_type_id=st.session_state.get(
                            "selected_questionnaire_type", 1
                        ),
                        bo_config=bo_config,
                        experiment_config=full_experiment_config,
                    )

                    if success_db:
                        st.session_state.session_created_in_db = True
                        st.success("Session created in database")
                    else:
                        st.error(
                            "Failed to create session in database. Please try again."
                        )
                        st.stop()

                num_ingredients = st.session_state.experiment_config["num_ingredients"]

                # Build ingredient configs with custom ranges
                # FIXED: Pass moderator's actual ingredient selection to start_trial
                ingredient_configs = []
                for ingredient_name in st.session_state.selected_ingredients:
                    # Get base configuration from defaults
                    from callback import DEFAULT_INGREDIENT_CONFIG

                    base_config = next(
                        (
                            ing
                            for ing in DEFAULT_INGREDIENT_CONFIG
                            if ing["name"] == ingredient_name
                        ),
                        None,
                    )

                    if not base_config:
                        st.error(
                            f"Ingredient '{ingredient_name}' not found in configuration"
                        )
                        continue

                    # Create a copy and apply custom ranges if set
                    custom_config = base_config.copy()

                    if ingredient_name in st.session_state.ingredient_ranges:
                        ranges = st.session_state.ingredient_ranges[ingredient_name]
                        custom_config["min_concentration"] = ranges["min"]
                        custom_config["max_concentration"] = ranges["max"]

                    ingredient_configs.append(custom_config)

                # Validate ingredient count matches
                if len(ingredient_configs) != num_ingredients:
                    st.error(
                        f"Configuration error: Expected {num_ingredients} ingredients, got {len(ingredient_configs)}"
                    )
                else:
                    # Start trial with moderator's ingredient selection
                    success = start_trial(
                        "mod",
                        st.session_state.participant,
                        method,
                        num_ingredients,
                        selected_ingredients=st.session_state.selected_ingredients,
                        ingredient_configs=ingredient_configs,
                    )
                    if success:
                        clear_canvas_state()  # Clear any previous canvas state
                        # Transition to trial_started phase (replaces session_active = True)
                        # Note: start_trial() in callback.py handles the phase transition
                        st.toast(f"Trial started for {st.session_state.participant}")
                        time.sleep(1)
                        st.rerun()

        # Helper message at bottom of setup section
        st.markdown("---")

    # ===== SUBJECT CONNECTION & ACCESS SECTION =====
    st.markdown("---")
    from state_machine import recover_phase_from_database

    recovered_phase = recover_phase_from_database(st.session_state.session_id)
    if recovered_phase == "waiting":
        with st.expander("Subject Access - QR Code & Session Info", expanded=False):
            st.info(
                "Waiting for subject to join session... Share the QR code or session code below."
            )

            # Smart URL detection - production first, then localhost for development
            try:
                server_address = st.get_option("browser.serverAddress")
                if server_address and "streamlit.app" in server_address:
                    base_url = f"https://{server_address}"
                elif st.get_option("server.headless"):
                    # Running in cloud/headless mode, use production URL
                    base_url = "https://robotaste.streamlit.app"
                else:
                    # Check if running locally (port 8501 indicates local development)
                    base_url = "http://localhost:8501"  # Local development
            except:
                # Default to production URL for QR codes
                base_url = "https://robotaste.streamlit.app"

            display_session_qr_code(
                st.session_state.session_code, base_url, context="waiting"
            )
    else:
        st.success("Subject device connected and active")

    # ===== ORGANIZED TABS FOR MONITORING & MANAGEMENT =====
    # Only show monitoring tabs when trial is in active phase
    if ExperimentStateMachine.should_show_monitoring():
        st.markdown("---")

        # Organized, minimal tabs calling placeholder renderers
        tab_live, tab_analytics, tab_settings = st.tabs(
            ["Live Monitor", "Analytics", "Settings"]
        )

        with tab_live:
            render_live_monitor(st.session_state.session_id)

        with tab_analytics:
            render_analytics(st.session_state.session_id)

        with tab_settings:
            render_settings(st.session_state.session_id)
                                # Layer 2: Uncertainty Contours (±2σ)
                                fig.add_trace(
                                    go.Contour(
                                        x=x_vals,
                                        y=y_vals,
                                        z=z_unc * 2,  # ±2σ
                                        showscale=False,
                                        contours=dict(
                                            coloring="none",
                                            showlabels=True,
                                            labelfont=dict(size=10, color="white"),
                                        ),
                                        line=dict(color="white", width=1.5, dash="dot"),
                                        name="Uncertainty (±2σ)",
                                        hovertemplate="<b>Uncertainty</b><br>%{x:.2f}, %{y:.2f}<br>±2σ: %{z:.2f}<extra></extra>",
                                    )
                                )

                                # Layer 3: Acquisition Function Contours
                                acq_name = (
                                    "Expected Improvement"
                                    if acq_func == "ei"
                                    else "Upper Confidence Bound"
                                )
                                fig.add_trace(
                                    go.Contour(
                                        x=x_vals,
                                        y=y_vals,
                                        z=z_acq,
                                        showscale=False,
                                        contours=dict(
                                            coloring="none",
                                            showlabels=True,
                                            labelfont=dict(size=10, color="cyan"),
                                        ),
                                        line=dict(color="cyan", width=2, dash="dash"),
                                        name=acq_name,
                                        hovertemplate=f"<b>{acq_name}</b><br>%{{x:.2f}}, %{{y:.2f}}<br>Value: %{{z:.3f}}<extra></extra>",
                                    )
                                )

                                # Layer 4: Training Data Scatter Points
                                if training_df is not None and len(training_df) > 0:
                                    fig.add_trace(
                                        go.Scatter(
                                            x=training_df[ing_names[0]],
                                            y=training_df[ing_names[1]],
                                            mode="markers",
                                            marker=dict(
                                                size=12,
                                                color=training_df["target_value"],
                                                colorscale="RdYlGn",
                                                showscale=False,
                                                symbol="circle",
                                                line=dict(color="black", width=2),
                                            ),
                                            name="Observed Data",
                                            text=[
                                                f"Score: {score:.2f}"
                                                for score in training_df["target_value"]
                                            ],
                                            hovertemplate="<b>Observed</b><br>%{x:.2f}, %{y:.2f}<br>%{text}<extra></extra>",
                                        )
                                    )

                                # Layer 5: Next Recommended Point
                                fig.add_trace(
                                    go.Scatter(
                                        x=[next_point[0]],
                                        y=[next_point[1]],
                                        mode="markers",
                                        marker=dict(
                                            size=20,
                                            color="gold",
                                            symbol="star",
                                            line=dict(color="black", width=2),
                                        ),
                                        name=f"Next Sample (Pred: {next_pred:.2f})",
                                        hovertemplate=f"<b>Next Sample</b><br>%{{x:.2f}}, %{{y:.2f}}<br>Predicted: {next_pred:.2f}<br>Uncertainty: ±{next_unc*2:.2f}<br>{acq_func.upper()}: {next_acq:.3f}<extra></extra>",
                                    )
                                )

                                # Layout
                                fig.update_layout(
                                    title="Bayesian Optimization Landscape",
                                    xaxis_title=f"{ing_names[0]} Concentration (mM)",
                                    yaxis_title=f"{ing_names[1]} Concentration (mM)",
                                    height=600,
                                    hovermode="closest",
                                    showlegend=True,
                                    legend=dict(
                                        x=1.02,
                                        y=1,
                                        xanchor="left",
                                        yanchor="top",
                                        bgcolor="rgba(255, 255, 255, 0.8)",
                                        bordercolor="black",
                                        borderwidth=1,
                                    ),
                                )

                                st.plotly_chart(fig, use_container_width=True)

                                # Add legend explanation
                                st.caption(
                                    "**Legend:** "
                                    "🟢 Heatmap = GP predicted scores | "
                                    "⚪ Dotted white contours = Uncertainty (±2σ) | "
                                    "🔵 Dashed cyan contours = Acquisition function | "
                                    "⚫ Black-outlined circles = Observed data | "
                                    "⭐ Gold star = Next recommended sample"
                                )

                            elif bo_model and num_ingredients > 2:
                                # Multi-ingredient visualization - Parallel coordinates
                                training_df = sql.get_training_data(
                                    st.session_state.session_id,
                                    only_final=bo_status.get("bo_config", {}).get(
                                        "only_final_responses", True
                                    ),
                                )

                                if training_df is not None and len(training_df) > 0:
                                    ing_names = [ing["name"] for ing in ingredients]

                                    # Create dimensions for parallel coordinates
                                    dimensions = []
                                    for ing_name in ing_names:
                                        dimensions.append(
                                            dict(
                                                label=ing_name,
                                                values=training_df[ing_name],
                                            )
                                        )

                                    # Add target variable
                                    dimensions.append(
                                        dict(
                                            label="Score",
                                            values=training_df["target_value"],
                                        )
                                    )

                                    fig = go.Figure(
                                        data=go.Parcoords(
                                            line=dict(
                                                color=training_df["target_value"],
                                                colorscale="RdYlGn",
                                                showscale=True,
                                                cmin=training_df["target_value"].min(),
                                                cmax=training_df["target_value"].max(),
                                            ),
                                            dimensions=dimensions,
                                        )
                                    )

                                    fig.update_layout(
                                        height=400,
                                        title="Ingredient Concentrations vs Scores",
                                    )

                                    st.plotly_chart(fig, use_container_width=True)

                                    # ===== 1D SLICE VIEWER =====
                                    with st.expander(
                                        "📊 1D Slice Analysis (GP Predictions & Uncertainty)",
                                        expanded=False,
                                    ):
                                        st.markdown(
                                            "Explore how the GP model predicts scores along individual ingredient dimensions."
                                        )

                                        # Get current best sample
                                        best_idx = training_df["target_value"].idxmax()
                                        best_values = {
                                            ing_name: training_df[ing_name].iloc[
                                                best_idx
                                            ]
                                            for ing_name in ing_names
                                        }

                                        # Select which ingredient to vary
                                        selected_ing_idx = st.selectbox(
                                            "Select ingredient to analyze:",
                                            range(len(ing_names)),
                                            format_func=lambda i: ing_names[i],
                                            key="slice_ingredient_select",
                                        )
                                        selected_ing = ing_names[selected_ing_idx]

                                        # Create sliders for other ingredients
                                        st.markdown("**Fix other ingredients at:**")
                                        fixed_values = {}
                                        cols_sliders = st.columns(
                                            min(3, num_ingredients - 1)
                                        )

                                        col_idx = 0
                                        for i, ing_name in enumerate(ing_names):
                                            if i == selected_ing_idx:
                                                continue

                                            ing_config = ingredients[i]
                                            with cols_sliders[
                                                col_idx % len(cols_sliders)
                                            ]:
                                                fixed_values[ing_name] = st.slider(
                                                    f"{ing_name} (mM)",
                                                    min_value=float(
                                                        ing_config["min_concentration"]
                                                    ),
                                                    max_value=float(
                                                        ing_config["max_concentration"]
                                                    ),
                                                    value=float(best_values[ing_name]),
                                                    step=(
                                                        ing_config["max_concentration"]
                                                        - ing_config[
                                                            "min_concentration"
                                                        ]
                                                    )
                                                    / 100,
                                                    key=f"slice_fixed_{ing_name}",
                                                )
                                            col_idx += 1

                                        # Generate 1D slice candidates
                                        selected_ing_config = ingredients[
                                            selected_ing_idx
                                        ]
                                        x_slice = np.linspace(
                                            selected_ing_config["min_concentration"],
                                            selected_ing_config["max_concentration"],
                                            200,
                                        )

                                        # Create candidate matrix
                                        candidates_slice = np.zeros(
                                            (200, num_ingredients)
                                        )
                                        for i, ing_name in enumerate(ing_names):
                                            if i == selected_ing_idx:
                                                candidates_slice[:, i] = x_slice
                                            else:
                                                candidates_slice[:, i] = fixed_values[
                                                    ing_name
                                                ]

                                        # Get predictions and uncertainties
                                        pred_slice, unc_slice = bo_model.predict(
                                            candidates_slice, return_std=True
                                        )

                                        # Calculate acquisition function
                                        acq_func = bo_status.get("bo_config", {}).get(
                                            "acquisition_function", "ei"
                                        )
                                        if acq_func == "ei":
                                            xi = bo_status.get("bo_config", {}).get(
                                                "ei_xi", 0.01
                                            )
                                            acq_slice = bo_model.expected_improvement(
                                                candidates_slice, xi=xi
                                            )
                                        else:
                                            kappa = bo_status.get("bo_config", {}).get(
                                                "ucb_kappa", 2.0
                                            )
                                            acq_slice = bo_model.upper_confidence_bound(
                                                candidates_slice, kappa=kappa
                                            )

                                        # Create 1D slice plot
                                        fig_slice = go.Figure()

                                        # GP mean prediction
                                        fig_slice.add_trace(
                                            go.Scatter(
                                                x=x_slice,
                                                y=pred_slice,
                                                mode="lines",
                                                name="GP Mean",
                                                line=dict(color="red", width=2),
                                            )
                                        )

                                        # Uncertainty bands (±2σ)
                                        fig_slice.add_trace(
                                            go.Scatter(
                                                x=np.concatenate(
                                                    [x_slice, x_slice[::-1]]
                                                ),
                                                y=np.concatenate(
                                                    [
                                                        pred_slice + 2 * unc_slice,
                                                        (pred_slice - 2 * unc_slice)[
                                                            ::-1
                                                        ],
                                                    ]
                                                ),
                                                fill="toself",
                                                fillcolor="rgba(255, 0, 0, 0.2)",
                                                line=dict(color="rgba(255, 0, 0, 0)"),
                                                name="±2σ Uncertainty",
                                                showlegend=True,
                                            )
                                        )

                                        # Observed training points on this slice dimension
                                        fig_slice.add_trace(
                                            go.Scatter(
                                                x=training_df[selected_ing],
                                                y=training_df["target_value"],
                                                mode="markers",
                                                name="Observed Data",
                                                marker=dict(
                                                    size=10,
                                                    color="red",
                                                    symbol="circle",
                                                    line=dict(color="black", width=2),
                                                ),
                                            )
                                        )

                                        # Acquisition function (on secondary y-axis)
                                        fig_slice.add_trace(
                                            go.Scatter(
                                                x=x_slice,
                                                y=acq_slice,
                                                mode="lines",
                                                name="Acquisition Function",
                                                line=dict(
                                                    color="green", width=2, dash="dash"
                                                ),
                                                yaxis="y2",
                                            )
                                        )

                                        # Find and mark next recommended point on this slice
                                        next_idx_slice = np.argmax(acq_slice)
                                        fig_slice.add_trace(
                                            go.Scatter(
                                                x=[x_slice[next_idx_slice]],
                                                y=[acq_slice[next_idx_slice]],
                                                mode="markers",
                                                name="Max Acquisition",
                                                marker=dict(
                                                    size=14,
                                                    color="green",
                                                    symbol="triangle-down",
                                                    line=dict(color="black", width=2),
                                                ),
                                                yaxis="y2",
                                                showlegend=True,
                                            )
                                        )

                                        fig_slice.update_layout(
                                            title=f"GP Predictions along {selected_ing}",
                                            xaxis_title=f"{selected_ing} Concentration (mM)",
                                            yaxis_title="Predicted Score",
                                            yaxis2=dict(
                                                title=f"{acq_func.upper()} Value",
                                                overlaying="y",
                                                side="right",
                                                showgrid=False,
                                            ),
                                            height=450,
                                            hovermode="x unified",
                                            legend=dict(
                                                orientation="h",
                                                yanchor="bottom",
                                                y=1.02,
                                                xanchor="right",
                                                x=1,
                                            ),
                                        )

                                        st.plotly_chart(
                                            fig_slice, use_container_width=True
                                        )

                                        # Show info about the slice
                                        st.caption(
                                            f"**Fixed values:** "
                                            + ", ".join(
                                                [
                                                    f"{k}: {v:.2f} mM"
                                                    for k, v in fixed_values.items()
                                                ]
                                            )
                                        )

                    except Exception as viz_error:
                        st.warning(f"Could not generate visualization: {viz_error}")

            except Exception as e:
                st.warning(f"Could not load BO status: {e}")

            st.markdown("---")

            # ===== OPTIMIZATION PROGRESS ANALYTICS =====
            st.markdown("### Optimization Progress")
            import sql_handler as sql

            training_df = sql.get_training_data(
                st.session_state.session_id,
                only_final=False,  # Include all samples for progress analysis
            )
            st.dataframe(training_df)
            bool_val = training_df is not None and len(training_df) >= 2
            st.write(f"Boolean value: {bool_val}")
            try:
                if training_df is not None and len(training_df) >= 2:
                    # Create two columns for side-by-side plots
                    col1, col2 = st.columns(2)

                    # ===== CONVERGENCE PLOT =====
                    with col1:
                        try:
                            # Calculate best score so far at each iteration
                            best_so_far = [
                                training_df.iloc[: i + 1]["target_value"].max()
                                for i in range(len(training_df))
                            ]

                            fig_convergence = go.Figure()

                            # Best so far line
                            fig_convergence.add_trace(
                                go.Scatter(
                                    x=list(range(1, len(best_so_far) + 1)),
                                    y=best_so_far,
                                    mode="lines+markers",
                                    name="Best Score Found",
                                    line=dict(color="#2E86AB", width=3),
                                    marker=dict(size=8, symbol="circle"),
                                )
                            )

                            # Add target line if configured
                            target_score = bo_status.get("bo_config", {}).get(
                                "target_score"
                            )
                            if target_score:
                                fig_convergence.add_hline(
                                    y=target_score,
                                    line_dash="dash",
                                    line_color="red",
                                    annotation_text=f"Target ({target_score})",
                                    annotation_position="right",
                                )

                            fig_convergence.update_layout(
                                title="Convergence Plot",
                                xaxis_title="Iteration",
                                yaxis_title="Best Score Found",
                                height=400,
                                showlegend=True,
                                hovermode="x unified",
                            )

                            st.plotly_chart(fig_convergence, use_container_width=True)

                        except Exception as e:
                            st.warning(f"Could not generate convergence plot: {e}")

                    # ===== SCORE DISTRIBUTION & PROGRESSION =====
                    with col2:
                        try:
                            # Calculate best so far for comparison
                            best_so_far = [
                                training_df.iloc[: i + 1]["target_value"].max()
                                for i in range(len(training_df))
                            ]

                            fig_scores = go.Figure()

                            # All samples
                            fig_scores.add_trace(
                                go.Scatter(
                                    x=list(range(1, len(training_df) + 1)),
                                    y=training_df["target_value"].tolist(),
                                    mode="markers",
                                    name="All Samples",
                                    marker=dict(
                                        size=10,
                                        color=training_df["target_value"],
                                        colorscale="Viridis",
                                        showscale=True,
                                        colorbar=dict(title="Score"),
                                        line=dict(color="black", width=1),
                                    ),
                                    opacity=0.7,
                                )
                            )

                            # Best so far line
                            fig_scores.add_trace(
                                go.Scatter(
                                    x=list(range(1, len(best_so_far) + 1)),
                                    y=best_so_far,
                                    mode="lines",
                                    name="Best So Far",
                                    line=dict(color="red", width=3),
                                )
                            )

                            fig_scores.update_layout(
                                title="All Scores vs Best So Far",
                                xaxis_title="Iteration",
                                yaxis_title="Score",
                                height=400,
                                showlegend=True,
                                hovermode="x unified",
                            )

                            st.plotly_chart(fig_scores, use_container_width=True)

                        except Exception as e:
                            st.warning(
                                f"Could not generate score progression plot: {e}"
                            )

                    # ===== SCORE DISTRIBUTION HISTOGRAM =====
                    try:
                        fig_hist = go.Figure()

                        fig_hist.add_trace(
                            go.Histogram(
                                x=training_df["target_value"],
                                nbinsx=min(20, len(training_df)),
                                marker=dict(
                                    color="#A23B72", line=dict(color="black", width=1)
                                ),
                                name="Score Distribution",
                            )
                        )

                        # Add mean line
                        mean_score = training_df["target_value"].mean()
                        fig_hist.add_vline(
                            x=mean_score,
                            line_dash="dash",
                            line_color="green",
                            annotation_text=f"Mean: {mean_score:.2f}",
                            annotation_position="top",
                        )

                        fig_hist.update_layout(
                            title="Score Distribution",
                            xaxis_title="Score",
                            yaxis_title="Frequency",
                            height=350,
                            showlegend=False,
                        )

                        st.plotly_chart(fig_hist, use_container_width=True)

                    except Exception as e:
                        st.warning(f"Could not generate score distribution: {e}")

                else:
                    st.info(
                        "Not enough data for optimization progress visualization (minimum 2 samples required)"
                    )

            except Exception as e:
                st.warning(f"Could not load optimization progress analytics: {e}")

            st.markdown("---")

            # ===== INGREDIENT ANALYSIS =====
            st.markdown("### Ingredient Analysis")

            try:
                if training_df is not None and len(training_df) >= 2:
                    # Get ingredient names (all columns except 'target_value')
                    ingredient_names = [
                        col for col in training_df.columns if col != "target_value"
                    ]
                    num_ingredients = len(ingredient_names)

                    # ===== INGREDIENT PAIR SCATTER PLOTS =====
                    if num_ingredients == 2:
                        # For 2 ingredients: single large scatter plot
                        try:
                            ing1, ing2 = ingredient_names[0], ingredient_names[1]

                            fig_scatter = go.Figure()

                            # All samples
                            fig_scatter.add_trace(
                                go.Scatter(
                                    x=training_df[ing1],
                                    y=training_df[ing2],
                                    mode="markers",
                                    name="Samples",
                                    marker=dict(
                                        size=12,
                                        color=training_df["target_value"],
                                        colorscale="RdYlGn",
                                        showscale=True,
                                        colorbar=dict(title="Score"),
                                        line=dict(color="black", width=1),
                                    ),
                                    text=[
                                        f"Score: {score:.2f}"
                                        for score in training_df["target_value"]
                                    ],
                                    hovertemplate=f"<b>{ing1}</b>: %{{x:.2f}}<br><b>{ing2}</b>: %{{y:.2f}}<br>%{{text}}<extra></extra>",
                                )
                            )

                            # Mark initial samples (first 5 or 10% whichever is smaller)
                            n_initial = min(5, max(1, len(training_df) // 10))
                            fig_scatter.add_trace(
                                go.Scatter(
                                    x=training_df[ing1].iloc[:n_initial],
                                    y=training_df[ing2].iloc[:n_initial],
                                    mode="markers",
                                    name="Initial Samples",
                                    marker=dict(
                                        size=15,
                                        symbol="square",
                                        color="rgba(255, 0, 0, 0)",
                                        line=dict(color="red", width=3),
                                    ),
                                )
                            )

                            # Mark best sample
                            best_idx = training_df["target_value"].idxmax()
                            fig_scatter.add_trace(
                                go.Scatter(
                                    x=[training_df[ing1].iloc[best_idx]],
                                    y=[training_df[ing2].iloc[best_idx]],
                                    mode="markers",
                                    name=f'Best Sample ({training_df["target_value"].iloc[best_idx]:.2f})',
                                    marker=dict(
                                        size=20,
                                        symbol="star",
                                        color="gold",
                                        line=dict(color="black", width=2),
                                    ),
                                )
                            )

                            fig_scatter.update_layout(
                                title=f"{ing1} vs {ing2}",
                                xaxis_title=f"{ing1} Concentration",
                                yaxis_title=f"{ing2} Concentration",
                                height=500,
                                showlegend=True,
                            )

                            st.plotly_chart(fig_scatter, use_container_width=True)

                        except Exception as e:
                            st.warning(f"Could not generate ingredient pair plot: {e}")

                    elif num_ingredients >= 3:
                        # For 3+ ingredients: grid of pairwise scatter plots
                        try:
                            st.markdown("#### Ingredient Pair Relationships")

                            # Create scatter matrix using plotly
                            from plotly.subplots import make_subplots
                            import numpy as np

                            # Limit to showing key pairs if too many ingredients
                            pairs_to_show = []
                            if num_ingredients <= 4:
                                # Show all pairs
                                for i in range(num_ingredients):
                                    for j in range(i + 1, num_ingredients):
                                        pairs_to_show.append(
                                            (ingredient_names[i], ingredient_names[j])
                                        )
                            else:
                                # Show first 6 most variable pairs
                                variances = {
                                    ing: training_df[ing].var()
                                    for ing in ingredient_names
                                }
                                top_ingredients = sorted(
                                    variances, key=variances.get, reverse=True
                                )[:3]
                                for i in range(len(top_ingredients)):
                                    for j in range(i + 1, len(top_ingredients)):
                                        pairs_to_show.append(
                                            (top_ingredients[i], top_ingredients[j])
                                        )

                            # Calculate grid dimensions
                            n_pairs = len(pairs_to_show)
                            n_cols = min(3, n_pairs)
                            n_rows = (n_pairs + n_cols - 1) // n_cols

                            fig_pairs = make_subplots(
                                rows=n_rows,
                                cols=n_cols,
                                subplot_titles=[
                                    f"{p[0]} vs {p[1]}" for p in pairs_to_show
                                ],
                                vertical_spacing=0.12,
                                horizontal_spacing=0.1,
                            )

                            for idx, (ing1, ing2) in enumerate(pairs_to_show):
                                row = idx // n_cols + 1
                                col = idx % n_cols + 1

                                fig_pairs.add_trace(
                                    go.Scatter(
                                        x=training_df[ing1],
                                        y=training_df[ing2],
                                        mode="markers",
                                        marker=dict(
                                            size=10,
                                            color=training_df["target_value"],
                                            colorscale="RdYlGn",
                                            showscale=(idx == 0),
                                            colorbar=(
                                                dict(title="Score", x=1.02)
                                                if idx == 0
                                                else None
                                            ),
                                            line=dict(color="black", width=1),
                                        ),
                                        showlegend=False,
                                        hovertemplate=f"<b>{ing1}</b>: %{{x:.2f}}<br><b>{ing2}</b>: %{{y:.2f}}<extra></extra>",
                                    ),
                                    row=row,
                                    col=col,
                                )

                                # Update axes labels
                                fig_pairs.update_xaxes(
                                    title_text=ing1, row=row, col=col
                                )
                                fig_pairs.update_yaxes(
                                    title_text=ing2, row=row, col=col
                                )

                            fig_pairs.update_layout(
                                height=300 * n_rows, showlegend=False
                            )

                            st.plotly_chart(fig_pairs, use_container_width=True)

                        except Exception as e:
                            st.warning(f"Could not generate ingredient pair plots: {e}")

                    # ===== INDIVIDUAL INGREDIENT IMPACT =====
                    try:
                        st.markdown("#### Individual Ingredient Impact")

                        # Create columns for ingredient plots
                        n_cols = min(3, num_ingredients)
                        cols = st.columns(n_cols)

                        for idx, ing_name in enumerate(ingredient_names):
                            with cols[idx % n_cols]:
                                fig_ing = go.Figure()

                                fig_ing.add_trace(
                                    go.Scatter(
                                        x=training_df[ing_name],
                                        y=training_df["target_value"],
                                        mode="markers",
                                        marker=dict(
                                            size=10,
                                            color=training_df["target_value"],
                                            colorscale="Viridis",
                                            line=dict(color="black", width=1),
                                        ),
                                        showlegend=False,
                                        hovertemplate=f"<b>{ing_name}</b>: %{{x:.2f}}<br><b>Score</b>: %{{y:.2f}}<extra></extra>",
                                    )
                                )

                                # Calculate correlation
                                correlation = training_df[ing_name].corr(
                                    training_df["target_value"]
                                )

                                fig_ing.update_layout(
                                    title=f"{ing_name}<br><sub>Correlation: {correlation:.3f}</sub>",
                                    xaxis_title=f"{ing_name} Concentration",
                                    yaxis_title="Score",
                                    height=300,
                                    margin=dict(t=60, b=40, l=40, r=20),
                                )

                                st.plotly_chart(fig_ing, use_container_width=True)

                    except Exception as e:
                        st.warning(
                            f"Could not generate individual ingredient plots: {e}"
                        )

                else:
                    st.info(
                        "Not enough data for ingredient analysis (minimum 2 samples required)"
                    )

            except Exception as e:
                st.warning(f"Could not load ingredient analysis: {e}")

            st.markdown("---")

            # ===== CYCLE HISTORY TABLE =====
            st.markdown("### Cycle History")

            try:
                cycle_num = get_current_cycle(st.session_state.session_id)
                st.info(f"Current Cycle: {cycle_num}")

                # Get all samples for this session
                samples = get_session_samples(
                    st.session_state.session_id, only_final=False
                )

                if samples:
                    # Build display dataframe
                    history_data = []
                    for sample in samples:
                        row = {
                            "Cycle": sample.get("cycle_number", "?"),
                            "Concentrations": ", ".join(
                                [
                                    f"{k}: {v:.1f}"
                                    for k, v in sample.get(
                                        "ingredient_concentration", {}
                                    ).items()
                                ]
                            ),
                            "Target Score": sample.get("questionnaire_answer", {}).get(
                                "overall_liking", "N/A"
                            ),
                            "Is Final": "Yes" if sample.get("is_final") else "",
                            "Timestamp": (
                                sample.get("created_at", "")[:19]
                                if sample.get("created_at")
                                else ""
                            ),
                        }
                        history_data.append(row)

                    df = pd.DataFrame(history_data)
                    st.dataframe(df, width="stretch")
                else:
                    st.info("No cycles completed yet")
            except Exception as e:
                st.warning(f"Could not load cycle history: {e}")

            st.markdown("---")

            # ===== CYCLE MANAGEMENT CONTROLS =====
            # Show controls when in SELECTION phase
            if phase == ExperimentPhase.SELECTION:
                st.markdown("### Session Management")

                # Only show Finish Session button (Start Next Cycle is now automatic)
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button(
                        "Finish Session",
                        type="primary",
                        width="stretch",
                        key="finish_session",
                    ):
                        # Show confirmation
                        if st.session_state.get("confirm_finish"):
                            # Update session state to completed
                            update_session_state(
                                st.session_state.session_id, "completed"
                            )

                            # Transition to complete
                            ExperimentStateMachine.transition(
                                new_phase=ExperimentPhase.COMPLETE,
                                session_id=st.session_state.session_id,
                            )
                            st.success("Session completed!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.session_state.confirm_finish = True
                            st.warning("Click 'Finish Session' again to confirm")
                            st.rerun()

        with main_tab3:
            st.markdown("### Session Settings")

            # Theme Settings
            st.markdown("#### Theme & Display")

            # Force dark mode option for better readability
            force_dark_mode = st.checkbox(
                "Force Dark Mode (recommended for better readability)",
                value=st.session_state.get("force_dark_mode", False),
                key="moderator_force_dark_mode",
                help="Enables dark mode theme to fix text visibility issues in select boxes",
            )

            if force_dark_mode != st.session_state.get("force_dark_mode", False):
                st.session_state.force_dark_mode = force_dark_mode
                # Add JavaScript to apply theme change
                if force_dark_mode:
                    st.markdown(
                        """
                        <script>
                        document.documentElement.setAttribute('data-theme', 'dark');
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                st.success(
                    "Theme setting updated! Refresh the page to see full effects."
                )

            # Display Settings
            auto_refresh = st.checkbox(
                "Auto-refresh monitoring",
                value=st.session_state.get("auto_refresh", True),
                key="moderator_auto_refresh_setting",
                help="Automatically refresh live monitoring every 15 seconds",
            )
            st.session_state.auto_refresh = auto_refresh

            st.divider()

            # Data Export Section
            st.markdown("#### Data Export")

            if st.button(
                "Export Session Data (CSV)",
                key="moderator_export_csv",
                help="Download all experiment data for this session as CSV file",
            ):
                try:
                    session_code = st.session_state.get(
                        "session_code", "default_session"
                    )

                    # Try new export function first, fallback to old one if needed
                    csv_data = export_session_csv(session_code)

                    if csv_data:
                        # Create download button
                        st.download_button(
                            label="Download CSV File",
                            data=csv_data,
                            file_name=f"robotaste_session_{session_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="download_csv_data",
                        )
                        st.success("Export data ready for download!")
                    else:
                        st.warning("No data found to export for this session.")

                except Exception as e:
                    st.error(f"Error exporting data: {e}")

            # Summary of data that will be exported
            with st.expander("What data gets exported?"):
                st.markdown(
                    """
                **CSV Export includes:**
                - Participant IDs and session information
                - Interface type (grid vs. slider) and method used
                - Random start settings and initial positions
                - All user interactions (clicks, slider adjustments)
                - Reaction times and timestamps
                - Actual concentrations (mM values) for all ingredients
                - Final response indicators
                - Questionnaire responses (if any)
                
                **Data is organized chronologically** for easy analysis in research tools like R, Python, or Excel.
                """
                )
    # ===== AUTO-REFRESH LOGIC =====
    if ExperimentStateMachine.should_show_monitoring():
        if st.session_state.get("auto_refresh", True):
            # Sync phase from database (in case subject progressed independently)
            session_info = get_session_info(st.session_state.session_id)
            if session_info:
                phase_from_db = session_info.get(
                    "current_phase", st.session_state.get("phase", "waiting")
                )
                if phase_from_db != st.session_state.get("phase"):
                    logger.info(
                        f"Moderator synced phase: {st.session_state.get('phase')} -> {phase_from_db}"
                    )
                    st.session_state.phase = phase_from_db
            time.sleep(15)
            st.rerun()
