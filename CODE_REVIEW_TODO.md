# RoboTaste Code Review - Comprehensive TODO List

**Generated:** 2026-01-25  
**Reviewed Files:** 27,397 lines of Python code  
**Issues Found:** 140+  
**Team:** 1 Frontend Dev + 1 Backend Dev

---

## 🚨 CRITICAL PRIORITIES (Must Fix Immediately)

### Backend (High Severity Security & Safety)

#### 1. **Unsafe `eval()` Usage - CODE INJECTION RISK** 
- **Files:** `robotaste/config/defaults.py:508`, `questionnaire.py:442`
- **Risk:** Remote code execution if formulas come from untrusted source
- **Fix:** Replace with `numexpr.evaluate()` or safe expression parser
```python
# BEFORE (UNSAFE):
target_value = eval(formula, {"__builtins__": {}}, response)

# AFTER:
import numexpr
target_value = numexpr.evaluate(formula, local_dict=response)
```
- **Owner:** Backend Dev
- **Estimate:** 4 hours

---

#### 2. **Hardware Safety - Dispensing Timeout Risk**
- **File:** `robotaste/hardware/pump_controller.py:983-998`
- **Risk:** Hard-coded 10% time buffer could cause continuous pump flow if pump runs slow
- **Impact:** Could dispense entire syringe (dangerous!)
- **Fix:** Replace sleep-based timing with polling for completion status
```python
# BEFORE:
time.sleep(wait_time)
self.stop()

# AFTER:
while not self._check_dispense_complete(timeout=wait_time):
    time.sleep(0.1)
self.stop()
```
- **Owner:** Backend Dev
- **Estimate:** 8 hours (includes testing)

---

#### 3. **Silent Exception Swallowing in BO Convergence**
- **File:** `robotaste/core/bo_integration.py:234-258`
- **Issue:** `except Exception as e: pass` hides critical errors
- **Fix:** Log exceptions and return error state
```python
except Exception as e:
    logger.error(f"Convergence check failed: {e}")
    return {"has_converged": False, "error": str(e)}
```
- **Owner:** Backend Dev
- **Estimate:** 2 hours

---

#### 4. **JSON Parsing Without Error Handling**
- **File:** `pump_control_service.py:212`
- **Risk:** Malformed JSON in database crashes entire pump service
- **Fix:** Add try-except around `json.loads()`
```python
try:
    recipe = json.loads(recipe_json)
except json.JSONDecodeError as e:
    logger.error(f"Invalid recipe JSON: {e}")
    mark_operation_failed(conn, op_id, f"Invalid JSON: {e}")
    continue
```
- **Owner:** Backend Dev
- **Estimate:** 1 hour

---

### Frontend (High Severity Security)

#### 5. **XSS Vulnerability - HTML Injection**
- **Files:** `robotaste/views/protocol_manager.py:92-103`, `questionnaire.py:136-137`, `sample_sequence_builder.py:68-90`
- **Risk:** User-provided text rendered as HTML without sanitization
- **Fix:** Create HTML sanitization utility
```python
import html

def safe_markdown(text: str, **kwargs):
    """Render markdown with escaped HTML"""
    escaped = html.escape(text)
    st.markdown(escaped, **kwargs)
```
- **Owner:** Frontend Dev
- **Estimate:** 6 hours (create utility + fix all occurrences)

---

#### 6. **Input Validation Missing on All Forms**
- **Files:** `protocol_manager.py:241-243, 315-332`, `landing.py:110-116`
- **Risk:** Accepts negative concentrations, invalid characters, arbitrary strings
- **Fix:** Create validation utility and apply to all inputs
```python
def validate_concentration(value: float, min_val: float, max_val: float) -> bool:
    if not isinstance(value, (int, float)):
        return False
    if value < min_val or value > max_val:
        return False
    return True
```
- **Owner:** Frontend Dev
- **Estimate:** 8 hours

---

## 🔴 HIGH PRIORITY (Fix Within Sprint)

### Backend

#### 7. **Database Transaction Management**
- **Files:** `robotaste/data/protocol_repo.py:68-81, 240-255, 281-299`
- **Issue:** No rollback on exceptions - partial writes possible
- **Fix:** Add transaction wrapper
```python
try:
    cursor.execute(...)
    conn.commit()
except Exception as e:
    conn.rollback()
    raise
```
- **Owner:** Backend Dev
- **Estimate:** 4 hours

---

#### 8. **Pump Serial Port Lock Held Too Long**
- **File:** `robotaste/hardware/pump_controller.py:1068-1079`
- **Issue:** Lock held during 5-second timeout blocks all other pumps
- **Fix:** Release lock after write, reacquire for read
- **Owner:** Backend Dev
- **Estimate:** 3 hours

---

#### 9. **BO Training Data Uses Wrong Parameter**
- **File:** `robotaste/core/bo_utils.py:71`
- **Issue:** Gets ALL data instead of only final responses
- **Fix:** Verify `only_final=True` parameter is correct
- **Owner:** Backend Dev
- **Estimate:** 2 hours + testing

---

#### 10. **Pump S? Response Not Raising Exceptions**
- **Files:** `robotaste/hardware/pump_controller.py:418, 469, 565`
- **Issue:** Pump rejection logged but code continues assuming success
- **Fix:** Raise `PumpCommandError` on S? response
```python
if response == "S?":
    logger.error(f"[Pump {self.address}] Command rejected")
    raise PumpCommandError("Pump rejected command")
```
- **Owner:** Backend Dev
- **Estimate:** 2 hours

---

#### 11. **Bare `except:` Clauses**
- **Files:** `pump_control_service.py:301, 379`
- **Issue:** Catches SystemExit, KeyboardInterrupt - prevents graceful shutdown
- **Fix:** Change to `except Exception as e:`
- **Owner:** Backend Dev
- **Estimate:** 1 hour

---

#### 12. **Missing Indexes on Database**
- **File:** `robotaste/data/schema.sql`
- **Issue:** No indexes on `deleted_at`, `(session_id, cycle_number)`
- **Fix:** Add indexes
```sql
CREATE INDEX idx_sessions_deleted ON sessions(deleted_at);
CREATE INDEX idx_samples_deleted ON samples(deleted_at);
CREATE INDEX idx_samples_session_cycle ON samples(session_id, cycle_number);
```
- **Owner:** Backend Dev
- **Estimate:** 2 hours (includes migration)

---

### Frontend

#### 13. **Session State Cleanup Causes Race Conditions**
- **Files:** `completion.py:40-43, 91-93`, `protocol_manager.py:548-555`
- **Issue:** Clears entire session state without protecting critical keys
- **Fix:** Create safe cleanup utility
```python
def safe_state_cleanup(preserve_keys: List[str]):
    """Clear session state except protected keys"""
    to_delete = [k for k in st.session_state.keys() if k not in preserve_keys]
    for key in to_delete:
        del st.session_state[key]
```
- **Owner:** Frontend Dev
- **Estimate:** 4 hours

---

#### 14. **No Loading Indicators on Async Operations**
- **Files:** `protocol_manager.py:516-557`, `completion.py:327-361`, `subject.py:237-238`
- **Issue:** UI appears frozen during database writes
- **Fix:** Add `st.spinner()` wrappers
```python
with st.spinner("Saving protocol..."):
    save_protocol(data)
st.success("Protocol saved!")
```
- **Owner:** Frontend Dev
- **Estimate:** 3 hours

---

#### 15. **Emoji-Only Buttons Not Accessible**
- **Files:** `completion.py:39, 327, 365`, `moderator_views.py:389-391`
- **Issue:** Screen readers can't understand button purpose
- **Fix:** Add text labels
```python
# BEFORE:
st.button("📥")

# AFTER:
st.button("📥 Download Data")
```
- **Owner:** Frontend Dev
- **Estimate:** 2 hours

---

## 🟡 MEDIUM PRIORITY (Plan for Next Sprint)

### Backend

#### 16. **Circular Dependencies in State Machine**
- **Files:** `state_helpers.py`, `state_machine.py`, `phase_engine.py`
- **Issue:** Line 430 in `state_machine.py` has late import to avoid circular dependency
- **Fix:** Refactor to separate concerns properly
- **Owner:** Backend Dev
- **Estimate:** 12 hours

---

#### 17. **Code Duplication in Protocol Loading**
- **File:** `robotaste/core/trials.py:404-412, 429-441`
- **Issue:** Same protocol loading logic repeated 3+ times
- **Fix:** Extract helper function
```python
def _get_protocol(session: dict) -> dict:
    """Get protocol from experiment_config or protocol_repo"""
    # Extract repeated logic here
```
- **Owner:** Backend Dev
- **Estimate:** 3 hours

---

#### 18. **Inefficient DataFrame Iterations in BO**
- **File:** `robotaste/core/bo_utils.py:376-399`
- **Issue:** O(n²) complexity in convergence metrics
- **Fix:** Vectorize operations using pandas
- **Owner:** Backend Dev
- **Estimate:** 4 hours

---

#### 19. **N+1 Query Pattern in Protocol Search**
- **File:** `robotaste/data/protocol_repo.py:378-409`
- **Issue:** Fetches all protocols then loads each individually
- **Fix:** Optimize to single query with joins
- **Owner:** Backend Dev
- **Estimate:** 4 hours

---

#### 20. **Type Hints Inconsistency**
- **Files:** `viewport.py:13`, `serial_utils.py:144, 191`
- **Issue:** Uses `any` instead of `Any` (with type: ignore to suppress)
- **Fix:** Fix type hints and remove suppressions
```python
from typing import Any

def initialize_viewport_detection() -> Dict[str, Any]:
```
- **Owner:** Backend Dev
- **Estimate:** 1 hour

---

#### 21. **Shallow Copy of Nested Dict**
- **File:** `robotaste/config/bo_config.py:86`
- **Issue:** `.copy()` doesn't deep copy nested dicts
- **Fix:** Use `copy.deepcopy()`
```python
import copy
return copy.deepcopy(DEFAULT_BO_CONFIG)
```
- **Owner:** Backend Dev
- **Estimate:** 1 hour

---

#### 22. **Missing Questionnaire Type**
- **Files:** `protocol_schema.py:742` allows `intensity_continuous`, but `defaults.py` doesn't define it
- **Fix:** Either add definition or remove from schema
- **Owner:** Backend Dev
- **Estimate:** 2 hours

---

#### 23. **Zero Division Risk in Pump Service**
- **File:** `pump_control_service.py:309`
- **Issue:** If `dispensing_rate` is 0, crashes
- **Fix:** Add validation
```python
if dispensing_rate <= 0:
    raise ValueError(f"Invalid rate: {dispensing_rate}")
time_needed = (volume_ul / dispensing_rate) * 60 * 1.1
```
- **Owner:** Backend Dev
- **Estimate:** 1 hour

---

#### 24. **Pump Connection State Not Verified**
- **File:** `pump_control_service.py:271-288`
- **Issue:** Commands sent without verifying connection still valid
- **Fix:** Add reconnection logic
- **Owner:** Backend Dev
- **Estimate:** 4 hours

---

### Frontend

#### 25. **Error Messages Lack Context**
- **Files:** `protocol_manager.py:558`, `subject.py:96-98`, `completion.py:98`
- **Issue:** Generic "An error occurred" messages don't help users
- **Fix:** Add specific error details and remediation steps
```python
st.error(f"Failed to save protocol: {error_details}. Please try again or contact support.")
```
- **Owner:** Frontend Dev
- **Estimate:** 4 hours

---

#### 26. **Disabled Buttons Without Explanation**
- **Files:** `protocol_manager.py:131-137`, `consent.py:45`
- **Issue:** Buttons disabled without tooltip explaining why
- **Fix:** Add help text
```python
st.button("Continue", disabled=not agreed, help="Please agree to consent form first")
```
- **Owner:** Frontend Dev
- **Estimate:** 2 hours

---

#### 27. **Code Duplication - DRY Violations**
- **Issue:** Session state cleanup repeated 5+ times across views
- **Fix:** Extract to shared utility (see #13)
- **Owner:** Frontend Dev
- **Estimate:** 2 hours

---

#### 28. **Magic Numbers Throughout Code**
- **Files:** `subject.py:238` (3 second sleep), `custom_phases.py:214-215`
- **Fix:** Extract constants
```python
PHASE_TRANSITION_DELAY_SECONDS = 3
time.sleep(PHASE_TRANSITION_DELAY_SECONDS)
```
- **Owner:** Frontend Dev
- **Estimate:** 2 hours

---

#### 29. **Missing Form Validation UX**
- **Files:** `subject.py:80-112`, `protocol_manager.py:314-332`
- **Issue:** Validation only on submit, no live feedback
- **Fix:** Add real-time validation using callbacks
- **Owner:** Frontend Dev
- **Estimate:** 6 hours

---

#### 30. **Color-Only Status Indicators**
- **Files:** `moderator_views.py:373-377`, `completion.py:296-297`
- **Issue:** Users with color blindness can't distinguish status
- **Fix:** Add text labels alongside emojis
- **Owner:** Frontend Dev
- **Estimate:** 2 hours

---

## 🔵 LOW PRIORITY (Technical Debt)

### Backend

#### 31. **Missing Docstrings**
- **Files:** Throughout `robotaste/core/`, `robotaste/data/`
- **Issue:** Complex functions lack documentation
- **Fix:** Add comprehensive docstrings
- **Owner:** Backend Dev
- **Estimate:** 8 hours

---

#### 32. **Inconsistent Error Return Values**
- **File:** `robotaste/data/database.py`
- **Issue:** Functions return `False`, `[]`, `{}`, or `None` inconsistently
- **Fix:** Standardize on exceptions or single return pattern
- **Owner:** Backend Dev
- **Estimate:** 6 hours

---

#### 33. **No Audit Trail for Data Modifications**
- **Issue:** No tracking of who modified what data and when
- **Fix:** Add user_id, modification_reason to sensitive updates
- **Owner:** Backend Dev
- **Estimate:** 12 hours

---

#### 34. **Hard-coded String Values in Queries**
- **File:** `robotaste/data/protocol_repo.py:160`
- **Issue:** Direct string building instead of parameterized
- **Fix:** Use consistent parameterized approach
- **Owner:** Backend Dev
- **Estimate:** 3 hours

---

#### 35. **Inefficient Uniqueness Counting**
- **File:** `robotaste/core/moderator_metrics.py:332-336`
- **Issue:** JSON serialization for every comparison
- **Fix:** Use hash or tuple comparison
```python
unique_samples = len(set(
    tuple(sorted(s.get("ingredient_concentration", {}).items()))
    for s in user_samples
))
```
- **Owner:** Backend Dev
- **Estimate:** 2 hours

---

#### 36. **Missing CASCADE Delete Specifications**
- **File:** `robotaste/data/schema.sql:60-62`
- **Issue:** Foreign keys lack CASCADE DELETE, risking orphaned records
- **Fix:** Add CASCADE specifications
```sql
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
```
- **Owner:** Backend Dev
- **Estimate:** 2 hours + migration

---

#### 37. **Test Coverage Gaps**
- **Files:** `main_app.py`, `pump_control_service.py` have NO tests
- **Missing:** Multi-device routing, signal handling, concurrent operations
- **Fix:** Add comprehensive test suite
- **Owner:** Backend Dev
- **Estimate:** 20 hours

---

### Frontend

#### 38. **Over-Complex Functions**
- **File:** `protocol_manager.py:207-571` - `protocol_editor()` is 365 lines
- **Fix:** Break into smaller, testable functions
- **Owner:** Frontend Dev
- **Estimate:** 8 hours

---

#### 39. **Inconsistent Naming Conventions**
- **Issue:** `cycle_num` vs `current_cycle` vs `cycle_number`
- **Fix:** Standardize on single naming convention
- **Owner:** Frontend Dev
- **Estimate:** 4 hours

---

#### 40. **HTML Timeline Not Accessible**
- **Files:** `sample_sequence_builder.py:68-90`, `moderator.py`
- **Issue:** No semantic structure, not accessible to screen readers
- **Fix:** Use `st.dataframe()` or semantic HTML with ARIA labels
- **Owner:** Frontend Dev
- **Estimate:** 6 hours

---

#### 41. **Missing Alt Text for Dynamic Content**
- **File:** `subject.py` - Canvas elements
- **Fix:** Add descriptive labels
- **Owner:** Frontend Dev
- **Estimate:** 2 hours

---

#### 42. **No Environment Variable Support**
- **File:** `main_app.py`
- **Issue:** All settings hardcoded
- **Fix:** Add config file and environment variable support
- **Owner:** Frontend Dev
- **Estimate:** 4 hours

---

## 📊 SUMMARY STATISTICS

| Priority | Backend Tasks | Frontend Tasks | Total Est. Hours |
|----------|---------------|----------------|------------------|
| **Critical** | 4 | 2 | 29 hours |
| **High** | 7 | 3 | 31 hours |
| **Medium** | 9 | 6 | 49 hours |
| **Low** | 7 | 5 | 63 hours |
| **TOTAL** | **27 tasks** | **16 tasks** | **172 hours** |

---

## 🎯 RECOMMENDED SPRINT PLANNING

### Sprint 1 (Critical + High Priority)
- **Backend Focus:** Security fixes (#1, #3, #4), Hardware safety (#2), Database transactions (#7)
- **Frontend Focus:** XSS fixes (#5), Input validation (#6), Session state cleanup (#13)
- **Total:** ~60 hours

### Sprint 2 (High Priority Completion)
- **Backend Focus:** Pump improvements (#8, #10, #11), Database indexes (#12)
- **Frontend Focus:** Loading indicators (#14), Accessibility (#15), Error messages (#25)
- **Total:** ~20 hours

### Sprint 3 (Medium Priority)
- **Backend Focus:** Circular dependencies (#16), Code duplication (#17), Query optimization (#19)
- **Frontend Focus:** Form validation UX (#29), Disabled button tooltips (#26)
- **Total:** ~40 hours

### Sprint 4+ (Technical Debt)
- **Backend Focus:** Test coverage (#37), Documentation (#31), Audit trail (#33)
- **Frontend Focus:** Refactoring large functions (#38), Accessibility improvements (#40, #41)
- **Total:** ~52 hours

---

## 📝 NOTES FOR TEAM

### Backend Developer Priority Order:
1. **Day 1:** Fix `eval()` usage (#1) and JSON parsing (#4) - security critical
2. **Day 2-3:** Hardware safety fixes (#2, #10) - user safety critical
3. **Week 1:** Complete all Critical + High priority backend tasks
4. **Week 2+:** Address Medium priority items systematically

### Frontend Developer Priority Order:
1. **Day 1:** XSS vulnerability fixes (#5) - security critical
2. **Day 2-3:** Input validation (#6) - data integrity critical
3. **Week 1:** Session state cleanup (#13), Loading indicators (#14)
4. **Week 2+:** Accessibility improvements (#15, #30, #40)

### Testing Strategy:
- Add integration tests BEFORE fixing hardware issues (#2)
- Create regression tests for all security fixes (#1, #5, #6)
- Test multi-device scenarios after state management fixes (#13)

### Documentation Needs:
- Update architecture docs after circular dependency fix (#16)
- Document validation rules after implementing validation utilities (#6)
- Create pump safety guidelines after hardware fixes (#2, #8, #10)

---

## 🔗 RELATED DOCUMENTATION

- **Architecture:** See `docs/PROJECT_CONTEXT.md`
- **Protocol Schema:** See `docs/protocol_schema.md`
- **Development Guide:** See `AGENTS.md`, `CLAUDE.md`
- **Pump Configuration:** See `docs/pump_config.md`

---

**Last Updated:** 2026-01-25  
**Next Review:** After Sprint 1 completion
