/**
 * SubjectAutoJoinPage — Waiting room for subjects.
 *
 * Behavior (Option B):
 * 1. Polls GET /api/sessions every 5 s for active sessions.
 * 2. While no session exists: show a calm "waiting for moderator" spinner.
 * 3. Once ≥1 session is found: transition to a "ready" confirmation screen
 *    with a large "Join Now" button. Always joins the most-recently-created
 *    session so subjects never have to choose from a list.
 * 4. Subject presses "Join Now" → navigates to the consent page.
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Session } from '../types';
import PageLayout from '../components/PageLayout';

type PageStatus = 'loading' | 'waiting' | 'ready';

export default function SubjectAutoJoinPage() {
  const [pageStatus, setPageStatus] = useState<PageStatus>('loading');
  const [targetSession, setTargetSession] = useState<Session | null>(null);
  const navigate = useNavigate();

  // Keep a stable ref to targetSession so the poll callback always sees the
  // latest value without needing to be re-created on every render.
  const targetSessionRef = useRef<Session | null>(null);
  targetSessionRef.current = targetSession;

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const res = await api.get('/sessions');
        const allSessions: Session[] = res.data.sessions || res.data || [];

        if (cancelled) return;

        if (allSessions.length === 0) {
          setPageStatus('waiting');
          setTargetSession(null);
          timeoutId = setTimeout(poll, 5000);
        } else {
          // Pick the most-recently-created session.
          const newest = [...allSessions].sort((a, b) => {
            const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
            const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
            return tb - ta;
          })[0];

          setTargetSession(newest);
          setPageStatus('ready');
          // Keep polling so we update the target if a newer session appears.
          timeoutId = setTimeout(poll, 5000);
        }
      } catch {
        if (!cancelled) {
          setPageStatus('waiting');
          timeoutId = setTimeout(poll, 5000);
        }
      }
    }

    poll();
    return () => { cancelled = true; clearTimeout(timeoutId); };
  }, []);

  function handleJoin() {
    if (targetSession) {
      navigate(`/subject/${targetSession.session_id}/consent`, { replace: true });
    }
  }

  return (
    <PageLayout showLogo={true}>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">

        {/* ─── LOADING ──────────────────────────────────────────────── */}
        {pageStatus === 'loading' && (
          <div className="space-y-4">
            <div className="inline-block w-10 h-10 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-base text-text-secondary">Connecting…</p>
          </div>
        )}

        {/* ─── WAITING ──────────────────────────────────────────────── */}
        {pageStatus === 'waiting' && (
          <div className="space-y-6 max-w-sm">
            <div className="inline-block w-12 h-12 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <div>
              <h1 className="text-2xl font-light text-text-primary mb-3">
                Welcome
              </h1>
              <p className="text-base text-text-secondary leading-relaxed">
                Please wait here. You'll be connected automatically once the moderator starts the experiment.
              </p>
            </div>
          </div>
        )}

        {/* ─── READY ────────────────────────────────────────────────── */}
        {pageStatus === 'ready' && targetSession && (
          <div className="space-y-8 max-w-sm">
            {/* Green checkmark / ready indicator */}
            <div className="flex items-center justify-center w-20 h-20 rounded-full bg-green-50 border-2 border-green-200 mx-auto">
              <span className="text-4xl">✓</span>
            </div>

            <div>
              <h1 className="text-2xl font-light text-text-primary mb-3">
                Your experiment is ready!
              </h1>
              <p className="text-base text-text-secondary leading-relaxed">
                The moderator has prepared a session for you. Press the button below when you're ready to begin.
              </p>
            </div>

            <button
              onClick={handleJoin}
              className="w-full py-4 px-8 rounded-xl text-lg font-semibold bg-primary text-white hover:bg-primary-light active:bg-primary-dark shadow-md transition-all duration-200 cursor-pointer"
            >
              Join Now
            </button>
          </div>
        )}

      </div>
    </PageLayout>
  );
}

