/**
 * CategoryScale — discrete labelled points (9-point hedonic, Likert, JAR,
 * category intensity, facial scales). question.type === 'category_scale'.
 * Nothing is pre-selected; the answer is the option's numeric `value`.
 */
import type { QuestionConfig } from '../../types';
import { normalizeOptions } from '../../utils/questionnaire';

interface CategoryScaleProps {
  question: QuestionConfig;
  value: number | undefined;
  onChange: (value: number) => void;
}

export default function CategoryScale({ question, value, onChange }: CategoryScaleProps) {
  const options = normalizeOptions(question.options);
  const style = question.style ?? 'buttons';
  const layout = question.layout ?? 'horizontal';

  const containerClass =
    layout === 'vertical'
      ? 'flex flex-col gap-2 max-w-md mx-auto'
      : layout === 'grid'
        ? 'grid grid-cols-2 sm:grid-cols-3 gap-2'
        : 'flex flex-wrap justify-center gap-2';

  return (
    <div role="radiogroup" aria-label={question.label} className={containerClass}>
      {options.map((opt) => {
        const selected = value !== undefined && String(value) === String(opt.value);
        const numeric = typeof opt.value === 'number' ? opt.value : Number(opt.value);
        const select = () => onChange(numeric);

        if (style === 'faces') {
          return (
            <button
              key={String(opt.value)}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={select}
              className={`flex w-20 sm:w-24 flex-col items-center gap-1 rounded-xl border p-2 transition-all duration-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary ${
                selected
                  ? 'border-2 border-primary bg-primary/10'
                  : 'border-border bg-white hover:border-primary/40'
              }`}
            >
              <span className="text-4xl sm:text-5xl leading-none" aria-hidden="true">
                {opt.icon ?? '•'}
              </span>
              <span className={`text-xs text-center leading-tight ${selected ? 'text-primary font-semibold' : 'text-text-secondary'}`}>
                {opt.label}
              </span>
            </button>
          );
        }

        if (style === 'radio') {
          return (
            <button
              key={String(opt.value)}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={select}
              className={`flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-all duration-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary ${
                selected
                  ? 'border-2 border-primary bg-primary/10'
                  : 'border-border bg-white hover:border-primary/40'
              }`}
            >
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
                  selected ? 'border-primary' : 'border-text-secondary'
                }`}
                aria-hidden="true"
              >
                {selected && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
              </span>
              {opt.icon && <span aria-hidden="true">{opt.icon}</span>}
              <span className={`text-base ${selected ? 'text-primary font-semibold' : 'text-text-primary'}`}>
                {opt.label}
              </span>
            </button>
          );
        }

        return (
          <button
            key={String(opt.value)}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={select}
            className={`rounded-xl border px-4 py-3 text-sm font-medium transition-all duration-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary ${
              selected
                ? 'border-2 border-primary bg-primary/10 text-primary'
                : 'border-border bg-white text-text-primary hover:border-primary/40'
            }`}
          >
            {opt.icon && <span className="mr-1" aria-hidden="true">{opt.icon}</span>}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
