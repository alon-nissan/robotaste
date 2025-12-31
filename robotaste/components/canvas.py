"""
RoboTaste Canvas Component - Interactive Grid Drawing

Provides canvas rendering utilities for 2D grid experiments.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
from typing import Dict, Any, List, Tuple


# Constants
CANVAS_SIZE = 500  # Default fallback size
GRID_STEP = 50


def get_canvas_size() -> int:
    """
    Get responsive canvas size based on viewport.

    Returns:
        Canvas size in pixels
    """
    try:
        from robotaste.utils.viewport import get_responsive_canvas_size
        return get_responsive_canvas_size()
    except Exception:
        # Fallback to default if viewport utils not available
        return CANVAS_SIZE


def create_canvas_drawing(
    x: float,
    y: float,
    selection_history: List[Dict] = None,
) -> Dict[str, Any]:
    """
    Create initial canvas drawing with grid, starting dot, and selection history.

    Args:
        x, y: Initial dot position
        selection_history: List of previous selections with order tracking

    Returns:
        Fabric.js compatible drawing object
    """
    if selection_history is None:
        selection_history = []

    canvas_size = get_canvas_size()
    objects = []

    # Add grid lines
    for i in range(0, canvas_size + 1, GRID_STEP):
        # Vertical lines
        objects.append(
            {
                "type": "line",
                "x1": i,
                "y1": 0,
                "x2": i,
                "y2": canvas_size,
                "stroke": "#E5E7EB",
                "strokeWidth": 1,
                "selectable": False,
                "evented": False,
            }
        )

        # Horizontal lines
        objects.append(
            {
                "type": "line",
                "x1": 0,
                "y1": i,
                "x2": canvas_size,
                "y2": i,
                "stroke": "#E5E7EB",
                "strokeWidth": 1,
                "selectable": False,
                "evented": False,
            }
        )

    # Add initial starting position as gray dot
    objects.append(
        {
            "type": "circle",
            "left": x,
            "top": y,
            "radius": 8,
            "fill": "#9CA3AF",  # Gray for starting position
            "stroke": "#6B7280",
            "strokeWidth": 2,
            "originX": "center",
            "originY": "center",
        }
    )

    # Add selection history with visual progression and numbering
    if selection_history:
        for i, selection in enumerate(selection_history):
            # Determine color based on selection type (BO vs manual)
            is_bo = selection.get("is_bo_suggestion", False)
            fill_color = "#8B5CF6" if is_bo else "#14B8A6"  # Purple for BO, teal for manual
            stroke_color = "#6D28D9" if is_bo else "#0D9488"  # Darker purple/teal for stroke

            # Add selection circle
            objects.append(
                {
                    "type": "circle",
                    "left": selection["x"],
                    "top": selection["y"],
                    "radius": 10,  # Slightly larger than starting position
                    "fill": fill_color,
                    "stroke": stroke_color,
                    "strokeWidth": 3,
                    "originX": "center",
                    "originY": "center",
                }
            )

            # Add selection order number as text
            objects.append(
                {
                    "type": "text",
                    "left": selection["x"],
                    "top": selection["y"],
                    "text": str(selection.get("order", i + 1)),
                    "fontSize": 18,
                    "fontWeight": "bold",
                    "fontFamily": "Arial",
                    "fill": "white",
                    "originX": "center",
                    "originY": "center",
                    "selectable": False,
                    "evented": False,
                }
            )

    return {"version": "4.4.0", "objects": objects}


def clear_canvas_state():
    """Clear all canvas-related keys from session state."""
    keys_to_remove = []
    for key in st.session_state.keys():
        if key.startswith("canvas_"):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]
