-- RoboTaste Enhanced Database Schema
-- Based on simplified architecture with JSON storage
-- One moderator, one taster per session

-- Users table stores taste testers (subjects)
CREATE TABLE IF NOT EXISTS "users" (
	"id"	TEXT NOT NULL UNIQUE,
	"created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMP,
	PRIMARY KEY("id")
);

-- Questionnaire types define different types of surveys/questions
CREATE TABLE IF NOT EXISTS "questionnaire_types" (
	"id"	INTEGER NOT NULL UNIQUE,
	"name"	TEXT NOT NULL,
	"data"	TEXT NOT NULL,
	"created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMP,
	PRIMARY KEY("id")
);

-- Sessions track experiments with their configuration
-- session_id serves as both UUID and join code
CREATE TABLE IF NOT EXISTS "sessions" (
	"session_id"	TEXT NOT NULL UNIQUE,
	"user_id"	TEXT NOT NULL,
	"ingredients"	TEXT NOT NULL,  -- JSON: [{position, name, min, max, unit}, ...]
	"question_type_id"	INTEGER NOT NULL,
	"state"	TEXT NOT NULL CHECK (state IN ('active', 'completed', 'cancelled')),
	"current_phase"	TEXT NOT NULL DEFAULT 'waiting',  -- Current experiment phase for device sync
	"experiment_config" TEXT,  -- JSON: full config backup (num_ingredients, interface_type, method, current_cycle, etc.)
	"created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("session_id"),
   	FOREIGN KEY("question_type_id") REFERENCES "questionnaire_types"("id"),
    FOREIGN KEY("user_id") REFERENCES "users"("id")
);

-- Samples store complete cycle data (taste + questionnaire + selection)
-- Each row = one complete tasting cycle
CREATE TABLE IF NOT EXISTS "samples" (
	"sample_id"	TEXT NOT NULL UNIQUE,
	"session_id"	TEXT NOT NULL,
	"cycle_number"	INTEGER NOT NULL,  -- Which cycle: 1, 2, 3, ...
	"ingredient_concentration"	TEXT NOT NULL,  -- JSON: {"Sugar": 36.5, "Salt": 5.2}
	"questionnaire_answer"	TEXT NOT NULL,  -- JSON: {"overall_liking": 7, "sweetness": 6, ...}
	"selection_data"	TEXT,  -- JSON: {interface_type, x_position, y_position, method} OR {slider_values, ...}
	"is_final"	INTEGER DEFAULT 0,  -- 1 if last cycle in session
	"created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("sample_id"),
	FOREIGN KEY("session_id") REFERENCES "sessions"("session_id")
);

-- Bayesian Optimization configuration parameters for each session
CREATE TABLE IF NOT EXISTS "bo_configuration" (
	"session_id"	TEXT NOT NULL UNIQUE,

	-- Core BO parameters
	"enabled"	INTEGER DEFAULT 1,  -- 0=disabled, 1=enabled
	"min_samples_for_bo"	INTEGER DEFAULT 3,  -- Minimum cycles before BO activates
	"acquisition_function"	TEXT NOT NULL DEFAULT 'ei',  -- 'ei' or 'ucb'
	"ei_xi"	REAL NOT NULL DEFAULT 0.01,  -- Exploration parameter for EI
	"ucb_kappa"	REAL NOT NULL DEFAULT 2.0,  -- Exploration parameter for UCB

	-- Gaussian Process kernel parameters
	"kernel_nu"	REAL NOT NULL DEFAULT 2.5,  -- Matern smoothness: 0.5, 1.5, 2.5
	"length_scale_initial"	REAL DEFAULT 1.0,  -- Initial length scale
	"length_scale_bounds"	TEXT DEFAULT '[0.1, 10.0]',  -- JSON: [min, max]
	"constant_kernel_bounds"	TEXT DEFAULT '[0.001, 1000.0]',  -- JSON: [min, max]

	-- GP training parameters
	"alpha"	REAL NOT NULL DEFAULT 0.001,  -- Noise/regularization parameter
	"n_restarts_optimizer"	INTEGER NOT NULL DEFAULT 10,  -- GP hyperparameter optimization restarts
	"normalize_y"	INTEGER NOT NULL DEFAULT 1,  -- 0=false, 1=true - normalize target values
	"random_state"	INTEGER NOT NULL DEFAULT 42,  -- Random seed for reproducibility
	"only_final_responses"	INTEGER DEFAULT 1,  -- 0=use all cycles, 1=use only final for training

	"created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("session_id"),
   	FOREIGN KEY("session_id") REFERENCES "sessions"("session_id"),
    CONSTRAINT valid_acquisition_function CHECK (acquisition_function IN ('ei', 'ucb')),
    CONSTRAINT valid_numerical_values CHECK (
        ei_xi >= 0 AND
        ucb_kappa >= 0 AND
        kernel_nu >= 0 AND
        alpha >= 0
    )
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_question_type_id ON sessions(question_type_id);
CREATE INDEX IF NOT EXISTS idx_samples_session_id ON samples(session_id);
CREATE INDEX IF NOT EXISTS idx_samples_cycle ON samples(session_id, cycle_number);
CREATE INDEX IF NOT EXISTS idx_samples_final ON samples(is_final, session_id);

-- Triggers for automatic updated_at timestamps
CREATE TRIGGER IF NOT EXISTS update_sessions_timestamp
AFTER UPDATE ON sessions
FOR EACH ROW
BEGIN
    UPDATE sessions SET updated_at = CURRENT_TIMESTAMP
    WHERE session_id = NEW.session_id;
END;

CREATE TRIGGER IF NOT EXISTS update_samples_timestamp
AFTER UPDATE ON samples
FOR EACH ROW
BEGIN
    UPDATE samples SET updated_at = CURRENT_TIMESTAMP
    WHERE sample_id = NEW.sample_id;
END;

CREATE TRIGGER IF NOT EXISTS update_bo_configuration_timestamp
AFTER UPDATE ON bo_configuration
FOR EACH ROW
BEGIN
    UPDATE bo_configuration SET updated_at = CURRENT_TIMESTAMP
    WHERE session_id = NEW.session_id;
END;
