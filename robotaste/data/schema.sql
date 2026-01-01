-- RoboTaste Database Schema
-- Architecture with Protocol System
-- Version: 4.0
-- Last Updated: January 2026

-- Table 1: Users (Taste Testers/Subjects)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT,          -- New field
    gender TEXT,        -- New field
    age INTEGER,        -- New field
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL
);

-- Table 2: Questionnaire Types (Survey Definitions)
CREATE TABLE IF NOT EXISTS questionnaire_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL
);

-- Table 3: Protocol Library (Reusable Experiment Protocols)
CREATE TABLE IF NOT EXISTS protocol_library (
    protocol_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    protocol_json TEXT NOT NULL,  -- Complete protocol stored as JSON
    protocol_hash TEXT,  -- SHA256 for version control
    version TEXT DEFAULT '1.0',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_archived INTEGER DEFAULT 0,
    tags TEXT,  -- JSON array
    deleted_at TIMESTAMP DEFAULT NULL
);

-- Table 4: Sessions (Experiment Sessions)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    session_code TEXT UNIQUE NOT NULL,
    user_id TEXT,
    ingredients TEXT,
    question_type_id INTEGER,
    protocol_id TEXT,  -- Link to protocol_library (optional)
    state TEXT NOT NULL DEFAULT 'active',
    current_phase TEXT DEFAULT 'waiting',
    current_cycle INTEGER DEFAULT 0,
    experiment_config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (question_type_id) REFERENCES questionnaire_types(id),
    FOREIGN KEY (protocol_id) REFERENCES protocol_library(protocol_id)
);

-- Table 5: Samples (Complete Cycle Data - ONE ROW PER CYCLE)
CREATE TABLE IF NOT EXISTS samples (
    sample_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    cycle_number INTEGER NOT NULL,
    ingredient_concentration TEXT NOT NULL,
    questionnaire_answer TEXT,
    selection_data TEXT,
    -- Sample selection mode tracking (for mixed-mode protocols)
    selection_mode TEXT DEFAULT 'user_selected',  -- "user_selected", "bo_selected", "predetermined"
    was_bo_overridden INTEGER DEFAULT 0,  -- 1 if user overrode BO suggestion
    -- Bayesian Optimization prediction data (extracted from selection_data for easy querying)
    acquisition_function TEXT DEFAULT NULL,
    acquisition_xi REAL DEFAULT NULL,
    acquisition_kappa REAL DEFAULT NULL,
    acquisition_value REAL DEFAULT NULL,
    predicted_value REAL DEFAULT NULL,
    uncertainty REAL DEFAULT NULL,
    is_final INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Table 6: Bayesian Optimization Configuration (Per Session)
CREATE TABLE IF NOT EXISTS bo_configuration (
    session_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    min_samples_for_bo INTEGER DEFAULT 3,
    acquisition_function TEXT DEFAULT 'ei',
    ei_xi REAL DEFAULT 0.01,
    ucb_kappa REAL DEFAULT 2.0,
    -- Adaptive acquisition parameters
    adaptive_acquisition INTEGER DEFAULT 1,
    exploration_budget REAL DEFAULT 0.25,
    xi_exploration REAL DEFAULT 0.1,
    xi_exploitation REAL DEFAULT 0.01,
    kappa_exploration REAL DEFAULT 3.0,
    kappa_exploitation REAL DEFAULT 1.0,
    -- Gaussian Process kernel parameters
    kernel_nu REAL DEFAULT 2.5,
    length_scale_initial REAL DEFAULT 1.0,
    length_scale_bounds TEXT DEFAULT '[0.1, 10.0]',
    constant_kernel_bounds TEXT DEFAULT '[0.001, 1000.0]',
    alpha REAL DEFAULT 0.001,
    n_restarts_optimizer INTEGER DEFAULT 10,
    normalize_y INTEGER DEFAULT 1,
    random_state INTEGER DEFAULT 42,
    only_final_responses INTEGER DEFAULT 1,
    -- Convergence/stopping criteria
    convergence_enabled INTEGER DEFAULT 1,
    min_cycles_1d INTEGER DEFAULT 10,
    max_cycles_1d INTEGER DEFAULT 30,
    min_cycles_2d INTEGER DEFAULT 15,
    max_cycles_2d INTEGER DEFAULT 50,
    ei_threshold REAL DEFAULT 0.001,
    ucb_threshold REAL DEFAULT 0.01,
    stability_window INTEGER DEFAULT 5,
    stability_threshold REAL DEFAULT 0.05,
    consecutive_required INTEGER DEFAULT 2,
    stopping_mode TEXT DEFAULT 'suggest_auto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Create indexes for performance
-- Protocol Library indexes
CREATE INDEX IF NOT EXISTS idx_protocol_library_name ON protocol_library(name);
CREATE INDEX IF NOT EXISTS idx_protocol_library_tags ON protocol_library(tags);
CREATE INDEX IF NOT EXISTS idx_protocol_library_created_by ON protocol_library(created_by);
CREATE INDEX IF NOT EXISTS idx_protocol_library_archived ON protocol_library(is_archived);

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state);
CREATE INDEX IF NOT EXISTS idx_sessions_code ON sessions(session_code);
CREATE INDEX IF NOT EXISTS idx_sessions_protocol_id ON sessions(protocol_id);

-- Samples indexes
CREATE INDEX IF NOT EXISTS idx_samples_session_id ON samples(session_id);
CREATE INDEX IF NOT EXISTS idx_samples_is_final ON samples(is_final);
CREATE INDEX IF NOT EXISTS idx_samples_cycle_number ON samples(cycle_number);
CREATE INDEX IF NOT EXISTS idx_samples_acquisition_function ON samples(acquisition_function);
CREATE INDEX IF NOT EXISTS idx_samples_selection_mode ON samples(selection_mode);

-- Create view for Bayesian Optimization cycle analysis
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

-- Insert default questionnaire types
INSERT OR IGNORE INTO questionnaire_types (id, name, data) VALUES
(1, 'hedonic_continuous', '{"questions": [{"id": "overall_liking", "type": "slider", "label": "How much do you like this sample?", "min": 1.0, "max": 9.0, "step": 0.01, "default": 5.0, "display_type": "slider_continuous", "scale_labels": {"1": "Dislike Extremely", "5": "Neither Like nor Dislike", "9": "Like Extremely"}, "required": true}], "target_variable": "overall_liking", "bayesian_target": {"variable": "overall_liking", "transform": "identity", "higher_is_better": true, "expected_range": [1.0, 9.0], "optimal_threshold": 7.0}}'),
(2, 'unified_feedback', '{"questions": [{"id": "satisfaction", "type": "slider", "label": "How satisfied are you with this sample?", "min": 1, "max": 7, "step": 1, "default": 4, "required": true}, {"id": "confidence", "type": "slider", "label": "How confident are you in your selection?", "min": 1, "max": 7, "step": 1, "default": 4, "required": true}], "target_variable": "satisfaction", "bayesian_target": {"variable": "satisfaction", "transform": "identity", "higher_is_better": true, "expected_range": [1, 7], "optimal_threshold": 5.5}}'),
(3, 'multi_attribute', '{"questions": [{"id": "overall_liking", "type": "slider", "label": "Overall Liking", "min": 1, "max": 9, "step": 1, "default": 5, "required": true}, {"id": "sweetness_liking", "type": "slider", "label": "Sweetness Liking", "min": 1, "max": 9, "step": 1, "default": 5, "required": true}, {"id": "flavor_intensity", "type": "slider", "label": "Flavor Intensity", "min": 1, "max": 9, "step": 1, "default": 5, "required": false}], "target_variable": "overall_liking", "bayesian_target": {"variable": "overall_liking", "transform": "identity", "higher_is_better": true, "expected_range": [1, 9], "optimal_threshold": 7.0}}'),
(4, 'composite_preference', '{"questions": [{"id": "liking", "type": "slider", "label": "How much do you like it?", "min": 1, "max": 9, "step": 1, "default": 5, "required": true}, {"id": "healthiness_perception", "type": "slider", "label": "How healthy does it seem?", "min": 1, "max": 7, "step": 1, "default": 4, "required": true}], "target_variable": "composite", "bayesian_target": {"variable": "composite", "formula": "0.7 * liking + 0.3 * healthiness_perception", "transform": "identity", "higher_is_better": true, "expected_range": [1, 8.5], "optimal_threshold": 6.0}}'),
(5, 'hedonic_discrete', '{"questions": [{"id": "overall_liking", "type": "slider", "label": "How much do you like this sample?", "min": 1, "max": 9, "step": 1, "default": 5, "display_type": "pillboxes", "scale_labels": {"1": "Dislike Extremely", "2": "Dislike Very Much", "3": "Dislike Moderately", "4": "Dislike Slightly", "5": "Neither Like nor Dislike", "6": "Like Slightly", "7": "Like Moderately", "8": "Like Very Much", "9": "Like Extremely"}, "required": true}], "target_variable": "overall_liking", "bayesian_target": {"variable": "overall_liking", "transform": "identity", "higher_is_better": true, "expected_range": [1, 9], "optimal_threshold": 7.0}}'),
(6, 'intensity_continuous', '{"name": "Intensity Scale (Continuous)", "description": "Continuous 9-point intensity scale for measuring attribute strength.", "version": "1.0", "questions": [{"id": "sweetness_intensity", "type": "slider", "label": "How sweet is this sample?", "help_text": "Rate the sweetness intensity from 1 (No sweet) to 9 (Very strong).", "scale_labels": {"1": "No sweet", "3": "Light", "5": "Medium", "7": "Strong", "9": "Very strong"}, "min": 1.0, "max": 9.0, "default": 5.0, "step": 0.01, "required": true, "display_type": "slider_continuous"}], "bayesian_target": {"variable": "sweetness_intensity", "transform": "identity", "higher_is_better": false, "description": "Measure sweetness intensity.", "expected_range": [1.0, 9.0], "optimal_threshold": 5.0}}');
