/**
 * WizardContext — State management for the Protocol Creation Wizard.
 *
 * Uses React Context + useReducer to manage the protocol being built
 * across all wizard steps. Each step reads/writes its slice of the
 * protocol draft via typed dispatch actions.
 */

import { createContext, useContext, useReducer, type ReactNode } from 'react';
import type {
  ProtocolDraft,
  Ingredient,
  ScheduleBlock,
  PumpConfig,
  InlineQuestionnaire,
  BayesianOptimizationConfig,
  ConsentFormConfig,
  InstructionsScreenConfig,
  LoadingScreenConfig,
  PhaseSequenceConfig,
  DataCollectionConfig,
  StoppingCriteria,
  WizardStepId,
} from '../types';

// ─── State ───────────────────────────────────────────────────────────────────

export interface WizardState {
  protocol: ProtocolDraft;
  currentStep: number;
  visitedSteps: Set<number>;
}

// ─── Default protocol draft ──────────────────────────────────────────────────

function generateProtocolId(): string {
  return `protocol_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const DEFAULT_PROTOCOL: ProtocolDraft = {
  protocol_id: generateProtocolId(),
  name: '',
  description: '',
  version: '1.0',
  schema_version: '1.0',
  tags: [],
  ingredients: [],
  sample_selection_schedule: [],
  pump_config: { enabled: false },
  questionnaire: {
    name: '',
    description: '',
    version: '1.0',
    questions: [],
  },
  bayesian_optimization: { enabled: false },
  consent_form: {
    explanation: '',
    contact_info: '',
    medical_disclaimers: [],
    consent_label: 'I have read and understood the information above.',
  },
  instructions_screen: {
    title: 'Instructions',
    text: '',
    confirm_label: 'I have read and understand the instructions.',
    button_label: 'Begin Experiment',
  },
  loading_screen: {
    message: 'Please rinse your mouth with water.',
    duration_seconds: 5,
    show_progress: true,
    show_cycle_info: true,
    message_size: 'normal',
  },
  phase_sequence: {
    phases: [
      { phase_id: 'consent', phase_type: 'builtin', required: false },
      { phase_id: 'registration', phase_type: 'builtin', required: true },
      { phase_id: 'instructions', phase_type: 'builtin', required: true },
      { phase_id: 'experiment_loop', phase_type: 'loop', required: true },
      { phase_id: 'completion', phase_type: 'builtin', required: true },
    ],
  },
  stopping_criteria: {
    max_cycles: 6,
    min_cycles: 1,
  },
  data_collection: {
    track_trajectory: true,
    track_interaction_times: true,
    collect_demographics: true,
    custom_metadata: {},
  },
};

const INITIAL_STATE: WizardState = {
  protocol: DEFAULT_PROTOCOL,
  currentStep: 0,
  visitedSteps: new Set([0]),
};

// ─── Actions ─────────────────────────────────────────────────────────────────

type WizardAction =
  | { type: 'SET_STEP'; step: number }
  | { type: 'UPDATE_OVERVIEW'; payload: Partial<Pick<ProtocolDraft, 'name' | 'description' | 'tags'>> }
  | { type: 'SET_DATA_COLLECTION'; payload: DataCollectionConfig }
  | { type: 'SET_INGREDIENTS'; payload: Ingredient[] }
  | { type: 'SET_SCHEDULE'; payload: ScheduleBlock[] }
  | { type: 'SET_STOPPING_CRITERIA'; payload: StoppingCriteria }
  | { type: 'SET_QUESTIONNAIRE'; payload: InlineQuestionnaire }
  | { type: 'SET_BO_CONFIG'; payload: BayesianOptimizationConfig }
  | { type: 'SET_PUMP_CONFIG'; payload: PumpConfig }
  | { type: 'SET_CONSENT_FORM'; payload: ConsentFormConfig }
  | { type: 'SET_INSTRUCTIONS'; payload: InstructionsScreenConfig }
  | { type: 'SET_LOADING_SCREEN'; payload: LoadingScreenConfig }
  | { type: 'SET_PHASE_SEQUENCE'; payload: PhaseSequenceConfig }
  | { type: 'LOAD_PROTOCOL'; payload: ProtocolDraft }
  | { type: 'RESET' };

// ─── Reducer ─────────────────────────────────────────────────────────────────

function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'SET_STEP': {
      const newVisited = new Set(state.visitedSteps);
      newVisited.add(action.step);
      return { ...state, currentStep: action.step, visitedSteps: newVisited };
    }

    case 'UPDATE_OVERVIEW':
      return {
        ...state,
        protocol: { ...state.protocol, ...action.payload },
      };

    case 'SET_DATA_COLLECTION':
      return {
        ...state,
        protocol: { ...state.protocol, data_collection: action.payload },
      };

    case 'SET_INGREDIENTS':
      return {
        ...state,
        protocol: { ...state.protocol, ingredients: action.payload },
      };

    case 'SET_SCHEDULE':
      return {
        ...state,
        protocol: { ...state.protocol, sample_selection_schedule: action.payload },
      };

    case 'SET_STOPPING_CRITERIA':
      return {
        ...state,
        protocol: { ...state.protocol, stopping_criteria: action.payload },
      };

    case 'SET_QUESTIONNAIRE':
      return {
        ...state,
        protocol: { ...state.protocol, questionnaire: action.payload },
      };

    case 'SET_BO_CONFIG':
      return {
        ...state,
        protocol: { ...state.protocol, bayesian_optimization: action.payload },
      };

    case 'SET_PUMP_CONFIG':
      return {
        ...state,
        protocol: { ...state.protocol, pump_config: action.payload },
      };

    case 'SET_CONSENT_FORM':
      return {
        ...state,
        protocol: { ...state.protocol, consent_form: action.payload },
      };

    case 'SET_INSTRUCTIONS':
      return {
        ...state,
        protocol: { ...state.protocol, instructions_screen: action.payload },
      };

    case 'SET_LOADING_SCREEN':
      return {
        ...state,
        protocol: { ...state.protocol, loading_screen: action.payload },
      };

    case 'SET_PHASE_SEQUENCE':
      return {
        ...state,
        protocol: { ...state.protocol, phase_sequence: action.payload },
      };

    case 'LOAD_PROTOCOL':
      return {
        ...state,
        protocol: { ...DEFAULT_PROTOCOL, ...action.payload },
      };

    case 'RESET':
      return {
        ...INITIAL_STATE,
        protocol: { ...DEFAULT_PROTOCOL, protocol_id: generateProtocolId() },
      };

    default:
      return state;
  }
}

// ─── Context ─────────────────────────────────────────────────────────────────

interface WizardContextValue {
  state: WizardState;
  dispatch: React.Dispatch<WizardAction>;
  /** Whether any schedule block uses bo_selected mode */
  needsBO: boolean;
  /** Whether pumps are enabled */
  needsPumps: boolean;
  /** Whether the consent phase is in the phase sequence */
  hasConsent: boolean;
  /** Whether the instructions phase is in the phase sequence */
  hasInstructions: boolean;
}

const WizardContext = createContext<WizardContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────────────────

export function WizardProvider({ children, initialProtocol }: {
  children: ReactNode;
  initialProtocol?: ProtocolDraft;
}) {
  const [state, dispatch] = useReducer(wizardReducer, {
    ...INITIAL_STATE,
    protocol: initialProtocol
      ? { ...DEFAULT_PROTOCOL, ...initialProtocol }
      : { ...DEFAULT_PROTOCOL, protocol_id: generateProtocolId() },
  });

  const needsBO = (state.protocol.sample_selection_schedule ?? []).some(
    (b) => b.mode === 'bo_selected'
  );

  const needsPumps = state.protocol.pump_config?.enabled ?? false;

  const phases = state.protocol.phase_sequence?.phases ?? [];
  const hasConsent = phases.some((p) => p.phase_id === 'consent');
  const hasInstructions = phases.some((p) => p.phase_id === 'instructions');

  return (
    <WizardContext.Provider value={{ state, dispatch, needsBO, needsPumps, hasConsent, hasInstructions }}>
      {children}
    </WizardContext.Provider>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useWizard(): WizardContextValue {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error('useWizard must be used within <WizardProvider>');
  return ctx;
}

// ─── Step definitions ────────────────────────────────────────────────────────

export const WIZARD_STEPS: { id: WizardStepId; label: string; description: string; conditional?: boolean }[] = [
  { id: 'overview', label: 'Overview', description: 'Name your experiment' },
  { id: 'ingredients', label: 'Ingredients', description: 'Define what you\'re testing' },
  { id: 'schedule', label: 'Schedule', description: 'Plan the experiment flow' },
  { id: 'questionnaire', label: 'Questionnaire', description: 'What subjects will rate' },
  { id: 'optimization', label: 'Optimization', description: 'Algorithm settings', conditional: true },
  { id: 'experience', label: 'Experience', description: 'Consent, instructions, loading' },
  { id: 'pumps', label: 'Pumps', description: 'Hardware configuration', conditional: true },
  { id: 'review', label: 'Review', description: 'Review and save' },
];
