# CLAUDE.md

## 1. Style & Behavior
- **Be Concise:** No "Here is the code," "I've updated the file," or conversational filler. Just the code/answer.
- **Diffs Only:** When updating code, show *only* the modified blocks with context headers. Do not reprint unchanged functions.
- **Imports:** Do not hallucinate dependencies. Use existing `pyserial`, `streamlit`, `pandas`.

## 2. Project Type
Multi-device taste experiment platform. Moderator + subjects sync via database polling. Optional NE-4000 pump hardware.

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