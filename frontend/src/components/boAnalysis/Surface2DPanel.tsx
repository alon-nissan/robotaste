/**
 * Surface2DPanel — reusable Plotly 3D GP response surface for post-hoc BO
 * analysis (Compare / Mean / Replay in BOSurfacesTab).
 *
 * Adapted from the `SurfacePanel` in BOVisualization2D.tsx (the live BO
 * monitoring view): same mean-surface + colored-by-uncertainty convention,
 * generalized to (a) accept an arbitrary color grid (per-model σ for a
 * single participant, or between-subject σ for a mean surface) and (b)
 * render one or more observation "discovery route" paths, since Mean mode
 * overlays every participant's path on one surface.
 */

import Plot from 'react-plotly.js';

const PRIMARY = '#521924';
export const SURFACE_H = 340;

export interface ObservationPath {
  label: string;
  color: string;
  points: { x: number; y: number; z: number }[];
  /** Show "C1..Cn" step labels on the path. Off by default when there are
   *  multiple overlaid paths (Mean mode) to avoid clutter. */
  showStepLabels?: boolean;
}

interface Surface2DPanelProps {
  xVals: number[];
  yVals: number[];
  mean: number[][];
  colorGrid: number[][];
  colorLabel: string;
  colorMin?: number;
  colorMax?: number;
  colorscale?: string;
  xLabel: string;
  yLabel: string;
  zLabel?: string;
  paths: ObservationPath[];
  height?: number;
  uirevision: string;
}

export default function Surface2DPanel({
  xVals,
  yVals,
  mean,
  colorGrid,
  colorLabel,
  colorMin,
  colorMax,
  colorscale = 'YlOrRd',
  xLabel,
  yLabel,
  zLabel = 'Response',
  paths,
  height = SURFACE_H,
  uirevision,
}: Surface2DPanelProps) {
  // Grids are computed with y descending (row 0 = max y), matching the live
  // BOVisualization2D convention — reverse to ascending for Plotly's surface
  // trace, which expects y increasing along the array.
  const yValsAsc = [...yVals].reverse();
  const meanAsc = [...mean].reverse();
  const colorAsc = [...colorGrid].reverse();

  const flatColor = colorGrid.flat();
  const cmin = colorMin ?? Math.min(...flatColor);
  const cmax = colorMax ?? Math.max(...flatColor);

  return (
    <Plot
      data={[
        {
          type: 'surface',
          x: xVals,
          y: yValsAsc,
          z: meanAsc,
          surfacecolor: colorAsc,
          colorscale,
          cmin,
          cmax,
          showscale: true,
          opacity: 0.9,
          contours: { z: { show: true, usecolormap: true, width: 1 } },
          hovertemplate: `${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>${zLabel}: %{z:.3f}<br>${colorLabel}: %{surfacecolor:.3f}<extra></extra>`,
          colorbar: {
            title: { text: colorLabel, font: { size: 11, color: '#6b7280' } },
            thickness: 15,
            len: 0.8,
            tickfont: { size: 10, color: '#6b7280' },
          },
        },
        ...paths.map((path) => {
          const labels = path.points.map((_, i) => `C${i + 1}`);
          return {
            type: 'scatter3d' as const,
            mode: (path.showStepLabels ? 'lines+markers+text' : 'lines+markers') as
              | 'lines+markers+text'
              | 'lines+markers',
            name: path.label,
            x: path.points.map((p) => p.x),
            y: path.points.map((p) => p.y),
            z: path.points.map((p) => p.z),
            text: path.showStepLabels ? labels : undefined,
            textposition: 'top center' as const,
            line: { color: path.color, width: 6 },
            marker: { color: path.color, size: 4, line: { color: '#ffffff', width: 1.5 } },
            hovertemplate: `${path.label}<br>${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>Observed: %{z:.3f}<extra></extra>`,
            showlegend: paths.length > 1,
          };
        }),
      ]}
      layout={{
        uirevision,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 0, r: 0, t: 10, b: 0 },
        height,
        showlegend: paths.length > 1,
        legend: { x: 0, y: 1, font: { size: 10, color: '#6b7280' } },
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
            title: { text: zLabel, font: { size: 11, color: '#6b7280' } },
            gridcolor: '#E5E7EB',
            zerolinecolor: '#D1D5DB',
            tickfont: { size: 10, color: '#6b7280' },
          },
          camera: { eye: { x: 1.35, y: 1.35, z: 0.85 } },
        },
      }}
      style={{ width: '100%', height: `${height}px` }}
      config={{ displayModeBar: false, responsive: true }}
    />
  );
}

// ─── HEATMAP (generic) ──────────────────────────────────────────────────────
// 2D heatmap for any scalar grid over the same (x, y) axes — used for the
// Compare mode's "meanA − meanB" difference panel and the Mean mode's
// between-subject-disagreement panel.

interface HeatmapPanelProps {
  xVals: number[];
  yVals: number[];
  grid: number[][];
  xLabel: string;
  yLabel: string;
  colorLabel: string;
  /** Diverging colorscale centered at zero (e.g. a difference grid) vs a
   *  sequential one starting at the grid's own minimum (e.g. a σ grid). */
  diverging?: boolean;
  colorscale?: string;
  height?: number;
  uirevision: string;
}

export function HeatmapPanel({
  xVals,
  yVals,
  grid,
  xLabel,
  yLabel,
  colorLabel,
  diverging = false,
  colorscale,
  height = SURFACE_H,
  uirevision,
}: HeatmapPanelProps) {
  const yValsAsc = [...yVals].reverse();
  const gridAsc = [...grid].reverse();
  const flat = grid.flat();

  const zmin = diverging ? -Math.max(1e-9, ...flat.map((v) => Math.abs(v))) : Math.min(...flat);
  const zmax = diverging ? Math.max(1e-9, ...flat.map((v) => Math.abs(v))) : Math.max(...flat);

  return (
    <Plot
      data={[
        {
          type: 'heatmap',
          x: xVals,
          y: yValsAsc,
          z: gridAsc,
          colorscale: colorscale ?? (diverging ? 'RdBu' : 'YlOrRd'),
          zmid: diverging ? 0 : undefined,
          zmin,
          zmax,
          showscale: true,
          hovertemplate: `${xLabel}: %{x:.2f}<br>${yLabel}: %{y:.2f}<br>${colorLabel}: %{z:.3f}<extra></extra>`,
          colorbar: {
            title: { text: colorLabel, font: { size: 11, color: '#6b7280' } },
            thickness: 15,
            len: 0.8,
            tickfont: { size: 10, color: '#6b7280' },
          },
        },
      ]}
      layout={{
        uirevision,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 50, r: 10, t: 10, b: 40 },
        height,
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
      }}
      style={{ width: '100%', height: `${height}px` }}
      config={{ displayModeBar: false, responsive: true }}
    />
  );
}

/** Preset: diverging heatmap for a "meanA − meanB" difference grid. */
export function DifferenceHeatmap(props: {
  xVals: number[];
  yVals: number[];
  diff: number[][];
  xLabel: string;
  yLabel: string;
  height?: number;
  uirevision: string;
}) {
  return (
    <HeatmapPanel
      xVals={props.xVals}
      yVals={props.yVals}
      grid={props.diff}
      xLabel={props.xLabel}
      yLabel={props.yLabel}
      colorLabel="Δ mean"
      diverging
      height={props.height}
      uirevision={props.uirevision}
    />
  );
}

export { PRIMARY };
