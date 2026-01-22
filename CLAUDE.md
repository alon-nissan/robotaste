# CLAUDE.md

## 1. Style & Behavior
- **No Conversational Filler:** Never write "Here is...", "I've updated...", "Let me..." before tool calls. Just do the action.
- **Diffs Only:** Show ONLY changed blocks with 2-3 lines context. Never reprint unchanged functions.
- **General Logic, Not Code:** Explain approach in bullet points, not line-by-line code walkthrough.
- **Concise Questions:** Ask 1-2 focused questions maximum per turn.
- **Imports:** Do not hallucinate dependencies. Use existing `pyserial`, `streamlit`, `pandas`.

## 2. Project Type
Multi-device taste experiment platform. Moderator + subjects sync via database polling. Optional NE-4000 pump hardware.

## 2.5. Quick File Lookup
Map common tasks to exact file paths (use these before exploring):
- **Phase transitions** → `robotaste/core/state_machine.py`
- **Protocol logic** → `robotaste/core/phase_engine.py`, `robotaste/config/protocols.py`
- **BO algorithm** → `robotaste/core/bo_engine.py`, `robotaste/core/bo_integration.py`
- **Pump hardware** → `robotaste/hardware/pump_controller.py`
- **Pump caching** → `robotaste/core/pump_manager.py`
- **Database (SQL)** → `robotaste/data/database.py`
- **Database (business logic)** → `robotaste/data/session_repo.py`, `robotaste/data/protocol_repo.py`
- **Moderator UI** → `robotaste/views/moderator.py`
- **Subject UI** → `robotaste/views/subject.py`
- **Questionnaires** → `robotaste/views/questionnaire.py`, `robotaste/config/questionnaire.py`
- **Trials management** → `robotaste/core/trials.py`
- **Pump operations** → `robotaste/core/pump_integration.py`
- **Session sync** → `robotaste/data/session_repo.py` (`sync_session_state_to_streamlit()`)
- **Protocol schema** → `robotaste/config/protocol_schema.py`
- **Sample storage** → `robotaste/utils/pump_db.py`

## 3. Key Architecture & Entry Points
- **App:** `main_app.py` (Streamlit UI)
- **Service:** `pump_control_service.py` (Background hardware daemon)
- **State:** `robotaste/core/state_machine.py` (Phase transitions)
- **DB:** `robotaste.db` (SQLite) | Schema: `robotaste/data/schema.sql`
- **Protocol:** `robotaste/config/protocols.py`
- **Sync Pattern:** All devices poll `sessions` table for `current_phase` changes

## 4. CRITICAL Technical Constraints (Strict Adherence)
- **Pump Caching:** Re-use connections via `pump_manager.py`. Initialization takes ~21s; DO NOT create new pump instances per cycle.
- **Serial Locking:** Pumps share one port. Initialize sequentially using `_serial_port_lock` to avoid hardware conflicts.
- **Units:**
  - DB/UI = **µL** (microliters)
  - Pump Hardware = **mL** (milliliters) -> `vol_ml = vol_ul / 1000.0`
- **BO Training Data:** Column order MUST match `experiment_config.ingredients` order.
- **Phase Transitions:** Validate via `ExperimentStateMachine.validate_transition()` before updating `current_phase`.

### Common Pitfalls
- ❌ Creating new pump instances per cycle (21s penalty) → ✓ Use `pump_manager.get_or_create_pumps()`
- ❌ Bypassing `validate_transition()` → ✓ Always validate before updating `current_phase`
- ❌ Mixing µL/mL units → ✓ DB/UI uses µL, hardware uses mL (convert with `/1000.0`)
- ❌ Running hardware tests without pumps → ✓ Only run `test_pump_*.py` with physical connection
- ❌ Writing raw SQL in views → ✓ Use `session_repo.py` or `protocol_repo.py` for business logic
- ❌ Updating only `st.session_state` → ✓ Update database first, then sync to Streamlit state

## 5. Phase Flows (Quick Reference)
- **Standard:** WAITING → REGISTRATION → INSTRUCTIONS → SELECTION → LOADING → QUESTIONNAIRE → (loop) → COMPLETE
- **Pump:** WAITING → ... → SELECTION → ROBOT_PREPARING → QUESTIONNAIRE → (loop) → COMPLETE

## 6. Development Commands
- **Run App:** `streamlit run main_app.py`
- **Run Pump Service:** `python pump_control_service.py --db-path robotaste.db`
- **Tests:**
  - All: `pytest`
  - Hardware (Safety): `python robotaste/hardware/test_pump_movement.py`

## 7. Documentation
For deep context on Session Flows, BO Algorithms, or Protocol JSON schemas, refer to `docs/PROJECT_CONTEXT.md` (if created) or the specific file headers.