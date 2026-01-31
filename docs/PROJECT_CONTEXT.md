# Project Context & Architecture

## Project Overview
RoboTaste is a multi-device interactive experiment platform for taste preference studies. It supports binary mixtures (2D grid) and single-variable experiments (slider), with optional automated hardware pump control for precise solution dispensing.

**Key Capabilities:**
- Multi-device experiments: moderator configures trials, subjects respond on separate devices
- Session-based synchronization via SQLite database
- Protocol-driven experiment workflows with custom phase sequences
- Hardware integration: NE-4000 syringe pump control via RS-232 serial
- Bayesian Optimization for intelligent sampling
- Streamlit-based UI

## Development Commands

### Running the Application
```bash
# Main Streamlit application (moderator/subject interface)
streamlit run main_app.py

# Pump control service (separate process, runs on hardware-connected machine)
python pump_control_service.py --db-path robotaste.db --poll-interval 0.5

# Belt control service (separate process, runs on belt-connected machine)
python belt_control_service.py --db-path robotaste.db --poll-interval 0.5
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_protocol_integration.py

# Integration tests with hardware (requires physical pump connection)
python robotaste/hardware/test_pump_movement.py
python robotaste/hardware/test_dual_pump.py
```

## Architecture

### Core Design Pattern: Database-Centric Multi-Device Synchronization
RoboTaste uses a **shared SQLite database** as the central coordination mechanism between:
1. **Moderator device** (Streamlit app) - configures experiments, monitors progress
2. **Subject device(s)** (Streamlit app) - participants make selections and answer questionnaires
3. **Pump control service** (Python daemon) - executes hardware dispensing operations

All devices poll the database for state changes. Session state is stored in the `sessions` table.

### Multi-Device Synchronization Flow Diagram
```
Moderator (Streamlit)          Database (SQLite)           Subject (Streamlit)           Pump Service (Python)
       │                              │                            │                              │
       ├─ UPDATE sessions ────────────►                            │                              │
       │  SET current_phase=SELECTION  │                            │                              │
       │                              │                            │                              │
       │                              │ ◄──── SELECT current_phase ┤                              │
       │                              │       (polls every 5s)      │                              │
       │                              │                            │                              │
       │                              │                            ├─ User clicks grid (x,y)      │
       │                              │ ◄──── INSERT samples ──────┤                              │
       │                              │                            │                              │
       ├─ UPDATE sessions ────────────►                            │                              │
       │  SET current_phase=ROBOT_PREP │                            │                              │
       │                              │                            │                              │
       │  INSERT pump_operations ──────►                            │                              │
       │  (recipe_json)                │                            │                              │
       │                              │                            │                              │
       │                              │ ◄──── SELECT pending ───────────────────────────────────────┤
       │                              │       pump_operations       │                              │
       │                              │                            │                              ├─ Dispense sample
       │                              │ ◄──── UPDATE completed ─────────────────────────────────────┤
       │                              │                            │                              │
```

### State Machine & Phase Flow
Experiment progression is governed by `robotaste/core/state_machine.py` (`ExperimentStateMachine`):

**Standard Flow (Non-Pump):**
WAITING → REGISTRATION → INSTRUCTIONS → SELECTION → LOADING → QUESTIONNAIRE → (loop) → COMPLETE

**Pump-Enabled Flow:**
WAITING → REGISTRATION → INSTRUCTIONS → SELECTION → ROBOT_PREPARING → QUESTIONNAIRE → (loop) → COMPLETE

**Robot Flow (Pump + Belt):**
Same as Pump flow. During ROBOT_PREPARING, the robot orchestrator coordinates:
1. Belt positions cup at spout
2. Pump dispenses sample
3. Belt performs mixing oscillations
4. Belt moves cup to display area

### Hardware Pump Control
- **Service:** `pump_control_service.py` monitors `pump_operations` table
- **Controller:** `robotaste/hardware/pump_controller.py` handles NE-4000 serial comms
- **Manager:** `robotaste/core/pump_manager.py` handles connection caching

**Burst Mode:** Enables simultaneous dispensing from multiple pumps using NE-4000 Network Command Burst protocol (addresses 0-9 only).

### Hardware Conveyor Belt Control
- **Service:** `belt_control_service.py` monitors `belt_operations` table
- **Controller:** `robotaste/hardware/belt_controller.py` handles Arduino serial comms
- **Manager:** `robotaste/core/belt_manager.py` handles connection caching
- **Orchestrator:** `robotaste/core/robot_orchestrator.py` coordinates pump + belt

**Belt Commands:**
- `MOVE_TO_SPOUT` - Position next cup under dispensing spout
- `MOVE_TO_DISPLAY` - Move current cup to subject pickup area
- `MIX <count>` - Perform oscillation mixing movements
- `STATUS` - Query current belt position

## Key Architectural Decisions

### Why Database Polling Instead of WebSockets?
- **Simplicity**: No server infrastructure, no connection management
- **Reliability**: Works across networks, survives disconnections
- **Multi-process**: Separate pump service process needs shared state
- **Portability**: SQLite file-based, no server setup required

### Why Pump Connection Caching?
- **Performance**: Initialization takes ~21 seconds per pump
- **User experience**: First cycle = 21s, subsequent cycles = 0s (25% time savings)
- **Implementation**: `pump_manager.py` maintains session-persistent connections

### Why Streamlit?
- **Rapid prototyping**: Research tool needs fast iteration
- **Python ecosystem**: Direct access to scikit-learn, numpy, pandas for BO
- **Multi-page**: Native support for moderator/subject interfaces

### Why SQLite?
- **Portability**: Single file, no server, cross-platform
- **Sufficient performance**: ~20 samples/session, <100 sessions typical
- **Development**: Easy to inspect/debug with DB Browser

### Why Serial Communication for Pumps?
- **Hardware constraint**: NE-4000 pumps only support RS-232 serial protocol
- **Network Command Burst**: Proprietary protocol for simultaneous dispensing

### Bayesian Optimization Integration
- Training data: `samples` table (`ingredient_concentration` + `questionnaire_answer`)
- BO engine: `robotaste/core/bo_integration.py` using scikit-optimize
- Configuration: Stored per-session in `bo_configuration` table.

## Package Structure
```
robotaste/
├── components/     # Reusable Streamlit UI components
├── config/         # Protocol definitions, questionnaire configs, BO defaults
├── core/           # Business logic: state machine, trials, BO, pump integration
├── data/           # Database layer: schema.sql, database.py, repositories
├── hardware/       # NE-4000 pump controller, serial communication
├── utils/          # Logging, viewport detection, utilities
└── views/          # Streamlit pages: landing, moderator, subject, questionnaire
```

## Database Tables
- `sessions`: Experiment sessions (session_code, protocol_id, current_phase)
- `samples`: One row per cycle (ingredient_concentration, questionnaire_answer)
- `protocol_library`: Reusable protocol templates
- `pump_operations`: Pending/in-progress/completed dispensing operations
- `belt_operations`: Pending/in-progress/completed belt positioning/mixing operations
- `belt_logs`: Belt operation debug logs
- `bo_configuration`: BO hyperparameters per session

## Troubleshooting Index

| Issue | Likely Cause | File to Check |
|-------|-------------|---------------|
| Pump not responding | Serial config, baud rate, port | `robotaste/hardware/pump_controller.py:150` |
| Belt not responding | Serial config, Arduino port | `robotaste/hardware/belt_controller.py` |
| Invalid phase transition | Missing entry in VALID_TRANSITIONS | `robotaste/core/state_machine.py:45` |
| BO not suggesting | Column order mismatch, <3 samples | `robotaste/core/bo_integration.py:80`, check `samples` table |
| Devices out of sync | Polling not running | `robotaste/data/session_repo.py` (`sync_session_state_to_streamlit()`) |
| Units wrong | µL/mL conversion missing | `robotaste/core/pump_integration.py` (`calculate_volumes()`) |
| Phase validation error | Protocol phase_sequence invalid | `robotaste/config/protocol_schema.py`, `robotaste/core/phase_engine.py` |
| Belt mixing fails | Arduino timeout, mixing oscillations | `robotaste/core/belt_integration.py` |
| Robot cycle fails | Pump or belt error | `robotaste/core/robot_orchestrator.py` |

## Multi-Device Session Flow
1. **Moderator**: Creates session → `session_code` generated.
2. **Moderator**: Selects protocol → `update_session_with_config()`.
3. **Subject**: Joins via code → `join_session()` → syncs to state.
4. **Subject**: Makes selection → stored in session state.
5. **Moderator**: Confirms → creates pump operation.
6. **Pump Service**: Executes dispensing → marks complete.
7. **Subject**: Answers questionnaire → saves to `samples` → next cycle.

## Common Development Tasks

### Adding a New Questionnaire Type
1. Define in `robotaste/config/questionnaire.py`
2. Add to `questionnaire_types` table
3. Specify `bayesian_target` for BO integration

### Creating a New Protocol
1. Define JSON in `robotaste/config/protocols.py`
2. Use `save_protocol()` in `robotaste/data/protocol_repo.py`

### Modifying Phase Flow
1. **Standard flow**: Update `VALID_TRANSITIONS` in `state_machine.py`
2. **Protocol flow**: Define custom `phase_sequence` in protocol JSON

## Important Implementation Details

### Pump Connection Caching
`pump_manager.py` maintains session-persistent pump connections. First cycle initialization takes ~21s; subsequent cycles are instant. **DO NOT** create new pump instances per cycle.

### Belt Connection Caching
`belt_manager.py` maintains session-persistent belt connections. Arduino may reset on serial connect (~2s). Use `belt_manager.get_or_create_belt()` to reuse connections.

### Serial Port Conflicts
Daisy-chained pumps share a single serial port. Belt uses a separate dedicated serial port. Use `_serial_port_lock` in `pump_controller.py` and `_belt_serial_lock` in `belt_controller.py` to prevent conflicts.

### Volume Units
- UI/Database: **microliters (µL)**
- Pump Hardware: **milliliters (mL)**
- Conversion: `volume_ml = volume_ul / 1000.0`

### BO Training Data Order
Ingredient columns MUST match `experiment_config.ingredients` order.
