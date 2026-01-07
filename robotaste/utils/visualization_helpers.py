"""
Visualization Helpers for RoboTaste Moderator Views

Reusable chart creation functions following the project's Plotly patterns.

Author: RoboTaste Team
Version: 1.0
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Project color scheme constants
COLOR_PURPLE = "#A855F7"  # Predictions
COLOR_TEAL = "#14B8A6"    # Acquisition/exploration
COLOR_GREEN = "#10B981"   # Success/observed
COLOR_ORANGE = "#F59E0B"  # Warning
COLOR_RED = "#F87171"     # Error/threshold
COLOR_GRAY = "#6B7280"    # Neutral

# Font sizes
FONT_SIZE_BODY = 18
FONT_SIZE_TITLE = 21

# Chart layout defaults
DEFAULT_CHART_HEIGHT = 300
DEFAULT_MARGIN = dict(l=50, r=50, t=80, b=50)


def create_empty_state_message(message: str, height: int = DEFAULT_CHART_HEIGHT) -> go.Figure:
    """
    Create a placeholder figure with informational message.

    Args:
        message: Text to display
        height: Figure height in pixels

    Returns:
        Plotly figure with centered message
    """
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=FONT_SIZE_BODY, color=COLOR_GRAY)
    )
    fig.update_layout(
        height=height,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=DEFAULT_MARGIN
    )
    return fig


def create_timeline_chart(
    cycles: List[int],
    values: List[float],
    title: str,
    y_label: str,
    color: str = COLOR_GREEN,
    threshold: Optional[float] = None,
    threshold_label: Optional[str] = None
) -> go.Figure:
    """
    Create a time-series line chart with optional threshold.

    Args:
        cycles: List of cycle numbers
        values: List of values corresponding to cycles
        title: Chart title
        y_label: Y-axis label
        color: Line color (hex)
        threshold: Optional horizontal threshold line
        threshold_label: Label for threshold

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    # Main line
    fig.add_trace(go.Scatter(
        x=cycles,
        y=values,
        mode="lines+markers",
        name=y_label,
        line=dict(color=color, width=2),
        marker=dict(size=8)
    ))

    # Threshold line
    if threshold is not None:
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color=COLOR_RED,
            annotation_text=threshold_label or "Threshold"
        )

    fig.update_layout(
        title=title,
        title_font=dict(size=FONT_SIZE_TITLE),
        xaxis_title="Cycle",
        yaxis_title=y_label,
        xaxis=dict(title_font=dict(size=FONT_SIZE_TITLE), tickfont=dict(size=FONT_SIZE_BODY)),
        yaxis=dict(title_font=dict(size=FONT_SIZE_TITLE), tickfont=dict(size=FONT_SIZE_BODY)),
        font=dict(size=FONT_SIZE_BODY),
        height=DEFAULT_CHART_HEIGHT,
        margin=DEFAULT_MARGIN
    )

    return fig


def create_scatter_plot(
    x_values: List[float],
    y_values: List[float],
    title: str,
    x_label: str,
    y_label: str,
    cycle_labels: Optional[List[int]] = None,
    color_values: Optional[List[float]] = None,
    colorbar_title: Optional[str] = None
) -> go.Figure:
    """
    Create a scatter plot with optional color mapping.

    Args:
        x_values: X coordinates
        y_values: Y coordinates
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        cycle_labels: Optional cycle numbers for hover text
        color_values: Optional values for color mapping
        colorbar_title: Title for colorbar

    Returns:
        Plotly figure
    """
    hover_text = None
    if cycle_labels:
        hover_text = [f"Cycle {c}<br>{x_label}: {x:.2f}<br>{y_label}: {y:.2f}"
                      for c, x, y in zip(cycle_labels, x_values, y_values)]

    marker_config = dict(size=10)
    if color_values:
        marker_config.update({
            "color": color_values,
            "colorscale": "Viridis",
            "showscale": True,
            "colorbar": dict(title=colorbar_title or "Value")
        })
    else:
        marker_config["color"] = COLOR_TEAL

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="markers",
        marker=marker_config,
        hovertext=hover_text,
        hoverinfo="text" if hover_text else "x+y"
    ))

    fig.update_layout(
        title=title,
        title_font=dict(size=FONT_SIZE_TITLE),
        xaxis_title=x_label,
        yaxis_title=y_label,
        xaxis=dict(title_font=dict(size=FONT_SIZE_TITLE), tickfont=dict(size=FONT_SIZE_BODY)),
        yaxis=dict(title_font=dict(size=FONT_SIZE_TITLE), tickfont=dict(size=FONT_SIZE_BODY)),
        font=dict(size=FONT_SIZE_BODY),
        height=DEFAULT_CHART_HEIGHT,
        margin=DEFAULT_MARGIN
    )

    return fig


def create_bar_chart(
    categories: List[str],
    values: List[float],
    title: str,
    y_label: str,
    color: str = COLOR_TEAL
) -> go.Figure:
    """
    Create a simple bar chart.

    Args:
        categories: X-axis categories
        values: Bar heights
        title: Chart title
        y_label: Y-axis label
        color: Bar color

    Returns:
        Plotly figure
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=categories,
        y=values,
        marker_color=color
    ))

    fig.update_layout(
        title=title,
        title_font=dict(size=FONT_SIZE_TITLE),
        yaxis_title=y_label,
        xaxis=dict(tickfont=dict(size=FONT_SIZE_BODY)),
        yaxis=dict(title_font=dict(size=FONT_SIZE_TITLE), tickfont=dict(size=FONT_SIZE_BODY)),
        font=dict(size=FONT_SIZE_BODY),
        height=DEFAULT_CHART_HEIGHT,
        margin=DEFAULT_MARGIN
    )

    return fig


def create_protocol_schedule_gantt(
    sample_selection_schedule: List[Dict[str, Any]]
) -> go.Figure:
    """
    Create a Gantt-style visualization of protocol schedule.

    Args:
        sample_selection_schedule: List of schedule entries from protocol

    Returns:
        Plotly figure showing mode blocks
    """
    # Color mapping for modes
    mode_colors = {
        "predetermined": COLOR_PURPLE,
        "user_selected": COLOR_TEAL,
        "bo_selected": COLOR_GREEN
    }

    fig = go.Figure()

    for entry in sample_selection_schedule:
        cycle_range = entry.get("cycle_range", {})
        mode = entry.get("mode", "user_selected")
        start = cycle_range.get("start", 0)
        end = cycle_range.get("end", 0)

        fig.add_trace(go.Bar(
            x=[end - start + 1],
            y=[mode],
            orientation='h',
            base=[start - 1],
            marker_color=mode_colors.get(mode, COLOR_GRAY),
            name=mode.replace("_", " ").title(),
            hovertext=f"Cycles {start}-{end}",
            hoverinfo="text"
        ))

    fig.update_layout(
        title="Protocol Schedule",
        title_font=dict(size=FONT_SIZE_TITLE),
        xaxis_title="Cycle Number",
        xaxis=dict(title_font=dict(size=FONT_SIZE_TITLE), tickfont=dict(size=FONT_SIZE_BODY)),
        yaxis=dict(tickfont=dict(size=FONT_SIZE_BODY)),
        font=dict(size=FONT_SIZE_BODY),
        height=200,
        showlegend=True,
        barmode='stack',
        margin=DEFAULT_MARGIN
    )

    return fig
