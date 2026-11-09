/**
 * Step 4: Questionnaire — What subjects will rate.
 * Starting templates, questionnaire settings, question list (scale library
 * picker + per-question editor) and the optimization target editor.
 */

import { useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import type { QuestionConfig, InlineQuestionnaire, BayesianTarget } from '../../../types';
import { questionFromPreset, useScalePresets } from '../../../utils/scalePresets';
import QuestionEditor from '../questionnaire/QuestionEditor';
import ScaleLibraryPicker from '../questionnaire/ScaleLibraryPicker';
import TargetEditor from '../questionnaire/TargetEditor';
import { uniqueId } from '../questionnaire/questionTemplates';

// ─── Questionnaire presets ──────────────────────────────────────────────────

const PRESETS: { id: string; label: string; description: string; questionnaire: InlineQuestionnaire }[] = [
  {
    id: 'hedonic_continuous',
    label: 'Simple Liking Scale',
    description: 'Continuous 9-point hedonic scale — "How much do you like this?"',
    questionnaire: {
      name: 'Hedonic Scale (Continuous)',
      description: 'Continuous 9-point hedonic scale for measuring preference.',
      version: '1.0',
      questions: [
        {
          id: 'overall_liking',
          type: 'slider',
          label: 'How much do you like this sample?',
          help_text: 'Rate from 1 (Dislike Extremely) to 9 (Like Extremely)',
          min: 1,
          max: 9,
          default: 5,
          step: 0.01,
          required: true,
          scale_labels: {
            '1': 'Dislike Extremely',
            '3': 'Dislike Moderately',
            '5': 'Neither Like nor Dislike',
            '7': 'Like Moderately',
            '9': 'Like Extremely',
          },
        },
      ],
      bayesian_target: {
        variable: 'overall_liking',
        transform: 'identity',
        higher_is_better: true,
        expected_range: [1, 9],
        optimal_threshold: 7.0,
      },
    },
  },
  {
    id: 'intensity_continuous',
    label: 'Intensity Scale',
    description: 'Continuous 9-point intensity scale — "How strong is the taste?"',
    questionnaire: {
      name: 'Intensity Scale (Continuous)',
      description: 'Continuous 9-point intensity scale for measuring attribute strength.',
      version: '1.0',
      questions: [
        {
          id: 'intensity',
          type: 'slider',
          label: 'How intense is the taste?',
          help_text: 'Rate from 1 (Not at All) to 9 (Extremely Intense)',
          min: 1,
          max: 9,
          default: 5,
          step: 0.01,
          required: true,
          scale_labels: {
            '1': 'Not at All',
            '3': 'Light',
            '5': 'Moderate',
            '7': 'Strong',
            '9': 'Extremely Intense',
          },
        },
      ],
      bayesian_target: {
        variable: 'intensity',
        transform: 'identity',
        higher_is_better: true,
        expected_range: [1, 9],
        optimal_threshold: 5.0,
      },
    },
  },
  {
    id: 'rebm_taste_profile',
    label: 'Taste Profile (ReBM)',
    description: 'Sweet, bitter, and salty intensity scales used in ReBM dose-response experiments.',
    questionnaire: {
      name: 'Taste Profile (ReBM)',
      description: 'Continuous 9-point intensity scales for sweet, bitter, and salty dimensions.',
      version: '1.0',
      display_mode: 'one_at_a_time',
      questions: [
        {
          id: 'sweetness',
          type: 'slider',
          label: 'How sweet is the sample?',
          help_text: 'Rate from 1 (Not at All) to 9 (Extremely Strong)',
          min: 1,
          max: 9,
          default: 5,
          step: 0.01,
          required: true,
          scale_labels: {
            '1': 'Not at All',
            '3': 'Light',
            '5': 'Moderate',
            '7': 'Strong',
            '9': 'Extremely Strong',
          },
        },
        {
          id: 'bitterness',
          type: 'slider',
          label: 'How bitter is the sample?',
          min: 1,
          max: 9,
          default: 5,
          step: 0.01,
          required: true,
          scale_labels: {
            '1': 'Not at All',
            '3': 'Light',
            '5': 'Moderate',
            '7': 'Strong',
            '9': 'Extremely Strong',
          },
        },
        {
          id: 'saltiness',
          type: 'slider',
          label: 'How salty is the sample?',
          min: 1,
          max: 9,
          default: 5,
          step: 0.01,
          required: true,
          scale_labels: {
            '1': 'Not at All',
            '3': 'Light',
            '5': 'Moderate',
            '7': 'Strong',
            '9': 'Extremely Strong',
          },
        },
      ],
      bayesian_target: {
        variable: 'sweetness',
        transform: 'identity',
        higher_is_better: true,
        expected_range: [1, 9],
        optimal_threshold: 5.0,
      },
    },
  },
  {
    id: 'custom',
    label: 'Start from Scratch',
    description: 'Build your own questionnaire from an empty template.',
    questionnaire: {
      name: '',
      description: '',
      version: '1.0',
      questions: [],
    },
  },
];

// ─── Library-based starting templates (built from backend scale presets) ────

const LIBRARY_TEMPLATES: {
  id: string;
  label: string;
  description: string;
  name: string;
  questions: { preset: string; id: string; label: string }[];
  targetId?: string;
}[] = [
  {
    id: 'glms_intensity',
    label: 'gLMS Intensity',
    description: 'General Labeled Magnitude Scale — valid across subject groups.',
    name: 'gLMS Intensity',
    questions: [{ preset: 'glms', id: 'intensity', label: 'How intense is the taste?' }],
    targetId: 'intensity',
  },
  {
    id: 'gvas_intensity',
    label: 'gVAS Intensity',
    description: 'Generalized VAS — unlabeled line to "strongest imaginable".',
    name: 'gVAS Intensity',
    questions: [{ preset: 'gvas', id: 'intensity', label: 'How intense is the taste?' }],
    targetId: 'intensity',
  },
  {
    id: 'vas_liking',
    label: 'VAS Liking',
    description: 'Hedonic visual analogue scale, dislike → like extremely.',
    name: 'VAS Liking',
    questions: [{ preset: 'hedonic_vas', id: 'liking', label: 'How much do you like this sample?' }],
    targetId: 'liking',
  },
  {
    id: 'hedonic_9pt',
    label: '9-point Hedonic',
    description: 'Peryam & Pilgrim category scale — the industry standard.',
    name: '9-point Hedonic',
    questions: [{ preset: 'hedonic_9pt', id: 'liking', label: 'How much do you like this sample?' }],
    targetId: 'liking',
  },
  {
    id: 'lhs_liking',
    label: 'LHS Liking',
    description: 'Labeled Hedonic Scale — ratio-level liking.',
    name: 'LHS Liking',
    questions: [{ preset: 'lhs', id: 'liking', label: 'How much do you like this sample?' }],
    targetId: 'liking',
  },
  {
    id: 'liking_cata',
    label: 'Liking + CATA',
    description: '9-point liking plus check-all-that-apply basic tastes.',
    name: 'Liking and taste profile',
    questions: [
      { preset: 'hedonic_9pt', id: 'liking', label: 'How much do you like this sample?' },
      { preset: 'cata_basic_tastes', id: 'tastes', label: 'Which tastes do you notice?' },
    ],
    targetId: 'liking',
  },
];

let uidCounter = 0;
const newUid = () => `q${++uidCounter}`;

export default function Step4Questionnaire() {
  const { state, dispatch, needsBO } = useWizard();
  const questionnaire = state.protocol.questionnaire ?? PRESETS[0].questionnaire;
  const questions = questionnaire.questions;
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [showLibrary, setShowLibrary] = useState(false);
  const { presets, byId, loading, error } = useScalePresets();

  // Stable React keys for questions (IDs are editable, indexes shift on reorder).
  const [uids, setUids] = useState<string[]>(() => questions.map(() => newUid()));
  // Questions replaced from outside (e.g. protocol loaded for editing): re-key.
  if (uids.length !== questions.length) {
    setUids(questions.map((_, i) => `loaded_${questions.length}_${i}`));
  }

  function setQuestionnaire(q: InlineQuestionnaire) {
    dispatch({ type: 'SET_QUESTIONNAIRE', payload: q });
  }

  /** Update questions; pass `target` explicitly (incl. `undefined` to clear it) or omit to keep it. */
  function setQuestions(next: QuestionConfig[], ...targetArg: [BayesianTarget | undefined] | []) {
    const target = targetArg.length ? targetArg[0] : questionnaire.bayesian_target;
    const updated: InlineQuestionnaire = { ...questionnaire, questions: next };
    if (target) updated.bayesian_target = target;
    else delete updated.bayesian_target;
    setQuestionnaire(updated);
  }

  function applyPreset(presetId: string) {
    const preset = PRESETS.find((p) => p.id === presetId);
    if (preset) {
      setUids(preset.questionnaire.questions.map(() => newUid()));
      setQuestionnaire(JSON.parse(JSON.stringify(preset.questionnaire)));
      setSelectedPreset(presetId);
    }
  }

  function applyLibraryTemplate(templateId: string) {
    const tpl = LIBRARY_TEMPLATES.find((t) => t.id === templateId);
    if (!tpl) return;
    const built = tpl.questions
      .filter((q) => byId[q.preset])
      .map((q) => questionFromPreset(byId[q.preset], q.id, q.label));
    if (!built.length) return;
    setUids(built.map(() => newUid()));
    const next: InlineQuestionnaire = {
      name: tpl.name,
      description: tpl.description,
      version: '1.0',
      display_mode: questionnaire.display_mode,
      title: questionnaire.title,
      questions: built,
    };
    if (tpl.targetId) next.bayesian_target = { variable: tpl.targetId, higher_is_better: true };
    setQuestionnaire(next);
    setSelectedPreset(templateId);
  }

  function updateQuestion(index: number, updates: Partial<QuestionConfig>) {
    const before = questions[index];
    const next = questions.map((q, i) => (i === index ? { ...q, ...updates } : q));
    // Keep the optimization target pointing at a renamed question.
    let target = questionnaire.bayesian_target;
    if (updates.id !== undefined && target?.variable === before.id) {
      target = { ...target, variable: updates.id };
    }
    setQuestions(next, target);
  }

  function replaceQuestion(index: number, question: QuestionConfig) {
    setQuestions(questions.map((q, i) => (i === index ? question : q)));
  }

  function addQuestion(question: QuestionConfig) {
    setUids([...uids, newUid()]);
    setQuestions([...questions, question]);
    setShowLibrary(false);
  }

  function moveQuestion(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= questions.length) return;
    const next = [...questions];
    [next[index], next[target]] = [next[target], next[index]];
    const nextUids = [...uids];
    [nextUids[index], nextUids[target]] = [nextUids[target], nextUids[index]];
    setUids(nextUids);
    setQuestions(next);
  }

  function duplicateQuestion(index: number) {
    const original = questions[index];
    const copy: QuestionConfig = {
      ...JSON.parse(JSON.stringify(original)),
      id: uniqueId(`${original.id}_copy`, questions.map((q) => q.id)),
    };
    const next = [...questions.slice(0, index + 1), copy, ...questions.slice(index + 1)];
    const nextUids = [...uids];
    nextUids.splice(index + 1, 0, newUid());
    setUids(nextUids);
    setQuestions(next);
  }

  function removeQuestion(index: number) {
    const removed = questions[index];
    setUids(uids.filter((_, i) => i !== index));
    const target =
      questionnaire.bayesian_target?.variable === removed.id ? undefined : questionnaire.bayesian_target;
    setQuestions(questions.filter((_, i) => i !== index), target);
  }

  function setTarget(target: BayesianTarget | undefined) {
    setQuestions(questions, target);
  }

  const templateButton = (id: string, label: string, description: string, onClick: () => void, disabled = false) => (
    <button
      key={id}
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`text-left p-3 border rounded-lg transition-colors disabled:opacity-50 ${
        selectedPreset === id ? 'border-blue-300 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
      }`}
    >
      <div className="text-sm font-medium text-gray-700">{label}</div>
      <div className="text-xs text-gray-500 mt-0.5">{description}</div>
    </button>
  );

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Questionnaire</h2>
        <p className="text-sm text-gray-500">
          Define the questions participants answer after tasting each sample.
        </p>
      </div>

      {/* Starting templates */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Start from a template</label>
        <p className="text-xs text-gray-500 mb-3">Replaces the current questions. You can edit everything afterwards.</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {LIBRARY_TEMPLATES.map((t) =>
            templateButton(t.id, t.label, t.description, () => applyLibraryTemplate(t.id), loading || !!error)
          )}
          {PRESETS.map((p) => templateButton(p.id, p.label, p.description, () => applyPreset(p.id)))}
        </div>
      </div>

      {/* Questionnaire settings */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Questionnaire Name</label>
          <input
            type="text"
            value={questionnaire.name}
            onChange={(e) => setQuestionnaire({ ...questionnaire, name: e.target.value })}
            placeholder="e.g., Hedonic Scale"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <input
            type="text"
            value={questionnaire.description ?? ''}
            onChange={(e) => setQuestionnaire({ ...questionnaire, description: e.target.value })}
            placeholder="Brief description"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Page title shown to subjects</label>
          <input
            type="text"
            value={questionnaire.title ?? ''}
            onChange={(e) => setQuestionnaire({ ...questionnaire, title: e.target.value || undefined })}
            placeholder="How did you find this sample?"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Display mode</label>
          <select
            value={questionnaire.display_mode ?? 'all_at_once'}
            aria-label="Display mode"
            onChange={(e) =>
              setQuestionnaire({
                ...questionnaire,
                display_mode: e.target.value as 'all_at_once' | 'one_at_a_time',
              })
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="all_at_once">All questions on one page</option>
            <option value="one_at_a_time">One question at a time</option>
          </select>
        </div>
      </div>

      {/* Questions */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">Questions ({questions.length})</h3>
        <div className="space-y-4">
          {questions.map((q, index) => (
            <QuestionEditor
              key={uids[index] ?? `q_${index}`}
              question={q}
              preset={q.preset ? byId[q.preset] : undefined}
              index={index}
              total={questions.length}
              onChange={(updates) => updateQuestion(index, updates)}
              onReplace={(question) => replaceQuestion(index, question)}
              onMove={(delta) => moveQuestion(index, delta)}
              onDuplicate={() => duplicateQuestion(index)}
              onRemove={() => removeQuestion(index)}
            />
          ))}

          {showLibrary ? (
            <ScaleLibraryPicker
              presets={presets}
              loading={loading}
              error={error}
              existingIds={questions.map((q) => q.id)}
              onPick={addQuestion}
              onCancel={() => setShowLibrary(false)}
            />
          ) : (
            <button
              type="button"
              onClick={() => setShowLibrary(true)}
              className="w-full py-2.5 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
            >
              + Add Question
            </button>
          )}
        </div>
      </div>

      {/* Optimization target */}
      {questions.length > 0 && (
        <TargetEditor questionnaire={questionnaire} presetsById={byId} needsBO={needsBO} onChange={setTarget} />
      )}
    </div>
  );
}
