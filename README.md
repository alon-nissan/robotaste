# RoboTaste

Multi-device taste experiment platform with Bayesian Optimization and hardware pump control.

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### Installation
```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend && npm install && cd ..
```

### Running the Application (React + FastAPI)

**All-in-one launcher:**
```bash
python start_new_ui.py            # Starts FastAPI + Vite dev server
python start_new_ui.py --with-pump  # Also starts pump control service
```

Or start each service individually:
```bash
# Terminal 1: FastAPI backend (port 8000)
uvicorn api.main:app --reload --port 8000

# Terminal 2: React frontend dev server (port 5173)
cd frontend && npm run dev

# Terminal 3 (optional): Pump service (requires hardware)
python pump_control_service.py --db-path robotaste.db --poll-interval 0.5
```

**Access URLs:**
| Role | URL |
|------|-----|
| Moderator | http://localhost:5173/ |
| Subject | http://localhost:5173/subject |
| API docs | http://localhost:8000/docs |

### Legacy Streamlit UI
```bash
streamlit run main_app.py
```

### Running with ngrok (Multi-Device)
```bash
python start_robotaste.py             # Streamlit + ngrok
python start_robotaste.py --with-pump # With hardware pumps
```
Full setup guide: **[docs/NGROK_SETUP.md](docs/NGROK_SETUP.md)**

### Testing
```bash
pytest                                          # All tests
pytest tests/test_protocol_integration.py       # Specific test
python robotaste/hardware/test_pump_movement.py # Hardware test (requires pumps)
```

## Architecture

```
Browser (localhost:5173)
    │
    ├── React App (TypeScript + Tailwind CSS)
    │   ├── Moderator pages  → Setup, monitoring, protocol management
    │   └── Subject pages    → Consent, registration, selection, questionnaire
    │
    ▼
FastAPI Server (localhost:8000)
    │
    ├── /api/sessions    → Session lifecycle
    ├── /api/protocols   → Protocol CRUD
    ├── /api/pump        → Pump status and refill
    │
    ▼
Python Business Logic (robotaste/)
    │
    ▼
SQLite Database (robotaste.db)
```

## Project Structure
- `start_new_ui.py` - Launcher for React + FastAPI stack
- `frontend/` - React 19 + TypeScript + Tailwind CSS 4.1
  - `src/pages/` - Page components (13 pages)
  - `src/components/` - Reusable UI components
  - `src/types/index.ts` - TypeScript type definitions
  - `src/api/client.ts` - Axios HTTP client
- `api/` - FastAPI backend
  - `main.py` - App entry point
  - `routers/` - Endpoint handlers (sessions, protocols, pump)
- `robotaste/` - Python business logic
  - `config/` - Protocols, questionnaires, BO configuration
  - `core/` - State machine, phase engine, trials, BO, pump manager
  - `data/` - Database layer, repositories, schema
  - `hardware/` - NE-4000 pump serial controller
- `main_app.py` - Legacy Streamlit UI entry point
- `pump_control_service.py` - Background pump control daemon
- `tests/` - Pytest test suite
- `docs/` - Documentation
- `protocols/` - Example protocol JSON files

## Key Capabilities
- Multi-device experiments (moderator + subjects sync via database)
- Protocol-driven workflows with custom phase sequences
- Bayesian Optimization for intelligent sampling
- Hardware integration: NE-4000 syringe pump control (RS-232 serial)
- 2D grid interface (binary mixtures) or 1D sliders (single ingredient)

## Documentation
- **Getting Started**: `docs/NEW_STACK_GUIDE.md`, `docs/WORKFLOW_GUIDE.md`
- **For AI Agents**: `CLAUDE.md`, `AGENTS.md`, `docs/AGENT_EFFICIENCY.md`
- **For Humans**: `docs/PROJECT_CONTEXT.md`, `docs/protocol_user_guide.md`
- **For Researchers**: `docs/protocol_schema.md`, `docs/pump_config.md`
- **UI Guidelines**: `frontend/DESIGN_GUIDELINES.md`

## Hardware Requirements
- NE-4000 syringe pumps (optional, for automated dispensing)
- RS-232 serial connection (USB-to-serial adapter supported)
- Syringe diameter: 26.7mm recommended

## Critical Notes
- **Units**: UI/DB uses microliters (µL), pumps use milliliters (mL)
- **Pump init time**: First cycle ~21s, subsequent cycles instant (connection caching)
- **Phase validation**: Always use `ExperimentStateMachine.validate_transition()`
- **BO column order**: Must match `experiment_config.ingredients` order
