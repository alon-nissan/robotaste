/**
 * TypeScript Type Definitions — Shared data shapes for the entire app.
 *
 * === WHAT IS THIS? ===
 * TypeScript types define the "shape" of data objects. They're like Python
 * type hints or dataclasses — they describe what fields an object has
 * and what types those fields are.
 *
 * They don't exist at runtime (they're erased during compilation).
 * They're purely for development: your editor will warn you if you
 * try to access a field that doesn't exist, or pass the wrong type.
 *
 * === KEY SYNTAX ===
 * - `interface`: Defines the shape of an object (like Python's TypedDict)
 * - `field: string`: This field must be a string
 * - `field?: number`: The ? means this field is optional (can be undefined)
 * - `field: string[]`: An array of strings (like Python's List[str])
 * - `Record<string, number>`: A dictionary with string keys and number values
 *   (like Python's Dict[str, float])
 *
 * === WHY THESE SPECIFIC TYPES? ===
 * These match the JSON data returned by our FastAPI endpoints,
 * which in turn match the data in robotaste.db (SQLite).
 */


// ─── PROTOCOL ──────────────────────────────────────────────────────────────
// Represents an experiment protocol stored in the database.
// Matches the data returned by GET /api/protocols

export interface Protocol {
  protocol_id: string;           // UUID (unique identifier)
  name: string;                  // Human-readable name like "Sucrose Dose Response"
  description?: string;          // Optional description text
  version?: string;              // Version string like "1.0"
  tags?: string[];               // Optional tags like ["taste", "sucrose"]
  ingredients: Ingredient[];     // List of ingredients used
  stopping_criteria?: StoppingCriteria;  // When does the experiment end?
  questionnaire_type?: string;   // Which questionnaire to show
  sample_selection_schedule?: ScheduleBlock[];  // How samples are selected per cycle
  pump_config?: PumpConfig;      // Pump hardware configuration
  bayesian_optimization?: Record<string, unknown>;  // BO settings (flexible shape)
  created_at?: string;           // ISO timestamp
  updated_at?: string;
  is_archived?: boolean;
}


// ─── INGREDIENT ────────────────────────────────────────────────────────────
// A single ingredient in the experiment (e.g., Sugar, Salt)

export interface Ingredient {
  name: string;                  // Ingredient name (e.g., "Sucrose")
  min_concentration: number;     // Minimum concentration in mM
  max_concentration: number;     // Maximum concentration in mM
}


// ─── STOPPING CRITERIA ─────────────────────────────────────────────────────
// Defines when the experiment should end

export interface StoppingCriteria {
  max_cycles: number;            // Maximum number of taste cycles
}


// ─── SCHEDULE BLOCK ────────────────────────────────────────────────────────
// A block in the sample selection schedule

export interface ScheduleBlock {
  cycle_range: {
    start: number;               // First cycle in this block
    end: number;                 // Last cycle in this block
  };
  mode: string;                  // "user_selected", "bo_selected", "predetermined", etc.
  predetermined_samples?: Array<{
    cycle: number;
    concentrations: Record<string, number>;  // { "Sugar": 10.0, "Salt": 2.0 }
  }>;
  bo_config?: Record<string, unknown>;
}


// ─── PUMP CONFIG ───────────────────────────────────────────────────────────
// Configuration for the syringe pump hardware

export interface PumpConfig {
  enabled: boolean;              // Whether pumps are connected
  port?: string;                 // Serial port (e.g., "/dev/tty.usbserial")
  baud_rate?: number;
}


// ─── SESSION ───────────────────────────────────────────────────────────────
// Represents an active experiment session

export interface Session {
  session_id: string;            // UUID
  session_code: string;          // 6-character human-readable code
  moderator_name?: string;
  state: string;                 // "active", "completed", etc.
  current_phase: string;         // "waiting", "registration", "selection", etc.
  current_cycle: number;
  experiment_config?: Record<string, unknown>;  // Full config (flexible shape)
  created_at?: string;
}


// ─── SESSION STATUS ────────────────────────────────────────────────────────
// Status data returned by the monitoring endpoint

export interface SessionStatus {
  session_id: string;
  session_code: string;
  current_phase: string;
  current_cycle: number;
  state: string;
  total_cycles: number;
  experiment_config: Record<string, unknown>;
}


// ─── PUMP STATUS ───────────────────────────────────────────────────────────
// Pump volume status for monitoring

export interface PumpIngredientStatus {
  current_ul: number;            // Current volume remaining (microliters)
  max_capacity_ul: number;       // Maximum syringe capacity
  percent_remaining: number;     // 0-100
  alert_active: boolean;         // True if critically low
}

export interface PumpStatus {
  pump_enabled: boolean;
  ingredients: Record<string, PumpIngredientStatus>;  // { "Sugar": {...}, "Salt": {...} }
}


// ─── PUMP GLOBAL STATUS ───────────────────────────────────────────────────
// Cross-session volume tracking (persists between sessions)

export interface PumpGlobalIngredientStatus {
  pump_address: number;
  current_ul: number;
  max_capacity_ul: number;
  percent_remaining: number;
  alert_active: boolean;
  alert_threshold_ul: number;
  total_dispensed_ul: number;
  last_session_id: string | null;
  last_dispensed_at: string | null;
  last_refilled_at: string | null;
}

export interface PumpGlobalStatus {
  pump_enabled: boolean;
  protocol_id?: string;
  ingredients: Record<string, PumpGlobalIngredientStatus>;
  error?: string;
}


// ─── REFILL OPERATION ─────────────────────────────────────────────────────
// Status of a refill withdraw/purge operation

export interface RefillOperationStatus {
  operation_id: number;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  operation_type: 'withdraw' | 'purge';
  ingredient: string;
  volume_ul: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export type RefillStep = 'idle' | 'withdrawing' | 'swap_syringe' | 'purging' | 'enter_volume' | 'done';


// ─── SAMPLE ────────────────────────────────────────────────────────────────
// A single taste trial sample

export interface Sample {
  cycle_number: number;
  ingredient_concentration: Record<string, number>;  // { "Sugar": 15.0, "Salt": 3.0 }
  questionnaire_answer?: Record<string, unknown>;    // Participant's response
  created_at?: string;
}


// ─── MODE INFO ─────────────────────────────────────────────────────────────
// Current mode information for monitoring

export interface ModeInfo {
  current_mode: string;          // "user_selected", "bo_selected", "predetermined"
  current_cycle: number;
  is_mixed_mode: boolean;
  all_modes: string[];
  schedule?: ScheduleBlock[];
}


// ─── PARTICIPANT ───────────────────────────────────────────────────────────
// Participant registration data

export interface Participant {
  user_id: string;
  name: string;
  age: number;
  gender: string;
}


// ─── CONSENT CONFIG ────────────────────────────────────────────────────────
// Protocol-driven consent form configuration

export interface ConsentConfig {
  explanation?: string;
  medical_disclaimers?: string[];
  contact_info?: string;
  consent_label?: string;
}


// ─── QUESTIONNAIRE CONFIG ──────────────────────────────────────────────────
// Dynamic questionnaire form configuration

export interface QuestionConfig {
  id: string;
  label: string;
  type: 'slider' | 'dropdown' | 'text_input' | 'text_area' | 'pillbox';
  required?: boolean;
  min?: number;
  max?: number;
  step?: number;
  default?: number | string;
  options?: string[];
  scale_labels?: Record<string, string>;
}

export interface QuestionnaireConfig {
  name: string;
  title?: string;
  questions: QuestionConfig[];
}


// ─── BO MODEL ──────────────────────────────────────────────────────────────
// Bayesian Optimization model data for visualization

export interface BOPrediction {
  x: number[];
  mean: number[];
  std: number[];
  acquisition: number[];
}

export interface BOModel {
  predictions: BOPrediction;
  observations: { x: number[]; y: number[] };
  suggestion?: { x: number; predicted_value: number; uncertainty: number };
  ingredient_name: string;
}

export interface BOModel2D {
  predictions: {
    x: number[];
    y: number[];
    mean: number[][];
    std: number[][];
    acquisition: number[][];
  };
  observations: { x: number[]; y: number[]; z: number[] };
  suggestion?: { x: number; y: number; predicted_value: number };
  ingredient_names: [string, string];
}


// ─── BO SUGGESTION ─────────────────────────────────────────────────────────
// BO suggestion for subject selection

export interface BOSuggestion {
  concentrations: Record<string, number>;
  predicted_value?: number;
  uncertainty?: number;
  grid_coordinates?: { x: number; y: number };
  slider_values?: Record<string, number>;
}


// ─── CUSTOM PHASE ──────────────────────────────────────────────────────────
// Protocol-defined custom phase configuration

export interface CustomPhaseConfig {
  type: 'text' | 'media' | 'break' | 'survey';
  title?: string;
  body?: string;
  image_url?: string;
  media_type?: 'image' | 'video';
  media_url?: string;
  caption?: string;
  duration_seconds?: number;
  message?: string;
  questions?: QuestionConfig[];
}


// ─── SESSION SUMMARY ───────────────────────────────────────────────────────
// Summary statistics for completion screen

export interface SessionSummary {
  total_cycles: number;
  duration_seconds?: number;
  protocol_name?: string;
  samples_count?: number;
}
