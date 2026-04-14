import { useState, useCallback, useEffect } from 'react';
import { api } from '../../api/client';
import DataTable from '../../components/analysis/DataTable';
import Pagination from '../../components/analysis/Pagination';
import FilterBar from '../../components/analysis/FilterBar';
import JsonRenderer from '../../components/analysis/JsonRenderer';
import type { ExplorerColumn, ColumnFilter } from '../../types';

const TABLES = [
  { value: 'sessions', label: 'Sessions' },
  { value: 'samples', label: 'Samples' },
  { value: 'users', label: 'Users' },
  { value: 'protocols', label: 'Protocols' },
];

interface ExplorerResponse {
  data: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
  columns: ExplorerColumn[];
}

export default function DataExplorerPage() {
  const [table, setTable] = useState('sessions');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortColumn, setSortColumn] = useState<string | undefined>();
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [filters, setFilters] = useState<ColumnFilter[]>([]);
  const [result, setResult] = useState<ExplorerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRow, setSelectedRow] = useState<Record<string, unknown> | null>(null);
  const [detailData, setDetailData] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async (
    t: string,
    p: number,
    ps: number,
    sc?: string,
    sd?: string,
    f?: ColumnFilter[],
  ) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page: p, page_size: ps };
      if (sc) { params.sort_column = sc; params.sort_dir = sd ?? 'asc'; }
      if (f && f.length > 0) params.filters = JSON.stringify(f);
      const res = await api.get(`/analysis/explorer/${t}`, { params });
      setResult(res.data as ExplorerResponse);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchData(table, page, pageSize, sortColumn, sortDir, filters);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleTableChange(t: string) {
    setTable(t);
    setPage(1);
    setSortColumn(undefined);
    setFilters([]);
    setSelectedRow(null);
    setDetailData(null);
    fetchData(t, 1, pageSize);
  }

  function handleSort(col: string) {
    const newDir = sortColumn === col && sortDir === 'asc' ? 'desc' : 'asc';
    setSortColumn(col);
    setSortDir(newDir);
    fetchData(table, page, pageSize, col, newDir, filters);
  }

  function handleFiltersChange(f: ColumnFilter[]) {
    setFilters(f);
    setPage(1);
    fetchData(table, 1, pageSize, sortColumn, sortDir, f);
  }

  function handlePageChange(p: number) {
    setPage(p);
    fetchData(table, p, pageSize, sortColumn, sortDir, filters);
  }

  function handlePageSizeChange(ps: number) {
    setPageSize(ps);
    setPage(1);
    fetchData(table, 1, ps, sortColumn, sortDir, filters);
  }

  async function handleRowClick(row: Record<string, unknown>) {
    setSelectedRow(row);
    const pkMap: Record<string, string> = {
      sessions: 'session_id',
      samples: 'sample_id',
      users: 'id',
      protocols: 'protocol_id',
    };
    const pk = pkMap[table];
    const id = row[pk];
    if (!id) return;
    setDetailLoading(true);
    try {
      const res = await api.get(`/analysis/explorer/${table}/${id}`);
      setDetailData(res.data as Record<string, unknown>);
    } catch {
      setDetailData(null);
    } finally {
      setDetailLoading(false);
    }
  }

  const columns = result?.columns ?? [];

  return (
    <div className="flex gap-4">
      {/* Main panel */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-text-primary">Data Explorer</h2>
          <select
            value={table}
            onChange={(e) => handleTableChange(e.target.value)}
            className="border border-border rounded-lg px-3 py-2 text-sm bg-white"
          >
            {TABLES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        {/* Filters */}
        {columns.length > 0 && (
          <div className="mb-4 p-4 bg-surface rounded-lg border border-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-3">Filters</p>
            <FilterBar
              columns={columns}
              filters={filters}
              onFiltersChange={handleFiltersChange}
            />
          </div>
        )}

        {/* Table */}
        <div className="bg-surface rounded-xl border border-border p-4">
          <DataTable
            columns={columns.map((c) => ({ key: c.key, label: c.label ?? c.key, type: c.type }))}
            rows={result?.data ?? []}
            sortColumn={sortColumn}
            sortDir={sortDir}
            onSort={handleSort}
            onRowClick={handleRowClick}
            loading={loading}
            emptyMessage="No records found."
          />
          {result && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={result.total}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selectedRow && (
        <div className="w-96 shrink-0">
          <div className="sticky top-0 bg-surface rounded-xl border border-border p-4 max-h-[calc(100vh-8rem)] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text-primary">Record Detail</h3>
              <button
                onClick={() => { setSelectedRow(null); setDetailData(null); }}
                className="text-text-secondary hover:text-text-primary text-lg leading-none"
              >
                ✕
              </button>
            </div>
            {detailLoading ? (
              <p className="text-text-secondary text-sm">Loading...</p>
            ) : detailData ? (
              <div className="bg-gray-50 rounded-lg p-3">
                <JsonRenderer data={detailData} />
              </div>
            ) : (
              <JsonRenderer data={selectedRow} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
