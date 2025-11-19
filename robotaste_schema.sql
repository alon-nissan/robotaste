-- RoboTaste Database Schema
-- Simplified Architecture with 5 tables
-- Version: 3.0
-- Last Updated: November 2025

-- Table 1: Users (Taste Testers/Subjects)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
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

-- Table 3: Sessions (Experiment Sessions)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    session_code TEXT UNIQUE NOT NULL,
    user_id TEXT,
    ingredients TEXT,
    question_type_id INTEGER,
    state TEXT NOT NULL DEFAULT 'active',
    current_phase TEXT DEFAULT 'waiting',
    current_cycle INTEGER DEFAULT 0,
    experiment_config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (question_type_id) REFERENCES questionnaire_types(id)
);

-- Table 4: Samples (Complete Cycle Data - ONE ROW PER CYCLE)
CREATE TABLE IF NOT EXISTS samples (
    sample_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    cycle_number INTEGER NOT NULL,
    ingredient_concentration TEXT NOT NULL,
    questionnaire_answer TEXT,
    selection_data TEXT,
    is_final INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP DEFAULT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Table 5: Bayesian Optimization Configuration (Per Session)
CREATE TABLE IF NOT EXISTS bo_configuration (
    session_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    min_samples_for_bo INTEGER DEFAULT 3,
    acquisition_function TEXT DEFAULT 'ei',
    ei_xi REAL DEFAULT 0.01,
    ucb_kappa REAL DEFAULT 2.0,
    kernel_nu REAL DEFAULT 2.5,
    length_scale_initial REAL DEFAULT 1.0,
    length_scale_bounds TEXT DEFAULT '[0.1, 10.0]',
    constant_kernel_bounds TEXT DEFAULT '[0.001, 1000.0]',
    alpha REAL DEFAULT 0.001,
    n_restarts_optimizer INTEGER DEFAULT 10,
    normalize_y INTEGER DEFAULT 1,
    random_state INTEGER DEFAULT 42,
    only_final_responses INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state);
CREATE INDEX IF NOT EXISTS idx_sessions_code ON sessions(session_code);
CREATE INDEX IF NOT EXISTS idx_samples_session_id ON samples(session_id);
CREATE INDEX IF NOT EXISTS idx_samples_is_final ON samples(is_final);
CREATE INDEX IF NOT EXISTS idx_samples_cycle_number ON samples(cycle_number);

-- Insert default questionnaire types
INSERT OR IGNORE INTO questionnaire_types (id, name, data) VALUES
(1, 'hedonic_preference', '{"questions": [{"id": "overall_liking", "type": "scale", "text": "Overall, how much do you like this sample?", "scale": {"min": 1, "max": 9, "labels": {"1": "Dislike Extremely", "5": "Neither Like nor Dislike", "9": "Like Extremely"}}, "required": true}], "target_variable": "overall_liking"}'),
(2, 'unified_feedback', '{"questions": [{"id": "satisfaction", "type": "scale", "text": "How satisfied are you with this sample?", "scale": {"min": 1, "max": 7}, "required": true}, {"id": "confidence", "type": "scale", "text": "How confident are you in your selection?", "scale": {"min": 1, "max": 7}, "required": true}], "target_variable": "satisfaction"}'),
(3, 'multi_attribute', '{"questions": [{"id": "overall_liking", "type": "scale", "text": "Overall Liking", "scale": {"min": 1, "max": 9}, "required": true}, {"id": "sweetness_liking", "type": "scale", "text": "Sweetness Liking", "scale": {"min": 1, "max": 9}, "required": true}, {"id": "flavor_intensity", "type": "scale", "text": "Flavor Intensity", "scale": {"min": 1, "max": 9}, "required": true}], "target_variable": "overall_liking"}'),
(4, 'composite_preference', '{"questions": [{"id": "liking", "type": "scale", "text": "How much do you like it?", "scale": {"min": 1, "max": 9}, "required": true}, {"id": "healthiness", "type": "scale", "text": "How healthy does it seem?", "scale": {"min": 1, "max": 7}, "required": true}], "target_variable": "composite", "transform": "0.7 * liking + 0.3 * healthiness"}');
