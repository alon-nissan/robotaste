# AGENTS.md

This file is guidance for agentic coding tools working in this repo.
Focus on correctness, hardware safety, and adherence to the experiment flow.

## Quick Orientation
- App entrypoint: `main_app.py` (Streamlit UI).
- Experiment page: `pages/experiment.py` (dynamic phase rendering - NEW).
- Pump daemon: `pump_control_service.py` (hardware-connected machine).
- State machine: `robotaste/core/state_machine.py`.
- Phase router: `robotaste/core/phase_router.py` (NEW - protocol-driven navigation).
- DB: `robotaste.db` (SQLite); schema in `robotaste/data/schema.sql`.
- Protocols: `robotaste/config/protocols.py` and `robotaste/config/protocol_schema.py`.

## Navigation Quick Reference

### By Task Type
| Task | Primary Files | Helper Files |
|------|--------------|--------------|
| Add protocol feature | `robotaste/config/protocols.py`, `robotaste/config/protocol_schema.py` | `robotaste/data/protocol_repo.py` |
| Modify phase flow | `robotaste/core/phase_router.py`, `robotaste/core/phase_engine.py` | `robotaste/views/phases/builtin/*.py` |
| Add new phase | `robotaste/views/phases/builtin/my_phase.py` (NEW) | `robotaste/core/phase_router.py` (register) |
| Change UI behavior | `robotaste/views/moderator.py` or phase renderer files | `robotaste/components/`, `robotaste/views/moderator_views.py` |
| Fix BO issues | `robotaste/core/bo_engine.py`, `robotaste/core/bo_integration.py` | `robotaste/core/bo_utils.py`, `robotaste/config/bo_config.py` |
| Pump problems | `robotaste/hardware/pump_controller.py`, `robotaste/core/pump_manager.py` | `robotaste/core/pump_integration.py`, `robotaste/utils/pump_db.py` |
| Database queries | `robotaste/data/database.py` (low-level SQL) | `robotaste/data/session_repo.py`, `robotaste/data/protocol_repo.py` |
| Questionnaire changes | `robotaste/views/phases/builtin/questionnaire.py` (NEW) | `robotaste/data/database.py` (save logic) |

### By Component
- **Entry points**: `main_app.py` (UI), `pages/experiment.py` (NEW - subject experiments), `pump_control_service.py` (daemon)
- **Phase system**: `robotaste/core/phase_router.py` (NEW - routing), `robotaste/views/phases/` (NEW - renderers)
- **State management**: `robotaste/core/state_machine.py` (validation), `robotaste/core/phase_engine.py` (sequencing)
- **Data layer**: `robotaste/data/database.py` (low-level SQL), `robotaste/data/session_repo.py` (business logic)
- **Hardware**: `robotaste/hardware/pump_controller.py` (serial), `robotaste/core/pump_manager.py` (caching)
- **Trials**: `robotaste/core/trials.py` (BO suggestions, sample tracking)
- **Views**: `robotaste/views/moderator.py` (moderator UI), `robotaste/views/subject.py` (DEPRECATED - use phases/)
- **Components**: `robotaste/components/` (reusable UI widgets)

## Build / Run Commands
- **App UI**: `streamlit run main_app.py`
- **Pump service**: `python pump_control_service.py --db-path robotaste.db --poll-interval 0.5`
- **Tests (all)**: `pytest`
- **Tests (single file)**: `pytest tests/test_protocol_integration.py`
- **Tests (single test)**: `pytest tests/test_protocol_integration.py::test_name`
- **Tests (by keyword)**: `pytest -k "protocol"`
- **Tests (verbose)**: `pytest -v` or `pytest -vv`
- **Hardware tests** (requires physical pump connection):
  - `python robotaste/hardware/test_pump_movement.py`
  - `python robotaste/hardware/test_dual_pump.py`
  - `python robotaste/hardware/test_burst_commands.py`

## Lint / Format
- No lint or formatter configured in-repo.
- Do not add new tooling without explicit request.
- Keep formatting consistent with surrounding code (see style notes below).

## Test Notes
- Integration tests use temporary SQLite DBs.
- Hardware tests must only run with physical pump connection.
- Avoid running pump tests in CI-like environments.

## Required Project Rules (from CLAUDE.md)
- Reuse pump connections via `robotaste/core/pump_manager.py` (init is slow).
- Pumps share one serial port; use `_serial_port_lock` to serialize init.
- UI/DB units are microliters; pump hardware uses milliliters.
- Convert volume: `volume_ml = volume_ul / 1000.0`.
- BO training data column order must match `experiment_config.ingredients`.
- Validate phase transitions via `ExperimentStateMachine.validate_transition()`.

## Workflow / State Machine
- Standard flow: WAITING -> REGISTRATION -> INSTRUCTIONS -> SELECTION -> LOADING -> QUESTIONNAIRE -> loop -> COMPLETE.
- Pump flow: WAITING -> REGISTRATION -> INSTRUCTIONS -> SELECTION -> ROBOT_PREPARING -> QUESTIONNAIRE -> loop -> COMPLETE.
- Protocols may override phase sequence; fall back to `VALID_TRANSITIONS`.

## Code Style Guidelines (Python)
### Imports
- Prefer standard-library imports first, then third-party, then local modules.
- Keep `pyserial`, `streamlit`, `pandas` as the allowed external deps; avoid adding new ones.
- Use explicit imports over wildcard imports.

### Formatting
- Keep lines readable (target ~88-100 chars unless file uses different style).
- Use blank lines to separate logical blocks and top-level sections.
- Use consistent docstrings (triple-quoted, sentence case) for public functions.
- Prefer f-strings for logging and formatting.

### Types
- Use type hints for public functions and important internal helpers.
- Favor `Optional[...]` and `Dict[str, Any]` where needed (matches current code).
- Keep enums for phases (`ExperimentPhase`) rather than raw strings.

### Naming
- Modules and functions: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Be explicit with domain terms: `phase`, `cycle`, `session_id`, `protocol_id`.

### Error Handling
- Validate phase transitions before updating `current_phase`.
- Prefer raising specific exceptions (e.g., `InvalidTransitionError`) with context.
- Log errors with context (session id, phase, protocol id) before failing.
- Fail fast for invalid protocol or DB state; avoid silent fallbacks unless documented.

### Logging
- Use module-level logger: `logger = logging.getLogger(__name__)`.
- Use `info` for state transitions and `warning` for recoverable fallbacks.
- Avoid logging sensitive participant data.

### Database
- Use existing data access helpers (`robotaste/data/*`) instead of raw SQL.
- Keep session state in the `sessions` table in sync with Streamlit state.
- Use the DB utilities for connection management rather than ad-hoc connections.

### Streamlit UI
- Use `st.session_state` as the source of truth for per-device state.
- Initialize state early in `main_app.py` before rendering views.
- Avoid circular imports; defer view imports when necessary.

### Hardware / Pump Integration
- Never create new pump instances per cycle; reuse cached manager instances.
- Serial init must be sequential to avoid port conflicts.
- When in doubt, treat pump commands as slow/unsafe operations.

## Project Conventions
- Protocols are JSON-like dicts; validation is in `robotaste/config/protocols.py`.
- `robotaste/core/phase_engine.py` handles protocol-defined phases.
- Tests live in `tests/` and should be small, isolated, and DB-clean.

## Documentation References
- `docs/PROJECT_CONTEXT.md` for architecture and flow details.
- `docs/protocol_schema.md` for protocol JSON requirements.
- `docs/protocol_user_guide.md` for protocol authoring.

## Common Patterns & Gotchas

### Database Access Pattern
- **Simple CRUD**: Use `robotaste/data/database.py` functions directly
- **Business logic**: Use `robotaste/data/session_repo.py` or `robotaste/data/protocol_repo.py`
- **Never**: Write raw SQL in views or core modules

### Pump Operations Workflow (7 steps)
1. Subject selects sample → `trials.save_click()`
2. DB: `samples` table INSERT with concentrations
3. Phase advances to ROBOT_PREPARING
4. Create operation: `pump_integration.create_pump_operation_for_cycle()`
5. DB: `pump_operations` table INSERT with recipe
6. Pump service polls and executes: `pump_control_service.dispense_sample()`
7. DB: `pump_operations` UPDATE status=completed

### State Synchronization Pattern
- **Database polling** every ~5 seconds (`sync_session_state_to_streamlit()`)
- **Source of truth**: `sessions.current_phase` in database
- **Streamlit state**: Local cache, refreshed from DB on each poll
- **Never**: Update only `st.session_state` without DB update

### BO Training Data Pattern
- **Column order**: Must match `experiment_config.ingredients` order exactly
- **Minimum samples**: Need ≥3 samples before BO can suggest
- **Convergence**: Check `bo_integration.check_convergence()` for stopping criteria
- **Storage**: `samples` table stores `concentrations_json` as JSON string

## What Not To Do
- Do not add dependencies or tooling without asking.
- Do not run hardware tests unless explicitly requested.
- Do not bypass phase validation or pump safety constraints.
- Do not remove existing user changes in unrelated files.

## If You Need More Context
- Read `CLAUDE.md` for repo-specific constraints and instructions.
- Search for similar implementations in `robotaste/core/` and `robotaste/views/`.

## Multipage Architecture (NEW - Jan 2026)

### Overview
RoboTaste now uses a modular phase system where each experiment phase is a separate renderer function. This replaces the monolithic `subject.py` approach.

### Phase Development

To add a new builtin phase:

1. **Create phase file**: `robotaste/views/phases/builtin/my_phase.py`

```python
import streamlit as st
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def render_my_phase(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render my custom phase.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    st.title("My Phase")
    
    # Get configuration from protocol
    config = protocol.get("my_phase_config", {})
    
    # Render UI
    st.write("Phase content here")
    
    # Handle completion
    if st.button("Continue"):
        # Save data if needed
        # ...
        
        # Mark phase complete (REQUIRED)
        st.session_state.phase_complete = True
        logger.info(f"Session {session_id}: My phase completed")
```

2. **Register in PhaseRouter**: Update `robotaste/core/phase_router.py`

```python
def _register_builtin_phases(self) -> None:
    from robotaste.views.phases.builtin.my_phase import render_my_phase
    
    self._builtin_renderers = {
        # ... existing phases ...
        "my_phase": render_my_phase,
    }
```

3. **Update protocol**: Add phase to protocol's `phase_sequence`

```json
{
  "phase_sequence": {
    "phases": [
      {"phase_id": "my_phase", "phase_type": "builtin"}
    ]
  }
}
```

### Phase Renderer Rules

✅ **DO:**
- Use signature: `def render_phase(session_id: str, protocol: Dict[str, Any]) -> None`
- Set `st.session_state.phase_complete = True` when phase is done
- Extract configuration from `protocol` dict
- Add logging for debugging
- Handle errors gracefully

❌ **DON'T:**
- Call `st.rerun()` directly (PhaseRouter handles navigation)
- Modify database phase directly (PhaseRouter does this)
- Create global state (use st.session_state)
- Hard-code values (use protocol configuration)

### Custom Phases

Custom phases are defined entirely in protocol JSON (no code changes needed):

```json
{
  "phase_id": "welcome_video",
  "phase_type": "custom",
  "content": {
    "type": "media",
    "title": "Welcome",
    "media_type": "video",
    "media_url": "https://example.com/intro.mp4"
  }
}
```

Supported types: `text`, `media`, `survey`, `break`

### Architecture Flow

```
User visits: /experiment?session=ABC&role=subject
    ↓
pages/experiment.py validates session
    ↓
PhaseRouter initializes with protocol
    ↓
PhaseRouter.render_phase(current_phase)
    ↓
Routes to appropriate renderer (builtin or custom)
    ↓
Renderer displays UI and sets phase_complete
    ↓
PhaseRouter navigation advances to next phase
```

### Key Files

- `pages/experiment.py` - Entry point for experiments
- `robotaste/core/phase_router.py` - Routing and navigation logic
- `robotaste/views/phases/builtin/*.py` - Builtin phase renderers
- `robotaste/views/phases/custom/custom_phase.py` - Custom phase rendering

### Migration Notes

- `robotaste/views/subject.py` is **DEPRECATED** - use phase renderers instead
- Subjects are automatically redirected to `pages/experiment.py`
- All existing protocols work without modification
- See `docs/MULTIPAGE_MIGRATION.md` for full details

