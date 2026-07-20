import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { BOModel2D, Sample } from '../types';

interface BOVisualization2DProps {
  sessionId: string;
}

const PRIMARY = '#521924';
const ACCENT = '#fda50f';

const ACQ_SIZE = 320;
const ACQ_PAD = { top: 30, right: 20, bottom: 48, left: 52 };
const ACQ_W = ACQ_SIZE - ACQ_PAD.left - ACQ_PAD.right;
const ACQ_H = ACQ_SIZE - ACQ_PAD.top - ACQ_PAD.bottom;
const SURFACE_W = 420;
const SURFACE_H = 320;

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
  return `#${[r, g, b].map((v) => clamp(v).toString(16).padStart(2, '0')).join('')}`;
}

function valueToColor(value: number, min: number, max: number, palette: 'viridis' | 'amber'): string {
  const t = max === min ? 0.5 : (value - min) / (max - min);

  if (palette === 'viridis') {
    if (t < 0.33) {
      const s = t / 0.33;
      return rgbToHex(lerp(68, 49, s), lerp(1, 163, s), lerp(84, 84, s));
    }
    if (t < 0.66) {
      const s = (t - 0.33) / 0.33;
      return rgbToHex(lerp(49, 253, s), lerp(163, 231, s), lerp(84, 37, s));
    }
    const s = (t - 0.66) / 0.34;
    return rgbToHex(lerp(253, 220, s), lerp(231, 50, s), lerp(37, 32, s));
  }

  return rgbToHex(lerp(248, 253, t), lerp(249, 165, t), lerp(250, 15, t));
}

function buildPath(points: { x: number; y: number }[]): string {
  if (!points.length) return '';
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
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

interface AcquisitionPanelProps {
  grid: number[][];
  min: number;
  max: number;
  xLabel: string;
  yLabel: string;
  xRange: [number, number];
  yRange: [number, number];
  observations: { x: number; y: number }[];
  suggestion?: { x: number; y: number };
}

function AcquisitionPanel({
  grid,
  min,
  max,
  xLabel,
  yLabel,
  xRange,
  yRange,
  observations,
  suggestion,
}: AcquisitionPanelProps) {
  const rows = grid.length;
  const cols = rows > 0 ? grid[0].length : 0;
  const cellW = ACQ_W / cols;
  const cellH = ACQ_H / rows;

  const toSvgX = (val: number) =>
    xRange[1] === xRange[0]
      ? ACQ_PAD.left + ACQ_W / 2
      : ((val - xRange[0]) / (xRange[1] - xRange[0])) * ACQ_W + ACQ_PAD.left;

  const toSvgY = (val: number) =>
    yRange[1] === yRange[0]
      ? ACQ_PAD.top + ACQ_H / 2
      : ACQ_H - ((val - yRange[0]) / (yRange[1] - yRange[0])) * ACQ_H + ACQ_PAD.top;

  const xTicks = [xRange[0], (xRange[0] + xRange[1]) / 2, xRange[1]];
  const yTicks = [yRange[0], (yRange[0] + yRange[1]) / 2, yRange[1]];
  const pathPoints = observations.map((obs) => ({ x: toSvgX(obs.x), y: toSvgY(obs.y) }));

  return (
    <svg viewBox={`0 0 ${ACQ_SIZE} ${ACQ_SIZE}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id="bo-path-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3.5" orient="auto">
          <polygon points="0 0, 7 3.5, 0 7" fill={PRIMARY} />
        </marker>
      </defs>

      {grid.map((row, ri) =>
        row.map((val, ci) => (
          <rect
            key={`${ri}-${ci}`}
            x={ACQ_PAD.left + ci * cellW}
            y={ACQ_PAD.top + ri * cellH}
            width={cellW + 0.5}
            height={cellH + 0.5}
            fill={valueToColor(val, min, max, 'amber')}
          />
        )),
      )}

      <rect x={ACQ_PAD.left} y={ACQ_PAD.top} width={ACQ_W} height={ACQ_H} fill="none" stroke="#9ca3af" strokeWidth={0.5} />

      {xTicks.map((v, i) => (
        <text key={`x-${i}`} x={toSvgX(v)} y={ACQ_SIZE - ACQ_PAD.bottom + 16} textAnchor="middle" fontSize={10} fill="#6b7280">
          {v.toFixed(0)}
        </text>
      ))}

      {yTicks.map((v, i) => (
        <text key={`y-${i}`} x={ACQ_PAD.left - 8} y={toSvgY(v)} textAnchor="end" dominantBaseline="central" fontSize={10} fill="#6b7280">
          {v.toFixed(0)}
        </text>
      ))}

      <text x={ACQ_PAD.left + ACQ_W / 2} y={ACQ_SIZE - 6} textAnchor="middle" fontSize={11} fill="#6b7280">
        {xLabel}
      </text>
      <text
        x={14}
        y={ACQ_PAD.top + ACQ_H / 2}
        textAnchor="middle"
        dominantBaseline="central"
        transform={`rotate(-90, 14, ${ACQ_PAD.top + ACQ_H / 2})`}
        fontSize={11}
        fill="#6b7280"
      >
        {yLabel}
      </text>

      {pathPoints.length > 1 && (
        <path d={buildPath(pathPoints)} fill="none" stroke={PRIMARY} strokeWidth={2.5} markerEnd="url(#bo-path-arrow)" />
      )}

      {pathPoints.map((point, i) => (
        <g key={`path-${i}`}>
          <circle cx={point.x} cy={point.y} r={4.5} fill={PRIMARY} stroke="#fff" strokeWidth={1.5} />
          <text x={point.x} y={point.y - 8} textAnchor="middle" fontSize={8} fill="#374151">
            C{i + 1}
          </text>
        </g>
      ))}

      {suggestion && <StarMarker cx={toSvgX(suggestion.x)} cy={toSvgY(suggestion.y)} r={7} fill={ACCENT} />}
    </svg>
  );
}

interface SurfacePanelProps {
  xVals: number[];
  yVals: number[];
  mean: number[][];
  zMin: number;
  zMax: number;
  xLabel: string;
  yLabel: string;
  observations: { x: number; y: number; z: number }[];
  suggestion?: { x: number; y: number; z: number };
}

function SurfacePanel({
  xVals,
  yVals,
  mean,
  zMin,
  zMax,
  xLabel,
  yLabel,
  observations,
  suggestion,
}: SurfacePanelProps) {
  const xMin = Math.min(...xVals);
  const xMax = Math.max(...xVals);
  const yMin = Math.min(...yVals);
  const yMax = Math.max(...yVals);

  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  const zSpan = zMax - zMin || 1;

  const centerX = SURFACE_W * 0.5;
  const baseY = SURFACE_H * 0.82;
  const xScale = 120;
  const yScale = 75;
  const zScale = 95;

  const project = (x: number, y: number, z: number) => {
    const nx = (x - xMin) / xSpan;
    const ny = (y - yMin) / ySpan;
    const nz = (z - zMin) / zSpan;

    return {
      x: centerX + (nx - ny) * xScale,
      y: baseY - (nx + ny) * yScale - nz * zScale,
    };
  };

  const quads: {
    key: string;
    points: string;
    fill: string;
    depth: number;
  }[] = [];

  for (let yi = 0; yi < yVals.length - 1; yi++) {
    for (let xi = 0; xi < xVals.length - 1; xi++) {
      const p1 = project(xVals[xi], yVals[yi], mean[yi][xi]);
      const p2 = project(xVals[xi + 1], yVals[yi], mean[yi][xi + 1]);
      const p3 = project(xVals[xi + 1], yVals[yi + 1], mean[yi + 1][xi + 1]);
      const p4 = project(xVals[xi], yVals[yi + 1], mean[yi + 1][xi]);
      const avgZ = (mean[yi][xi] + mean[yi][xi + 1] + mean[yi + 1][xi + 1] + mean[yi + 1][xi]) / 4;

      quads.push({
        key: `${yi}-${xi}`,
        points: `${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y} ${p4.x},${p4.y}`,
        fill: valueToColor(avgZ, zMin, zMax, 'viridis'),
        depth: yi + xi,
      });
    }
  }

  quads.sort((a, b) => a.depth - b.depth);
  const pathPoints = observations.map((obs) => project(obs.x, obs.y, obs.z));
  const suggestionPoint = suggestion ? project(suggestion.x, suggestion.y, suggestion.z) : null;

  return (
    <svg viewBox={`0 0 ${SURFACE_W} ${SURFACE_H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      <line x1={centerX - xScale} y1={baseY} x2={centerX + xScale} y2={baseY - yScale} stroke="#9ca3af" strokeWidth={1} />
      <line x1={centerX + xScale} y1={baseY - yScale} x2={centerX} y2={baseY - 2 * yScale} stroke="#9ca3af" strokeWidth={1} />
      <line x1={centerX - xScale} y1={baseY} x2={centerX} y2={baseY - 2 * yScale} stroke="#9ca3af" strokeWidth={1} />
      <line x1={centerX} y1={baseY - 2 * yScale} x2={centerX} y2={baseY - 2 * yScale - zScale * 0.85} stroke="#9ca3af" strokeWidth={1} />

      {quads.map((quad) => (
        <polygon key={quad.key} points={quad.points} fill={quad.fill} stroke="rgba(255,255,255,0.35)" strokeWidth={0.6} />
      ))}

      {pathPoints.length > 1 && (
        <path d={buildPath(pathPoints)} fill="none" stroke={PRIMARY} strokeWidth={2.5} />
      )}

      {pathPoints.map((point, i) => (
        <g key={`surface-point-${i}`}>
          <circle cx={point.x} cy={point.y} r={4.5} fill={PRIMARY} stroke="#fff" strokeWidth={1.5} />
          <text x={point.x} y={point.y - 8} textAnchor="middle" fontSize={8} fill="#374151">
            C{i + 1}
          </text>
        </g>
      ))}

      {suggestionPoint && <StarMarker cx={suggestionPoint.x} cy={suggestionPoint.y} r={8} fill={ACCENT} />}

      <text x={centerX - xScale - 8} y={baseY + 10} textAnchor="end" fontSize={11} fill="#6b7280">
        {xLabel}
      </text>
      <text x={centerX + xScale + 10} y={baseY - yScale - 3} textAnchor="start" fontSize={11} fill="#6b7280">
        {yLabel}
      </text>
      <text x={centerX + 8} y={baseY - 2 * yScale - zScale * 0.85 - 5} textAnchor="start" fontSize={11} fill="#6b7280">
        Response
      </text>
    </svg>
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
      setSamples(samplesRes.data.samples || []);
      setError(null);
    } catch {
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

  const flatMean = mean.flat();
  const flatStd = std.flat();
  const flatAcq = acquisition.flat();

  const obsPoints = observations.x.map((x, i) => ({ x, y: observations.y[i], z: observations.z[i] }));
  const suggestionPoint = suggestion
    ? { x: suggestion.x, y: suggestion.y, z: suggestion.predicted_value }
    : undefined;

  const zMin = Math.min(...flatMean, ...observations.z);
  const zMax = Math.max(...flatMean, ...observations.z);
  const latestObservation = obsPoints[obsPoints.length - 1];
  const latestValue = observations.z[observations.z.length - 1];
  const stdMean = flatStd.reduce((acc, value) => acc + value, 0) / (flatStd.length || 1);

  return (
    <div className="p-6 bg-surface rounded-xl border border-border">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
        Bayesian Optimization — 2D GP Model
      </h3>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        <div className="rounded-lg border border-border bg-background p-4">
          <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
            GP Mean Surface + Observed Path
          </p>
          <SurfacePanel
            xVals={xVals}
            yVals={yVals}
            mean={mean}
            zMin={zMin}
            zMax={zMax}
            xLabel={ingredient_names[0]}
            yLabel={ingredient_names[1]}
            observations={obsPoints}
            suggestion={suggestionPoint}
          />
        </div>

        <div className="rounded-lg border border-border bg-background p-4">
          <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
            Acquisition Heatmap + Search Trajectory
          </p>
          <AcquisitionPanel
            grid={acquisition}
            min={Math.min(...flatAcq)}
            max={Math.max(...flatAcq)}
            xLabel={ingredient_names[0]}
            yLabel={ingredient_names[1]}
            xRange={xRange}
            yRange={yRange}
            observations={obsPoints.map(({ x, y }) => ({ x, y }))}
            suggestion={suggestionPoint ? { x: suggestionPoint.x, y: suggestionPoint.y } : undefined}
          />
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
        <div className="rounded-lg border border-border bg-background px-4 py-3">
          <p className="text-xs uppercase tracking-wider text-text-secondary">Cycles observed</p>
          <p className="mt-1 font-semibold">{obsPoints.length}</p>
        </div>
        <div className="rounded-lg border border-border bg-background px-4 py-3">
          <p className="text-xs uppercase tracking-wider text-text-secondary">Latest response</p>
          <p className="mt-1 font-semibold">{latestValue?.toFixed(2) ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-background px-4 py-3">
          <p className="text-xs uppercase tracking-wider text-text-secondary">Mean uncertainty</p>
          <p className="mt-1 font-semibold">{stdMean.toFixed(3)}</p>
        </div>
      </div>

      <div className="mt-4 text-xs text-text-secondary">
        <span className="inline-flex items-center mr-4">
          <span className="inline-block w-2.5 h-2.5 rounded-full mr-1.5" style={{ backgroundColor: PRIMARY }} />
          Sample path (C1 → Cn)
        </span>
        <span className="inline-flex items-center mr-4">
          <span className="inline-block mr-1.5" style={{ color: ACCENT }}>★</span>
          BO suggestion
        </span>
        <span className="inline-flex items-center">
          <span className="inline-block w-3 h-1 mr-1.5" style={{ backgroundColor: '#f59e0b' }} />
          Acquisition intensity
        </span>
      </div>

      {latestObservation && (
        <div className="mt-4 text-xs text-text-secondary">
          Latest sampled point: {ingredient_names[0]}={latestObservation.x.toFixed(1)}, {ingredient_names[1]}=
          {latestObservation.y.toFixed(1)}
        </div>
      )}
    </div>
  );
}
