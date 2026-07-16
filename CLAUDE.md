# CLAUDE.md

## 1. Style & Behavior
- **No Conversational Filler:** Never write "Here is...", "I've updated...", "Let me..." before tool calls. Just do the action.
- **Diffs Only:** Show ONLY changed blocks with 2-3 lines context. Never reprint unchanged functions.
- **General Logic, Not Code:** Explain approach in bullet points, not line-by-line code walkthrough.
- **Concise Questions:** Ask 1-2 focused questions maximum per turn.
- **Imports:** Do not hallucinate dependencies. Python: `pyserial`, `pandas`, `numpy`, `scipy`, `scikit-learn`, `fastapi`, `uvicorn`, `pydantic`. Frontend: `react`, `react-router-dom`, `axios`, `tailwindcss`, `recharts`.

## 2. Project Type
Multi-device taste experiment platform: React (Vite) frontend + FastAPI backend. Moderator + subjects
sync via API polling against a shared SQLite database. Optional NE-4000 pump hardware. Optional
Bayesian Optimization (BO) mode auto-selects the next sample instead of the subject picking manually.

## 2.5. Quick File Lookup
Map common tasks to exact file paths (use these before exploring). **There is no Streamlit UI** —
`main_app.py` and `robotaste/views/` do not exist; the moderator and subject UI are 100% React.
- **Phase transitions** → `robotaste/core/state_machine.py`
- **Protocol logic** → `robotaste/core/phase_engine.py`, `robotaste/config/protocols.py`
- **BO algorithm (GP, acquisition functions)** → `robotaste/core/bo_engine.py`
- **BO suggestion generation (per-cycle)** → `robotaste/core/bo_integration.py`
- **BO training data (DB → DataFrame)** → `robotaste/data/database.py` (`get_training_data()`)
- **BO monitoring/convergence metrics** → `robotaste/core/bo_utils.py` (`get_convergence_metrics()`, `check_convergence()`)
- **Pump hardware** → `robotaste/hardware/pump_controller.py`
- **Pump caching** → `robotaste/core/pump_manager.py`
- **Database (SQL)** → `robotaste/data/database.py`
- **Database (business logic)** → `robotaste/data/session_repo.py`, `robotaste/data/protocol_repo.py`
- **Moderator setup UI** → `frontend/src/pages/ModeratorSetupPage.tsx`
- **Moderator monitoring UI** → `frontend/src/pages/ModeratorMonitoringPage.tsx`
- **BO monitoring graphs (moderator view)** → `frontend/src/components/BOProgressChart.tsx` (progress line chart), `BOVisualization1D.tsx` / `BOVisualization2D.tsx` (GP response-surface)
- **Subject selection UI (incl. BO auto-apply)** → `frontend/src/pages/SelectionPage.tsx`
- **Subject questionnaire UI** → `frontend/src/pages/QuestionnairePage.tsx`
- **Questionnaires** → `robotaste/config/questionnaire.py`
  - **Note:** Questionnaires support inline configuration in protocols (preferred, incl. `bayesian_target`) or legacy library-based lookup by name (deprecated fallback)
- **Trials management (per-cycle sample prep)** → `robotaste/core/trials.py` (`prepare_cycle_sample()`)
- **Pump operations** → `robotaste/core/pump_integration.py`
- **Protocol schema** → `robotaste/config/protocol_schema.py`
- **Sample storage** → `robotaste/utils/pump_db.py`
- **React app router** → `frontend/src/App.tsx`
- **React page layout** → `frontend/src/components/PageLayout.tsx`
- **React error boundary** → `frontend/src/components/ErrorBoundary.tsx` (catches render crashes app-wide)
- **React pages** → `frontend/src/pages/*.tsx`
- **TypeScript types** → `frontend/src/types/index.ts`
- **API client (frontend)** → `frontend/src/api/client.ts`
- **FastAPI app** → `api/main.py`
- **Session API endpoints (incl. BO: bo-suggestion, bo-status, bo-model)** → `api/routers/sessions.py`
- **Protocol API endpoints** → `api/routers/protocols.py`
- **Pump API endpoints** → `api/routers/pump.py`
- **Analysis API endpoints** → `api/routers/analysis.py`
- **Dose-response dashboard** → `frontend/src/pages/DoseResponseDashboardPage.tsx`
- **Design guidelines** → `docs/DESIGN_GUIDELINES.md`
- **Workflow guide** → `docs/WORKFLOW_GUIDE.md`

## 3. Key Architecture & Entry Points
- **React Frontend:** `frontend/src/App.tsx` (Vite + React 19 + TypeScript + Tailwind 4.1)
- **FastAPI Backend:** `api/main.py` (port 8000; in production also serves the built `frontend/dist/` via `StaticFiles`)
- **Service:** `pump_control_service.py` (Background hardware daemon)
- **State:** `robotaste/core/state_machine.py` (Phase transitions)
- **DB:** `robotaste.db` (SQLite) | Schema: `robotaste/data/schema.sql`
- **Protocol:** `robotaste/config/protocols.py`
- **Sync Pattern:** Subject pages poll API endpoints (e.g. `/sessions/{id}/status`, `/cycle-info`); moderator monitoring polls `/sessions/{id}/status` + `/samples` + BO endpoints
- **BO auto-apply:** `bo_selected` cycles are resolved and submitted automatically (no manual subject pick) — see `robotaste/core/trials.py::prepare_cycle_sample()` and the auto-submit effect in `SelectionPage.tsx` / `QuestionnairePage.tsx`. There is no separate "BO phase"; it's a selection *mode* within the existing `selection` phase.

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
- ❌ Using raw hex colors in React → ✓ Use Tailwind design tokens from `docs/DESIGN_GUIDELINES.md`
- ❌ Defining types in page files → ✓ Add to `frontend/src/types/index.ts`
- ❌ Direct `fetch()` calls → ✓ Use `api` from `frontend/src/api/client.ts`
- ❌ Forgetting `showLogo={false}` on subject experiment pages → ✓ Only consent/registration/instructions show logo
- ❌ Hardcoding a BO target column name or `ing["min_concentration"]` key → ✓ Target column comes from `get_training_data(...).columns[-1]` (matches the protocol's inline `bayesian_target`); ingredient ranges via `get_ingredient_range()` in `bo_integration.py` (handles both `min_concentration` and `min_concentration_mM`)
- ❌ Computing a BO suggestion (`predicted_value`/`uncertainty`/`acquisition_value`) without persisting it → ✓ Thread it through as `selection_data` from `prepare_cycle_sample()` → `submit_selection`/`submit_response` → `save_sample_cycle()`, or `samples.acquisition_*` columns stay NULL and BO monitoring graphs stay empty

## 5. Phase Flows (Quick Reference)
- **Standard:** WAITING → REGISTRATION → INSTRUCTIONS → SELECTION → LOADING → QUESTIONNAIRE → (loop) → COMPLETE
- **Pump:** WAITING → ... → SELECTION → ROBOT_PREPARING → QUESTIONNAIRE → (loop) → COMPLETE

## 6. Development Commands
- **Run Pump Service:** `python pump_control_service.py --db-path robotaste.db`
- **Tests:**
  - All: `pytest`
  - Single file: `pytest tests/test_protocol_integration.py`
  - Single test: `pytest tests/test_protocol_integration.py::test_name`
  - By keyword: `pytest -k "protocol"`
  - Hardware (Safety): `python robotaste/hardware/test_pump_movement.py`
- **React dev**: `cd frontend && npm run dev` (port 5173)
- **React build**: `cd frontend && npm run build`
- **React type-check**: `cd frontend && npx tsc --noEmit`
- **FastAPI**: `uvicorn api.main:app --reload --port 8000`

## 6.5. Lint / Format
- No lint or formatter configured in-repo.
- Do not add new tooling without explicit request.
- Keep formatting consistent with surrounding code.

## 6.6. Editor / Assistant Rules
- No `.cursorrules`, `.cursor/rules/`, or `.github/copilot-instructions.md` files found.

## 7. Documentation
For deep context on Session Flows, BO Algorithms, or Protocol JSON schemas, refer to `docs/WORKFLOW_GUIDE.md`, `docs/protocol_schema.md`, or the specific file headers.
