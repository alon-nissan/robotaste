import type { DRDataPoint } from '../../types';

export interface ConcentrationStats {
  concentration: number;
  n: number;
  mean: number;
  std: number;
  sem: number;
  min: number;
  max: number;
}

/**
 * Group a protocol's data points by concentration of `ingredient` and compute
 * summary statistics of `variable` within each group. Single source of truth
 * for the mean/SEM math — used by DoseResponseChart's mean-trace builder and
 * by both pages' Summary Statistics tables, so chart and table numbers can't drift.
 */
export function groupStatsByConcentration(
  points: DRDataPoint[], ingredient: string, variable: string,
): ConcentrationStats[] {
  const groups = new Map<number, number[]>();
  for (const dp of points) {
    const c = dp.concentrations[ingredient];
    const v = Number(dp.responses[variable]);
    if (c === undefined || !Number.isFinite(v)) continue;
    const arr = groups.get(c) ?? [];
    arr.push(v);
    groups.set(c, arr);
  }
  return Array.from(groups.entries())
    .map(([concentration, vals]) => {
      const n = vals.length;
      const mean = vals.reduce((a, b) => a + b, 0) / n;
      const variance = n > 1 ? vals.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1) : 0;
      const std = Math.sqrt(variance);
      const sem = n > 1 ? std / Math.sqrt(n) : 0;
      return { concentration, n, mean, std, sem, min: Math.min(...vals), max: Math.max(...vals) };
    })
    .sort((a, b) => a.concentration - b.concentration);
}
