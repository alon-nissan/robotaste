/**
 * DoseResponseDashboardPage — Visualize dose-response curves from experiment data.
 *
 * Shows:
 * - Individual subject dose-response curves (scatter + line)
 * - Aggregated mean curve with error bars (SEM)
 * - Summary statistics table
 * - Filters for protocol, ingredient, and response variable
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';
import {
  Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ComposedChart, Area,
} from 'recharts';

// ─── TYPES ──────────────────────────────────────────────────────────────────

interface ProtocolInfo {
  protocol_id: string;
  name: string;
}

interface SubjectInfo {
  session_id: string;
  session_code: string;
  subject_name: string;
  protocol_id: string;
}

interface DataPoint {
  session_id: string;
  session_code: string;
  subject_name: string;
  cycle_number: number;
  concentrations: Record<string, number>;
  responses: Record<string, number>;
}

interface StatEntry {
  mean: number;
  std: number;
  sem: number;
  min: number;
  max: number;
  n: number;
}

interface AggregatedEntry {
  concentrations: Record<string, number>;
  n: number;
  stats: Record<string, StatEntry>;
}

interface DoseResponseData {
  protocols: ProtocolInfo[];
  subjects: SubjectInfo[];
  data_points: DataPoint[];
  aggregated: AggregatedEntry[];
  ingredients: string[];
  response_variables: string[];
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
  const [selectedProtocol, setSelectedProtocol] = useState<string>('');
  const [selectedIngredient, setSelectedIngredient] = useState<string>('');
  const [selectedVariable, setSelectedVariable] = useState<string>('');
  const [selectedSubjects, setSelectedSubjects] = useState<Set<string>>(new Set());

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (selectedProtocol) params.protocol_id = selectedProtocol;
      const res = await api.get('/analysis/dose-response', { params });
      const d: DoseResponseData = res.data;
      setData(d);

      // Auto-select first ingredient and variable if not set
      if (!selectedIngredient && d.ingredients.length > 0) {
        setSelectedIngredient(d.ingredients[0]);
      }
      if (!selectedVariable && d.response_variables.length > 0) {
        setSelectedVariable(d.response_variables[0]);
      }
      // Select all subjects by default
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
  }, [selectedProtocol]); // Only re-fetch when protocol filter changes

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ─── DERIVED DATA ───────────────────────────────────────────────────────

  // Per-subject chart data: [{ concentration, response, subject }]
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

  // Per-subject line data grouped by subject
  const subjectLines = useMemo(() => {
    const grouped: Record<string, { concentration: number; response: number }[]> = {};
    for (const dp of subjectChartData) {
      if (!grouped[dp.subject]) grouped[dp.subject] = [];
      grouped[dp.subject].push({ concentration: dp.concentration, response: dp.response });
    }
    // Sort each subject's data by concentration
    for (const key in grouped) {
      grouped[key].sort((a, b) => a.concentration - b.concentration);
    }
    return grouped;
  }, [subjectChartData]);

  // Aggregated mean curve with error bars
  const meanCurveData = useMemo(() => {
    if (!data || !selectedIngredient || !selectedVariable) return [];

    return data.aggregated
      .filter(agg => agg.stats[selectedVariable])
      .map(agg => ({
        concentration: agg.concentrations[selectedIngredient] ?? 0,
        mean: agg.stats[selectedVariable].mean,
        sem: agg.stats[selectedVariable].sem,
        std: agg.stats[selectedVariable].std,
        n: agg.stats[selectedVariable].n,
        min: agg.stats[selectedVariable].min,
        max: agg.stats[selectedVariable].max,
        upper: agg.stats[selectedVariable].mean + agg.stats[selectedVariable].sem,
        lower: agg.stats[selectedVariable].mean - agg.stats[selectedVariable].sem,
      }))
      .sort((a, b) => a.concentration - b.concentration);
  }, [data, selectedIngredient, selectedVariable]);

  // Subject color map
  const subjectColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    data?.subjects.forEach((s, i) => {
      map[s.subject_name || s.session_code] = SUBJECT_COLORS[i % SUBJECT_COLORS.length];
    });
    return map;
  }, [data]);

  // ─── SUBJECT TOGGLE ─────────────────────────────────────────────────────

  function toggleSubject(sessionId: string) {
    setSelectedSubjects(prev => {
      const next = new Set(prev);
      if (next.has(sessionId)) next.delete(sessionId);
      else next.add(sessionId);
      return next;
    });
  }

  function selectAllSubjects() {
    if (!data) return;
    setSelectedSubjects(new Set(data.subjects.map(s => s.session_id)));
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {/* Protocol filter */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Protocol</label>
              <select
                value={selectedProtocol}
                onChange={e => setSelectedProtocol(e.target.value)}
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              >
                <option value="">All Protocols</option>
                {data.protocols.map(p => (
                  <option key={p.protocol_id} value={p.protocol_id}>{p.name}</option>
                ))}
              </select>
            </div>

            {/* Ingredient selector */}
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

            {/* Response variable selector */}
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

          {/* ═══ CHARTS ROW ═══ */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">

            {/* LEFT: Individual Subject Curves */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
                Individual Subject Curves
              </h3>
              <div className="h-[360px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis
                      dataKey="concentration"
                      type="number"
                      label={{ value: selectedIngredient, position: 'bottom', offset: 0, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }}
                      allowDuplicatedCategory={false}
                    />
                    <YAxis
                      label={{ value: selectedVariable.replace(/_/g, ' '), angle: -90, position: 'insideLeft', offset: 10, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 13 }}
                      formatter={(value) => typeof value === 'number' ? value.toFixed(2) : value}
                    />
                    <Legend verticalAlign="top" height={36} />
                    {Object.entries(subjectLines).map(([subject, points]) => (
                      <Line
                        key={subject}
                        data={points}
                        dataKey="response"
                        name={subject}
                        stroke={subjectColorMap[subject] || '#521924'}
                        strokeWidth={2}
                        dot={{ r: 5, fill: subjectColorMap[subject] || '#521924' }}
                        connectNulls
                        type="monotone"
                      />
                    ))}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* RIGHT: Mean Curve with SEM Error Band */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
                Mean Dose-Response Curve (± SEM)
              </h3>
              <div className="h-[360px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={meanCurveData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis
                      dataKey="concentration"
                      type="number"
                      label={{ value: selectedIngredient, position: 'bottom', offset: 0, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }}
                    />
                    <YAxis
                      label={{ value: selectedVariable.replace(/_/g, ' '), angle: -90, position: 'insideLeft', offset: 10, style: { fill: '#7F8C8D', fontSize: 13 } }}
                      tick={{ fill: '#7F8C8D', fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 13 }}
                      formatter={(value, name) => [typeof value === 'number' ? value.toFixed(2) : value, name === 'mean' ? 'Mean' : name]}
                    />
                    {/* SEM band */}
                    <Area
                      dataKey="upper"
                      stroke="none"
                      fill="#521924"
                      fillOpacity={0.1}
                      connectNulls
                      type="monotone"
                    />
                    <Area
                      dataKey="lower"
                      stroke="none"
                      fill="#ffffff"
                      fillOpacity={1}
                      connectNulls
                      type="monotone"
                    />
                    {/* Mean line */}
                    <Line
                      dataKey="mean"
                      name="Mean"
                      stroke="#521924"
                      strokeWidth={3}
                      dot={{ r: 6, fill: '#521924', stroke: '#fff', strokeWidth: 2 }}
                      connectNulls
                      type="monotone"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ═══ BOTTOM ROW: Subject Selector + Summary Stats ═══ */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Subject Selector */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
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
                {data.subjects.map((s, i) => (
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
                      style={{ backgroundColor: SUBJECT_COLORS[i % SUBJECT_COLORS.length] }}
                    />
                    <span className="text-sm text-text-primary">
                      {s.subject_name || s.session_code}
                    </span>
                    <span className="text-xs text-text-secondary ml-auto">{s.session_code}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Summary Statistics Table */}
            <div className="lg:col-span-2 p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
                Summary Statistics
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left p-2 text-text-secondary font-medium">
                        {selectedIngredient || 'Concentration'}
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
                        <td className="p-2 font-medium">{row.concentration}</td>
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
