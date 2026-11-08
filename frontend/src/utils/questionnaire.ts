/**
 * Questionnaire helpers shared by the subject questionnaire page and custom
 * survey phases: answer initialisation, required/answered checks, option
 * normalisation, seeded shuffling and per-question response metadata.
 */
import { useCallback, useMemo, useRef } from 'react';
import type { AnswerMeta, ChoiceOption, QuestionConfig, ScaleAnchor } from '../types';

const TEXT_TYPES = new Set(['text_input', 'text_area']);

/**
 * Starting answers for a questionnaire.
 * - Legacy sliders start where their thumb is drawn (default, else min), as before.
 * - Dropdown / text keep their `default` if given.
 * - Line scales start unmarked unless `start_unmarked: false` (then default, else midpoint).
 * - Category, magnitude, multi-select and ranking questions always start empty.
 */
export function initialAnswers(questions: QuestionConfig[]): Record<string, unknown> {
  const answers: Record<string, unknown> = {};
  for (const q of questions) {
    if (q.type === 'slider' && q.display_type !== 'pillboxes') {
      answers[q.id] = typeof q.default === 'number' ? q.default : q.min ?? 5;
    } else if (q.type === 'line_scale' && q.start_unmarked === false) {
      const min = q.min ?? 0;
      const max = q.max ?? 100;
      answers[q.id] = typeof q.default === 'number' ? q.default : (min + max) / 2;
    } else if (
      q.default !== undefined &&
      (q.type === 'dropdown' || TEXT_TYPES.has(q.type))
    ) {
      answers[q.id] = q.default;
    }
  }
  return answers;
}

/**
 * Whether the subject must answer before moving on. Questions are required
 * unless `required: false`; free-text questions are optional unless
 * explicitly `required: true` (they are usually comment boxes).
 */
export function mustAnswer(q: QuestionConfig): boolean {
  if (TEXT_TYPES.has(q.type)) return q.required === true;
  return q.required !== false;
}

export function isAnswered(q: QuestionConfig, value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (q.type === 'multi_select') {
    return Array.isArray(value) && value.length >= (q.min_selected ?? 0);
  }
  if (q.type === 'ranking') {
    return Array.isArray(value) && value.length === normalizeOptions(q.options).length;
  }
  if (typeof value === 'string') return value.trim() !== '';
  if (typeof value === 'number') return Number.isFinite(value);
  return true;
}

/** First question that must be answered but isn't, or null. */
export function firstUnanswered(
  questions: QuestionConfig[],
  answers: Record<string, unknown>
): QuestionConfig | null {
  return questions.find((q) => mustAnswer(q) && !isAnswered(q, answers[q.id])) ?? null;
}

/** Accepts ['a', 'b'] or [{value, label}] and always returns ChoiceOption[]. */
export function normalizeOptions(options: QuestionConfig['options']): ChoiceOption[] {
  return (options ?? []).map((opt) =>
    typeof opt === 'string' ? { value: opt, label: opt } : opt
  );
}

/** Deterministic string hash → 32-bit seed (FNV-1a). */
function hashSeed(seed: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** Fisher–Yates shuffle driven by a seeded PRNG (mulberry32), so order is stable per seed. */
export function seededShuffle<T>(items: T[], seed: string): T[] {
  let state = hashSeed(seed);
  const rand = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export function nearestAnchorLabel(anchors: ScaleAnchor[] | undefined, value: number): string | undefined {
  if (!anchors?.length) return undefined;
  let best = anchors[0];
  for (const a of anchors) {
    if (Math.abs(a.value - value) < Math.abs(best.value - value)) best = a;
  }
  return best.label;
}

/** Short instruction shown under a question in one-at-a-time mode. */
export function defaultInstruction(q: QuestionConfig): string {
  switch (q.type) {
    case 'line_scale':
    case 'slider':
      return 'Tap the line to mark your rating';
    case 'category_scale':
    case 'pillbox':
    case 'dropdown':
      return 'Choose one option';
    case 'multi_select':
      return 'Select all that apply';
    case 'ranking':
      return 'Tap the items in order of preference';
    case 'magnitude_estimation':
      return 'Enter a number';
    default:
      return '';
  }
}

// ─── RESPONSE METADATA ─────────────────────────────────────────────────────

interface MetaState {
  shownAt: number;
  interacted: boolean;
  lastChangeAt: number | null;
  nChanges: number;
  optionOrder?: Array<string | number>;
}

/**
 * Tracks per-question interaction metadata (interacted, response time,
 * number of changes, displayed option order) for `answer_meta`.
 *
 * - `markShown(ids)` starts the clock for questions now on screen (all of
 *   them in all-at-once mode, the current one in one-at-a-time mode). Only
 *   the first call per question counts.
 * - `recordChange(id)` is called on every answer change.
 * - `recordOptionOrder(id, order)` stores the order options were displayed in.
 */
export function useAnswerMeta() {
  const stateRef = useRef<Record<string, MetaState>>({});

  const ensure = (id: string): MetaState => {
    if (!stateRef.current[id]) {
      stateRef.current[id] = {
        shownAt: performance.now(),
        interacted: false,
        lastChangeAt: null,
        nChanges: 0,
      };
    }
    return stateRef.current[id];
  };

  const markShown = useCallback((ids: string[]) => {
    ids.forEach((id) => ensure(id));
  }, []);

  const recordChange = useCallback((id: string) => {
    const s = ensure(id);
    s.interacted = true;
    s.nChanges += 1;
    s.lastChangeAt = performance.now();
  }, []);

  const recordOptionOrder = useCallback((id: string, order: Array<string | number>) => {
    ensure(id).optionOrder = order;
  }, []);

  const reset = useCallback(() => {
    stateRef.current = {};
  }, []);

  const build = useCallback((questions: QuestionConfig[]): Record<string, AnswerMeta> => {
    const meta: Record<string, AnswerMeta> = {};
    for (const q of questions) {
      const s = stateRef.current[q.id];
      const entry: AnswerMeta = {
        interacted: s?.interacted ?? false,
        rt_ms: s?.lastChangeAt != null ? Math.round(s.lastChangeAt - s.shownAt) : null,
        n_changes: s?.nChanges ?? 0,
      };
      if (q.preset) entry.preset = q.preset;
      if (q.preset_version) entry.preset_version = q.preset_version;
      if (s?.optionOrder) entry.option_order = s.optionOrder;
      meta[q.id] = entry;
    }
    return meta;
  }, []);

  // Stable object so callers can list it in effect dependencies.
  return useMemo(
    () => ({ markShown, recordChange, recordOptionOrder, reset, build }),
    [markShown, recordChange, recordOptionOrder, reset, build]
  );
}
