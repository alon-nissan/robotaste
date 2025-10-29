"""
RoboTaste Callback Functions - Experimental Logic & Data Processing

OVERVIEW:
=========
Core business logic for taste preference experiments. Handles concentration mapping,
multi-component mixture calculations, questionnaire rendering, and data persistence.

KEY COMPONENTS:
==============
1. CONCENTRATION MAPPING:
   - ConcentrationMapper: Converts 2D coordinates to sugar/salt concentrations
   - Supports linear, logarithmic, and exponential mapping methods
   - Literature-based concentration ranges (Breslin paper)

2. MULTI-COMPONENT SYSTEM:
   - MultiComponentMixture: Handles 2-6 ingredient mixtures
   - Independent slider-based concentration control
   - Real mM calculations hidden from subjects

3. CANVAS MANAGEMENT:
   - Dynamic canvas creation with grid overlays
   - Persistent selection history visualization
   - Support for both 2D grid and slider interfaces

4. QUESTIONNAIRE SYSTEM:
   - Configurable questionnaire components
   - Unified feedback collection for research
   - Post-selection data collection workflow

5. DATA PERSISTENCE:
   - Trial management (start/finish)
   - Response tracking with reaction times
   - Multi-format data storage (coordinates + concentrations + JSON)

CONCENTRATION CALCULATIONS:
==========================
• Sugar (Sucrose): 0.73 - 73.0 mM (MW: 342.3 g/mol)
• Salt (NaCl): 0.10 - 10.0 mM (MW: 58.44 g/mol)
• Citric Acid: 0.1 - 5.0 mM (MW: 192.12 g/mol)
• Caffeine: 0.01 - 1.0 mM (MW: 194.19 g/mol)
• Vanilla: 0.001 - 0.1 mM (MW: 152.15 g/mol)
• Menthol: 0.001 - 0.5 mM (MW: 156.27 g/mol)

MATHEMATICAL MODELS:
===================
Linear: conc = min + (coord/max_coord) * (max - min)
Logarithmic: conc = min * ((max/min)^(coord/max_coord))
Exponential: conc = min + (max-min) * (e^(k*coord/max_coord) - 1) / (e^k - 1)

TODO PRIORITIES:
===============
HIGH:
- [ ] Add concentration safety validation
- [ ] Implement ingredient interaction warnings
- [ ] Add solution stability calculations
- [ ] Create automated calibration system

MEDIUM:
- [ ] Add custom ingredient support
- [ ] Implement batch processing
- [ ] Add temperature-dependent calculations
- [ ] Create pH adjustment recommendations

LOW:
- [ ] Add molecular interaction modeling
- [ ] Implement flavor prediction algorithms
- [ ] Add sensory threshold calculations

Author: Masters Research Project
Version: 2.0 - Multi-Component Support
Last Updated: 2025
"""

import streamlit as st
import random
import time
import math
import streamlit_vertical_slider as svs
from datetime import datetime
from typing import Tuple, Dict, Any, Optional
from sql_handler import update_session_state, save_response
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
CANVAS_SIZE = 500
GRID_STEP = 50
NACL_MW = 58.44  # g/mol

# Multi-component mixture configuration
# TODO: Move to configuration file for easier customization
# TODO: Add ingredient compatibility matrix
# TODO: Add safety limits and allergen warnings
DEFAULT_INGREDIENT_CONFIG = [
    {
        "name": "Sugar",
        "min_concentration": 0.73,
        "max_concentration": 73.0,
        "molecular_weight": 342.3,
        "unit": "mM",
        "stock_concentration_mM": 1000.0,  # Stock solution concentration - CHANGE THIS AS NEEDED
    },
    {
        "name": "Salt",
        "min_concentration": 0.10,
        "max_concentration": 10.0,
        "molecular_weight": 58.44,
        "unit": "mM",
        "stock_concentration_mM": 1000.0,  # Stock solution concentration - CHANGE THIS AS NEEDED
    },
    {
        "name": "Citric Acid",
        "min_concentration": 0.1,
        "max_concentration": 5.0,
        "molecular_weight": 192.12,
        "unit": "mM",
        "stock_concentration_mM": 1000.0,  # Stock solution concentration - CHANGE THIS AS NEEDED
    },
    {
        "name": "Caffeine",
        "min_concentration": 0.01,
        "max_concentration": 1.0,
        "molecular_weight": 194.19,
        "unit": "mM",
        "stock_concentration_mM": 1000.0,  # Stock solution concentration - CHANGE THIS AS NEEDED
    },
    {
        "name": "Vanilla",
        "min_concentration": 0.001,
        "max_concentration": 0.1,
        "molecular_weight": 152.15,
        "unit": "mM",
        "stock_concentration_mM": 1000.0,  # Stock solution concentration - CHANGE THIS AS NEEDED
    },
    {
        "name": "Menthol",
        "min_concentration": 0.001,
        "max_concentration": 0.5,
        "molecular_weight": 156.27,
        "unit": "mM",
        "stock_concentration_mM": 1000.0,  # Stock solution concentration - CHANGE THIS AS NEEDED
    },
]

# Interface type constants
INTERFACE_2D_GRID = "2d_grid"
INTERFACE_SLIDERS = "sliders"
SUCROSE_MW = 342.3  # g/mol

# Concentration ranges from literature
SUGAR_RANGE_MM = (0.73, 73.0)  # mM from Breslin paper
SALT_RANGE_MM = (0.10, 10.0)  # mM approximation

# Canvas bounds for random positioning
POSITION_BOUNDS = (GRID_STEP, CANVAS_SIZE - GRID_STEP)


class ConcentrationMapper:
    """Handles mapping between canvas coordinates and concentrations.

    TODO: Add concentration safety limits and validation
    TODO: Implement non-linear interpolation methods
    TODO: Add unit conversion support (mM, mg/mL, etc.)
    TODO: Add ingredient interaction compatibility checks
    """

    @staticmethod
    def map_coordinates_to_concentrations(
        x: float,
        y: float,
        method: str = "linear",
        canvas_size: int = CANVAS_SIZE,
        sugar_range: Tuple[float, float] = SUGAR_RANGE_MM,
        salt_range: Tuple[float, float] = SALT_RANGE_MM,
    ) -> Tuple[float, float]:
        """
        Convert canvas coordinates to sugar & salt concentrations.

        Args:
            x, y: Canvas coordinates (0 to canvas_size)
            method: Mapping method ('linear', 'logarithmic', 'exponential')
            canvas_size: Size of the canvas
            sugar_range: (min, max) sugar concentration in mM
            salt_range: (min, max) salt concentration in mM

        Returns:
            (sugar_concentration, salt_concentration) in mM

        Note:
            Y-axis is flipped so that minimum is at bottom (canvas y=canvas_size)
            and maximum is at top (canvas y=0), creating a standard coordinate system
            where bottom-left = (min, min) and top-right = (max, max)
        """
        # Normalize coordinates to [0, 1]
        x_norm = max(0.0, min(1.0, x / canvas_size))
        # Flip y-axis: canvas y=0 (top) should map to max, canvas y=canvas_size (bottom) to min
        y_norm = max(0.0, min(1.0, (canvas_size - y) / canvas_size))

        if method == "linear":
            sugar = sugar_range[0] + x_norm * (sugar_range[1] - sugar_range[0])
            salt = salt_range[0] + y_norm * (salt_range[1] - salt_range[0])

        elif method == "logarithmic":
            # Logarithmic scaling
            if sugar_range[0] <= 0 or salt_range[0] <= 0:
                raise ValueError(
                    "Logarithmic mapping requires positive concentration ranges"
                )

            log_sugar_range = (math.log(sugar_range[0]), math.log(sugar_range[1]))
            log_salt_range = (math.log(salt_range[0]), math.log(salt_range[1]))

            sugar = math.exp(
                log_sugar_range[0] + x_norm * (log_sugar_range[1] - log_sugar_range[0])
            )
            salt = math.exp(
                log_salt_range[0] + y_norm * (log_salt_range[1] - log_salt_range[0])
            )

        elif method == "exponential":
            # Exponential scaling (inverse of logarithmic)
            sugar = sugar_range[1] * ((sugar_range[0] / sugar_range[1]) ** (1 - x_norm))
            salt = salt_range[1] * ((salt_range[0] / salt_range[1]) ** (1 - y_norm))

        else:
            raise ValueError(f"Unknown mapping method: {method}")

        return round(sugar, 3), round(salt, 3)

    @staticmethod
    def concentrations_to_masses(
        sugar_mm: float, salt_mm: float, volume_ml: float = 100.0
    ) -> Tuple[float, float]:
        """Convert concentrations to masses for solution preparation."""
        # Convert mM to g for given volume
        sugar_mass = (sugar_mm / 1000.0) * SUCROSE_MW * (volume_ml / 1000.0)
        salt_mass = (salt_mm / 1000.0) * NACL_MW * (volume_ml / 1000.0)

        return round(sugar_mass, 4), round(salt_mass, 4)


def generate_random_position(
    x_range: Tuple[float, float] = POSITION_BOUNDS,
    y_range: Tuple[float, float] = POSITION_BOUNDS,
) -> Tuple[float, float]:
    """Generate random coordinates within canvas bounds.

    TODO: Add deterministic seed support for reproducible experiments
    TODO: Implement strategic positioning algorithms
    """
    x = random.uniform(x_range[0], x_range[1])
    y = random.uniform(y_range[0], y_range[1])
    return round(x, 1), round(y, 1)


def create_canvas_drawing(
    x: float, y: float, selection_history: list = None
) -> Dict[str, Any]:
    """
    Create initial canvas drawing with grid, starting dot, and selection history.

    Args:
        x, y: Initial dot position
        selection_history: List of previous selections with order tracking

    Returns:
        Fabric.js compatible drawing object
    """
    objects = []

    # Add grid lines
    for i in range(0, CANVAS_SIZE + 1, GRID_STEP):
        # Vertical lines
        objects.append(
            {
                "type": "line",
                "x1": i,
                "y1": 0,
                "x2": i,
                "y2": CANVAS_SIZE,
                "stroke": "#03060DAB",
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
                "x2": CANVAS_SIZE,
                "y2": i,
                "stroke": "#03060DAB",
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
            "fill": "#9CA3AF",  # Gray color for starting position
            "stroke": "#6B7280",
            "strokeWidth": 2,
            "originX": "center",
            "originY": "center",
        }
    )

    # Add selection history with visual progression and numbering
    if selection_history:
        for i, selection in enumerate(selection_history):
            # Color progression - darker red for more recent selections
            opacity = (
                0.4 + (i * 0.6 / max(len(selection_history) - 1, 1))
                if len(selection_history) > 1
                else 1.0
            )

            # Add selection circle
            objects.append(
                {
                    "type": "circle",
                    "left": selection["x"],
                    "top": selection["y"],
                    "radius": 10,  # Slightly larger than starting position
                    "fill": "#EF4444",
                    "stroke": "#DC2626",
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
                    "text": str(selection["order"]),
                    "fontSize": 12,
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


class MultiComponentMixture:
    """
    Handle multi-component mixture configurations and calculations.

    Manages complex mixture systems with 2-6 ingredients, providing concentration
    calculations, solution preparation data, and interface type determination.

    TODO: Add ingredient interaction validation
    TODO: Implement temperature compensation
    TODO: Add pH calculation support
    TODO: Create mixture stability warnings
    """

    def __init__(self, ingredients_config: list):
        """
        Initialize with ingredient configuration.

        Args:
            ingredients_config: List of ingredient dictionaries with name,
                              min_concentration, max_concentration, molecular_weight

        TODO: Validate ingredient configuration
        TODO: Check for incompatible ingredient combinations
        TODO: Add concentration range validation
        """
        self.ingredients = ingredients_config
        self.num_ingredients = len(ingredients_config)

        # TODO: Add ingredient validation
        # TODO: Check for duplicate ingredients
        # TODO: Validate concentration ranges

    def get_interface_type(self) -> str:
        """Determine interface type based on number of ingredients."""
        return INTERFACE_2D_GRID if self.num_ingredients == 2 else INTERFACE_SLIDERS

    def calculate_concentrations_from_sliders(self, slider_values: dict) -> dict:
        """
        Calculate actual concentrations from slider positions (0-100).

        Args:
            slider_values: Dict with ingredient names as keys, slider positions (0-100) as values

        Returns:
            Dict with actual concentrations in mM and display values
        """
        concentrations = {}

        for ingredient in self.ingredients:
            name = ingredient["name"]
            if name in slider_values:
                slider_pos = slider_values[name]  # 0-100
                min_conc = ingredient["min_concentration"]
                max_conc = ingredient["max_concentration"]

                # Linear mapping from slider position to concentration
                actual_concentration = min_conc + (slider_pos / 100.0) * (
                    max_conc - min_conc
                )

                concentrations[name] = {
                    "slider_position": slider_pos,
                    "actual_concentration_mM": actual_concentration,
                    "display_value": f"{slider_pos:.1f}%",  # What subject sees
                    "min_mM": min_conc,
                    "max_mM": max_conc,
                    "molecular_weight": ingredient["molecular_weight"],
                }

        return concentrations

    def get_default_slider_values(self) -> dict:
        """Get default slider positions for initialization."""
        default_values = {}
        for ingredient in self.ingredients:
            # Start at middle of range
            default_values[ingredient["name"]] = 50.0
        return default_values

    def calculate_solution_mass(
        self, concentrations: dict, volume_ml: float = 100.0
    ) -> dict:
        """
        Calculate mass of each ingredient needed for solution preparation.

        Args:
            concentrations: Output from calculate_concentrations_from_sliders
            volume_ml: Solution volume in mL

        Returns:
            Dict with mass calculations for each ingredient
        """
        masses = {}

        for ingredient_name, conc_data in concentrations.items():
            conc_mM = conc_data["actual_concentration_mM"]
            mw = conc_data["molecular_weight"]

            # Convert mM to g/L: mM * MW(g/mol) / 1000
            conc_g_per_L = conc_mM * mw / 1000.0

            # Calculate mass needed for given volume
            mass_g = conc_g_per_L * (volume_ml / 1000.0)

            masses[ingredient_name] = {
                "concentration_mM": conc_mM,
                "concentration_g_per_L": conc_g_per_L,
                "mass_g_per_100ml": mass_g,
                "molecular_weight": mw,
            }

        return masses


def calculate_stock_volumes(
    concentrations: dict, ingredient_configs: list, final_volume_mL: float = 10.0
) -> dict:
    """
    Calculate volume of each stock solution needed for preparation.

    Args:
        concentrations: Dict of {ingredient_name: desired_mM}
        ingredient_configs: List of ingredient config dicts with stock_concentration_mM
        final_volume_mL: Final solution volume in mL (default 10.0 mL)

    Returns:
        Dict with:
        {
            "stock_volumes": {ingredient_name: volume_µL, ...},
            "water_volume": µL of water to add,
            "total_volume": final volume in mL,
            "ingredient_configs": reference to configs used
        }

    Formula:
        volume_stock_mL = (desired_mM × final_volume_mL) / stock_mM
        volume_stock_µL = volume_stock_mL × 1000

    Example:
        If you want 12.5 mM Sugar in 10 mL final volume, with 1000 mM stock:
        volume_stock = (12.5 × 10.0) / 1000 = 0.125 mL = 125 µL
    """
    stock_volumes = {}
    total_stock_volume = 0.0

    for ingredient_name, desired_mM in concentrations.items():
        # Find ingredient config
        config = next(
            (ing for ing in ingredient_configs if ing["name"] == ingredient_name), None
        )

        if config and "stock_concentration_mM" in config:
            stock_mM = config["stock_concentration_mM"]

            # Calculate volume of stock solution needed
            # Formula: C1*V1 = C2*V2 → V1 = (C2*V2)/C1
            volume_stock_mL = (desired_mM * final_volume_mL) / stock_mM
            volume_stock_µL = volume_stock_mL * 1000  # Convert to microliters

            stock_volumes[ingredient_name] = round(
                volume_stock_µL, 3
            )  # Round to 3 decimal in µL
            total_stock_volume += volume_stock_mL

    # Calculate water volume needed to reach final volume
    water_volume_mL = final_volume_mL - total_stock_volume
    water_volume_µL = water_volume_mL * 1000  # Convert to microliters

    return {
        "stock_volumes": stock_volumes,
        "water_volume": round(water_volume_µL, 1),
        "total_volume": final_volume_mL,
        "ingredient_configs": ingredient_configs,  # Include for reference
    }


def create_ingredient_sliders(
    ingredients_config: list, participant_id: str, current_values: dict = None
) -> dict:
    """
    Create independent concentration sliders for multi-component interface.

    Args:
        ingredients_config: List of ingredient configurations
        participant_id: Participant identifier
        current_values: Current slider values (if any)

    Returns:
        Dict with slider values or None if not submitted
    """
    if current_values is None:
        current_values = {}

    st.markdown("### Adjust Ingredient Concentrations")
    st.info(
        "Move each slider to adjust the concentration of each ingredient. The position on each slider determines the mixture composition."
    )

    # Create form for all sliders
    with st.form(key=f"ingredient_sliders_{participant_id}"):
        slider_values = {}

        # Create columns for sliders (max 3 per row)
        num_cols = min(3, len(ingredients_config))
        cols = st.columns(num_cols)

        for i, ingredient in enumerate(ingredients_config):
            col_idx = i % num_cols
            ingredient_name = ingredient["name"]

            with cols[col_idx]:
                # Create slider with generic label (hide that it's concentration)
                slider_key = f"slider_{ingredient_name}_{participant_id}"
                # Use random starting position if available, otherwise default to 50.0
                random_values = st.session_state.get("random_slider_values", {})
                if ingredient_name in random_values:
                    default_value = random_values[ingredient_name]
                else:
                    default_value = current_values.get(ingredient_name, 50.0)

                st.markdown(f"**Ingredient {chr(65 + i)}**")
                slider_values[ingredient_name] = svs.vertical_slider(
                    key=slider_key,
                    default_value=default_value,
                    step=1.0,
                    min_value=0.0,
                    max_value=100.0,
                    slider_color="#3b82f6",  # Blue color matching the theme
                    track_color="#e2e8f0",  # Light gray track
                    thumb_color="#1e40af",  # Darker blue thumb
                )

                # Show position as percentage (what subject sees)
                st.caption(f"Position: {slider_values[ingredient_name]:.1f}%")

        # Submit button (this will be moved to questionnaire later)
        submitted = st.form_submit_button(
            "Update Mixture",
            type="primary",
            use_container_width=True,
            key=f"update_mixture_{participant_id}",
        )

        if submitted:
            return slider_values

    return None


def start_trial(
    user_type: str,
    participant_id: str,
    method: str,
    num_ingredients: int = 2,
    selected_ingredients: Optional[list] = None,
    ingredient_configs: Optional[list] = None,
) -> bool:
    """
    Initialize a new trial with random starting position using new database schema.

    Args:
        user_type: 'mod' or 'sub'
        participant_id: Unique participant identifier
        method: Concentration mapping method
        num_ingredients: Number of ingredients
        selected_ingredients: List of selected ingredient names (e.g., ['Sugar', 'Salt', 'Citric Acid'])
        ingredient_configs: List of ingredient configuration dicts with custom ranges

    Returns:
        Success status
    """
    try:
        from sql_handler import update_session_state, store_initial_slider_positions

        # Generate random starting position for grid interface
        x, y = generate_random_position()

        # Determine interface type
        interface_type = (
            INTERFACE_2D_GRID if num_ingredients == 2 else INTERFACE_SLIDERS
        )

        # Get session code - create one if missing
        session_code = st.session_state.get("session_code")
        if not session_code:
            session_code = f"session_{int(time.time())}"
            st.session_state.session_code = session_code
            st.warning(f"Created new session code: {session_code}")
        use_random_start = st.session_state.get("use_random_start", False)

        # Get ingredient configuration - FIXED: Use moderator's actual ingredient selection
        if ingredient_configs:
            # Use moderator's custom configuration with custom concentration ranges
            ingredients = ingredient_configs
            logger.info(
                f"Using custom ingredient configuration: {[ing['name'] for ing in ingredients]}"
            )
        elif selected_ingredients:
            # Build configuration from selected ingredient names
            ingredients = [
                ing
                for ing in DEFAULT_INGREDIENT_CONFIG
                if ing["name"] in selected_ingredients
            ]
            logger.info(
                f"Using selected ingredients: {[ing['name'] for ing in ingredients]}"
            )
        else:
            # Fallback to defaults (for backward compatibility with old code)
            ingredients = DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
            logger.warning(
                f"Using default ingredient configuration (first {num_ingredients} ingredients)"
            )

        # Validate we have the correct number of ingredients
        if len(ingredients) != num_ingredients:
            logger.error(
                f"Ingredient count mismatch: expected {num_ingredients}, got {len(ingredients)}"
            )
            st.error(
                f"Configuration error: Expected {num_ingredients} ingredients, got {len(ingredients)}"
            )

        # Generate random starting positions for sliders if enabled and using slider interface
        random_slider_values = {}
        random_concentrations = {}
        if use_random_start and interface_type == INTERFACE_SLIDERS:
            # Generate random starting positions for each ingredient (10-90%)
            mixture = MultiComponentMixture(ingredients)
            for ingredient in ingredients:
                random_percent = random.uniform(10.0, 90.0)
                random_slider_values[ingredient["name"]] = random_percent

            # Calculate actual concentrations from percentages
            concentrations = mixture.calculate_concentrations_from_sliders(
                random_slider_values
            )
            for ingredient_name, conc_data in concentrations.items():
                random_concentrations[ingredient_name] = round(
                    conc_data["actual_concentration_mM"], 3
                )

            # Store initial slider positions in database
            ingredient_names = [ing["name"] for ing in ingredients]
            store_initial_slider_positions(
                session_id=session_code,
                participant_id=participant_id,
                num_ingredients=num_ingredients,
                initial_percentages=random_slider_values,
                initial_concentrations=random_concentrations,
                ingredient_names=ingredient_names,
            )

        # Register initial random positions as first response
        try:
            from sql_handler import save_multi_ingredient_response

            # Calculate initial concentrations based on interface type
            initial_concentrations = {}
            if interface_type == INTERFACE_SLIDERS and random_concentrations:
                # Use calculated random concentrations for slider interface
                initial_concentrations = random_concentrations
            elif interface_type == INTERFACE_2D_GRID:
                # Calculate concentrations from random grid position for 2D grid
                sugar_mm, salt_mm = (
                    ConcentrationMapper.map_coordinates_to_concentrations(
                        x, y, method=method
                    )
                )
                initial_concentrations = {
                    "Sugar": round(sugar_mm, 3),
                    "Salt": round(salt_mm, 3),
                }

            # Save initial position as first response with is_initial=True
            if initial_concentrations:
                initial_success = save_multi_ingredient_response(
                    participant_id=participant_id,
                    session_id=session_code,
                    method=method,
                    interface_type=interface_type,
                    ingredient_concentrations=initial_concentrations,
                    reaction_time_ms=0,  # No reaction time for initial position
                    questionnaire_response=None,
                    is_final_response=False,
                    is_initial=True,  # Mark as initial random position
                    extra_data={
                        "interface_type": interface_type,
                        "method": method,
                        "response_metadata": {
                            "is_initial_random": True,
                            "is_finish_button": False,
                            "is_final_submission": False,
                        },
                        "ui_data": {
                            "grid_position": (
                                {"x": x, "y": y}
                                if interface_type == INTERFACE_2D_GRID
                                else None
                            ),
                            "slider_percentages": (
                                random_slider_values
                                if interface_type == INTERFACE_SLIDERS
                                else None
                            ),
                            "concentrations_summary": None,
                        },
                        "ingredient_metadata": {
                            "ingredient_names": [ing["name"] for ing in ingredients],
                            "ingredient_order": list(range(len(ingredients))),
                            "ingredient_ranges": {
                                ing["name"]: {
                                    "min": ing["min_concentration"],
                                    "max": ing["max_concentration"],
                                    "unit": ing.get("unit", "mM"),
                                    "molecular_weight": ing.get("molecular_weight", 0),
                                }
                                for ing in ingredients
                            },
                        },
                    },
                )

                if initial_success:
                    st.info(
                        f"Initial random position registered for {participant_id}"
                    )
                else:
                    st.warning("Could not register initial position")

        except Exception as e:
            st.warning(f"Could not register initial position: {e}")

        # Update Streamlit session state
        st.session_state.phase = "respond"
        st.session_state.trial_start_time = time.perf_counter()
        st.session_state.participant = participant_id
        st.session_state.method = method
        st.session_state.num_ingredients = num_ingredients
        st.session_state.interface_type = interface_type
        st.session_state.ingredients = (
            ingredients  # FIXED: Store for subject interface to use
        )

        # Store initial positions in session state for immediate use
        if random_slider_values:
            st.session_state.random_slider_values = random_slider_values
        else:
            st.session_state.random_slider_values = {}

        # Store initial position in session state (for backward compatibility)
        st.session_state.x = x
        st.session_state.y = y

        # Store experiment configuration in session database for subject synchronization
        try:
            import json
            from session_manager import update_session_activity

            experiment_config = {
                "num_ingredients": num_ingredients,
                "interface_type": interface_type,
                "method": method,
                "ingredients": [
                    ing for ing in ingredients
                ],  # Store ingredient configuration
                "ingredient_metadata": {
                    "ingredient_names": [ing["name"] for ing in ingredients],
                    "ingredient_order": list(range(len(ingredients))),
                    "custom_ranges_used": ingredient_configs is not None,
                    "selected_by_moderator": selected_ingredients is not None,
                },
            }

            update_session_activity(
                session_code,
                phase="trial_started",
                config=json.dumps(experiment_config),
            )

        except Exception as e:
            st.warning(f"Could not update session config: {e}")

        # Also update old database for backward compatibility
        try:
            success = update_session_state(
                user_type=user_type,
                participant_id=participant_id,
                method=method,
                x=x,
                y=y,
                num_ingredients=num_ingredients,
            )
            if success:
                st.success(f"Trial started successfully for {participant_id}")
            else:
                st.warning("Trial started (old database compatibility issue)")
        except:
            st.warning("Trial started (old database compatibility issue)")

        return True

    except Exception as e:
        st.error(f"Error starting trial: {e}")
        import traceback

        st.error(f"Full traceback: {traceback.format_exc()}")
        return False


def finish_trial(
    canvas_result: Optional[Dict], participant_id: str, method: str
) -> bool:
    """
    Complete the current trial and save final results.

    Args:
        canvas_result: Canvas data with user's final position
        participant_id: Participant identifier
        method: Mapping method used

    Returns:
        Success status
    """
    try:
        if not canvas_result or not canvas_result.json_data:
            st.warning("No response data found.")
            return False

        # Get final position
        objects = canvas_result.json_data.get("objects", [])
        if not objects:
            st.warning("No position selected.")
            return False

        # Find the last dot (user's final selection)
        final_dot = None
        for obj in reversed(objects):
            if obj.get("type") == "circle" and obj.get("fill") in [
                "#EF4444",
                "#FF0000",
            ]:
                final_dot = obj
                break

        if not final_dot:
            st.warning("No valid selection found.")
            return False

        # Extract coordinates
        x = final_dot.get("left", 0)
        y = final_dot.get("top", 0)

        # Calculate concentrations
        sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
            x, y, method=method
        )

        # Calculate reaction time
        reaction_time_ms = None
        if hasattr(st.session_state, "trial_start_time"):
            reaction_time_ms = int(
                (time.perf_counter() - st.session_state.trial_start_time) * 1000
            )

        # Debug logging
        st.write(
            f"DEBUG: Saving FINAL response - participant: {participant_id}, x: {x}, y: {y}, method: {method}"
        )
        st.write(f"DEBUG: Concentrations - sugar: {sugar_mm}, salt: {salt_mm}")

        # Create ingredient concentrations dictionary
        ingredient_concentrations = {
            "Sugar": round(sugar_mm, 3),
            "Salt": round(salt_mm, 3),
        }

        # Get session code for database storage
        session_code = st.session_state.get("session_code", "default_session")

        # Save final response to responses table
        success = save_response(
            participant_id=participant_id,
            session_id=session_code,  # Add session_id parameter
            method=method,
            ingredient_concentrations=ingredient_concentrations,
            reaction_time_ms=reaction_time_ms,
            is_final=True,  # Mark as final response
            is_initial=False,  # User-generated response
            extra_data={
                "interface_type": INTERFACE_2D_GRID,
                "method": method,
                "response_metadata": {
                    "is_initial_random": False,
                    "is_finish_button": False,
                    "is_final_submission": True,
                },
                "ui_data": {
                    "grid_position": {"x": x, "y": y},
                    "slider_percentages": None,
                    "concentrations_summary": None,
                },
                "ingredient_metadata": {
                    "ingredient_names": ["Sugar", "Salt"],
                    "ingredient_order": [0, 1],
                    "ingredient_ranges": {
                        "Sugar": {
                            "min": 0.73,
                            "max": 73.0,
                            "unit": "mM",
                            "molecular_weight": 342.3,
                        },
                        "Salt": {
                            "min": 0.10,
                            "max": 10.0,
                            "unit": "mM",
                            "molecular_weight": 58.44,
                        },
                    },
                },
            },
        )

        if success:
            st.write("DEBUG: Final response saved successfully to database!")

            # Update session state for immediate feedback
            st.session_state.last_response = {
                "x": x,
                "y": y,
                "sugar_mm": sugar_mm,
                "salt_mm": salt_mm,
                "reaction_time_ms": reaction_time_ms,
            }

            return True
        else:
            st.error("Failed to save final response to database.")
            return False

    except Exception as e:
        st.error(f"Error finishing trial: {e}")
        import traceback

        st.error(f"Full traceback: {traceback.format_exc()}")
        return False


def save_click(participant_id: str, x: float, y: float, method: str) -> bool:
    """Save an intermediate click (part of the trajectory)."""
    try:
        # Calculate concentrations for every click
        from callback import ConcentrationMapper

        sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
            x, y, method=method
        )

        # Calculate reaction time from trial start
        reaction_time_ms = None

        if hasattr(st.session_state, "trial_start_time"):
            reaction_time_ms = int(
                (time.perf_counter() - st.session_state.trial_start_time) * 1000
            )

        # Create ingredient concentrations dictionary
        ingredient_concentrations = {
            "Sugar": round(sugar_mm, 3),
            "Salt": round(salt_mm, 3),
        }

        # Get session code for database storage
        session_code = st.session_state.get("session_code", "default_session")

        return save_response(
            participant_id=participant_id,
            session_id=session_code,  # Add session_id parameter
            method=method,
            ingredient_concentrations=ingredient_concentrations,
            reaction_time_ms=reaction_time_ms,
            is_final=False,
            is_initial=False,
            extra_data={
                "interface_type": INTERFACE_2D_GRID,
                "method": method,
                "response_metadata": {
                    "is_initial_random": False,
                    "is_finish_button": False,
                    "is_final_submission": False,
                },
                "ui_data": {
                    "grid_position": {"x": x, "y": y},
                    "slider_percentages": None,
                    "concentrations_summary": None,
                },
                "ingredient_metadata": {
                    "ingredient_names": ["Sugar", "Salt"],
                    "ingredient_order": [0, 1],
                    "ingredient_ranges": {
                        "Sugar": {
                            "min": 0.73,
                            "max": 73.0,
                            "unit": "mM",
                            "molecular_weight": 342.3,
                        },
                        "Salt": {
                            "min": 0.10,
                            "max": 10.0,
                            "unit": "mM",
                            "molecular_weight": 58.44,
                        },
                    },
                },
            },
        )

    except Exception as e:
        # logger.error(f"Error saving click: {e}")
        return False


def save_intermediate_click(
    participant_id: str, x: float, y: float, method: str
) -> bool:
    """Save an intermediate click to track the subject's path."""
    try:
        return save_click(participant_id, x, y, method)
    except Exception as e:
        st.error(f"Error saving intermediate click: {e}")
        return False


def get_concentration_display(x: float, y: float, method: str) -> Dict[str, Any]:
    """Get formatted concentration display for UI."""
    try:
        sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
            x, y, method=method
        )

        sugar_g, salt_g = ConcentrationMapper.concentrations_to_masses(
            sugar_mm, salt_mm
        )

        return {
            "sugar_mm": sugar_mm,
            "salt_mm": salt_mm,
            "sugar_g_per_100ml": sugar_g,
            "salt_g_per_100ml": salt_g,
            "coordinates": {"x": round(x, 1), "y": round(y, 1)},
        }

    except Exception as e:
        return {
            "error": f"Calculation error: {e}",
            "coordinates": {"x": round(x, 1), "y": round(y, 1)},
        }


def clear_canvas_state():
    """Clear all canvas-related keys from session state"""
    keys_to_remove = []
    for key in st.session_state.keys():
        if key.startswith("canvas_"):
            keys_to_remove.append(key)
    for key in keys_to_remove:
        del st.session_state[key]


# Questionnaire Configuration
QUESTIONNAIRE_CONFIG = {
    "unified_feedback": {
        "title": "Response Questionnaire",
        "description": "Please answer these questions about your current selection or impression.",
        "questions": [
            {
                "key": "confidence",
                "type": "slider",
                "label": "How confident are you in this selection/impression?",
                "min_value": 1,
                "max_value": 7,
                "help": "1 = Not confident at all, 7 = Very confident",
            },
            {
                "key": "strategy",
                "type": "selectbox",
                "label": "What guided your selection/impression?",
                "options": [
                    "Initial impression",
                    "Random selection",
                    "Based on previous selections",
                    "Systematic approach",
                    "Intuition/gut feeling",
                    "Other",
                ],
            },
            {
                "key": "satisfaction",
                "type": "slider",
                "label": "How satisfied are you with this selection?",
                "min_value": 1,
                "max_value": 7,
                "help": "1 = Not satisfied at all, 7 = Very satisfied",
            },
        ],
    },
    # Keep legacy configurations for backward compatibility
    "pre_sample": {
        "title": "Initial Impression Questionnaire",
        "description": "Please answer these questions about your initial impression.",
        "questions": [
            {
                "key": "confidence",
                "type": "slider",
                "label": "How confident are you in this initial impression?",
                "min_value": 1,
                "max_value": 7,
                "help": "1 = Not confident at all, 7 = Very confident",
            },
            {
                "key": "strategy",
                "type": "selectbox",
                "label": "What guided your initial impression?",
                "options": [
                    "Initial impression",
                    "Random response",
                    "Past experience",
                    "Intuition/gut feeling",
                    "Other",
                ],
            },
        ],
    },
    "post_response": {
        "title": "Selection Feedback Questionnaire",
        "description": "Please answer these questions about your selection.",
        "questions": [
            {
                "key": "confidence",
                "type": "slider",
                "label": "How confident are you in this selection?",
                "min_value": 1,
                "max_value": 7,
                "help": "1 = Not confident at all, 7 = Very confident",
            },
            {
                "key": "strategy",
                "type": "selectbox",
                "label": "What guided your selection?",
                "options": [
                    "Random selection",
                    "Based on previous selections",
                    "Systematic approach",
                    "Intuition/gut feeling",
                    "Other",
                ],
            },
        ],
    },
}


def render_questionnaire(
    questionnaire_type: str, participant_id: str, show_final_response: bool = False
) -> dict:
    """
    Render a modular questionnaire component.

    Args:
        questionnaire_type: Type of questionnaire ('pre_sample' or 'post_response')
        participant_id: Participant identifier
        show_final_response: Whether to show Final Response button instead of Continue

    Returns:
        dict: Questionnaire responses or None if not completed
    """
    if questionnaire_type not in QUESTIONNAIRE_CONFIG:
        st.error(f"Unknown questionnaire type: {questionnaire_type}")
        return None

    config = QUESTIONNAIRE_CONFIG[questionnaire_type]

    # Create unique session state keys for this questionnaire instance
    instance_key = f"questionnaire_{questionnaire_type}_{participant_id}"

    # Show placeholder notice
    st.markdown("### [QUESTIONNAIRE PLACEHOLDER - TO BE IMPLEMENTED]")
    st.info(
        "This is a temporary placeholder. The actual questionnaire content will be implemented based on research requirements."
    )

    st.markdown(f"### {config['title']}")
    st.write(config["description"])

    # Form to collect all responses
    with st.form(key=f"form_{instance_key}"):
        responses = {}

        for question in config["questions"]:
            question_key = f"{instance_key}_{question['key']}"

            if question["type"] == "slider":
                responses[question["key"]] = st.slider(
                    label=question["label"],
                    min_value=question["min_value"],
                    max_value=question["max_value"],
                    key=question_key,
                    help=question.get("help", None),
                )

            elif question["type"] == "selectbox":
                responses[question["key"]] = st.selectbox(
                    label=question["label"],
                    options=question["options"],
                    key=question_key,
                    help=question.get("help", None),
                )

            elif question["type"] == "text_input":
                responses[question["key"]] = st.text_input(
                    label=question["label"],
                    key=question_key,
                    help=question.get("help", None),
                )

            elif question["type"] == "text_area":
                responses[question["key"]] = st.text_area(
                    label=question["label"],
                    key=question_key,
                    help=question.get("help", None),
                )

        # Determine button text based on context
        button_text = "🏁 Final Response" if show_final_response else "Continue"
        submitted = st.form_submit_button(
            button_text,
            type="primary",
            use_container_width=True,
            key=f"submit_{instance_key}",
        )

        if submitted:
            # Add metadata
            responses["questionnaire_type"] = questionnaire_type
            responses["participant_id"] = participant_id
            responses["timestamp"] = datetime.now().isoformat()
            responses["is_final"] = show_final_response

            return responses

    return None


def show_preparation_message():
    """Display the solution preparation message."""
    st.success("Thank you for your response!")
    st.info(
        "The solution is being prepared. Please answer the questionnaire while you wait."
    )

    # Add a small loading animation
    with st.spinner("Preparing solution..."):
        time.sleep(1)  # Brief pause for realism


def save_slider_trial(participant_id: str, concentrations: dict, method: str) -> bool:
    """
    Save final slider-based trial results using unified database schema.

    Args:
        participant_id: Participant identifier
        concentrations: Dictionary of actual concentrations from MultiComponentMixture
        method: Always "slider_based" for slider trials

    Returns:
        Success status
    """
    try:
        from sql_handler import save_multi_ingredient_response

        # Calculate reaction time from trial start
        reaction_time_ms = None
        if hasattr(st.session_state, "trial_start_time"):
            reaction_time_ms = int(
                (time.perf_counter() - st.session_state.trial_start_time) * 1000
            )

        # Get session code from session state
        session_id = st.session_state.get("session_code", "default_session")

        # Extract actual mM concentrations for database storage
        ingredient_concentrations = {}
        for ingredient_name, conc_data in concentrations.items():
            ingredient_concentrations[ingredient_name] = round(
                conc_data["actual_concentration_mM"], 3
            )

        # Get questionnaire responses if available
        questionnaire_response = st.session_state.get(
            "post_questionnaire_responses", {}
        )

        # Store in unified database schema
        success = save_multi_ingredient_response(
            participant_id=participant_id,
            session_id=session_id,
            method=method,
            interface_type=INTERFACE_SLIDERS,
            ingredient_concentrations=ingredient_concentrations,
            reaction_time_ms=reaction_time_ms,
            questionnaire_response=questionnaire_response,
            is_final_response=True,
            is_initial=False,
            extra_data={
                "interface_type": INTERFACE_SLIDERS,
                "method": method,
                "response_metadata": {
                    "is_initial_random": False,
                    "is_finish_button": False,
                    "is_final_submission": True,
                },
                "ui_data": {
                    "grid_position": None,
                    "slider_percentages": {
                        ing: concentrations[ing]["slider_position"]
                        for ing in concentrations
                    },
                    "concentrations_summary": concentrations,
                },
                "ingredient_metadata": {
                    "ingredient_names": list(ingredient_concentrations.keys()),
                    "ingredient_order": list(range(len(ingredient_concentrations))),
                    "ingredient_ranges": {
                        ing: {
                            "min": concentrations[ing]["min_mM"],
                            "max": concentrations[ing]["max_mM"],
                            "unit": "mM",
                            "molecular_weight": concentrations[ing]["molecular_weight"],
                        }
                        for ing in concentrations
                    },
                },
            },
        )

        if success:
            # Store for display
            st.session_state.last_response = {
                "concentrations": concentrations,
                "method": method,
                "reaction_time_ms": reaction_time_ms or 0,
                "interface_type": INTERFACE_SLIDERS,
            }

            logger.info(f"Successfully saved slider trial for {participant_id}")
            return True
        else:
            logger.error(f"Failed to save slider trial for {participant_id}")
            return False

    except Exception as e:
        logger.error(f"Error saving slider trial: {e}")
        return False


def get_stored_random_values(participant_id: str) -> dict:
    """
    Retrieve stored random slider values from database.

    This fixes the random start bug by ensuring random values are persistent
    and retrieved correctly from the database.

    Args:
        participant_id: Participant identifier

    Returns:
        Dictionary of random slider values or empty dict
    """
    try:
        from sql_handler import get_initial_positions_v2

        # Get experiment ID from session state
        experiment_id = st.session_state.get("experiment_id")
        if not experiment_id:
            return {}

        # Retrieve initial positions from database
        initial_positions = get_initial_positions_v2(experiment_id, participant_id)
        if not initial_positions:
            return {}

        # Extract slider values from database columns
        random_values = {}
        ingredient_config = st.session_state.get(
            "ingredient_config", DEFAULT_INGREDIENT_CONFIG
        )
        num_ingredients = st.session_state.get("num_ingredients", 2)

        for i, ingredient in enumerate(ingredient_config[:num_ingredients]):
            column_name = f"ingredient_{i+1}_initial"
            if (
                column_name in initial_positions
                and initial_positions[column_name] is not None
            ):
                random_values[ingredient["name"]] = initial_positions[column_name]

        return random_values

    except Exception as e:
        st.error(f"Error retrieving stored random values: {e}")
        return {}


def ensure_random_values_loaded(participant_id: str) -> bool:
    """
    Ensure random slider values are loaded into session state.

    This fixes the random start issue by checking if values exist in database
    and loading them into session state for immediate use.

    Args:
        participant_id: Participant identifier

    Returns:
        True if values were loaded or already exist, False otherwise
    """
    try:
        # Check if values already exist in session state
        existing_values = st.session_state.get("random_slider_values", {})
        if existing_values:
            return True

        # Try to load from database
        stored_values = get_stored_random_values(participant_id)
        if stored_values:
            st.session_state.random_slider_values = stored_values
            return True

        # No values found
        return False

    except Exception as e:
        st.error(f"Error ensuring random values loaded: {e}")
        import traceback

        st.error(f"Full traceback: {traceback.format_exc()}")
        return False


def cleanup_pending_results():
    """Clean up all pending result data from session state."""
    pending_keys = ["pending_canvas_result", "pending_slider_result", "pending_method"]

    for key in pending_keys:
        if hasattr(st.session_state, key):
            delattr(st.session_state, key)


# =============================================================================
# END OF FILE - DEVELOPMENT NOTES
# =============================================================================
# MATHEMATICAL MODELS IMPLEMENTED:
# - Linear mapping: Direct proportional concentration scaling
# - Logarithmic mapping: Natural log-based scaling for wider ranges
# - Exponential mapping: Exponential curve-based scaling
#
# KEY AREAS FOR IMPROVEMENT:
# - Add concentration safety validation before solution preparation
# - Implement ingredient interaction compatibility matrix
# - Add temperature and pH-dependent concentration adjustments
# - Create automated calibration and quality control systems
#
# RESEARCH CONSIDERATIONS:
# - All concentration calculations based on peer-reviewed literature
# - Molecular weights and ranges validated against taste threshold studies
# - JSON data storage supports complex multi-component analysis
# =============================================================================
