# Database Schema Documentation

## Overview
The RoboTaste platform uses SQLite for local data storage with a comprehensive schema supporting multi-ingredient taste preference experiments.

## Core Tables

### `responses` Table
**Primary data storage for all participant responses**

```sql
CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    selection_number INTEGER,
    participant_id TEXT NOT NULL,
    interface_type TEXT DEFAULT 'grid_2d',
    method TEXT NOT NULL,
    ingredient_1_conc REAL,
    ingredient_2_conc REAL,
    ingredient_3_conc REAL,
    ingredient_4_conc REAL,
    ingredient_5_conc REAL,
    ingredient_6_conc REAL,
    x_position REAL,
    y_position REAL,
    reaction_time_ms INTEGER,
    questionnaire_response TEXT,  -- JSON format
    is_final_response BOOLEAN DEFAULT 0,
    extra_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Column Details:**
- `id`: Auto-incrementing primary key
- `session_id`: Links to experimental session
- `selection_number`: Order of selections within participant's session
- `participant_id`: Unique participant identifier
- `interface_type`: `'grid_2d'` or `'slider_based'`
- `method`: Response method (`'linear'`, `'logarithmic'`, `'exponential'`, `'slider_based'`)
- `ingredient_X_conc`: Concentration in mM for ingredient X (1-6)
- `x_position`, `y_position`: Grid coordinates (for 2D interface)
- `reaction_time_ms`: Response time in milliseconds
- `questionnaire_response`: JSON string with questionnaire answers
- `is_final_response`: Boolean indicating final submission vs. intermediate
- `extra_data`: JSON string with additional metadata
- `created_at`: Timestamp of response

**Usage Examples:**
```sql
-- Get all final responses for a session
SELECT * FROM responses
WHERE session_id = 'SESSION123' AND is_final_response = 1;

-- Get slider responses with ingredient concentrations
SELECT participant_id, ingredient_1_conc, ingredient_2_conc, ingredient_3_conc
FROM responses
WHERE interface_type = 'slider_based';

-- Get questionnaire data
SELECT participant_id, questionnaire_response
FROM responses
WHERE questionnaire_response IS NOT NULL;
```

### `initial_slider_positions` Table
**Stores custom starting positions for slider experiments**

```sql
CREATE TABLE initial_slider_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    interface_type TEXT DEFAULT 'slider_based',
    num_ingredients INTEGER NOT NULL,
    ingredient_1_initial REAL,
    ingredient_2_initial REAL,
    ingredient_3_initial REAL,
    ingredient_4_initial REAL,
    ingredient_5_initial REAL,
    ingredient_6_initial REAL,
    ingredient_1_percent REAL,
    ingredient_2_percent REAL,
    ingredient_3_percent REAL,
    ingredient_4_percent REAL,
    ingredient_5_percent REAL,
    ingredient_6_percent REAL,
    extra_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, participant_id)
)
```

**Column Details:**
- `ingredient_X_initial`: Initial concentration in mM for ingredient X
- `ingredient_X_percent`: Initial slider percentage (0-100) for ingredient X
- `num_ingredients`: Number of active ingredients (2-6)
- `extra_data`: JSON with ingredient names and metadata

**Usage Examples:**
```sql
-- Get initial positions for a participant
SELECT * FROM initial_slider_positions
WHERE session_id = 'SESSION123' AND participant_id = 'P001';

-- Set initial positions
INSERT INTO initial_slider_positions
(session_id, participant_id, num_ingredients,
 ingredient_1_initial, ingredient_1_percent,
 ingredient_2_initial, ingredient_2_percent)
VALUES ('SESSION123', 'P001', 2, 25.5, 60.0, 12.3, 40.0);
```

### `sessions` Table
**Session management and metadata**

```sql
CREATE TABLE sessions (
    session_code TEXT PRIMARY KEY,
    moderator_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    subject_connected BOOLEAN DEFAULT 0,
    experiment_config TEXT DEFAULT '{}',
    current_phase TEXT DEFAULT 'waiting'
)
```

### `session_state` Table
**Tracks participant state within sessions**

```sql
CREATE TABLE session_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_type TEXT NOT NULL CHECK(user_type IN ('mod', 'sub')),
    participant_id TEXT NOT NULL,
    method TEXT CHECK(method IN ('linear', 'logarithmic', 'exponential', 'slider_based')),
    x_position REAL,
    y_position REAL,
    num_ingredients INTEGER DEFAULT 2,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_type, participant_id)
)
```

## Database Views

### `current_slider_positions`
**Base view for tracking latest slider positions**

```sql
CREATE VIEW current_slider_positions AS
SELECT
    r.session_id,
    r.participant_id,
    r.interface_type,
    r.method,
    r.ingredient_1_conc,
    r.ingredient_2_conc,
    r.ingredient_3_conc,
    r.ingredient_4_conc,
    r.ingredient_5_conc,
    r.ingredient_6_conc,
    r.is_final_response,
    r.questionnaire_response,
    r.created_at as last_update,
    ROW_NUMBER() OVER (
        PARTITION BY r.session_id, r.participant_id
        ORDER BY r.created_at DESC
    ) as row_num
FROM responses r
WHERE r.interface_type = 'slider_based'
```

### `live_slider_monitoring`
**Live monitoring view with status indicators**

```sql
CREATE VIEW live_slider_monitoring AS
SELECT
    session_id,
    participant_id,
    interface_type,
    method,
    ingredient_1_conc,
    ingredient_2_conc,
    ingredient_3_conc,
    ingredient_4_conc,
    ingredient_5_conc,
    ingredient_6_conc,
    is_final_response,
    questionnaire_response,
    last_update,
    CASE
        WHEN is_final_response = 1 THEN 'Final Submission'
        ELSE 'Live Position'
    END as status
FROM current_slider_positions
WHERE row_num = 1
```

**Usage:**
```sql
-- Monitor all live slider positions
SELECT * FROM live_slider_monitoring;

-- Monitor specific session
SELECT * FROM live_slider_monitoring
WHERE session_id = 'SESSION123';

-- Check final submissions only
SELECT * FROM live_slider_monitoring
WHERE status = 'Final Submission';
```

## Indices

### Performance Optimization
```sql
-- Participant response lookups
CREATE INDEX idx_responses_participant
ON responses(participant_id, created_at DESC);

-- Session activity tracking
CREATE INDEX idx_sessions_activity
ON sessions(is_active, last_activity DESC);

-- Session state lookups
CREATE INDEX idx_session_participant
ON session_state(participant_id, user_type);
```

## Data Types and Constraints

### Concentration Values
- **Range**: 0.0 to 100.0 mM typically
- **Precision**: REAL type supports decimal precision
- **NULL handling**: NULL indicates ingredient not used

### Percentages
- **Range**: 0.0 to 100.0 for slider positions
- **Default**: 50.0 for center position

### JSON Fields
- **questionnaire_response**: Structured questionnaire data
- **extra_data**: Flexible metadata storage
- **Format**: Valid JSON strings, parsed by application

### Timestamps
- **Format**: SQLite TIMESTAMP (ISO 8601)
- **Default**: CURRENT_TIMESTAMP for automatic timestamping
- **Timezone**: UTC recommended for consistency

## Migration Strategy

### Schema Evolution
The database includes automatic migration logic in `_migrate_database()`:

1. **Check existing schema** using `PRAGMA table_info()`
2. **Add missing columns** with `ALTER TABLE`
3. **Create new tables** if they don't exist
4. **Update views** by dropping and recreating
5. **Preserve existing data** during all migrations

### Migration Examples
```python
# Add new column
if 'new_column' not in existing_columns:
    cursor.execute("ALTER TABLE responses ADD COLUMN new_column TEXT")

# Migrate data
cursor.execute("""
    INSERT INTO new_table (id, data)
    SELECT id, old_data FROM old_table
""")
```

## Backup and Recovery

### Backup Strategy
```bash
# Database backup
cp experiment_sync.db experiment_sync_backup_$(date +%Y%m%d_%H%M%S).db

# Export to SQL
sqlite3 experiment_sync.db .dump > backup.sql
```

### Data Export
```python
# Export specific data
from sql_handler import export_responses_csv
csv_data = export_responses_csv("SESSION123")
```

## Performance Considerations

### Query Optimization
- Use **prepared statements** for repeated queries
- **Limit results** with appropriate WHERE clauses
- **Index key columns** used in JOIN and WHERE operations

### Storage Efficiency
- **JSON compression** for large extra_data fields
- **Regular cleanup** of old session data
- **Vacuum database** periodically to reclaim space

```sql
-- Cleanup old sessions
DELETE FROM sessions
WHERE is_active = 0 AND last_activity < date('now', '-30 days');

-- Vacuum database
VACUUM;
```

## Data Integrity

### Constraints
- **UNIQUE constraints** prevent duplicate entries
- **CHECK constraints** validate enum values
- **NOT NULL constraints** ensure required fields
- **Foreign key relationships** maintain referential integrity

### Validation
- **Application-level validation** before database insertion
- **Database-level constraints** as final safeguard
- **Transaction management** for atomic operations

### Example Validation
```python
# Validate before insert
if not (0 <= concentration <= 100):
    raise ValueError("Concentration must be between 0 and 100 mM")

if interface_type not in ['grid_2d', 'slider_based']:
    raise ValueError("Invalid interface type")
```