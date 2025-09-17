# 🎯 RoboTaste - Multi-Device Taste Preference Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)

> **A comprehensive Streamlit-based platform for conducting taste preference experiments with real-time multi-device synchronization. Features dual interface support (2D grid & sliders), custom initial positions, live monitoring, and complete data export capabilities.**

## ✨ Features

### 🎛️ **Dual Interface Support**
- **2D Grid Interface** - Traditional X-Y coordinate selection (2 ingredients)
- **Slider Interface** - Independent concentration control (3-6 ingredients)

### 🔄 **Real-Time Multi-Device**
- **Session-based experiments** with unique session codes
- **Live synchronization** between moderator and participants
- **Real-time monitoring** of participant progress

### 🗄️ **Advanced Database Features**
- **Multi-ingredient support** (2-6 ingredients with automatic interface selection)
- **Custom initial positions** for slider experiments
- **Complete response tracking** with questionnaire integration
- **Live monitoring views** for real-time position tracking
- **Comprehensive data export** in CSV format

### 📊 **Research-Ready**
- **Timing data** with millisecond precision
- **Questionnaire integration** with linked responses
- **Complete interaction history** for analysis
- **Flexible experiment configuration**

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Web browser (Chrome, Firefox, Safari, Edge)

### Installation
```bash
# Clone repository
git clone <repository_url>
cd RoboTaste/Software

# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run main_app.py
```

Visit `http://localhost:8501` to access the platform.

### Multi-Device Setup
For experiments across multiple devices:
```bash
# Run on network interface
streamlit run main_app.py --server.address 0.0.0.0 --server.port 8501
```

- **Moderator**: Access via `http://<host_ip>:8501` to create sessions
- **Participants**: Join using session code on same URL

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

## 🗂️ Project Structure

```
RoboTaste/Software/
├── 📱 main_app.py              # Main Streamlit application
├── 🔄 callback.py              # Trial and response management
├── 🗄️ sql_handler.py           # Database operations
├── 🌐 session_manager.py       # Multi-device session handling
├── 📋 requirements.txt         # Python dependencies
├── 📊 experiment_sync.db       # SQLite database (auto-created)
├── 📚 docs/                    # Complete documentation
├── 🧪 tests/                   # Comprehensive test suite
└── ⚙️ .streamlit/              # Application configuration
```

## 🎛️ Interface Types

### 2D Grid Interface (2 ingredients)
- **Usage**: Traditional sugar/salt or two-ingredient experiments
- **Interaction**: Click anywhere on the grid to select concentration ratio
- **Display**: Real-time concentration values and visual feedback

### Slider Interface (3-6 ingredients)
- **Usage**: Multi-ingredient taste experiments
- **Interaction**: Independent sliders for each ingredient concentration
- **Features**:
  - Custom starting positions from database
  - Real-time concentration calculations
  - Mixer-board styling for intuitive use

## 🗄️ Database Features

### Enhanced Schema
- **📊 `responses` table** - Multi-ingredient response storage
- **🎯 `initial_slider_positions` table** - Custom starting positions
- **📈 Live monitoring views** - Real-time position tracking
- **🔄 Automatic migrations** - Seamless schema updates

### Data Export
```python
from sql_handler import export_responses_csv

# Export all session data
csv_data = export_responses_csv("SESSION123")
```

**Exported fields include:**
- Participant IDs and session information
- Individual ingredient concentrations (mM)
- Interface type and interaction method
- Reaction times and timestamps
- Questionnaire responses (JSON format)
- Complete interaction history

## 🧪 Testing

### Comprehensive Test Suite
```bash
cd tests

# Run all tests
python test_fixes_complete.py

# Individual components
python test_database_fix.py
python test_slider_workflow.py
python test_unboundlocalerror_fix.py
```

**Test Coverage:**
- ✅ Database schema and migrations
- ✅ Multi-ingredient response storage (2-6 ingredients)
- ✅ Initial slider positions from database
- ✅ Live monitoring functionality
- ✅ Data export and CSV generation
- ✅ Error handling and edge cases

## 🔧 Recent Improvements

### ✅ **Three Critical Fixes Implemented**

1. **🎯 Slider Initial Positions from Database**
   - Custom starting positions per session/participant
   - Database-driven initialization
   - Support for all ingredient counts (2-6)

2. **📊 Database View for Live Monitoring**
   - Real-time position tracking
   - SQL views for efficient querying
   - Status indicators (Live/Final)

3. **🐛 UnboundLocalError Resolution**
   - Fixed scope issues in slider initialization
   - Proper variable definition order
   - Error-free final response submission

### 🎛️ **Enhanced Slider Interface**
- **Database-driven initial positions** - Sliders start at custom positions set by moderator
- **Real-time database saves** - Both "Finish" button and questionnaire submission save to database
- **Complete data capture** - All slider movements and final selections recorded
- **Multi-ingredient support** - Seamless support for 3-6 ingredient experiments

## 🌐 Multi-Device Workflow

### Session Creation (Moderator)
1. **Create session** with unique code
2. **Configure experiment** (ingredients, method, initial positions)
3. **Monitor participants** in real-time
4. **Export data** when complete

### Participation (Subjects)
1. **Join session** using session code
2. **Load interface** with custom initial positions
3. **Make selections** with real-time feedback
4. **Complete questionnaire** for final submission

### Data Flow
```
Moderator creates session → Participants join → Custom initial positions loaded
    ↓
Real-time interaction tracking → Slider movements saved → Final submission
    ↓
Complete data export → Research-ready CSV with all interaction data
```

## 📊 Research Applications

### Ideal For
- **Multi-ingredient taste studies** with 3-6 components
- **Controlled starting conditions** with custom initial positions
- **Real-time monitoring** of participant behavior
- **Comprehensive data collection** with timing and interaction history

### Data Output
- **Individual ingredient concentrations** (mM values)
- **Complete interaction timeline** with timestamps
- **Questionnaire responses** linked to selections
- **Reaction times** and selection patterns
- **Export-ready format** for statistical analysis

## 🔒 Requirements

### Core Dependencies
```
streamlit>=1.24.0          # Web application framework
pandas>=1.5.0              # Data manipulation
sqlite3                    # Database (built into Python)
streamlit-drawable-canvas  # 2D grid interface
streamlit-vertical-slider  # Slider interface components
```

### System Requirements
- **Python 3.8+**
- **4GB RAM minimum** (8GB recommended for large datasets)
- **Network access** for multi-device experiments
- **Modern web browser** with JavaScript enabled

## 📞 Support

### Documentation
- **[📚 Complete Documentation](docs/)** - Comprehensive guides and references
- **[🔧 API Reference](docs/API_REFERENCE.md)** - Function documentation with examples
- **[🗄️ Database Schema](docs/DATABASE_SCHEMA.md)** - Complete database documentation

### Testing
- **[🧪 Test Suite](tests/)** - Comprehensive test coverage
- **Automated verification** of all critical functionality
- **Integration tests** for multi-device scenarios

## 📝 License

This project is developed for academic research purposes. Please see license file for usage terms.

---

**🎯 RoboTaste Platform** - Enabling precise, multi-device taste preference research with real-time synchronization and comprehensive data collection.

*Last Updated: September 2025*
*Version: 1.1 - Enhanced Multi-Ingredient Support*
*Status: Production Ready with Comprehensive Testing*