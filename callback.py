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
from datetime import datetime
from typing import Tuple, Dict, Any, Optional
from bayesian_optimizer import get_default_bo_config
from robotaste.data import database as sql
from robotaste.components.canvas import (
    create_canvas_drawing,
    clear_canvas_state,
    get_canvas_size,
    CANVAS_SIZE,
    GRID_STEP,
)
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Note: CANVAS_SIZE, GRID_STEP, get_canvas_size(), create_canvas_drawing(), and clear_canvas_state()
# are now imported from robotaste.components.canvas


NACL_MW = 58.44  # g/mol

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
INTERFACE_SINGLE_INGREDIENT = "single_ingredient"
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

    @staticmethod
    def map_concentrations_to_coordinates(
        sugar_mm: float,
        salt_mm: float,
        method: str = "linear",
        canvas_size: int = CANVAS_SIZE,
        sugar_range: Tuple[float, float] = SUGAR_RANGE_MM,
        salt_range: Tuple[float, float] = SALT_RANGE_MM,
    ) -> Tuple[float, float]:
        """
        Convert sugar & salt concentrations back to canvas coordinates.

        This is the INVERSE of map_coordinates_to_concentrations().

        Args:
            sugar_mm: Sugar concentration in mM
            salt_mm: Salt concentration in mM
            method: Mapping method ('linear', 'logarithmic', 'exponential')
            canvas_size: Size of the canvas
            sugar_range: (min, max) sugar concentration in mM
            salt_range: (min, max) salt concentration in mM

        Returns:
            (x, y) canvas coordinates

        Note:
            Y-axis is flipped: higher concentration = lower y value
            This matches the forward mapping behavior.
        """
        if method == "linear":
            # Inverse of: sugar = min + x_norm * (max - min)
            # Solve for x_norm: x_norm = (sugar - min) / (max - min)
            x_norm = (sugar_mm - sugar_range[0]) / (sugar_range[1] - sugar_range[0])
            y_norm = (salt_mm - salt_range[0]) / (salt_range[1] - salt_range[0])

        elif method == "logarithmic":
            # Inverse of: sugar = exp(log_min + x_norm * (log_max - log_min))
            # Solve for x_norm: x_norm = (log(sugar) - log_min) / (log_max - log_min)
            if sugar_range[0] <= 0 or salt_range[0] <= 0:
                raise ValueError(
                    "Logarithmic mapping requires positive concentration ranges"
                )

            log_sugar_range = (math.log(sugar_range[0]), math.log(sugar_range[1]))
            log_salt_range = (math.log(salt_range[0]), math.log(salt_range[1]))

            x_norm = (math.log(sugar_mm) - log_sugar_range[0]) / (
                log_sugar_range[1] - log_sugar_range[0]
            )
            y_norm = (math.log(salt_mm) - log_salt_range[0]) / (
                log_salt_range[1] - log_salt_range[0]
            )

        elif method == "exponential":
            # Inverse of: sugar = max * ((min/max)^(1 - x_norm))
            # Solve for x_norm: x_norm = 1 - (log(sugar/max) / log(min/max))
            ratio_sugar = sugar_mm / sugar_range[1]
            ratio_salt = salt_mm / salt_range[1]

            base_sugar = sugar_range[0] / sugar_range[1]
            base_salt = salt_range[0] / salt_range[1]

            x_norm = 1 - (math.log(ratio_sugar) / math.log(base_sugar))
            y_norm = 1 - (math.log(ratio_salt) / math.log(base_salt))

        else:
            raise ValueError(f"Unknown mapping method: {method}")

        # Clamp normalized values to [0, 1]
        x_norm = max(0.0, min(1.0, x_norm))
        y_norm = max(0.0, min(1.0, y_norm))

        # Convert back to canvas coordinates
        x = x_norm * canvas_size
        # Flip y-axis: y_norm=1 (max salt) should be at canvas y=0 (top)
        y = (1.0 - y_norm) * canvas_size

        return round(x, 1), round(y, 1)


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


# create_canvas_drawing() now imported from robotaste.components.canvas


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
        return (
            INTERFACE_2D_GRID
            if self.num_ingredients == 2
            else INTERFACE_SINGLE_INGREDIENT
        )

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
        from robotaste.data.database import update_session_state

        # Generate random starting position for grid interface
        x, y = generate_random_position()

        # Determine interface type
        interface_type = (
            INTERFACE_2D_GRID if num_ingredients == 2 else INTERFACE_SINGLE_INGREDIENT
        )

        # Get session identifiers - session_id for DB, session_code for display
        session_id = st.session_state.get("session_id")
        session_code = st.session_state.get("session_code")
        if not session_id:
            st.error("No session ID found. Please create a session first.")
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

        # Generate random starting positions if enabled
        random_slider_values = {}
        random_concentrations = {}
        if use_random_start and interface_type == INTERFACE_SINGLE_INGREDIENT:
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

            # Initial random positions are stored in session state
            # (st.session_state.random_slider_values for single ingredient)
            # In the new 6-phase workflow, initial positions don't need separate DB storage
            # They will be included in selection_data when save_sample_cycle() is called

        # Update Streamlit session state
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

        # Store the initial random concentration as the "current tasted sample" for cycle 1
        # This will be used when saving the first cycle's data after questionnaire
        if random_concentrations:
            # Slider interface - use calculated random concentrations
            st.session_state.current_tasted_sample = random_concentrations.copy()
        elif interface_type == INTERFACE_2D_GRID:
            # Grid interface - calculate concentrations from random x,y position
            sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
                x, y, method=method
            )
            st.session_state.current_tasted_sample = {
                "Sugar": round(sugar_mm, 3),
                "Salt": round(salt_mm, 3),
            }
        else:
            st.session_state.current_tasted_sample = {}

        # Note: Cycle 0 data is NOT saved here to avoid duplicate sample IDs.
        # The initial random sample will be saved with the first questionnaire answer,
        # creating a single sample ID that links the initial concentrations with the first response.

        # Store experiment configuration in session database for subject synchronization
        try:
            import json
            from robotaste.core.state_machine import ExperimentPhase
            from robotaste.core import state_helpers

            # Get questionnaire type from session state (set by moderator)
            from questionnaire_config import get_default_questionnaire_type

            questionnaire_type = st.session_state.get(
                "selected_questionnaire_type", get_default_questionnaire_type()
            )

            experiment_config = {
                "num_ingredients": num_ingredients,
                "interface_type": interface_type,
                "method": method,
                "current_cycle": 0,  # Initialize cycle counter to 0
                "initial_concentrations": st.session_state.current_tasted_sample,  # Store for subject interface sync
                "initial_slider_values": random_slider_values,  # Store random slider positions for subject interface
                "questionnaire_type": questionnaire_type,  # Store selected questionnaire type
                "bayesian_optimization": st.session_state.get(
                    "bo_config", get_default_bo_config()
                ),  # Store BO configuration
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

            # Update experiment config in database
            # Get questionnaire_type_id from database
            question_type_id = sql.get_questionnaire_type_id(questionnaire_type)

            # Serialize ingredients to JSON
            ingredients_json = json.dumps([ing for ing in ingredients])

            with sql.get_database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE sessions
                    SET experiment_config = ?,
                        question_type_id = ?,
                        ingredients = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """,
                    (
                        json.dumps(experiment_config),
                        question_type_id,
                        ingredients_json,
                        session_id,
                    ),  # Use session_id for DB
                )
                conn.commit()

            # Use state machine to transition to LOADING phase
            # In the 5-phase workflow, trial starts in LOADING where robot prepares first sample
            # This follows the valid transition: WAITING → LOADING
            try:
                current_phase = state_helpers.get_current_phase()
                state_helpers.transition(
                    current_phase=current_phase,
                    new_phase=ExperimentPhase.LOADING,
                    session_id=session_id,  # Use session_id for DB
                )
            except Exception as sm_error:
                # Fallback: directly set phase if state machine fails
                logger.warning(
                    f"State machine transition failed: {sm_error}. Using direct assignment."
                )
                st.session_state.phase = "loading"

        except Exception as e:
            st.warning(f"Could not update session config: {e}")

        # Success message
        st.success(f"Trial started successfully for {participant_id}")
        return True

    except Exception as e:
        st.error(f"Error starting trial: {e}")
        import traceback

        st.error(f"Full traceback: {traceback.format_exc()}")
        return False


def save_click(
    participant_id: str,
    x: float,
    y: float,
    method: str,
    sample_id: Optional[str] = None,
) -> bool:
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

        # Store click data in session state for trajectory tracking
        # This will be included in selection_data when save_sample_cycle() is called
        if not hasattr(st.session_state, "trajectory_clicks"):
            st.session_state.trajectory_clicks = []

        st.session_state.trajectory_clicks.append(
            {
                "x": x,
                "y": y,
                "concentrations": ingredient_concentrations,
                "reaction_time_ms": reaction_time_ms,
                "sample_id": sample_id,
                "timestamp": time.time(),
            }
        )

        return True

    except Exception as e:
        # logger.error(f"Error saving click: {e}")
        return False


def save_intermediate_click(
    participant_id: str,
    x: float,
    y: float,
    method: str,
    sample_id: Optional[str] = None,
) -> bool:
    """Save an intermediate click to track the subject's path."""
    try:
        return save_click(participant_id, x, y, method, sample_id)
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


# clear_canvas_state() now imported from robotaste.components.canvas


def render_questionnaire(
    questionnaire_type: str, participant_id: str, show_final_response: bool = False
) -> dict:
    """
    Render a modular questionnaire component using the centralized questionnaire configuration.

    Args:
        questionnaire_type: Type of questionnaire (e.g., 'hedonic', 'unified_feedback')
        participant_id: Participant identifier
        show_final_response: Whether to show Final Response button instead of Continue

    Returns:
        dict: Questionnaire responses or None if not completed
    """
    from questionnaire_config import get_questionnaire_config

    # Get questionnaire configuration from centralized system
    config = get_questionnaire_config(questionnaire_type)

    if config is None:
        st.error(f"Unknown questionnaire type: {questionnaire_type}")
        return None  # type: ignore

    # Create unique session state keys for this questionnaire instance
    instance_key = f"questionnaire_{questionnaire_type}_{participant_id}"

    # Display questionnaire header
    st.markdown(f"### {config.get('name', 'Questionnaire')}")

    # Form to collect all responses
    with st.form(key=f"form_{instance_key}"):
        responses = {}

        for question in config["questions"]:
            question_id = question["id"]
            question_key = f"{instance_key}_{question_id}"
            question_type = question["type"]

            if question_type == "slider":
                # Build scale labels display if available
                scale_labels = question.get("scale_labels", {})
                help_text = question.get("help_text", "")
                display_type = question.get("display_type", "slider")

                # Get numeric parameters - support both int and float
                min_val = question["min"]
                max_val = question["max"]
                default_val = question.get("default", min_val)
                step_val = question.get("step", 1)

                # Determine if this is a float or int scale
                is_float = isinstance(step_val, float) and step_val < 1

                # Handle pillboxes display type (radio buttons)
                if display_type == "pillboxes":
                    st.markdown(f"**{question['label']}**")
                    if help_text:
                        st.caption(help_text)

                    # Show scale labels if available
                    if scale_labels:
                        label_display = " | ".join(
                            [
                                f"{val}: {label}"
                                for val, label in sorted(scale_labels.items())
                            ]
                        )
                        st.caption(label_display)

                    # Create options list (only works for integer scales)
                    options = list(range(int(min_val), int(max_val) + 1))
                    default_index = (
                        options.index(int(default_val))
                        if int(default_val) in options
                        else 0
                    )

                    responses[question_id] = st.radio(
                        label=question["label"],
                        options=options,
                        index=default_index,
                        format_func=lambda x: (
                            scale_labels.get(x, str(x)) if scale_labels else str(x)
                        ),
                        horizontal=True,
                        key=question_key,
                        label_visibility="collapsed",
                    )

                # Handle continuous slider display (float values)
                elif display_type == "slider_continuous" or is_float:
                    if scale_labels:
                        st.markdown(f"**{question['label']}**")
                        if help_text:
                            st.caption(help_text)

                        # Show key scale labels
                        label_display = " | ".join(
                            [
                                f"{val}: {label}"
                                for val, label in sorted(scale_labels.items())
                            ]
                        )
                        st.caption(label_display)

                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=float(min_val),
                            max_value=float(max_val),
                            value=float(default_val),
                            step=float(step_val),
                            key=question_key,
                            label_visibility="collapsed",
                            format="%.2f",  # Show 2 decimal places
                        )
                    else:
                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=float(min_val),
                            max_value=float(max_val),
                            value=float(default_val),
                            step=float(step_val),
                            key=question_key,
                            help=help_text if help_text else None,
                            format="%.2f",
                        )

                # Handle standard discrete slider (default behavior)
                else:
                    if scale_labels:
                        st.markdown(f"**{question['label']}**")
                        if help_text:
                            st.caption(help_text)

                        # Show key scale labels
                        label_display = " | ".join(
                            [
                                f"{val}: {label}"
                                for val, label in sorted(scale_labels.items())
                            ]
                        )
                        st.caption(label_display)

                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=int(min_val),
                            max_value=int(max_val),
                            value=int(default_val),
                            step=int(step_val),
                            key=question_key,
                            label_visibility="collapsed",
                            format="%d",  # Show as integers
                        )
                    else:
                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=int(min_val),
                            max_value=int(max_val),
                            value=int(default_val),
                            step=int(step_val),
                            key=question_key,
                            help=help_text if help_text else None,
                        )

            elif question_type == "dropdown":
                responses[question_id] = st.selectbox(
                    label=question["label"],
                    options=question["options"],
                    index=(
                        question["options"].index(
                            question.get("default", question["options"][0])
                        )
                        if question.get("default") in question["options"]
                        else 0
                    ),
                    key=question_key,
                    help=question.get("help_text", None),
                )

            elif question_type == "text_input":
                responses[question_id] = st.text_input(
                    label=question["label"],
                    value=question.get("default", ""),
                    key=question_key,
                    help=question.get("help_text", None),
                )

            elif question_type == "text_area":
                responses[question_id] = st.text_area(
                    label=question["label"],
                    value=question.get("default", ""),
                    key=question_key,
                    help=question.get("help_text", None),
                )

        # Determine button text based on context
        button_text = "Final Response" if show_final_response else "Continue"
        submitted = st.form_submit_button(
            button_text,
            type="primary",
            width="stretch",
            key=f"submit_{instance_key}",
        )

        if submitted:
            # Add metadata
            responses["questionnaire_type"] = questionnaire_type
            responses["participant_id"] = participant_id
            responses["timestamp"] = datetime.now().isoformat()
            responses["is_final"] = show_final_response

            return responses

    return None  # type: ignore


def ensure_random_values_loaded(participant_id: str) -> bool:
    """
    Ensure random slider values are loaded into session state.

    Args:
        participant_id: Participant identifier

    Returns:
        True if values exist in session state, False otherwise
    """
    try:
        # Check if values already exist in session state
        existing_values = st.session_state.get("random_slider_values", {})
        if existing_values:
            return True

        # No values found
        return False

    except Exception as e:
        logger.error(f"Error ensuring random values loaded: {e}")
        return False


def get_bo_suggestion_for_session(
    session_id: str, participant_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get Bayesian Optimization suggestion for the next sample.

    This function checks if BO should be active (cycle >= 3), trains the BO model
    from existing data, generates candidate samples, and returns the best suggestion
    with interface-specific coordinates.

    Args:
        session_id: Session identifier for database queries
        participant_id: Participant identifier

    Returns:
        Dictionary with BO suggestion or None if BO not ready/active:
        {
            "concentrations": {"Sugar": 42.3, "Salt": 6.7, ...},
            "predicted_value": 7.8,
            "uncertainty": 0.5,
            "acquisition_value": 0.0234,
            "grid_coordinates": {"x": 250, "y": 300},  # For 2D grid only
            "slider_values": {"Sugar": 65, "Salt": 42, ...},  # For sliders only
            "mode": "bayesian_optimization"
        }
    """
    try:
        from bayesian_optimizer import (
            train_bo_model_for_participant,
            generate_candidate_grid_2d,
            generate_candidates_latin_hypercube,
        )

        # Get current cycle and experiment config
        current_cycle = sql.get_current_cycle(session_id)
        session = sql.get_session(session_id)

        if not session:
            logger.warning(f"Session {session_id} not found")
            return None

        experiment_config = session.get("experiment_config", {})
        bo_config = experiment_config.get("bayesian_optimization", {})

        # Check if BO is enabled
        if not bo_config.get("enabled", True):
            logger.info("BO disabled for this session")
            return None

        # Check if we have enough samples (default: 3, meaning cycle >= 3)
        min_samples = bo_config.get("min_samples_for_bo", 3)
        if current_cycle < min_samples:
            logger.info(f"BO not ready: cycle {current_cycle} < min {min_samples}")
            return None

        # Train BO model
        logger.info(f"Training BO model for cycle {current_cycle}")
        bo_model = train_bo_model_for_participant(
            participant_id=participant_id, session_id=session_id, bo_config=bo_config
        )

        if bo_model is None:
            logger.warning("BO model training failed")
            return None

        # Get ingredient configuration
        ingredients = experiment_config.get("ingredients", [])
        num_ingredients = len(ingredients)

        # Generate candidates based on interface type
        if num_ingredients == 2:
            # 2D Grid interface - use grid sampling
            ingredient_ranges = {
                ing["name"]: (ing["min_concentration"], ing["max_concentration"])
                for ing in ingredients
            }

            # Get concentration ranges for the two ingredients
            ranges_list = list(ingredient_ranges.values())
            candidates = generate_candidate_grid_2d(
                sugar_range=ranges_list[0],
                salt_range=ranges_list[1],
                n_points=bo_config.get("n_candidates_grid", 20),
            )
        else:
            # Slider interface - use Latin Hypercube Sampling
            ingredient_ranges = {
                ing["name"]: (ing["min_concentration"], ing["max_concentration"])
                for ing in ingredients
            }
            candidates = generate_candidates_latin_hypercube(
                ranges=ingredient_ranges,
                n_candidates=bo_config.get("n_candidates_lhs", 1000),
                random_state=bo_config.get("random_state", 42),
            )

        # Determine max_cycles based on dimensionality
        stopping_criteria = bo_config.get("stopping_criteria", {})
        if num_ingredients == 2:
            max_cycles = stopping_criteria.get("max_cycles_2d", 50)
        else:
            max_cycles = stopping_criteria.get("max_cycles_1d", 30)

        # Get BO suggestion with adaptive acquisition parameters
        suggestion = bo_model.suggest_next_sample(
            candidates=candidates,
            acquisition=bo_config.get("acquisition_function", "ei"),
            current_cycle=current_cycle,
            max_cycles=max_cycles,
            # Note: xi/kappa will be computed adaptively if adaptive_acquisition=True
            # Otherwise, config defaults will be used
        )

        if not suggestion:
            logger.warning("BO suggestion failed")
            return None

        # Extract concentrations
        concentrations = suggestion["best_candidate_dict"]

        # Build result dictionary
        result = {
            "concentrations": concentrations,
            "predicted_value": suggestion.get("predicted_value"),
            "uncertainty": suggestion.get("uncertainty"),
            "acquisition_value": suggestion.get("acquisition_value"),
            "acquisition_function": suggestion.get("acquisition_function"),  # ei or ucb
            "acquisition_params": suggestion.get(
                "acquisition_params", {}
            ),  # Store xi/kappa for tracking
            "current_cycle": current_cycle,
            "max_cycles": max_cycles,
            "mode": "bayesian_optimization",
        }

        # Convert to interface-specific coordinates
        if num_ingredients == 2:
            # Convert concentrations to grid coordinates (x, y)
            ingredient_names = list(concentrations.keys())
            sugar_conc = concentrations[ingredient_names[0]]
            salt_conc = concentrations[ingredient_names[1]]

            # Get the mapping method from config
            method = experiment_config.get("method", "logarithmic")

            # Get concentration ranges
            ingredient_ranges_dict = {
                ing["name"]: (ing["min_concentration"], ing["max_concentration"])
                for ing in ingredients
            }
            sugar_range = ingredient_ranges_dict[ingredient_names[0]]
            salt_range = ingredient_ranges_dict[ingredient_names[1]]

            # Use ConcentrationMapper to convert back to coordinates
            x, y = ConcentrationMapper.map_concentrations_to_coordinates(
                sugar_mm=sugar_conc,
                salt_mm=salt_conc,
                method=method,
                sugar_range=sugar_range,
                salt_range=salt_range,
                canvas_size=CANVAS_SIZE,
            )

            # Clamp coordinates to canvas bounds [0, CANVAS_SIZE-1] to ensure visibility
            # Canvas is 0-indexed, so valid range is [0, 499] not [0, 500]
            result["grid_coordinates"] = {
                "x": max(0, min(CANVAS_SIZE - 1, int(x))),
                "y": max(0, min(CANVAS_SIZE - 1, int(y))),
            }

        else:
            # Convert concentrations to slider percentages (0-100)
            slider_values = {}
            for ing in ingredients:
                ing_name = ing["name"]
                conc = concentrations.get(ing_name, 0)
                min_conc = ing["min_concentration"]
                max_conc = ing["max_concentration"]

                # Convert to percentage (0-100)
                if max_conc > min_conc:
                    percentage = ((conc - min_conc) / (max_conc - min_conc)) * 100
                    slider_values[ing_name] = max(0, min(100, int(percentage)))
                else:
                    slider_values[ing_name] = 0

            result["slider_values"] = slider_values

        # Check convergence and add to result
        try:
            from bayesian_optimizer import check_convergence

            stopping_criteria = bo_config.get("stopping_criteria")
            convergence = check_convergence(session_id, stopping_criteria)

            # Add convergence info to result for subject interface
            result["convergence"] = {
                "converged": convergence.get("converged", False),
                "recommendation": convergence.get("recommendation", "continue"),
                "reason": convergence.get("reason", ""),
                "confidence": convergence.get("confidence", 0.0),
                "status_emoji": convergence.get("status_emoji", "🔴"),
                "current_cycle": convergence["metrics"].get(
                    "current_cycle", current_cycle
                ),
                "max_cycles": convergence["thresholds"].get("max_cycles", 30),
            }

            logger.info(
                f"Convergence check: {convergence.get('recommendation')} - {convergence.get('reason')}"
            )

        except Exception as e:
            logger.warning(f"Could not check convergence: {e}")
            result["convergence"] = {
                "converged": False,
                "recommendation": "continue",
                "reason": "Error checking convergence",
                "confidence": 0.0,
                "status_emoji": "🔴",
                "current_cycle": current_cycle,
                "max_cycles": 30,
            }

        logger.info(
            f"BO suggestion generated for cycle {current_cycle}: "
            f"predicted={result['predicted_value']:.2f}"
        )
        return result

    except Exception as e:
        logger.error(f"Error getting BO suggestion: {e}", exc_info=True)
        return None


def cleanup_pending_results():
    """Clean up all pending result data from session state."""
    pending_keys = ["pending_canvas_result", "pending_slider_result", "pending_method"]

    for key in pending_keys:
        if hasattr(st.session_state, key):
            delattr(st.session_state, key)


def render_loading_spinner(message: str = "Loading...", load_time=5):
    """Render a loading spinner with a custom message."""
    with st.spinner(message, width="stretch"):
        time.sleep(load_time)  # Small delay to ensure spinner is visible
        # Phase transition handled by calling code using state machine


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
