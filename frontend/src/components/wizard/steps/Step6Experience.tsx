/**
 * Step 6: Participant Experience
 * Phase sequence, consent form, instructions, and loading screen settings.
 */

import { useWizard } from '../../../context/WizardContext';
import type {
  PhaseConfig,
  ConsentFormConfig,
  InstructionsScreenConfig,
  LoadingScreenConfig,
} from '../../../types';

const BUILTIN_PHASES: { id: string; label: string; description: string; alwaysOn?: boolean }[] = [
  { id: 'consent', label: 'Consent Form', description: 'Participants read and accept the consent form' },
  { id: 'registration', label: 'Registration', description: 'Participants enter name, age, gender' },
  { id: 'instructions', label: 'Instructions', description: 'Show experiment instructions' },
  { id: 'experiment_loop', label: 'Experiment Loop', description: 'Sample tasting and questionnaire cycles', alwaysOn: true },
  { id: 'completion', label: 'Completion', description: 'Thank-you screen shown at the end', alwaysOn: true },
];

export default function Step6Experience() {
  const { state, dispatch, hasConsent, hasInstructions } = useWizard();
  const phases = state.protocol.phase_sequence?.phases ?? [];
  const consent = state.protocol.consent_form ?? {
    explanation: '',
    contact_info: '',
    medical_disclaimers: [],
    consent_label: 'I have read and understood the information above.',
  };
  const instructions = state.protocol.instructions_screen ?? {
    title: 'Instructions',
    text: '',
    confirm_label: 'I have read and understand the instructions.',
    button_label: 'Begin Experiment',
  };
  const loading = state.protocol.loading_screen ?? {
    message: 'Please rinse your mouth with water.',
    duration_seconds: 5,
    show_progress: true,
    show_cycle_info: true,
    message_size: 'normal' as const,
  };

  function togglePhase(phaseId: string) {
    const exists = phases.some((p) => p.phase_id === phaseId);
    let updated: PhaseConfig[];
    if (exists) {
      updated = phases.filter((p) => p.phase_id !== phaseId);
    } else {
      // Append at the end (before completion if present), preserving user order
      const completionIdx = phases.findIndex((p) => p.phase_id === 'completion');
      const newPhase: PhaseConfig = {
        phase_id: phaseId,
        phase_type: phaseId === 'experiment_loop' ? 'loop' : 'builtin',
        required: true,
      };
      if (completionIdx >= 0) {
        updated = [
          ...phases.slice(0, completionIdx),
          newPhase,
          ...phases.slice(completionIdx),
        ];
      } else {
        updated = [...phases, newPhase];
      }
    }
    dispatch({ type: 'SET_PHASE_SEQUENCE', payload: { phases: updated } });
  }

  function movePhase(phaseId: string, direction: 'up' | 'down') {
    const idx = phases.findIndex((p) => p.phase_id === phaseId);
    if (idx < 0) return;
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= phases.length) return;
    const updated = [...phases];
    [updated[idx], updated[targetIdx]] = [updated[targetIdx], updated[idx]];
    dispatch({ type: 'SET_PHASE_SEQUENCE', payload: { phases: updated } });
  }

  function updateConsent(updates: Partial<ConsentFormConfig>) {
    dispatch({ type: 'SET_CONSENT_FORM', payload: { ...consent, ...updates } });
  }

  function updateInstructions(updates: Partial<InstructionsScreenConfig>) {
    dispatch({ type: 'SET_INSTRUCTIONS', payload: { ...instructions, ...updates } });
  }

  function updateLoading(updates: Partial<LoadingScreenConfig>) {
    dispatch({ type: 'SET_LOADING_SCREEN', payload: { ...loading, ...updates } });
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Participant Experience</h2>
        <p className="text-sm text-gray-500">
          Configure what participants see before, during, and after the experiment.
        </p>
      </div>

      {/* Phase sequence */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">Experiment Phases</h3>
        <p className="text-xs text-gray-500 mb-3">
          Toggle phases on or off and drag them into the order they should appear. Experiment Loop and Completion are always included.
        </p>
        <div className="space-y-2">
          {phases.map((phase, idx) => {
            const def = BUILTIN_PHASES.find((p) => p.id === phase.phase_id);
            const label = def?.label ?? phase.phase_id;
            const description = def?.description ?? '';
            const alwaysOn = def?.alwaysOn ?? false;
            return (
              <div
                key={phase.phase_id}
                className={`flex items-center gap-3 p-3 border rounded-lg transition-colors ${
                  alwaysOn
                    ? 'border-gray-200 bg-gray-50'
                    : 'border-blue-200 bg-blue-50'
                }`}
              >
                {/* Enabled checkbox */}
                <input
                  type="checkbox"
                  checked
                  onChange={() => togglePhase(phase.phase_id)}
                  disabled={alwaysOn}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-700">{label}</div>
                  <div className="text-xs text-gray-500">{description}</div>
                </div>
                {/* Move buttons */}
                <div className="flex flex-col gap-0.5">
                  <button
                    type="button"
                    onClick={() => movePhase(phase.phase_id, 'up')}
                    disabled={idx === 0}
                    className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none px-1"
                    title="Move up"
                  >
                    ▲
                  </button>
                  <button
                    type="button"
                    onClick={() => movePhase(phase.phase_id, 'down')}
                    disabled={idx === phases.length - 1}
                    className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none px-1"
                    title="Move down"
                  >
                    ▼
                  </button>
                </div>
              </div>
            );
          })}

          {/* Show available-but-disabled phases as toggle-able */}
          {BUILTIN_PHASES.filter(
            (def) => !phases.some((p) => p.phase_id === def.id)
          ).map((def) => (
            <label
              key={def.id}
              className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:border-gray-300 transition-colors"
            >
              <input
                type="checkbox"
                checked={false}
                onChange={() => togglePhase(def.id)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <div className="text-sm font-medium text-gray-700">{def.label}</div>
                <div className="text-xs text-gray-500">{def.description}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Consent form editor */}
      {hasConsent && (
        <div className="border-t border-gray-200 pt-6">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Consent Form</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Study Explanation</label>
              <textarea
                value={consent.explanation}
                onChange={(e) => updateConsent({ explanation: e.target.value })}
                placeholder="Dear Participant, Welcome to..."
                rows={6}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Contact Info</label>
              <input
                type="text"
                value={consent.contact_info ?? ''}
                onChange={(e) => updateConsent({ contact_info: e.target.value })}
                placeholder="e.g., For questions, contact: researcher@university.edu"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Consent Checkbox Text</label>
              <input
                type="text"
                value={consent.consent_label ?? ''}
                onChange={(e) => updateConsent({ consent_label: e.target.value })}
                placeholder="I have read and understood the information above."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
      )}

      {/* Instructions editor */}
      {hasInstructions && (
        <div className="border-t border-gray-200 pt-6">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Instructions Screen</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Title</label>
              <input
                type="text"
                value={instructions.title ?? 'Instructions'}
                onChange={(e) => updateInstructions({ title: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Instructions Text (supports **markdown**)
              </label>
              <textarea
                value={instructions.text}
                onChange={(e) => updateInstructions({ text: e.target.value })}
                placeholder="**Welcome!**&#10;&#10;In this experiment you will taste..."
                rows={8}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Confirmation Text</label>
                <input
                  type="text"
                  value={instructions.confirm_label ?? ''}
                  onChange={(e) => updateInstructions({ confirm_label: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Button Text</label>
                <input
                  type="text"
                  value={instructions.button_label ?? 'Begin Experiment'}
                  onChange={(e) => updateInstructions({ button_label: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading screen */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Loading Screen (between cycles)</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Message</label>
            <textarea
              value={loading.message ?? ''}
              onChange={(e) => updateLoading({ message: e.target.value })}
              placeholder="Please rinse your mouth with water..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
            />
          </div>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Duration (seconds)</label>
              <input
                type="number"
                value={loading.duration_seconds ?? 5}
                onChange={(e) => updateLoading({ duration_seconds: parseInt(e.target.value) || 5 })}
                min={1}
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Message Size</label>
              <select
                value={loading.message_size ?? 'normal'}
                onChange={(e) =>
                  updateLoading({ message_size: e.target.value as 'normal' | 'large' | 'extra_large' })
                }
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="normal">Normal</option>
                <option value="large">Large</option>
                <option value="extra_large">Extra Large</option>
              </select>
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={loading.show_progress ?? true}
                  onChange={(e) => updateLoading({ show_progress: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Show progress bar
              </label>
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={loading.show_cycle_info ?? true}
                  onChange={(e) => updateLoading({ show_cycle_info: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Show cycle counter
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
