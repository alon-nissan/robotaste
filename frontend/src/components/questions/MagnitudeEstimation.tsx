/**
 * MagnitudeEstimation — free numeric entry proportional to perceived intensity
 * (question.type === 'magnitude_estimation'). With `modulus` set, the
 * reference stimulus value is shown (fixed-modulus ME).
 *
 * The raw text is kept locally so partially typed numbers ("1.") aren't lost;
 * only valid numbers are reported upward, anything else reports undefined.
 */
import { useState } from 'react';
import type { QuestionConfig } from '../../types';

interface MagnitudeEstimationProps {
  question: QuestionConfig;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
}

function magnitudeError(question: QuestionConfig, text: string): string | null {
  if (text.trim() === '') return null;
  const n = Number(text);
  if (!Number.isFinite(n)) return 'Please enter a number.';
  if (n < 0) return 'Please enter a positive number.';
  if (n === 0 && !question.allow_zero) return 'Please enter a number greater than 0.';
  if (question.max !== undefined && n > question.max) return `Please enter a number up to ${question.max}.`;
  return null;
}

export default function MagnitudeEstimation({ question, value, onChange }: MagnitudeEstimationProps) {
  const [text, setText] = useState(value !== undefined ? String(value) : '');
  const error = magnitudeError(question, text);
  const inputId = `me-${question.id}`;

  function handleChange(next: string) {
    setText(next);
    const n = Number(next);
    if (next.trim() !== '' && magnitudeError(question, next) === null && Number.isFinite(n)) {
      onChange(n);
    } else {
      onChange(undefined);
    }
  }

  return (
    <div className="max-w-xs mx-auto">
      {question.modulus !== undefined && (
        <div className="mb-3 rounded-lg border border-border bg-white px-4 py-2 text-center text-sm text-text-secondary">
          {question.reference_label ?? 'The reference sample'} ={' '}
          <span className="font-semibold text-text-primary">{question.modulus}</span>
        </div>
      )}
      <label htmlFor={inputId} className="sr-only">
        {question.label}
      </label>
      <input
        id={inputId}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={text}
        onChange={(e) => handleChange(e.target.value.replace(',', '.'))}
        aria-invalid={error !== null}
        className="w-full rounded-lg border border-border bg-white p-3 text-center text-2xl text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
        placeholder="Your number"
      />
      {error && <div className="mt-2 text-center text-sm text-red-700">⚠️ {error}</div>}
    </div>
  );
}
