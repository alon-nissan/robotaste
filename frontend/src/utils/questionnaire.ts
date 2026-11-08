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

// ─── AUTHORING HELPERS (protocol wizard) ──────────────────────────────────
// These mirror robotaste/config/scales.py so the wizard can flag problems
// before the server-side /protocols/validate call.

const NUMERIC_TYPES = new Set([
  'slider',
  'pillbox',
  'line_scale',
  'category_scale',
  'magnitude_estimation',
]);

/** True if the question yields a single number (usable as an optimisation target). */
export function isNumericQuestion(q: QuestionConfig): boolean {
  if (!NUMERIC_TYPES.has(q.type)) return false;
  if (q.type === 'pillbox' && q.options?.length) {
    return normalizeOptions(q.options).every((o) => typeof o.value === 'number');
  }
  return true;
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** Problems with a question definition (empty list = valid). */
export function validateQuestion(q: QuestionConfig): string[] {
  const errors: string[] = [];
  if (!q.id?.trim()) errors.push('Question ID is required.');
  if (!q.label?.trim()) errors.push('Question text is required.');

  if (q.type === 'slider' || q.type === 'line_scale') {
    if (!isNum(q.min) || !isNum(q.max)) errors.push('Min and max are required.');
    else if (q.min >= q.max) errors.push('Min must be smaller than max.');
    if (q.step !== undefined && (!isNum(q.step) || q.step <= 0)) errors.push('Step must be a positive number.');
  }

  if (q.type === 'line_scale') {
    const anchors = q.anchors ?? [];
    let prev: number | null = null;
    anchors.forEach((a, i) => {
      if (!isNum(a.value)) errors.push(`Anchor ${i + 1} needs a numeric value.`);
      else {
        if (isNum(q.min) && isNum(q.max) && (a.value < q.min || a.value > q.max)) {
          errors.push(`Anchor "${a.label}" (${a.value}) is outside ${q.min}–${q.max}.`);
        }
        if (prev !== null && a.value <= prev) errors.push('Anchor values must increase from top of the list to bottom.');
        prev = a.value;
      }
      if (!a.label?.trim()) errors.push(`Anchor ${i + 1} needs a label.`);
    });
  }

  if (q.type === 'category_scale' || q.type === 'multi_select' || q.type === 'ranking' || q.type === 'dropdown') {
    const opts = normalizeOptions(q.options);
    const min = q.type === 'multi_select' || q.type === 'dropdown' ? 1 : 2;
    if (opts.length < min) errors.push(`Add at least ${min} option${min > 1 ? 's' : ''}.`);
    const values = opts.map((o) => String(o.value));
    if (new Set(values).size !== values.length) errors.push('Option values must be unique.');
    if (opts.some((o) => !String(o.label ?? '').trim())) errors.push('Every option needs a label.');
    if (q.type === 'category_scale' && opts.some((o) => !isNum(o.value))) {
      errors.push('Category options need numeric values.');
    }
    if (q.type === 'category_scale' && q.ideal_value !== undefined && !values.includes(String(q.ideal_value))) {
      errors.push('Ideal value must be one of the option values.');
    }
    if (q.type === 'multi_select') {
      const lo = q.min_selected ?? 0;
      if (q.max_selected !== undefined && (q.max_selected < Math.max(lo, 1) || q.max_selected > opts.length)) {
        errors.push('Max selected must be between min selected and the number of options.');
      }
      if (lo > opts.length) errors.push('Min selected exceeds the number of options.');
    }
  }

  if (q.type === 'magnitude_estimation') {
    if (q.modulus !== undefined && (!isNum(q.modulus) || q.modulus <= 0)) errors.push('Modulus must be a positive number.');
    if (q.max !== undefined && (!isNum(q.max) || q.max <= 0)) errors.push('Max must be a positive number.');
  }
  return errors;
}

/** Sensible starting fields when the moderator switches a question to `type`. */
export function defaultsForType(type: QuestionConfig['type']): Partial<QuestionConfig> {
  switch (type) {
    case 'line_scale':
      return {
        min: 0,
        max: 100,
        orientation: 'horizontal',
        polarity: 'unipolar',
        anchors: [
          { value: 0, label: 'Not at all' },
          { value: 100, label: 'Extremely' },
        ],
        show_value: false,
        start_unmarked: true,
        show_ticks: true,
        step: undefined,
        default: undefined,
      };
    case 'category_scale':
      return {
        layout: 'horizontal',
        style: 'buttons',
        options: [1, 2, 3, 4, 5].map((v) => ({ value: v, label: String(v) })),
        min: undefined,
        max: undefined,
        default: undefined,
      };
    case 'magnitude_estimation':
      return { allow_zero: false, min: undefined, max: undefined, default: undefined };
    case 'multi_select':
      return {
        randomize_order: true,
        min_selected: 0,
        options: [
          { value: 'option_a', label: 'Option A' },
          { value: 'option_b', label: 'Option B' },
        ],
        default: undefined,
      };
    case 'ranking':
      return {
        randomize_order: true,
        options: [
          { value: 'option_a', label: 'Option A' },
          { value: 'option_b', label: 'Option B' },
          { value: 'option_c', label: 'Option C' },
        ],
        default: undefined,
      };
    case 'dropdown':
      return { options: ['Option A', 'Option B'], default: undefined };
    case 'slider':
      return { min: 1, max: 9, step: 0.01, default: 5 };
    case 'pillbox':
      return { min: 1, max: 5, default: undefined };
    default:
      return { default: undefined };
  }
}

/** Turn a label into a safe ID / option value: "How sweet?" → "how_sweet". */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

/**
 * Problems with a whole questionnaire as authored in the wizard, each prefixed
 * with the question it belongs to. `needsBO` = the schedule uses bo_selected.
 */
export function questionnaireErrors(
  questionnaire: { questions: QuestionConfig[]; bayesian_target?: { variable: string; formula?: string } } | undefined,
  needsBO: boolean
): string[] {
  const questions = questionnaire?.questions ?? [];
  const errors: string[] = [];
  if (!questions.length) errors.push('At least one question is required.');
  const seen = new Set<string>();
  questions.forEach((q, i) => {
    const name = q.label?.trim() ? `"${q.label}"` : `Question ${i + 1}`;
    if (seen.has(q.id)) errors.push(`${name}: duplicate question ID "${q.id}".`);
    seen.add(q.id);
    validateQuestion(q).forEach((e) => errors.push(`${name}: ${e}`));
  });
  const target = questionnaire?.bayesian_target;
  if (target?.variable) {
    if (target.variable === 'composite') {
      if (!target.formula?.trim()) errors.push('Optimization target: the composite formula is empty.');
    } else {
      const tq = questions.find((q) => q.id === target.variable);
      if (!tq) errors.push(`Optimization target "${target.variable}" is not a question in this questionnaire.`);
      else if (!isNumericQuestion(tq)) errors.push(`Optimization target ${tq.label || tq.id} is not a numeric question.`);
    }
  } else if (needsBO) {
    errors.push('Optimization target is required because the schedule uses BO-selected cycles.');
  }
  return errors;
}
