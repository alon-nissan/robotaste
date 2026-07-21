/**
 * DoseResponseDashboardPage — Visualize dose-response curves from experiment data.
 *
 * Shows (via the shared doseResponse components, Plotly-backed):
 * - Mean ± SEM curve, individual subject curves, per-dose distribution, or a
 *   3D response surface for mixture protocols
 * - Multi-protocol comparison (overlaid, colored by protocol)
 * - Summary statistics table
 * - Filters for protocols, subjects, ingredient, and response variable
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';
import type { DoseResponseData } from '../types';
import DoseResponseChart, { type ProtocolSeries } from '../components/doseResponse/DoseResponseChart';
import ChartTypeSelector, { type DRChartType } from '../components/doseResponse/ChartTypeSelector';
import ProtocolMultiSelect from '../components/doseResponse/ProtocolMultiSelect';
import { PROTOCOL_COLORS } from '../components/doseResponse/plotlyTheme';

// ─── FORMATTERS ─────────────────────────────────────────────────────────────

/**
 * Format a concentration value for axis ticks and table cells.
 * Adapts decimal places to value magnitude so small values aren't truncated.
 * e.g. 0 → "0", 0.0003 → "0.0003", 1.5 → "1.50"
 */
function formatConc(val: number): string {
  if (val === 0) return '0';
  const abs = Math.abs(val);
  if (abs >= 1) return val.toFixed(2);
  const decimals = Math.max(2, -Math.floor(Math.log10(abs)) + 1);
  return val.toFixed(decimals);
}

// ─── COLOR PALETTE ──────────────────────────────────────────────────────────
// Distinguishable colors for up to 10 subjects
const SUBJECT_COLORS = [
  '#521924', '#2563eb', '#16a34a', '#ea580c', '#7c3aed',
  '#0891b2', '#be123c', '#4f46e5', '#ca8a04', '#0d9488',
];

// ─── COMPONENT ──────────────────────────────────────────────────────────────

export default function DoseResponseDashboardPage() {
  const navigate = useNavigate();

  // State
  const [data, setData] = useState<DoseResponseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedProtocols, setSelectedProtocols] = useState<Set<string>>(new Set());
  const [chartType, setChartType] = useState<DRChartType>('mean');
  const [selectedIngredient, setSelectedIngredient] = useState<string>('');
  const [ingredientX, setIngredientX] = useState<string>('');
  const [ingredientY, setIngredientY] = useState<string>('');
  const [selectedVariable, setSelectedVariable] = useState<string>('');
  const [selectedSubjects, setSelectedSubjects] = useState<Set<string>>(new Set());

  // Fetch once — this endpoint already returns every protocol's data in one payload,
  // so comparing protocols is done client-side; no protocol_id filter is sent.
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/analysis/dose-response');
      const d: DoseResponseData = res.data;
      setData(d);

      if (!selectedIngredient && d.ingredients.length > 0) setSelectedIngredient(d.ingredients[0]);
      if (!ingredientX && d.ingredients.length > 0) setIngredientX(d.ingredients[0]);
      if (!ingredientY && d.ingredients.length > 1) setIngredientY(d.ingredients[1]);
      if (!selectedVariable && d.response_variables.length > 0) setSelectedVariable(d.response_variables[0]);
      if (selectedProtocols.size === 0 && d.protocols.length > 0) {
        setSelectedProtocols(new Set(d.protocols.map(p => p.protocol_id)));
      }
      if (selectedSubjects.size === 0 && d.subjects.length > 0) {
        setSelectedSubjects(new Set(d.subjects.map(s => s.session_id)));
      }

      setError(null);
    } catch (err) {
      console.error('Error fetching dose-response data:', err);
      setError('Failed to load dose-response data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ─── DERIVED DATA ───────────────────────────────────────────────────────

  const sessionProtocol = useMemo(() => {
    const m = new Map<string, string>();
    data?.subjects.forEach(s => m.set(s.session_id, s.protocol_id));
    return m;
  }, [data]);

  const protocolColor = useCallback(
    (protocolId: string) => {
      const idx = data?.protocols.findIndex(p => p.protocol_id === protocolId) ?? -1;
      return PROTOCOL_COLORS[Math.max(idx, 0) % PROTOCOL_COLORS.length];
    },
    [data],
  );

  const visibleSubjects = useMemo(
    () => data?.subjects.filter(s => selectedProtocols.has(s.protocol_id)) ?? [],
    [data, selectedProtocols],
  );

  const subjectColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    data?.subjects.forEach((s, i) => { map[s.session_id] = SUBJECT_COLORS[i % SUBJECT_COLORS.length]; });
    return map;
  }, [data]);

  const filteredForChart = useMemo(() => {
    if (!data) return [];
    return data.data_points.filter(dp => {
      const pid = sessionProtocol.get(dp.session_id);
      if (!pid || !selectedProtocols.has(pid)) return false;
      return selectedSubjects.has(dp.session_id);
    });
  }, [data, sessionProtocol, selectedProtocols, selectedSubjects]);

  const series: ProtocolSeries[] = useMemo(() => {
    if (!data) return [];
    const byProtocol = new Map<string, typeof filteredForChart>();
    for (const dp of filteredForChart) {
      const pid = sessionProtocol.get(dp.session_id);
      if (!pid) continue;
      const arr = byProtocol.get(pid) ?? [];
      arr.push(dp);
      byProtocol.set(pid, arr);
    }
    return data.protocols
      .filter(p => selectedProtocols.has(p.protocol_id))
      .map(p => ({
        protocolId: p.protocol_id, label: p.name, color: protocolColor(p.protocol_id),
        points: byProtocol.get(p.protocol_id) ?? [],
      }));
  }, [data, filteredForChart, sessionProtocol, selectedProtocols, protocolColor]);

  // Aggregated mean curve with error bars — used for the Summary Statistics table
  const meanCurveData = useMemo(() => {
    if (!selectedIngredient || !selectedVariable) return [];
    const groups = new Map<number, number[]>();
    for (const dp of filteredForChart) {
      const c = dp.concentrations[selectedIngredient];
      const v = Number(dp.responses[selectedVariable]);
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
        return { concentration, mean, sem, std, n, min: Math.min(...vals), max: Math.max(...vals) };
      })
      .sort((a, b) => a.concentration - b.concentration);
  }, [filteredForChart, selectedIngredient, selectedVariable]);

  // ─── SUBJECT / PROTOCOL TOGGLES ─────────────────────────────────────────

  function toggleSubject(sessionId: string) {
    setSelectedSubjects(prev => {
      const next = new Set(prev);
      if (next.has(sessionId)) next.delete(sessionId);
      else next.add(sessionId);
      return next;
    });
  }

  function selectAllSubjects() {
    setSelectedSubjects(new Set(visibleSubjects.map(s => s.session_id)));
  }

  function clearAllSubjects() {
    setSelectedSubjects(new Set());
  }

  // ─── LOADING / ERROR ────────────────────────────────────────────────────

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-text-secondary text-lg">Loading dose-response data...</div>
        </div>
      </PageLayout>
    );
  }

  if (error && !data) {
    return (
      <PageLayout>
        <div className="p-6 bg-red-50 rounded-xl text-red-700">
          <h2 className="font-semibold mb-2">Error</h2>
          <p>{error}</p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 px-4 py-2 bg-primary text-white rounded-lg"
          >
            Back to Home
          </button>
        </div>
      </PageLayout>
    );
  }

  const hasData = data && data.data_points.length > 0;
  const allowSurface3d = (data?.ingredients.length ?? 0) >= 2;

  // Axis label strings derived from selected filters + ingredient units
  const xUnit = data?.ingredient_units?.[selectedIngredient] ?? 'mM';
  const xAxisLabel = selectedIngredient ? `${selectedIngredient} (${xUnit})` : 'Concentration';
  const yAxisLabel = selectedVariable
    ? selectedVariable.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) + ' (score)'
    : 'Response';
  const xUnitOf = (ing: string) => data?.ingredient_units?.[ing] ?? 'mM';

  // ─── RENDER ─────────────────────────────────────────────────────────────

  return (
    <PageLayout>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-light text-text-primary tracking-wide">
          Dose-Response Dashboard
        </h1>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 text-sm bg-surface text-text-primary rounded-lg border border-border hover:bg-gray-100 transition-colors"
        >
          Back to Home
        </button>
      </div>

      {!hasData ? (
        <div className="p-6 bg-surface rounded-xl border border-border">
          <div className="flex items-center justify-center h-48 text-text-secondary">
            <p>No experiment data available. Complete some sessions to see dose-response curves.</p>
          </div>
        </div>
      ) : (
        <>
          {/* ═══ FILTERS ROW ═══ */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Ingredient (X-axis)</label>
              <select
                value={selectedIngredient}
                onChange={e => setSelectedIngredient(e.target.value)}
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              >
                {data.ingredients.map(ing => (
                  <option key={ing} value={ing}>{ing}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Response Variable (Y-axis)</label>
              <select
                value={selectedVariable}
                onChange={e => setSelectedVariable(e.target.value)}
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              >
                {data.response_variables.map(v => (
                  <option key={v} value={v}>{v.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</option>
                ))}
              </select>
            </div>
          </div>

          {/* ═══ CHART ═══ */}
          <div className="p-6 bg-surface rounded-xl border border-border mb-6">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
                {chartType === 'surface3d' ? `${ingredientX} × ${ingredientY}` : `${yAxisLabel} vs. ${selectedIngredient}`}
              </h3>
              <ChartTypeSelector value={chartType} onChange={setChartType} allowSurface3d={allowSurface3d} />
            </div>

            {chartType === 'surface3d' && (
              <div className="grid grid-cols-2 gap-3 mb-4">
                <select value={ingredientX} onChange={e => setIngredientX(e.target.value)}
                  className="w-full p-2 text-sm border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary">
                  {data.ingredients.map(ing => <option key={ing} value={ing}>{ing} (X)</option>)}
                </select>
                <select value={ingredientY} onChange={e => setIngredientY(e.target.value)}
                  className="w-full p-2 text-sm border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary">
                  {data.ingredients.map(ing => <option key={ing} value={ing}>{ing} (Y)</option>)}
                </select>
              </div>
            )}

            <DoseResponseChart
              chartType={chartType}
              series={series}
              variable={selectedVariable}
              responseLabel={yAxisLabel}
              ingredient={selectedIngredient}
              ingredientLabel={xAxisLabel}
              ingredientX={ingredientX}
              ingredientXLabel={`${ingredientX} (${xUnitOf(ingredientX)})`}
              ingredientY={ingredientY}
              ingredientYLabel={`${ingredientY} (${xUnitOf(ingredientY)})`}
              subjectColor={sid => subjectColorMap[sid] ?? '#521924'}
              height={420}
            />
          </div>

          {/* ═══ BOTTOM ROW: Protocols + Subjects + Summary Stats ═══ */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Protocols + Subjects */}
            <div className="p-6 bg-surface rounded-xl border border-border flex flex-col gap-5">
              <div>
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">
                  Protocols (compare)
                </h3>
                <ProtocolMultiSelect
                  protocols={data.protocols}
                  selected={selectedProtocols}
                  onChange={setSelectedProtocols}
                  colorFor={protocolColor}
                />
              </div>

              <div>
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">
                  Subjects
                </h3>
                <div className="flex gap-2 mb-3">
                  <button
                    onClick={selectAllSubjects}
                    className="px-3 py-1 text-xs bg-primary text-white rounded-lg hover:bg-primary-light transition-colors"
                  >
                    Select All
                  </button>
                  <button
                    onClick={clearAllSubjects}
                    className="px-3 py-1 text-xs bg-surface text-text-primary rounded-lg border border-border hover:bg-gray-100 transition-colors"
                  >
                    Clear All
                  </button>
                </div>
                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {visibleSubjects.map(s => (
                    <label
                      key={s.session_id}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSubjects.has(s.session_id)}
                        onChange={() => toggleSubject(s.session_id)}
                        className="w-4 h-4 rounded accent-primary"
                      />
                      <span
                        className="w-3 h-3 rounded-full flex-shrink-0"
                        style={{ backgroundColor: subjectColorMap[s.session_id] }}
                      />
                      <span className="text-sm text-text-primary">
                        {s.subject_name || s.session_code}
                      </span>
                      <span className="text-xs text-text-secondary ml-auto">{s.session_code}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            {/* Summary Statistics Table */}
            <div className="lg:col-span-2 p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
                Summary Statistics {series.length > 1 ? '(all selected protocols combined)' : ''}
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left p-2 text-text-secondary font-medium">
                        {selectedIngredient ? `${selectedIngredient} (${xUnit})` : 'Concentration'}
                      </th>
                      <th className="text-right p-2 text-text-secondary font-medium">n</th>
                      <th className="text-right p-2 text-text-secondary font-medium">Mean</th>
                      <th className="text-right p-2 text-text-secondary font-medium">SD</th>
                      <th className="text-right p-2 text-text-secondary font-medium">SEM</th>
                      <th className="text-right p-2 text-text-secondary font-medium">Min</th>
                      <th className="text-right p-2 text-text-secondary font-medium">Max</th>
                    </tr>
                  </thead>
                  <tbody>
                    {meanCurveData.map((row, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="p-2 font-medium">{formatConc(row.concentration)}</td>
                        <td className="p-2 text-right">{row.n}</td>
                        <td className="p-2 text-right">{row.mean.toFixed(2)}</td>
                        <td className="p-2 text-right">{row.std.toFixed(2)}</td>
                        <td className="p-2 text-right">{row.sem.toFixed(2)}</td>
                        <td className="p-2 text-right">{row.min.toFixed(2)}</td>
                        <td className="p-2 text-right">{row.max.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {meanCurveData.length === 0 && (
                <div className="flex items-center justify-center h-24 text-text-secondary text-sm">
                  No aggregated data for the selected filters.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </PageLayout>
  );
}
