import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import Pagination from '../../components/analysis/Pagination';
import type { SessionListItem } from '../../types';

interface SessionsResponse {
  data: SessionListItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function SessionManagerPage() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [stateFilter, setStateFilter] = useState('');
  const [showArchived, setShowArchived] = useState(false);

  // Selection
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Confirm delete modal
  const [deleteTarget, setDeleteTarget] = useState<string[] | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const fetchSessions = useCallback(
    async (p: number, ps: number) => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, unknown> = {
          page: p,
          page_size: ps,
          include_archived: showArchived,
        };
        if (stateFilter) params.state = stateFilter;
        const res = await api.get('/analysis/sessions', { params });
        const data = res.data as SessionsResponse;
        setSessions(data.data);
        setTotal(data.total);
      } catch {
        setError('Failed to load sessions');
      } finally {
        setLoading(false);
      }
    },
    [showArchived, stateFilter],
  );

  useEffect(() => {
    setPage(1);
    setSelected(new Set());
    fetchSessions(1, pageSize);
  }, [stateFilter, showArchived]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleArchive(ids: string[], restore = false) {
    setActionLoading(true);
    setActionMsg(null);
    try {
      if (ids.length === 1) {
        await api.patch(`/analysis/sessions/${ids[0]}/archive`, { restore });
      } else {
        await api.post('/analysis/sessions/batch', {
          action: restore ? 'restore' : 'archive',
          session_ids: ids,
        });
      }
      setActionMsg(`${restore ? 'Restored' : 'Archived'} ${ids.length} session(s)`);
      setSelected(new Set());
      fetchSessions(page, pageSize);
    } catch {
      setActionMsg('Action failed');
    } finally {
      setActionLoading(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setActionLoading(true);
    setActionMsg(null);
    try {
      if (deleteTarget.length === 1) {
        await api.delete(`/analysis/sessions/${deleteTarget[0]}`);
      } else {
        await api.post('/analysis/sessions/batch', {
          action: 'delete',
          session_ids: deleteTarget,
        });
      }
      setActionMsg(`Deleted ${deleteTarget.length} session(s)`);
      setSelected(new Set());
      setDeleteTarget(null);
      fetchSessions(page, pageSize);
    } catch {
      setActionMsg('Delete failed');
    } finally {
      setActionLoading(false);
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === sessions.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sessions.map((s) => s.session_id)));
    }
  }

  const selectedIds = Array.from(selected);

  const columns = [
    { key: 'session_code', label: 'Code' },
    { key: 'protocol_name', label: 'Protocol' },
    { key: 'subject_name', label: 'Subject' },
    { key: 'state', label: 'State' },
    { key: 'current_phase', label: 'Phase' },
    { key: 'current_cycle', label: 'Cycle' },
    { key: 'created_at', label: 'Created' },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold text-text-primary mb-6">Session Manager</h2>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          className="border border-border rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">All states</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
        </select>

        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
            className="rounded"
          />
          Show archived
        </label>
      </div>

      {/* Batch actions */}
      {selectedIds.length > 0 && (
        <div className="flex items-center gap-2 mb-4 p-3 bg-surface rounded-lg border border-border">
          <span className="text-sm text-text-secondary">{selectedIds.length} selected</span>
          <button
            onClick={() => handleArchive(selectedIds)}
            disabled={actionLoading}
            className="px-3 py-1.5 text-sm border border-border rounded-lg bg-white hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            Archive
          </button>
          {showArchived && (
            <button
              onClick={() => handleArchive(selectedIds, true)}
              disabled={actionLoading}
              className="px-3 py-1.5 text-sm border border-border rounded-lg bg-white hover:bg-gray-100 transition-colors disabled:opacity-50"
            >
              Restore
            </button>
          )}
          <button
            onClick={() => setDeleteTarget(selectedIds)}
            disabled={actionLoading}
            className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      )}

      {/* Action message */}
      {actionMsg && (
        <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm">
          {actionMsg}
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* Table with checkbox column */}
      <div className="bg-surface rounded-xl border border-border p-4">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="p-2 w-8">
                  <input
                    type="checkbox"
                    checked={sessions.length > 0 && selected.size === sessions.length}
                    onChange={toggleAll}
                    className="rounded"
                  />
                </th>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className="text-left p-2 text-text-secondary font-medium whitespace-nowrap"
                  >
                    {col.label}
                  </th>
                ))}
                <th className="p-2 text-text-secondary font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={columns.length + 2} className="p-4 text-center text-text-secondary">
                    Loading...
                  </td>
                </tr>
              ) : sessions.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 2} className="p-4 text-center text-text-secondary">
                    No sessions found.
                  </td>
                </tr>
              ) : (
                sessions.map((s) => (
                  <tr
                    key={s.session_id}
                    className={`border-b border-border/50 ${s.deleted_at ? 'opacity-50' : ''}`}
                  >
                    <td className="p-2">
                      <input
                        type="checkbox"
                        checked={selected.has(s.session_id)}
                        onChange={() => toggleSelect(s.session_id)}
                        className="rounded"
                      />
                    </td>
                    <td className="p-2 font-mono text-xs">{s.session_code}</td>
                    <td className="p-2">{s.protocol_name ?? '—'}</td>
                    <td className="p-2">{s.subject_name ?? '—'}</td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          s.state === 'completed'
                            ? 'bg-green-100 text-green-700'
                            : s.state === 'active'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {s.state}
                      </span>
                    </td>
                    <td className="p-2 text-text-secondary">{s.current_phase}</td>
                    <td className="p-2 text-right">{s.current_cycle}</td>
                    <td className="p-2 text-text-secondary text-xs">
                      {s.created_at?.slice(0, 10)}
                    </td>
                    <td className="p-2">
                      <div className="flex gap-1">
                        {s.deleted_at ? (
                          <button
                            onClick={() => handleArchive([s.session_id], true)}
                            className="px-2 py-1 text-xs border border-border rounded bg-white hover:bg-gray-100"
                          >
                            Restore
                          </button>
                        ) : (
                          <button
                            onClick={() => handleArchive([s.session_id])}
                            className="px-2 py-1 text-xs border border-border rounded bg-white hover:bg-gray-100"
                          >
                            Archive
                          </button>
                        )}
                        <button
                          onClick={() => setDeleteTarget([s.session_id])}
                          className="px-2 py-1 text-xs bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={(p) => { setPage(p); fetchSessions(p, pageSize); }}
          onPageSizeChange={(ps) => { setPageSize(ps); setPage(1); fetchSessions(1, ps); }}
        />
      </div>

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-text-primary mb-2">Confirm Delete</h3>
            <p className="text-sm text-text-secondary mb-6">
              Permanently delete {deleteTarget.length} session
              {deleteTarget.length !== 1 ? 's' : ''}? This will also delete all related samples,
              pump operations, and BO data. This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteTarget(null)}
                className="flex-1 px-4 py-2 border border-border rounded-lg text-sm text-text-primary hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={actionLoading}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {actionLoading ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
