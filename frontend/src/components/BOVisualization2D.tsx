import { useEffect, useState, useCallback } from 'react';
import Plot from 'react-plotly.js';
import { api } from '../api/client';
import type { BOModel2D, Sample } from '../types';

interface BOVisualization2DProps {
  sessionId: string;
}

const PRIMARY = '#521924';
const ACCENT = '#fda50f';
const SURFACE_H = 320;

interface AcquisitionPanelProps {
  xVals: number[];
  yVals: number[];
  grid: number[][];
  min: number;
  max: number;
  xLabel: string;
  yLabel: string;
  xRange: [number, number];
  yRange: [number, number];
  observations: { x: number; y: number }[];
  suggestion?: { x: number; y: number };
  sessionId: string;
}

function AcquisitionPanel({
  xVals,
  yVals,
  grid,
  min,
  max,
  xLabel,
  yLabel,
  xRange,
  yRange,
  observations,
  suggestion,
  sessionId,
}: AcquisitionPanelProps) {
  const pathLabels = observations.map((_, i) => `C${i + 1}`);
  const yValsAsc = [...yVals].reverse();
  const gridAsc = [...grid].reverse();

  return (
    <Plot
      data={[
        {
          type: 'heatmap',
          x: xVals,
          y: yValsAsc,
          z: gridAsc,
          colorscale: [
            [0, '#f8f9fa'],
            [1, '#fda50f'],
          ],
          zmin: min,
          zmax: max,
          showscale: true,
          hovertemplate: `${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>Acquisition: %{z:.3f}<extra></extra>`,
          colorbar: {
            thickness: 15,
            len: 0.8,
            tickfont: { size: 10, color: '#6b7280' },
          },
        },
        {
          type: 'scatter',
          mode: 'lines+markers+text',
          x: observations.map((p) => p.x),
          y: observations.map((p) => p.y),
          text: pathLabels,
          textposition: 'top center',
          line: { color: PRIMARY, width: 3 },
          marker: { color: PRIMARY, size: 8, line: { color: '#ffffff', width: 1.5 } },
          hovertemplate: `Cycle %{text}<br>${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<extra></extra>`,
          showlegend: false,
        },
        ...(suggestion
          ? [
              {
                type: 'scatter',
                mode: 'markers',
                x: [suggestion.x],
                y: [suggestion.y],
                marker: {
                  color: ACCENT,
                  size: 12,
                  symbol: 'star',
                  line: { color: '#ffffff', width: 1.5 },
                },
                hovertemplate: `Next suggestion<br>${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<extra></extra>`,
                showlegend: false,
              },
            ]
          : []),
      ]}
      layout={{
        uirevision: sessionId,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 50, r: 10, t: 10, b: 40 },
        height: SURFACE_H,
        xaxis: {
          title: { text: xLabel, font: { size: 11, color: '#6b7280' } },
          gridcolor: '#E5E7EB',
          zerolinecolor: '#D1D5DB',
          range: xRange,
          tickfont: { size: 10, color: '#6b7280' },
        },
        yaxis: {
          title: { text: yLabel, font: { size: 11, color: '#6b7280' } },
          gridcolor: '#E5E7EB',
          zerolinecolor: '#D1D5DB',
          range: yRange,
          tickfont: { size: 10, color: '#6b7280' },
        },
      }}
      style={{ width: '100%', height: `${SURFACE_H}px` }}
      config={{ displayModeBar: false, responsive: true }}
    />
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
  sessionId: string;
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
  sessionId,
}: SurfacePanelProps) {
  const pathLabels = observations.map((_, i) => `C${i + 1}`);
  const yValsAsc = [...yVals].reverse();
  const meanAsc = [...mean].reverse();

  return (
    <Plot
      data={[
        {
          type: 'surface',
          x: xVals,
          y: yValsAsc,
          z: meanAsc,
          colorscale: 'Viridis',
          cmin: zMin,
          cmax: zMax,
          showscale: true,
          opacity: 0.9,
          contours: {
            z: { show: true, usecolormap: true, width: 1 },
          },
          hovertemplate: `${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>Predicted: %{z:.3f}<extra></extra>`,
          colorbar: {
            thickness: 15,
            len: 0.8,
            tickfont: { size: 10, color: '#6b7280' },
          },
        },
        {
          type: 'scatter3d',
          mode: 'lines+markers+text',
          x: observations.map((p) => p.x),
          y: observations.map((p) => p.y),
          z: observations.map((p) => p.z),
          text: pathLabels,
          textposition: 'top center',
          line: { color: PRIMARY, width: 8 },
          marker: { color: PRIMARY, size: 5, line: { color: '#ffffff', width: 2 } },
          hovertemplate: `Cycle %{text}<br>${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>Observed: %{z:.3f}<extra></extra>`,
          showlegend: false,
        },
        ...(suggestion
          ? [
              {
                type: 'scatter3d',
                mode: 'markers',
                x: [suggestion.x],
                y: [suggestion.y],
                z: [suggestion.z],
                marker: {
                  color: ACCENT,
                  size: 8,
                  symbol: 'diamond',
                  line: { color: '#ffffff', width: 1.5 },
                },
                hovertemplate: `Next suggestion<br>${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>Predicted: %{z:.3f}<extra></extra>`,
                showlegend: false,
              },
            ]
          : []),
      ]}
      layout={{
        uirevision: sessionId,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 0, r: 0, t: 10, b: 0 },
        height: SURFACE_H,
        scene: {
          xaxis: {
            title: { text: xLabel, font: { size: 11, color: '#6b7280' } },
            gridcolor: '#E5E7EB',
            zerolinecolor: '#D1D5DB',
            tickfont: { size: 10, color: '#6b7280' },
          },
          yaxis: {
            title: { text: yLabel, font: { size: 11, color: '#6b7280' } },
            gridcolor: '#E5E7EB',
            zerolinecolor: '#D1D5DB',
            tickfont: { size: 10, color: '#6b7280' },
          },
          zaxis: {
            title: { text: 'Response', font: { size: 11, color: '#6b7280' } },
            gridcolor: '#E5E7EB',
            zerolinecolor: '#D1D5DB',
            tickfont: { size: 10, color: '#6b7280' },
          },
          camera: { eye: { x: 1.35, y: 1.35, z: 0.85 } },
        },
      }}
      style={{ width: '100%', height: `${SURFACE_H}px` }}
      config={{ displayModeBar: false, responsive: true }}
    />
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
            sessionId={sessionId}
          />
        </div>

        <div className="rounded-lg border border-border bg-background p-4">
          <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
            Acquisition Heatmap + Search Trajectory
          </p>
          <AcquisitionPanel
            xVals={xVals}
            yVals={yVals}
            grid={acquisition}
            min={Math.min(...flatAcq)}
            max={Math.max(...flatAcq)}
            xLabel={ingredient_names[0]}
            yLabel={ingredient_names[1]}
            xRange={xRange}
            yRange={yRange}
            observations={obsPoints.map(({ x, y }) => ({ x, y }))}
            suggestion={suggestionPoint ? { x: suggestionPoint.x, y: suggestionPoint.y } : undefined}
            sessionId={sessionId}
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
          <span className="inline-block w-3 h-1 mr-1.5" style={{ backgroundColor: '#fda50f' }} />
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
