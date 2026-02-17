/**
 * LandingPage — Entry point for moderators and participants.
 *
 * Two-column layout:
 * - Left: Moderator panel (create new session or resume existing)
 * - Right: Participant panel (join session by code)
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Session } from '../types';

import PageLayout from '../components/PageLayout';

export default function LandingPage() {
  // ─── STATE ─────────────────────────────────────────────────────────────
  const [sessionCode, setSessionCode] = useState('');
  const [activeSessions, setActiveSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  // ─── FETCH ACTIVE SESSIONS ON MOUNT ────────────────────────────────────
  useEffect(() => {
    async function fetchSessions() {
      try {
        const res = await api.get('/sessions');
        const sessions: Session[] = res.data;
        setActiveSessions(sessions.filter(s => s.state === 'active'));
      } catch {
        // Non-critical — resume dropdown will just be empty
      }
    }
    fetchSessions();
  }, []);

  // ─── HANDLERS ──────────────────────────────────────────────────────────

  async function handleCreateSession() {
    setCreating(true);
    setError(null);
    try {
      const res = await api.post('/sessions', {
        moderator_name: 'Research Team',
      });
      const newSessionId = res.data.session_id;
      navigate(`/moderator/setup?session=${newSessionId}`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to create session';
      setError(detail);
    } finally {
      setCreating(false);
    }
  }

  function handleResumeSession() {
    if (!selectedSessionId) {
      setError('Please select a session to resume');
      return;
    }
    navigate(`/moderator/monitoring?session=${selectedSessionId}`);
  }

  async function handleJoinSession() {
    const code = sessionCode.trim();
    if (!code) {
      setError('Please enter a session code');
      return;
    }

    setJoining(true);
    setError(null);
    try {
      const res = await api.get(`/sessions/code/${code}`);
      const session: Session = res.data;
      navigate(`/subject/${session.session_id}/consent`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Invalid session code';
      setError(detail);
    } finally {
      setJoining(false);
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
        <div className="mb-6 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ═══ LEFT: Moderator Panel ═══ */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          <h2 className="text-lg font-semibold mb-4">🧪 Moderator</h2>

          {/* Create new session */}
          <button
            onClick={handleCreateSession}
            disabled={creating}
            className={`
              w-full py-4 px-8 rounded-xl text-lg font-semibold
              transition-all duration-200 shadow-md mb-6
              ${creating
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer'
              }
            `}
          >
            {creating ? 'Creating...' : 'Create New Session'}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-border" />
            <span className="text-sm text-text-secondary">or</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Resume existing session */}
          <label className="block text-sm font-medium text-text-primary mb-2">
            Resume Session
          </label>
          <select
            value={selectedSessionId}
            onChange={e => setSelectedSessionId(e.target.value)}
            className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary mb-4"
          >
            <option value="">Select a session...</option>
            {activeSessions.map(s => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_code} — Cycle {s.current_cycle} ({s.current_phase})
              </option>
            ))}
          </select>

          <button
            onClick={handleResumeSession}
            disabled={!selectedSessionId}
            className={`
              px-4 py-2 text-sm rounded-lg border border-border
              transition-colors
              ${selectedSessionId
                ? 'bg-surface text-text-primary hover:bg-gray-100 cursor-pointer'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }
            `}
          >
            Continue
          </button>
        </div>

        {/* ═══ RIGHT: Participant Panel ═══ */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          <h2 className="text-lg font-semibold mb-4">👤 Participant</h2>

          <label className="block text-sm font-medium text-text-primary mb-2">
            Session Code
          </label>
          <input
            type="text"
            value={sessionCode}
            onChange={e => setSessionCode(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && handleJoinSession()}
            placeholder="Enter 6-character code"
            maxLength={6}
            className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary tracking-widest text-center text-lg mb-4"
          />

          <button
            onClick={handleJoinSession}
            disabled={joining || !sessionCode.trim()}
            className={`
              w-full py-4 px-8 rounded-xl text-lg font-semibold
              transition-all duration-200 shadow-md
              ${joining || !sessionCode.trim()
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer'
              }
            `}
          >
            {joining ? 'Joining...' : 'Join Session'}
          </button>
        </div>
      </div>
    </PageLayout>
  );
}
