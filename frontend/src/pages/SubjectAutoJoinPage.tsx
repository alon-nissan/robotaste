/**
 * SubjectAutoJoinPage — Auto-connect subjects to active sessions.
 *
 * Mirrors the Streamlit `landing_page_subject()` behavior:
 * 1. Polls GET /api/sessions for active sessions
 * 2. If exactly 1 active → auto-redirect to consent page
 * 3. If 0 → show "Waiting for moderator..." + poll every 5s
 * 4. If multiple → show list of sessions to pick from
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Session } from '../types';
import PageLayout from '../components/PageLayout';

export default function SubjectAutoJoinPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [status, setStatus] = useState<'loading' | 'waiting' | 'multiple'>('loading');
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const res = await api.get('/sessions');
        const allSessions: Session[] = res.data.sessions || res.data || [];
        const active = allSessions.filter(s => s.state === 'active');

        if (cancelled) return;

        if (active.length === 1) {
          navigate(`/subject/${active[0].session_id}/consent`, { replace: true });
          return;
        } else if (active.length === 0) {
          setStatus('waiting');
          setSessions([]);
          timeoutId = setTimeout(poll, 5000);
        } else {
          setStatus('multiple');
          setSessions(active);
        }
      } catch {
        if (!cancelled) {
          setStatus('waiting');
          timeoutId = setTimeout(poll, 5000);
        }
      }
    }

    poll();
    return () => { cancelled = true; clearTimeout(timeoutId); };
  }, [navigate]);

  return (
    <PageLayout>
      {status === 'loading' && (
        <div className="text-center py-12">
          <div className="text-lg text-text-secondary">Connecting...</div>
        </div>
      )}

      {status === 'waiting' && (
        <div className="text-center py-12">
          <h1 className="text-2xl font-light text-text-primary mb-4">
            Waiting for Session
          </h1>
          <p className="text-text-secondary mb-6">
            Waiting for moderator to create a session...
          </p>
          <div className="inline-block w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {status === 'multiple' && (
        <div className="max-w-md mx-auto py-12">
          <h1 className="text-2xl font-light text-text-primary mb-6 text-center">
            Select Session
          </h1>
          <div className="space-y-3">
            {sessions.map(s => (
              <button
                key={s.session_id}
                onClick={() => navigate(`/subject/${s.session_id}/consent`, { replace: true })}
                className="w-full p-4 bg-surface rounded-xl border border-border hover:border-primary transition-colors text-left cursor-pointer"
              >
                <div className="font-medium text-text-primary">
                  Session {s.session_code}
                </div>
                <div className="text-sm text-text-secondary">
                  Phase: {s.current_phase} · Cycle: {s.current_cycle}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  );
}
