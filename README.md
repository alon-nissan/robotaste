# 🍯 RoboTaste - Interactive Taste Preference Experiment Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)

> **A sophisticated multi-device research platform for studying taste preferences through interactive digital interfaces. Designed for Masters-level taste perception research with comprehensive data collection and analysis capabilities.**

## 📱 **Multi-Device Architecture**

### **🎮 Moderator Dashboard** 
- **Purpose**: Experiment control and real-time monitoring
- **Device**: Desktop/laptop with large screen
- **Features**: Session management, live monitoring, data analytics, QR code generation

### **👤 Subject Interface**
- **Purpose**: Taste preference selection and questionnaires  
- **Device**: Any device (phone, tablet, laptop)
- **Features**: 2D grid selection, vertical sliders, questionnaire forms

---

## 🚀 **Quick Start**

### **🔧 For Moderators (Experiment Setup)**
1. **Create Session**: Visit the app → "New Session" → Enter moderator name
2. **Get Session Code**: Share the 6-digit code or QR code with subjects
3. **Configure Experiment**: Select 2-6 ingredients, mapping method
4. **Start Trial**: Click "Start Trial" to activate subject interface
5. **Monitor Live**: Watch real-time responses and analytics

### **📱 For Subjects (Participants)**
1. **Join Session**: Visit the app → "Join Session" → Enter 6-digit code
2. **Enter ID**: Provide your participant identifier
3. **Wait for Activation**: Moderator will start your trial
4. **Make Selection**: Use 2D grid or vertical sliders interface
5. **Complete Questionnaires**: Answer pre/post-response questions

---

## 🧪 **Interface Modes**

### **1. 2D Grid Mode (2 ingredients)**
- **Use Case**: Binary mixtures (e.g., Sugar + Salt)
- **Interface**: Traditional X-Y coordinate selection
- **Mapping Methods**: Linear, Logarithmic, Exponential
- **Concentration Ranges**: 
  - Sugar: 0.73-73.0 mM
  - Salt: 0.10-10.0 mM

### **2. Vertical Sliders Mode (3-6 ingredients)**
- **Use Case**: Multi-component mixtures
- **Interface**: Independent concentration sliders per ingredient
- **Display**: Subjects see percentages, system calculates mM concentrations
- **Supported Ingredients**: Sugar, Salt, Citric Acid, Caffeine, Vanilla, Menthol

---

## 🛠️ **Installation & Deployment**

### **Local Development**
```bash
# Clone repository
git clone https://github.com/alon-nissan/robotaste.git
cd robotaste/Software

# Install dependencies  
pip install -r requirements.txt

# Run locally
streamlit run main_app.py
```

### **Streamlit Cloud Deployment**
1. **Fork/Clone** this repository to your GitHub account
2. **Connect to Streamlit Cloud**: 
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub account
   - Select this repository
   - Set **main branch** as deployment source
   - Set `Software/main_app.py` as the main file
3. **Deploy**: Streamlit Cloud will automatically deploy from the main branch
4. **Custom Domain** (optional): Configure custom domain in Streamlit Cloud settings

### **Multi-Device Setup**
1. **Deploy to Streamlit Cloud** (recommended for multi-device access)
2. **Share App URL** with moderators and subjects
3. **Session Codes**: Each experiment session gets a unique 6-digit code
4. **QR Codes**: Automatically generated for easy subject access via mobile

---

## 📁 **Project Structure**

```
RoboTaste/
├── Software/
│   ├── main_app.py              # Main Streamlit application
│   ├── callback.py              # Core experiment logic and handlers  
│   ├── session_manager.py       # Multi-device session management
│   ├── sql_handler.py          # Database operations and storage
│   ├── requirements.txt        # Python dependencies
│   ├── test_keys.py           # Testing utilities
│   └── experiment_sync.db     # SQLite database (auto-generated)
├── README.md                  # This documentation
├── .gitignore                # Git ignore patterns
└── docs/                     # Additional documentation
```

---

## 📊 **Workflow**

### **Subject Flow**
`Welcome → Pre-Questionnaire → Interface Selection → Post-Questionnaire → Final Response`

### **Moderator Flow**
`Configure Experiment → Monitor Real-time → Analyze Data → Export Results`

---

## 🔧 **Configuration**

### **Experiment Parameters**
- **Number of Ingredients**: 2-6 (affects interface type)
- **Concentration Mapping**: Linear, Logarithmic, Exponential (2D grid only)
- **Participant Management**: Multi-participant session support
- **Data Collection**: Automatic SQLite storage with JSON support

### **Interface Switching Logic**
- **2 ingredients** → 2D Grid Interface (X-Y coordinates)  
- **3+ ingredients** → Vertical Sliders Interface (independent controls)

---

## 📊 **Data Collection & Export**

### **Collected Data**
- **Participant Information**: ID, session code, timestamps
- **Selection Data**: Coordinates, concentrations, reaction times
- **Questionnaire Responses**: Pre/post-selection feedback
- **Session Metadata**: Moderator, configuration, device info

### **Export Formats**
- **CSV**: Complete response data with calculated concentrations
- **Real-time Monitoring**: Live position tracking and analytics
- **Solution Preparation**: Exact mass calculations for lab preparation

---

## 🔍 **Technical Features**

### **Multi-Device Synchronization**
- **Session-based Architecture**: Unique codes for device pairing
- **Real-time Updates**: Live monitoring without auto-refresh conflicts
- **Cross-platform Compatibility**: Works on desktop, tablet, mobile

### **Data Integrity**
- **Unique Element Keys**: Prevents Streamlit duplicate ID errors
- **Session State Management**: Persistent data across page refreshes
- **Error Handling**: Graceful degradation and user feedback

### **User Experience**
- **Responsive Design**: Adapts to different screen sizes
- **Accessibility**: High contrast mode, keyboard navigation
- **Visual Feedback**: Clear status indicators and progress tracking

---

## 🚧 **Known Issues & Fixes**

### **✅ Recently Fixed** (v1.0-demo)
- **Blank Screen Issues**: Removed problematic auto-refresh loops
- **Duplicate Element IDs**: Added unique keys to all interactive elements
- **Session Management**: Improved multi-device state synchronization

### **⚠️ Current Limitations**
- **Manual Refresh**: Users need to manually refresh for updates (prevents blank screens)
- **Single Session**: One active experiment per session code
- **Local Storage**: SQLite database (consider PostgreSQL for production)

---

## 🤝 **Development**

### **Branch Structure**
- **`main`**: Stable demo/production version ✅
- **`development`**: Active development and new features  
- **Feature branches**: `feature/feature-name` for specific improvements

### **Getting Started with Development**
```bash
# Clone and checkout development branch
git clone https://github.com/alon-nissan/robotaste.git
cd robotaste/Software
git checkout development

# Install dependencies
pip install -r requirements.txt

# Run locally with hot reload
streamlit run main_app.py

# Make changes and commit to development branch
git add .
git commit -m "Your feature description"
git push origin development
```

---

## 📝 **Research Applications**

### **Suitable For**
- **Taste Perception Studies**: Multi-component flavor optimization
- **Preference Mapping**: Individual and group taste profiling
- **Product Development**: Beverage and food formulation research
- **Sensory Analysis**: Digital alternative to traditional methods

### **Research Outputs**
- **Individual Preference Maps**: Per-participant concentration preferences
- **Group Analytics**: Population-level taste preference patterns  
- **Optimization Data**: Ideal concentration combinations
- **Behavioral Metrics**: Response times and selection patterns

---

## 🔗 **Quick Links**

- **🚀 [Live Demo](https://alon-nissan-robotaste.streamlit.app)** - Try the application
- **📊 [GitHub Repository](https://github.com/alon-nissan/robotaste)** - Source code
- **🐛 [Issues](https://github.com/alon-nissan/robotaste/issues)** - Bug reports & feature requests
- **📖 [Project Documentation](PROJECT_DOCUMENTATION.md)** - Detailed technical docs
- **🛠️ [Deployment Guide](DEPLOYMENT_GUIDE.md)** - Setup instructions

---

## 📄 **License**

This project is developed for Masters-level research. Please contact the authors for usage permissions and collaboration opportunities.

---

## 👥 **Authors**

**Masters Research Project**  
University Research Team  
*Taste Perception & Digital Interface Laboratory*

---

*Last Updated: September 2025*  
*Version: 1.0-demo*  
*Status: Stable Demo Version*