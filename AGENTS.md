# AGENTS.md

This file is guidance for agentic coding tools working in this repo.
Focus on correctness, hardware safety, and adherence to the experiment flow.

## Quick Orientation
- App entrypoint: `main_app.py` (Streamlit UI).
- React frontend: `frontend/` (Vite + React 19 + TypeScript + Tailwind 4.1)
- FastAPI backend: `api/main.py` (serves at port 8000)
- API routers: `api/routers/sessions.py`, `api/routers/protocols.py`, `api/routers/pump.py`
- Frontend pages: `frontend/src/pages/` (13 page components)
- Frontend components: `frontend/src/components/` (reusable React components)
- Design guidelines: `frontend/DESIGN_GUIDELINES.md`
- Workflow guide: `docs/WORKFLOW_GUIDE.md`
- Pump daemon: `pump_control_service.py` (hardware-connected machine).
- State machine: `robotaste/core/state_machine.py`.
- DB: `robotaste.db` (SQLite); schema in `robotaste/data/schema.sql`.
- Protocols: `robotaste/config/protocols.py` and `robotaste/config/protocol_schema.py`.
- Docs: `docs/PROJECT_CONTEXT.md`, `docs/protocol_schema.md`, `docs/protocol_user_guide.md`.

## Navigation Quick Reference

### By Task Type
| Task | Primary Files | Helper Files |
|------|--------------|--------------|
| Add protocol feature | `robotaste/config/protocols.py`, `robotaste/config/protocol_schema.py` | `robotaste/data/protocol_repo.py` |
| Modify phase flow | `robotaste/core/state_machine.py`, `robotaste/core/phase_engine.py` | `robotaste/views/phase_utils.py` |
| Change UI behavior | `robotaste/views/moderator.py` or `robotaste/views/subject.py` | `robotaste/components/`, `robotaste/views/moderator_views.py` |
| Fix BO issues | `robotaste/core/bo_engine.py`, `robotaste/core/bo_integration.py` | `robotaste/core/bo_utils.py`, `robotaste/config/bo_config.py` |
| Pump problems | `robotaste/hardware/pump_controller.py`, `robotaste/core/pump_manager.py` | `robotaste/core/pump_integration.py`, `robotaste/utils/pump_db.py` |
| Database queries | `robotaste/data/database.py` (low-level SQL) | `robotaste/data/session_repo.py`, `robotaste/data/protocol_repo.py` |
| Questionnaire changes | `robotaste/views/questionnaire.py`, `robotaste/config/questionnaire.py` | `robotaste/data/database.py` (save logic) |
| Change React UI page    | `frontend/src/pages/<PageName>.tsx`          | `frontend/src/components/`, `frontend/src/types/index.ts` |
| Add/modify API endpoint | `api/routers/sessions.py` or `api/routers/protocols.py` | `robotaste/data/database.py`, `robotaste/data/session_repo.py` |
| Change frontend routing | `frontend/src/App.tsx`                       | `frontend/src/pages/` |
| Frontend styling/layout | `frontend/src/components/PageLayout.tsx`     | `frontend/DESIGN_GUIDELINES.md`, `frontend/src/index.css` |

### By Component
- **Entry points**: `main_app.py` (UI), `pump_control_service.py` (daemon)
- **State management**: `robotaste/core/state_machine.py` (validation), `robotaste/core/phase_engine.py` (sequencing)
- **Data layer**: `robotaste/data/database.py` (low-level SQL), `robotaste/data/session_repo.py` (business logic)
- **Hardware**: `robotaste/hardware/pump_controller.py` (serial), `robotaste/core/pump_manager.py` (caching)
- **Trials**: `robotaste/core/trials.py` (BO suggestions, sample tracking)
- **Views**: `robotaste/views/moderator.py` (moderator UI), `robotaste/views/subject.py` (subject UI)
- **Components**: `robotaste/components/` (reusable UI widgets)
- **React entry point**: `frontend/src/App.tsx` (router), `frontend/src/main.tsx` (bootstrap)
- **React pages**: `frontend/src/pages/` — 13 page components (LandingPage, ConsentPage, RegistrationPage, etc.)
- **React components**: `frontend/src/components/` — PageLayout, ProtocolSelector, PumpSetup, BOVisualization1D/2D, etc.
- **TypeScript types**: `frontend/src/types/index.ts` — Session, Protocol, Participant, etc.
- **API client**: `frontend/src/api/client.ts` — Axios instance (baseURL: /api)
- **FastAPI app**: `api/main.py` — Registers routers, CORS, static files
- **API routers**: `api/routers/sessions.py` (15 endpoints), `api/routers/protocols.py`, `api/routers/pump.py`

## Build / Run Commands
- **App UI**: `streamlit run main_app.py`
- **Pump service**: `python pump_control_service.py --db-path robotaste.db --poll-interval 0.5`
- **React frontend (dev)**: `cd frontend && npm run dev` (port 5173, hot reload)
- **React frontend (build)**: `cd frontend && npm run build` (outputs to frontend/dist/)
- **React frontend (type-check)**: `cd frontend && npx tsc --noEmit`
- **FastAPI backend**: `uvicorn api.main:app --reload --port 8000`
- **Full stack**: Run FastAPI (port 8000) + Vite dev (port 5173) + pump service concurrently
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

## Editor / Assistant Rules
- No `.cursorrules`, `.cursor/rules/`, or `.github/copilot-instructions.md` files found.

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

### TypeScript / React (frontend/)
- Use functional components with hooks (no class components).
- Follow existing PageLayout pattern: wrap every page in `<PageLayout>` (accepts `showLogo?: boolean`).
- Moderator pages: `showLogo` defaults to `true`. Subject experiment pages (Selection, Questionnaire, RobotPreparing, Completion, CustomPhase): pass `showLogo={false}`.
- Use Tailwind CSS design tokens defined in `frontend/DESIGN_GUIDELINES.md` — do not use raw hex colors.
- API calls go through the shared Axios client: `import { api } from '../api/client'`.
- Types live in `frontend/src/types/index.ts` — add new interfaces there, not in page files.
- Use `useNavigate()` from React Router for page transitions.
- Use `useParams()` to read URL parameters like `:sessionId`.

### FastAPI (api/)
- Each router file in `api/routers/` handles one resource (sessions, protocols, pump).
- Request bodies use Pydantic `BaseModel` classes defined at the top of the router file.
- Reuse existing `robotaste.data.database` functions — do not write raw SQL in router handlers.
- Always validate session existence before operating on it (return 404 if not found).

### Hardware / Pump Integration
- Never create new pump instances per cycle; reuse cached manager instances.
- Serial init must be sequential to avoid port conflicts.
- When in doubt, treat pump commands as slow/unsafe operations.

## Project Conventions
- Protocols are JSON-like dicts; validation is in `robotaste/config/protocols.py`.
- `robotaste/core/phase_engine.py` handles protocol-defined phases.
- Tests live in `tests/` and should be small, isolated, and DB-clean.

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

### React Frontend Routing Pattern
- **Moderator flow**: `/` → `/moderator/setup` → `/moderator/monitoring`
- **Subject flow**: `/subject` (auto-join) → `/subject/{sessionId}/consent` → `/subject/{sessionId}/register` → `.../instructions` → `.../select` → `.../questionnaire` → `.../complete`
- **Subject auto-connect**: `/subject` route polls `GET /api/sessions` for active sessions, auto-redirects when exactly 1 session found (matches Streamlit auto-join behavior)
- **Logo visibility**: Moderator pages always show logo. Subject pages show logo only on consent, registration, instructions.

## What Not To Do
- Do not add dependencies or tooling without asking.
- Do not run hardware tests unless explicitly requested.
- Do not bypass phase validation or pump safety constraints.
- Do not remove existing user changes in unrelated files.

## If You Need More Context
- Read `CLAUDE.md` for repo-specific constraints and instructions.
