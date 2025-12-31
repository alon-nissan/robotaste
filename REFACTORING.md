# RoboTaste Architecture Refactoring v3.0

**Date**: December 31, 2025
**Branch**: `refactor/architecture-v1`
**Status**: ✅ Complete

## Overview

This document describes the comprehensive refactoring of the RoboTaste codebase from a flat, monolithic structure to a modular package architecture. The refactoring improves maintainability, testability, and code organization while preserving all functionality.

## Summary of Changes

### Files Created (2)
- `robotaste/config/bo_config.py` - Centralized Bayesian Optimization configuration
- `robotaste/core/bo_utils.py` - Database-coupled BO utility functions

### Files Modified (12)
- `robotaste/core/bo_engine.py` - Updated imports to use new config module
- `robotaste/core/bo_integration.py` - Updated BO utility imports
- `robotaste/config/questionnaire.py` - Fixed semantic bug in intensity questionnaire
- `robotaste/views/moderator.py` - Fixed 7 inline imports
- `robotaste/views/completion.py` - Fixed 1 inline import
- `robotaste/core/trials.py` - Fixed 1 inline import
- `robotaste/views/questionnaire.py` - Updated config imports
- `robotaste/views/subject.py` - Updated config imports
- `main_app.py` - Updated viewport utility imports
- `css_style.py` - Updated viewport utility imports
- `robotaste/core/state_helpers.py` - Import path updates
- `robotaste/data/database.py` - Import path updates

### Files Deleted (5)
- `callback.py` (51KB) - Replaced by `robotaste/core/calculations.py`
- `bayesian_optimizer.py` (58KB) - Split into `bo_config.py`, `bo_utils.py`, `bo_engine.py`
- `questionnaire_config.py` (19KB) - Replaced by `robotaste/config/questionnaire.py`
- `viewport_utils.py` (3.3KB) - Replaced by `robotaste/utils/viewport.py`
- `config.py` (21KB) - BO config moved to `robotaste/config/bo_config.py`

### Total Changes
- **10 import fixes** (including inline imports inside functions)
- **1 semantic bug fix** (questionnaire `higher_is_better` parameter)
- **~150KB of code** migrated and reorganized

---

## New Package Structure

```
robotaste/
├── config/                    # Configuration management
│   ├── bo_config.py          # Bayesian Optimization configuration
│   ├── questionnaire.py      # Questionnaire definitions
│   └── defaults.py           # Default ingredient configurations
│
├── core/                      # Core business logic
│   ├── bo_engine.py          # Pure BO algorithm (Gaussian Processes)
│   ├── bo_utils.py           # Database-coupled BO functions
│   ├── bo_integration.py     # BO suggestion API for sessions
│   ├── calculations.py       # Concentration mapping & mixture calculations
│   ├── trials.py             # Trial initialization & click tracking
│   ├── state_machine.py      # Experiment phase transitions
│   └── state_helpers.py      # State machine helper functions
│
├── data/                      # Data layer
│   ├── database.py           # SQLite database operations
│   └── session_repo.py       # Session repository pattern
│
├── views/                     # UI layer (Streamlit pages)
│   ├── landing.py            # Landing page
│   ├── moderator.py          # Moderator interface
│   ├── subject.py            # Subject interface
│   ├── questionnaire.py      # Questionnaire components
│   └── completion.py         # Completion page
│
├── utils/                     # Utility functions
│   ├── ui_helpers.py         # UI helper functions
│   └── viewport.py           # Viewport detection utilities
│
└── components/                # Reusable UI components
    ├── canvas.py             # 2D grid canvas component
    └── styles.py             # CSS styles
```

---

## Breaking Changes

### Import Path Changes

All imports must now use the `robotaste.*` namespace:

#### Before (Root-level imports):
```python
from callback import ConcentrationMapper, MultiComponentMixture
from bayesian_optimizer import train_bo_model_for_participant
from questionnaire_config import get_questionnaire_config
from viewport_utils import is_mobile_viewport
from config import DEFAULT_BO_CONFIG
```

#### After (Package imports):
```python
from robotaste.core.calculations import ConcentrationMapper, MultiComponentMixture
from robotaste.core.bo_utils import train_bo_model_for_participant
from robotaste.config.questionnaire import get_questionnaire_config
from robotaste.utils.viewport import is_mobile_viewport
from robotaste.config.bo_config import DEFAULT_BO_CONFIG
```

### Configuration Changes

Bayesian Optimization configuration is now centralized in `robotaste/config/bo_config.py`:

```python
from robotaste.config.bo_config import (
    get_default_bo_config,
    validate_bo_config,
    get_bo_config_from_experiment,
    DEFAULT_BO_CONFIG,
)
```

---

## Key Improvements

### 1. Separation of Concerns

**Before**: `bayesian_optimizer.py` (58KB) contained:
- BO configuration constants
- Pure algorithm code (GP training, acquisition functions)
- Database-coupled functions (get_bo_status, check_convergence)

**After**: Split into 3 focused modules:
- `robotaste/config/bo_config.py` - Configuration management
- `robotaste/core/bo_engine.py` - Pure algorithm code
- `robotaste/core/bo_utils.py` - Database integration

**Benefits**:
- Easier testing (pure functions can be tested without DB)
- Better code organization
- Clearer dependencies

### 2. Centralized Configuration

All BO parameters now have a single source of truth:

```python
DEFAULT_BO_CONFIG = {
    "enabled": True,
    "min_samples_for_bo": 3,
    "acquisition_function": "ei",
    "adaptive_acquisition": True,
    "exploration_budget": 0.25,
    "kernel_nu": 2.5,
    "alpha": 1e-3,
    # ... complete configuration
}
```

**Benefits**:
- No duplicate configuration
- Validation in one place
- Easier to modify defaults

### 3. Fixed Semantic Bug

**Issue**: Intensity questionnaire had incorrect `higher_is_better: False`

**Fix**: Changed to `higher_is_better: True` in [robotaste/config/questionnaire.py:152](robotaste/config/questionnaire.py#L152)

**Impact**: BO now correctly optimizes to maximize intensity instead of minimize

### 4. Eliminated Inline Import Errors

**Issue**: 9 inline imports inside functions were using old root-level paths

**Fix**: Updated all inline imports to use `robotaste.*` paths

**Files affected**:
- [robotaste/views/moderator.py](robotaste/views/moderator.py) (7 fixes)
- [robotaste/views/completion.py:287](robotaste/views/completion.py#L287) (1 fix)
- [robotaste/core/trials.py:177](robotaste/core/trials.py#L177) (1 fix)

---

## Migration Guide for Developers

### If you have custom code importing RoboTaste modules:

1. **Update all imports** to use `robotaste.*` namespace
2. **Replace bayesian_optimizer imports**:
   - `train_bo_model_for_participant` → `robotaste.core.bo_utils`
   - `check_convergence` → `robotaste.core.bo_utils`
   - `get_bo_status` → `robotaste.core.bo_utils`
3. **Replace config imports**:
   - `DEFAULT_BO_CONFIG` → `robotaste.config.bo_config`
4. **Replace callback imports**:
   - All functions → `robotaste.core.calculations`

### If you modified BO configuration:

The BO configuration structure remains the same, but is now accessed via:

```python
from robotaste.config.bo_config import get_default_bo_config

config = get_default_bo_config()
config["acquisition_function"] = "ucb"  # Modify as needed
```

### If you added custom questionnaires:

Questionnaire definitions remain in the same format, but are now in:
- `robotaste/config/questionnaire.py`

---

## Testing Performed

### Import Verification
✅ All modules import successfully without `ModuleNotFoundError`
✅ No circular import dependencies
✅ All inline imports use correct paths

### Application Startup
✅ `streamlit run main_app.py` runs without errors
✅ All views load correctly
✅ Database connections work

### Functionality Testing
✅ Trial initialization works
✅ BO suggestions generated correctly
✅ Questionnaire rendering works
✅ State machine transitions correctly

---

## Rollback Plan

If issues are discovered after merge:

1. **Revert the merge commit**:
   ```bash
   git revert <merge-commit-hash>
   ```

2. **Or checkout previous version**:
   ```bash
   git checkout <previous-commit-hash>
   ```

3. **Legacy files are preserved in git history** and can be recovered if needed

---

## Performance Impact

**No performance degradation expected**:
- Same algorithm implementations
- Same database queries
- Only import paths changed

**Minor improvements**:
- Slightly faster startup (fewer redundant imports)
- Better memory usage (no duplicate configuration objects)

---

## Future Recommendations

### Short-term (Next 1-2 sprints)
1. Add unit tests for `robotaste/core/bo_engine.py` (pure functions)
2. Add integration tests for `robotaste/core/bo_utils.py` (DB-coupled)
3. Add docstring coverage for public APIs

### Long-term (Next quarter)
1. Consider migrating to `pyproject.toml` for package management
2. Add type hints to all public functions
3. Create API documentation with Sphinx
4. Consider splitting large files:
   - `robotaste/views/moderator.py` (96KB) could be split into sub-modules
   - `robotaste/data/database.py` could separate schema from queries

---

## Credits

**Refactoring completed by**: Claude Sonnet 4.5
**Reviewed by**: Alon Nissan
**Version**: 3.0 (Refactored Architecture)
**Date**: December 31, 2025

---

## Appendix: Detailed File Changes

### robotaste/config/bo_config.py (NEW)

**Purpose**: Centralized Bayesian Optimization configuration

**Key exports**:
- `DEFAULT_BO_CONFIG` - Default configuration dictionary
- `get_default_bo_config()` - Get configuration copy
- `validate_bo_config(config)` - Validate and sanitize config
- `get_bo_config_from_experiment(experiment_config)` - Extract BO config from experiment

**Lines**: 213

### robotaste/core/bo_utils.py (NEW)

**Purpose**: Database-coupled BO utility functions

**Key exports**:
- `train_bo_model_for_participant(participant_id, session_id, bo_config)` - Train GP model from DB
- `get_bo_status(session_id)` - Get BO status for display
- `get_convergence_metrics(session_id)` - Analyze convergence
- `check_convergence(session_id, stopping_criteria)` - Multi-criteria convergence check

**Lines**: 677

### robotaste/core/bo_engine.py (MODIFIED)

**Changes**:
- Line 174: `from config import` → `from robotaste.config.bo_config import`
- Line 552: Same import fix in `train_bo_model()` function

**Impact**: Fixed import errors when config.py was deleted

### robotaste/config/questionnaire.py (MODIFIED)

**Changes**:
- Line 152: `higher_is_better: False` → `higher_is_better: True`

**Impact**: Fixed semantic bug - BO now correctly maximizes intensity

### robotaste/views/moderator.py (MODIFIED)

**Changes**: 7 inline import fixes

**Lines affected**:
- 563-567: `from questionnaire_config import` → `from robotaste.config.questionnaire import`
- 842: Same fix
- 1207: `from bayesian_optimizer import` → `from robotaste.core.bo_utils import`
- 1208: questionnaire_config fix
- 1485-1487: bayesian_optimizer fixes
- 1832: bayesian_optimizer fix

**Impact**: Fixed runtime `ModuleNotFoundError` when functions executed

### robotaste/views/completion.py (MODIFIED)

**Changes**:
- Line 287: `from bayesian_optimizer import` → `from robotaste.core.bo_utils import`

**Impact**: Fixed convergence check import

### robotaste/core/trials.py (MODIFIED)

**Changes**:
- Line 177: `from questionnaire_config import` → `from robotaste.config.questionnaire import`

**Impact**: Fixed questionnaire type lookup

---

## Questions?

For questions about this refactoring, please contact the development team or review the git history for detailed commit messages.
