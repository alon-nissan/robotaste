# 🍯 RoboTaste - Comprehensive Development Documentation

## PROJECT OVERVIEW

**RoboTaste** is an advanced research platform for studying taste preferences through interactive digital interfaces. Designed for Masters-level research, it provides sophisticated data collection and analysis capabilities for taste perception studies.

---

## 🏗️ ARCHITECTURE OVERVIEW

### Core Components
- **main_app.py** - Primary Streamlit application and UI router
- **callback.py** - Experimental logic and concentration calculations  
- **sql_handler.py** - Database management and data persistence

### Technology Stack
- **Frontend**: Streamlit with custom CSS theming
- **Backend**: Python with SQLite database
- **Visualization**: Plotly + streamlit-drawable-canvas
- **Data Processing**: Pandas, JSON for complex data structures

---

## 📊 INTERFACE SYSTEMS

### 1. 2D Grid Interface (Binary Mixtures)
- **Use Case**: 2-ingredient experiments (Sugar + Salt)
- **Interaction**: Click-based coordinate selection
- **Mapping**: Linear, logarithmic, or exponential concentration mapping
- **Range**: Sugar (0.73-73.0 mM), Salt (0.10-10.0 mM)

### 2. Multi-Component Slider Interface  
- **Use Case**: 3-6 ingredient experiments
- **Interaction**: Independent concentration sliders
- **Ingredients**: Sugar, Salt, Citric Acid, Caffeine, Vanilla, Menthol
- **Subject View**: Generic labels (A, B, C...) with percentage positions
- **Backend**: Real mM concentration calculations

---

## 🗄️ DATABASE SCHEMA

### session_state
```sql
CREATE TABLE session_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_type TEXT CHECK(user_type IN ('mod', 'sub')),
    participant_id TEXT NOT NULL,
    method TEXT CHECK(method IN ('linear', 'logarithmic', 'exponential', 'slider_based')),
    x_position REAL,
    y_position REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### responses  
```sql
CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id TEXT NOT NULL,
    x_position REAL NOT NULL,
    y_position REAL NOT NULL,
    method TEXT NOT NULL,
    sugar_concentration REAL,
    salt_concentration REAL,
    reaction_time_ms INTEGER,
    is_final BOOLEAN,
    extra_data TEXT,  -- JSON for multi-component data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔄 WORKFLOW SYSTEMS

### Subject Workflow
```
Welcome → Pre-Questionnaire → Interface Selection → Post-Questionnaire → Final Response
```

### Moderator Workflow  
```
Configure Experiment → Monitor Real-time → Analyze Data → Export Results
```

### Questionnaire System
- **Unified questionnaire** for both initial impressions and post-selection feedback
- **Configurable questions** via QUESTIONNAIRE_CONFIG
- **Automatic triggering** after each interface interaction
- **Final response** vs **continue selection** options

---

## 🚨 HIGH PRIORITY TODOS

### Critical Features Needed
- [ ] **Data Export System**
  - CSV export for statistical analysis
  - JSON export with full metadata
  - Batch export for multiple participants
  - Real-time data streaming

- [ ] **Participant Progress Tracking**  
  - Visual progress indicators
  - Session completion status
  - Time-on-task measurements
  - Dropout detection and recovery

- [ ] **Safety & Validation**
  - Concentration safety limits
  - Ingredient interaction warnings
  - Solution stability calculations
  - Quality control checks

- [ ] **Mobile Responsiveness**
  - Touch-friendly slider controls
  - Responsive grid interface
  - Mobile-optimized questionnaires
  - Cross-device session continuity

### Security & Authentication
- [ ] **Moderator Authentication**
  - Password-protected moderator access
  - Session-based authentication
  - Role-based permissions
  - Audit logging

- [ ] **Data Security**
  - Database encryption
  - Secure session handling
  - Data anonymization options
  - GDPR compliance features

### Performance & Reliability
- [ ] **Error Handling**
  - Comprehensive error recovery
  - Automatic session restoration
  - Database connection pooling
  - Graceful degradation

- [ ] **Backup & Recovery**
  - Automated database backups
  - Data recovery utilities
  - Session state restoration
  - Disaster recovery procedures

---

## 🛠️ MEDIUM PRIORITY TODOS

### Analytics & Reporting
- [ ] **Advanced Analytics Dashboard**
  - Statistical analysis tools
  - Data visualization enhancements
  - Trend analysis
  - Comparative studies

- [ ] **Research Tools**
  - Experiment templates
  - Batch participant management
  - Custom concentration ranges
  - Protocol validation

### User Experience
- [ ] **Interface Improvements**
  - Dark mode support
  - Accessibility enhancements
  - Keyboard navigation
  - Screen reader compatibility

- [ ] **Workflow Optimization**
  - Streamlined setup process
  - Quick start templates
  - Automated calibration
  - Smart defaults

### Technical Enhancements
- [ ] **Database Improvements**
  - Performance optimization
  - Advanced querying
  - Data archiving
  - Connection pooling

- [ ] **Code Quality**
  - Comprehensive testing suite
  - Type hints throughout
  - Performance profiling
  - Code documentation

---

## 🔍 LOW PRIORITY TODOS

### Advanced Features
- [ ] **Multi-Language Support**
  - Internationalization framework
  - Translated questionnaires
  - Cultural adaptation tools
  - Language detection

- [ ] **Advanced Modeling**
  - Molecular interaction modeling
  - Flavor prediction algorithms
  - Sensory threshold calculations
  - Machine learning integration

- [ ] **Integration Capabilities**
  - API endpoints for external tools
  - Database replication
  - Third-party analytics
  - Cloud storage integration

### Research Enhancements
- [ ] **Experiment Extensions**
  - Temperature-dependent calculations
  - pH adjustment recommendations
  - Time-based studies
  - Longitudinal tracking

---

## 🧪 TECHNICAL DEBT & MAINTENANCE

### Code Cleanup
- [ ] Remove unused imports (pd, go, Optional, etc.)
- [ ] Fix unused variable warnings (col1, col3, etc.)
- [ ] Standardize error handling patterns
- [ ] Consolidate duplicate code sections

### Performance Optimization
- [ ] Optimize database queries
- [ ] Implement caching for frequent calculations
- [ ] Reduce memory usage in large datasets
- [ ] Streamline UI updates

### Testing & Validation
- [ ] Unit tests for concentration calculations
- [ ] Integration tests for workflow
- [ ] UI/UX testing across devices
- [ ] Load testing for concurrent users

---

## 📚 RESEARCH CONSIDERATIONS

### Data Collection Best Practices
- Ensure consistent data formats across interface types
- Implement reaction time accuracy validation
- Add metadata for experimental conditions
- Create standardized export formats for analysis

### Statistical Considerations  
- Power analysis for sample size determination
- Randomization strategies for stimulus presentation
- Control for order effects and learning
- Validation against known taste preference data

### Ethical Considerations
- Informed consent integration
- Data anonymization procedures
- Participant withdrawal mechanisms
- Secure data handling protocols

---

## 🚀 DEPLOYMENT CHECKLIST

### Pre-Production
- [ ] Complete security audit
- [ ] Performance testing under load
- [ ] Database backup procedures
- [ ] Documentation completeness
- [ ] User training materials

### Production Setup
- [ ] Server environment configuration  
- [ ] SSL/TLS certificate installation
- [ ] Database security hardening
- [ ] Monitoring and alerting setup
- [ ] Backup automation

### Post-Deployment
- [ ] User acceptance testing
- [ ] Performance monitoring
- [ ] Regular security updates
- [ ] Data quality validation
- [ ] Ongoing maintenance procedures

---

## 📞 SUPPORT & MAINTENANCE

### Regular Maintenance Tasks
- Database optimization and cleanup
- Security updates and patches  
- Performance monitoring and tuning
- User feedback collection and analysis
- Documentation updates

### Troubleshooting Common Issues
- Database connection failures
- Session state corruption
- Canvas rendering problems
- Mobile compatibility issues
- Data export formatting problems

---

*This documentation serves as a comprehensive guide for current and future development of the RoboTaste platform. Prioritize HIGH priority items for immediate development focus.*

**Last Updated**: 2025  
**Version**: 2.0 - Multi-Component Support