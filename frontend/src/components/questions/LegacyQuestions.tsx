/**
 * Legacy question renderers (slider, pillbox, dropdown, text), moved out of
 * QuestionnairePage so the questionnaire and custom survey phases share them.
 *
 * Fix vs. the previous version: slider scale labels are placed at their
 * numeric value (not spread evenly), so uneven label sets line up correctly.
 */
import type { QuestionConfig } from '../../types';
import { normalizeOptions } from '../../utils/questionnaire';

/** Thumb diameter of `.slider-range` in index.css; used to align labels with the thumb centre. */
const THUMB_PX = 18;

/** CSS left offset that lines up with a native range thumb centre at `frac` (0..1). */
function thumbLeft(frac: number) {
  return `calc(${frac * 100}% + ${THUMB_PX / 2 - frac * THUMB_PX}px)`;
}

export function SliderQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: number;
  onChange: (v: number) => void;
}) {
  const min = question.min ?? 0;
  const max = question.max ?? 10;
  const step = question.step ?? 1;
  const labels = question.scale_labels ?? {};
  const range = max - min || 1;

  const labelKeys = Object.keys(labels)
    .map(Number)
    .filter((n) => !isNaN(n) && n >= min && n <= max)
    .sort((a, b) => a - b);

  const frac = Math.min(1, Math.max(0, (value - min) / range));

  return (
    <div>
      {/* Scale labels positioned at their value */}
      {labelKeys.length > 0 && (
        <div className="relative mb-1 h-10 text-sm text-text-secondary">
          {labelKeys.map((key) => {
            const f = (key - min) / range;
            const translate = f <= 0.02 ? '' : f >= 0.98 ? '-translate-x-full' : '-translate-x-1/2';
            const align = f <= 0.02 ? 'text-left' : f >= 0.98 ? 'text-right' : 'text-center';
            return (
              <span
                key={key}
                data-scale-label={key}
                className={`absolute bottom-0 leading-tight ${f <= 0.02 || f >= 0.98 ? 'max-w-[30%]' : 'max-w-[22%]'} ${translate} ${align}`}
                style={{
                  left: f <= 0.02 ? 0 : f >= 0.98 ? '100%' : thumbLeft(f),
                }}
              >
                {labels[String(key)]}
              </span>
            );
          })}
        </div>
      )}

      {/* Current value floating above the thumb */}
      <div className="relative mb-1 h-5">
        <div
          className="absolute w-10 -translate-x-1/2 text-center text-sm font-semibold text-primary"
          style={{ left: thumbLeft(frac) }}
        >
          {typeof value === 'number' ? value.toFixed(step < 1 ? 2 : 0) : value}
        </div>
      </div>

      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={question.label}
        onChange={(e) => onChange(Number(e.target.value))}
        className="slider-range w-full"
      />

      {labelKeys.length === 0 && (
        <div className="flex justify-between text-sm text-text-secondary mt-1">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      )}
    </div>
  );
}

export function PillboxQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: number | string | undefined;
  onChange: (v: number | string) => void;
}) {
  const labels = question.scale_labels ?? {};
  const hasOptions = Boolean(question.options && question.options.length > 0);

  let pills: { key: string; label: string; answer: number | string }[] = [];
  if (hasOptions) {
    pills = normalizeOptions(question.options).map((opt) => ({
      key: String(opt.value),
      label: labels[String(opt.value)] ?? opt.label,
      answer: opt.value,
    }));
  } else if (question.min !== undefined && question.max !== undefined) {
    for (let i = question.min; i <= question.max; i++) {
      pills.push({ key: String(i), label: labels[String(i)] ?? String(i), answer: i });
    }
  }

  return (
    <div className="flex flex-wrap gap-2 justify-center" role="radiogroup" aria-label={question.label}>
      {pills.map((pill) => {
        const selected = value !== undefined && String(value) === pill.key;
        return (
          <button
            key={pill.key}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(pill.answer)}
            className={`
              px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200
              border cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary
              ${
                selected
                  ? 'bg-primary/10 border-2 border-primary text-primary'
                  : 'border-border bg-white text-text-primary hover:border-primary/40'
              }
            `}
          >
            {pill.label}
          </button>
        );
      })}
    </div>
  );
}

export function DropdownQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      aria-label={question.label}
      onChange={(e) => onChange(e.target.value)}
      className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
    >
      <option value="">Select...</option>
      {normalizeOptions(question.options).map((opt) => (
        <option key={String(opt.value)} value={String(opt.value)}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

export function TextInputQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <input
      type="text"
      value={value}
      aria-label={question.label}
      maxLength={question.max_length}
      onChange={(e) => onChange(e.target.value)}
      className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
    />
  );
}

export function TextAreaQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <textarea
      value={value}
      aria-label={question.label}
      maxLength={question.max_length}
      onChange={(e) => onChange(e.target.value)}
      rows={3}
      className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary resize-y"
    />
  );
}
