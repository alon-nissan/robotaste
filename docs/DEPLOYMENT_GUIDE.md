# Deployment Guide - RoboTaste Platform

## Quick Start

### Prerequisites
- **Python 3.8+** with pip
- **Git** for version control
- **Web browser** (Chrome, Firefox, Safari, Edge)

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

The application will be available at `http://localhost:8501`

## Dependencies

### Core Requirements (`requirements.txt`)
```
streamlit>=1.24.0
pandas>=1.5.0
sqlite3  # Built into Python
streamlit-drawable-canvas>=0.9.0
streamlit-vertical-slider>=1.0.0
```

### Additional Dependencies
```bash
# For development/testing
pip install pytest black flake8

# For deployment
pip install gunicorn  # If using production server
```

## Configuration

### Environment Variables
```bash
# Optional configuration
export ROBOTASTE_DB_PATH="./experiment_sync.db"
export ROBOTASTE_DEBUG="false"
export ROBOTASTE_PORT="8501"
```

### Streamlit Configuration
Create `.streamlit/config.toml`:
```toml
[server]
port = 8501
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#3b82f6"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f8fafc"
textColor = "#1e293b"
```

## Database Setup

### Automatic Initialization
The database initializes automatically on first run:
```python
# Database auto-created at startup
from sql_handler import init_database
init_database()  # Creates experiment_sync.db
```

### Manual Database Setup
```bash
# If needed, manually initialize
python -c "from sql_handler import init_database; init_database()"
```

### Database Migration
Existing databases are automatically migrated to the latest schema:
- ✅ Preserves existing data
- ✅ Adds new columns and tables
- ✅ Updates views and indices
- ✅ Backwards compatible

## Multi-Device Setup

### Network Deployment
For multi-device experiments across network:

```bash
# Run on network interface
streamlit run main_app.py --server.address 0.0.0.0 --server.port 8501
```

**Access URLs:**
- **Moderator**: `http://<host_ip>:8501` (create session)
- **Participants**: `http://<host_ip>:8501` (join session)

### Session Management
1. **Moderator creates session** with unique session code
2. **Participants join** using session code
3. **Real-time synchronization** via shared database
4. **Live monitoring** of participant progress

## Production Deployment

### Using Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "main_app.py", "--server.address", "0.0.0.0"]
```

```bash
# Build and run
docker build -t robotaste .
docker run -p 8501:8501 -v $(pwd)/data:/app/data robotaste
```

### Using systemd (Linux)
Create `/etc/systemd/system/robotaste.service`:
```ini
[Unit]
Description=RoboTaste Application
After=network.target

[Service]
Type=exec
User=robotaste
WorkingDirectory=/opt/robotaste
Environment=PATH=/opt/robotaste/venv/bin
ExecStart=/opt/robotaste/venv/bin/streamlit run main_app.py --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable robotaste
sudo systemctl start robotaste
```

## File Structure

### Project Organization
```
RoboTaste/Software/
├── main_app.py              # Main Streamlit application
├── callback.py               # Trial and response management
├── sql_handler.py            # Database operations
├── session_manager.py        # Multi-device session handling
├── requirements.txt          # Python dependencies
├── experiment_sync.db        # SQLite database (auto-created)
├── docs/                     # Documentation
│   ├── README.md
│   ├── API_REFERENCE.md
│   ├── DATABASE_SCHEMA.md
│   └── DEPLOYMENT_GUIDE.md
├── tests/                    # Test files
│   ├── test_database_fix.py
│   ├── test_fixes_complete.py
│   ├── test_slider_workflow.py
│   └── test_unboundlocalerror_fix.py
└── .streamlit/               # Streamlit configuration
    └── config.toml
```

## Testing

### Run Test Suite
```bash
# All tests
cd tests
python test_fixes_complete.py

# Individual test components
python test_database_fix.py
python test_slider_workflow.py
python test_unboundlocalerror_fix.py
```

### Test Coverage
- ✅ **Database schema** and migrations
- ✅ **Multi-ingredient responses** (2-6 ingredients)
- ✅ **Initial slider positions** from database
- ✅ **Live monitoring** views
- ✅ **Data export** functionality
- ✅ **Error handling** and edge cases

## Monitoring and Logging

### Application Logs
```python
# Logging configuration in sql_handler.py
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

### Database Monitoring
```sql
-- Check database size
SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();

-- Monitor response counts
SELECT interface_type, COUNT(*) as count
FROM responses
GROUP BY interface_type;

-- Check recent activity
SELECT session_id, COUNT(*) as responses, MAX(created_at) as last_response
FROM responses
GROUP BY session_id
ORDER BY last_response DESC;
```

### Performance Monitoring
```bash
# Monitor Streamlit process
ps aux | grep streamlit

# Check network connections
netstat -tulpn | grep 8501

# Monitor database file
ls -lh experiment_sync.db
```

## Backup and Recovery

### Data Backup
```bash
# Regular backup script
#!/bin/bash
BACKUP_DIR="/backup/robotaste"
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
cp experiment_sync.db "$BACKUP_DIR/experiment_sync_$DATE.db"

# Configuration backup
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" .streamlit/ docs/

# Keep last 30 days
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
```

### Data Export
```python
# Export session data
from sql_handler import export_responses_csv

# All data
csv_data = export_responses_csv()
with open("all_responses.csv", "w") as f:
    f.write(csv_data)

# Specific session
session_data = export_responses_csv("SESSION123")
with open("session_123.csv", "w") as f:
    f.write(session_data)
```

## Troubleshooting

### Common Issues

#### Database Locked
```bash
# Check for locks
lsof experiment_sync.db

# Force unlock (if safe)
sqlite3 experiment_sync.db "BEGIN IMMEDIATE; ROLLBACK;"
```

#### Port Already in Use
```bash
# Find process using port
lsof -i :8501

# Kill process if needed
kill <pid>

# Use different port
streamlit run main_app.py --server.port 8502
```

#### Memory Issues
```bash
# Monitor memory usage
ps aux --sort=-%mem | head

# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
```

### Debugging Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Streamlit debug mode
streamlit run main_app.py --logger.level=debug
```

### Database Recovery
```sql
-- Check database integrity
PRAGMA integrity_check;

-- Repair if needed
PRAGMA quick_check;

-- Vacuum to optimize
VACUUM;
```

## Security Considerations

### Network Security
- **Use HTTPS** in production
- **Firewall rules** to restrict access
- **VPN access** for remote experiments

### Data Privacy
- **No personal data** stored by default
- **Anonymous participant IDs** recommended
- **Data encryption** for sensitive experiments

### Access Control
- **Session codes** provide basic access control
- **IP restrictions** can be implemented
- **User authentication** for sensitive research

## Performance Optimization

### Database Performance
```sql
-- Optimize queries with indices
CREATE INDEX idx_responses_session ON responses(session_id, created_at);

-- Regular maintenance
PRAGMA optimize;
VACUUM;
```

### Application Performance
- **Streamlit caching** for expensive operations
- **Database connection pooling**
- **Async operations** for real-time updates

### Resource Management
```python
# Connection management
@contextmanager
def get_database_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()
```

## Updates and Maintenance

### Update Procedure
```bash
# Backup current version
cp -r RoboTaste RoboTaste_backup_$(date +%Y%m%d)

# Pull updates
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Test functionality
python tests/test_fixes_complete.py

# Restart application
sudo systemctl restart robotaste
```

### Database Maintenance
```bash
# Monthly maintenance script
sqlite3 experiment_sync.db "VACUUM; PRAGMA optimize;"

# Check and repair
sqlite3 experiment_sync.db "PRAGMA integrity_check;"
```