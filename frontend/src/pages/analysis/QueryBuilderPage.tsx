import { useState } from 'react';
import { api } from '../../api/client';
import DataTable from '../../components/analysis/DataTable';
import Pagination from '../../components/analysis/Pagination';
import { getSavedViews, saveView, deleteView } from '../../utils/savedViews';
import type { QueryResult } from '../../types';

const TABLES = ['sessions', 'samples', 'users', 'protocol_library'];

export default function QueryBuilderPage() {
  const [activeTab, setActiveTab] = useState<'visual' | 'sql'>('sql');
  const [sql, setSql] = useState('SELECT * FROM sessions LIMIT 25');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [savedViews, setSavedViews] = useState(getSavedViews);
  const [saveName, setSaveName] = useState('');
  const [showSaveInput, setShowSaveInput] = useState(false);

  // Visual builder state
  const [vTable, setVTable] = useState('sessions');
  const [vLimit, setVLimit] = useState(25);

  async function runQuery(sqlStr: string) {
    setLoading(true);
    setError(null);
    setPage(1);
    try {
      const res = await api.post('/analysis/query', { sql: sqlStr });
      setResult(res.data as QueryResult);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Query failed';
      setError(detail);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  function handleRunSQL() {
    runQuery(sql);
  }

  function handleRunVisual() {
    const q = `SELECT * FROM ${vTable} LIMIT ${vLimit}`;
    setSql(q);
    runQuery(q);
  }

  function downloadCSV() {
    if (!result) return;
    const header = result.columns.join(',');
    const rows = result.rows.map((r) =>
      r
        .map((v) => {
          const s = v === null ? '' : String(v);
          return s.includes(',') || s.includes('"') || s.includes('\n')
            ? `"${s.replace(/"/g, '""')}"`
            : s;
        })
        .join(','),
    );
    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query_results.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleSaveView() {
    if (!saveName.trim()) return;
    saveView(saveName.trim(), sql);
    setSavedViews(getSavedViews());
    setSaveName('');
    setShowSaveInput(false);
  }

  function handleLoadView(id: string) {
    const view = savedViews.find((v) => v.id === id);
    if (view) {
      setSql(view.sql);
      setActiveTab('sql');
    }
  }

  function handleDeleteView(id: string) {
    deleteView(id);
    setSavedViews(getSavedViews());
  }

  // Paginated display slice
  const displayColumns = result
    ? result.columns.map((c) => ({ key: c, label: c }))
    : [];
  const pagedRows = result
    ? result.rows
        .slice((page - 1) * pageSize, page * pageSize)
        .map((row) => {
          const obj: Record<string, unknown> = {};
          result.columns.forEach((c, i) => {
            obj[c] = row[i];
          });
          return obj;
        })
    : [];

  return (
    <div>
      <h2 className="text-xl font-semibold text-text-primary mb-6">Query Builder</h2>

      <div className="flex gap-4">
        {/* Main query area */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Tabs */}
          <div className="flex border-b border-border">
            {(['visual', 'sql'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab
                    ? 'border-primary text-primary'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                }`}
              >
                {tab === 'visual' ? 'Visual Builder' : 'SQL Editor'}
              </button>
            ))}
          </div>

          {/* Visual Builder */}
          {activeTab === 'visual' && (
            <div className="p-4 bg-surface rounded-xl border border-border space-y-3">
              <div className="flex items-center gap-3">
                <label className="text-sm text-text-secondary w-16">Table</label>
                <select
                  value={vTable}
                  onChange={(e) => setVTable(e.target.value)}
                  className="border border-border rounded px-2 py-1 text-sm bg-white"
                >
                  {TABLES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="flex items-center gap-3">
                <label className="text-sm text-text-secondary w-16">Limit</label>
                <input
                  type="number"
                  value={vLimit}
                  onChange={(e) => setVLimit(Number(e.target.value))}
                  min={1}
                  max={1000}
                  className="border border-border rounded px-2 py-1 text-sm bg-white w-24"
                />
              </div>
              <button
                onClick={handleRunVisual}
                disabled={loading}
                className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-light transition-colors disabled:opacity-50"
              >
                {loading ? 'Running...' : 'Execute'}
              </button>
            </div>
          )}

          {/* SQL Editor */}
          {activeTab === 'sql' && (
            <div className="p-4 bg-surface rounded-xl border border-border space-y-3">
              <textarea
                value={sql}
                onChange={(e) => setSql(e.target.value)}
                rows={6}
                spellCheck={false}
                className="w-full font-mono text-sm border border-border rounded-lg p-3 bg-white resize-y"
                placeholder="SELECT * FROM sessions LIMIT 25"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRunSQL}
                  disabled={loading}
                  className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-light transition-colors disabled:opacity-50"
                >
                  {loading ? 'Running...' : 'Execute'}
                </button>
                <button
                  onClick={() => setShowSaveInput((s) => !s)}
                  className="px-3 py-2 border border-border rounded-lg text-sm text-text-secondary hover:bg-gray-100 transition-colors"
                >
                  💾 Save View
                </button>
              </div>
              {showSaveInput && (
                <div className="flex gap-2">
                  <input
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    placeholder="View name"
                    className="border border-border rounded px-2 py-1 text-sm bg-white flex-1"
                    onKeyDown={(e) => e.key === 'Enter' && handleSaveView()}
                  />
                  <button
                    onClick={handleSaveView}
                    className="px-3 py-1 bg-primary text-white rounded text-sm"
                  >
                    Save
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
          )}

          {/* Results */}
          {result && (
            <div className="bg-surface rounded-xl border border-border p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-text-secondary">
                  {result.row_count} row{result.row_count !== 1 ? 's' : ''} in{' '}
                  {result.execution_time_ms}ms
                </p>
                <button
                  onClick={downloadCSV}
                  className="px-3 py-1.5 text-sm border border-border rounded-lg bg-white hover:bg-gray-100 transition-colors"
                >
                  ⬇ Download CSV
                </button>
              </div>
              <DataTable
                columns={displayColumns}
                rows={pagedRows}
                loading={loading}
                emptyMessage="Query returned no rows."
              />
              <Pagination
                page={page}
                pageSize={pageSize}
                total={result.row_count}
                onPageChange={setPage}
                onPageSizeChange={(ps) => { setPageSize(ps); setPage(1); }}
              />
            </div>
          )}
        </div>

        {/* Saved views sidebar */}
        {savedViews.length > 0 && (
          <div className="w-56 shrink-0">
            <div className="bg-surface rounded-xl border border-border p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-3">
                Saved Views
              </h3>
              <ul className="space-y-1">
                {savedViews.map((v) => (
                  <li key={v.id} className="flex items-center justify-between gap-1 group">
                    <button
                      onClick={() => handleLoadView(v.id)}
                      className="text-sm text-text-primary hover:text-primary truncate flex-1 text-left"
                    >
                      {v.name}
                    </button>
                    <button
                      onClick={() => handleDeleteView(v.id)}
                      className="text-text-secondary hover:text-red-600 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
