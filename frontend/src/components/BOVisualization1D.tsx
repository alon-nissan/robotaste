import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { BOModel, Sample } from '../types';

interface BOVisualization1DProps {
  sessionId: string;
}

const PRIMARY = '#521924';
const ACCENT = '#fda50f';

// GP chart layout
const GP_WIDTH = 600;
const GP_HEIGHT = 400;
const ACQ_WIDTH = 600;
const ACQ_HEIGHT = 150;
const PAD = { top: 30, right: 30, bottom: 50, left: 60 };
const CHART_W = GP_WIDTH - PAD.left - PAD.right;
const CHART_H = GP_HEIGHT - PAD.top - PAD.bottom;
const ACQ_CHART_H = ACQ_HEIGHT - PAD.top - PAD.bottom;

function scaleX(value: number, min: number, max: number): number {
  if (max === min) return PAD.left + CHART_W / 2;
  return ((value - min) / (max - min)) * CHART_W + PAD.left;
}

function scaleY(value: number, min: number, max: number, chartHeight: number): number {
  if (max === min) return PAD.top + chartHeight / 2;
  return chartHeight - ((value - min) / (max - min)) * chartHeight + PAD.top;
}

function buildPathD(xs: number[], ys: number[], xMin: number, xMax: number, yMin: number, yMax: number, chartHeight: number): string {
  return xs
    .map((x, i) => {
      const sx = scaleX(x, xMin, xMax);
      const sy = scaleY(ys[i], yMin, yMax, chartHeight);
      return `${i === 0 ? 'M' : 'L'}${sx},${sy}`;
    })
    .join(' ');
}

function StarMarker({ cx, cy, r, fill }: { cx: number; cy: number; r: number; fill: string }) {
  const points: string[] = [];
  for (let i = 0; i < 10; i++) {
    const angle = (Math.PI / 5) * i - Math.PI / 2;
    const radius = i % 2 === 0 ? r : r * 0.45;
    points.push(`${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`);
  }
  return <polygon points={points.join(' ')} fill={fill} stroke="#fff" strokeWidth={1} />;
}

function generateTicks(min: number, max: number, count: number): number[] {
  if (max === min) return [min];
  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, i) => min + step * i);
}

export default function BOVisualization1D({ sessionId }: BOVisualization1DProps) {
  const [model, setModel] = useState<BOModel | null>(null);
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
          Bayesian Optimization — GP Model
        </h3>
        <p className="text-text-secondary text-center py-8">
          No data yet — need at least 3 observations to visualize the GP model.
        </p>
      </div>
    );
  }

  const { predictions, observations, suggestion, ingredient_name } = model;
  const { x: predX, mean, std, acquisition } = predictions;
  const { x: obsX, y: obsY } = observations;

  // Compute axis ranges
  const allX = [...predX, ...obsX];
  const xMin = Math.min(...allX);
  const xMax = Math.max(...allX);

  const upper = mean.map((m, i) => m + 2 * std[i]);
  const lower = mean.map((m, i) => m - 2 * std[i]);
  const allY = [...mean, ...upper, ...lower, ...obsY];
  const yMin = Math.min(...allY);
  const yMax = Math.max(...allY);

  const acqMin = Math.min(...acquisition);
  const acqMax = Math.max(...acquisition);

  // Build SVG paths
  const meanPath = buildPathD(predX, mean, xMin, xMax, yMin, yMax, CHART_H);

  // Uncertainty band: upper forward, then lower reversed
  const upperPath = predX.map((x, i) => {
    const sx = scaleX(x, xMin, xMax);
    const sy = scaleY(upper[i], yMin, yMax, CHART_H);
    return `${i === 0 ? 'M' : 'L'}${sx},${sy}`;
  }).join(' ');
  const lowerPath = [...predX].reverse().map((x, i) => {
    const idx = predX.length - 1 - i;
    const sx = scaleX(x, xMin, xMax);
    const sy = scaleY(lower[idx], yMin, yMax, CHART_H);
    return `L${sx},${sy}`;
  }).join(' ');
  const bandPath = `${upperPath} ${lowerPath} Z`;

  // Acquisition path
  const acqPath = buildPathD(predX, acquisition, xMin, xMax, acqMin, acqMax, ACQ_CHART_H);

  // Find suggestion index for acquisition star
  const acqMaxIdx = acquisition.indexOf(Math.max(...acquisition));

  const xTicks = generateTicks(xMin, xMax, 6);
  const yTicks = generateTicks(yMin, yMax, 5);
  const acqTicks = generateTicks(acqMin, acqMax, 3);

  return (
    <div className="p-6 bg-surface rounded-xl border border-border">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
        Bayesian Optimization — GP Model
      </h3>

      {/* GP Mean + Uncertainty chart */}
      <svg viewBox={`0 0 ${GP_WIDTH} ${GP_HEIGHT}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Y-axis label */}
        <text
          x={15}
          y={PAD.top + CHART_H / 2}
          textAnchor="middle"
          dominantBaseline="central"
          transform={`rotate(-90, 15, ${PAD.top + CHART_H / 2})`}
          fontSize={12}
          fill="#6b7280"
        >
          Response
        </text>

        {/* Grid lines and Y ticks */}
        {yTicks.map((v) => {
          const sy = scaleY(v, yMin, yMax, CHART_H);
          return (
            <g key={`ytick-${v}`}>
              <line x1={PAD.left} y1={sy} x2={PAD.left + CHART_W} y2={sy} stroke="#e5e7eb" strokeWidth={0.5} />
              <text x={PAD.left - 8} y={sy} textAnchor="end" dominantBaseline="central" fontSize={11} fill="#6b7280">
                {v.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* X ticks */}
        {xTicks.map((v) => {
          const sx = scaleX(v, xMin, xMax);
          return (
            <g key={`xtick-${v}`}>
              <line x1={sx} y1={PAD.top} x2={sx} y2={PAD.top + CHART_H} stroke="#e5e7eb" strokeWidth={0.5} />
              <text x={sx} y={PAD.top + CHART_H + 18} textAnchor="middle" fontSize={11} fill="#6b7280">
                {v.toFixed(0)}
              </text>
            </g>
          );
        })}

        {/* X-axis label */}
        <text
          x={PAD.left + CHART_W / 2}
          y={GP_HEIGHT - 8}
          textAnchor="middle"
          fontSize={12}
          fill="#6b7280"
        >
          {ingredient_name} (mM)
        </text>

        {/* Axes */}
        <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={PAD.top + CHART_H} stroke="#9ca3af" strokeWidth={1} />
        <line x1={PAD.left} y1={PAD.top + CHART_H} x2={PAD.left + CHART_W} y2={PAD.top + CHART_H} stroke="#9ca3af" strokeWidth={1} />

        {/* Uncertainty band */}
        <path d={bandPath} fill={PRIMARY} opacity={0.15} />

        {/* GP mean line */}
        <path d={meanPath} fill="none" stroke={PRIMARY} strokeWidth={2} />

        {/* Observation points */}
        {obsX.map((x, i) => (
          <circle
            key={`obs-${i}`}
            cx={scaleX(x, xMin, xMax)}
            cy={scaleY(obsY[i], yMin, yMax, CHART_H)}
            r={5}
            fill={PRIMARY}
            stroke="#fff"
            strokeWidth={1.5}
          />
        ))}

        {/* Suggestion star */}
        {suggestion && (
          <StarMarker
            cx={scaleX(suggestion.x, xMin, xMax)}
            cy={scaleY(suggestion.predicted_value, yMin, yMax, CHART_H)}
            r={10}
            fill={ACCENT}
          />
        )}
      </svg>

      {/* Acquisition function chart */}
      <div className="mt-4">
        <p className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Acquisition Function (EI)
        </p>
        <svg viewBox={`0 0 ${ACQ_WIDTH} ${ACQ_HEIGHT}`} className="w-full" preserveAspectRatio="xMidYMid meet">
          {/* Y ticks */}
          {acqTicks.map((v) => {
            const sy = scaleY(v, acqMin, acqMax, ACQ_CHART_H);
            return (
              <g key={`acq-ytick-${v}`}>
                <line x1={PAD.left} y1={sy} x2={PAD.left + CHART_W} y2={sy} stroke="#e5e7eb" strokeWidth={0.5} />
                <text x={PAD.left - 8} y={sy} textAnchor="end" dominantBaseline="central" fontSize={10} fill="#6b7280">
                  {v.toFixed(2)}
                </text>
              </g>
            );
          })}

          {/* Axes */}
          <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={PAD.top + ACQ_CHART_H} stroke="#9ca3af" strokeWidth={1} />
          <line x1={PAD.left} y1={PAD.top + ACQ_CHART_H} x2={PAD.left + CHART_W} y2={PAD.top + ACQ_CHART_H} stroke="#9ca3af" strokeWidth={1} />

          {/* Acquisition line */}
          <path d={acqPath} fill="none" stroke={ACCENT} strokeWidth={2} />

          {/* Star at max acquisition */}
          {predX[acqMaxIdx] !== undefined && (
            <StarMarker
              cx={scaleX(predX[acqMaxIdx], xMin, xMax)}
              cy={scaleY(acquisition[acqMaxIdx], acqMin, acqMax, ACQ_CHART_H)}
              r={8}
              fill={ACCENT}
            />
          )}

          {/* X ticks */}
          {xTicks.map((v) => {
            const sx = scaleX(v, xMin, xMax);
            return (
              <text key={`acq-xtick-${v}`} x={sx} y={PAD.top + ACQ_CHART_H + 16} textAnchor="middle" fontSize={11} fill="#6b7280">
                {v.toFixed(0)}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
