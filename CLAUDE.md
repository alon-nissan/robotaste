# CLAUDE.md

## 1. Style & Behavior
- **No Conversational Filler:** Never write "Here is...", "I've updated...", "Let me..." before tool calls. Just do the action.
- **Diffs Only:** Show ONLY changed blocks with 2-3 lines context. Never reprint unchanged functions.
- **General Logic, Not Code:** Explain approach in bullet points, not line-by-line code walkthrough.
- **Concise Questions:** Ask 1-2 focused questions maximum per turn.
- **Imports:** Do not hallucinate dependencies. Use existing `pyserial`, `streamlit`, `pandas`.

## 2. Project Type
Multi-device taste experiment platform. Moderator + subjects sync via database polling. Optional NE-4000 pump hardware and conveyor belt.

## 2.5. Quick File Lookup
Map common tasks to exact file paths (use these before exploring):
- **Phase transitions** → `robotaste/core/state_machine.py`
- **Protocol logic** → `robotaste/core/phase_engine.py`, `robotaste/config/protocols.py`
- **BO algorithm** → `robotaste/core/bo_engine.py`, `robotaste/core/bo_integration.py`
- **Pump hardware** → `robotaste/hardware/pump_controller.py`
- **Pump caching** → `robotaste/core/pump_manager.py`
- **Belt hardware** → `robotaste/hardware/belt_controller.py`
- **Belt caching** → `robotaste/core/belt_manager.py`
- **Robot orchestration** → `robotaste/core/robot_orchestrator.py`
- **Database (SQL)** → `robotaste/data/database.py`
- **Database (business logic)** → `robotaste/data/session_repo.py`, `robotaste/data/protocol_repo.py`
- **Moderator UI** → `robotaste/views/moderator.py`
- **Subject UI** → `robotaste/views/subject.py`
- **Questionnaires** → `robotaste/views/questionnaire.py`, `robotaste/config/questionnaire.py`
- **Trials management** → `robotaste/core/trials.py`
- **Pump operations** → `robotaste/core/pump_integration.py`
- **Belt operations** → `robotaste/core/belt_integration.py`
- **Session sync** → `robotaste/data/session_repo.py` (`sync_session_state_to_streamlit()`)
- **Protocol schema** → `robotaste/config/protocol_schema.py`
- **Sample storage** → `robotaste/utils/pump_db.py`, `robotaste/utils/belt_db.py`

## 3. Key Architecture & Entry Points
- **App:** `main_app.py` (Streamlit UI)
- **Pump Service:** `pump_control_service.py` (Background pump daemon)
- **Belt Service:** `belt_control_service.py` (Background belt daemon)
- **State:** `robotaste/core/state_machine.py` (Phase transitions)
- **DB:** `robotaste.db` (SQLite) | Schema: `robotaste/data/schema.sql`
- **Protocol:** `robotaste/config/protocols.py`
- **Sync Pattern:** All devices poll `sessions` table for `current_phase` changes

## 4. CRITICAL Technical Constraints (Strict Adherence)
- **Pump Caching:** Re-use connections via `pump_manager.py`. Initialization takes ~21s; DO NOT create new pump instances per cycle.
- **Belt Caching:** Re-use connections via `belt_manager.py`. Arduino resets on serial connect (~2s).
- **Serial Ports:** Pumps share one port; belt uses separate port. Initialize sequentially using locks.
- **Units:**
  - DB/UI = **µL** (microliters)
  - Pump Hardware = **mL** (milliliters) -> `vol_ml = vol_ul / 1000.0`
- **BO Training Data:** Column order MUST match `experiment_config.ingredients` order.
- **Phase Transitions:** Validate via `ExperimentStateMachine.validate_transition()` before updating `current_phase`.

### Common Pitfalls
- ❌ Creating new pump instances per cycle (21s penalty) → ✓ Use `pump_manager.get_or_create_pumps()`
- ❌ Creating new belt instances per cycle → ✓ Use `belt_manager.get_or_create_belt()`
- ❌ Bypassing `validate_transition()` → ✓ Always validate before updating `current_phase`
- ❌ Mixing µL/mL units → ✓ DB/UI uses µL, hardware uses mL (convert with `/1000.0`)
- ❌ Running hardware tests without pumps → ✓ Only run `test_pump_*.py` with physical connection
- ❌ Running belt tests without hardware → ✓ Use `--mock` flag or `test_belt_integration.py`
- ❌ Writing raw SQL in views → ✓ Use `session_repo.py` or `protocol_repo.py` for business logic
- ❌ Updating only `st.session_state` → ✓ Update database first, then sync to Streamlit state

## 5. Phase Flows (Quick Reference)
- **Standard:** WAITING → REGISTRATION → INSTRUCTIONS → SELECTION → LOADING → QUESTIONNAIRE → (loop) → COMPLETE
- **Pump:** WAITING → ... → SELECTION → ROBOT_PREPARING → QUESTIONNAIRE → (loop) → COMPLETE
- **Robot (Pump + Belt):** Same as Pump flow. Belt operations (position → dispense → mix → deliver) happen within ROBOT_PREPARING.

## 6. Development Commands
- **Run App:** `streamlit run main_app.py`
- **Run Pump Service:** `python pump_control_service.py --db-path robotaste.db`
- **Run Belt Service:** `python belt_control_service.py --db-path robotaste.db`
- **Tests:**
  - All: `pytest`
  - Single file: `pytest tests/test_protocol_integration.py`
  - Single test: `pytest tests/test_protocol_integration.py::test_name`
  - By keyword: `pytest -k "protocol"`
  - Belt tests: `pytest tests/test_belt_integration.py`
  - Hardware (Safety): `python robotaste/hardware/test_pump_movement.py`
  - Belt hardware: `python robotaste/hardware/test_belt.py --mock`

## 6.5. Lint / Format
- No lint or formatter configured in-repo.
- Do not add new tooling without explicit request.
- Keep formatting consistent with surrounding code.

## 6.6. Editor / Assistant Rules
- No `.cursorrules`, `.cursor/rules/`, or `.github/copilot-instructions.md` files found.

## 7. Documentation
For deep context on Session Flows, BO Algorithms, or Protocol JSON schemas, refer to `docs/PROJECT_CONTEXT.md` (if created) or the specific file headers.
