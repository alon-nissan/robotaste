# API Reference - RoboTaste Platform

## Database Functions (`sql_handler.py`)

### Multi-Ingredient Response Storage

#### `save_multi_ingredient_response()`
Saves slider or grid responses with support for 2-6 ingredients.

```python
def save_multi_ingredient_response(
    participant_id: str,
    session_id: str,
    method: str,
    interface_type: str = "slider_based",
    ingredient_concentrations: Optional[Dict[str, float]] = None,
    x_position: Optional[float] = None,
    y_position: Optional[float] = None,
    reaction_time_ms: Optional[int] = None,
    questionnaire_response: Optional[Dict[str, Any]] = None,
    is_final_response: bool = False,
    extra_data: Optional[Dict[str, Any]] = None,
) -> bool
```

**Parameters:**
- `participant_id`: Unique participant identifier
- `session_id`: Session identifier
- `method`: Response method (`"slider_based"`, `"linear"`, etc.)
- `interface_type`: Interface type (`"slider_based"`, `"grid_2d"`)
- `ingredient_concentrations`: Dict of ingredient names to mM concentrations
- `x_position`, `y_position`: Grid coordinates (for 2D interface)
- `reaction_time_ms`: Response time in milliseconds
- `questionnaire_response`: Questionnaire responses as dict
- `is_final_response`: Whether this is the final submission
- `extra_data`: Additional data as dict

**Example Usage:**
```python
# Save slider response
success = save_multi_ingredient_response(
    participant_id="participant_001",
    session_id="SESSION_ABC123",
    method="slider_based",
    interface_type="slider_based",
    ingredient_concentrations={
        "Sugar": 25.5,
        "Salt": 8.3,
        "Citric Acid": 12.7,
        "Caffeine": 4.2
    },
    reaction_time_ms=3200,
    questionnaire_response={
        "sweetness": 7,
        "saltiness": 4,
        "overall_liking": 6
    },
    is_final_response=True
)
```

### Initial Slider Positions

#### `store_initial_slider_positions()`
Stores custom starting positions for sliders.

```python
def store_initial_slider_positions(
    session_id: str,
    participant_id: str,
    num_ingredients: int,
    initial_percentages: Dict[str, float],
    initial_concentrations: Dict[str, float],
    ingredient_names: Optional[List[str]] = None
) -> bool
```

**Example:**
```python
store_initial_slider_positions(
    session_id="SESSION_ABC123",
    participant_id="participant_001",
    num_ingredients=4,
    initial_percentages={
        "Sugar": 30.0,
        "Salt": 70.0,
        "Citric Acid": 45.0,
        "Caffeine": 85.0
    },
    initial_concentrations={
        "Sugar": 15.0,  # mM
        "Salt": 35.0,   # mM
        "Citric Acid": 22.5,  # mM
        "Caffeine": 42.5   # mM
    },
    ingredient_names=["Sugar", "Salt", "Citric Acid", "Caffeine"]
)
```

#### `get_initial_slider_positions()`
Retrieves stored initial positions.

```python
def get_initial_slider_positions(session_id: str, participant_id: str) -> Optional[Dict[str, Any]]
```

**Returns:**
```python
{
    "session_id": "SESSION_ABC123",
    "participant_id": "participant_001",
    "num_ingredients": 4,
    "percentages": {
        "Sugar": 30.0,
        "Salt": 70.0,
        "Citric Acid": 45.0,
        "Caffeine": 85.0
    },
    "concentrations": {
        "Sugar": 15.0,
        "Salt": 35.0,
        "Citric Acid": 22.5,
        "Caffeine": 42.5
    },
    "created_at": "2025-09-17 14:30:25"
}
```

### Live Monitoring

#### `get_live_slider_positions()`
Gets current slider positions for monitoring.

```python
def get_live_slider_positions(session_id: Optional[str] = None) -> pd.DataFrame
```

**Returns DataFrame with columns:**
- `session_id`, `participant_id`, `interface_type`, `method`
- `ingredient_1_conc`, `ingredient_2_conc`, ..., `ingredient_6_conc`
- `is_final_response`, `questionnaire_response`, `last_update`, `status`

### Data Export

#### `export_responses_csv()`
Exports all response data to CSV format.

```python
def export_responses_csv(session_id: Optional[str] = None) -> str
```

**Example:**
```python
# Export all data
csv_data = export_responses_csv()

# Export specific session
csv_data = export_responses_csv("SESSION_ABC123")

# Save to file
with open("experiment_data.csv", "w") as f:
    f.write(csv_data)
```

## Callback Functions (`callback.py`)

### Trial Management

#### `start_trial()`
Initializes a new trial with optional random starting positions.

```python
def start_trial(
    user_type: str,
    participant_id: str,
    method: str,
    num_ingredients: int = 2
) -> bool
```

#### `save_slider_trial()`
Saves completed slider trial results.

```python
def save_slider_trial(participant_id: str, concentrations: dict, method: str) -> bool
```

## Main Application (`main_app.py`)

### Session Management Functions

#### Session Creation and Management
- `create_session()` - Create new experimental session
- `join_session()` - Join existing session as participant
- `get_session_info()` - Retrieve session details

### Interface Components

#### Grid Interface (2 ingredients)
- Traditional X-Y coordinate selection
- Click-based position selection
- Real-time concentration display

#### Slider Interface (3-6 ingredients)
- Independent concentration control per ingredient
- Vertical slider layout with mixer-board styling
- Real-time concentration calculations
- Database-driven initial positions

## Database Schema

### `responses` Table
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
    reaction_time_ms INTEGER,
    questionnaire_response TEXT,  -- JSON format
    is_final_response BOOLEAN DEFAULT 0,
    extra_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### `initial_slider_positions` Table
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

### Database Views

#### `live_slider_monitoring`
Real-time view of current slider positions:
```sql
SELECT session_id, participant_id, interface_type, method,
       ingredient_1_conc, ingredient_2_conc, ingredient_3_conc,
       ingredient_4_conc, ingredient_5_conc, ingredient_6_conc,
       is_final_response, questionnaire_response, last_update,
       CASE WHEN is_final_response = 1 THEN 'Final Submission'
            ELSE 'Live Position' END as status
FROM current_slider_positions
WHERE row_num = 1
```

## Error Handling

### Common Patterns
```python
try:
    success = save_multi_ingredient_response(...)
    if success:
        st.success("✅ Response saved successfully")
    else:
        st.error("❌ Failed to save response")
except Exception as e:
    st.error(f"❌ Error: {e}")
    logger.error(f"Database error: {e}")
```

### Logging
All functions use structured logging:
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Successfully saved response for {participant_id}")
logger.error(f"Error saving response: {e}")
```