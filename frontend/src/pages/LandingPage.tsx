/**
 * LandingPage — Entry point for moderators.
 *
 * Single-column moderator layout:
 * - Create / manage sessions
 * - View and manage active sessions
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Session } from '../types';

import PageLayout from '../components/PageLayout';

export default function LandingPage() {
  // ─── STATE ─────────────────────────────────────────────────────────────
  const [activeSessions, setActiveSessions] = useState<Session[]>([]);
  const [killing, setKilling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  // ─── FETCH ACTIVE SESSIONS ─────────────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    try {
      const res = await api.get('/sessions?available=false');
      const sessions: Session[] = res.data.sessions || [];
      setActiveSessions(sessions);
    } catch {
      // Non-critical — active sessions section will just be empty
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // ─── HANDLERS ──────────────────────────────────────────────────────────

  function handleCreateSession() {
    navigate('/moderator/setup');
  }

  async function handleKillSession(sessionId: string, sessionCode: string) {
    if (!window.confirm(`Are you sure you want to end session ${sessionCode}? This cannot be undone.`)) {
      return;
    }
    setKilling(sessionId);
    setError(null);
    try {
      await api.post(`/sessions/${sessionId}/end`);
      await fetchSessions();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to end session';
      setError(detail);
    } finally {
      setKilling(null);
    }
  }

  // ─── RENDER ────────────────────────────────────────────────────────────
  return (
    <PageLayout>
      <h1 className="text-2xl font-light text-text-primary tracking-wide mb-8 text-center">
        Welcome to RoboTaste
      </h1>

      {/* Error banner */}
      {error && (
        <div className="mb-6 p-3 bg-red-50 text-red-700 rounded-lg text-base">
          {error}
        </div>
      )}

      <div className="max-w-xl mx-auto space-y-6">
        {/* ═══ Moderator Actions ═══ */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          <h2 className="text-lg font-semibold mb-4">🧪 Moderator</h2>

          <button
            onClick={handleCreateSession}
            className="w-full py-4 px-8 rounded-xl text-lg font-semibold transition-all duration-200 shadow-md mb-6 bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer"
          >
            Create New Session
          </button>

          <button
            onClick={() => navigate('/protocols')}
            className="w-full py-2 px-4 rounded-lg text-sm font-medium border border-border bg-surface text-text-primary hover:bg-gray-100 transition-colors cursor-pointer mb-3"
          >
            Manage Protocols
          </button>

          <button
            onClick={() => navigate('/analysis/dose-response')}
            className="w-full py-2 px-4 rounded-lg text-sm font-medium border border-border bg-surface text-text-primary hover:bg-gray-100 transition-colors cursor-pointer"
          >
            Dose-Response Dashboard
          </button>
        </div>

        {/* ═══ Active Sessions ═══ */}
        {activeSessions.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-widest text-text-secondary mb-3 px-1">
              Active Sessions
            </h2>
            <div className="space-y-3">
              {activeSessions.map((s) => {
                const config = s.experiment_config as Record<string, unknown> | undefined;
                const protocolName = (config?.protocol_name as string) ?? 'Not started';
                const createdAt = s.created_at?.slice(0, 19).replace('T', ' ') ?? '—';

                return (
                  <div
                    key={s.session_id}
                    className="p-4 bg-surface rounded-xl border border-border border-l-4 border-l-primary"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-text-primary">{protocolName}</span>
                      <span className="text-xs font-mono bg-gray-100 text-text-secondary px-2 py-0.5 rounded">
                        {s.session_code}
                      </span>
                    </div>
                    <p className="text-xs text-text-secondary mb-1">
                      Phase: {s.current_phase} · Cycle: {s.current_cycle}
                    </p>
                    <p className="text-xs text-text-secondary mb-4">
                      Created: {createdAt}
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate(`/moderator/monitoring?session=${s.session_id}`)}
                        className="px-4 py-1.5 text-sm rounded-lg border border-border bg-surface text-text-primary hover:bg-gray-100 transition-colors cursor-pointer"
                      >
                        Resume
                      </button>
                      <button
                        onClick={() => handleKillSession(s.session_id, s.session_code)}
                        disabled={killing === s.session_id}
                        className={`px-4 py-1.5 text-sm rounded-lg transition-colors ${
                          killing === s.session_id
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-red-600 text-white hover:bg-red-700 cursor-pointer'
                        }`}
                      >
                        {killing === s.session_id ? 'Ending...' : 'Kill Session'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  );
}
