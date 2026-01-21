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

### State Machine & Phase Flow
Experiment progression is governed by `robotaste/core/state_machine.py` (`ExperimentStateMachine`):

**Standard Flow (Non-Pump):**
WAITING → REGISTRATION → INSTRUCTIONS → SELECTION → LOADING → QUESTIONNAIRE → (loop) → COMPLETE

**Pump-Enabled Flow:**
WAITING → REGISTRATION → INSTRUCTIONS → SELECTION → ROBOT_PREPARING → QUESTIONNAIRE → (loop) → COMPLETE

### Hardware Pump Control
- **Service:** `pump_control_service.py` monitors `pump_operations` table
- **Controller:** `robotaste/hardware/pump_controller.py` handles NE-4000 serial comms
- **Manager:** `robotaste/core/pump_manager.py` handles connection caching

**Burst Mode:** Enables simultaneous dispensing from multiple pumps using NE-4000 Network Command Burst protocol (addresses 0-9 only).

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
- `bo_configuration`: BO hyperparameters per session

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

### Serial Port Conflicts
Daisy-chained pumps share a single serial port. Use `_serial_port_lock` in `pump_controller.py` to prevent conflicts.

### Volume Units
- UI/Database: **microliters (µL)**
- Pump Hardware: **milliliters (mL)**
- Conversion: `volume_ml = volume_ul / 1000.0`

### BO Training Data Order
Ingredient columns MUST match `experiment_config.ingredients` order.
