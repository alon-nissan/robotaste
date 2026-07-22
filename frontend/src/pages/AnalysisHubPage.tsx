/**
 * AnalysisHubPage — Unified analysis interface.
 *
 * Tabs (sidebar):
 *   1. Dashboard     — Per-protocol session / subject / sample counts
 *   2. Dose Response — Individual & mean dose-response curves + per-subject table
 *   3. BO Surfaces   — Post-hoc Bayesian Optimization analysis: compare participants'
 *                       response surfaces, view a mean surface, and replay a session's
 *                       GP model sample-by-sample
 *   4. Explorer      — Browse database tables
 *   5. Query Builder — Run SQL queries (SELECT by default; write ops in power mode)
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';
import type { DoseResponseData } from '../types';
import DoseResponseChart, { type ProtocolSeries } from '../components/doseResponse/DoseResponseChart';
import ChartTypeSelector, { type DRChartType } from '../components/doseResponse/ChartTypeSelector';
import ProtocolMultiSelect from '../components/doseResponse/ProtocolMultiSelect';
import { PROTOCOL_COLORS } from '../components/doseResponse/plotlyTheme';
import { groupStatsByConcentration } from '../components/doseResponse/stats';
import BOSurfacesTab from '../components/boAnalysis/BOSurfacesTab';

// ─── TYPES ──────────────────────────────────────────────────────────────────

interface DashboardProtocol {
  protocol_id: string; protocol_name: string;
  session_count: number; subject_count: number; sample_count: number;
}
interface DashboardData {
  protocols: DashboardProtocol[];
  totals: { sessions: number; subjects: number; samples: number };
}

interface TableMeta  { name: string; row_count: number; }
interface TableData  { table: string; columns: string[]; rows: Record<string, unknown>[]; total: number; page: number; page_size: number; }
interface QueryResult { columns: string[]; rows: Record<string, unknown>[]; row_count: number; is_write: boolean; }

// ─── HELPERS ────────────────────────────────────────────────────────────────


// ─── CHART STYLE ─────────────────────────────────────────────────────────────
// Matches the reference matplotlib palette from scripts/generate_rebm_plots.py

const CS = {
  blue:        '#3D5A99',
  blueLight:   '#A8B8D8',
  maroon:      '#7B2D3E',
  bg:          '#F8F9FC',
  grid:        '#DDE1EC',
  titleColor:  '#2D3A5C',
  axisColor:   '#4A5568',
};

function fmtConc(val: number): string {
  if (val === 0) return '0';
  if (val < 0.1) return val.toFixed(3);
  return val.toFixed(2);
}

const SUBJECT_COLORS = [
  CS.blue, CS.maroon, '#2E7D32', '#E65100', '#6A1B9A',
  '#00695C', '#AD1457', '#283593', '#F57F17', '#004D40',
];

async function downloadExcel(request: Promise<{ data: Blob }>, filename: string) {
  const res = await request;
  const url = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── TAB DEFINITIONS ────────────────────────────────────────────────────────

type TabId = 'dashboard' | 'dose-response' | 'bo-surfaces' | 'explorer' | 'query-builder';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'dashboard',      label: 'Dashboard',     icon: '📊' },
  { id: 'dose-response',  label: 'Dose Response',  icon: '📈' },
  { id: 'bo-surfaces',    label: 'BO Surfaces',    icon: '🧠' },
  { id: 'explorer',       label: 'Explorer',       icon: '🗂️' },
  { id: 'query-builder',  label: 'Query Builder',  icon: '⌨️'  },
];

// ═══════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

export default function AnalysisHubPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialTab = (searchParams.get('tab') as TabId) ?? 'dashboard';
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);

  function switchTab(id: TabId) {
    setActiveTab(id);
    setSearchParams({ tab: id });
  }

  return (
    <PageLayout>
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-light text-text-primary tracking-wide">Analysis Hub</h1>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 text-sm bg-surface text-text-primary rounded-lg border border-border hover:bg-gray-100 transition-colors"
        >
          ← Back to Home
        </button>
      </div>

      {/* ── Layout: Sidebar + Content ── */}
      <div className="flex gap-6 min-h-[600px]">

        {/* Sidebar */}
        <aside className="w-48 shrink-0">
          <nav className="space-y-1">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => switchTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors text-left ${
                  activeTab === tab.id
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-text-secondary hover:bg-surface hover:text-text-primary'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* Content panel */}
        <div className="flex-1 min-w-0">
          {activeTab === 'dashboard'     && <DashboardTab />}
          {activeTab === 'dose-response' && <DoseResponseTab />}
          {activeTab === 'bo-surfaces'   && <BOSurfacesTab />}
          {activeTab === 'explorer'      && <ExplorerTab />}
          {activeTab === 'query-builder' && <QueryBuilderTab />}
        </div>
      </div>
    </PageLayout>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB: DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════

function DashboardTab() {
  const [data, setData]         = useState<DashboardData | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [exportProtocol, setExportProtocol] = useState('');
  const [exporting, setExporting]           = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get('/analysis/dashboard')
      .then(r => { setData(r.data); setError(null); })
      .catch(() => setError('Failed to load dashboard statistics.'))
      .finally(() => setLoading(false));
  }, []);

  async function handleExport() {
    setExporting(true);
    try {
      const params: Record<string, string> = {};
      if (exportProtocol) params.protocol_id = exportProtocol;
      await downloadExcel(
        api.get('/analysis/export/samples', { params, responseType: 'blob' }),
        'samples_export.xlsx',
      );
    } catch {
      // silent — browser will not navigate on blob error
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <LoadingState text="Loading dashboard…" />;
  if (error)   return <ErrorState text={error} />;
  if (!data)   return null;

  const { protocols, totals } = data;

  return (
    <div>
      {/* Totals row */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Sessions" value={totals.sessions} />
        <StatCard label="Unique Subjects" value={totals.subjects} />
        <StatCard label="Total Samples" value={totals.samples} />
      </div>

      {/* Per-protocol table */}
      <div className="p-6 bg-surface rounded-xl border border-border mb-6">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
          Statistics by Protocol
        </h2>
        {protocols.length === 0 ? (
          <p className="text-text-secondary text-sm py-8 text-center">No experiment data yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-2 text-text-secondary font-medium">Protocol</th>
                  <th className="text-right p-2 text-text-secondary font-medium">Sessions</th>
                  <th className="text-right p-2 text-text-secondary font-medium">Subjects</th>
                  <th className="text-right p-2 text-text-secondary font-medium">Samples</th>
                </tr>
              </thead>
              <tbody>
                {protocols.map((p, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-gray-50">
                    <td className="p-2 font-medium">{p.protocol_name}</td>
                    <td className="p-2 text-right">{p.session_count}</td>
                    <td className="p-2 text-right">{p.subject_count}</td>
                    <td className="p-2 text-right">{p.sample_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Export card */}
      <div className="p-6 bg-surface rounded-xl border border-border">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-1">
          Export Sample Data
        </h2>
        <p className="text-xs text-text-secondary mb-4">
          Downloads an Excel file with one row per sample: sample&nbsp;ID · participant · cycle ·
          per-ingredient concentrations · temperature · questionnaire ratings · timestamp.
          Columns are discovered from the selected protocol's data.
        </p>
        <div className="flex items-center gap-3">
          <select
            value={exportProtocol}
            onChange={e => setExportProtocol(e.target.value)}
            className="p-2 border border-border rounded-lg bg-white text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="">All Protocols</option>
            {protocols.map(p => (
              <option key={p.protocol_id} value={p.protocol_id}>{p.protocol_name}</option>
            ))}
          </select>
          <button
            onClick={handleExport}
            disabled={exporting}
            aria-label="Download sample data as Excel"
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              exporting
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-primary text-white hover:bg-primary-light'
            }`}
          >
            {exporting ? 'Preparing…' : '↓ Download .xlsx'}
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="p-5 bg-surface rounded-xl border border-border text-center">
      <div className="text-3xl font-bold text-primary">{value}</div>
      <div className="text-sm text-text-secondary mt-1">{label}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB: DOSE RESPONSE
// ═══════════════════════════════════════════════════════════════════════════

function DoseResponseTab() {
  const [data, setData]                   = useState<DoseResponseData | null>(null);
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState<string | null>(null);
  const [selectedProtocols, setSelectedProtocols] = useState<Set<string>>(new Set());
  const [chartType, setChartType]         = useState<DRChartType>('mean');
  const [selectedIngredient, setSelectedIngredient] = useState('');
  const [ingredientX, setIngredientX]     = useState('');
  const [ingredientY, setIngredientY]     = useState('');
  const [selectedVariable, setSelectedVariable]     = useState('');
  const [selectedSubjects, setSelectedSubjects]     = useState<Set<string>>(new Set());
  const [selectedTemps, setSelectedTemps]           = useState<Set<string>>(new Set());
  const [cycleMin, setCycleMin]                     = useState<number | null>(null);
  const [cycleMax, setCycleMax]                     = useState<number | null>(null);
  const [dateFrom, setDateFrom]                     = useState('');
  const [dateTo, setDateTo]                         = useState('');

  // Fetch once — the endpoint already returns every protocol's data in one payload
  // (each subject/session carries its own protocol_id), so protocol comparison is
  // done entirely client-side; no protocol_id query param is sent.
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/analysis/dose-response');
      const d: DoseResponseData = res.data;
      setData(d);
      if (!selectedIngredient && d.ingredients.length > 0) setSelectedIngredient(d.ingredients[0]);
      if (!ingredientX && d.ingredients.length > 0) setIngredientX(d.ingredients[0]);
      if (!ingredientY && d.ingredients.length > 1) setIngredientY(d.ingredients[1]);
      if (!selectedVariable  && d.response_variables.length > 0) setSelectedVariable(d.response_variables[0]);
      if (selectedProtocols.size === 0 && d.protocols.length > 0)
        setSelectedProtocols(new Set(d.protocols.map(p => p.protocol_id)));
      if (selectedSubjects.size === 0 && d.subjects.length > 0)
        setSelectedSubjects(new Set(d.subjects.map(s => s.session_id)));
      setError(null);
    } catch {
      setError('Failed to load dose-response data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Derived data ──

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
    const m: Record<string, string> = {};
    data?.subjects.forEach((s, i) => { m[s.session_id] = SUBJECT_COLORS[i % SUBJECT_COLORS.length]; });
    return m;
  }, [data]);

  const filteredForChart = useMemo(() => {
    if (!data) return [];
    return data.data_points.filter(dp => {
      const pid = sessionProtocol.get(dp.session_id);
      if (!pid || !selectedProtocols.has(pid)) return false;
      if (!selectedSubjects.has(dp.session_id)) return false;
      if (selectedTemps.size > 0) {
        const t = dp.sample_temperature_c == null ? '' : String(dp.sample_temperature_c);
        if (!selectedTemps.has(t)) return false;
      }
      if (cycleMin != null && dp.cycle_number < cycleMin) return false;
      if (cycleMax != null && dp.cycle_number > cycleMax) return false;
      if (dateFrom && dp.created_at && dp.created_at < dateFrom) return false;
      if (dateTo && dp.created_at && dp.created_at > dateTo + 'T23:59:59') return false;
      return true;
    });
  }, [data, sessionProtocol, selectedProtocols, selectedSubjects, selectedTemps, cycleMin, cycleMax, dateFrom, dateTo]);

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

  // Summary stats: one group of rows per selected protocol (not merged), so two
  // protocols can be compared directly — mirrors the per-protocol chart series.
  const meanCurveData = useMemo(() => {
    if (!selectedIngredient || !selectedVariable) return [];
    return series.flatMap(s =>
      groupStatsByConcentration(s.points, selectedIngredient, selectedVariable)
        .map(row => ({ ...row, protocolId: s.protocolId, protocolLabel: s.label, protocolColor: s.color })),
    );
  }, [series, selectedIngredient, selectedVariable]);

  // Per-subject raw data table (all data points for selected filters), tagged with
  // each row's protocol so it's readable alongside the per-protocol summary table.
  const perSubjectRows = useMemo(() => {
    if (!data || !selectedIngredient || !selectedVariable) return [];
    return filteredForChart
      .filter(dp => dp.concentrations[selectedIngredient] !== undefined && dp.responses[selectedVariable] !== undefined)
      .map(dp => {
        const pid = sessionProtocol.get(dp.session_id);
        return {
          subject:       dp.subject_name || dp.session_code,
          session_code:  dp.session_code,
          cycle:         dp.cycle_number,
          concentration: dp.concentrations[selectedIngredient],
          response:      dp.responses[selectedVariable],
          protocolLabel: (pid && data.protocols.find(p => p.protocol_id === pid)?.name) || '—',
          protocolColor: pid ? protocolColor(pid) : '#9ca3af',
        };
      })
      .sort((a, b) => a.protocolLabel.localeCompare(b.protocolLabel) || a.subject.localeCompare(b.subject) || a.concentration - b.concentration);
  }, [data, filteredForChart, selectedIngredient, selectedVariable, sessionProtocol, protocolColor]);

  function toggleSubject(id: string) {
    setSelectedSubjects(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const xUnit    = data?.ingredient_units?.[selectedIngredient] ?? 'mM';
  const xLabel   = selectedIngredient ? `${selectedIngredient} (${xUnit})` : 'Concentration';
  const yLabel   = selectedVariable
    ? selectedVariable.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + ' score'
    : 'Response score';
  const xUnitOf = (ing: string) => data?.ingredient_units?.[ing] ?? 'mM';

  if (loading) return <LoadingState text="Loading dose-response data…" />;
  if (error && !data) return <ErrorState text={error} />;

  const hasData = data && data.data_points.length > 0;
  const allowSurface3d = (data?.ingredients.length ?? 0) >= 2;

  return (
    <div>
      {!hasData ? (
        <div className="p-6 bg-surface rounded-xl border border-border flex items-center justify-center h-48 text-text-secondary text-sm">
          No experiment data available. Complete some sessions to see dose-response curves.
        </div>
      ) : (
        <>
          {/* Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Ingredient (X-axis)</label>
              <select value={selectedIngredient} onChange={e => setSelectedIngredient(e.target.value)}
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary">
                {data.ingredients.map(ing => <option key={ing} value={ing}>{ing}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Response Variable (Y-axis)</label>
              <select value={selectedVariable} onChange={e => setSelectedVariable(e.target.value)}
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary">
                {data.response_variables.map(v => (
                  <option key={v} value={v}>{v.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Chart + Filters */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Chart — 2/3 width */}
            <div className="lg:col-span-2 p-6 rounded-xl border border-border" style={{ backgroundColor: CS.bg }}>
              <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: CS.titleColor }}>
                  {yLabel} vs. {chartType === 'surface3d' ? `${ingredientX} × ${ingredientY}` : selectedIngredient}
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
                responseLabel={yLabel}
                ingredient={selectedIngredient}
                ingredientLabel={xLabel}
                ingredientX={ingredientX}
                ingredientXLabel={`${ingredientX} (${xUnitOf(ingredientX)})`}
                ingredientY={ingredientY}
                ingredientYLabel={`${ingredientY} (${xUnitOf(ingredientY)})`}
                subjectColor={sid => subjectColorMap[sid] ?? CS.blue}
                height={420}
              />
            </div>

            {/* Filters card — 1/3 width */}
            <div className="p-6 bg-surface rounded-xl border border-border flex flex-col gap-5 overflow-y-auto">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Filters</h3>
                <button
                  onClick={() => {
                    setSelectedProtocols(new Set(data.protocols.map(p => p.protocol_id)));
                    setSelectedSubjects(new Set(data.subjects.map(s => s.session_id)));
                    setSelectedTemps(new Set());
                    setCycleMin(null);
                    setCycleMax(null);
                    setDateFrom('');
                    setDateTo('');
                  }}
                  className="text-xs px-2 py-1 rounded border border-border text-text-secondary hover:bg-gray-100 transition-colors">
                  Reset
                </button>
              </div>

              {/* Protocols */}
              <div>
                <div className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">
                  Protocols (compare)
                </div>
                <ProtocolMultiSelect
                  protocols={data.protocols}
                  selected={selectedProtocols}
                  onChange={setSelectedProtocols}
                  colorFor={protocolColor}
                />
              </div>

              {/* Subjects */}
              <div>
                <div className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">Subjects</div>
                <div className="flex gap-2 mb-2">
                  <button onClick={() => setSelectedSubjects(new Set(visibleSubjects.map(s => s.session_id)))}
                    className="px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary-light transition-colors">
                    All
                  </button>
                  <button onClick={() => setSelectedSubjects(new Set())}
                    className="px-2 py-1 text-xs bg-surface text-text-primary rounded border border-border hover:bg-gray-100 transition-colors">
                    None
                  </button>
                </div>
                <div className="space-y-1 max-h-[160px] overflow-y-auto">
                  {visibleSubjects.map(s => (
                    <label key={s.session_id} className="flex items-center gap-2 py-1 px-1 rounded hover:bg-gray-50 cursor-pointer">
                      <input type="checkbox" checked={selectedSubjects.has(s.session_id)}
                        onChange={() => toggleSubject(s.session_id)} className="w-4 h-4 rounded accent-primary" />
                      <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: subjectColorMap[s.session_id] }} />
                      <span className="text-sm text-text-primary truncate">{s.subject_name || s.session_code}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Temperature */}
              {data.sample_temperatures_c && data.sample_temperatures_c.length > 1 && (
                <div>
                  <div className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">Temperature</div>
                  <div className="space-y-1">
                    {data.sample_temperatures_c.map(t => {
                      const key = String(t);
                      return (
                        <label key={key} className="flex items-center gap-2 py-1 cursor-pointer">
                          <input type="checkbox"
                            checked={selectedTemps.size === 0 || selectedTemps.has(key)}
                            onChange={() => {
                              setSelectedTemps(prev => {
                                const allKeys = new Set((data.sample_temperatures_c ?? []).map(String));
                                if (prev.size === 0) {
                                  const next = new Set(allKeys);
                                  next.delete(key);
                                  return next;
                                }
                                const next = new Set(prev);
                                next.has(key) ? next.delete(key) : next.add(key);
                                if (next.size === allKeys.size) return new Set<string>();
                                return next;
                              });
                            }}
                            className="w-4 h-4 rounded accent-primary" />
                          <span className="text-sm text-text-primary">{t.toFixed(1)} °C</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Cycle range */}
              <div>
                <div className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">Cycle Range</div>
                <div className="flex gap-2 items-center">
                  <input type="number" min={1} placeholder="Min"
                    value={cycleMin ?? ''}
                    onChange={e => setCycleMin(e.target.value ? Number(e.target.value) : null)}
                    className="w-full p-2 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary" />
                  <span className="text-text-secondary text-sm flex-shrink-0">–</span>
                  <input type="number" min={1} placeholder="Max"
                    value={cycleMax ?? ''}
                    onChange={e => setCycleMax(e.target.value ? Number(e.target.value) : null)}
                    className="w-full p-2 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary" />
                </div>
              </div>

              {/* Date range */}
              <div>
                <div className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">Date Range</div>
                <div className="flex flex-col gap-2">
                  <input type="date"
                    value={dateFrom}
                    onChange={e => setDateFrom(e.target.value)}
                    className="w-full p-2 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary" />
                  <input type="date"
                    value={dateTo}
                    onChange={e => setDateTo(e.target.value)}
                    className="w-full p-2 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary" />
                </div>
              </div>
            </div>
          </div>

          {/* Summary stats */}
          <div className="p-6 bg-surface rounded-xl border border-border mb-6">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
              Summary Statistics
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left p-2 text-text-secondary font-medium">Protocol</th>
                    <th className="text-left p-2 text-text-secondary font-medium">{xLabel}</th>
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
                      <td className="p-2">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: row.protocolColor }} />
                          {row.protocolLabel}
                        </span>
                      </td>
                      <td className="p-2 font-medium">{fmtConc(row.concentration)}</td>
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
              {meanCurveData.length === 0 && (
                <p className="text-center text-text-secondary text-sm py-6">No data for the selected filters.</p>
              )}
            </div>
          </div>

          {/* Per-subject raw data table */}
          <div className="p-6 bg-surface rounded-xl border border-border">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
              Per-Subject Data Points
            </h3>
            <div className="overflow-x-auto max-h-72 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-border">
                    <th className="text-left p-2 text-text-secondary font-medium">Protocol</th>
                    <th className="text-left p-2 text-text-secondary font-medium">Subject</th>
                    <th className="text-left p-2 text-text-secondary font-medium">Session</th>
                    <th className="text-right p-2 text-text-secondary font-medium">Cycle</th>
                    <th className="text-right p-2 text-text-secondary font-medium">{xLabel}</th>
                    <th className="text-right p-2 text-text-secondary font-medium">{yLabel}</th>
                  </tr>
                </thead>
                <tbody>
                  {perSubjectRows.map((row, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-gray-50">
                      <td className="p-2">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: row.protocolColor }} />
                          {row.protocolLabel}
                        </span>
                      </td>
                      <td className="p-2">{row.subject}</td>
                      <td className="p-2 font-mono text-xs text-text-secondary">{row.session_code}</td>
                      <td className="p-2 text-right">{row.cycle}</td>
                      <td className="p-2 text-right">{fmtConc(row.concentration)}</td>
                      <td className="p-2 text-right">{typeof row.response === 'number' ? row.response.toFixed(2) : row.response}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {perSubjectRows.length === 0 && (
                <p className="text-center text-text-secondary text-sm py-6">No data for the selected filters.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB: EXPLORER
// ═══════════════════════════════════════════════════════════════════════════

function ExplorerTab() {
  const [tables, setTables]             = useState<TableMeta[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableData, setTableData]       = useState<TableData | null>(null);
  const [page, setPage]                 = useState(0);
  const [loadingTables, setLoadingTables] = useState(true);
  const [loadingData, setLoadingData]   = useState(false);
  const [error, setError]               = useState<string | null>(null);

  useEffect(() => {
    api.get('/analysis/explorer/tables')
      .then(r => { setTables(r.data.tables); setError(null); })
      .catch(() => setError('Failed to load table list.'))
      .finally(() => setLoadingTables(false));
  }, []);

  const loadTableData = useCallback((name: string, p = 0) => {
    setLoadingData(true);
    setError(null);
    api.get(`/analysis/explorer/table/${name}`, { params: { page: p, page_size: 50 } })
      .then(r => { setTableData(r.data); setPage(p); })
      .catch(() => setError(`Failed to load data for table "${name}".`))
      .finally(() => setLoadingData(false));
  }, []);

  function handleSelectTable(name: string) {
    setSelectedTable(name);
    setTableData(null);
    loadTableData(name, 0);
  }

  const totalPages = tableData ? Math.ceil(tableData.total / tableData.page_size) : 0;

  return (
    <div className="flex gap-4 h-full">
      {/* Table list */}
      <div className="w-44 shrink-0 p-4 bg-surface rounded-xl border border-border">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">Tables</h3>
        {loadingTables ? (
          <p className="text-sm text-text-secondary">Loading…</p>
        ) : (
          <ul className="space-y-1">
            {tables.map(t => (
              <li key={t.name}>
                <button
                  onClick={() => handleSelectTable(t.name)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    selectedTable === t.name
                      ? 'bg-primary text-white'
                      : 'text-text-primary hover:bg-gray-100'
                  }`}
                >
                  <div className="font-medium truncate">{t.name}</div>
                  <div className={`text-xs ${selectedTable === t.name ? 'text-white/70' : 'text-text-secondary'}`}>
                    {t.row_count.toLocaleString()} rows
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Table data */}
      <div className="flex-1 min-w-0 p-4 bg-surface rounded-xl border border-border">
        {!selectedTable ? (
          <div className="flex items-center justify-center h-48 text-text-secondary text-sm">
            Select a table from the list to browse its data.
          </div>
        ) : loadingData ? (
          <LoadingState text={`Loading ${selectedTable}…`} />
        ) : error ? (
          <ErrorState text={error} />
        ) : tableData ? (
          <>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-text-primary">{tableData.table}</h3>
              <span className="text-xs text-text-secondary">
                {tableData.total.toLocaleString()} rows · page {page + 1} of {totalPages}
              </span>
            </div>
            <div className="overflow-auto max-h-[calc(100vh-300px)]">
              <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 bg-surface z-10">
                  <tr>
                    {tableData.columns.map(col => (
                      <th key={col} className="text-left p-2 border-b border-border font-semibold text-text-secondary whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.rows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50 border-b border-border/30">
                      {tableData.columns.map(col => {
                        const val = row[col];
                        const display = val === null ? <span className="text-text-secondary italic">null</span>
                          : typeof val === 'string' && val.length > 60 ? `${val.slice(0, 60)}…`
                          : String(val);
                        return (
                          <td key={col} className="p-2 whitespace-nowrap max-w-[200px] truncate" title={String(val ?? '')}>
                            {display}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center gap-2 mt-3">
                <button disabled={page === 0}
                  onClick={() => loadTableData(selectedTable, page - 1)}
                  className="px-3 py-1 text-xs rounded border border-border disabled:opacity-40 hover:bg-gray-100 transition-colors">
                  ← Prev
                </button>
                <span className="text-xs text-text-secondary">Page {page + 1} / {totalPages}</span>
                <button disabled={page >= totalPages - 1}
                  onClick={() => loadTableData(selectedTable, page + 1)}
                  className="px-3 py-1 text-xs rounded border border-border disabled:opacity-40 hover:bg-gray-100 transition-colors">
                  Next →
                </button>
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB: QUERY BUILDER
// ═══════════════════════════════════════════════════════════════════════════

function QueryBuilderTab() {
  const [sql, setSql]               = useState('SELECT * FROM sessions LIMIT 20;');
  const [powerMode, setPowerMode]   = useState(false);
  const [result, setResult]         = useState<QueryResult | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const [running, setRunning]       = useState(false);
  const [exporting, setExporting]   = useState(false);

  async function handleExportExcel() {
    if (!sql.trim()) return;
    setExporting(true);
    try {
      await downloadExcel(
        api.post('/analysis/export/query', { sql: sql.trim(), power_mode: false }, { responseType: 'blob' }),
        'query_export.xlsx',
      );
    } catch {
      // silent
    } finally {
      setExporting(false);
    }
  }

  async function runQuery() {
    if (!sql.trim()) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.post('/analysis/query', { sql: sql.trim(), power_mode: powerMode });
      setResult(res.data);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Query failed.';
      setError(detail);
    } finally {
      setRunning(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runQuery();
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Power-mode toggle + warning */}
      <div className="flex items-center gap-4 p-4 bg-surface rounded-xl border border-border">
        <label className="flex items-center gap-3 cursor-pointer select-none">
          <div
            onClick={() => setPowerMode(p => !p)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${powerMode ? 'bg-red-600' : 'bg-gray-300'}`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${powerMode ? 'translate-x-6' : 'translate-x-1'}`} />
          </div>
          <span className="text-sm font-medium text-text-primary">Power Mode</span>
        </label>
        {powerMode && (
          <div role="alert" className="flex items-center gap-2 px-3 py-1.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            <span className="sr-only">Warning: </span>
            ⚠️ Write operations (DELETE / UPDATE / INSERT / DROP) are enabled. Proceed with caution.
          </div>
        )}
        <span className="ml-auto text-xs text-text-secondary">Ctrl+Enter to run</span>
      </div>

      {/* Editor */}
      <div className="bg-surface rounded-xl border border-border overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-gray-50">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">SQL</span>
          <button
            onClick={runQuery}
            disabled={running}
            className={`px-4 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              running ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : 'bg-primary text-white hover:bg-primary-light'
            }`}
          >
            {running ? 'Running…' : '▶ Run'}
          </button>
        </div>
        <textarea
          value={sql}
          onChange={e => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={8}
          spellCheck={false}
          className="w-full p-4 font-mono text-sm bg-gray-900 text-green-300 resize-y focus:outline-none"
          placeholder="SELECT * FROM sessions LIMIT 10;"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="p-4 bg-surface rounded-xl border border-border">
          <div className="flex items-center gap-3 mb-3">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Results</h3>
            {result.is_write ? (
              <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded">
                {result.row_count} row(s) affected
              </span>
            ) : (
              <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">
                {result.row_count} row(s) returned
              </span>
            )}
            {result.columns.length > 0 && !result.is_write && (
              <button
                onClick={handleExportExcel}
                disabled={exporting}
                aria-label="Download query results as Excel"
                className={`ml-auto text-xs px-2 py-1 rounded border border-border transition-colors ${
                  exporting ? 'opacity-40 cursor-not-allowed' : 'text-text-secondary hover:bg-gray-100'
                }`}
              >
                {exporting ? 'Preparing…' : '↓ Excel'}
              </button>
            )}
          </div>
          {result.columns.length > 0 ? (
            <div className="overflow-auto max-h-96">
              <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 bg-surface z-10">
                  <tr>
                    {result.columns.map(col => (
                      <th key={col} className="text-left p-2 border-b border-border font-semibold text-text-secondary whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i} className={`border-b border-border/30 ${i % 2 === 0 ? '' : 'bg-gray-50/50'}`}>
                      {result.columns.map(col => {
                        const val = row[col];
                        return (
                          <td key={col} className="p-2 whitespace-nowrap max-w-[240px] truncate" title={String(val ?? '')}>
                            {val === null
                              ? <span className="text-text-secondary italic">null</span>
                              : typeof val === 'string' && val.length > 80
                                ? `${val.slice(0, 80)}…`
                                : String(val)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-text-secondary">
              {result.is_write ? `Operation completed. ${result.row_count} row(s) affected.` : 'Query returned no rows.'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── SHARED HELPERS ─────────────────────────────────────────────────────────

function LoadingState({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center h-48">
      <p className="text-text-secondary">{text}</p>
    </div>
  );
}

function ErrorState({ text }: { text: string }) {
  return (
    <div className="p-6 bg-red-50 rounded-xl text-red-700 text-sm">
      <strong>Error:</strong> {text}
    </div>
  );
}
