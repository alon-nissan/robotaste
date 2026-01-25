# RoboTaste

Multi-device taste experiment platform with Bayesian Optimization and hardware pump control.

## Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Running with ngrok (Multi-Device)
```bash
# Single command - starts Streamlit + ngrok
python start_robotaste.py

# With hardware pumps
python start_robotaste.py --with-pump
```

Full setup guide: **[docs/NGROK_SETUP.md](docs/NGROK_SETUP.md)**

### Running Locally (Same Computer)
```bash
# Terminal 1: Web application
streamlit run main_app.py

# Terminal 2: Pump service (optional, requires hardware)
python pump_control_service.py --db-path robotaste.db
```

### Testing
```bash
pytest                                          # All tests
pytest tests/test_protocol_integration.py       # Specific test
python robotaste/hardware/test_pump_movement.py # Hardware test (requires pumps)
```

## Project Structure
- `main_app.py` - Streamlit UI entry point (moderator & subject interfaces)
- `pump_control_service.py` - Background pump control daemon
- `robotaste/`
  - `config/` - Protocols, questionnaires, BO configuration
  - `core/` - State machine, phase engine, trials, BO, pump manager
  - `data/` - Database layer, repositories, schema
  - `hardware/` - NE-4000 pump serial controller
  - `views/` - Streamlit pages (moderator, subject, questionnaire)
  - `components/` - Reusable UI components
  - `utils/` - Logging, viewport, visualization
- `tests/` - Pytest test suite
- `docs/` - Documentation

## Key Capabilities
- Multi-device experiments (moderator + subjects sync via database)
- Protocol-driven workflows with custom phase sequences
- Bayesian Optimization for intelligent sampling
- Hardware integration: NE-4000 syringe pump control (RS-232 serial)
- 2D grid interface (binary mixtures) or 1D sliders (single ingredient)

## Documentation
- **For AI Agents**: `CLAUDE.md`, `AGENTS.md`, `docs/AGENT_EFFICIENCY.md`
- **For Humans**: `docs/PROJECT_CONTEXT.md`, `docs/protocol_user_guide.md`
- **For Researchers**: `docs/protocol_schema.md`, `docs/pump_config.md`

## Hardware Requirements
- NE-4000 syringe pumps (optional, for automated dispensing)
- RS-232 serial connection (USB-to-serial adapter supported)
- Syringe diameter: 26.7mm recommended

## Critical Notes
- **Units**: UI/DB uses microliters (µL), pumps use milliliters (mL)
- **Pump init time**: First cycle ~21s, subsequent cycles instant (connection caching)
- **Phase validation**: Always use `ExperimentStateMachine.validate_transition()`
- **BO column order**: Must match `experiment_config.ingredients` order
