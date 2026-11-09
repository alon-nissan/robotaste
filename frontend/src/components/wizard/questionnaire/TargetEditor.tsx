/**
 * TargetEditor — which answer Bayesian optimisation should maximise/minimise,
 * and how it is transformed. Only numeric questions can be targets. A target
 * is optional unless the schedule uses bo_selected cycles.
 */
import type { BayesianTarget, InlineQuestionnaire, ScalePreset } from '../../../types';
import { isNumericQuestion, normalizeOptions } from '../../../utils/questionnaire';
import { TRANSFORM_DESCRIPTIONS } from '../../../utils/scalePresets';
import { checkboxClass, fieldLabelClass, inputClass } from './styles';

interface TargetEditorProps {
  questionnaire: InlineQuestionnaire;
  presetsById: Record<string, ScalePreset>;
  needsBO: boolean;
  onChange: (target: BayesianTarget | undefined) => void;
}

const COMPOSITE = 'composite';
const NONE = '';

export default function TargetEditor({ questionnaire, presetsById, needsBO, onChange }: TargetEditorProps) {
  const target = questionnaire.bayesian_target;
  const numericQuestions = questionnaire.questions.filter(isNumericQuestion);
  const variable = target?.variable ?? NONE;
  const targetQuestion = questionnaire.questions.find((q) => q.id === variable);
  const preset = targetQuestion?.preset ? presetsById[targetQuestion.preset] : undefined;
  const presetDefault = preset?.default_transform ?? 'identity';
  const transform = target?.transform;

  function update(patch: Partial<BayesianTarget>) {
    onChange({
      variable: target?.variable ?? '',
      higher_is_better: target?.higher_is_better ?? true,
      ...target,
      ...patch,
    });
  }

  function selectVariable(v: string) {
    if (v === NONE) {
      onChange(undefined);
      return;
    }
    // Picking a new question resets the transform to "scale default".
    const next: BayesianTarget = {
      variable: v,
      higher_is_better: target?.higher_is_better ?? true,
    };
    if (v === COMPOSITE) next.formula = target?.formula ?? '';
    onChange(next);
  }

  const idealOptions = targetQuestion ? normalizeOptions(targetQuestion.options) : [];
  const variableIsStale = variable !== NONE && variable !== COMPOSITE && !numericQuestions.some((q) => q.id === variable);

  return (
    <div className="border-t border-gray-200 pt-6 space-y-3" data-testid="target-editor">
      <div>
        <h3 className="text-sm font-medium text-gray-700">Optimization target</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Which answer should the algorithm maximize (or minimize)?{' '}
          {needsBO
            ? 'Required: your schedule uses algorithm-selected (BO) cycles.'
            : 'Optional: only needed for algorithm-selected (BO) cycles.'}
        </p>
      </div>

      {needsBO && variable === NONE && (
        <div className="text-xs text-red-700 bg-red-50 rounded-lg p-2">
          ⚠️ Choose a target question — BO cycles cannot run without one.
        </div>
      )}
      {variableIsStale && (
        <div className="text-xs text-red-700 bg-red-50 rounded-lg p-2">
          ⚠️ The target "{variable}" is not a numeric question in this questionnaire. Pick another target.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className={fieldLabelClass}>Target</label>
          <select
            value={variable}
            aria-label="Optimization target"
            onChange={(e) => selectVariable(e.target.value)}
            className={inputClass}
          >
            <option value={NONE}>{needsBO ? 'Select a question…' : 'None (no optimization)'}</option>
            {numericQuestions.map((q) => (
              <option key={q.id} value={q.id}>
                {q.label || q.id}
                {q.preset && presetsById[q.preset] ? ` — ${presetsById[q.preset].name}` : ''}
              </option>
            ))}
            <option value={COMPOSITE}>Composite formula (combine several answers)</option>
          </select>
        </div>

        {variable !== NONE && (
          <div>
            <label className={fieldLabelClass}>Transform</label>
            <select
              value={transform ?? ''}
              aria-label="Target transform"
              onChange={(e) =>
                update({
                  transform: (e.target.value || undefined) as BayesianTarget['transform'],
                  ideal_value:
                    e.target.value === 'ideal_point'
                      ? target?.ideal_value ?? targetQuestion?.ideal_value
                      : undefined,
                })
              }
              className={inputClass}
            >
              {variable !== COMPOSITE && (
                <option value="">
                  Scale default — {TRANSFORM_DESCRIPTIONS[presetDefault] ?? presetDefault}
                </option>
              )}
              {Object.entries(TRANSFORM_DESCRIPTIONS).map(([key, desc]) => (
                <option key={key} value={key}>
                  {key}: {desc}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {variable === COMPOSITE && (
        <div>
          <label className={fieldLabelClass}>Formula</label>
          <input
            type="text"
            value={target?.formula ?? ''}
            onChange={(e) => update({ formula: e.target.value })}
            placeholder="e.g. 0.7 * liking + 0.3 * sweetness"
            className={`${inputClass} font-mono`}
          />
          <p className="text-xs text-gray-500 mt-1">
            Available question IDs: {numericQuestions.map((q) => q.id).join(', ') || '(none)'}
          </p>
        </div>
      )}

      {transform === 'ideal_point' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={fieldLabelClass}>Ideal value</label>
            {idealOptions.length > 0 ? (
              <select
                value={target?.ideal_value ?? ''}
                onChange={(e) => update({ ideal_value: e.target.value === '' ? undefined : Number(e.target.value) })}
                className={inputClass}
              >
                <option value="">Select…</option>
                {idealOptions.map((o) => (
                  <option key={String(o.value)} value={String(o.value)}>
                    {String(o.value)} — {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="number"
                step="any"
                value={target?.ideal_value ?? ''}
                onChange={(e) => update({ ideal_value: e.target.value === '' ? undefined : Number(e.target.value) })}
                className={inputClass}
              />
            )}
            <p className="text-xs text-gray-500 mt-1">The optimizer aims for answers as close to this value as possible.</p>
          </div>
        </div>
      )}

      {transform === 'normalize' && (
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {[0, 1].map((i) => (
            <div key={i}>
              <label className={fieldLabelClass}>{i === 0 ? 'Expected min' : 'Expected max'}</label>
              <input
                type="number"
                step="any"
                value={target?.expected_range?.[i] ?? ''}
                onChange={(e) => {
                  const range: [number, number] = [...(target?.expected_range ?? [1, 9])] as [number, number];
                  range[i] = Number(e.target.value);
                  update({ expected_range: range });
                }}
                className={inputClass}
              />
            </div>
          ))}
        </div>
      )}

      {variable !== NONE && transform !== 'ideal_point' && (
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={target?.higher_is_better ?? true}
            onChange={(e) => update({ higher_is_better: e.target.checked })}
            className={checkboxClass}
          />
          Higher values are better (uncheck to minimize)
        </label>
      )}
    </div>
  );
}
