/**
 * RankingQuestion — tap items in order of preference (question.type === 'ranking').
 * Tapping a ranked item removes it and renumbers the rest. The answer (list
 * of option values, best first) is reported only once every item is ranked;
 * a partial ranking reports undefined.
 */
import { useEffect, useMemo, useState } from 'react';
import type { QuestionConfig } from '../../types';
import { normalizeOptions, seededShuffle } from '../../utils/questionnaire';

interface RankingQuestionProps {
  question: QuestionConfig;
  value: Array<string | number> | undefined;
  onChange: (value: Array<string | number> | undefined) => void;
  seed: string;
  onOrder?: (order: Array<string | number>) => void;
}

export default function RankingQuestion({ question, value, onChange, seed, onOrder }: RankingQuestionProps) {
  const options = useMemo(() => {
    const opts = normalizeOptions(question.options);
    return question.randomize_order === false ? opts : seededShuffle(opts, `${seed}:${question.id}`);
  }, [question.options, question.randomize_order, question.id, seed]);

  useEffect(() => {
    onOrder?.(options.map((o) => o.value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options]);

  const [order, setOrder] = useState<Array<string | number>>(value ?? []);

  function update(next: Array<string | number>) {
    setOrder(next);
    onChange(next.length === options.length ? next : undefined);
  }

  function tap(v: string | number) {
    const idx = order.findIndex((o) => String(o) === String(v));
    if (idx >= 0) update(order.filter((_, i) => i !== idx));
    else update([...order, v]);
  }

  return (
    <div className="max-w-md mx-auto">
      <div className="space-y-2" role="list" aria-label={question.label}>
        {options.map((opt) => {
          const rank = order.findIndex((o) => String(o) === String(opt.value));
          const ranked = rank >= 0;
          return (
            <button
              key={String(opt.value)}
              type="button"
              role="listitem"
              aria-label={ranked ? `${opt.label}, ranked ${rank + 1}` : `${opt.label}, not ranked`}
              onClick={() => tap(opt.value)}
              className={`flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-all duration-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary ${
                ranked
                  ? 'border-2 border-primary bg-primary/10'
                  : 'border-border bg-white hover:border-primary/40'
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
                  ranked ? 'bg-primary text-white' : 'border-2 border-dashed border-border text-text-secondary'
                }`}
                aria-hidden="true"
              >
                {ranked ? rank + 1 : ''}
              </span>
              {opt.icon && <span aria-hidden="true">{opt.icon}</span>}
              <span className={`text-base ${ranked ? 'text-primary font-semibold' : 'text-text-primary'}`}>
                {opt.label}
              </span>
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex items-center justify-between text-sm text-text-secondary">
        <span>
          {order.length} of {options.length} ranked
        </span>
        {order.length > 0 && (
          <button
            type="button"
            onClick={() => update([])}
            className="underline hover:text-text-primary cursor-pointer"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
