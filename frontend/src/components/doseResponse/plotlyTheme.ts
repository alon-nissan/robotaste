/**
 * Shared Plotly styling for dose-response charts.
 *
 * Mirrors the layout/config conventions established in BOVisualization2D.tsx
 * (transparent backgrounds so the app's Tailwind chrome shows through, gray
 * axis/grid colors, `responsive: true`) but centralizes them here instead of
 * duplicating the objects per-chart.
 */

import type { Config, Layout } from 'plotly.js';

export const AXIS_FONT = { size: 11, color: '#6b7280' };
export const TICK_FONT = { size: 10, color: '#6b7280' };
export const GRID_COLOR = '#E5E7EB';
export const ZERO_LINE_COLOR = '#D1D5DB';

// Unlike BOVisualization2D (which disables the modebar entirely), dose-response
// charts keep it so users get Plotly's native "Download plot as PNG" button.
export const PLOTLY_CONFIG: Partial<Config> = {
  displayModeBar: true,
  displaylogo: false,
  responsive: true,
};

export const TRANSPARENT_LAYOUT: Partial<Layout> = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
};

export function axisStyle(title: string): Partial<Layout['xaxis']> {
  return {
    title: { text: title, font: AXIS_FONT },
    gridcolor: GRID_COLOR,
    zerolinecolor: ZERO_LINE_COLOR,
    tickfont: TICK_FONT,
  };
}

// Distinguishable palette for up to 10 protocols/series. Matches the palette
// style already used for per-subject colors in the analysis pages.
export const PROTOCOL_COLORS = [
  '#3D5A99', '#7B2D3E', '#2E7D32', '#E65100', '#6A1B9A',
  '#00695C', '#AD1457', '#283593', '#F57F17', '#004D40',
];

export function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
