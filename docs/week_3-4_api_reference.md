# Week 3-4 API Reference: Mixed-Mode Sample Selection

## Overview

The mixed-mode sample selection system enables three different modes for sample selection within a single experiment:
- **user_selected**: Subject manually chooses the next sample
- **bo_selected**: Bayesian Optimization suggests the next sample
- **predetermined**: Protocol specifies exact sample concentrations

## Core Functions for Developer B

### 1. `prepare_cycle_sample(session_id, cycle_number)`

**Location:** `robotaste/core/trials.py`

**Purpose:** Main API to determine what to show in the UI for the current cycle.

**Usage:**
```python
from robotaste.core.trials import prepare_cycle_sample

cycle_data = prepare_cycle_sample(session_id, cycle_number)

# Returns:
# {
#     "mode": "user_selected" | "bo_selected" | "predetermined",
#     "concentrations": {"Sugar": 42.0, "Salt": 6.0} | None,
#     "metadata": {
#         "is_predetermined": bool,
#         "allows_override": bool,
#         "show_suggestion": bool,
#         "acquisition_function": str | None,
#         "acquisition_params": dict | None,
#         "predicted_value": float | None,
#         "uncertainty": float | None
#     }
# }
```

**UI Integration:**
```python
# At the start of SELECTION phase:
cycle_data = prepare_cycle_sample(session_id, current_cycle)

if cycle_data["mode"] == "predetermined":
    # Hide selection interface
    st.info("Sample predetermined by protocol")
    st.write(f"Concentrations: {cycle_data['concentrations']}")
    if st.button("Continue to Tasting"):
        # Advance to next phase

elif cycle_data["mode"] == "bo_selected":
    # Show BO suggestion with optional override
    st.info("🤖 Bayesian Optimization Suggestion:")
    st.write(f"Concentrations: {cycle_data['concentrations']}")
    st.metric("Predicted Liking", f"{cycle_data['metadata']['predicted_value']:.2f}")

    if cycle_data['metadata']['allows_override']:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✓ Confirm Suggestion"):
                # Use BO suggestion
                save_with_mode(cycle_data['concentrations'], "bo_selected", overridden=False)
        with col2:
            if st.button("✏️ Override"):
                # Show manual selection interface
                st.session_state.override_bo = True
    else:
        # Auto-accept BO suggestion
        save_with_mode(cycle_data['concentrations'], "bo_selected", overridden=False)

else:  # user_selected
    # Show normal selection interface (grid/sliders)
    render_selection_interface()
```

### 2. `save_sample_cycle()` - Updated Signature

**Location:** `robotaste/data/database.py`

**New Parameters:**
- `selection_mode: str = "user_selected"` - The mode used for this sample
- `was_bo_overridden: bool = False` - True if user overrode BO suggestion

**Usage:**
```python
from robotaste.data import database as sql

sample_id = sql.save_sample_cycle(
    session_id=session_id,
    cycle_number=cycle_number,
    ingredient_concentration={"Sugar": 42.0, "Salt": 6.0},
    selection_data=selection_trajectory,
    questionnaire_answer={"overall_liking": 7.5},
    is_final=False,
    selection_mode="bo_selected",  # NEW
    was_bo_overridden=False  # NEW
)
```

### 3. `should_use_bo_for_cycle(session_id, cycle_number)`

**Location:** `robotaste/core/bo_integration.py`

**Purpose:** Check if current cycle should use BO mode per protocol.

**Usage:**
```python
from robotaste.core.bo_integration import should_use_bo_for_cycle

if should_use_bo_for_cycle(session_id, current_cycle):
    # This cycle uses BO mode
    bo_suggestion = get_bo_suggestion_for_session(session_id, participant_id)
```

## Protocol JSON Schema

### Sample Selection Schedule

```json
{
  "sample_selection_schedule": [
    {
      "cycle_range": {"start": 1, "end": 2},
      "mode": "predetermined",
      "predetermined_samples": [
        {"cycle": 1, "concentrations": {"Sugar": 10.0, "Salt": 2.0}},
        {"cycle": 2, "concentrations": {"Sugar": 40.0, "Salt": 6.0}}
      ]
    },
    {
      "cycle_range": {"start": 3, "end": 5},
      "mode": "user_selected",
      "config": {
        "interface_type": "grid",
        "randomize_start": true
      }
    },
    {
      "cycle_range": {"start": 6, "end": 15},
      "mode": "bo_selected",
      "config": {
        "show_bo_suggestion": true,
        "allow_override": true,
        "auto_accept_suggestion": false
      }
    }
  ]
}
```

## Database Schema Updates

### samples table (already in schema)

```sql
CREATE TABLE samples (
    -- ... existing fields ...
    selection_mode TEXT DEFAULT 'user_selected',  -- "user_selected", "bo_selected", "predetermined"
    was_bo_overridden INTEGER DEFAULT 0,  -- 1 if user overrode BO suggestion
    -- ... existing fields ...
);
```

## Testing

### Test Protocol
Location: `tests/test_protocol_mixed_mode.json`

Use this protocol to test all three modes:
- Cycles 1-2: Predetermined (fixed concentrations)
- Cycles 3-5: User selected (manual choice)
- Cycles 6-15: BO selected (with override allowed)

### Unit Tests
Location: `tests/test_mixed_mode_selection.py`

Run tests:
```bash
cd /path/to/RoboTaste/Software
PYTHONPATH=. python tests/test_mixed_mode_selection.py
```

## Example Workflow

### 1. Create Session with Protocol
```python
from robotaste.data import database as sql

session_id, session_code = sql.create_session(
    moderator_name="Researcher",
    protocol_id="proto_test_mixed_001"
)
```

### 2. Subject Interface - Selection Phase
```python
# Get current cycle
current_cycle = sql.get_current_cycle(session_id)

# Prepare cycle sample
cycle_data = prepare_cycle_sample(session_id, current_cycle)

# Render based on mode
if cycle_data["mode"] == "predetermined":
    render_predetermined_ui(cycle_data["concentrations"])
elif cycle_data["mode"] == "bo_selected":
    render_bo_suggestion_ui(cycle_data)
else:
    render_manual_selection_ui()
```

### 3. Save Sample with Mode
```python
# After questionnaire completion
sql.save_sample_cycle(
    session_id=session_id,
    cycle_number=current_cycle,
    ingredient_concentration=tasted_concentrations,
    selection_data=selection_trajectory,
    questionnaire_answer=questionnaire_responses,
    is_final=False,
    selection_mode=cycle_data["mode"],
    was_bo_overridden=user_overrode_bo
)
```

## Helper Functions

### `get_selection_mode_for_cycle_runtime(session_id, cycle_number)`

**Location:** `robotaste/core/trials.py`

Internal function that loads the protocol and determines the mode. You should use `prepare_cycle_sample()` instead, which calls this and provides additional data.

### `get_sessions_by_protocol(protocol_id)`

**Location:** `robotaste/data/database.py`

**Purpose:** Get all sessions using a specific protocol.

**Usage:**
```python
from robotaste.data import database as sql

sessions = sql.get_sessions_by_protocol("proto_test_mixed_001")
# Returns list of session dictionaries
```

## Validation

All protocols are validated before use:
- Cycle ranges cannot overlap
- Predetermined mode requires `predetermined_samples` for all cycles in range
- BO mode requires valid `bayesian_optimization` config
- Valid modes: "user_selected", "bo_selected", "predetermined"

## Logging

All selection mode operations are logged:
```python
# Examples:
logger.info(f"Session {session_id}, cycle {cycle_number}: mode = bo_selected")
logger.info(f"Predetermined sample for cycle 1: {'Sugar': 10.0, 'Salt': 2.0}")
logger.info(f"BO suggestion for cycle 6: {'Sugar': 42.3, 'Salt': 6.7}")
logger.info(f"Saved sample {sample_id}, mode=bo_selected")
logger.info(f"User overrode BO suggestion")
```

## Error Handling

All functions gracefully fallback to `user_selected` mode on errors:
- Protocol not found → user_selected
- Protocol missing schedule → user_selected
- BO not ready → user_selected
- Any exception → user_selected

This ensures the experiment can always continue even if protocol data is missing or invalid.

## Next Steps (Week 5-6)

The next implementation phase will add:
- Custom phase sequences
- Phase auto-advance
- Phase skipping
- Custom phase renderers

See the plan file for details: `~/.claude/plans/jazzy-growing-flask.md`
