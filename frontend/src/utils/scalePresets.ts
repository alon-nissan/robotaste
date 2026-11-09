/**
 * Scale preset helpers for the protocol wizard.
 *
 * Presets (VAS, gVAS, gLMS, 9-pt hedonic, …) are defined once on the backend
 * in robotaste/config/scales.py and served by GET /protocols/scale-presets.
 * This module fetches them once per page load and turns a preset into an
 * editable question.
 */
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { QuestionConfig, ScalePreset, ScalePresetsResponse } from '../types';

let cache: Promise<ScalePresetsResponse> | null = null;

function loadPresets(): Promise<ScalePresetsResponse> {
  if (!cache) {
    cache = api
      .get<ScalePresetsResponse>('/protocols/scale-presets')
      .then((res) => res.data)
      .catch((err) => {
        cache = null; // allow retry on next mount
        throw err;
      });
  }
  return cache;
}

export function useScalePresets() {
  const [data, setData] = useState<ScalePresetsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    loadPresets()
      .then((d) => alive && setData(d))
      .catch(() => alive && setError('Could not load the scale library.'));
    return () => {
      alive = false;
    };
  }, []);

  return {
    presets: data?.presets ?? [],
    byId: Object.fromEntries((data?.presets ?? []).map((p) => [p.id, p])) as Record<string, ScalePreset>,
    loading: !data && !error,
    error,
  };
}

/** A fully expanded, editable question built from a preset. */
export function questionFromPreset(preset: ScalePreset, id: string, label: string): QuestionConfig {
  return {
    ...(JSON.parse(JSON.stringify(preset.question)) as Partial<QuestionConfig>),
    type: preset.question.type ?? 'line_scale',
    preset: preset.id,
    id,
    label,
    required: true,
  } as QuestionConfig;
}

/** Fields that define the scale itself; changing them means "modified from preset". */
const SCALE_FIELDS: Array<keyof QuestionConfig> = ['type', 'min', 'max', 'anchors', 'options', 'ideal_value'];

export function isModifiedFromPreset(q: QuestionConfig, preset: ScalePreset | undefined): boolean {
  if (!preset) return false;
  return SCALE_FIELDS.some((field) => {
    const presetValue = preset.question[field];
    if (presetValue === undefined) return false;
    return JSON.stringify(q[field]) !== JSON.stringify(presetValue);
  });
}

/** Restore the scale-defining fields of a question to its preset (keeps id/label/help text). */
export function resetToPreset(q: QuestionConfig, preset: ScalePreset): QuestionConfig {
  return {
    ...q,
    ...(JSON.parse(JSON.stringify(preset.question)) as Partial<QuestionConfig>),
    id: q.id,
    label: q.label,
    help_text: q.help_text,
    required: q.required,
    preset: preset.id,
  } as QuestionConfig;
}

export const TRANSFORM_DESCRIPTIONS: Record<string, string> = {
  identity: 'Raw rating',
  log: 'ln(x + 1)',
  log10: 'log10(x) — values must be > 0',
  log10p1: 'log10(x + 1) — recommended for gLMS / magnitude estimation',
  normalize: 'Rescale to 0–1 using the expected range',
  ideal_point: 'Closeness to an ideal value (JAR) — −|x − ideal|',
};
