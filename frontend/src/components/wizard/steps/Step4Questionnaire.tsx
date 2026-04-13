/**
 * Step 4: Questionnaire — What subjects will rate.
 * Template presets, question list editor, and bayesian target selector.
 */

import { useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import type { QuestionConfig, InlineQuestionnaire, BayesianTarget } from '../../../types';

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

export default function Step4Questionnaire() {
  const { state, dispatch } = useWizard();
  const questionnaire = state.protocol.questionnaire ?? PRESETS[0].questionnaire;
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  function setQuestionnaire(q: InlineQuestionnaire) {
    dispatch({ type: 'SET_QUESTIONNAIRE', payload: q });
  }

  function applyPreset(presetId: string) {
    const preset = PRESETS.find((p) => p.id === presetId);
    if (preset) {
      setQuestionnaire(preset.questionnaire);
      setSelectedPreset(presetId);
    }
  }

  function updateQuestion(index: number, updates: Partial<QuestionConfig>) {
    const updated = questionnaire.questions.map((q, i) => (i === index ? { ...q, ...updates } : q));
    setQuestionnaire({ ...questionnaire, questions: updated });
  }

  function addQuestion() {
    const newQ: QuestionConfig = {
      id: `question_${questionnaire.questions.length + 1}`,
      type: 'slider',
      label: '',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
    };
    setQuestionnaire({ ...questionnaire, questions: [...questionnaire.questions, newQ] });
  }

  function removeQuestion(index: number) {
    setQuestionnaire({
      ...questionnaire,
      questions: questionnaire.questions.filter((_, i) => i !== index),
    });
  }

  function updateTarget(updates: Partial<BayesianTarget>) {
    setQuestionnaire({
      ...questionnaire,
      bayesian_target: {
        ...(questionnaire.bayesian_target ?? {
          variable: '',
          transform: 'identity' as const,
          higher_is_better: true,
        }),
        ...updates,
      },
    });
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Questionnaire</h2>
        <p className="text-sm text-gray-500">
          Define the questions participants answer after tasting each sample.
        </p>
      </div>

      {/* Template presets */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">Start from a template</label>
        <div className="grid grid-cols-3 gap-3">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => applyPreset(preset.id)}
              className={`text-left p-3 border rounded-lg transition-colors ${
                selectedPreset === preset.id
                  ? 'border-blue-300 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="text-sm font-medium text-gray-700">{preset.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{preset.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Questionnaire name */}
      <div className="grid grid-cols-2 gap-4">
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
      </div>

      {/* Questions */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">
          Questions ({questionnaire.questions.length})
        </h3>
        <div className="space-y-4">
          {questionnaire.questions.map((q, index) => (
            <QuestionEditor
              key={index}
              question={q}
              canRemove={questionnaire.questions.length > 1}
              onChange={(updates) => updateQuestion(index, updates)}
              onRemove={() => removeQuestion(index)}
            />
          ))}

          <button
            type="button"
            onClick={addQuestion}
            className="w-full py-2.5 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
          >
            + Add Question
          </button>
        </div>
      </div>

      {/* Bayesian target */}
      {questionnaire.questions.length > 0 && (
        <div className="border-t border-gray-200 pt-6">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Optimization Target</h3>
          <p className="text-xs text-gray-500 mb-3">
            If using algorithm optimization, which question should it try to maximize (or minimize)?
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Target Question</label>
              <select
                value={questionnaire.bayesian_target?.variable ?? ''}
                onChange={(e) => updateTarget({ variable: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="">Select a question...</option>
                {questionnaire.questions.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.label || q.id}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end pb-0.5">
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={questionnaire.bayesian_target?.higher_is_better ?? true}
                  onChange={(e) => updateTarget({ higher_is_better: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Higher values are better
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ─── Question Editor ─────────────────────────────────────────────────────────

function QuestionEditor({
  question,
  canRemove,
  onChange,
  onRemove,
}: {
  question: QuestionConfig;
  canRemove: boolean;
  onChange: (updates: Partial<QuestionConfig>) => void;
  onRemove: () => void;
}) {
  const [showScaleLabels, setShowScaleLabels] = useState(
    Object.keys(question.scale_labels ?? {}).length > 0
  );

  function autoId(label: string): string {
    return label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      || question.id;
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-gray-400">ID: {question.id}</span>
        {canRemove && (
          <button type="button" onClick={onRemove} className="text-gray-400 hover:text-red-500 text-sm">
            Remove
          </button>
        )}
      </div>

      {/* Label */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Question Text</label>
        <input
          type="text"
          value={question.label}
          onChange={(e) => {
            const updates: Partial<QuestionConfig> = { label: e.target.value };
            if (!question.label) updates.id = autoId(e.target.value);
            onChange(updates);
          }}
          placeholder="e.g., How much do you like this sample?"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="grid grid-cols-5 gap-3">
        {/* Type */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
          <select
            value={question.type}
            onChange={(e) => onChange({ type: e.target.value as QuestionConfig['type'] })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="slider">Slider</option>
            <option value="dropdown">Dropdown</option>
            <option value="text_input">Text</option>
          </select>
        </div>

        {question.type === 'slider' && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Min</label>
              <input
                type="number"
                value={question.min ?? 1}
                onChange={(e) => onChange({ min: parseFloat(e.target.value) || 1 })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Max</label>
              <input
                type="number"
                value={question.max ?? 9}
                onChange={(e) => onChange({ max: parseFloat(e.target.value) || 9 })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Step</label>
              <input
                type="number"
                value={question.step ?? 0.01}
                onChange={(e) => onChange({ step: parseFloat(e.target.value) || 0.01 })}
                step="any"
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Default</label>
              <input
                type="number"
                value={question.default as number ?? 5}
                onChange={(e) => onChange({ default: parseFloat(e.target.value) || 5 })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </>
        )}
      </div>

      {/* Scale labels toggle */}
      {question.type === 'slider' && (
        <div>
          <button
            type="button"
            onClick={() => setShowScaleLabels(!showScaleLabels)}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            {showScaleLabels ? '▾ Hide scale labels' : '▸ Add scale labels (anchor points)'}
          </button>
          {showScaleLabels && (
            <ScaleLabelEditor
              labels={question.scale_labels ?? {}}
              onChange={(labels) => onChange({ scale_labels: labels })}
            />
          )}
        </div>
      )}

      {/* Required */}
      <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
        <input
          type="checkbox"
          checked={question.required ?? true}
          onChange={(e) => onChange({ required: e.target.checked })}
          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        Required
      </label>
    </div>
  );
}


// ─── Scale Label Editor ──────────────────────────────────────────────────────

function ScaleLabelEditor({
  labels,
  onChange,
}: {
  labels: Record<string, string>;
  onChange: (labels: Record<string, string>) => void;
}) {
  const entries = Object.entries(labels).sort(([a], [b]) => parseFloat(a) - parseFloat(b));
  const [newValue, setNewValue] = useState('');
  const [newLabel, setNewLabel] = useState('');

  function addLabel() {
    if (newValue && newLabel) {
      onChange({ ...labels, [newValue]: newLabel });
      setNewValue('');
      setNewLabel('');
    }
  }

  function removeLabel(value: string) {
    const updated = { ...labels };
    delete updated[value];
    onChange(updated);
  }

  return (
    <div className="mt-2 space-y-1">
      {entries.map(([value, label]) => (
        <div key={value} className="flex items-center gap-2 text-xs">
          <span className="w-8 text-gray-500 font-mono text-right">{value}:</span>
          <span className="text-gray-700">{label}</span>
          <button
            type="button"
            onClick={() => removeLabel(value)}
            className="text-gray-400 hover:text-red-500 ml-auto"
          >
            ×
          </button>
        </div>
      ))}
      <div className="flex items-center gap-2 text-xs mt-1">
        <input
          type="number"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          placeholder="Value"
          className="w-16 px-2 py-1 border border-gray-300 rounded text-sm"
        />
        <input
          type="text"
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          placeholder="Label text"
          className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
          onKeyDown={(e) => e.key === 'Enter' && addLabel()}
        />
        <button
          type="button"
          onClick={addLabel}
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          Add
        </button>
      </div>
    </div>
  );
}
