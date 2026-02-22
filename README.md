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

**Production mode (multi-device, LAN):**
```bash
python start_new_ui.py                # Builds frontend, serves on LAN
python start_new_ui.py --with-pump    # Also starts pump control service
```
On startup, the terminal shows the subject URL and a QR code for the tablet.

**Development mode (localhost only):**
```bash
python start_new_ui.py --dev          # Vite hot-reload + FastAPI
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
| Moderator (this computer) | http://localhost:8000/ |
| Subject (tablet, LAN) | http://\<LAN-IP\>:8000/subject |
| API docs | http://localhost:8000/docs |
| Dev mode (Vite) | http://localhost:5173/ |

### Multi-Device Setup (Moderator + Tablet)

Both devices must be on the same WiFi network. In production mode (`python start_new_ui.py`),
the server binds to `0.0.0.0:8000` and serves both the API and the React frontend.
The startup output shows the subject URL and QR code for the tablet.

If your organization's network blocks device-to-device traffic, use a personal hotspot instead.

See **[docs/MULTI_DEVICE_SETUP.md](docs/MULTI_DEVICE_SETUP.md)** for full instructions.

### Legacy Streamlit UI
```bash
streamlit run main_app.py
```

### Legacy: Running with ngrok (Streamlit only, deprecated)
```bash
python start_robotaste.py             # Streamlit + ngrok
python start_robotaste.py --with-pump # With hardware pumps
```
See **[docs/NGROK_SETUP.md](docs/NGROK_SETUP.md)** (deprecated — use LAN setup above instead).

### Testing
```bash
pytest                                          # All tests
pytest tests/test_protocol_integration.py       # Specific test
python robotaste/hardware/test_pump_movement.py # Hardware test (requires pumps)
```

## Architecture

```
Browser (moderator: localhost:8000, subject: <LAN-IP>:8000)
    │
    ├── React App (TypeScript + Tailwind CSS)
    │   ├── Moderator pages  → Setup, monitoring, protocol management
    │   └── Subject pages    → Consent, registration, selection, questionnaire
    │
    ▼
FastAPI Server (0.0.0.0:8000 — serves API + React frontend)
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
