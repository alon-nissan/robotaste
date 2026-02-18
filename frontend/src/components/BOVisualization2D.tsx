import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { BOModel2D, Sample } from '../types';

interface BOVisualization2DProps {
  sessionId: string;
}

const PRIMARY = '#521924';
const ACCENT = '#fda50f';

const PANEL_SIZE = 200;
const PAD = { top: 30, right: 10, bottom: 40, left: 40 };
const PLOT_W = PANEL_SIZE - PAD.left - PAD.right;
const PLOT_H = PANEL_SIZE - PAD.top - PAD.bottom;

// Color interpolation helpers
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
  return `#${[r, g, b].map((v) => clamp(v).toString(16).padStart(2, '0')).join('')}`;
}

function valueToColor(value: number, min: number, max: number, palette: 'viridis' | 'purple' | 'amber'): string {
  const t = max === min ? 0.5 : (value - min) / (max - min);

  if (palette === 'viridis') {
    // blue → green → yellow → red
    if (t < 0.33) {
      const s = t / 0.33;
      return rgbToHex(lerp(68, 49, s), lerp(1, 163, s), lerp(84, 84, s));
    } else if (t < 0.66) {
      const s = (t - 0.33) / 0.33;
      return rgbToHex(lerp(49, 253, s), lerp(163, 231, s), lerp(84, 37, s));
    } else {
      const s = (t - 0.66) / 0.34;
      return rgbToHex(lerp(253, 220, s), lerp(231, 50, s), lerp(37, 32, s));
    }
  }

  if (palette === 'purple') {
    return rgbToHex(lerp(248, 100, t), lerp(249, 40, t), lerp(250, 160, t));
  }

  // amber
  return rgbToHex(lerp(248, 253, t), lerp(249, 165, t), lerp(250, 15, t));
}

function StarMarker({ cx, cy, r, fill }: { cx: number; cy: number; r: number; fill: string }) {
  const points: string[] = [];
  for (let i = 0; i < 10; i++) {
    const angle = (Math.PI / 5) * i - Math.PI / 2;
    const radius = i % 2 === 0 ? r : r * 0.4;
    points.push(`${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`);
  }
  return <polygon points={points.join(' ')} fill={fill} stroke="#fff" strokeWidth={1.5} />;
}

function HeatmapPanel({
  title,
  grid,
  min,
  max,
  palette,
  xLabel,
  yLabel,
  xRange,
  yRange,
  observations,
  suggestion,
  showSuggestion,
}: {
  title: string;
  grid: number[][];
  min: number;
  max: number;
  palette: 'viridis' | 'purple' | 'amber';
  xLabel: string;
  yLabel: string;
  xRange: [number, number];
  yRange: [number, number];
  observations?: { x: number; y: number }[];
  suggestion?: { x: number; y: number };
  showSuggestion?: boolean;
}) {
  const rows = grid.length;
  const cols = rows > 0 ? grid[0].length : 0;
  const cellW = PLOT_W / cols;
  const cellH = PLOT_H / rows;

  const toSvgX = (val: number) =>
    xRange[1] === xRange[0]
      ? PAD.left + PLOT_W / 2
      : ((val - xRange[0]) / (xRange[1] - xRange[0])) * PLOT_W + PAD.left;
  const toSvgY = (val: number) =>
    yRange[1] === yRange[0]
      ? PAD.top + PLOT_H / 2
      : PLOT_H - ((val - yRange[0]) / (yRange[1] - yRange[0])) * PLOT_H + PAD.top;

  const xTicks = [xRange[0], (xRange[0] + xRange[1]) / 2, xRange[1]];
  const yTicks = [yRange[0], (yRange[0] + yRange[1]) / 2, yRange[1]];

  return (
    <div className="flex flex-col items-center">
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1">{title}</p>
      <svg viewBox={`0 0 ${PANEL_SIZE} ${PANEL_SIZE}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Heatmap cells — row 0 = top of grid */}
        {grid.map((row, ri) =>
          row.map((val, ci) => (
            <rect
              key={`${ri}-${ci}`}
              x={PAD.left + ci * cellW}
              y={PAD.top + ri * cellH}
              width={cellW + 0.5}
              height={cellH + 0.5}
              fill={valueToColor(val, min, max, palette)}
            />
          )),
        )}

        {/* Axes border */}
        <rect x={PAD.left} y={PAD.top} width={PLOT_W} height={PLOT_H} fill="none" stroke="#9ca3af" strokeWidth={0.5} />

        {/* X ticks */}
        {xTicks.map((v, i) => (
          <text key={`x-${i}`} x={toSvgX(v)} y={PANEL_SIZE - PAD.bottom + 16} textAnchor="middle" fontSize={9} fill="#6b7280">
            {v.toFixed(0)}
          </text>
        ))}

        {/* Y ticks */}
        {yTicks.map((v, i) => (
          <text key={`y-${i}`} x={PAD.left - 5} y={toSvgY(v)} textAnchor="end" dominantBaseline="central" fontSize={9} fill="#6b7280">
            {v.toFixed(0)}
          </text>
        ))}

        {/* Axis labels */}
        <text x={PAD.left + PLOT_W / 2} y={PANEL_SIZE - 4} textAnchor="middle" fontSize={10} fill="#6b7280">
          {xLabel}
        </text>
        <text
          x={10}
          y={PAD.top + PLOT_H / 2}
          textAnchor="middle"
          dominantBaseline="central"
          transform={`rotate(-90, 10, ${PAD.top + PLOT_H / 2})`}
          fontSize={10}
          fill="#6b7280"
        >
          {yLabel}
        </text>

        {/* Observation markers */}
        {observations?.map((obs, i) => (
          <circle key={`obs-${i}`} cx={toSvgX(obs.x)} cy={toSvgY(obs.y)} r={3.5} fill={PRIMARY} stroke="#fff" strokeWidth={1.5} />
        ))}

        {/* Suggestion star */}
        {showSuggestion && suggestion && (
          <StarMarker cx={toSvgX(suggestion.x)} cy={toSvgY(suggestion.y)} r={7} fill={ACCENT} />
        )}
      </svg>
    </div>
  );
}

export default function BOVisualization2D({ sessionId }: BOVisualization2DProps) {
  const [model, setModel] = useState<BOModel2D | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [modelRes, samplesRes] = await Promise.all([
        api.get(`/sessions/${sessionId}/bo-model`),
        api.get(`/sessions/${sessionId}/samples`),
      ]);
      setModel(modelRes.data);
      setSamples(samplesRes.data);
      setError(null);
    } catch (err) {
      setError('Failed to load BO model data');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="p-6 bg-surface rounded-xl border border-border">
        <p className="text-text-secondary text-center py-8">Loading BO model…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-surface rounded-xl border border-border">
        <p className="text-red-500 text-center py-8">{error}</p>
      </div>
    );
  }

  if (!model || samples.length < 3) {
    return (
      <div className="p-6 bg-surface rounded-xl border border-border">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
          Bayesian Optimization — 2D GP Model
        </h3>
        <p className="text-text-secondary text-center py-8">
          Need ≥3 samples for visualization.
        </p>
      </div>
    );
  }

  const { predictions, observations, suggestion, ingredient_names } = model;
  const { x: xVals, y: yVals, mean, std, acquisition } = predictions;

  const xRange: [number, number] = [Math.min(...xVals), Math.max(...xVals)];
  const yRange: [number, number] = [Math.min(...yVals), Math.max(...yVals)];

  // Flatten grids to get min/max for color scaling
  const flatMean = mean.flat();
  const flatStd = std.flat();
  const flatAcq = acquisition.flat();

  const obsPoints = observations.x.map((x, i) => ({ x, y: observations.y[i] }));
  const suggestionPoint = suggestion ? { x: suggestion.x, y: suggestion.y } : undefined;

  return (
    <div className="p-6 bg-surface rounded-xl border border-border">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
        Bayesian Optimization — 2D GP Model
      </h3>

      {/* Three-panel heatmap grid */}
      <div className="grid grid-cols-3 gap-4">
        <HeatmapPanel
          title="Mean Prediction"
          grid={mean}
          min={Math.min(...flatMean)}
          max={Math.max(...flatMean)}
          palette="viridis"
          xLabel={ingredient_names[0]}
          yLabel={ingredient_names[1]}
          xRange={xRange}
          yRange={yRange}
          observations={obsPoints}
        />
        <HeatmapPanel
          title="Uncertainty"
          grid={std}
          min={Math.min(...flatStd)}
          max={Math.max(...flatStd)}
          palette="purple"
          xLabel={ingredient_names[0]}
          yLabel={ingredient_names[1]}
          xRange={xRange}
          yRange={yRange}
        />
        <HeatmapPanel
          title="Acquisition"
          grid={acquisition}
          min={Math.min(...flatAcq)}
          max={Math.max(...flatAcq)}
          palette="amber"
          xLabel={ingredient_names[0]}
          yLabel={ingredient_names[1]}
          xRange={xRange}
          yRange={yRange}
          suggestion={suggestionPoint}
          showSuggestion
        />
      </div>

      {/* Observation table */}
      <div className="mt-6">
        <p className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Observations
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-text-secondary font-medium">Cycle</th>
                <th className="text-left py-2 px-3 text-text-secondary font-medium">{ingredient_names[0]}</th>
                <th className="text-left py-2 px-3 text-text-secondary font-medium">{ingredient_names[1]}</th>
                <th className="text-left py-2 px-3 text-text-secondary font-medium">Response</th>
              </tr>
            </thead>
            <tbody>
              {samples.map((s, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-2 px-3">{s.cycle_number}</td>
                  <td className="py-2 px-3">
                    {s.ingredient_concentration[ingredient_names[0]]?.toFixed(1) ?? '—'}
                  </td>
                  <td className="py-2 px-3">
                    {s.ingredient_concentration[ingredient_names[1]]?.toFixed(1) ?? '—'}
                  </td>
                  <td className="py-2 px-3 text-text-secondary">
                    {observations.z[i]?.toFixed(2) ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
