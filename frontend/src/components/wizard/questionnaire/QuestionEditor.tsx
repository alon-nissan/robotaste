/**
 * QuestionEditor — edit one questionnaire question in the protocol wizard.
 * Common fields (ID, text, help, type, required) plus a type-specific section
 * for every supported question type, a preset bar ("Based on gLMS v1.0",
 * modified badge, reset), a live preview and inline validation.
 */
import { useState } from 'react';
import type { QuestionConfig, QuestionType, ScalePreset } from '../../../types';
import QuestionRenderer from '../../questions/QuestionRenderer';
import { defaultsForType, slugify, validateQuestion } from '../../../utils/questionnaire';
import { isModifiedFromPreset, resetToPreset } from '../../../utils/scalePresets';
import AnchorEditor from './AnchorEditor';
import OptionEditor from './OptionEditor';
import { checkboxClass, fieldLabelClass, inputClass, smallInputClass } from './styles';

const TYPE_OPTIONS: { value: QuestionType; label: string }[] = [
  { value: 'line_scale', label: 'Line scale (VAS, gVAS, gLMS…)' },
  { value: 'category_scale', label: 'Category scale (hedonic, Likert, JAR, faces)' },
  { value: 'magnitude_estimation', label: 'Magnitude estimation (number)' },
  { value: 'multi_select', label: 'Check-all-that-apply' },
  { value: 'ranking', label: 'Ranking' },
  { value: 'slider', label: 'Classic slider' },
  { value: 'pillbox', label: 'Pill buttons (legacy)' },
  { value: 'dropdown', label: 'Dropdown' },
  { value: 'text_input', label: 'Short text' },
  { value: 'text_area', label: 'Comment box' },
];

function num(value: string): number | undefined {
  if (value.trim() === '') return undefined;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : undefined;
}

interface QuestionEditorProps {
  question: QuestionConfig;
  preset: ScalePreset | undefined;
  index: number;
  total: number;
  onChange: (updates: Partial<QuestionConfig>) => void;
  onReplace: (question: QuestionConfig) => void;
  onMove: (delta: number) => void;
  onDuplicate: () => void;
  onRemove: () => void;
}

export default function QuestionEditor({
  question,
  preset,
  index,
  total,
  onChange,
  onReplace,
  onMove,
  onDuplicate,
  onRemove,
}: QuestionEditorProps) {
  const [showPreview, setShowPreview] = useState(false);
  const [previewValue, setPreviewValue] = useState<unknown>(undefined);
  const errors = validateQuestion(question);
  const modified = isModifiedFromPreset(question, preset);

  function changeType(type: QuestionType) {
    if (type === question.type) return;
    onReplace({
      id: question.id,
      label: question.label,
      help_text: question.help_text,
      required: question.required,
      type,
      ...defaultsForType(type),
    });
    setPreviewValue(undefined);
  }

  const q = question;

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-4 bg-white" data-testid={`question-editor-${index}`}>
      {/* Header: ID + actions */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-xs font-semibold text-gray-500 mr-1">Q{index + 1}</span>
          <span className="text-xs text-gray-400 shrink-0">ID:</span>
          <input
            type="text"
            value={q.id}
            aria-label="Question ID"
            onChange={(e) => onChange({ id: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })}
            className="text-xs font-mono text-gray-600 bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5 w-40 focus:outline-none focus:ring-1 focus:ring-blue-400"
            placeholder="question_id"
          />
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-400">
          <button type="button" disabled={index === 0} onClick={() => onMove(-1)} className="hover:text-gray-700 disabled:opacity-30" aria-label="Move question up">
            ↑
          </button>
          <button type="button" disabled={index === total - 1} onClick={() => onMove(1)} className="hover:text-gray-700 disabled:opacity-30" aria-label="Move question down">
            ↓
          </button>
          <button type="button" onClick={onDuplicate} className="hover:text-gray-700">
            Duplicate
          </button>
          {total > 1 && (
            <button type="button" onClick={onRemove} className="hover:text-red-500">
              Remove
            </button>
          )}
        </div>
      </div>

      {/* Preset bar */}
      {preset && (
        <div className="flex flex-wrap items-center gap-2 text-xs bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
          <span className="text-blue-800">
            Based on <strong>{preset.name}</strong> v{preset.version}
          </span>
          {modified && (
            <>
              <span className="px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-800 font-medium" data-testid="preset-modified">
                Modified
              </span>
              <button
                type="button"
                onClick={() => onReplace(resetToPreset(q, preset))}
                className="text-blue-700 underline hover:text-blue-900"
              >
                Reset to preset
              </button>
            </>
          )}
          {!preset.anchors_verified && (
            <span className="px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-800">anchors unverified</span>
          )}
          <span className="text-gray-500 italic basis-full sm:basis-auto">{preset.citation}</span>
        </div>
      )}

      {/* Text */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className={fieldLabelClass}>Question text</label>
          <input
            type="text"
            value={q.label}
            aria-label="Question text"
            onChange={(e) => {
              const updates: Partial<QuestionConfig> = { label: e.target.value };
              if (!q.label) updates.id = slugify(e.target.value) || q.id;
              onChange(updates);
            }}
            placeholder="e.g., How sweet is the sample?"
            className={inputClass}
          />
        </div>
        <div>
          <label className={fieldLabelClass}>Help text (optional)</label>
          <input
            type="text"
            value={q.help_text ?? ''}
            onChange={(e) => onChange({ help_text: e.target.value || undefined })}
            placeholder="Shown under the question"
            className={inputClass}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-end">
        <div>
          <label className={fieldLabelClass}>Question type</label>
          <select
            value={q.type}
            aria-label="Question type"
            onChange={(e) => changeType(e.target.value as QuestionType)}
            className={inputClass}
          >
            {TYPE_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer pb-1.5">
          <input
            type="checkbox"
            checked={q.required ?? !(q.type === 'text_input' || q.type === 'text_area')}
            onChange={(e) => onChange({ required: e.target.checked })}
            className={checkboxClass}
          />
          Required
        </label>
      </div>

      {/* Type-specific settings */}
      <div className="border-t border-gray-100 pt-3">
        <TypeSettings question={q} onChange={onChange} />
      </div>

      {/* Validation */}
      {errors.length > 0 && (
        <ul className="text-xs text-red-700 bg-red-50 rounded-lg p-2 space-y-0.5" data-testid="question-errors">
          {errors.map((err) => (
            <li key={err}>⚠️ {err}</li>
          ))}
        </ul>
      )}

      {/* Preview */}
      <div>
        <button
          type="button"
          onClick={() => setShowPreview(!showPreview)}
          className="text-xs text-blue-600 hover:text-blue-800"
        >
          {showPreview ? '▾ Hide subject preview' : '▸ Show subject preview'}
        </button>
        {showPreview && (
          <div className="mt-2 border border-gray-200 rounded-lg p-4 bg-gray-50" data-testid="question-preview">
            <div className="text-sm font-medium text-gray-800 mb-3">{q.label || '(question text)'}</div>
            {errors.length === 0 ? (
              <QuestionRenderer question={q} value={previewValue} onChange={setPreviewValue} seed="preview" />
            ) : (
              <div className="text-xs text-gray-500">Fix the problems above to see the preview.</div>
            )}
            {previewValue !== undefined && (
              <div className="mt-3 flex items-center gap-3 text-xs text-gray-500">
                <span>
                  Recorded answer: <code className="font-mono">{JSON.stringify(previewValue)}</code>
                </span>
                <button type="button" onClick={() => setPreviewValue(undefined)} className="underline">
                  Reset preview
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Type-specific settings ──────────────────────────────────────────────────

function TypeSettings({
  question: q,
  onChange,
}: {
  question: QuestionConfig;
  onChange: (updates: Partial<QuestionConfig>) => void;
}) {
  switch (q.type) {
    case 'line_scale':
      return (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <NumberField label="Min" value={q.min} onChange={(v) => onChange({ min: v })} />
            <NumberField label="Max" value={q.max} onChange={(v) => onChange({ max: v })} />
            <NumberField label="Step (optional)" value={q.step} onChange={(v) => onChange({ step: v })} placeholder="0.1" />
            <div>
              <label className={fieldLabelClass}>Orientation</label>
              <select
                value={q.orientation ?? 'horizontal'}
                onChange={(e) => onChange({ orientation: e.target.value as 'horizontal' | 'vertical' })}
                className={inputClass}
              >
                <option value="horizontal">Horizontal</option>
                <option value="vertical">Vertical</option>
              </select>
            </div>
            <div>
              <label className={fieldLabelClass}>Polarity</label>
              <select
                value={q.polarity ?? 'unipolar'}
                onChange={(e) => onChange({ polarity: e.target.value as 'unipolar' | 'bipolar' })}
                className={inputClass}
              >
                <option value="unipolar">Unipolar</option>
                <option value="bipolar">Bipolar</option>
              </select>
            </div>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            <Toggle
              label="Start with no marker (recommended)"
              checked={q.start_unmarked !== false}
              onChange={(v) => onChange({ start_unmarked: v })}
            />
            <Toggle label="Show numeric value" checked={q.show_value === true} onChange={(v) => onChange({ show_value: v })} />
            <Toggle label="Tick marks at anchors" checked={q.show_ticks !== false} onChange={(v) => onChange({ show_ticks: v })} />
            <Toggle
              label="Extend line past end anchors"
              checked={q.inset_anchors === true}
              onChange={(v) => onChange({ inset_anchors: v })}
            />
          </div>
          <div>
            <div className={fieldLabelClass}>Anchors (labels placed at their position on the line)</div>
            <AnchorEditor anchors={q.anchors ?? []} min={q.min} max={q.max} onChange={(anchors) => onChange({ anchors })} />
          </div>
        </div>
      );

    case 'category_scale':
      return (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div>
              <label className={fieldLabelClass}>Style</label>
              <select
                value={q.style ?? 'buttons'}
                onChange={(e) => onChange({ style: e.target.value as 'buttons' | 'radio' | 'faces' })}
                className={inputClass}
              >
                <option value="buttons">Buttons</option>
                <option value="radio">Radio list</option>
                <option value="faces">Faces / icons</option>
              </select>
            </div>
            <div>
              <label className={fieldLabelClass}>Layout</label>
              <select
                value={q.layout ?? 'horizontal'}
                onChange={(e) => onChange({ layout: e.target.value as 'horizontal' | 'vertical' | 'grid' })}
                className={inputClass}
              >
                <option value="horizontal">Horizontal</option>
                <option value="vertical">Vertical</option>
                <option value="grid">Grid</option>
              </select>
            </div>
            <NumberField
              label="Ideal value (JAR, optional)"
              value={q.ideal_value}
              onChange={(v) => onChange({ ideal_value: v })}
            />
          </div>
          <div>
            <div className={fieldLabelClass}>Options</div>
            <OptionEditor
              options={q.options}
              valueKind="number"
              showIcons={q.style === 'faces' || (q.options ?? []).some((o) => typeof o !== 'string' && o.icon)}
              onChange={(options) => onChange({ options })}
            />
          </div>
        </div>
      );

    case 'magnitude_estimation':
      return (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <NumberField
              label="Modulus (fixed-modulus ME, optional)"
              value={q.modulus}
              onChange={(v) => onChange({ modulus: v })}
            />
            <div>
              <label className={fieldLabelClass}>Reference label</label>
              <input
                type="text"
                value={q.reference_label ?? ''}
                onChange={(e) => onChange({ reference_label: e.target.value || undefined })}
                placeholder="The reference sample"
                className={inputClass}
              />
            </div>
            <NumberField label="Max (optional)" value={q.max} onChange={(v) => onChange({ max: v })} />
          </div>
          <Toggle label="Allow 0 (no sensation)" checked={q.allow_zero === true} onChange={(v) => onChange({ allow_zero: v })} />
        </div>
      );

    case 'multi_select':
      return (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <NumberField label="Min selected" value={q.min_selected} onChange={(v) => onChange({ min_selected: v })} />
            <NumberField
              label="Max selected (optional)"
              value={q.max_selected}
              onChange={(v) => onChange({ max_selected: v })}
            />
          </div>
          <Toggle
            label="Randomize option order per subject (recommended)"
            checked={q.randomize_order !== false}
            onChange={(v) => onChange({ randomize_order: v })}
          />
          <OptionEditor options={q.options} valueKind="text" onChange={(options) => onChange({ options })} />
        </div>
      );

    case 'ranking':
      return (
        <div className="space-y-3">
          <Toggle
            label="Randomize starting order"
            checked={q.randomize_order !== false}
            onChange={(v) => onChange({ randomize_order: v })}
          />
          <OptionEditor options={q.options} valueKind="text" onChange={(options) => onChange({ options })} />
        </div>
      );

    case 'dropdown':
      return (
        <div>
          <label className={fieldLabelClass}>Options (one per line)</label>
          <textarea
            value={(q.options ?? []).map((o) => (typeof o === 'string' ? o : o.label)).join('\n')}
            onChange={(e) =>
              onChange({ options: e.target.value.split('\n').map((s) => s.trim()).filter(Boolean) })
            }
            rows={3}
            placeholder={'Option A\nOption B\nOption C'}
            className={`${inputClass} resize-y`}
          />
        </div>
      );

    case 'slider':
    case 'pillbox':
      return (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <NumberField label="Min" value={q.min} onChange={(v) => onChange({ min: v })} />
            <NumberField label="Max" value={q.max} onChange={(v) => onChange({ max: v })} />
            {q.type === 'slider' && (
              <>
                <NumberField label="Step" value={q.step} onChange={(v) => onChange({ step: v })} />
                <NumberField
                  label="Default"
                  value={typeof q.default === 'number' ? q.default : undefined}
                  onChange={(v) => onChange({ default: v })}
                />
              </>
            )}
          </div>
          <div>
            <div className={fieldLabelClass}>Scale labels</div>
            <ScaleLabelEditor labels={q.scale_labels ?? {}} onChange={(labels) => onChange({ scale_labels: labels })} />
          </div>
        </div>
      );

    case 'text_input':
    case 'text_area':
      return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <NumberField label="Max characters (optional)" value={q.max_length} onChange={(v) => onChange({ max_length: v })} />
        </div>
      );

    default:
      return null;
  }
}

function NumberField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className={fieldLabelClass}>{label}</label>
      <input
        type="number"
        step="any"
        aria-label={label}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(e) => onChange(num(e.target.value))}
        className={inputClass}
      />
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className={checkboxClass} />
      {label}
    </label>
  );
}

// ─── Scale Label Editor (classic slider) ─────────────────────────────────────

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
    <div className="space-y-1">
      {entries.map(([value, label]) => (
        <div key={value} className="flex items-center gap-2 text-xs">
          <span className="w-8 text-gray-500 font-mono text-right">{value}:</span>
          <span className="text-gray-700">{label}</span>
          <button type="button" onClick={() => removeLabel(value)} className="text-gray-400 hover:text-red-500 ml-auto">
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
          className={`${smallInputClass} w-16`}
        />
        <input
          type="text"
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          placeholder="Label text"
          className={`${smallInputClass} flex-1`}
          onKeyDown={(e) => e.key === 'Enter' && addLabel()}
        />
        <button type="button" onClick={addLabel} className="text-blue-600 hover:text-blue-700 font-medium">
          Add
        </button>
      </div>
    </div>
  );
}
