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
  schema_version?: string;
  created_by?: string;
  tags?: string[];               // Optional tags like ["taste", "sucrose"]
  ingredients: Ingredient[];     // List of ingredients used
  stopping_criteria?: StoppingCriteria;  // When does the experiment end?
  questionnaire_type?: string;   // Which questionnaire to show (legacy)
  questionnaire?: InlineQuestionnaire;   // Inline questionnaire config (preferred)
  sample_selection_schedule?: ScheduleBlock[];  // How samples are selected per cycle
  pump_config?: PumpConfig;      // Pump hardware configuration
  bayesian_optimization?: BayesianOptimizationConfig;
  consent_form?: ConsentFormConfig;
  instructions_screen?: InstructionsScreenConfig;
  loading_screen?: LoadingScreenConfig;
  phase_sequence?: PhaseSequenceConfig;
  data_collection?: DataCollectionConfig;
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
  unit?: string;                 // Concentration unit (default "mM")
  molecular_weight?: number;     // Molecular weight in g/mol
  stock_concentration_mM?: number; // Stock solution concentration
  is_diluent?: boolean;          // Whether this is the diluent (e.g., Water)
}


// ─── STOPPING CRITERIA ─────────────────────────────────────────────────────
// Defines when the experiment should end

export interface StoppingCriteria {
  max_cycles: number;            // Maximum number of taste cycles
  min_cycles?: number;           // Minimum cycles before stopping allowed
  mode?: 'manual_only' | 'suggest_auto' | 'auto_with_minimum';
  convergence_detection?: boolean;
  early_termination_allowed?: boolean;
  ei_threshold?: number;
  stability_threshold?: number;
}


// ─── SCHEDULE BLOCK ────────────────────────────────────────────────────────
// A block in the sample selection schedule

export type SelectionMode = 'predetermined' | 'predetermined_randomized' | 'user_selected' | 'bo_selected';

export interface PredeterminedSample {
  cycle: number;
  concentrations: Record<string, number>;  // { "Sugar": 10.0, "Salt": 2.0 }
}

export interface SampleBankEntry {
  id: string;                    // Unique sample ID (e.g., "A", "B")
  concentrations: Record<string, number>;
  label?: string;                // Human-readable label (e.g., "Low Sugar")
}

export interface SampleBankConfig {
  samples: SampleBankEntry[];
  design_type: 'latin_square' | 'randomized';
  constraints?: {
    prevent_consecutive_repeats?: boolean;
    ensure_all_used_before_repeat?: boolean;
  };
}

export interface ScheduleBlock {
  cycle_range: {
    start: number;               // First cycle in this block
    end: number;                 // Last cycle in this block
  };
  mode: SelectionMode;
  predetermined_samples?: PredeterminedSample[];
  sample_bank?: SampleBankConfig;
  config?: {
    interface_type?: string;
    randomize_start?: boolean;
    show_bo_suggestion?: boolean;
    allow_override?: boolean;
    auto_accept_suggestion?: boolean;
  };
}


// ─── PUMP CONFIG ───────────────────────────────────────────────────────────
// Configuration for the syringe pump hardware

export interface PumpMapping {
  address: number;               // Pump address (0-99, must be <10 for burst mode)
  ingredient: string;            // Matches an ingredient name
  syringe_diameter_mm: number;   // Syringe inner diameter
  max_rate_ul_min: number;       // Maximum dispensing rate
  stock_concentration_mM: number;
  description?: string;
  dual_syringe?: boolean;        // Dual-syringe mode doubles effective capacity
  tube_volume_ul?: number;
  purge_volume_ul?: number;
}

export interface PumpConfig {
  enabled: boolean;              // Whether pumps are connected
  port?: string;                 // Serial port (e.g., "/dev/tty.usbserial") — legacy field
  serial_port?: string;          // Serial port (canonical field name)
  baud_rate?: number;
  pumps?: PumpMapping[];
  total_volume_ml?: number;      // Total sample volume per dispensing
  dispensing_rate_ul_min?: number;
  simultaneous_dispensing?: boolean;
  use_burst_mode?: boolean;
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
  help_text?: string;
  min?: number;
  max?: number;
  step?: number;
  default?: number | string;
  options?: string[];
  scale_labels?: Record<string, string>;
  display_type?: string;
  color_scale?: string;
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


// ─── INLINE QUESTIONNAIRE ────────────────────────────────────────────────────
// Full questionnaire config embedded in a protocol

export interface BayesianTarget {
  variable: string;              // Question ID to optimize, or "composite"
  formula?: string;              // Composite formula (e.g., "0.7 * liking + 0.3 * health")
  transform: 'identity' | 'log' | 'normalize';
  higher_is_better: boolean;
  description?: string;
  expected_range?: [number, number];
  optimal_threshold?: number;
}

export interface InlineQuestionnaire {
  name: string;
  description?: string;
  version?: string;
  citation?: string;
  questions: QuestionConfig[];
  bayesian_target?: BayesianTarget;
}


// ─── BAYESIAN OPTIMIZATION CONFIG ─────────────────────────────────────────
// Full BO algorithm settings

export interface BayesianOptimizationConfig {
  enabled: boolean;
  min_samples_for_bo?: number;   // Minimum observations before BO kicks in (>= 2)
  acquisition_function?: 'ei' | 'ucb';
  ei_xi?: number;                // EI exploration parameter [0, 1]
  ucb_kappa?: number;            // UCB exploration parameter [0.1, 10]
  adaptive_acquisition?: boolean;
  exploration_budget?: number;
  xi_exploration?: number;
  xi_exploitation?: number;
  kappa_exploration?: number;
  kappa_exploitation?: number;
  kernel_nu?: 0.5 | 1.5 | 2.5;  // Matern kernel smoothness
  alpha?: number;                // Noise parameter (0, 1]
  n_restarts_optimizer?: number;
}


// ─── CONSENT FORM CONFIG ──────────────────────────────────────────────────
// Consent form text and settings (also used by ConsentConfig above)

export interface ConsentFormConfig {
  explanation: string;
  contact_info?: string;
  medical_disclaimers?: string[];
  consent_label?: string;
}


// ─── INSTRUCTIONS SCREEN CONFIG ──────────────────────────────────────────
// Instructions page text and settings

export interface InstructionsScreenConfig {
  title?: string;
  text: string;                  // Supports markdown
  callout?: string;              // Highlighted callout text
  confirm_label?: string;
  button_label?: string;
}


// ─── LOADING SCREEN CONFIG ────────────────────────────────────────────────
// Loading/rinse screen between cycles

export interface LoadingScreenConfig {
  message?: string;
  duration_seconds?: number;
  use_dynamic_duration?: boolean;
  show_progress?: boolean;
  show_cycle_info?: boolean;
  message_size?: 'normal' | 'large' | 'extra_large';
}


// ─── PHASE SEQUENCE CONFIG ────────────────────────────────────────────────
// Ordered list of experiment phases

export interface PhaseConfig {
  phase_id: string;
  phase_type: 'builtin' | 'custom' | 'loop';
  required?: boolean;
}

export interface PhaseSequenceConfig {
  phases: PhaseConfig[];
}


// ─── DATA COLLECTION CONFIG ───────────────────────────────────────────────
// What data to collect during the experiment

export interface DataCollectionConfig {
  track_trajectory?: boolean;
  track_interaction_times?: boolean;
  collect_demographics?: boolean;
  custom_metadata?: Record<string, unknown>;
}


// ─── PROTOCOL WIZARD TYPES ───────────────────────────────────────────────
// Types used by the protocol creation wizard

export type WizardStepId =
  | 'overview'
  | 'ingredients'
  | 'schedule'
  | 'questionnaire'
  | 'optimization'
  | 'experience'
  | 'pumps'
  | 'review';

export interface WizardStepDef {
  id: WizardStepId;
  label: string;
  description: string;
  conditional?: boolean;         // Step may be skipped based on protocol state
}

// The wizard builds a ProtocolDraft incrementally — all fields optional
export type ProtocolDraft = Partial<Protocol> & {
  ingredients?: Ingredient[];
  sample_selection_schedule?: ScheduleBlock[];
}
