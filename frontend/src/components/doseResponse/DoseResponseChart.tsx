import Plot from 'react-plotly.js';
import type { Data, Layout } from 'plotly.js';
import type { DRDataPoint } from '../../types';
import { PLOTLY_CONFIG, TRANSPARENT_LAYOUT, axisStyle, hexToRgba } from './plotlyTheme';
import type { DRChartType } from './ChartTypeSelector';

export type { DRChartType };

export interface ProtocolSeries {
  protocolId: string;
  label: string;
  color: string;
  points: DRDataPoint[];
}

interface DoseResponseChartProps {
  chartType: DRChartType;
  series: ProtocolSeries[];
  variable: string;
  /** Y-axis label for mean/subjects/distribution, Z-axis label for the 3D surface. */
  responseLabel: string;
  /** Ingredient used as the X-axis for mean/subjects/distribution modes. */
  ingredient: string;
  ingredientLabel: string;
  /** Ingredients used as X/Y for the 3D surface (mixture protocols only). */
  ingredientX?: string;
  ingredientXLabel?: string;
  ingredientY?: string;
  ingredientYLabel?: string;
  /** Optional per-subject color override (used by 'subjects' mode); falls back to series color. */
  subjectColor?: (sessionId: string) => string;
  height?: number;
}

function fmtConc(val: number): string {
  if (val === 0) return '0';
  if (Math.abs(val) < 0.1) return val.toFixed(3);
  return val.toFixed(2);
}

function sortedConcentrationLabels(series: ProtocolSeries[], ingredient: string): string[] {
  const vals = new Set<number>();
  for (const s of series) {
    for (const p of s.points) {
      const c = p.concentrations[ingredient];
      if (c !== undefined) vals.add(c);
    }
  }
  return Array.from(vals).sort((a, b) => a - b).map(fmtConc);
}

function meanByConcentration(points: DRDataPoint[], ingredient: string, variable: string) {
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
      const sem = n > 1 ? Math.sqrt(variance) / Math.sqrt(n) : 0;
      return { concentration, mean, sem, n };
    })
    .sort((a, b) => a.concentration - b.concentration);
}

function meanBy2D(points: DRDataPoint[], xIng: string, yIng: string, variable: string) {
  const groups = new Map<string, { x: number; y: number; vals: number[] }>();
  for (const dp of points) {
    const x = dp.concentrations[xIng];
    const y = dp.concentrations[yIng];
    const v = Number(dp.responses[variable]);
    if (x === undefined || y === undefined || !Number.isFinite(v)) continue;
    const key = `${x}|${y}`;
    const g = groups.get(key) ?? { x, y, vals: [] };
    g.vals.push(v);
    groups.set(key, g);
  }
  return Array.from(groups.values()).map(g => ({
    x: g.x, y: g.y, mean: g.vals.reduce((a, b) => a + b, 0) / g.vals.length, n: g.vals.length,
  }));
}

function buildMeanTraces(series: ProtocolSeries[], ingredient: string, variable: string, label: string): Data[] {
  const traces: Data[] = [];
  for (const s of series) {
    const rows = meanByConcentration(s.points, ingredient, variable);
    if (rows.length === 0) continue;
    const x = rows.map(r => fmtConc(r.concentration));
    traces.push(
      {
        type: 'scatter', mode: 'lines', x, y: rows.map(r => r.mean - r.sem),
        line: { width: 0 }, hoverinfo: 'skip', showlegend: false,
      },
      {
        type: 'scatter', mode: 'lines', x, y: rows.map(r => r.mean + r.sem),
        line: { width: 0 }, fill: 'tonexty', fillcolor: hexToRgba(s.color, 0.15),
        hoverinfo: 'skip', showlegend: false,
      },
      {
        type: 'scatter', mode: 'lines+markers', x, y: rows.map(r => r.mean), name: s.label,
        line: { color: s.color, width: 2.5 },
        marker: { color: s.color, size: 7, line: { color: '#fff', width: 1.5 } },
        hovertemplate: `${s.label}<br>%{x} ${label}: %{y:.2f}<extra></extra>`,
      },
    );
  }
  return traces;
}

function buildSubjectTraces(
  series: ProtocolSeries[], ingredient: string, variable: string,
  subjectColor: ((sessionId: string) => string) | undefined, multiProtocol: boolean,
): Data[] {
  const traces: Data[] = [];
  for (const s of series) {
    const bySubject = new Map<string, { label: string; pts: { x: number; y: number }[] }>();
    for (const dp of s.points) {
      const c = dp.concentrations[ingredient];
      const v = dp.responses[variable];
      if (c === undefined || v == null) continue;
      const key = dp.session_id;
      const label = (dp.subject_name || dp.session_code) + (multiProtocol ? ` · ${s.label}` : '');
      const entry = bySubject.get(key) ?? { label, pts: [] };
      entry.pts.push({ x: c, y: Number(v) });
      bySubject.set(key, entry);
    }
    for (const [sid, entry] of bySubject) {
      entry.pts.sort((a, b) => a.x - b.x);
      const color = subjectColor ? subjectColor(sid) : s.color;
      traces.push({
        type: 'scatter', mode: 'lines+markers',
        x: entry.pts.map(p => p.x), y: entry.pts.map(p => p.y), name: entry.label,
        line: { color, width: 2 }, marker: { color, size: 6 },
        hovertemplate: `${entry.label}<br>%{x}: %{y:.2f}<extra></extra>`,
      });
    }
  }
  return traces;
}

function buildDistributionTraces(series: ProtocolSeries[], ingredient: string, variable: string): Data[] {
  return series.map(s => {
    const x: string[] = [];
    const y: number[] = [];
    for (const dp of s.points) {
      const c = dp.concentrations[ingredient];
      const v = dp.responses[variable];
      if (c === undefined || v == null) continue;
      x.push(fmtConc(c));
      y.push(Number(v));
    }
    return {
      type: 'box', x, y, name: s.label, marker: { color: s.color },
      boxpoints: 'all', jitter: 0.4, pointpos: 0,
    } satisfies Data;
  });
}

function buildSurfaceTraces(
  series: ProtocolSeries[], xIng: string, yIng: string, variable: string, responseLabel: string,
): Data[] {
  const traces: Data[] = [];
  for (const s of series) {
    const pts = meanBy2D(s.points, xIng, yIng, variable);
    if (pts.length < 3) continue;
    traces.push(
      {
        type: 'mesh3d', x: pts.map(p => p.x), y: pts.map(p => p.y), z: pts.map(p => p.mean),
        opacity: 0.55, color: s.color, name: s.label, showlegend: true,
        hovertemplate: `${s.label}<br>%{x:.2f}, %{y:.2f}<br>${responseLabel}: %{z:.2f}<extra></extra>`,
      } as Data,
      {
        type: 'scatter3d', mode: 'markers',
        x: pts.map(p => p.x), y: pts.map(p => p.y), z: pts.map(p => p.mean),
        marker: { color: s.color, size: 4, line: { color: '#fff', width: 1 } }, showlegend: false,
        hovertemplate: `${s.label}<br>%{x:.2f}, %{y:.2f}<br>${responseLabel}: %{z:.2f}<extra></extra>`,
      },
    );
  }
  return traces;
}

export default function DoseResponseChart({
  chartType, series, variable, responseLabel,
  ingredient, ingredientLabel, ingredientX, ingredientXLabel, ingredientY, ingredientYLabel,
  subjectColor, height = 420,
}: DoseResponseChartProps) {
  const activeSeries = series.filter(s => s.points.length > 0);

  if (activeSeries.length === 0) {
    return (
      <div className="flex items-center justify-center text-text-secondary text-sm" style={{ height }}>
        No data for the selected filters.
      </div>
    );
  }

  const multiProtocol = activeSeries.length > 1;

  if (chartType === 'surface3d') {
    const xIng = ingredientX ?? ingredient;
    const yIng = ingredientY ?? ingredient;
    const data = buildSurfaceTraces(activeSeries, xIng, yIng, variable, responseLabel);
    if (data.length === 0) {
      return (
        <div className="flex items-center justify-center text-center text-text-secondary text-sm px-6" style={{ height }}>
          Not enough distinct concentration combinations for a 3D surface (need ≥3 per protocol).
        </div>
      );
    }
    const layout: Partial<Layout> = {
      ...TRANSPARENT_LAYOUT,
      margin: { l: 0, r: 0, t: 10, b: 0 },
      height,
      legend: { orientation: 'h', y: 1.05 },
      scene: {
        xaxis: axisStyle(ingredientXLabel ?? xIng),
        yaxis: axisStyle(ingredientYLabel ?? yIng),
        zaxis: axisStyle(responseLabel),
        camera: { eye: { x: 1.35, y: 1.35, z: 0.85 } },
      },
    };
    return <Plot data={data} layout={layout} style={{ width: '100%', height }} config={PLOTLY_CONFIG} />;
  }

  const categoryLabels = sortedConcentrationLabels(activeSeries, ingredient);
  const baseLayout: Partial<Layout> = {
    ...TRANSPARENT_LAYOUT,
    margin: { l: 60, r: 20, t: 10, b: 60 },
    height,
    legend: { orientation: 'h', y: 1.15 },
    xaxis: {
      ...axisStyle(ingredientLabel),
      type: 'category', categoryorder: 'array', categoryarray: categoryLabels,
    },
    yaxis: axisStyle(responseLabel),
  };

  if (chartType === 'mean') {
    const data = buildMeanTraces(activeSeries, ingredient, variable, responseLabel);
    return <Plot data={data} layout={baseLayout} style={{ width: '100%', height }} config={PLOTLY_CONFIG} />;
  }

  if (chartType === 'subjects') {
    const data = buildSubjectTraces(activeSeries, ingredient, variable, subjectColor, multiProtocol);
    const layout: Partial<Layout> = { ...baseLayout, xaxis: axisStyle(ingredientLabel) };
    return <Plot data={data} layout={layout} style={{ width: '100%', height }} config={PLOTLY_CONFIG} />;
  }

  // distribution
  const data = buildDistributionTraces(activeSeries, ingredient, variable);
  const layout: Partial<Layout> = { ...baseLayout, boxmode: 'group' };
  return <Plot data={data} layout={layout} style={{ width: '100%', height }} config={PLOTLY_CONFIG} />;
}
