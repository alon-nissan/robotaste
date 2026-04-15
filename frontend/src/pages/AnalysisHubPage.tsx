/**
 * AnalysisHubPage — Unified analysis interface.
 *
 * Tabs (sidebar):
 *   1. Dashboard     — Per-protocol session / subject / sample counts
 *   2. Dose Response — Individual & mean dose-response curves + per-subject table
 *   3. Explorer      — Browse database tables
 *   4. Query Builder — Run SQL queries (SELECT by default; write ops in power mode)
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';
import {
  Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ComposedChart, Area,
} from 'recharts';

// ─── TYPES ──────────────────────────────────────────────────────────────────

interface ProtocolInfo { protocol_id: string; name: string; }
interface SubjectInfo  { session_id: string; session_code: string; subject_name: string; protocol_id: string; }
interface DataPoint    {
  session_id: string; session_code: string; subject_name: string;
  cycle_number: number; concentrations: Record<string, number>; responses: Record<string, number>;
}
interface StatEntry    { mean: number; std: number; sem: number; min: number; max: number; n: number; }
interface AggregatedEntry { concentrations: Record<string, number>; n: number; stats: Record<string, StatEntry>; }
interface DoseResponseData {
  protocols: ProtocolInfo[]; subjects: SubjectInfo[]; data_points: DataPoint[];
  aggregated: AggregatedEntry[]; ingredients: string[]; response_variables: string[];
  ingredient_units: Record<string, string>;
}

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

function formatConc(val: number): string {
  if (val === 0) return '0';
  const abs = Math.abs(val);
  if (abs >= 1) return val.toFixed(2);
  return val.toFixed(Math.max(2, -Math.floor(Math.log10(abs)) + 1));
}

const SUBJECT_COLORS = [
  '#521924', '#2563eb', '#16a34a', '#ea580c', '#7c3aed',
  '#0891b2', '#be123c', '#4f46e5', '#ca8a04', '#0d9488',
];

function downloadSvg(containerRef: React.RefObject<HTMLDivElement | null>, filename: string) {
  const svgEl = containerRef.current?.querySelector('svg');
  if (!svgEl) return;
  const clone = svgEl.cloneNode(true) as SVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  const svgData = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([svgData], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── TAB DEFINITIONS ────────────────────────────────────────────────────────

type TabId = 'dashboard' | 'dose-response' | 'explorer' | 'query-builder';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'dashboard',      label: 'Dashboard',     icon: '📊' },
  { id: 'dose-response',  label: 'Dose Response',  icon: '📈' },
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
  const [data, setData]     = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.get('/analysis/dashboard')
      .then(r => { setData(r.data); setError(null); })
      .catch(() => setError('Failed to load dashboard statistics.'))
      .finally(() => setLoading(false));
  }, []);

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
      <div className="p-6 bg-surface rounded-xl border border-border">
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
  const [selectedProtocol, setSelectedProtocol] = useState('');
  const [selectedIngredient, setSelectedIngredient] = useState('');
  const [selectedVariable, setSelectedVariable]     = useState('');
  const [selectedSubjects, setSelectedSubjects]     = useState<Set<string>>(new Set());

  const individualChartRef = useRef<HTMLDivElement>(null);
  const meanChartRef       = useRef<HTMLDivElement>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (selectedProtocol) params.protocol_id = selectedProtocol;
      const res = await api.get('/analysis/dose-response', { params });
      const d: DoseResponseData = res.data;
      setData(d);
      if (!selectedIngredient && d.ingredients.length > 0) setSelectedIngredient(d.ingredients[0]);
      if (!selectedVariable  && d.response_variables.length > 0) setSelectedVariable(d.response_variables[0]);
      if (selectedSubjects.size === 0 && d.subjects.length > 0)
        setSelectedSubjects(new Set(d.subjects.map(s => s.session_id)));
      setError(null);
    } catch {
      setError('Failed to load dose-response data.');
    } finally {
      setLoading(false);
    }
  }, [selectedProtocol]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Derived data ──

  const subjectChartData = useMemo(() => {
    if (!data || !selectedIngredient || !selectedVariable) return [];
    return data.data_points
      .filter(dp => selectedSubjects.has(dp.session_id))
      .filter(dp => dp.concentrations[selectedIngredient] !== undefined)
      .filter(dp => dp.responses[selectedVariable] !== undefined)
      .map(dp => ({
        concentration: dp.concentrations[selectedIngredient],
        response: dp.responses[selectedVariable],
        subject: dp.subject_name,
        session_id: dp.session_id,
      }))
      .sort((a, b) => a.concentration - b.concentration);
  }, [data, selectedIngredient, selectedVariable, selectedSubjects]);

  const subjectLines = useMemo(() => {
    const grouped: Record<string, { concentration: number; response: number }[]> = {};
    for (const dp of subjectChartData) {
      if (!grouped[dp.subject]) grouped[dp.subject] = [];
      grouped[dp.subject].push({ concentration: dp.concentration, response: dp.response });
    }
    for (const k in grouped) grouped[k].sort((a, b) => a.concentration - b.concentration);
    return grouped;
  }, [subjectChartData]);

  const meanCurveData = useMemo(() => {
    if (!data || !selectedIngredient || !selectedVariable) return [];
    return data.aggregated
      .filter(agg => agg.stats[selectedVariable])
      .map(agg => ({
        concentration: agg.concentrations[selectedIngredient] ?? 0,
        mean:  agg.stats[selectedVariable].mean,
        sem:   agg.stats[selectedVariable].sem,
        std:   agg.stats[selectedVariable].std,
        n:     agg.stats[selectedVariable].n,
        min:   agg.stats[selectedVariable].min,
        max:   agg.stats[selectedVariable].max,
        upper: agg.stats[selectedVariable].mean + agg.stats[selectedVariable].sem,
        lower: agg.stats[selectedVariable].mean - agg.stats[selectedVariable].sem,
      }))
      .sort((a, b) => a.concentration - b.concentration);
  }, [data, selectedIngredient, selectedVariable]);

  const subjectColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    data?.subjects.forEach((s, i) => { map[s.subject_name || s.session_code] = SUBJECT_COLORS[i % SUBJECT_COLORS.length]; });
    return map;
  }, [data]);

  // Per-subject raw data table (all data points for selected filters)
  const perSubjectRows = useMemo(() => {
    if (!data || !selectedIngredient || !selectedVariable) return [];
    return data.data_points
      .filter(dp => selectedSubjects.has(dp.session_id))
      .filter(dp => dp.concentrations[selectedIngredient] !== undefined && dp.responses[selectedVariable] !== undefined)
      .map(dp => ({
        subject:       dp.subject_name || dp.session_code,
        session_code:  dp.session_code,
        cycle:         dp.cycle_number,
        concentration: dp.concentrations[selectedIngredient],
        response:      dp.responses[selectedVariable],
      }))
      .sort((a, b) => a.subject.localeCompare(b.subject) || a.concentration - b.concentration);
  }, [data, selectedIngredient, selectedVariable, selectedSubjects]);

  function toggleSubject(id: string) {
    setSelectedSubjects(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const xUnit    = data?.ingredient_units?.[selectedIngredient] ?? 'mM';
  const xLabel   = selectedIngredient ? `${selectedIngredient} (${xUnit})` : 'Concentration';
  const yLabel   = selectedVariable
    ? selectedVariable.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + ' (score)'
    : 'Response';

  if (loading) return <LoadingState text="Loading dose-response data…" />;
  if (error && !data) return <ErrorState text={error} />;

  const hasData = data && data.data_points.length > 0;

  return (
    <div>
      {!hasData ? (
        <div className="p-6 bg-surface rounded-xl border border-border flex items-center justify-center h-48 text-text-secondary text-sm">
          No experiment data available. Complete some sessions to see dose-response curves.
        </div>
      ) : (
        <>
          {/* Filters */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Protocol</label>
              <select value={selectedProtocol} onChange={e => setSelectedProtocol(e.target.value)}
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary">
                <option value="">All Protocols</option>
                {data.protocols.map(p => <option key={p.protocol_id} value={p.protocol_id}>{p.name}</option>)}
              </select>
            </div>
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

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Individual curves */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
                  Individual Subject Curves
                </h3>
                <button onClick={() => downloadSvg(individualChartRef, 'individual-curves.svg')}
                  className="text-xs px-2 py-1 rounded border border-border text-text-secondary hover:bg-gray-100 transition-colors">
                  ↓ SVG
                </button>
              </div>
              <div className="h-[360px]" ref={individualChartRef}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart margin={{ top: 10, right: 20, bottom: 40, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="concentration" type="number" tickFormatter={formatConc}
                      label={{ value: xLabel, position: 'bottom', offset: 10, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }} allowDuplicatedCategory={false} />
                    <YAxis
                      label={{ value: yLabel, angle: -90, position: 'insideLeft', offset: 10, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 13 }}
                      formatter={(v) => typeof v === 'number' ? v.toFixed(2) : v} />
                    <Legend verticalAlign="top" height={36} />
                    {Object.entries(subjectLines).map(([subject, points]) => (
                      <Line key={subject} data={points} dataKey="response" name={subject}
                        stroke={subjectColorMap[subject] || '#521924'} strokeWidth={2}
                        dot={{ r: 5, fill: subjectColorMap[subject] || '#521924' }}
                        connectNulls type="monotone" />
                    ))}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Mean curve */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
                  Mean Dose-Response Curve (± SEM)
                </h3>
                <button onClick={() => downloadSvg(meanChartRef, 'mean-curve.svg')}
                  className="text-xs px-2 py-1 rounded border border-border text-text-secondary hover:bg-gray-100 transition-colors">
                  ↓ SVG
                </button>
              </div>
              <div className="h-[360px]" ref={meanChartRef}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={meanCurveData} margin={{ top: 10, right: 20, bottom: 40, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="concentration" type="number" tickFormatter={formatConc}
                      label={{ value: xLabel, position: 'bottom', offset: 10, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }} />
                    <YAxis
                      label={{ value: yLabel, angle: -90, position: 'insideLeft', offset: 10, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 13 }}
                      formatter={(v, name) => [typeof v === 'number' ? v.toFixed(2) : v, name === 'mean' ? 'Mean' : name]} />
                    <Area dataKey="upper" stroke="none" fill="#521924" fillOpacity={0.1} connectNulls type="monotone" />
                    <Area dataKey="lower" stroke="none" fill="#ffffff" fillOpacity={1}   connectNulls type="monotone" />
                    <Line dataKey="mean" name="Mean" stroke="#521924" strokeWidth={3}
                      dot={{ r: 6, fill: '#521924', stroke: '#fff', strokeWidth: 2 }} connectNulls type="monotone" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Bottom row: Subject selector + summary stats */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Subject selector */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Subjects</h3>
              <div className="flex gap-2 mb-3">
                <button onClick={() => setSelectedSubjects(new Set(data.subjects.map(s => s.session_id)))}
                  className="px-3 py-1 text-xs bg-primary text-white rounded-lg hover:bg-primary-light transition-colors">
                  Select All
                </button>
                <button onClick={() => setSelectedSubjects(new Set())}
                  className="px-3 py-1 text-xs bg-surface text-text-primary rounded-lg border border-border hover:bg-gray-100 transition-colors">
                  Clear All
                </button>
              </div>
              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                {data.subjects.map((s, i) => (
                  <label key={s.session_id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                    <input type="checkbox" checked={selectedSubjects.has(s.session_id)}
                      onChange={() => toggleSubject(s.session_id)} className="w-4 h-4 rounded accent-primary" />
                    <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: SUBJECT_COLORS[i % SUBJECT_COLORS.length] }} />
                    <span className="text-sm text-text-primary">{s.subject_name || s.session_code}</span>
                    <span className="text-xs text-text-secondary ml-auto">{s.session_code}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Summary stats */}
            <div className="lg:col-span-2 p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Summary Statistics</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
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
                {meanCurveData.length === 0 && (
                  <p className="text-center text-text-secondary text-sm py-6">No aggregated data for the selected filters.</p>
                )}
              </div>
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
                      <td className="p-2">{row.subject}</td>
                      <td className="p-2 font-mono text-xs text-text-secondary">{row.session_code}</td>
                      <td className="p-2 text-right">{row.cycle}</td>
                      <td className="p-2 text-right">{formatConc(row.concentration)}</td>
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
          <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
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
