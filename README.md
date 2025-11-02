# RoboTaste - Multi-Device Taste Preference Research Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: Academic](https://img.shields.io/badge/License-Academic-green.svg)](LICENSE)

> **A sophisticated research-grade platform for conducting taste preference experiments with real-time multi-device synchronization. Built on Streamlit with centralized state management, dual interface support (2D grid & sliders), database-driven customization, and comprehensive research-ready data export.**

**Total Codebase:** 6,900+ lines of well-structured Python code | **Version:** 2.0 | **Status:** Production Ready

## What is RoboTaste?

RoboTaste is a **Masters-level taste perception research platform** designed to revolutionize how multi-ingredient taste preference experiments are conducted. Built on modern web technologies, it enables researchers to run sophisticated taste studies with **real-time multi-device synchronization**, where moderators monitor participants remotely while collecting comprehensive, research-grade data.

### Key Innovations

**Centralized State Management** - Industry-grade state machine (ExperimentStateMachine) validates all phase transitions with atomic database synchronization, ensuring data integrity across all connected devices.

**Dual Interface Architecture** - Automatically selects optimal interface based on ingredient count: 2D coordinate grid for binary mixtures, independent sliders for 3-6 ingredient experiments.

**Database-Driven Customization** - Custom initial slider positions set per participant, stored in SQLite database with automatic schema migrations and live monitoring views.

**Research-Grade Data Collection** - Millisecond-precision timing, complete interaction history, questionnaire integration, and export-ready CSV format for statistical analysis.

## Core Features

### Intelligent Interface Selection
- **2D Grid Interface** - For 2-ingredient experiments (e.g., Sugar + Salt)
  - Three concentration mapping methods: Linear, Logarithmic, Exponential
  - Visual selection history with canvas drawing
  - Concentration ranges based on Breslin taste perception research

- **Slider Interface** - For 3-6 ingredient experiments
  - Supports: Sugar, Salt, Citric Acid, Caffeine, Vanilla, Menthol
  - Database-driven custom starting positions per participant
  - Real-time percentage display (internal mM calculations)
  - Mixer-board styling for intuitive control

### Real-Time Multi-Device Synchronization
- **Session-based architecture** with unique 6-character codes
- **QR code generation** for mobile device pairing
- **Live connection tracking** with 30-second heartbeat monitoring
- **Phase recovery** on browser reload
- **Automatic session cleanup** (24-hour expiry)

### Advanced State Management
- **8 Experiment Phases:** Waiting → Trial Started → Subject Welcome → Pre-Questionnaire → Trial Active → Post-Response → Post-Questionnaire → Complete
- **Validated transitions** prevent invalid state changes
- **Atomic database sync** ensures consistency
- **Phase indicators** with color coding for status visualization

### Comprehensive Data Collection
- **Individual ingredient concentrations** (mM values for 2-6 ingredients)
- **Reaction times** with millisecond precision
- **Complete selection history** with timestamps
- **Questionnaire responses** in JSON format
- **Interface metadata** (type, method, coordinates)
- **Export-ready CSV** for SPSS, R, Python analysis

### Research-Ready Analytics
- **Live monitoring views** - SQL views for real-time position tracking
- **Connection status dashboard** - Track participant engagement
- **Visual grid display** - See participant selections in real-time
- **Stock volume calculations** - Solution preparation guidance
- **Multi-session support** - Run concurrent experiments

## Quick Start

### Prerequisites
- Python 3.8 or higher
- Modern web browser (Chrome, Firefox, Safari, Edge recommended)
- 4GB RAM minimum (8GB recommended for large datasets)
- Network access for multi-device experiments

### Installation
```bash
# Clone repository
git clone <repository_url>
cd RoboTaste/Software

# Install dependencies
pip install -r requirements.txt

# Run application locally
streamlit run main_app.py
```

Visit `http://localhost:8501` to access the platform.

### Multi-Device Setup
For experiments across multiple devices (recommended for research):
```bash
# Run on network interface
streamlit run main_app.py --server.address 0.0.0.0 --server.port 8501
```

**Access Instructions:**
- **Moderator**: Navigate to `http://<host_ip>:8501` to create and manage sessions
- **Participants**: Join using session code or scan QR code on any device
- **Network**: Ensure all devices are on the same network or use Streamlit Cloud deployment

## 📖 Documentation

### 📁 **Complete Documentation**
- **[📚 Documentation Hub](docs/README.md)** - Complete documentation index
- **[⚡ Quick API Reference](docs/API_REFERENCE.md)** - Function usage and examples
- **[🗄️ Database Schema](docs/DATABASE_SCHEMA.md)** - Complete database documentation
- **[🚀 Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Setup and deployment instructions

### 🔧 **Implementation Details**
- **[✅ Three Critical Fixes](docs/THREE_FIXES_COMPLETE.md)** - Major implementation improvements
- **[🎛️ Slider Fix Summary](docs/SLIDER_FIX_SUMMARY.md)** - Slider response database recording
- **[🐛 Error Fix Details](docs/UNBOUNDLOCALERROR_FIX.md)** - Scope issue resolution

## Technology Stack

### Core Framework
- **Streamlit 1.49.1+** - Modern web application framework with real-time updates
- **Python 3.8+** - Programming language foundation

### Data & Storage
- **SQLite3** - Embedded database with automatic schema migrations
- **Pandas 1.5.3+** - Data manipulation and CSV export

### UI & Visualization
- **Plotly 5.17.0+** - Interactive charts and real-time graphs
- **Streamlit-Drawable-Canvas 0.9.3+** - 2D grid interface with drawing capabilities
- **Streamlit-Vertical-Slider 2.5.5+** - Professional mixer-board style sliders
- **Streamlit-Toggle 0.1.3+** - Toggle switches for settings
- **Streamlit-Space 0.1.5+** - Layout spacing components

### Utilities
- **QRCode 7.4.2+** - QR code generation for mobile device pairing
- **Pillow 9.5.0+** - Image processing for QR codes

## Project Architecture

### Modular Design (6,900+ lines of Python)

```
RoboTaste/Software/
├── Core Application (2,771 lines)
│   ├── main_app.py (613 lines)           # Application router & entry point
│   ├── landing_page.py (160 lines)       # Session creation/joining interface
│   ├── moderator_interface.py (760 lines) # Moderator dashboard & monitoring
│   ├── subject_interface.py (926 lines)  # Participant experience interface
│   └── ui_components.py (102 lines)      # Shared UI components
│
├── Business Logic (2,213 lines)
│   ├── callback.py (1,560 lines)         # Core experiment logic & calculations
│   ├── state_machine.py (312 lines)      # Centralized phase management
│   └── session_manager.py (341 lines)    # Multi-device synchronization
│
├── Data Layer
│   ├── sql_handler.py (1,999 lines)      # Database operations & schema
│   └── experiment_sync.db                # SQLite database (auto-created)
│
├── Configuration
│   ├── requirements.txt                   # Python dependencies
│   ├── .streamlit/config.toml            # Streamlit configuration
│   └── .gitignore                         # Version control settings
│
├── Documentation
│   └── docs/
│       ├── README.md                      # Documentation index
│       ├── API_REFERENCE.md               # Function documentation
│       ├── DATABASE_SCHEMA.md             # Complete schema reference
│       ├── DEPLOYMENT_GUIDE.md            # Deployment instructions
│       └── Implementation guides (4 files)
│
└── Testing & Quality Assurance
    └── tests/
        ├── test_fixes_complete.py         # Integration tests
        ├── test_database_fix.py           # Database validation
        ├── test_slider_workflow.py        # Slider functionality
        └── test_unboundlocalerror_fix.py  # Error handling tests
```

## Experiment Workflow

### Moderator Workflow
```
1. Landing Page
   ↓
2. Create New Session (generates unique 6-character code)
   ↓
3. Configure Experiment
   ├─ Select ingredients (2-6 ingredients)
   ├─ Choose concentration mapping method
   ├─ Define questionnaires (pre/post)
   └─ Set initial slider positions per participant
   ↓
4. Display QR Code & Session Code
   ↓
5. Monitor Real-Time Progress
   ├─ Track participant connection status
   ├─ View current experiment phase
   ├─ See live position selections on visual grid
   └─ Monitor individual concentration values
   ↓
6. Export Results
   └─ Download complete dataset as CSV
```

### Participant Workflow
```
1. Landing Page
   ↓
2. Join Session (enter code or scan QR)
   ↓
3. Enter Participant ID
   ↓
4. Pre-Questionnaire (initial impressions)
   ↓
5. Interface Automatically Selected
   ├─ 2 ingredients → 2D Grid
   └─ 3-6 ingredients → Sliders
   ↓
6. Make Selection
   ├─ 2D Grid: Click coordinates on canvas
   └─ Sliders: Adjust individual ingredient levels
   ↓
7. Review Concentrations
   ↓
8. Post-Questionnaire (feedback on selection)
   ↓
9. Final Response Submission
   ↓
10. Completion Confirmation
```

## Supported Ingredients & Concentrations

### Available Ingredients (Literature-Based Ranges)
| Ingredient | Range (mM) | Common Application |
|-----------|-----------|-------------------|
| Sugar (Sucrose) | 0.73 - 73.0 | Sweetness studies, baseline taste |
| Salt (NaCl) | 0.10 - 10.0 | Saltiness perception, taste masking |
| Citric Acid | 0.1 - 5.0 | Sourness, pH effects |
| Caffeine | 0.01 - 1.0 | Bitterness, flavor complexity |
| Vanilla | 0.001 - 0.1 | Aroma-taste integration |
| Menthol | 0.001 - 0.5 | Cooling sensation, trigeminal effects |

**Note:** All concentration ranges are based on Breslin taste perception research and human sensory thresholds.

## Database Architecture

### Enhanced SQLite Schema with 3 Core Tables

#### `responses` Table - Complete Participant Data
Stores all participant responses with comprehensive metadata:
- **session_id, participant_id** - Session and participant tracking
- **ingredient_1_conc through ingredient_6_conc** - Individual concentrations (mM)
- **interface_type** - 'grid_2d' or 'slider_based'
- **method** - 'linear', 'logarithmic', 'exponential', or 'slider_based'
- **x_position, y_position** - Grid coordinates (for 2D interface)
- **reaction_time_ms** - Millisecond-precision timing
- **questionnaire_response** - JSON-formatted survey data
- **is_final_response** - Distinguishes final vs. intermediate selections
- **extra_data** - JSON metadata for extensibility
- **created_at** - Timestamp for temporal analysis

#### `initial_slider_positions` Table - Custom Starting Positions
Database-driven slider initialization per participant:
- **session_id, participant_id** - Links to session and participant
- **num_ingredients** - Number of ingredients (2-6)
- **ingredient_1_initial through ingredient_6_initial** - Starting concentrations
- **created_at** - Configuration timestamp

#### `sessions` Table - Multi-Device Session Management
Tracks session state and synchronization:
- **session_code** - Unique 6-character identifier
- **moderator_name** - Session creator
- **is_active** - Session status flag
- **subject_connected** - Connection indicator
- **current_phase** - Current experiment phase (from state machine)
- **experiment_config** - JSON configuration (ingredients, methods, questionnaires)
- **created_at, last_activity** - Timestamps for cleanup and monitoring

### Advanced Features
- **Automatic Schema Migrations** - Database evolves seamlessly with code updates
- **SQL Views for Live Monitoring** - Efficient real-time position tracking
- **Parameterized Queries** - SQL injection prevention
- **Transaction Management** - Atomic operations for data integrity
- **Context-Managed Connections** - Automatic resource cleanup

### Data Export Example
```python
from sql_handler import export_responses_csv

# Export complete session data
csv_data = export_responses_csv("ABC123")

# CSV includes:
# - Participant IDs
# - All ingredient concentrations (mM values)
# - Interface type and mapping method
# - Reaction times (ms)
# - Pre and post-questionnaire responses
# - Complete interaction timestamps
# - Selection history and patterns
```

## Testing & Quality Assurance

### Comprehensive Test Suite
```bash
cd tests

# Run all integration tests
python test_fixes_complete.py

# Individual component tests
python test_database_fix.py           # Database schema validation
python test_slider_workflow.py        # Slider functionality tests
python test_unboundlocalerror_fix.py  # Error handling verification
```

### Test Coverage
- **Database Schema & Migrations** - Automatic migration validation
- **Multi-Ingredient Response Storage** - 2-6 ingredient data persistence
- **Initial Slider Positions** - Database-driven initialization
- **Live Monitoring Views** - SQL view functionality
- **Data Export & CSV Generation** - Complete data export validation
- **State Machine Transitions** - Phase validation and error handling
- **Multi-Device Synchronization** - Session state consistency
- **Error Handling & Edge Cases** - Robustness testing

## Key Improvements & Implementation History

### Major Architectural Enhancements

**Version 2.0 - Centralized State Management** (Latest)
- **ExperimentStateMachine** - Industry-grade state machine with validated transitions
- **Atomic database synchronization** - Ensures data integrity across all devices
- **Phase recovery** - Automatic state restoration on browser reload
- **8-phase experiment lifecycle** - Comprehensive workflow management

**Version 1.5 - Database-Driven Customization**
- **Custom slider initial positions** - Per-participant starting values from database
- **Live monitoring SQL views** - Real-time position tracking with efficient queries
- **Automatic schema migrations** - Seamless database evolution
- **Enhanced data export** - Complete CSV export with all metadata

**Version 1.0 - Core Platform**
- **Dual interface architecture** - Grid and slider support
- **Multi-device synchronization** - Session-based real-time updates
- **Comprehensive data collection** - Millisecond-precision timing and complete history
- **Research-ready output** - Export-ready CSV format

### Recent Bug Fixes
- **UnboundLocalError resolution** - Fixed variable scope issues in slider initialization
- **Database transaction handling** - Improved error handling and rollback
- **Connection status tracking** - More reliable device connectivity monitoring
- **QR code generation** - Enhanced mobile device pairing

## Research Applications

### Ideal Use Cases
- **Multi-ingredient taste studies** - Experiments with 3-6 taste components
- **Preference mapping** - Understanding individual taste profiles
- **Controlled starting conditions** - Database-driven initial positions eliminate bias
- **Real-time behavioral monitoring** - Track participant decision-making process
- **Remote experiments** - Conduct studies across multiple locations
- **Longitudinal studies** - Track taste preference changes over time

### Research-Grade Data Output

**Complete Dataset Includes:**
- Individual ingredient concentrations (mM values, chemically accurate)
- Complete interaction timeline with millisecond timestamps
- Questionnaire responses (pre and post-selection)
- Reaction times and decision patterns
- Selection history and modification counts
- Interface type and mapping method metadata
- Participant demographics and session information

**Analysis-Ready Format:**
- CSV export compatible with SPSS, R, Python, Excel
- JSON support for complex data structures
- Normalized database schema for SQL queries
- Time-series data for temporal analysis

### Scientific Foundation
All concentration ranges based on:
- Breslin taste perception research
- Human sensory threshold literature
- Molecular weight calculations for chemical accuracy
- Validated experimental protocols

## Accessibility & User Experience

### Inclusive Design Features
- **Theme Support** - Light and dark mode with user preference storage
- **High Contrast Mode** - Enhanced visibility for visual accessibility
- **Responsive Design** - Works on desktop, tablet, and mobile devices
- **Keyboard Navigation** - Full keyboard support for all interactions
- **Clear Visual Feedback** - Real-time concentration displays and status indicators
- **Intuitive Interfaces** - Minimal learning curve for participants

### Multi-Language Support (Extensible)
- Template structure supports internationalization
- JSON-based questionnaires allow language customization
- Modular UI components for easy translation

## Deployment Options

### Local Development
Perfect for testing and small-scale experiments:
```bash
streamlit run main_app.py
# Access at http://localhost:8501
```

### Network Multi-Device
Ideal for in-lab experiments with multiple participants:
```bash
streamlit run main_app.py --server.address 0.0.0.0 --server.port 8501
# Moderator: http://<host_ip>:8501
# Participants: Same URL or scan QR code
```

### Cloud Deployment (Streamlit Cloud)
Best for remote experiments and public research:
- Automatic HTTPS encryption
- Global accessibility
- Persistent database storage
- No server maintenance required
- See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for details

## Security & Data Protection

### Current Implementation
- **Parameterized SQL queries** - Prevents SQL injection attacks
- **Context-managed connections** - Automatic resource cleanup
- **Transaction rollback** - Data integrity on errors
- **Input validation** - Sanitization of user inputs
- **Session isolation** - Separate data per experiment

### Recommended for Production
- Password protection for moderator interface
- Session timeout management
- Data encryption for sensitive information
- Regular database backups
- Audit logging for compliance
- Rate limiting for API endpoints

## Documentation & Support

### Complete Documentation Suite
- **[Documentation Hub](docs/README.md)** - Central documentation index
- **[API Reference](docs/API_REFERENCE.md)** - Complete function documentation with examples
- **[Database Schema](docs/DATABASE_SCHEMA.md)** - Detailed table structures and SQL queries
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Setup and cloud deployment instructions
- **[Implementation Guides](docs/)** - Technical deep-dives on major features

### Getting Help
- **Issue Tracking** - Report bugs or request features via GitHub Issues
- **Test Suite** - [tests/](tests/) directory contains comprehensive test coverage
- **Code Examples** - See API_REFERENCE.md for usage examples

## Project Statistics

### Codebase Metrics
- **Total Lines of Code:** 6,900+ lines of well-structured Python
- **Core Modules:** 9 production modules
- **Database Tables:** 3 core tables with advanced schema
- **Test Files:** 4 comprehensive test suites
- **Documentation Pages:** 7 detailed guides

### Feature Completeness
- **Supported Ingredients:** 6 (expandable architecture)
- **Interface Types:** 2 (automatic selection based on ingredient count)
- **Concentration Mapping Methods:** 3 (Linear, Logarithmic, Exponential)
- **Experiment Phases:** 8 (managed by centralized state machine)
- **Concurrent Sessions:** Unlimited (resource-dependent)
- **Data Export Formats:** CSV (with full metadata)

### Technology Highlights
- **Framework:** Streamlit 1.49.1+ (modern Python web framework)
- **Database:** SQLite3 (embedded, zero-configuration)
- **UI Components:** 5 specialized Streamlit extensions
- **Real-time Updates:** WebSocket-based synchronization
- **Cross-platform:** Windows, macOS, Linux compatible

## Why RoboTaste?

### For Researchers
- **Reduce setup time** from hours to minutes with automated session management
- **Eliminate manual data entry** with automatic database persistence
- **Increase data quality** with millisecond-precision timing and complete history
- **Enable remote research** with multi-device cloud deployment
- **Ensure reproducibility** with standardized concentration ranges and validated protocols

### For Participants
- **Intuitive interfaces** require minimal training
- **Real-time feedback** improves engagement and data quality
- **Flexible access** from any device (phone, tablet, laptop)
- **Accessible design** with theme support and high contrast mode
- **Clear instructions** guide through each experiment phase

### Technical Advantages
- **Open source** - Full transparency and customizability
- **Well-documented** - 7 comprehensive documentation files
- **Thoroughly tested** - 4 test suites covering all critical functionality
- **Modern architecture** - Industry-standard state management and database design
- **Actively maintained** - Recent updates include centralized state machine and enhanced monitoring

## Future Roadmap

### Planned Enhancements
- **Advanced analytics dashboard** - Statistical analysis and visualization tools
- **Extended ingredient library** - Support for additional taste compounds
- **Machine learning integration** - Predictive taste preference modeling
- **Enhanced questionnaires** - Conditional logic and branching surveys
- **API endpoints** - Programmatic access for automation
- **Mobile app** - Native iOS/Android applications

### Community Contributions Welcome
This is an academic research project open to collaboration. Potential contribution areas:
- Additional concentration mapping algorithms
- New UI themes and accessibility features
- Extended ingredient support
- Integration with lab equipment
- Advanced statistical analysis modules
- Translation to other languages

## License

This project is developed for academic research purposes at the Masters level.

**Academic Use:** Free for educational and non-commercial research
**Commercial Use:** Please contact the authors for licensing terms
**Citation:** If you use RoboTaste in your research, please cite this repository

---

## Summary

**RoboTaste** is a production-ready, research-grade platform for conducting multi-ingredient taste preference experiments with real-time multi-device synchronization. Built on modern web technologies with centralized state management, dual interface support, and comprehensive data collection capabilities.

**Perfect for:**
- Sensory science research
- Taste perception studies
- Product development research
- Consumer preference testing
- Food science education
- Behavioral psychology experiments

---

**Project Information**
- **Version:** 2.0 (Centralized State Management)
- **Last Updated:** October 2025
- **Status:** Production Ready
- **Codebase:** 6,900+ lines of Python
- **Platform:** Cross-platform (Windows, macOS, Linux)
- **License:** Academic Research

**Built with:** Python • Streamlit • SQLite • Plotly • Modern Web Technologies

---

**RoboTaste Platform** - Revolutionizing taste preference research through intelligent automation, real-time synchronization, and comprehensive data collection.