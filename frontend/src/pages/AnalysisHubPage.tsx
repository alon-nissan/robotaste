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
  sample_temperature_c?: number;
  created_at?: string;
}
interface StatEntry    { mean: number; std: number; sem: number; min: number; max: number; n: number; }
interface AggregatedEntry { concentrations: Record<string, number>; n: number; stats: Record<string, StatEntry>; }
interface DoseResponseData {
  protocols: ProtocolInfo[]; subjects: SubjectInfo[]; data_points: DataPoint[];
  aggregated: AggregatedEntry[]; ingredients: string[]; response_variables: string[];
  ingredient_units: Record<string, string>;
  sample_temperatures_c?: number[];
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

const INTENSITY_LABELS: Record<number, string> = {
  1: 'Not at all',
  3: 'Light',
  5: 'Moderate',
  7: 'Strong',
  9: 'Extremely strong',
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

async function downloadChartAsPng(
  containerRef: React.RefObject<HTMLDivElement | null>,
  title: string,
  subtitle: string,
  baseName: string,
) {
  const svgEl = containerRef.current?.querySelector('svg');
  if (!svgEl) return;
  const clone = svgEl.cloneNode(true) as SVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

  const { width, height } = svgEl.getBoundingClientRect();
  const scale    = 2;
  const titleH   = subtitle ? 80 : 50;
  const footerH  = 32;

  const svgString = new XMLSerializer().serializeToString(clone);
  const svgBlob   = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
  const url       = URL.createObjectURL(svgBlob);

  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = reject;
    img.src = url;
  });

  const canvas    = document.createElement('canvas');
  canvas.width    = Math.round(width  * scale);
  canvas.height   = Math.round((titleH + height + footerH) * scale);
  const ctx       = canvas.getContext('2d')!;

  ctx.fillStyle   = CS.bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.textAlign   = 'center';
  ctx.fillStyle   = CS.titleColor;
  ctx.font        = `bold ${16 * scale}px -apple-system, BlinkMacSystemFont, sans-serif`;
  ctx.fillText(title, canvas.width / 2, 26 * scale);
  if (subtitle) {
    ctx.font      = `bold ${13 * scale}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.fillText(subtitle, canvas.width / 2, 50 * scale);
  }

  ctx.drawImage(img, 0, titleH * scale, Math.round(width * scale), Math.round(height * scale));

  const ts    = new Date();
  const stamp = ts.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  ctx.fillStyle   = CS.axisColor;
  ctx.font        = `${10 * scale}px -apple-system, BlinkMacSystemFont, sans-serif`;
  ctx.textAlign   = 'right';
  ctx.fillText(`Downloaded: ${stamp}`, canvas.width - 10 * scale, canvas.height - 8 * scale);

  URL.revokeObjectURL(url);

  const fileStamp = ts.toISOString().replace(/[:.T]/g, '-').slice(0, 19);
  canvas.toBlob(blob => {
    if (!blob) return;
    const dl = URL.createObjectURL(blob);
    const a  = document.createElement('a');
    a.href     = dl;
    a.download = `${baseName}_${fileStamp}.png`;
    a.click();
    URL.revokeObjectURL(dl);
  }, 'image/png');
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
  const [selectedProtocol, setSelectedProtocol] = useState('');
  const [selectedIngredient, setSelectedIngredient] = useState('');
  const [selectedVariable, setSelectedVariable]     = useState('');
  const [selectedSubjects, setSelectedSubjects]     = useState<Set<string>>(new Set());
  const [selectedTemps, setSelectedTemps]           = useState<Set<string>>(new Set());
  const [cycleMin, setCycleMin]                     = useState<number | null>(null);
  const [cycleMax, setCycleMax]                     = useState<number | null>(null);
  const [dateFrom, setDateFrom]                     = useState('');
  const [dateTo, setDateTo]                         = useState('');

  const meanChartRef = useRef<HTMLDivElement>(null);

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
  }, [selectedProtocol]);
  // selectedIngredient, selectedVariable, and selectedSubjects are intentionally omitted:
  // they filter data client-side from the already-fetched payload; only a protocol change
  // requires a new API call.

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Derived data ──


  const filteredForChart = useMemo(() => {
    if (!data || !selectedIngredient || !selectedVariable) return [];
    return data.data_points.filter(dp => {
      if (!selectedSubjects.has(dp.session_id)) return false;
      if (selectedTemps.size > 0) {
        const t = dp.sample_temperature_c == null ? '' : String(dp.sample_temperature_c);
        if (!selectedTemps.has(t)) return false;
      }
      if (cycleMin != null && dp.cycle_number < cycleMin) return false;
      if (cycleMax != null && dp.cycle_number > cycleMax) return false;
      if (dateFrom && dp.created_at && dp.created_at < dateFrom) return false;
      if (dateTo && dp.created_at && dp.created_at > dateTo + 'T23:59:59') return false;
      return dp.concentrations[selectedIngredient] !== undefined && dp.responses[selectedVariable] != null;
    });
  }, [data, selectedIngredient, selectedVariable, selectedSubjects, selectedTemps, cycleMin, cycleMax, dateFrom, dateTo]);

  const meanCurveData = useMemo(() => {
    const groups = new Map<number, number[]>();
    for (const dp of filteredForChart) {
      const c = dp.concentrations[selectedIngredient] ?? 0;
      const v = Number(dp.responses[selectedVariable]);
      if (!Number.isFinite(v)) continue;
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
        return {
          concentration, mean, std, sem, n,
          min: Math.min(...vals), max: Math.max(...vals),
          lower: mean - sem, upper: mean + sem,
        };
      })
      .sort((a, b) => a.concentration - b.concentration);
  }, [filteredForChart, selectedIngredient, selectedVariable]);

  const meanSubjectInfo = useMemo(() => {
    const n = new Set(filteredForChart.map(dp => dp.session_id)).size;
    const temps = filteredForChart.map(dp => dp.sample_temperature_c).filter((t): t is number => t != null);
    const meanTemp = temps.length > 0 ? temps.reduce((a, b) => a + b, 0) / temps.length : null;
    return { n, meanTempStr: meanTemp != null ? `${meanTemp.toFixed(1)}°C` : '?' };
  }, [filteredForChart]);

  const meanCurveDataCategorical = useMemo(
    () => meanCurveData.map(row => ({ ...row, concKey: fmtConc(row.concentration) })),
    [meanCurveData],
  );

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
    ? selectedVariable.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + ' score (1–9 scale)'
    : 'Response score (1–9 scale)';

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

          {/* Chart + Filters */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Mean curve — 2/3 width */}
            <div className="lg:col-span-2 p-6 rounded-xl border border-border" style={{ backgroundColor: CS.bg }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: CS.titleColor }}>
                  Mean Dose-Response Curve (± SEM)
                </h3>
                <button
                  onClick={() => void downloadChartAsPng(
                    meanChartRef,
                    `${selectedIngredient || 'Concentration'} Dose-Response`,
                    `Mean ${yLabel}`,
                    'mean-dose-response',
                  )}
                  aria-label="Download mean curve as PNG"
                  className="text-xs px-2 py-1 rounded border border-border text-text-secondary hover:bg-gray-100 transition-colors">
                  ↓ PNG
                </button>
              </div>
              <div className="h-[420px]" ref={meanChartRef}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={meanCurveDataCategorical} margin={{ top: 10, right: 100, bottom: 50, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CS.grid} />
                    <XAxis
                      dataKey="concKey" type="category" allowDuplicatedCategory={false}
                      label={{ value: xLabel, position: 'bottom', offset: 12, style: { fill: CS.axisColor, fontSize: 13 } }}
                      tick={{ fill: CS.axisColor, fontSize: 12 }}
                    />
                    <YAxis
                      domain={[1, 9]} ticks={[1,2,3,4,5,6,7,8,9]} allowDecimals={false}
                      label={{ value: yLabel, angle: -90, position: 'insideLeft', offset: 10, style: { fill: CS.axisColor, fontSize: 13 } }}
                      tick={{ fill: CS.axisColor, fontSize: 12 }}
                    />
                    <YAxis
                      yAxisId="intensity" orientation="right"
                      domain={[1, 9]} ticks={[1, 3, 5, 7, 9]}
                      tickFormatter={(v: number) => INTENSITY_LABELS[v] ?? ''}
                      tick={{ fill: CS.axisColor, fontSize: 11 }}
                      axisLine={{ stroke: CS.grid }} tickLine={{ stroke: CS.grid }} width={100}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 8, border: `1px solid ${CS.grid}`, fontSize: 13, backgroundColor: '#fff' }}
                      formatter={(v, name) => [typeof v === 'number' ? v.toFixed(2) : v, name === 'mean' ? 'Mean' : name]}
                    />
                    <Legend
                      verticalAlign="top" height={52}
                      content={() => (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '4px 12px', fontSize: 13, color: CS.axisColor }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ display: 'inline-block', width: 14, height: 14, backgroundColor: CS.blueLight, borderRadius: 2, flexShrink: 0 }} />
                            <span>±SEM band</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ display: 'inline-block', width: 24, height: 3, backgroundColor: CS.blue, borderRadius: 1, flexShrink: 0 }} />
                            <span>Mean {(selectedVariable || '').replace(/_/g, ' ')} (participants n={meanSubjectInfo.n}, mean temp={meanSubjectInfo.meanTempStr})</span>
                          </div>
                        </div>
                      )}
                    />
                    <Area dataKey="upper" stroke="none" fill={CS.blueLight} fillOpacity={0.5} connectNulls type="monotone" legendType="none" />
                    <Area dataKey="lower" stroke="none" fill={CS.bg}        fillOpacity={1}   connectNulls type="monotone" legendType="none" />
                    <Line dataKey="mean" stroke={CS.blue} strokeWidth={2.5}
                      dot={{ r: 7, fill: CS.blue, stroke: '#fff', strokeWidth: 2 }} connectNulls type="monotone" legendType="none" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Filters card — 1/3 width */}
            <div className="p-6 bg-surface rounded-xl border border-border flex flex-col gap-5 overflow-y-auto">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Filters</h3>
                <button
                  onClick={() => {
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

              {/* Subjects */}
              <div>
                <div className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">Subjects</div>
                <div className="flex gap-2 mb-2">
                  <button onClick={() => setSelectedSubjects(new Set(data.subjects.map(s => s.session_id)))}
                    className="px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary-light transition-colors">
                    All
                  </button>
                  <button onClick={() => setSelectedSubjects(new Set())}
                    className="px-2 py-1 text-xs bg-surface text-text-primary rounded border border-border hover:bg-gray-100 transition-colors">
                    None
                  </button>
                </div>
                <div className="space-y-1 max-h-[160px] overflow-y-auto">
                  {data.subjects.map((s, i) => (
                    <label key={s.session_id} className="flex items-center gap-2 py-1 px-1 rounded hover:bg-gray-50 cursor-pointer">
                      <input type="checkbox" checked={selectedSubjects.has(s.session_id)}
                        onChange={() => toggleSubject(s.session_id)} className="w-4 h-4 rounded accent-primary" />
                      <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: SUBJECT_COLORS[i % SUBJECT_COLORS.length] }} />
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
