"""
RoboTaste Core Calculations Module

Pure Python module for concentration mapping and mixture calculations.
NO external dependencies (no Streamlit, no SQL).

Contains:
- ConcentrationMapper: Coordinate ↔ concentration conversions
- MultiComponentMixture: Multi-ingredient mixture management
- Helper functions for solution preparation

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import math
import random
from typing import Tuple, Dict, Any, Optional, List


# ============================================================================
# CONSTANTS
# ============================================================================

# Scientific constants
SUCROSE_MW = 342.3  # g/mol (Sugar molecular weight)
NACL_MW = 58.44  # g/mol (Salt molecular weight)

# Canvas settings
CANVAS_SIZE = 500  # Default canvas size in pixels
GRID_STEP = 50  # Grid spacing in pixels

# Interface type constants
INTERFACE_2D_GRID = "2d_grid"
INTERFACE_SINGLE_INGREDIENT = "single_ingredient"

# Concentration ranges from literature
SUGAR_RANGE_MM = (0.73, 73.0)  # mM from Breslin paper
SALT_RANGE_MM = (0.10, 10.0)  # mM approximation

# Canvas bounds for random positioning
POSITION_BOUNDS = (GRID_STEP, CANVAS_SIZE - GRID_STEP)


# ============================================================================
# CONCENTRATION MAPPER CLASS
# ============================================================================


class ConcentrationMapper:
    """
    Handles mapping between canvas coordinates and concentrations.

    Supports three mapping methods:
    - Linear: Direct proportional mapping
    - Logarithmic: Log-scale mapping for wide concentration ranges
    - Exponential: Exponential scale mapping
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
        """
        Convert concentrations to masses for solution preparation.

        Args:
            sugar_mm: Sugar concentration in mM
            salt_mm: Salt concentration in mM
            volume_ml: Solution volume in mL

        Returns:
            (sugar_mass_g, salt_mass_g) tuple
        """
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


# ============================================================================
# MULTI-COMPONENT MIXTURE CLASS
# ============================================================================


class MultiComponentMixture:
    """
    Handle multi-component mixture configurations and calculations.

    Manages complex mixture systems with 2-6 ingredients, providing concentration
    calculations, solution preparation data, and interface type determination.
    """

    def __init__(self, ingredients_config: List[Dict[str, Any]]):
        """
        Initialize with ingredient configuration.

        Args:
            ingredients_config: List of ingredient dictionaries with name,
                              min_concentration, max_concentration, molecular_weight
        """
        self.ingredients = ingredients_config
        self.num_ingredients = len(ingredients_config)

    def get_interface_type(self) -> str:
        """
        Determine interface type based on number of ingredients.

        Returns:
            '2d_grid' for 2 ingredients, 'single_ingredient' otherwise
        """
        return (
            INTERFACE_2D_GRID
            if self.num_ingredients == 2
            else INTERFACE_SINGLE_INGREDIENT
        )

    def calculate_concentrations_from_sliders(
        self, slider_values: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
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

    def get_default_slider_values(self) -> Dict[str, float]:
        """
        Get default slider positions for initialization.

        Returns:
            Dict of ingredient names to default slider positions (50.0 = middle)
        """
        default_values = {}
        for ingredient in self.ingredients:
            # Start at middle of range
            default_values[ingredient["name"]] = 50.0
        return default_values

    def calculate_solution_mass(
        self, concentrations: Dict[str, Dict[str, Any]], volume_ml: float = 100.0
    ) -> Dict[str, Dict[str, float]]:
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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def generate_random_position(
    x_range: Tuple[float, float] = POSITION_BOUNDS,
    y_range: Tuple[float, float] = POSITION_BOUNDS,
) -> Tuple[float, float]:
    """
    Generate random coordinates within canvas bounds.

    Args:
        x_range: (min, max) x-coordinate range
        y_range: (min, max) y-coordinate range

    Returns:
        (x, y) tuple of random coordinates
    """
    x = random.uniform(x_range[0], x_range[1])
    y = random.uniform(y_range[0], y_range[1])
    return round(x, 1), round(y, 1)


def calculate_stock_volumes(
    concentrations: Dict[str, float],
    ingredient_configs: List[Dict[str, Any]],
    final_volume_mL: float = 10.0,
) -> Dict[str, Any]:
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
