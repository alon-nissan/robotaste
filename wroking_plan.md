# Developer A Implementation Plan: RoboTaste Protocol System (Weeks 3-10)

## Executive Summary

Implement a comprehensive protocol management system for RoboTaste that enables:
- **Mixed-mode sample selection** (user, BO, predetermined)
- **Custom phase sequences** with auto-advance and skipping
- **Protocol library** with CRUD operations
- **Session-protocol integration** for reusable experiment designs

**Assumption:** Clean slate - no database migration needed, existing schema supports all requirements.

---

## WEEK 3-4: Mixed-Mode Sample Selection Foundation

### Objective
Enable three sample selection modes controlled by protocol configuration.

### Implementation Tasks

#### 1. Sample Selection Runtime Logic
**File:** `robotaste/core/trials.py`

**Add Functions:**
```python
def get_selection_mode_for_cycle(session_id: str, cycle_number: int) -> str:
    """
    Determine selection mode for current cycle.
    Returns: "user_selected", "bo_selected", or "predetermined"

    Logic:
    1. Load session from database
    2. If session has protocol_id, load protocol JSON
    3. Parse sample_selection_schedule from protocol
    4. Find matching cycle_range for current cycle
    5. Return mode (fallback to "user_selected" if no protocol)
    """

def prepare_cycle_sample(session_id: str, cycle_number: int) -> Dict[str, Any]:
    """
    Unified function to prepare sample for any cycle.

    Returns:
        {
            "mode": str,
            "concentrations": Dict[str, float] | None,
            "metadata": {
                "is_predetermined": bool,
                "allows_override": bool,
                "show_suggestion": bool
            }
        }

    Handles all three modes:
    - predetermined: Return fixed concentrations from protocol
    - bo_selected: Call get_bo_suggestion_for_session()
    - user_selected: Return None (user chooses)
    """
```

**Integration Points:**
- Import from `robotaste.config.protocol_schema`
- Call from subject interface during SELECTION phase

#### 2. BO Mode Enhancements
**File:** `robotaste/core/bo_integration.py`

**Modify `get_bo_suggestion_for_session()`:**
- Add mode metadata to response
- Track if suggestion is from protocol-driven BO mode
- Include `allows_override` flag from protocol config

**Add Function:**
```python
def should_use_bo_for_cycle(session_id: str, cycle_number: int) -> bool:
    """Check if current cycle should use BO mode per protocol."""
```

#### 3. Database Updates
**File:** `robotaste/data/database.py`

**Modify `save_sample_cycle()`:**
```python
def save_sample_cycle(
    # ... existing params ...
    selection_mode: str = "user_selected",
    was_bo_overridden: bool = False
) -> str:
```

**Add Query:**
```python
def get_sessions_by_protocol(protocol_id: str) -> List[Dict]:
    """Get all sessions using a specific protocol."""
```

### API Contract for Developer B

**Protocol JSON Schema - Sample Selection:**
```json
{
  "sample_selection_schedule": [
    {
      "cycle_range": {"start": 1, "end": 3},
      "mode": "predetermined",
      "predetermined_samples": [
        {"cycle": 1, "concentrations": {"Sugar": 10.0, "Salt": 2.0}}
      ]
    },
    {
      "cycle_range": {"start": 4, "end": 10},
      "mode": "bo_selected",
      "config": {
        "allow_override": true,
        "show_bo_suggestion": true
      }
    }
  ]
}
```

**Function for Developer B:**
```python
from robotaste.core.trials import prepare_cycle_sample

cycle_data = prepare_cycle_sample(session_id, cycle_number)
# Use cycle_data["mode"] to render appropriate UI
```

### Deliverables
- [x] `get_selection_mode_for_cycle()` function
- [x] `prepare_cycle_sample()` function
- [x] Modified `save_sample_cycle()` with mode tracking
- [x] Unit tests for all three modes
- [x] Sample test protocol JSON

### Testing
- Unit: Test mode determination for various protocol schedules
- Integration: Full cycle execution with all three modes
- Edge cases: Missing protocol, invalid cycle ranges

---

## WEEK 5-6: Custom Phase Engine

### Objective
Build phase engine for custom phase sequences, skipping, and auto-advance.

### Implementation Tasks

#### 1. Phase Engine Core
**File:** `robotaste/core/phase_engine.py` (NEW)

**Create Classes:**
```python
@dataclass
class PhaseDefinition:
    """Single phase configuration."""
    phase_id: str
    phase_type: str  # "builtin", "custom", "loop"
    required: bool = True
    duration_ms: Optional[int] = None
    auto_advance: bool = False
    content: Optional[Dict[str, Any]] = None

class PhaseEngine:
    """Manages dynamic phase sequences from protocols."""

    def __init__(self, protocol: Dict[str, Any], session_id: str):
        self.protocol = protocol
        self.session_id = session_id
        self.phase_sequence = self._parse_phase_sequence()

    def get_next_phase(self, current_phase: ExperimentPhase,
                      skip_optional: bool = False) -> ExperimentPhase:
        """Determine next phase based on protocol sequence."""

    def should_auto_advance(self, current_phase: ExperimentPhase) -> Tuple[bool, int]:
        """Check if phase should auto-advance."""

    def can_skip_phase(self, phase: ExperimentPhase) -> bool:
        """Check if phase is optional per protocol."""
```

**Default Phase Sequence:**
```python
DEFAULT_PHASES = [
    {"phase_id": "waiting", "phase_type": "builtin", "required": True},
    {"phase_id": "registration", "phase_type": "builtin", "required": False},
    {"phase_id": "instructions", "phase_type": "builtin", "required": True},
    {"phase_id": "experiment_loop", "phase_type": "loop", "required": True},
    {"phase_id": "completion", "phase_type": "builtin", "required": True}
]
```

#### 2. State Machine Integration
**File:** `robotaste/core/state_machine.py`

**Add Method:**
```python
@staticmethod
def get_next_phase_with_protocol(
    current_phase: ExperimentPhase,
    protocol: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> ExperimentPhase:
    """
    Get next phase considering protocol.
    Uses PhaseEngine if protocol exists, otherwise VALID_TRANSITIONS.
    """
```

**Maintain backward compatibility:** Keep existing `get_allowed_transitions()` unchanged.

#### 3. Session Creation Integration
**File:** `robotaste/data/database.py`

**Modify `create_session()`:**
```python
def create_session(
    moderator_name: str,
    protocol_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Create session with optional protocol.
    Store protocol_id as FK, initialize phase engine state in experiment_config.
    """
```

### API Contract for Developer B

**Protocol JSON Schema - Phase Sequence:**
```json
{
  "phase_sequence": {
    "phases": [
      {
        "phase_id": "custom_intro",
        "phase_type": "custom",
        "required": true,
        "duration_ms": 5000,
        "auto_advance": true,
        "content": {
          "type": "text",
          "title": "Welcome!",
          "body": "Custom introduction..."
        }
      },
      {
        "phase_id": "experiment_loop",
        "phase_type": "loop",
        "required": true
      }
    ]
  }
}
```

**Functions for Developer B:**
```python
from robotaste.core.phase_engine import PhaseEngine

engine = PhaseEngine(protocol, session_id)
next_phase = engine.get_next_phase(current_phase)
should_advance, duration = engine.should_auto_advance(current_phase)
```

### Deliverables
- [x] `PhaseEngine` class with full API
- [x] State machine integration
- [x] Session creation with protocol support
- [x] Phase sequence validation
- [x] Unit tests for phase transitions

### Testing
- Unit: Phase sequence parsing, skip logic, auto-advance
- Integration: Full session with custom phases
- Edge cases: Circular loops, invalid phase IDs

---

## WEEK 7-8: Protocol Management & Integration

### Objective
Complete protocol CRUD operations, validation, and session integration.

### Implementation Tasks

#### 1. Protocol Validation Enhancement
**File:** `robotaste/config/protocols.py`

**Add Validations:**
```python
def _validate_phase_sequence(protocol: Dict[str, Any]) -> List[str]:
    """
    Validate phase sequence.
    - All referenced phases exist
    - No circular dependencies
    - Valid transition paths
    """

def validate_protocol_compatibility(
    protocol: Dict[str, Any],
    existing_session_id: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """Check if protocol can be used with session."""
```

#### 2. Protocol Import/Export Enhancement
**File:** `robotaste/config/protocols.py`

**Add Functions:**
```python
def increment_protocol_version(protocol: Dict[str, Any]) -> Dict[str, Any]:
    """Create new version (1.0 → 1.1), recompute hash."""

def compare_protocols(protocol_v1: Dict, protocol_v2: Dict) -> Dict[str, Any]:
    """Compare two protocol versions, return differences."""

def export_protocol_to_clipboard(protocol: Dict[str, Any]) -> str:
    """Generate shareable JSON string."""
```

#### 3. Session-Protocol Integration
**File:** `robotaste/core/trials.py`

**Modify `start_trial()`:**
```python
def start_trial(
    # ... existing params ...
    protocol_id: Optional[str] = None
) -> bool:
    """
    Initialize trial with optional protocol.
    If protocol_id provided:
    1. Load and validate protocol
    2. Override manual config with protocol settings
    3. Initialize phase engine
    4. Store protocol_id in session
    """
```

**Add Functions:**
```python
def load_protocol_for_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Load protocol for active session."""

def initialize_protocol_driven_session(session_id: str, protocol_id: str) -> bool:
    """Initialize all protocol-driven systems."""
```

#### 4. Database Repository Fixes
**File:** `robotaste/data/protocol_repo.py`

**Fix Connection:**
```python
def get_db_connection():
    """Use actual database connection from database.py."""
    from robotaste.data.database import get_database_connection
    return get_database_connection()
```

**Add Queries:**
```python
def link_session_to_protocol(session_id: str, protocol_id: str) -> bool:
    """Update sessions.protocol_id FK."""

def get_protocol_usage_stats(protocol_id: str) -> Dict[str, Any]:
    """Get statistics on protocol usage."""
```

### API Contract for Developer B

**Protocol CRUD Operations:**
```python
from robotaste.data.protocol_repo import (
    create_protocol_in_db,
    get_protocol_by_id,
    list_protocols,
    update_protocol,
    delete_protocol,
    archive_protocol,
    search_protocols_by_ingredients,
    get_all_tags
)

# Usage:
protocols = list_protocols(search="sugar")
protocol = get_protocol_by_id("proto_123")
success = create_protocol_in_db(new_protocol)
```

**Session Startup:**
```python
from robotaste.core.trials import start_trial

start_trial(
    user_type="mod",
    participant_id="P001",
    method="logarithmic",
    protocol_id="proto_123"  # Overrides manual config
)
```

### Deliverables
- [x] Enhanced protocol validation (phase sequence, compatibility)
- [x] Protocol versioning functions
- [x] Session-protocol integration in `start_trial()`
- [x] Fixed database connection in `protocol_repo.py`
- [x] Protocol usage statistics

### Testing
- Unit: Validation with all error cases, versioning logic
- Integration: Protocol CRUD → Session creation → Execution
- Stress: Large protocols (6 ingredients, 100 cycles)

---

## WEEK 9-10: Testing, Optimization & Documentation

### Objective
Finalize system with comprehensive testing, performance optimization, and documentation.

### Implementation Tasks

#### 1. Integration Testing Suite
**File:** `tests/test_protocol_integration.py` (NEW)

**Test Scenarios:**
```python
def test_protocol_full_lifecycle():
    """End-to-end: Create → Save → Load → Execute → Validate"""

def test_protocol_phase_sequence():
    """Custom phases, auto-advance, skipping"""

def test_mixed_mode_transitions():
    """Predetermined → User → BO mode transitions"""

def test_invalid_protocol_handling():
    """All validation error paths"""

def test_performance():
    """Protocol load < 100ms, mode lookup < 50ms"""
```

#### 2. Performance Optimization
**File:** `robotaste/core/protocol_helpers.py` (NEW)

**Add Caching:**
```python
from functools import lru_cache

@lru_cache(maxsize=32)
def get_protocol_by_id_cached(protocol_id: str) -> Optional[Dict]:
    """Cached protocol lookup."""

def get_protocol_metadata_only(protocol_id: str) -> Dict:
    """Load only name, version (not full JSON)."""
```

**Lazy Loading:**
```python
class PhaseEngine:
    @property
    def phase_sequence(self):
        """Lazy load phase sequence on first access."""
```

#### 3. API Documentation
**Files:**
- `docs/protocol_schema.md` (NEW)
- `docs/developer_a_api.md` (NEW)

**Protocol Schema Reference:**
- Required fields
- Sample selection schedule format
- Phase sequence format
- Examples for each mode

**API Reference:**
- `prepare_cycle_sample()` usage
- `PhaseEngine` methods
- `validate_protocol()` error handling
- Code examples

#### 4. Code Refactoring
**File:** `robotaste/core/protocol_helpers.py` (NEW)

**Centralize Common Logic:**
```python
def get_protocol_for_session(session_id: str) -> Optional[Dict]:
    """Centralized protocol loading for sessions."""

class ProtocolError(Exception):
    """Base protocol exception."""
    pass

class ProtocolNotFoundError(ProtocolError):
    pass

class ProtocolValidationError(ProtocolError):
    pass
```

**Add Type Hints:**
- Comprehensive type annotations for all new functions
- Docstrings with examples

#### 5. Logging Strategy

**Add Throughout:**
```python
import logging
logger = logging.getLogger(__name__)

# Examples:
logger.info(f"Loaded protocol '{protocol['name']}' for session {session_id}")
logger.debug(f"Cycle {cycle_number} using mode: {mode}")
logger.warning(f"Protocol {protocol_id} not found, using manual config")
logger.error(f"Protocol validation failed: {errors}")
```

### Deliverables
- [x] Comprehensive integration test suite
- [x] Performance optimizations (caching, lazy loading)
- [x] Complete API documentation
- [x] Refactored code with type hints
- [x] Logging throughout system

### Testing
- Integration: Full workflows with Developer B's UI
- Performance: 100+ protocols, concurrent sessions
- Backward compatibility: Sessions without protocols work

---

## Critical Files Summary

### Files to Create
1. `robotaste/core/phase_engine.py` - Phase management system
2. `robotaste/core/protocol_helpers.py` - Shared utilities
3. `tests/test_protocol_integration.py` - Integration tests
4. `docs/protocol_schema.md` - Protocol reference
5. `docs/developer_a_api.md` - API documentation

### Files to Modify
1. `robotaste/core/trials.py` - Add sample selection logic, protocol loading
2. `robotaste/core/bo_integration.py` - Add mode metadata
3. `robotaste/core/state_machine.py` - Add protocol-aware transitions
4. `robotaste/data/database.py` - Update `save_sample_cycle()`, `create_session()`
5. `robotaste/data/protocol_repo.py` - Fix DB connection, add queries
6. `robotaste/config/protocols.py` - Enhance validation, add versioning

---

## Developer B Coordination Points

### Week 3-4
- **Provide:** `prepare_cycle_sample()` API signature
- **Receive:** UI mockups for each mode
- **Integrate:** Sample test protocol JSON for UI testing

### Week 5-6
- **Provide:** `PhaseEngine` API and test protocol
- **Receive:** Custom phase rendering components
- **Integrate:** Auto-advance timing behavior

### Week 7-8
- **Provide:** Protocol CRUD API from `protocol_repo.py`
- **Receive:** Protocol editor UI validation feedback
- **Integrate:** Session creation with protocol selection

### Week 9-10
- **Joint:** Integration testing, performance profiling
- **Provide:** Test utilities, mock protocols
- **Receive:** UI test scenarios

---

## MVP Priorities

### Must-Have (Weeks 3-6)
1. Mixed-mode sample selection (3 modes)
2. Protocol JSON schema with validation
3. Phase skipping (registration optional)
4. Selection mode tracking in database
5. Basic protocol CRUD

### Should-Have (Weeks 7-8)
6. Protocol import/export files
7. Session-protocol linking
8. Custom phase engine with auto-advance
9. Protocol versioning

### Nice-to-Have (Weeks 9-10)
10. Protocol analytics/usage stats
11. Performance optimizations (caching)
12. Protocol comparison utilities

---

## Risk Mitigation

### Technical Risks
1. **Protocol JSON schema evolution**
   - Mitigation: Version field, compatibility warnings
   - Fallback: Schema migration utilities

2. **Phase engine complexity**
   - Mitigation: Start with builtin phases, iterate
   - Fallback: Default sequence if protocol missing

3. **Performance with large protocols**
   - Mitigation: Lazy loading, caching
   - Fallback: Protocol size limits (100 cycles max)

### Coordination Risks
1. **API contract misalignment**
   - Mitigation: Weekly API review, shared test protocols
   - Fallback: Version endpoints, backward compatibility

2. **Concurrent development conflicts**
   - Mitigation: Clear module boundaries
   - Fallback: Feature flags

---

## Success Criteria

### Week 3-4
- [x] All three selection modes working
- [x] Database correctly tracks selection_mode
- [x] Test protocol executes successfully

### Week 5-6
- [x] PhaseEngine handles custom sequences
- [x] Phase skipping works
- [x] Auto-advance functional

### Week 7-8
- [x] Protocol CRUD complete
- [x] Session-protocol integration working
- [x] Validation catches all error cases

### Week 9-10
- [x] All integration tests pass
- [x] Performance targets met (<100ms protocol load)
- [x] Documentation complete

---

# DEVELOPER B PROMPT

## Project Overview

You're working on **RoboTaste**, a Streamlit-based taste testing application for adaptive sensory experiments. Your role is to build the UI layer for a new protocol management system that allows researchers to create reusable experiment templates.

## Technology Stack

### Frontend Framework
- **Streamlit** (v1.49.1+) - Python-based web framework
- **streamlit-drawable-canvas** - 2D grid interface for sample selection
- **Plotly** - Interactive visualizations
- **HTML/CSS** - Custom styling via `st.markdown()`

### Architecture Pattern
- **Modular views**: Each page is a separate module in `robotaste/views/`
- **Session state**: Use `st.session_state` for UI state
- **Database sync**: Call `sync_session_state_to_streamlit()` for multi-device coordination
- **Pure components**: Views import from `robotaste/core/` (business logic) and `robotaste/data/` (database)

### Existing Components
- **Canvas drawing** (`robotaste/components/canvas.py`) - 2D selection grid
- **Styling system** (`robotaste/components/styles.py`) - CSS injection, card layouts
- **UI helpers** (`robotaste/utils/ui_helpers.py`) - Common UI patterns
- **Viewport detection** (`robotaste/utils/viewport.py`) - Responsive layouts

## Codebase Architecture Context

### Current File Structure
```
robotaste/
├── core/                    # Business logic (NO Streamlit imports)
│   ├── state_machine.py    # 8-phase experiment workflow
│   ├── trials.py           # Trial management (Developer A will add protocol functions here)
│   ├── bo_integration.py   # Bayesian Optimization integration
│   └── phase_engine.py     # NEW: Custom phase sequences (Developer A creates)
├── data/                    # Database layer
│   ├── database.py         # SQLite operations
│   ├── session_repo.py     # Session management
│   └── protocol_repo.py    # NEW: Protocol CRUD (Developer A enhances)
├── config/                  # Configuration
│   ├── defaults.py         # Ingredient/questionnaire defaults
│   ├── protocols.py        # NEW: Protocol validation (Developer A creates)
│   └── protocol_schema.py  # NEW: Protocol schema definitions
├── views/                   # Streamlit UI (YOUR WORK)
│   ├── landing.py          # Session join/create
│   ├── moderator.py        # Experiment setup & monitoring
│   ├── subject.py          # Subject interface (YOU WILL MODIFY)
│   ├── questionnaire.py    # Questionnaire rendering
│   └── protocol_manager.py # NEW: Protocol management UI (YOU WILL CREATE)
└── components/             # Reusable UI components
    ├── canvas.py           # 2D drawing canvas
    └── styles.py           # CSS styling
```

### Database Schema (Relevant Tables)

**sessions**
- `session_id` (TEXT PK) - UUID
- `session_code` (TEXT UNIQUE) - 6-char user code
- `protocol_id` (TEXT FK) - References protocol_library.protocol_id
- `current_phase` (TEXT) - Current experiment phase
- `current_cycle` (INT) - Current cycle number
- `experiment_config` (JSON) - Full experiment configuration

**protocol_library**
- `protocol_id` (TEXT PK) - UUID
- `name` (TEXT) - Protocol name
- `description` (TEXT) - Protocol description
- `protocol_json` (JSON) - Full protocol configuration
- `version` (TEXT) - Semantic version (e.g., "1.0")
- `protocol_hash` (TEXT) - SHA256 hash for versioning
- `tags` (JSON) - Array of tags
- `is_archived` (BOOLEAN) - Soft delete flag

**samples**
- `sample_id` (TEXT PK)
- `session_id` (TEXT FK)
- `cycle_number` (INT) - 1-indexed
- `ingredient_concentration` (JSON) - `{"Sugar": 42.0, "Salt": 6.0}`
- `selection_mode` (TEXT) - "user_selected", "bo_selected", "predetermined"
- `was_bo_overridden` (BOOLEAN) - True if user overrode BO suggestion

### State Machine (8 Phases)
1. **WAITING** - Session created, awaiting start
2. **REGISTRATION** - Subject enters personal info
3. **INSTRUCTIONS** - Subject reads instructions
4. **ROBOT_PREPARING** - (Placeholder for hardware)
5. **LOADING** - Preparation screen (5s spinner)
6. **QUESTIONNAIRE** - Subject rates sample
7. **SELECTION** - Subject selects next sample
8. **COMPLETE** - Session finished

---

## Your Tasks (Weeks 3-10)

### WEEK 3-4: Mixed-Mode Sample Selection UI

#### Task 1: Sample Sequence Builder UI
**File:** `robotaste/views/sample_sequence_builder.py` (NEW)

**Purpose:** Visual editor for defining sample selection schedule in protocols.

**UI Components:**

1. **Timeline Visualization**
   - Horizontal timeline showing cycles 1-N
   - Color-coded segments for each mode:
     - Blue: User selected
     - Green: BO selected
     - Orange: Predetermined
   - Interactive range selector (drag to define cycle_range)

2. **Mode Selector**
   - Dropdown per cycle range: ["User Selected", "BO Selected", "Predetermined"]
   - Conditional UI based on selection:
     - **Predetermined**: Show sample grid picker + manual entry
     - **BO Selected**: Show BO config options (allow_override, show_suggestion)
     - **User Selected**: No additional config

3. **Predetermined Sample Grid**
   - 2D grid interface (reuse `robotaste/components/canvas.py` pattern)
   - Click to select predetermined sample position
   - Show concentration labels
   - Manual concentration entry form as alternative

4. **CSV Import (Optional Nice-to-Have)**
   - Upload CSV with columns: cycle, ingredient1_mM, ingredient2_mM, ...
   - Parse and populate predetermined_samples array
   - Validation: Check concentration ranges

**Return Value:**
```python
def render_sample_sequence_builder() -> Dict[str, Any]:
    """
    Returns:
        {
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 3},
                    "mode": "predetermined",
                    "predetermined_samples": [...]
                }
            ]
        }
    """
```

**Example Code Structure:**
```python
import streamlit as st
from robotaste.config.defaults import DEFAULT_INGREDIENT_CONFIG

def render_sample_sequence_builder(num_cycles: int = 10, ingredients: list = None):
    """Visual sample sequence builder."""

    st.subheader("Sample Selection Schedule")

    # Timeline visualization
    st.write("Define which mode to use for each cycle range:")

    # Initialize state
    if 'schedule_segments' not in st.session_state:
        st.session_state.schedule_segments = [
            {"start": 1, "end": num_cycles, "mode": "user_selected"}
        ]

    # Render each segment
    for idx, segment in enumerate(st.session_state.schedule_segments):
        with st.expander(f"Cycles {segment['start']}-{segment['end']}: {segment['mode']}"):
            col1, col2, col3 = st.columns(3)

            with col1:
                segment['start'] = st.number_input("Start Cycle", value=segment['start'], key=f"start_{idx}")

            with col2:
                segment['end'] = st.number_input("End Cycle", value=segment['end'], key=f"end_{idx}")

            with col3:
                segment['mode'] = st.selectbox(
                    "Mode",
                    ["user_selected", "bo_selected", "predetermined"],
                    index=["user_selected", "bo_selected", "predetermined"].index(segment['mode']),
                    key=f"mode_{idx}"
                )

            # Conditional UI based on mode
            if segment['mode'] == "predetermined":
                render_predetermined_sample_picker(segment, ingredients)
            elif segment['mode'] == "bo_selected":
                render_bo_config_options(segment)

    # Add/remove segments
    if st.button("+ Add Cycle Range"):
        st.session_state.schedule_segments.append({
            "start": num_cycles + 1,
            "end": num_cycles + 5,
            "mode": "user_selected"
        })

    return {"sample_selection_schedule": st.session_state.schedule_segments}
```

#### Task 2: Subject Interface Updates
**File:** `robotaste/views/subject.py` (MODIFY)

**Purpose:** Adapt subject UI based on selection mode for current cycle.

**UI Changes:**

1. **Progress Indicator** (Predetermined Mode)
   ```python
   # Show "Sample 3 of 10" when mode = predetermined
   if selection_mode == "predetermined":
       st.info(f"Sample {current_cycle} of {total_predetermined_cycles}")
   ```

2. **Hide Grid/Sliders** (Predetermined Mode)
   ```python
   # Don't show selection interface if predetermined
   if selection_mode == "predetermined":
       st.success("Sample has been predetermined by protocol")
       st.write(f"Concentrations: {predetermined_concentrations}")
       if st.button("Continue to Tasting"):
           # Advance to next phase
   else:
       # Show normal grid/slider interface
       render_selection_interface()
   ```

3. **Highlight BO Suggestion** (BO Mode)
   ```python
   # When mode = bo_selected
   if selection_mode == "bo_selected":
       st.info("🤖 Bayesian Optimization Suggestion:")

       col1, col2 = st.columns([2, 1])

       with col1:
           # Show suggestion on grid with highlight
           render_grid_with_highlight(bo_suggestion_coords)

       with col2:
           st.metric("Predicted Liking", f"{bo_prediction:.2f}")
           st.metric("Uncertainty", f"±{bo_uncertainty:.2f}")

       # Buttons
       col_a, col_b = st.columns(2)
       with col_a:
           if st.button("✓ Confirm BO Suggestion", type="primary"):
               save_sample_with_mode(bo_suggestion, mode="bo_selected", overridden=False)

       with col_b:
           if st.button("✏️ Override & Choose My Own"):
               st.session_state.override_bo = True
               # Show normal selection interface

       if st.session_state.get('override_bo', False):
           st.warning("Choose your preferred sample:")
           render_selection_interface()
   ```

4. **Integration with Developer A's API**
   ```python
   from robotaste.core.trials import prepare_cycle_sample

   # At start of SELECTION phase
   cycle_data = prepare_cycle_sample(session_id, current_cycle)

   selection_mode = cycle_data["mode"]
   concentrations = cycle_data.get("concentrations")  # None for user_selected
   metadata = cycle_data["metadata"]

   # Render based on mode
   if selection_mode == "predetermined":
       render_predetermined_ui(concentrations)
   elif selection_mode == "bo_selected":
       render_bo_suggestion_ui(concentrations, metadata)
   else:
       render_manual_selection_ui()
   ```

**Testing Approach:**
```python
# Create mock protocol with mixed modes
test_protocol = {
    "sample_selection_schedule": [
        {"cycle_range": {"start": 1, "end": 2}, "mode": "predetermined", ...},
        {"cycle_range": {"start": 3, "end": 5}, "mode": "bo_selected", ...}
    ]
}

# Test UI with each mode
for cycle in range(1, 6):
    cycle_data = prepare_cycle_sample(session_id, cycle)
    assert cycle_data["mode"] in ["predetermined", "bo_selected"]
```

### Coordination (Week 3-4)
- **Week 3 Mid:** Receive `prepare_cycle_sample()` API signature from Developer A
- **Week 4 Start:** Test UI with Developer A's sample protocol JSON
- **Week 4 End:** Joint integration test of full cycle execution

---

### WEEK 5-6: Custom Phase Renderers & Phase Builder UI

#### Task 1: Custom Phase Renderers
**File:** `robotaste/views/custom_phases.py` (NEW)

**Purpose:** Render custom phase types defined in protocols.

**Phase Types to Support:**

1. **Text Phase**
   ```python
   def render_custom_text_phase(content: Dict[str, Any]) -> None:
       """
       Display custom text/instructions.

       content = {
           "type": "text",
           "title": "Welcome!",
           "body": "Custom introduction...",
           "image_url": "https://..." (optional)
       }
       """
       st.title(content["title"])
       st.markdown(content["body"])

       if "image_url" in content:
           st.image(content["image_url"])

       if st.button("Continue"):
           # Signal phase completion
           st.session_state.phase_complete = True
   ```

2. **Media Phase**
   ```python
   def render_custom_media_phase(content: Dict[str, Any]) -> None:
       """
       Display image or video.

       content = {
           "type": "media",
           "media_type": "image" | "video",
           "media_url": "https://...",
           "caption": "..." (optional)
       }
       """
       if content["media_type"] == "image":
           st.image(content["media_url"], caption=content.get("caption"))
       elif content["media_type"] == "video":
           st.video(content["media_url"])

       if st.button("Next"):
           st.session_state.phase_complete = True
   ```

3. **Break Phase**
   ```python
   def render_break_phase(content: Dict[str, Any]) -> None:
       """
       Timed break screen.

       content = {
           "type": "break",
           "duration_seconds": 30,
           "message": "Please wait 30 seconds..."
       }
       """
       st.info(content["message"])

       # Countdown timer
       duration = content["duration_seconds"]
       if 'break_start_time' not in st.session_state:
           st.session_state.break_start_time = time.time()

       elapsed = time.time() - st.session_state.break_start_time
       remaining = max(0, duration - elapsed)

       progress = st.progress(elapsed / duration)
       st.metric("Time Remaining", f"{int(remaining)}s")

       if remaining == 0:
           st.success("Break complete!")
           st.session_state.phase_complete = True
           st.rerun()
       else:
           time.sleep(1)
           st.rerun()
   ```

4. **Custom Survey Phase**
   ```python
   def render_custom_survey_phase(content: Dict[str, Any]) -> None:
       """
       Additional survey questions.

       content = {
           "type": "survey",
           "questions": [
               {"id": "q1", "text": "...", "type": "slider", "min": 1, "max": 9}
           ]
       }
       """
       responses = {}

       for q in content["questions"]:
           if q["type"] == "slider":
               responses[q["id"]] = st.slider(q["text"], q["min"], q["max"])
           elif q["type"] == "text":
               responses[q["id"]] = st.text_input(q["text"])

       if st.button("Submit"):
           # Save responses to database
           save_custom_survey_responses(st.session_state.session_id, responses)
           st.session_state.phase_complete = True
   ```

**Main Router Function:**
```python
def render_custom_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """Route to appropriate renderer based on content type."""

    phase_type = content.get("type")

    if phase_type == "text":
        render_custom_text_phase(content)
    elif phase_type == "media":
        render_custom_media_phase(content)
    elif phase_type == "break":
        render_break_phase(content)
    elif phase_type == "survey":
        render_custom_survey_phase(content)
    else:
        st.error(f"Unknown phase type: {phase_type}")
```

#### Task 2: Phase Sequence Builder UI
**File:** `robotaste/views/phase_builder.py` (NEW)

**Purpose:** Visual editor for custom phase sequences.

**UI Components:**

1. **Drag-and-Drop Phase Editor**
   ```python
   # Use st.columns for reordering (Streamlit doesn't have native drag-drop)
   # Alternative: Show numbered list with up/down buttons

   for idx, phase in enumerate(st.session_state.phase_sequence):
       with st.expander(f"{idx+1}. {phase['phase_id']}"):
           col1, col2, col3 = st.columns([3, 1, 1])

           with col1:
               st.write(f"Type: {phase['phase_type']}")

           with col2:
               if idx > 0 and st.button("⬆️", key=f"up_{idx}"):
                   # Swap with previous
                   st.session_state.phase_sequence[idx], st.session_state.phase_sequence[idx-1] = \
                       st.session_state.phase_sequence[idx-1], st.session_state.phase_sequence[idx]
                   st.rerun()

           with col3:
               if idx < len(st.session_state.phase_sequence)-1 and st.button("⬇️", key=f"down_{idx}"):
                   # Swap with next
                   st.session_state.phase_sequence[idx], st.session_state.phase_sequence[idx+1] = \
                       st.session_state.phase_sequence[idx+1], st.session_state.phase_sequence[idx]
                   st.rerun()

           # Phase configuration form
           render_phase_config_form(phase, idx)
   ```

2. **Phase Type Selector**
   ```python
   st.subheader("Add Phase")

   phase_type = st.selectbox("Phase Type", [
       "builtin (registration, instructions, etc.)",
       "custom (text, media, break, survey)",
       "loop (experiment cycles)"
   ])

   if phase_type == "builtin":
       phase_id = st.selectbox("Select Phase", [
           "waiting", "registration", "instructions", "completion"
       ])
       required = st.checkbox("Required", value=True)

   elif phase_type == "custom":
       custom_type = st.selectbox("Custom Type", ["text", "media", "break", "survey"])
       # Show type-specific form
       if custom_type == "text":
           title = st.text_input("Title")
           body = st.text_area("Body")
           content = {"type": "text", "title": title, "body": body}
   ```

3. **Phase Configuration Forms**
   - Required toggle
   - Auto-advance toggle + duration input
   - Content editor (type-specific)

4. **Preview**
   ```python
   st.subheader("Preview Phase Sequence")

   for idx, phase in enumerate(st.session_state.phase_sequence):
       st.write(f"{idx+1}. {phase['phase_id']} ({phase['phase_type']})")
       if phase.get('required'):
           st.caption("   ⚠️ Required")
       if phase.get('auto_advance'):
           st.caption(f"   ⏱️ Auto-advance after {phase['duration_ms']}ms")
   ```

#### Task 3: Subject Interface Integration
**File:** `robotaste/views/subject.py` (MODIFY)

**Purpose:** Use PhaseEngine API to render current phase.

```python
from robotaste.core.phase_engine import PhaseEngine
from robotaste.views.custom_phases import render_custom_phase

# Load protocol and initialize phase engine
protocol = load_protocol_for_session(session_id)
if protocol:
    phase_engine = PhaseEngine(protocol, session_id)

    # Get current phase
    current_phase = st.session_state.current_phase

    # Check if it's a custom phase
    phase_content = phase_engine.get_phase_content(current_phase)
    if phase_content:
        # Render custom phase
        render_custom_phase(current_phase.value, phase_content)

        # Check auto-advance
        should_advance, duration_ms = phase_engine.should_auto_advance(current_phase)
        if should_advance and st.session_state.get('phase_complete'):
            # Auto-transition after duration
            time.sleep(duration_ms / 1000)
            next_phase = phase_engine.get_next_phase(current_phase)
            update_current_phase(session_id, next_phase)
            st.rerun()
    else:
        # Render builtin phase (existing logic)
        render_builtin_phase(current_phase)
```

### Coordination (Week 5-6)
- **Week 5 Mid:** Receive phase configuration schema from Developer A
- **Week 5 End:** Demo custom phase rendering with test protocol
- **Week 6 Mid:** Test auto-advance behavior
- **Week 6 End:** Integration test full custom phase sequence

---

### WEEK 7-8: Protocol Management UI

#### Task 1: Protocol Library Manager
**File:** `robotaste/views/protocol_manager.py` (ENHANCE)

**Purpose:** Browse, search, and manage protocol library.

**UI Components:**

1. **Protocol Browser**
   ```python
   from robotaste.data.protocol_repo import list_protocols, get_all_tags

   st.title("Protocol Library")

   # Search & filters
   col1, col2, col3 = st.columns([3, 2, 2])

   with col1:
       search_query = st.text_input("🔍 Search protocols", placeholder="Search by name...")

   with col2:
       all_tags = get_all_tags()
       selected_tags = st.multiselect("Filter by tags", all_tags)

   with col3:
       show_archived = st.checkbox("Show archived")

   # Fetch protocols
   protocols = list_protocols(
       search=search_query,
       tags=selected_tags,
       include_archived=show_archived
   )

   # Display as cards
   for protocol in protocols:
       with st.expander(f"{protocol['name']} (v{protocol['version']})"):
           st.write(protocol['description'])

           col_a, col_b, col_c, col_d = st.columns(4)

           with col_a:
               if st.button("✏️ Edit", key=f"edit_{protocol['protocol_id']}"):
                   st.session_state.editing_protocol = protocol['protocol_id']
                   st.rerun()

           with col_b:
               if st.button("📋 Duplicate", key=f"dup_{protocol['protocol_id']}"):
                   duplicate_protocol(protocol['protocol_id'])
                   st.rerun()

           with col_c:
               if st.button("💾 Export", key=f"exp_{protocol['protocol_id']}"):
                   export_protocol_to_file(protocol['protocol_id'], f"{protocol['name']}.json")
                   st.success("Exported!")

           with col_d:
               if st.button("🗑️ Delete", key=f"del_{protocol['protocol_id']}"):
                   if st.session_state.get(f"confirm_delete_{protocol['protocol_id']}"):
                       delete_protocol(protocol['protocol_id'])
                       st.rerun()
                   else:
                       st.session_state[f"confirm_delete_{protocol['protocol_id']}"] = True
                       st.warning("Click again to confirm deletion")
   ```

2. **Protocol Actions**
   - **Edit**: Open protocol editor
   - **Duplicate**: Create copy with new ID, increment version
   - **Export**: Download as JSON file
   - **Delete**: Soft delete (set `is_archived=True`)
   - **Archive**: Toggle `is_archived` flag

3. **Protocol Preview**
   ```python
   st.subheader("Preview")
   st.json(protocol['protocol_json'])

   # Summary stats
   st.metric("Ingredients", len(protocol['protocol_json']['ingredients']))
   st.metric("Total Cycles", protocol['protocol_json'].get('num_cycles', 'N/A'))
   st.metric("Uses BO", "Yes" if protocol['protocol_json'].get('bo_config', {}).get('enabled') else "No")
   ```

#### Task 2: Protocol Editor (Complete)
**File:** `robotaste/views/protocol_manager.py` (ENHANCE)

**Purpose:** Multi-tab protocol editor.

**Tab Structure:**

```python
st.title("Protocol Editor")

tabs = st.tabs([
    "1️⃣ Basic Settings",
    "2️⃣ Sample Selection",
    "3️⃣ Phase Sequence",
    "4️⃣ Questionnaire & BO",
    "5️⃣ Advanced Options"
])

with tabs[0]:
    render_basic_settings_tab()

with tabs[1]:
    # Use sample_sequence_builder component
    from robotaste.views.sample_sequence_builder import render_sample_sequence_builder
    schedule = render_sample_sequence_builder()
    st.session_state.protocol['sample_selection_schedule'] = schedule

with tabs[2]:
    # Use phase_builder component
    from robotaste.views.phase_builder import render_phase_builder
    phase_sequence = render_phase_builder()
    st.session_state.protocol['phase_sequence'] = phase_sequence

with tabs[3]:
    render_questionnaire_bo_tab()

with tabs[4]:
    render_advanced_options_tab()

# Save/Cancel buttons (sticky footer)
col_save, col_cancel = st.columns(2)

with col_save:
    if st.button("💾 Save Protocol", type="primary"):
        # Validate
        from robotaste.config.protocols import validate_protocol
        is_valid, errors = validate_protocol(st.session_state.protocol)

        if is_valid:
            create_protocol_in_db(st.session_state.protocol)
            st.success("Protocol saved!")
        else:
            st.error("Validation errors:")
            for error in errors:
                st.error(f"  • {error}")

with col_cancel:
    if st.button("❌ Cancel"):
        st.session_state.pop('editing_protocol', None)
        st.rerun()
```

**Tab 1: Basic Settings**
```python
def render_basic_settings_tab():
    protocol = st.session_state.protocol

    protocol['name'] = st.text_input("Protocol Name", value=protocol.get('name', ''))
    protocol['description'] = st.text_area("Description", value=protocol.get('description', ''))

    # Tags
    current_tags = protocol.get('tags', [])
    protocol['tags'] = st.multiselect(
        "Tags",
        options=get_all_tags() + ["research", "pilot", "validation"],  # Suggestions
        default=current_tags
    )

    # Ingredient selection
    from robotaste.config.defaults import DEFAULT_INGREDIENT_CONFIG

    available_ingredients = list(DEFAULT_INGREDIENT_CONFIG.keys())
    selected = st.multiselect(
        "Ingredients",
        available_ingredients,
        default=protocol.get('ingredients', [])[:2]  # Default 2
    )

    protocol['ingredients'] = []
    for ing in selected:
        config = DEFAULT_INGREDIENT_CONFIG[ing]
        with st.expander(f"{ing} Configuration"):
            min_conc = st.number_input(f"Min Concentration (mM)", value=config['min_concentration'])
            max_conc = st.number_input(f"Max Concentration (mM)", value=config['max_concentration'])

            protocol['ingredients'].append({
                "name": ing,
                "min_concentration": min_conc,
                "max_concentration": max_conc
            })
```

**Tab 4: Questionnaire & BO**
```python
def render_questionnaire_bo_tab():
    protocol = st.session_state.protocol

    # Questionnaire selection
    from robotaste.config.questionnaire import list_available_questionnaires

    questionnaire_types = list_available_questionnaires()
    protocol['questionnaire_type'] = st.selectbox(
        "Questionnaire Type",
        questionnaire_types,
        index=questionnaire_types.index(protocol.get('questionnaire_type', 'hedonic_continuous'))
    )

    # BO Configuration
    st.subheader("Bayesian Optimization")

    bo_enabled = st.checkbox("Enable BO", value=protocol.get('bo_config', {}).get('enabled', False))

    if bo_enabled:
        protocol['bo_config'] = protocol.get('bo_config', {})
        protocol['bo_config']['enabled'] = True

        protocol['bo_config']['min_samples_for_bo'] = st.number_input(
            "Min samples before BO",
            min_value=1,
            value=protocol['bo_config'].get('min_samples_for_bo', 3)
        )

        protocol['bo_config']['acquisition_function'] = st.selectbox(
            "Acquisition Function",
            ["ei", "ucb"],
            index=["ei", "ucb"].index(protocol['bo_config'].get('acquisition_function', 'ei'))
        )
```

#### Task 3: Moderator Interface Integration
**File:** `robotaste/views/moderator.py` (MODIFY)

**Purpose:** Add protocol selection before session creation.

**UI Flow:**

```python
st.title("Moderator Dashboard")

# Phase 1: Protocol Setup (BEFORE session creation)
if 'session_id' not in st.session_state:
    st.header("Step 1: Protocol Setup")

    protocol_option = st.radio(
        "Choose protocol option:",
        ["Use saved protocol", "Create new protocol", "Manual configuration (no protocol)"]
    )

    if protocol_option == "Use saved protocol":
        protocols = list_protocols()

        selected_protocol_id = st.selectbox(
            "Select Protocol",
            options=[p['protocol_id'] for p in protocols],
            format_func=lambda pid: next(p['name'] for p in protocols if p['protocol_id'] == pid)
        )

        if selected_protocol_id:
            protocol = get_protocol_by_id(selected_protocol_id)

            # Display protocol summary
            st.subheader("Protocol Summary")
            st.json(protocol)

            if st.button("Start Session with This Protocol", type="primary"):
                # Create session with protocol_id
                session_id, session_code = create_session(
                    moderator_name=st.session_state.moderator_name,
                    protocol_id=selected_protocol_id
                )
                st.session_state.session_id = session_id
                st.session_state.session_code = session_code
                st.rerun()

    elif protocol_option == "Create new protocol":
        # Open protocol editor
        st.info("Opening protocol editor...")
        # Redirect to protocol_manager page
        st.session_state.creating_new_protocol = True
        # Show inline editor or link to protocol manager

    else:  # Manual configuration
        # Existing manual setup UI
        render_manual_session_setup()

# Phase 2: Session monitoring (AFTER session created)
else:
    st.header("Step 2: Session Monitoring")
    # Existing monitoring UI
    render_session_monitoring()
```

### Coordination (Week 7-8)
- **Week 7 Start:** Receive protocol CRUD API from Developer A
- **Week 7 Mid:** Test protocol validation in editor UI
- **Week 8 Start:** Test session creation from protocol
- **Week 8 End:** Full integration test: Create protocol → Start session → Execute

---

### WEEK 9-10: Testing, Refinement & Documentation

#### Task 1: UI Testing & Refinement

**Test Scenarios:**

1. **Protocol Creation Workflow**
   - Create new protocol from scratch
   - Configure all tabs
   - Save and verify in database
   - Load and edit existing protocol

2. **UI Component Testing**
   - Test with real protocols from Developer A
   - Test all three selection modes in subject interface
   - Test custom phase rendering
   - Test protocol browser with 20+ protocols

3. **User Experience Testing**
   - Measure time to create protocol
   - Test with non-technical users
   - Identify confusing UI elements
   - Gather feedback on phase builder

4. **Error Handling**
   - Invalid protocol data (trigger validation errors)
   - Missing protocol (session with deleted protocol)
   - Network errors (slow database)
   - Edge cases (0 cycles, 6 ingredients)

#### Task 2: UI Polish

**Polish Tasks:**

1. **Consistent Styling**
   - Use `robotaste/components/styles.py` for all custom CSS
   - Consistent button colors (primary = green, danger = red)
   - Consistent spacing (use `st.columns` for alignment)
   - Card-based layouts for protocol list

2. **Responsive Layout**
   - Test on mobile viewport (use `robotaste/utils/viewport.py`)
   - Adjust column widths for narrow screens
   - Ensure grid interface works on tablets

3. **Accessibility**
   - High contrast mode support
   - Keyboard navigation
   - Screen reader labels (use `label` params)
   - Focus indicators on buttons

4. **Loading States**
   ```python
   with st.spinner("Loading protocols..."):
       protocols = list_protocols()

   if st.button("Save"):
       with st.spinner("Saving protocol..."):
           create_protocol_in_db(protocol)
       st.success("Saved!")
   ```

5. **Help Text & Tooltips**
   ```python
   st.text_input(
       "Protocol Name",
       help="Choose a descriptive name for this experiment protocol"
   )

   st.info("ℹ️ Predetermined mode: Subjects taste pre-specified samples in order")
   ```

#### Task 3: User Documentation

**Create Documentation:**

1. **Protocol Creation Guide** (`docs/ui_user_guide.md`)
   - Step-by-step walkthrough with screenshots
   - How to use sample sequence builder
   - How to configure custom phases
   - Common protocol templates

2. **Sample Selection Modes Explanation**
   - When to use each mode
   - Differences between modes
   - Best practices

3. **Custom Phases Tutorial**
   - Available phase types
   - How to configure each type
   - Example phase sequences

4. **Example Protocol Walkthroughs**
   - "Simple 2-ingredient experiment"
   - "BO-driven adaptive study"
   - "Mixed-mode with predetermined intro"

5. **Screenshot Documentation**
   - Annotated screenshots of each UI screen
   - Common workflows visualized

### Coordination (Week 9-10)
- **Week 9 Start:** Joint integration testing with Developer A
- **Week 9 Mid:** Performance profiling (page load times)
- **Week 10 Start:** Documentation review
- **Week 10 End:** Production readiness checklist

---

## API Reference (Developer A → Developer B)

### Core Functions You'll Call

#### 1. Sample Selection
```python
from robotaste.core.trials import prepare_cycle_sample

cycle_data = prepare_cycle_sample(session_id: str, cycle_number: int)
# Returns:
# {
#     "mode": "user_selected" | "bo_selected" | "predetermined",
#     "concentrations": {"Sugar": 42.0, ...} | None,
#     "metadata": {"is_predetermined": bool, "allows_override": bool}
# }
```

#### 2. Phase Management
```python
from robotaste.core.phase_engine import PhaseEngine

engine = PhaseEngine(protocol: Dict, session_id: str)
next_phase = engine.get_next_phase(current_phase: ExperimentPhase)
should_advance, duration_ms = engine.should_auto_advance(current_phase)
can_skip = engine.can_skip_phase(phase: ExperimentPhase)
```

#### 3. Protocol CRUD
```python
from robotaste.data.protocol_repo import (
    create_protocol_in_db,
    get_protocol_by_id,
    list_protocols,
    update_protocol,
    delete_protocol,
    archive_protocol,
    search_protocols_by_ingredients,
    get_all_tags
)

# Examples:
protocols = list_protocols(search="sugar", tags=["research"])
protocol = get_protocol_by_id("proto_123")
success = create_protocol_in_db(new_protocol)
```

#### 4. Protocol Validation
```python
from robotaste.config.protocols import validate_protocol

is_valid, errors = validate_protocol(protocol: Dict)
# Returns: (bool, List[str])

# Display errors in UI:
if not is_valid:
    for error in errors:
        st.error(f"❌ {error}")
```

#### 5. Session Management
```python
from robotaste.data.database import create_session

session_id, session_code = create_session(
    moderator_name: str,
    protocol_id: Optional[str] = None
)
```

---

## Protocol JSON Schema Reference

### Complete Example
```json
{
  "protocol_id": "proto_abc123",
  "name": "Sugar-Salt BO Study",
  "description": "Adaptive optimization of sugar-salt preference",
  "version": "1.0",
  "tags": ["research", "bo", "2-ingredient"],

  "ingredients": [
    {
      "name": "Sugar",
      "min_concentration": 0.73,
      "max_concentration": 73.0,
      "unit": "mM"
    },
    {
      "name": "Salt",
      "min_concentration": 0.10,
      "max_concentration": 10.0,
      "unit": "mM"
    }
  ],

  "sample_selection_schedule": [
    {
      "cycle_range": {"start": 1, "end": 2},
      "mode": "predetermined",
      "predetermined_samples": [
        {
          "cycle": 1,
          "concentrations": {"Sugar": 10.0, "Salt": 2.0}
        },
        {
          "cycle": 2,
          "concentrations": {"Sugar": 50.0, "Salt": 8.0}
        }
      ]
    },
    {
      "cycle_range": {"start": 3, "end": 10},
      "mode": "bo_selected",
      "config": {
        "show_bo_suggestion": true,
        "allow_override": true,
        "auto_accept_suggestion": false
      }
    }
  ],

  "phase_sequence": {
    "phases": [
      {
        "phase_id": "waiting",
        "phase_type": "builtin",
        "required": true
      },
      {
        "phase_id": "registration",
        "phase_type": "builtin",
        "required": false
      },
      {
        "phase_id": "custom_intro",
        "phase_type": "custom",
        "required": true,
        "duration_ms": 5000,
        "auto_advance": true,
        "content": {
          "type": "text",
          "title": "Welcome to the Study!",
          "body": "You will taste 10 samples and rate them."
        }
      },
      {
        "phase_id": "experiment_loop",
        "phase_type": "loop",
        "required": true,
        "loop_config": {
          "phases": ["loading", "questionnaire", "selection"]
        }
      },
      {
        "phase_id": "completion",
        "phase_type": "builtin",
        "required": true
      }
    ]
  },

  "questionnaire_type": "hedonic_continuous",

  "bo_config": {
    "enabled": true,
    "min_samples_for_bo": 3,
    "acquisition_function": "ei"
  },

  "stopping_criteria": {
    "max_cycles": 10,
    "convergence_enabled": false
  }
}
```

---

## Development Guidelines

### Streamlit Best Practices

1. **Session State Management**
   ```python
   # Initialize state
   if 'key' not in st.session_state:
       st.session_state.key = default_value

   # Update state
   st.session_state.key = new_value

   # Force re-render
   st.rerun()
   ```

2. **Widget Keys**
   - Always use unique `key` parameter for widgets in loops
   - Format: `f"{widget_type}_{unique_id}_{index}"`

3. **Database Sync**
   ```python
   from robotaste.data.session_repo import sync_session_state_to_streamlit

   # Before critical operations
   sync_session_state_to_streamlit(session_id)
   ```

4. **Error Handling**
   ```python
   try:
       result = database_operation()
   except Exception as e:
       st.error(f"Error: {str(e)}")
       logger.error(f"Database error: {e}", exc_info=True)
   ```

### Code Organization

1. **Component Reusability**
   - Extract reusable UI components into `robotaste/components/`
   - Use functions that return data (not just render)

2. **View Structure**
   ```python
   # Top of file: Imports
   import streamlit as st
   from robotaste.core import ...
   from robotaste.data import ...

   # Helper functions
   def render_component():
       ...

   # Main function
   def render_page():
       st.title("Page Title")
       # Page logic

   # Entry point
   if __name__ == "__main__":
       render_page()
   ```

3. **Styling**
   ```python
   from robotaste.components.styles import inject_custom_css

   inject_custom_css()

   # Or inline:
   st.markdown("""
       <style>
       .custom-class { color: blue; }
       </style>
   """, unsafe_allow_html=True)
   ```

---

## Testing Strategies

### Manual Testing Checklist

**Week 3-4:**
- [ ] Sample sequence builder: Create schedule with 3 modes
- [ ] Subject interface: Test predetermined mode (hides grid)
- [ ] Subject interface: Test BO mode (shows suggestion + override)
- [ ] Subject interface: Test user mode (normal grid/sliders)
- [ ] Database: Verify selection_mode saved correctly

**Week 5-6:**
- [ ] Phase builder: Create custom text phase
- [ ] Phase builder: Create timed break phase
- [ ] Custom renderer: Test auto-advance
- [ ] Subject interface: Navigate through custom phase sequence

**Week 7-8:**
- [ ] Protocol browser: Search and filter
- [ ] Protocol editor: Save new protocol
- [ ] Protocol editor: Edit existing protocol
- [ ] Moderator: Create session from protocol
- [ ] Protocol validation: Trigger validation errors

**Week 9-10:**
- [ ] End-to-end: Protocol creation → session → execution → completion
- [ ] Performance: Protocol list loads < 1s with 50 protocols
- [ ] UI polish: All buttons have consistent styling
- [ ] Documentation: User can follow guide to create protocol

### Automated Testing (Optional)

```python
# tests/test_ui_components.py
import pytest
from robotaste.views.sample_sequence_builder import render_sample_sequence_builder

def test_sample_sequence_builder():
    """Test sample sequence builder returns correct structure."""
    # Mock st.session_state
    # Call render_sample_sequence_builder()
    # Assert output structure matches schema
```

---

## Success Criteria

### Week 3-4
- [ ] Sample sequence builder UI functional
- [ ] Subject interface adapts to all 3 modes
- [ ] BO suggestion display with override button
- [ ] Integration test with Developer A's API passes

### Week 5-6
- [ ] Custom phase renderers work for 4 phase types
- [ ] Phase builder UI allows sequence editing
- [ ] Subject interface uses PhaseEngine API
- [ ] Auto-advance timing works correctly

### Week 7-8
- [ ] Protocol browser shows all protocols
- [ ] Protocol editor has all 5 tabs functional
- [ ] Moderator can create session from protocol
- [ ] Validation errors display in UI

### Week 9-10
- [ ] All UI tests pass
- [ ] Performance targets met (< 1s page loads)
- [ ] Documentation complete with screenshots
- [ ] Zero critical bugs in production

---

## Questions & Support

### During Implementation

**Weekly Check-ins with Developer A:**
- Monday: Review API progress, discuss blockers
- Wednesday: Integration testing session
- Friday: Demo new UI features

**Communication:**
- Use shared protocol JSON files for testing
- Document API issues in shared tracker
- Review each other's code for integration points

**When Stuck:**
1. Check existing codebase for similar patterns (e.g., `moderator.py` for multi-step UI)
2. Review Developer A's API documentation
3. Test with mock data first, then integrate with real API
4. Ask Developer A for sample protocol JSON if schema unclear

---

## Summary

You're building the **UI layer** for RoboTaste's protocol system:

**Week 3-4:** Sample selection UI (sequence builder + adaptive subject interface)
**Week 5-6:** Custom phase UI (renderers + builder + integration)
**Week 7-8:** Protocol management UI (browser + editor + moderator integration)
**Week 9-10:** Testing, polish, documentation

**Key Integration Points:**
- Use Developer A's APIs (`prepare_cycle_sample`, `PhaseEngine`, protocol CRUD)
- Build on existing Streamlit patterns in codebase
- Coordinate weekly for testing and demos

**Deliverables:**
- 4 new view files (`sample_sequence_builder.py`, `custom_phases.py`, `phase_builder.py`, enhanced `protocol_manager.py`)
- Modified `subject.py` and `moderator.py`
- User documentation with screenshots

Good luck! 🚀
