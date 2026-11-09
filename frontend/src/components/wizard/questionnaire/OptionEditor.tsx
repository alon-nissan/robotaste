/**
 * OptionEditor — edit the options of category / CATA / ranking questions.
 * `valueKind="number"` (category scales) keeps values numeric; `"text"`
 * (CATA, ranking) auto-derives the stored value from the label until the
 * moderator edits the value directly.
 */
import type { ChoiceOption, QuestionConfig } from '../../../types';
import { normalizeOptions, slugify } from '../../../utils/questionnaire';
import { smallInputClass } from './styles';

interface OptionEditorProps {
  options: QuestionConfig['options'];
  valueKind: 'number' | 'text';
  showIcons?: boolean;
  onChange: (options: ChoiceOption[]) => void;
}

export default function OptionEditor({ options, valueKind, showIcons = false, onChange }: OptionEditorProps) {
  const opts = normalizeOptions(options);

  function update(index: number, patch: Partial<ChoiceOption>) {
    onChange(opts.map((o, i) => (i === index ? { ...o, ...patch } : o)));
  }

  function updateLabel(index: number, label: string) {
    const current = opts[index];
    const autoValue = valueKind === 'text' && (current.value === slugify(current.label) || current.value === '');
    update(index, autoValue ? { label, value: slugify(label) } : { label });
  }

  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= opts.length) return;
    const next = [...opts];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  function add() {
    if (valueKind === 'number') {
      const nums = opts.map((o) => Number(o.value)).filter(Number.isFinite);
      const nextValue = nums.length ? Math.max(...nums) + 1 : 1;
      onChange([...opts, { value: nextValue, label: String(nextValue) }]);
    } else {
      const label = `Option ${opts.length + 1}`;
      onChange([...opts, { value: slugify(label), label }]);
    }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className="w-24">Stored value</span>
        {showIcons && <span className="w-12">Icon</span>}
        <span>Label shown to subject</span>
      </div>
      {opts.map((o, i) => (
        <div key={i} className="flex items-center gap-2" data-testid="option-row">
          <input
            type={valueKind === 'number' ? 'number' : 'text'}
            step="any"
            aria-label={`Option ${i + 1} value`}
            value={String(o.value)}
            onChange={(e) =>
              update(i, {
                value: valueKind === 'number' ? parseFloat(e.target.value) : e.target.value,
              })
            }
            className={`${smallInputClass} w-24 font-mono`}
          />
          {showIcons && (
            <input
              type="text"
              aria-label={`Option ${i + 1} icon`}
              value={o.icon ?? ''}
              onChange={(e) => update(i, { icon: e.target.value || undefined })}
              className={`${smallInputClass} w-12 text-center`}
              placeholder="🙂"
            />
          )}
          <input
            type="text"
            aria-label={`Option ${i + 1} label`}
            value={o.label}
            onChange={(e) => updateLabel(i, e.target.value)}
            className={`${smallInputClass} flex-1`}
          />
          <div className="flex shrink-0 text-gray-400">
            <button type="button" onClick={() => move(i, -1)} aria-label="Move option up" className="px-1 hover:text-gray-700">
              ↑
            </button>
            <button type="button" onClick={() => move(i, 1)} aria-label="Move option down" className="px-1 hover:text-gray-700">
              ↓
            </button>
            <button
              type="button"
              onClick={() => onChange(opts.filter((_, j) => j !== i))}
              aria-label={`Remove option ${o.label}`}
              className="px-1 hover:text-red-500"
            >
              ×
            </button>
          </div>
        </div>
      ))}
      <button type="button" onClick={add} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
        + Add option
      </button>
    </div>
  );
}
