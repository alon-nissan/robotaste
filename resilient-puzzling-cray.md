# Dynamic Moderator View System Design

## Problem Statement

The current moderator view ([moderator.py](robotaste/views/moderator.py)) is static and always displays ALL features including BO information, even when:
- The protocol doesn't use BO at all
- Cycles are in predetermined or user_selected modes
- BO is disabled in the configuration

**User Requirements:**
1. Design moderator view that adapts to protocol configuration
2. Show relevant monitoring for each selection mode (BO, user_selected, predetermined)
3. Make moderator view compatible with the multi-protocol system
4. Render mode-specific views per configuration

## Current State Analysis

### Current Moderator View Structure

**File:** [robotaste/views/moderator.py](robotaste/views/moderator.py)

**Main Function:** `show_moderator_monitoring()` (lines 1776-2293)

**Always Displays:**
- BO visualizations (single_bo or binary_bo)
- Convergence status (4-metric card row)
- Time-series charts (acquisition function, best observed)
- BO configuration summary expander
- Response data table
- Session information
- Export options

**Problem:** No conditional rendering based on:
- Whether BO is enabled
- Current cycle's selection mode
- Protocol configuration

### Selection Modes Available

1. **predetermined** - Pre-specified concentrations
2. **user_selected** - Manual selection via UI
3. **bo_selected** - Bayesian Optimization suggestions

### Data Available Per Mode

#### Predetermined Mode
```python
{
    "mode": "predetermined",
    "concentrations": {"Sugar": 10.0, "Salt": 2.0},
    "metadata": {"is_predetermined": True}
}
```

**Monitorable Metrics:**
- Expected vs actual sample compliance
- Adherence to protocol schedule
- Completion status

#### User Selected Mode
```python
{
    "mode": "user_selected",
    "selection_data": {
        "trajectory_clicks": [...],  # Path taken
        "reaction_time_ms": 6100,    # Time to decide
        "x_position": 200,
        "y_position": 200
    }
}
```

**Monitorable Metrics:**
- Selection heatmap (where users click)
- Average reaction time per cycle
- Exploration coverage (how much of space is explored)
- Click trajectory visualization

#### BO Selected Mode
```python
{
    "mode": "bo_selected",
    "predicted_value": 7.8,
    "uncertainty": 0.5,
    "acquisition_value": 0.0234,
    "acquisition_function": "ei",
    "convergence": {...}
}
```

**Monitorable Metrics:**
- GP preference landscape visualization (current)
- Convergence status (current)
- Acquisition function over cycles (current)
- Best observed rating (current)
- BO override rate
- Prediction accuracy

---

## Design: Dynamic Moderator View System

### Architecture Overview

```
moderator_interface()
    └─ show_moderator_monitoring()
        ├─ Header (constant)
        ├─ Current Cycle Status Card (constant)
        ├─ MODE-SPECIFIC VIEW ROUTER ← NEW
        │   ├─ render_predetermined_mode_view()
        │   ├─ render_user_selected_mode_view()
        │   └─ render_bo_mode_view()
        ├─ Response Data Table (constant)
        ├─ Session Information (constant)
        └─ Export Options (constant)
```

### Key Design Decisions

1. **Mode Detection:** Use `get_selection_mode_for_cycle_runtime(session_id, current_cycle)` to determine what to show
2. **Protocol-Aware:** Check `experiment_config.sample_selection_schedule` for upcoming modes
3. **Tabbed Interface:** Use tabs when protocol has multiple modes
4. **Progressive Disclosure:** Use expanders for less critical information
5. **Reuse Existing Components:** Leverage current BO visualizations, just conditionally

---

## Implementation Plan

### CHANGE 1: Create Mode-Specific View Renderers

**New File:** `robotaste/views/moderator_views.py`

Create specialized rendering functions for each mode:

```python
def render_predetermined_mode_view(
    session_id: str,
    current_cycle: int,
    experiment_config: Dict
) -> None:
    """Render monitoring view for predetermined mode cycles."""

    # 1. Mode Badge
    st.markdown("### 📋 Predetermined Sample Mode")

    # 2. Schedule Overview
    with st.container(border=True):
        st.markdown("**Protocol Schedule:**")
        schedule = experiment_config.get("sample_selection_schedule", [])
        # Show which cycles are predetermined

    # 3. Current Cycle Expected Sample
    expected_sample = get_predetermined_sample(protocol, current_cycle)
    if expected_sample:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Expected Sample (Cycle {current_cycle})")
            for ing, conc in expected_sample.items():
                st.write(f"- {ing}: {conc} mM")
        with col2:
            # Compliance check if sample already collected
            actual_sample = get_sample_for_cycle(session_id, current_cycle)
            if actual_sample:
                # Compare expected vs actual
                pass

    # 4. Adherence Tracking
    with st.expander("Protocol Adherence", expanded=True):
        # Show all predetermined cycles and whether they matched
        adherence_data = []
        for cycle in predetermined_cycles:
            expected = get_predetermined_sample(protocol, cycle)
            actual = get_sample_for_cycle(session_id, cycle)
            adherence = check_sample_match(expected, actual)
            adherence_data.append({
                "cycle": cycle,
                "expected": expected,
                "actual": actual,
                "match": adherence
            })

        # Display as table with match indicators (✓ or ✗)
        st.dataframe(adherence_data)


def render_user_selected_mode_view(
    session_id: str,
    current_cycle: int,
    experiment_config: Dict
) -> None:
    """Render monitoring view for user selection mode cycles."""

    # 1. Mode Badge
    st.markdown("### 🎯 User Selection Mode")

    # 2. Selection Statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_reaction_time = get_avg_reaction_time(session_id, "user_selected")
        st.metric("Avg Reaction Time", f"{avg_reaction_time:.1f}s")

    with col2:
        total_user_cycles = count_cycles_by_mode(session_id, "user_selected")
        st.metric("User Selection Cycles", total_user_cycles)

    with col3:
        coverage = calculate_exploration_coverage(session_id)
        st.metric("Space Coverage", f"{coverage:.0%}")

    with col4:
        avg_clicks = get_avg_trajectory_length(session_id)
        st.metric("Avg Clicks/Cycle", f"{avg_clicks:.1f}")

    # 3. Selection Heatmap
    with st.expander("Selection Heatmap", expanded=True):
        st.markdown("**Where participants are selecting:**")
        # Create heatmap of all user selections
        samples = get_session_samples_by_mode(session_id, "user_selected")

        if num_ingredients == 2:
            # 2D heatmap
            render_selection_heatmap_2d(samples)
        else:
            # 1D histogram
            render_selection_histogram_1d(samples)

    # 4. Reaction Time Trend
    with st.expander("Reaction Time Over Cycles"):
        # Plot reaction time across user-selected cycles
        reaction_times = extract_reaction_times(session_id, "user_selected")
        fig = create_reaction_time_chart(reaction_times)
        st.plotly_chart(fig, use_container_width=True)

    # 5. Trajectory Viewer (if available)
    with st.expander("Latest Selection Trajectory"):
        latest_sample = get_latest_sample(session_id)
        if latest_sample and "trajectory_clicks" in latest_sample.get("selection_data", {}):
            trajectory = latest_sample["selection_data"]["trajectory_clicks"]
            render_trajectory_visualization(trajectory)


def render_bo_mode_view(
    session_id: str,
    current_cycle: int,
    experiment_config: Dict
) -> None:
    """Render monitoring view for BO mode cycles (CURRENT BEHAVIOR)."""

    # 1. Mode Badge
    st.markdown("### 🤖 Bayesian Optimization Mode")

    # 2. BO Visualizations (EXISTING)
    num_ingredients = experiment_config.get("num_ingredients", 2)
    if num_ingredients == 1:
        single_bo()  # Existing function
    elif num_ingredients == 2:
        binary_bo()  # Existing function

    # 3. Convergence Status (EXISTING - lines 1819-1901)
    # Copy existing convergence display code

    # 4. BO Override Statistics (NEW)
    with st.expander("BO Override Statistics"):
        override_rate = calculate_bo_override_rate(session_id)
        total_bo_cycles = count_cycles_by_mode(session_id, "bo_selected")
        total_overrides = count_bo_overrides(session_id)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("BO Cycles", total_bo_cycles)
        with col2:
            st.metric("Overrides", total_overrides)
        with col3:
            st.metric("Override Rate", f"{override_rate:.0%}")

    # 5. Time-Series Charts (EXISTING - lines 1926-2008)
    # Copy existing charts code

    # 6. BO Configuration Summary (EXISTING - lines 2100-2155)
    # Copy existing BO config display
```

**Critical Files to Create:**
1. [robotaste/views/moderator_views.py](robotaste/views/moderator_views.py) - Mode-specific view renderers

---

### CHANGE 2: Create Utility Functions for Mode-Specific Metrics

**New File:** `robotaste/core/moderator_metrics.py`

```python
def get_avg_reaction_time(session_id: str, mode: str = None) -> float:
    """Calculate average reaction time for cycles."""
    samples = get_session_samples(session_id)
    if mode:
        samples = [s for s in samples if s.get("selection_mode") == mode]

    reaction_times = []
    for sample in samples:
        selection_data = sample.get("selection_data", {})
        if "reaction_time_ms" in selection_data:
            reaction_times.append(selection_data["reaction_time_ms"] / 1000)

    return np.mean(reaction_times) if reaction_times else 0.0


def calculate_exploration_coverage(session_id: str) -> float:
    """Calculate what percentage of parameter space has been explored."""
    samples = get_session_samples(session_id)
    session = get_session(session_id)
    ingredients = session["experiment_config"]["ingredients"]

    # Create grid representation of space
    grid_resolution = 20
    grid = np.zeros((grid_resolution, grid_resolution))

    # Mark explored cells
    for sample in samples:
        conc = sample["ingredient_concentration"]
        # Map concentration to grid cell
        # Mark as explored

    explored_cells = np.count_nonzero(grid)
    total_cells = grid_resolution * grid_resolution

    return explored_cells / total_cells


def count_cycles_by_mode(session_id: str, mode: str) -> int:
    """Count how many cycles used a specific selection mode."""
    samples = get_session_samples(session_id)
    return len([s for s in samples if s.get("selection_mode") == mode])


def calculate_bo_override_rate(session_id: str) -> float:
    """Calculate percentage of BO cycles where user overrode the suggestion."""
    samples = get_session_samples(session_id)
    bo_samples = [s for s in samples if s.get("selection_mode") == "bo_selected"]

    if not bo_samples:
        return 0.0

    overridden = len([s for s in bo_samples if s.get("was_bo_overridden")])
    return overridden / len(bo_samples)


def check_sample_match(expected: Dict, actual: Dict, tolerance: float = 0.1) -> bool:
    """Check if actual sample matches expected within tolerance."""
    if not expected or not actual:
        return False

    for ingredient, exp_conc in expected.items():
        act_conc = actual.get(ingredient, 0)
        if abs(exp_conc - act_conc) > tolerance:
            return False

    return True


def get_protocol_schedule_summary(session_id: str) -> Dict:
    """Get summary of protocol's sample selection schedule."""
    session = get_session(session_id)
    experiment_config = session.get("experiment_config", {})
    schedule = experiment_config.get("sample_selection_schedule", [])

    summary = {
        "predetermined_cycles": [],
        "user_selected_cycles": [],
        "bo_selected_cycles": [],
        "total_cycles": 0
    }

    for entry in schedule:
        mode = entry.get("mode")
        cycle_range = entry.get("cycle_range", {})
        start = cycle_range.get("start", 0)
        end = cycle_range.get("end", 0)

        cycles = list(range(start, end + 1))

        if mode == "predetermined":
            summary["predetermined_cycles"].extend(cycles)
        elif mode == "user_selected":
            summary["user_selected_cycles"].extend(cycles)
        elif mode == "bo_selected":
            summary["bo_selected_cycles"].extend(cycles)

    summary["total_cycles"] = len(set(
        summary["predetermined_cycles"] +
        summary["user_selected_cycles"] +
        summary["bo_selected_cycles"]
    ))

    return summary
```

**Critical Files to Create:**
2. [robotaste/core/moderator_metrics.py](robotaste/core/moderator_metrics.py) - Metric calculation utilities

---

### CHANGE 3: Modify Main Moderator Monitoring Function

**File:** [robotaste/views/moderator.py](robotaste/views/moderator.py)

**Function:** `show_moderator_monitoring()` (lines 1776-2293)

**Changes:**

```python
def show_moderator_monitoring():
    """Main monitoring dashboard - now with dynamic mode-aware views."""

    # --- KEEP EXISTING: Header and Setup ---
    st.title("🧪 Monitoring")

    # End session button
    if st.button("End Session", ...):
        # existing code

    # --- KEEP EXISTING: Load session data ---
    session_id = st.session_state.session_id
    session = get_session(session_id)
    experiment_config = session.get("experiment_config", {})
    current_cycle = get_current_cycle(session_id)

    # --- NEW: Determine current and overall modes ---
    from robotaste.core.trials import get_selection_mode_for_cycle_runtime
    from robotaste.core.moderator_metrics import get_protocol_schedule_summary

    current_mode = get_selection_mode_for_cycle_runtime(session_id, current_cycle)
    schedule_summary = get_protocol_schedule_summary(session_id)

    # Determine if protocol uses mixed modes
    modes_used = set()
    if schedule_summary["predetermined_cycles"]:
        modes_used.add("predetermined")
    if schedule_summary["user_selected_cycles"]:
        modes_used.add("user_selected")
    if schedule_summary["bo_selected_cycles"]:
        modes_used.add("bo_selected")

    is_mixed_mode = len(modes_used) > 1

    # --- NEW: Current Cycle Status Card ---
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Current Cycle", current_cycle)

        with col2:
            st.metric("Total Cycles", schedule_summary["total_cycles"])

        with col3:
            mode_emoji = {
                "predetermined": "📋",
                "user_selected": "🎯",
                "bo_selected": "🤖"
            }
            st.metric(
                "Current Mode",
                f"{mode_emoji.get(current_mode, '')} {current_mode.replace('_', ' ').title()}"
            )

        with col4:
            # Best observed value (if available)
            best_value = get_best_observed_value(session_id)
            if best_value:
                st.metric("Best Rating", f"{best_value:.1f}")

    # --- NEW: MODE-SPECIFIC VIEW ROUTING ---

    if is_mixed_mode:
        # Use tabs for mixed-mode protocols
        tab_names = []
        tab_modes = []

        # Add tabs based on what modes are in protocol
        if "predetermined" in modes_used:
            tab_names.append("📋 Predetermined")
            tab_modes.append("predetermined")

        if "user_selected" in modes_used:
            tab_names.append("🎯 User Selection")
            tab_modes.append("user_selected")

        if "bo_selected" in modes_used:
            tab_names.append("🤖 Bayesian Optimization")
            tab_modes.append("bo_selected")

        # Add overview tab
        tab_names.insert(0, "📊 Overview")
        tab_modes.insert(0, "overview")

        tabs = st.tabs(tab_names)

        # Render each tab
        for i, tab in enumerate(tabs):
            with tab:
                mode = tab_modes[i]

                if mode == "overview":
                    render_overview_tab(session_id, schedule_summary, current_cycle)
                elif mode == "predetermined":
                    render_predetermined_mode_view(session_id, current_cycle, experiment_config)
                elif mode == "user_selected":
                    render_user_selected_mode_view(session_id, current_cycle, experiment_config)
                elif mode == "bo_selected":
                    render_bo_mode_view(session_id, current_cycle, experiment_config)

    else:
        # Single mode protocol - render directly without tabs
        if current_mode == "predetermined":
            render_predetermined_mode_view(session_id, current_cycle, experiment_config)
        elif current_mode == "user_selected":
            render_user_selected_mode_view(session_id, current_cycle, experiment_config)
        elif current_mode == "bo_selected":
            render_bo_mode_view(session_id, current_cycle, experiment_config)

    # --- KEEP EXISTING: Response Data Table ---
    with st.expander("📋 Response Data", expanded=False):
        # existing code (lines 2010-2069)

    # --- KEEP EXISTING: Session Information ---
    with st.expander("ℹ️ Session Information", expanded=False):
        # existing code (lines 2071-2097)

    # --- KEEP EXISTING: Export Data ---
    with st.expander("💾 Export Data", expanded=False):
        # existing code (lines 2157-2245)

    # --- KEEP EXISTING: End Session Modal ---
    # existing code (lines 2247-2292)
```

---

### CHANGE 4: Create Overview Tab Renderer

**File:** [robotaste/views/moderator_views.py](robotaste/views/moderator_views.py)

```python
def render_overview_tab(
    session_id: str,
    schedule_summary: Dict,
    current_cycle: int
) -> None:
    """Render overview tab showing progress across all modes."""

    st.markdown("### Experiment Progress Overview")

    # 1. Timeline visualization of protocol schedule
    with st.container(border=True):
        st.markdown("**Protocol Timeline:**")

        # Visual timeline showing which cycles use which mode
        total_cycles = schedule_summary["total_cycles"]

        # Create timeline HTML visualization
        timeline_html = create_protocol_timeline_html(
            schedule_summary,
            current_cycle,
            total_cycles
        )
        st.markdown(timeline_html, unsafe_allow_html=True)

    # 2. Progress by mode
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 📋 Predetermined")
        pred_total = len(schedule_summary["predetermined_cycles"])
        pred_completed = count_completed_cycles(
            session_id,
            schedule_summary["predetermined_cycles"]
        )
        st.progress(pred_completed / pred_total if pred_total > 0 else 0)
        st.write(f"{pred_completed}/{pred_total} completed")

    with col2:
        st.markdown("#### 🎯 User Selection")
        user_total = len(schedule_summary["user_selected_cycles"])
        user_completed = count_completed_cycles(
            session_id,
            schedule_summary["user_selected_cycles"]
        )
        st.progress(user_completed / user_total if user_total > 0 else 0)
        st.write(f"{user_completed}/{user_total} completed")

    with col3:
        st.markdown("#### 🤖 Bayesian Optimization")
        bo_total = len(schedule_summary["bo_selected_cycles"])
        bo_completed = count_completed_cycles(
            session_id,
            schedule_summary["bo_selected_cycles"]
        )
        st.progress(bo_completed / bo_total if bo_total > 0 else 0)
        st.write(f"{bo_completed}/{bo_total} completed")

    # 3. Overall statistics
    st.markdown("### Overall Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_completed = len(get_session_samples(session_id))
        st.metric("Total Samples", total_completed)

    with col2:
        avg_rating = calculate_avg_rating(session_id)
        st.metric("Avg Rating", f"{avg_rating:.1f}")

    with col3:
        best_rating = get_best_observed_value(session_id)
        st.metric("Best Rating", f"{best_rating:.1f}" if best_rating else "N/A")

    with col4:
        session_duration = calculate_session_duration(session_id)
        st.metric("Duration", format_duration(session_duration))

    # 4. Rating over time (all modes combined)
    with st.expander("Rating Over Time", expanded=True):
        samples = get_session_samples(session_id)
        fig = create_rating_over_time_chart(samples)
        st.plotly_chart(fig, use_container_width=True)
```

---

### CHANGE 5: Add Visualization Helper Functions

**File:** [robotaste/utils/visualization_helpers.py](robotaste/utils/visualization_helpers.py) (NEW)

```python
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from typing import List, Dict


def create_protocol_timeline_html(
    schedule_summary: Dict,
    current_cycle: int,
    total_cycles: int
) -> str:
    """Create HTML visualization of protocol timeline."""

    # Build array of mode for each cycle
    mode_per_cycle = [""] * (total_cycles + 1)  # 1-indexed

    for cycle in schedule_summary["predetermined_cycles"]:
        mode_per_cycle[cycle] = "predetermined"
    for cycle in schedule_summary["user_selected_cycles"]:
        mode_per_cycle[cycle] = "user_selected"
    for cycle in schedule_summary["bo_selected_cycles"]:
        mode_per_cycle[cycle] = "bo_selected"

    # Color mapping
    colors = {
        "predetermined": "#8B5CF6",  # Purple
        "user_selected": "#3B82F6",  # Blue
        "bo_selected": "#10B981",    # Green
    }

    # Generate HTML
    html = '<div style="display: flex; gap: 2px; margin: 10px 0;">'

    for cycle in range(1, total_cycles + 1):
        mode = mode_per_cycle[cycle]
        color = colors.get(mode, "#9CA3AF")

        # Highlight current cycle
        border = "3px solid #EF4444" if cycle == current_cycle else "none"

        html += f'''
        <div style="
            flex: 1;
            height: 30px;
            background-color: {color};
            border: {border};
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 10px;
            font-weight: bold;
        " title="Cycle {cycle}: {mode.replace('_', ' ').title()}">
            {cycle}
        </div>
        '''

    html += '</div>'

    # Legend
    html += '<div style="display: flex; gap: 15px; margin-top: 10px; font-size: 12px;">'
    for mode, color in colors.items():
        html += f'''
        <div style="display: flex; align-items: center; gap: 5px;">
            <div style="width: 20px; height: 20px; background-color: {color}; border-radius: 3px;"></div>
            <span>{mode.replace('_', ' ').title()}</span>
        </div>
        '''
    html += '</div>'

    return html


def render_selection_heatmap_2d(samples: List[Dict]) -> None:
    """Render 2D heatmap of user selections."""

    # Extract positions
    x_coords = []
    y_coords = []

    for sample in samples:
        selection_data = sample.get("selection_data", {})
        if "x_position" in selection_data and "y_position" in selection_data:
            x_coords.append(selection_data["x_position"])
            y_coords.append(selection_data["y_position"])

    if not x_coords:
        st.info("No selection data available yet")
        return

    # Create 2D histogram
    fig = go.Figure(go.Histogram2d(
        x=x_coords,
        y=y_coords,
        colorscale='Viridis',
        nbinsx=20,
        nbinsy=20
    ))

    fig.update_layout(
        title="Selection Frequency Heatmap",
        xaxis_title="X Position",
        yaxis_title="Y Position",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)


def create_reaction_time_chart(reaction_times: List[Dict]) -> go.Figure:
    """Create chart showing reaction time trend over cycles."""

    cycles = [rt["cycle"] for rt in reaction_times]
    times = [rt["time_ms"] / 1000 for rt in reaction_times]  # Convert to seconds

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=cycles,
        y=times,
        mode='lines+markers',
        name='Reaction Time',
        line=dict(color='#3B82F6', width=2),
        marker=dict(size=8)
    ))

    # Add average line
    avg_time = np.mean(times)
    fig.add_hline(
        y=avg_time,
        line_dash="dash",
        line_color="#EF4444",
        annotation_text=f"Average: {avg_time:.1f}s"
    )

    fig.update_layout(
        title="Reaction Time Across Cycles",
        xaxis_title="Cycle Number",
        yaxis_title="Reaction Time (seconds)",
        height=400,
        showlegend=True
    )

    return fig


def create_rating_over_time_chart(samples: List[Dict]) -> go.Figure:
    """Create chart showing rating progression over time."""

    cycles = []
    ratings = []
    modes = []

    for sample in samples:
        cycle = sample.get("cycle_number")
        qa = sample.get("questionnaire_answer", {})
        rating = qa.get("rating") or qa.get("overall_liking")
        mode = sample.get("selection_mode", "unknown")

        if rating is not None:
            cycles.append(cycle)
            ratings.append(rating)
            modes.append(mode)

    # Color by mode
    color_map = {
        "predetermined": "#8B5CF6",
        "user_selected": "#3B82F6",
        "bo_selected": "#10B981"
    }
    colors = [color_map.get(m, "#9CA3AF") for m in modes]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=cycles,
        y=ratings,
        mode='lines+markers',
        line=dict(color='#6B7280', width=1),
        marker=dict(size=10, color=colors, line=dict(color='white', width=2)),
        text=[m.replace('_', ' ').title() for m in modes],
        hovertemplate='<b>Cycle %{x}</b><br>Rating: %{y}<br>Mode: %{text}<extra></extra>'
    ))

    fig.update_layout(
        title="Rating Progression Over Cycles",
        xaxis_title="Cycle Number",
        yaxis_title="Rating",
        height=400
    )

    return fig
```

**Critical Files to Create:**
3. [robotaste/utils/visualization_helpers.py](robotaste/utils/visualization_helpers.py) - Visualization functions

---

## Implementation Sequence

### Phase 1: Create New Modules (No Breaking Changes)
1. Create `robotaste/core/moderator_metrics.py` with utility functions
2. Create `robotaste/utils/visualization_helpers.py` with chart functions
3. Create `robotaste/views/moderator_views.py` with mode-specific renderers
4. Add imports to existing files (no functional changes yet)

### Phase 2: Modify Moderator View
5. Update `show_moderator_monitoring()` in `robotaste/views/moderator.py`:
   - Add mode detection logic
   - Add current cycle status card
   - Add mode-specific view routing
   - Keep all existing sections in expanders

### Phase 3: Testing
6. Test with single-mode protocols (predetermined only, user only, BO only)
7. Test with mixed-mode protocols
8. Verify backward compatibility with existing sessions
9. Test tab switching and state persistence

### Phase 4: Polish
10. Add loading states for expensive computations
11. Add error handling for missing data
12. Add tooltips and help text
13. Update documentation

---

## Critical Files to Modify/Create

**New Files:**
1. [robotaste/views/moderator_views.py](robotaste/views/moderator_views.py) - Mode-specific view renderers
2. [robotaste/core/moderator_metrics.py](robotaste/core/moderator_metrics.py) - Metric calculation utilities
3. [robotaste/utils/visualization_helpers.py](robotaste/utils/visualization_helpers.py) - Visualization functions

**Modified Files:**
4. [robotaste/views/moderator.py](robotaste/views/moderator.py) - Lines 1776-2293 (show_moderator_monitoring)

---

## Design Mockup: View Structures

### Single-Mode Protocol (BO Only)
```
┌─────────────────────────────────────────┐
│ 🧪 Monitoring              [End Session]│
├─────────────────────────────────────────┤
│ Current Cycle: 6  │  Total: 50          │
│ Current Mode: 🤖 BO│  Best Rating: 8.1   │
├─────────────────────────────────────────┤
│                                          │
│ ### 🤖 Bayesian Optimization Mode       │
│                                          │
│ [BO Preference Landscape Visualization] │
│                                          │
│ ▸ Convergence Status                    │
│ ▸ BO Override Statistics                │
│ ▸ Time-Series Charts                    │
│ ▸ BO Configuration Summary              │
│                                          │
├─────────────────────────────────────────┤
│ ▸ Response Data                         │
│ ▸ Session Information                   │
│ ▸ Export Data                           │
└─────────────────────────────────────────┘
```

### Mixed-Mode Protocol
```
┌─────────────────────────────────────────┐
│ 🧪 Monitoring              [End Session]│
├─────────────────────────────────────────┤
│ Current Cycle: 8  │  Total: 20          │
│ Current Mode: 🤖 BO│  Best Rating: 7.8   │
├─────────────────────────────────────────┤
│ ┌───────────────────────────────────┐  │
│ │ 📊 Overview │ 📋 Predetermined │...│  │
│ └───────────────────────────────────┘  │
│                                          │
│ ### Experiment Progress Overview        │
│                                          │
│ Protocol Timeline:                      │
│ [1][2][3][4][5][6][7][8][9]...[20]     │
│  │  │  │  │  │  │  │  │               │
│  └──┴──┘ Predetermined                  │
│        └──────┘ User Selection          │
│                 └──────────┘ BO         │
│                                          │
│ Progress by Mode:                       │
│ ┌──────────┬──────────┬──────────┐     │
│ │📋 Pred   │🎯 User   │🤖 BO     │     │
│ │██░░ 2/3 │████░ 4/5 │█░░░ 2/12 │     │
│ └──────────┴──────────┴──────────┘     │
│                                          │
│ ▸ Overall Statistics                    │
│ ▸ Rating Over Time                      │
│                                          │
├─────────────────────────────────────────┤
│ ▸ Response Data                         │
│ ▸ Session Information                   │
│ ▸ Export Data                           │
└─────────────────────────────────────────┘
```

---

---

## Benefits

1. **Relevant Information:** Moderators only see what's relevant for current protocol
2. **Better Monitoring:** Mode-specific metrics provide actionable insights
3. **Scalability:** Easy to add new selection modes in future
4. **Protocol Awareness:** Fully integrated with multi-protocol system
5. **Progressive Disclosure:** Important info upfront, details in expanders/tabs
6. **Reusable Components:** Leverages existing BO visualizations

---

## Future Enhancements

1. **Real-time Updates:** Auto-refresh data during active session
2. **Comparison View:** Compare multiple sessions side-by-side
3. **Export Presets:** Mode-specific export templates
4. **Alerts:** Notify moderator of important events (convergence reached, etc.)
5. **Custom Dashboards:** Let moderators configure their preferred view layout
