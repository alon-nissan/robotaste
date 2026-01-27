# Multipage Migration Guide

## Overview

RoboTaste has migrated from state machine-based phase management to a dynamic single-page router for improved code organization and protocol flexibility.

**Migration Date:** January 27, 2026  
**Status:** Complete  
**Backward Compatibility:** Full - all existing protocols work without modification

## Key Changes

### For Researchers

✅ **No changes to protocol format** - all existing protocols work  
✅ **Custom phases fully supported** - add custom phases via JSON  
✅ **Same URLs** - subject links unchanged  
✅ **Same functionality** - all features preserved

### For Developers

#### Phase Code Location Changed

**Old:**
- Single monolithic file: `robotaste/views/subject.py` (1,290+ lines)
- All phase logic mixed together
- Hard to test and maintain

**New:**
- Modular phase renderers: `robotaste/views/phases/builtin/*.py`
- Each phase in separate file (~50-200 lines each)
- Easy to test, extend, and maintain

#### Navigation Changed

**Old:**
```python
# Direct calls with st.rerun()
if st.button("Continue"):
    transition_to_next_phase(current_phase, next_phase, session_id)
    st.rerun()
```

**New:**
```python
# Set flag, let PhaseRouter handle navigation
if st.button("Continue"):
    st.session_state.phase_complete = True
    # PhaseRouter automatically advances to next phase
```

#### Adding New Phases

**Old:** Edit massive `subject.py` file, add to state machine

**New:** Create modular phase renderer:

```python
# robotaste/views/phases/builtin/my_phase.py
def render_my_phase(session_id: str, protocol: Dict[str, Any]) -> None:
    """Render my custom phase."""
    st.title("My Phase")
    
    # Your UI code here
    
    if st.button("Continue"):
        st.session_state.phase_complete = True
```

Then register in `PhaseRouter._register_builtin_phases()`.

## Architecture

### System Flow

```
User Request
    ↓
pages/experiment.py (entry point)
    ↓
PhaseRouter (routes to correct renderer)
    ↓
Phase Renderer (builtin or custom)
    ↓
Sets phase_complete flag
    ↓
PhaseRouter navigation (advances to next phase)
```

### Directory Structure

```
robotaste/
├── core/
│   └── phase_router.py         # Main routing logic
├── views/
│   ├── phases/
│   │   ├── builtin/           # Standard experiment phases
│   │   │   ├── consent.py
│   │   │   ├── selection.py
│   │   │   ├── questionnaire.py
│   │   │   ├── loading.py
│   │   │   ├── robot_preparing.py
│   │   │   ├── registration.py
│   │   │   └── completion.py
│   │   └── custom/            # Protocol-defined phases
│   │       └── custom_phase.py
│   └── subject.py             # DEPRECATED - kept for reference
└── pages/
    └── experiment.py           # Single dynamic experiment page
```

### Phase Types

#### Builtin Phases (7 total)

1. **consent** - Informed consent screen
2. **selection** - Sample selection (grid/slider)
3. **questionnaire** - Rating questionnaire
4. **loading** - Loading/waiting screen
5. **robot_preparing** - Pump operation status
6. **registration** - Subject demographics
7. **completion** - Thank you screen

#### Custom Phases (4 types)

1. **text** - Display markdown text with optional images
2. **media** - Display images or videos from URLs
3. **survey** - Custom survey questions (5 question types)
4. **break** - Timed countdown timer

## Backward Compatibility

### Database Schema

✅ **No changes** - All existing tables unchanged  
✅ **Current_phase field** - Still used for phase tracking  
✅ **Custom phase data** - Stored in existing `experiment_config` JSON

### Existing Sessions

✅ **Continue working** - Sessions created before migration work normally  
✅ **URL format** - Same format: `/experiment?session=ABC123&role=subject`  
✅ **Multi-device sync** - Database polling mechanism unchanged

### Protocols

✅ **All protocols compatible** - No protocol format changes  
✅ **Custom phases** - Work exactly as before  
✅ **Phase sequences** - PhaseEngine logic preserved

## Migration Timeline

- **Phase 1 (Week 1):** Infrastructure setup ✅
- **Phase 2 (Week 2-3):** Extract builtin phases ✅
- **Phase 3 (Week 3-4):** Custom phase support ✅
- **Phase 4 (Week 4):** Integration & testing ✅

**Total Development Time:** 3 weeks  
**Lines of Code:** ~2,000 lines (from 1,290 monolithic lines)  
**Test Coverage:** 15+ comprehensive tests

## Benefits

### Code Quality

- ✅ **Modular:** Each phase 50-200 lines (was 1,290+ lines)
- ✅ **Testable:** Individual phase tests easy to write
- ✅ **Maintainable:** Changes isolated to specific files
- ✅ **Documented:** Each phase has comprehensive docstrings

### Developer Experience

- ✅ **Easy to extend:** New phases take < 1 hour
- ✅ **Clear patterns:** Consistent structure across phases
- ✅ **No st.rerun():** Navigation handled by PhaseRouter
- ✅ **Better debugging:** Clear separation of concerns

### User Experience

- ✅ **No visible changes:** Same experiment flow
- ✅ **Same performance:** No degradation
- ✅ **Custom phases:** More flexible protocols
- ✅ **Error handling:** Better error messages

## Common Issues & Solutions

### Issue: Phase not advancing

**Symptom:** User clicks "Continue" but nothing happens

**Solution:** Ensure phase renderer sets `st.session_state.phase_complete = True`

```python
# Correct
if st.button("Continue"):
    save_data_to_database()
    st.session_state.phase_complete = True  # ← Must set this

# Wrong - missing flag
if st.button("Continue"):
    save_data_to_database()
    # Missing: st.session_state.phase_complete = True
```

### Issue: Phase mismatch error

**Symptom:** Warning about phase mismatch

**Solution:** This happens when:
- Browser cache is stale → Refresh page
- Multiple devices out of sync → Wait for database poll
- URL manipulation → PhaseRouter blocks invalid access

### Issue: Custom phase not rendering

**Symptom:** "Unknown phase type" error

**Solution:** Check protocol JSON:

```json
{
  "phase_id": "intro",
  "phase_type": "custom",
  "content": {
    "type": "text",  // ← Must be one of: text, media, survey, break
    "title": "Welcome",
    "text": "Welcome to the experiment!"
  }
}
```

## Development Guide

### Creating a New Builtin Phase

1. **Create phase file**

```bash
touch robotaste/views/phases/builtin/my_phase.py
```

2. **Implement renderer**

```python
# robotaste/views/phases/builtin/my_phase.py
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
    
    # Get configuration
    config = protocol.get("my_phase_config", {})
    
    # Render UI
    st.write("Phase content here")
    
    # Handle interaction
    if st.button("Continue"):
        # Save data if needed
        from robotaste.data.database import save_my_data
        save_my_data(session_id, "value")
        
        # Mark complete
        st.session_state.phase_complete = True
        logger.info(f"Session {session_id}: My phase completed")
```

3. **Register in PhaseRouter**

```python
# robotaste/core/phase_router.py
def _register_builtin_phases(self) -> None:
    from robotaste.views.phases.builtin.my_phase import render_my_phase
    
    self._builtin_renderers = {
        # ... existing phases ...
        "my_phase": render_my_phase,
    }
```

4. **Update protocol**

```json
{
  "phase_sequence": {
    "phases": [
      {"phase_id": "my_phase", "phase_type": "builtin"}
    ]
  }
}
```

### Creating Custom Phase Content

Custom phases are defined entirely in protocol JSON:

```json
{
  "phase_id": "welcome_video",
  "phase_type": "custom",
  "content": {
    "type": "media",
    "title": "Welcome to the Experiment",
    "media_type": "video",
    "media_url": "https://example.com/welcome.mp4",
    "caption": "Please watch this short introduction"
  }
}
```

No code changes needed - just update protocol!

### Testing Phases

```python
# tests/test_my_phase.py
import pytest
from robotaste.views.phases.builtin.my_phase import render_my_phase

def test_my_phase_renders():
    """Test my phase displays correctly."""
    protocol = {
        "my_phase_config": {
            "setting": "value"
        }
    }
    
    render_my_phase("test-session", protocol)
    
    # Assertions here
```

## Performance Considerations

### Database Queries

- PhaseRouter caches protocol in session state
- Phase validation uses single query
- No regression in performance

### Page Load Time

- **Before:** ~1-2 seconds
- **After:** ~1-2 seconds (no change)
- PhaseRouter initialization: < 100ms

### Memory Usage

- Minimal increase (phase renderers lazy-loaded)
- No impact on multi-device experiments

## Future Enhancements

### Planned (Not Yet Implemented)

1. **Moderator Interface Migration**
   - Move moderator UI to pages/moderator.py
   - Separate setup, monitoring, configuration pages
   - Estimated: 2-3 weeks

2. **URL-Based Phase Navigation**
   - Add phase to URL: `/experiment?phase=selection`
   - Enable browser back button
   - Deep linking support
   - Estimated: 1 week

3. **Phase Analytics**
   - Track time spent in each phase
   - Identify bottlenecks
   - Generate reports
   - Estimated: 1 week

## Support

### Getting Help

- **Documentation:** This file (docs/MULTIPAGE_MIGRATION.md)
- **Code Examples:** See `robotaste/views/phases/builtin/`
- **Tests:** See `tests/test_custom_phases.py`

### Reporting Issues

Please include:
1. Phase where issue occurs
2. Error message or unexpected behavior
3. Protocol configuration (if custom phase)
4. Steps to reproduce

## Summary

✅ **Migration Complete:** All phases extracted and working  
✅ **Backward Compatible:** No breaking changes  
✅ **Well Tested:** 15+ comprehensive tests  
✅ **Documented:** Clear patterns and examples  
✅ **Production Ready:** Safe to deploy

The multipage migration improves code organization while maintaining 100% backward compatibility with existing experiments and protocols.
