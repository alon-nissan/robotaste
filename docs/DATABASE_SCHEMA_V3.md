# RoboTaste Database Schema v3.0

**Version:** 3.0
**Date:** November 2024
**Previous Version:** 2.0
**Breaking Changes:** Yes - requires fresh database or migration

## Overview

Schema version 3.0 introduces comprehensive support for adaptive Bayesian Optimization with full per-cycle tracking of acquisition parameters. This enables detailed research analysis of the optimization process.

## Major Changes from v2.0

### 1. Extended `bo_configuration` Table

Added **16 new columns** for adaptive acquisition and convergence criteria:

**Adaptive Acquisition Parameters:**
- `adaptive_acquisition` (INTEGER, default 1): Enable time-varying exploration
- `exploration_budget` (REAL, default 0.25): Fraction of cycles for exploration phase
- `xi_exploration` (REAL, default 0.1): EI parameter during exploration
- `xi_exploitation` (REAL, default 0.01): EI parameter during exploitation
- `kappa_exploration` (REAL, default 3.0): UCB parameter during exploration
- `kappa_exploitation` (REAL, default 1.0): UCB parameter during exploitation

**Convergence/Stopping Criteria:**
- `convergence_enabled` (INTEGER, default 1): Enable automatic convergence detection
- `min_cycles_1d` (INTEGER, default 10): Minimum cycles for 1D optimization
- `max_cycles_1d` (INTEGER, default 30): Maximum cycles for 1D optimization
- `min_cycles_2d` (INTEGER, default 15): Minimum cycles for 2D optimization
- `max_cycles_2d` (INTEGER, default 50): Maximum cycles for 2D optimization
- `ei_threshold` (REAL, default 0.001): EI convergence threshold
- `ucb_threshold` (REAL, default 0.01): UCB convergence threshold
- `stability_window` (INTEGER, default 5): Window for stability check
- `stability_threshold` (REAL, default 0.05): Std dev threshold for stability
- `consecutive_required` (INTEGER, default 2): Consecutive converged cycles required
- `stopping_mode` (TEXT, default 'suggest_auto'): How to handle convergence

### 2. Extended `samples` Table

Added **6 new columns** for per-cycle BO metadata:

- `acquisition_function` (TEXT, default NULL): "ei" or "ucb"
- `acquisition_xi` (REAL, default NULL): Xi parameter used for this cycle (EI only)
- `acquisition_kappa` (REAL, default NULL): Kappa parameter used for this cycle (UCB only)
- `acquisition_value` (REAL, default NULL): Acquisition function output
- `predicted_value` (REAL, default NULL): GP mean prediction
- `uncertainty` (REAL, default NULL): GP standard deviation

**Important:** Random exploration cycles (0 to min_samples_for_bo-1) will have NULL values for all BO columns.

### 3. New `bo_cycle_analysis` View

Created a comprehensive view for BO research analysis:

```sql
CREATE VIEW bo_cycle_analysis AS
SELECT
    s.session_id,
    s.cycle_number,
    s.acquisition_function,
    s.acquisition_xi,
    s.acquisition_kappa,
    s.acquisition_value,
    s.predicted_value,
    s.uncertainty,
    json_extract(s.ingredient_concentration, '$') as concentrations,
    json_extract(s.questionnaire_answer, '$.overall_liking') as observed_rating,
    (json_extract(s.questionnaire_answer, '$.overall_liking') - s.predicted_value) as prediction_error,
    ses.current_cycle as session_current_cycle,
    bc.max_cycles_2d,
    bc.max_cycles_1d,
    bc.exploration_budget,
    s.created_at
FROM samples s
LEFT JOIN sessions ses ON s.session_id = ses.session_id
LEFT JOIN bo_configuration bc ON s.session_id = bc.session_id
WHERE s.acquisition_function IS NOT NULL
ORDER BY s.session_id, s.cycle_number;
```

### 4. New Index

Added index for performance:
- `idx_samples_acquisition_function` on `samples(acquisition_function)`

## Complete Schema

See `robotaste_schema.sql` for the complete schema definition.

### Table Summary

1. **users** - Participant information
2. **questionnaire_types** - Survey definitions with 5 default types
3. **sessions** - Experiment sessions with configuration
4. **samples** - Per-cycle data with BO metadata (ONE ROW PER CYCLE)
5. **bo_configuration** - Per-session BO configuration with 32 columns

## Data Types and Defaults

### Boolean Fields (INTEGER)
SQLite uses INTEGER for booleans:
- `0` = False
- `1` = True

**Boolean fields:**
- `enabled`, `adaptive_acquisition`, `convergence_enabled`, `normalize_y`, `only_final_responses`

### JSON Fields (TEXT)
Stored as JSON strings, queryable with `json_extract()`:
- `questionnaire_types.data`
- `sessions.ingredients`, `sessions.experiment_config`
- `samples.ingredient_concentration`, `samples.questionnaire_answer`, `samples.selection_data`
- `bo_configuration.length_scale_bounds`, `bo_configuration.constant_kernel_bounds`

### NULL vs Default
- **NULL**: Optional value not provided (e.g., BO metadata for random exploration cycles)
- **Default**: Automatically assigned if not specified (e.g., `adaptive_acquisition = 1`)

## Migration from v2.0

**⚠️ WARNING: This is a breaking change. No automatic migration is provided.**

### Option 1: Fresh Database (Recommended)
1. Backup existing database: `cp robotaste.db robotaste_v2_backup.db`
2. Delete old database: `rm robotaste.db`
3. Restart application - schema will auto-create

### Option 2: Manual Migration
If you need to preserve existing data:

```sql
-- Backup first!
.backup robotaste_v2_backup.db

-- Add new columns to bo_configuration
ALTER TABLE bo_configuration ADD COLUMN adaptive_acquisition INTEGER DEFAULT 1;
ALTER TABLE bo_configuration ADD COLUMN exploration_budget REAL DEFAULT 0.25;
ALTER TABLE bo_configuration ADD COLUMN xi_exploration REAL DEFAULT 0.1;
ALTER TABLE bo_configuration ADD COLUMN xi_exploitation REAL DEFAULT 0.01;
ALTER TABLE bo_configuration ADD COLUMN kappa_exploration REAL DEFAULT 3.0;
ALTER TABLE bo_configuration ADD COLUMN kappa_exploitation REAL DEFAULT 1.0;
ALTER TABLE bo_configuration ADD COLUMN convergence_enabled INTEGER DEFAULT 1;
ALTER TABLE bo_configuration ADD COLUMN min_cycles_1d INTEGER DEFAULT 10;
ALTER TABLE bo_configuration ADD COLUMN max_cycles_1d INTEGER DEFAULT 30;
ALTER TABLE bo_configuration ADD COLUMN min_cycles_2d INTEGER DEFAULT 15;
ALTER TABLE bo_configuration ADD COLUMN max_cycles_2d INTEGER DEFAULT 50;
ALTER TABLE bo_configuration ADD COLUMN ei_threshold REAL DEFAULT 0.001;
ALTER TABLE bo_configuration ADD COLUMN ucb_threshold REAL DEFAULT 0.01;
ALTER TABLE bo_configuration ADD COLUMN stability_window INTEGER DEFAULT 5;
ALTER TABLE bo_configuration ADD COLUMN stability_threshold REAL DEFAULT 0.05;
ALTER TABLE bo_configuration ADD COLUMN consecutive_required INTEGER DEFAULT 2;
ALTER TABLE bo_configuration ADD COLUMN stopping_mode TEXT DEFAULT 'suggest_auto';

-- Add new columns to samples
ALTER TABLE samples ADD COLUMN acquisition_function TEXT DEFAULT NULL;
ALTER TABLE samples ADD COLUMN acquisition_xi REAL DEFAULT NULL;
ALTER TABLE samples ADD COLUMN acquisition_kappa REAL DEFAULT NULL;
ALTER TABLE samples ADD COLUMN acquisition_value REAL DEFAULT NULL;
ALTER TABLE samples ADD COLUMN predicted_value REAL DEFAULT NULL;
ALTER TABLE samples ADD COLUMN uncertainty REAL DEFAULT NULL;

-- Create new index
CREATE INDEX IF NOT EXISTS idx_samples_acquisition_function ON samples(acquisition_function);

-- Create new view
CREATE VIEW IF NOT EXISTS bo_cycle_analysis AS
SELECT
    s.session_id,
    s.cycle_number,
    s.acquisition_function,
    s.acquisition_xi,
    s.acquisition_kappa,
    s.acquisition_value,
    s.predicted_value,
    s.uncertainty,
    json_extract(s.ingredient_concentration, '$') as concentrations,
    json_extract(s.questionnaire_answer, '$.overall_liking') as observed_rating,
    (json_extract(s.questionnaire_answer, '$.overall_liking') - s.predicted_value) as prediction_error,
    ses.current_cycle as session_current_cycle,
    bc.max_cycles_2d,
    bc.max_cycles_1d,
    bc.exploration_budget,
    s.created_at
FROM samples s
LEFT JOIN sessions ses ON s.session_id = ses.session_id
LEFT JOIN bo_configuration bc ON s.session_id = bc.session_id
WHERE s.acquisition_function IS NOT NULL
ORDER BY s.session_id, s.cycle_number;
```

**Note:** Existing samples will have NULL BO metadata since the data wasn't captured in v2.0.

## Example Queries

### 1. View All BO Cycles for a Session
```sql
SELECT * FROM bo_cycle_analysis
WHERE session_id = 'your-session-id';
```

### 2. Check Adaptive Parameters for a Session
```sql
SELECT
    adaptive_acquisition,
    exploration_budget,
    xi_exploration,
    xi_exploitation,
    kappa_exploration,
    kappa_exploitation
FROM bo_configuration
WHERE session_id = 'your-session-id';
```

### 3. Analyze Prediction Accuracy
```sql
SELECT
    cycle_number,
    acquisition_xi,
    predicted_value,
    observed_rating,
    ABS(observed_rating - predicted_value) as abs_error
FROM bo_cycle_analysis
WHERE session_id = 'your-session-id'
ORDER BY cycle_number;
```

### 4. Count Exploration vs Exploitation Cycles
```sql
SELECT
    CASE
        WHEN cycle_number <= (max_cycles_1d * exploration_budget)
        THEN 'Exploration'
        ELSE 'Exploitation'
    END as phase,
    COUNT(*) as n_cycles
FROM bo_cycle_analysis
WHERE session_id = 'your-session-id'
GROUP BY phase;
```

### 5. Find Optimal Sample
```sql
SELECT
    cycle_number,
    concentrations,
    observed_rating
FROM bo_cycle_analysis
WHERE session_id = 'your-session-id'
ORDER BY observed_rating DESC
LIMIT 1;
```

## Data Validation

### Check for Missing BO Metadata
```sql
-- Should return 0 for BO cycles (cycle >= min_samples_for_bo)
SELECT COUNT(*) as missing_metadata
FROM samples s
JOIN sessions ses ON s.session_id = ses.session_id
JOIN bo_configuration bc ON s.session_id = bc.session_id
WHERE bc.enabled = 1
  AND s.cycle_number >= bc.min_samples_for_bo
  AND s.acquisition_function IS NULL;
```

### Verify Adaptive Parameters
```sql
-- Check that xi changes over cycles (adaptive mode)
SELECT
    session_id,
    COUNT(DISTINCT acquisition_xi) as unique_xi_values,
    MIN(acquisition_xi) as min_xi,
    MAX(acquisition_xi) as max_xi
FROM bo_cycle_analysis
WHERE acquisition_function = 'ei'
GROUP BY session_id
HAVING unique_xi_values > 1;  -- Should have multiple values if adaptive
```

## Performance Considerations

### Indexes
The schema includes 7 indexes for optimal query performance:
- `idx_sessions_user_id`, `idx_sessions_state`, `idx_sessions_code`
- `idx_samples_session_id`, `idx_samples_is_final`, `idx_samples_cycle_number`, `idx_samples_acquisition_function`

### View Performance
The `bo_cycle_analysis` view joins 3 tables and extracts JSON. For large datasets:
- Add `WHERE session_id = 'specific-id'` to queries
- Consider caching results for analysis
- Use indexed columns in WHERE clauses

### Storage
- Typical session (30 cycles): ~50 KB
- 100 sessions: ~5 MB
- No storage issues expected for normal use

## Backward Compatibility

### Removed Fields: None
All v2.0 fields are retained.

### Added Fields: 22
- 16 in `bo_configuration`
- 6 in `samples`

### Changed Defaults: 1
- `bo_configuration.adaptive_acquisition`: Now defaults to `1` (enabled)

### Code Compatibility
- **v3.0 code REQUIRES v3.0 schema** (new columns)
- v2.0 code will fail on v3.0 schema (missing column errors)
- No cross-compatibility between versions

## Testing

Run schema validation:
```bash
python3 test_schema_validation.py
```

Expected output:
```
✓ All 22 new columns present
✓ Default values correct
✓ Indexes created
✓ View created and queryable
✓ JSON extraction working
```

## Troubleshooting

### Error: "no such column: acquisition_function"
**Cause:** Using v3.0 code with v2.0 database
**Solution:** Migrate database or create fresh database

### Error: "UNIQUE constraint failed: bo_configuration.session_id"
**Cause:** Attempting to insert duplicate BO config
**Solution:** Use `INSERT OR REPLACE` in `update_session_with_config()`

### Issue: All BO metadata is NULL
**Cause:** Data pipeline not propagating acquisition metadata
**Solution:** Verify fixes in callback.py (line 1325) and subject_interface.py (lines 451-452, 1104-1105)

## Future Schema Changes

Potential additions for v4.0:
- `participant_model_state` table for per-participant GP models
- `convergence_history` table for detailed convergence tracking
- Additional indexes for common research queries

## References

- Schema definition: `robotaste_schema.sql`
- SQL handler: `sql_handler.py`
- BO implementation: `bayesian_optimizer.py`
- Adaptive acquisition docs: `docs/ADAPTIVE_ACQUISITION.md`

---

**Document Version:** 3.0
**Schema Version:** 3.0
**Last Updated:** November 2024
**Next Review:** After 50 production sessions
