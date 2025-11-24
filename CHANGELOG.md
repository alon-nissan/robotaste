# Changelog

All notable changes to the RoboTaste project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2024-11-24

### Added

#### Adaptive Bayesian Optimization
- **Adaptive Acquisition Parameters**: Implemented time-varying exploration/exploitation based on Benjamins et al. (2022) research
  - Linear decay schedule from high exploration to high exploitation
  - Configurable `exploration_budget` (default: 25% of cycles)
  - Separate parameters for early phase (exploration) and late phase (exploitation)
  - Supports both EI (xi parameter) and UCB (kappa parameter) acquisition functions
- **New BO Configuration Parameters**:
  - `adaptive_acquisition` (boolean, default: True)
  - `exploration_budget` (float, default: 0.25)
  - `xi_exploration` (float, default: 0.1)
  - `xi_exploitation` (float, default: 0.01)
  - `kappa_exploration` (float, default: 3.0)
  - `kappa_exploitation` (float, default: 1.0)
- **Adaptive Functions** in `bayesian_optimizer.py`:
  - `get_adaptive_xi()`: Computes time-varying xi parameter
  - `get_adaptive_kappa()`: Computes time-varying kappa parameter
  - Updated `suggest_next_sample()` to accept `current_cycle` and `max_cycles` parameters

#### Database Schema v3.0
- **Extended `bo_configuration` table** with 16 new columns:
  - 6 adaptive acquisition parameters
  - 10 convergence/stopping criteria parameters
- **Extended `samples` table** with 6 new columns for per-cycle BO metadata:
  - `acquisition_function`: "ei" or "ucb"
  - `acquisition_xi`: Xi parameter used (NULL for UCB)
  - `acquisition_kappa`: Kappa parameter used (NULL for EI)
  - `acquisition_value`: Acquisition function output
  - `predicted_value`: GP mean prediction
  - `uncertainty`: GP standard deviation (sigma)
- **New `bo_cycle_analysis` view** for research analysis:
  - Joins samples, sessions, and bo_configuration tables
  - Extracts JSON fields for easy querying
  - Calculates prediction errors automatically
  - Filters to BO cycles only (excludes random exploration)
- **New index**: `idx_samples_acquisition_function` for performance
- **Documentation**: Complete schema documentation in `docs/DATABASE_SCHEMA_V3.md`

#### Moderator UI Enhancements
- **New "🎯 Adaptive Exploration Strategy" section**:
  - Expanded by default to showcase new feature
  - Enable/disable checkbox with smart defaults
  - Exploration budget slider (0-100%)
  - Two-column phase layout:
    - Early Phase (🔵 Exploration): xi_exploration or kappa_exploration
    - Late Phase (🟢 Exploitation): xi_exploitation or kappa_exploitation
  - Visual phase progression timeline with color gradient
  - Conditional rendering based on acquisition function (EI vs UCB)
- **Static mode fallback**:
  - Warning message when adaptive mode is disabled
  - Clear labeling ("STATIC") to distinguish from adaptive parameters
- **New helper function**: `_render_phase_timeline()` for visual timeline
- **Academic citation**: Links to Benjamins et al. (2022) arXiv paper
- **Comprehensive tooltips**: Research-friendly explanations for all parameters

### Changed

#### Core BO Functionality
- **`bayesian_optimizer.py`**:
  - Modified `suggest_next_sample()` signature to accept `current_cycle` and `max_cycles`
  - Added `acquisition_params` to return dictionary with computed xi/kappa values
  - Default config now enables `adaptive_acquisition` by default
- **`callback.py`**:
  - Updated `get_bo_suggestion_for_session()` to determine and pass max_cycles based on dimensionality
  - Added `acquisition_function` to result dictionary (was missing)
  - Now passes `current_cycle` and `max_cycles` to BO model

#### Subject Interface
- **`subject_interface.py`**:
  - 2D Grid interface: Added `acquisition_function` and `acquisition_params` to `next_selection_data`
  - Slider interface: Added `acquisition_function` and `acquisition_params` to `next_selection_data`
  - Ensures BO metadata is captured for database storage

#### Database Operations
- **`sql_handler.py`**:
  - `update_session_with_config()`: Now inserts 32 columns to bo_configuration (was 20)
  - `save_sample_cycle()`: Extracts and stores 6 BO metadata fields
  - Added logging for BO parameters when saving samples

#### Visualization
- **`moderator_interface.py`**:
  - 1D BO visualization: Now clips confidence bounds to [1, 9] for hedonic scale
  - 2D BO visualization: (unchanged)
  - Both visualizations: Pass `current_cycle` and `max_cycles` to BO model

### Fixed

- **Missing BO Metadata in Database**: Fixed data pipeline bug where `acquisition_function` and `acquisition_params` were not being propagated from BO model to database
  - Root cause: Three missing field assignments in data flow
  - Fixed in: `callback.py` (line 1325), `subject_interface.py` (lines 451-452, 1104-1105)
  - Result: All BO cycles now correctly store acquisition metadata

- **Unbounded GP Confidence Intervals**: Clipped visualization bounds to hedonic scale [1, 9]
  - Actual GP predictions remain unbounded for scientific accuracy
  - Only visualization is clipped using `np.minimum()` and `np.maximum()`
  - Location: `moderator_interface.py` lines 1199-1200

### Documentation

- **New: `docs/ADAPTIVE_ACQUISITION.md`**:
  - Comprehensive guide to adaptive acquisition feature
  - Academic foundation and references
  - Configuration guidelines and parameter tuning
  - Implementation details and data flow
  - Analysis queries and troubleshooting
- **New: `docs/DATABASE_SCHEMA_V3.md`**:
  - Complete v3.0 schema documentation
  - Migration guide from v2.0
  - Example queries for research analysis
  - Data validation procedures
- **Updated: `CHANGELOG.md`** (this file):
  - Detailed changelog for v3.0 release

### Breaking Changes

⚠️ **Database Schema**: v3.0 requires fresh database or manual migration from v2.0
- Added 22 new columns across 2 tables
- Added 1 new view
- No automatic migration provided
- See `docs/DATABASE_SCHEMA_V3.md` for migration instructions

⚠️ **API Changes**:
- `suggest_next_sample()` now requires `current_cycle` and `max_cycles` parameters when adaptive mode is enabled
- Older code calling this function will still work (parameters are optional) but won't benefit from adaptive acquisition

### Performance

- Added index on `samples.acquisition_function` for faster BO cycle queries
- `bo_cycle_analysis` view optimized with proper joins and WHERE filtering
- No performance degradation from new features

### Testing

- All new features validated with comprehensive tests
- Database schema verified with validation test
- BO metadata storage tested for EI, UCB, and random exploration
- UI syntax checked and validated
- No regressions detected

### Security

- No security-related changes in this release

### Deprecated

- **Static exploration parameters** (ei_xi, ucb_kappa) are deprecated in favor of adaptive acquisition
  - Still supported for backward compatibility and research comparison
  - Users should migrate to adaptive mode for production studies

## [2.0.0] - Prior Release

(Previous changelog entries would go here)

---

## Release Notes Format

Each version follows this structure:
- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Now removed features
- **Fixed**: Bug fixes
- **Security**: Security-related changes

## Semantic Versioning

- **MAJOR** (X.0.0): Breaking changes, database migrations
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

Current version: **3.0.0**
