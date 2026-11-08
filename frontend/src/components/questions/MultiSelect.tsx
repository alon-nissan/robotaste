/**
 * MultiSelect — check-all-that-apply (CATA). question.type === 'multi_select'.
 * Answer is the list of selected option values. With `randomize_order`, the
 * display order is a seeded shuffle (stable for a given seed) and reported via
 * `onOrder` so it can be stored in answer_meta.option_order.
 */
import { useEffect, useMemo } from 'react';
import type { QuestionConfig } from '../../types';
import { normalizeOptions, seededShuffle } from '../../utils/questionnaire';

interface MultiSelectProps {
  question: QuestionConfig;
  value: Array<string | number> | undefined;
  onChange: (value: Array<string | number>) => void;
  seed: string;
  onOrder?: (order: Array<string | number>) => void;
}

export default function MultiSelect({ question, value, onChange, seed, onOrder }: MultiSelectProps) {
  const options = useMemo(() => {
    const opts = normalizeOptions(question.options);
    return question.randomize_order === false ? opts : seededShuffle(opts, `${seed}:${question.id}`);
  }, [question.options, question.randomize_order, question.id, seed]);

  useEffect(() => {
    onOrder?.(options.map((o) => o.value));
    // Report once per order; onOrder identity is not meaningful.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options]);

  const selected = value ?? [];
  const maxSel = question.max_selected;
  const minSel = question.min_selected ?? 0;
  const atMax = maxSel !== undefined && selected.length >= maxSel;

  function toggle(v: string | number) {
    if (selected.some((s) => String(s) === String(v))) {
      onChange(selected.filter((s) => String(s) !== String(v)));
    } else if (!atMax) {
      onChange([...selected, v]);
    }
  }

  let hint = '';
  if (minSel > 0 && maxSel !== undefined) hint = `Select ${minSel}–${maxSel} options`;
  else if (minSel > 0) hint = `Select at least ${minSel}`;
  else if (maxSel !== undefined) hint = `Select up to ${maxSel}`;

  return (
    <div>
      {hint && <div className="mb-2 text-center text-sm text-text-secondary">{hint}</div>}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" role="group" aria-label={question.label}>
        {options.map((opt) => {
          const checked = selected.some((s) => String(s) === String(opt.value));
          const disabled = !checked && atMax;
          return (
            <button
              key={String(opt.value)}
              type="button"
              role="checkbox"
              aria-checked={checked}
              aria-disabled={disabled}
              onClick={() => toggle(opt.value)}
              className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary ${
                checked
                  ? 'border-2 border-primary bg-primary/10'
                  : disabled
                    ? 'border-border bg-white opacity-50 cursor-not-allowed'
                    : 'border-border bg-white hover:border-primary/40 cursor-pointer'
              }`}
            >
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 text-xs font-bold ${
                  checked ? 'border-primary bg-primary text-white' : 'border-text-secondary'
                }`}
                aria-hidden="true"
              >
                {checked ? '✓' : ''}
              </span>
              {opt.icon && <span aria-hidden="true">{opt.icon}</span>}
              <span className={`text-base ${checked ? 'text-primary font-semibold' : 'text-text-primary'}`}>
                {opt.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
