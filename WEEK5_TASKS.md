# Week 5 Task List: Custom Phase Engine Implementation

**Week:** 5 (of 10-week development timeline)
**Focus:** Custom Phase Engine and UI Components
**Estimated Effort:** 30-40 hours (1 developer, 1 week)
**Status:** Not Started

---

## Overview

Week 5 focuses on implementing the **Custom Phase Engine** system that was planned but not implemented in Weeks 5-6. This is the primary gap preventing full protocol functionality.

### What We're Building

**Phase Engine** allows protocols to define:
- Custom phase sequences (not just default 8 phases)
- Phase skipping (e.g., optional registration)
- Auto-advance with timers
- Custom phase content (intro screens, breaks, surveys)

### Current State
- ❌ No phase engine exists
- ❌ Sessions use hardcoded default phase sequence
- ❌ Cannot skip phases
- ❌ No auto-advance functionality

### End Goal
- ✅ PhaseEngine class manages custom sequences
- ✅ Protocols define phase_sequence in JSON
- ✅ UI builds phase sequences visually
- ✅ Custom phases render (text, media, break, survey)
- ✅ Auto-advance works with timers
- ✅ Phase skipping functional

---

## Task Breakdown

## Priority 1: Custom Phase Engine Implementation (Must Have)

### Task 1.1: Create Phase Engine Core ⭐ HIGH PRIORITY

**File:** `robotaste/core/phase_engine.py` (NEW)

**Estimated Time:** 4-6 hours

#### Deliverables

1. **PhaseDefinition Dataclass**
```python
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class PhaseDefinition:
    """Single phase configuration from protocol."""
    phase_id: str  # "waiting", "registration", "custom_intro", etc.
    phase_type: str  # "builtin", "custom", "loop"
    required: bool = True  # If False, can be skipped
    duration_ms: Optional[int] = None  # For auto-advance
    auto_advance: bool = False  # Auto-transition after duration_ms
    content: Optional[Dict[str, Any]] = None  # Custom phase content
```

2. **PhaseEngine Class**
```python
class PhaseEngine:
    """Manages dynamic phase sequences from protocols."""

    def __init__(self, protocol: Dict[str, Any], session_id: str):
        """Initialize with protocol and session ID."""
        self.protocol = protocol
        self.session_id = session_id
        self.phase_sequence: List[PhaseDefinition] = self._parse_phase_sequence()

    def _parse_phase_sequence(self) -> List[PhaseDefinition]:
        """Parse protocol's phase_sequence into PhaseDefinition objects."""
        # If no phase_sequence in protocol, use DEFAULT_PHASES
        # Otherwise, parse each phase dict into PhaseDefinition

    def get_next_phase(
        self,
        current_phase: ExperimentPhase,
        skip_optional: bool = False
    ) -> ExperimentPhase:
        """Determine next phase based on protocol sequence."""
        # Find current phase in sequence
        # Return next required phase (or next optional if skip_optional=False)

    def should_auto_advance(
        self,
        current_phase: ExperimentPhase
    ) -> Tuple[bool, int]:
        """Check if phase should auto-advance.

        Returns:
            (should_advance, duration_ms)
        """
        # Look up phase in sequence
        # Return (auto_advance flag, duration_ms)

    def can_skip_phase(self, phase: ExperimentPhase) -> bool:
        """Check if phase is optional per protocol."""
        # Look up phase in sequence
        # Return not required

    def get_phase_content(
        self,
        phase: ExperimentPhase
    ) -> Optional[Dict[str, Any]]:
        """Get custom content for phase, if any."""
        # Look up phase in sequence
        # Return content dict or None
```

3. **Default Phase Sequence Constant**
```python
DEFAULT_PHASES = [
    {"phase_id": "waiting", "phase_type": "builtin", "required": True},
    {"phase_id": "registration", "phase_type": "builtin", "required": False},
    {"phase_id": "instructions", "phase_type": "builtin", "required": True},
    {"phase_id": "experiment_loop", "phase_type": "loop", "required": True},
    {"phase_id": "completion", "phase_type": "builtin", "required": True}
]
```

#### Implementation Notes

- **Error Handling:** If protocol has invalid phase_sequence, fall back to DEFAULT_PHASES
- **Logging:** Log phase transitions for debugging
- **Validation:** Validate phase_ids against ExperimentPhase enum
- **Type Safety:** Use type hints throughout

#### Testing

Create `tests/test_phase_engine.py` with:
- Test parsing default phases
- Test parsing custom phases
- Test get_next_phase() logic
- Test should_auto_advance()
- Test can_skip_phase()

---

### Task 1.2: State Machine Integration ⭐ HIGH PRIORITY

**File:** `robotaste/core/state_machine.py` (MODIFY)

**Estimated Time:** 2-3 hours

#### Deliverables

Add method to `ExperimentStateMachine`:

```python
@staticmethod
def get_next_phase_with_protocol(
    current_phase: ExperimentPhase,
    protocol: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> ExperimentPhase:
    """Get next phase considering protocol.

    If protocol provided, uses PhaseEngine.
    Otherwise, uses VALID_TRANSITIONS (backward compatible).

    Args:
        current_phase: Current experiment phase
        protocol: Optional protocol dict
        session_id: Optional session ID

    Returns:
        Next ExperimentPhase
    """
    if protocol and 'phase_sequence' in protocol:
        engine = PhaseEngine(protocol, session_id or "")
        return engine.get_next_phase(current_phase)
    else:
        # Use existing VALID_TRANSITIONS logic
        allowed = ExperimentStateMachine.get_allowed_transitions(current_phase)
        if allowed:
            return allowed[0]  # Return first allowed transition
        return current_phase  # Stay in current phase
```

#### Implementation Notes

- **Backward Compatibility:** Must not break existing sessions without protocols
- **Import:** Add `from robotaste.core.phase_engine import PhaseEngine`
- **Existing Code:** Keep `get_allowed_transitions()` unchanged
- **Testing:** Test both protocol and non-protocol paths

#### Testing

- Test with protocol (uses PhaseEngine)
- Test without protocol (uses VALID_TRANSITIONS)
- Test phase skipping with protocol
- Test default transitions without protocol

---

### Task 1.3: Phase Sequence Validation ⭐ HIGH PRIORITY

**File:** `robotaste/config/protocols.py` (MODIFY)

**Estimated Time:** 2-3 hours

#### Deliverables

1. **Add Phase Sequence Validation Function**

```python
def _validate_phase_sequence(protocol: Dict[str, Any]) -> List[str]:
    """Validate phase sequence configuration.

    Checks:
    - All phase_ids are valid
    - No circular dependencies
    - At least one path from start to completion
    - Required phases are present
    - Duration_ms is positive if auto_advance=True

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    phase_sequence = protocol.get("phase_sequence", {}).get("phases", [])

    if not phase_sequence:
        return []  # No custom sequence, will use default

    # Validate each phase
    valid_phase_ids = {"waiting", "registration", "instructions",
                      "robot_preparing", "loading", "questionnaire",
                      "selection", "completion", "experiment_loop"}

    for idx, phase in enumerate(phase_sequence):
        phase_id = phase.get("phase_id")
        phase_type = phase.get("phase_type")

        # Check phase_id
        if not phase_id:
            errors.append(f"Phase {idx}: Missing phase_id")
        elif phase_type == "builtin" and phase_id not in valid_phase_ids:
            errors.append(f"Phase {idx}: Invalid builtin phase_id '{phase_id}'")

        # Check auto_advance
        if phase.get("auto_advance") and not phase.get("duration_ms"):
            errors.append(f"Phase {phase_id}: auto_advance=True requires duration_ms")

        if phase.get("duration_ms") and phase["duration_ms"] <= 0:
            errors.append(f"Phase {phase_id}: duration_ms must be positive")

    # Check for required phases
    phase_ids = [p.get("phase_id") for p in phase_sequence]
    if "completion" not in phase_ids:
        errors.append("Phase sequence must include 'completion' phase")

    # Check for circular dependencies (simple check)
    # More sophisticated cycle detection could be added

    return errors
```

2. **Integrate into validate_protocol()**

```python
def validate_protocol(protocol: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate protocol against schema and business rules."""
    all_errors = []

    # ... existing validation ...

    # Add phase sequence validation
    phase_errors = _validate_phase_sequence(protocol)
    all_errors.extend(phase_errors)

    # ... rest of validation ...

    return len(all_errors) == 0, all_errors
```

#### Implementation Notes

- **Optional Sequence:** If no phase_sequence in protocol, it's valid (uses default)
- **Custom Phase IDs:** Allow arbitrary phase_ids for custom phases
- **Builtin Validation:** Only validate builtin phase_ids against known set

#### Testing

- Test valid phase sequence (passes)
- Test missing required phases (fails)
- Test invalid phase_id for builtin (fails)
- Test auto_advance without duration (fails)
- Test circular dependencies (fails)
- Test no phase_sequence (passes - uses default)

---

## Priority 2: Custom Phase UI Components (Must Have)

### Task 2.1: Custom Phase Renderers ⭐ HIGH PRIORITY

**File:** `robotaste/views/custom_phases.py` (NEW)

**Estimated Time:** 4-5 hours

#### Deliverables

1. **Text Phase Renderer**
```python
def render_custom_text_phase(content: Dict[str, Any]) -> None:
    """Display custom text/instructions.

    content = {
        "type": "text",
        "title": "Welcome!",
        "body": "Custom introduction...",
        "image_url": "https://..." (optional)
    }
    """
    st.title(content.get("title", ""))
    st.markdown(content.get("body", ""))

    if "image_url" in content:
        st.image(content["image_url"])

    if st.button("Continue"):
        st.session_state.phase_complete = True
        st.rerun()
```

2. **Media Phase Renderer**
```python
def render_custom_media_phase(content: Dict[str, Any]) -> None:
    """Display image or video.

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
        st.rerun()
```

3. **Break Phase Renderer**
```python
import time

def render_break_phase(content: Dict[str, Any]) -> None:
    """Timed break screen.

    content = {
        "type": "break",
        "duration_seconds": 30,
        "message": "Please wait 30 seconds..."
    }
    """
    st.info(content.get("message", "Please wait..."))

    duration = content.get("duration_seconds", 30)

    if 'break_start_time' not in st.session_state:
        st.session_state.break_start_time = time.time()

    elapsed = time.time() - st.session_state.break_start_time
    remaining = max(0, duration - elapsed)

    # Progress bar
    progress = elapsed / duration if duration > 0 else 1.0
    st.progress(min(1.0, progress))
    st.metric("Time Remaining", f"{int(remaining)}s")

    if remaining == 0:
        st.success("Break complete!")
        st.session_state.phase_complete = True
        del st.session_state.break_start_time
        st.rerun()
    else:
        time.sleep(1)
        st.rerun()
```

4. **Survey Phase Renderer**
```python
def render_custom_survey_phase(content: Dict[str, Any]) -> None:
    """Additional survey questions.

    content = {
        "type": "survey",
        "questions": [
            {"id": "q1", "text": "...", "type": "slider", "min": 1, "max": 9}
        ]
    }
    """
    responses = {}

    for q in content.get("questions", []):
        if q["type"] == "slider":
            responses[q["id"]] = st.slider(
                q["text"],
                min_value=q.get("min", 1),
                max_value=q.get("max", 9),
                key=f"survey_{q['id']}"
            )
        elif q["type"] == "text":
            responses[q["id"]] = st.text_input(
                q["text"],
                key=f"survey_{q['id']}"
            )

    if st.button("Submit"):
        # Save responses (add save function)
        st.session_state.phase_complete = True
        st.rerun()
```

5. **Router Function**
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
        st.error(f"Unknown custom phase type: {phase_type}")
```

#### Implementation Notes

- **Phase Completion:** Use `st.session_state.phase_complete` to signal done
- **Timers:** Use `st.rerun()` with `time.sleep()` for countdowns
- **Styling:** Use existing `robotaste/components/styles.py` patterns
- **Error Handling:** Validate content structure, show error if invalid

---

### Task 2.2: Phase Builder UI ⭐ MEDIUM PRIORITY

**File:** `robotaste/views/phase_builder.py` (NEW)

**Estimated Time:** 5-6 hours

#### Deliverables

Visual phase sequence builder UI component that returns phase_sequence JSON.

**Features:**
1. List of phases with reordering (up/down buttons)
2. Add phase button (builtin/custom/loop selector)
3. Phase configuration form (type-specific)
4. Delete phase button
5. Preview mode showing sequence

**Return Value:**
```python
{
    "phases": [
        {"phase_id": "custom_intro", "phase_type": "custom", ...},
        {"phase_id": "experiment_loop", "phase_type": "loop", ...}
    ]
}
```

#### Implementation Example

```python
def render_phase_builder(num_cycles: int = 10) -> Dict[str, Any]:
    """Visual phase sequence builder."""

    st.subheader("Phase Sequence Builder")

    # Initialize
    if 'phase_sequence' not in st.session_state:
        st.session_state.phase_sequence = DEFAULT_PHASES.copy()

    phases = st.session_state.phase_sequence

    # Render each phase
    for idx, phase in enumerate(phases):
        with st.expander(f"{idx+1}. {phase['phase_id']} ({phase.get('phase_type', 'builtin')})"):
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.write(f"Type: {phase.get('phase_type', 'builtin')}")
                st.write(f"Required: {phase.get('required', True)}")

            with col2:
                # Move up
                if idx > 0 and st.button("⬆️", key=f"up_{idx}"):
                    phases[idx], phases[idx-1] = phases[idx-1], phases[idx]
                    st.rerun()

            with col3:
                # Move down
                if idx < len(phases)-1 and st.button("⬇️", key=f"down_{idx}"):
                    phases[idx], phases[idx+1] = phases[idx+1], phases[idx]
                    st.rerun()

            # Phase config form
            phase['required'] = st.checkbox("Required", value=phase.get('required', True), key=f"req_{idx}")
            phase['auto_advance'] = st.checkbox("Auto-advance", value=phase.get('auto_advance', False), key=f"auto_{idx}")

            if phase['auto_advance']:
                phase['duration_ms'] = st.number_input(
                    "Duration (ms)",
                    min_value=100,
                    value=phase.get('duration_ms', 5000),
                    key=f"dur_{idx}"
                )

    # Add phase
    if st.button("+ Add Phase"):
        st.session_state.show_add_phase = True

    if st.session_state.get('show_add_phase'):
        with st.form("add_phase_form"):
            phase_type = st.selectbox("Phase Type", ["builtin", "custom"])

            if phase_type == "builtin":
                phase_id = st.selectbox("Phase", ["waiting", "registration", "instructions", "completion"])
            else:
                phase_id = st.text_input("Custom Phase ID")

            if st.form_submit_button("Add"):
                phases.append({"phase_id": phase_id, "phase_type": phase_type, "required": True})
                st.session_state.show_add_phase = False
                st.rerun()

    return {"phases": phases}
```

---

### Task 2.3: Subject View Integration ⭐ HIGH PRIORITY

**File:** `robotaste/views/subject.py` (MODIFY)

**Estimated Time:** 3-4 hours

#### Deliverables

Update subject view to:
1. Load PhaseEngine if protocol has phase_sequence
2. Check for custom phases
3. Render custom phases via `render_custom_phase()`
4. Handle auto-advance logic

#### Implementation

```python
from robotaste.core.phase_engine import PhaseEngine
from robotaste.views.custom_phases import render_custom_phase

# In main subject view rendering:

# Load protocol
protocol = load_protocol_for_session(session_id)

if protocol and 'phase_sequence' in protocol:
    # Use PhaseEngine
    engine = PhaseEngine(protocol, session_id)

    current_phase = st.session_state.current_phase

    # Check if custom phase
    phase_content = engine.get_phase_content(current_phase)

    if phase_content:
        # Render custom phase
        render_custom_phase(current_phase.value, phase_content)

        # Check auto-advance
        should_advance, duration_ms = engine.should_auto_advance(current_phase)

        if st.session_state.get('phase_complete'):
            if should_advance and duration_ms:
                time.sleep(duration_ms / 1000)

            next_phase = engine.get_next_phase(current_phase)
            update_current_phase(session_id, next_phase)
            st.session_state.phase_complete = False
            st.rerun()
    else:
        # Render builtin phase (existing logic)
        render_builtin_phase(current_phase)
else:
    # No protocol, use default phases
    render_builtin_phase(current_phase)
```

---

## Priority 3: Testing & Documentation (Should Have)

### Task 3.1: Phase Engine Tests

**File:** `tests/test_phase_engine.py` (NEW)

**Estimated Time:** 3-4 hours

**Test Cases:**
- Test parsing default phases
- Test parsing custom phases
- Test `get_next_phase()` with required phases
- Test `get_next_phase()` with optional phases (skipping)
- Test `should_auto_advance()` returns correct values
- Test `can_skip_phase()` for optional phases
- Test invalid phase sequence (fallback to default)
- Test circular dependency detection

---

### Task 3.2: Integration Tests

**File:** `tests/test_protocol_integration.py` (NEW)

**Estimated Time:** 3-4 hours

**Test Scenarios:**
1. Full lifecycle: Create protocol → Save → Load → Execute
2. Custom phase execution: Protocol with custom intro → Execute
3. Mixed-mode transitions: Predetermined → User → BO
4. Phase skipping: Protocol with optional registration → Skip
5. Auto-advance: Custom break phase → Auto-transition
6. Invalid protocol handling: Bad phase_sequence → Validation error

---

### Task 3.3: Documentation

**Files:**
- `docs/protocol_schema.md` (NEW)
- `docs/phase_engine_api.md` (NEW)
- Update `docs/week_3-4_api_reference.md`

**Estimated Time:** 2-3 hours

**Content:**

**protocol_schema.md:**
- Full JSON schema for protocols
- phase_sequence format
- Custom phase content formats
- Examples for each phase type

**phase_engine_api.md:**
- PhaseEngine class documentation
- Method signatures
- Usage examples
- Integration guide

---

## Priority 4: Integration & Polish (Nice to Have)

### Task 4.1: Protocol Editor Integration

**File:** `robotaste/views/protocol_manager.py` (MODIFY)

**Estimated Time:** 2-3 hours

**Add:**
- Tab 3: Phase Sequence (integrate phase_builder)
- Preview custom phases in protocol preview
- Validation error display for phase_sequence

---

### Task 4.2: Helper Functions (Optional)

**Files:** Various

**Estimated Time:** 1-2 hours

**Add:**
- `should_use_bo_for_cycle()` in bo_integration.py
- `get_sessions_by_protocol()` in database.py
- `load_protocol_for_session()` standalone in trials.py

---

## Summary

### Total Estimated Effort
- **Priority 1 (Must Have):** 8-12 hours - Phase Engine Core
- **Priority 2 (Must Have):** 12-15 hours - UI Components
- **Priority 3 (Should Have):** 8-12 hours - Testing & Docs
- **Priority 4 (Nice to Have):** 3-5 hours - Polish

**Total:** 31-44 hours (~1 week for 1 developer working full-time)

### Success Criteria

Week 5 is successful if:
- [ ] PhaseEngine class fully implemented and tested
- [ ] Custom phases can be defined in protocols
- [ ] Phase skipping works (registration optional)
- [ ] Auto-advance functional
- [ ] UI can create custom phase sequences
- [ ] Subject view renders custom phases
- [ ] All tests passing
- [ ] Documentation updated

### Files to Create

**New Files (7):**
1. `robotaste/core/phase_engine.py`
2. `robotaste/views/custom_phases.py`
3. `robotaste/views/phase_builder.py`
4. `tests/test_phase_engine.py`
5. `tests/test_protocol_integration.py`
6. `docs/protocol_schema.md`
7. `docs/phase_engine_api.md`

**Files to Modify (5):**
1. `robotaste/core/state_machine.py`
2. `robotaste/config/protocols.py`
3. `robotaste/views/subject.py`
4. `robotaste/views/protocol_manager.py`
5. `docs/week_3-4_api_reference.md`

---

## Implementation Order (Recommended)

**Day 1-2: Phase Engine Core**
1. Task 1.1: Create phase_engine.py (4-6 hours)
2. Task 1.2: State machine integration (2-3 hours)
3. Task 1.3: Phase validation (2-3 hours)
4. Task 3.1: Phase engine tests (3-4 hours)

**Day 3-4: UI Components**
5. Task 2.1: Custom phase renderers (4-5 hours)
6. Task 2.2: Phase builder UI (5-6 hours)
7. Task 2.3: Subject view integration (3-4 hours)

**Day 5: Testing & Documentation**
8. Task 3.2: Integration tests (3-4 hours)
9. Task 3.3: Documentation (2-3 hours)
10. Task 4.1: Protocol editor integration (2-3 hours)

---

**Document Version:** 1.0
**Created:** January 1, 2026
**Status:** Ready to Start
