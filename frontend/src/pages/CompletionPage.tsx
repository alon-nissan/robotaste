/**
 * CompletionPage — Thank you screen shown after the experiment ends.
 *
 * Displays session summary (cycles completed, duration, protocol name)
 * and a button to return home. Logo is hidden for a clean finish screen.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { SessionSummary } from '../types';

import PageLayout from '../components/PageLayout';

/** Format seconds into "X min Y sec" */
function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);
  if (minutes === 0) return `${seconds} sec`;
  return `${minutes} min ${seconds} sec`;
}

export default function CompletionPage() {
  // ─── STATE ─────────────────────────────────────────────────────────────
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ─── FETCH SESSION SUMMARY ─────────────────────────────────────────────
  useEffect(() => {
    async function fetchSummary() {
      try {
        const res = await api.get(`/sessions/${sessionId}/status`);
        setSummary(res.data as SessionSummary);
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail || 'Failed to load session summary';
        setError(detail);
      } finally {
        setLoading(false);
      }
    }
    fetchSummary();
  }, [sessionId]);

  // ─── RENDER ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <PageLayout showLogo={false}>
        <div className="flex items-center justify-center py-20">
          <p className="text-text-secondary">Loading summary...</p>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout showLogo={false}>
      <div className="max-w-lg mx-auto text-center">
        <div className="p-6 bg-surface rounded-xl border border-border">
          {/* Celebration emoji */}
          <div className="text-5xl mb-4">🎉</div>

          <h1 className="text-2xl font-light text-text-primary tracking-wide mb-8">
            Thank You for Participating!
          </h1>

          {/* Error */}
          {error && (
            <div className="mb-6 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Session Summary Card */}
          {summary && (
            <div className="mb-8 p-4 bg-surface rounded-lg border border-border border-l-4 border-l-primary text-left">
              <h2 className="text-lg font-semibold mb-3">Session Summary</h2>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-text-secondary">Cycles completed</dt>
                  <dd className="font-medium text-text-primary">{summary.total_cycles}</dd>
                </div>
                {summary.duration_seconds != null && (
                  <div className="flex justify-between">
                    <dt className="text-text-secondary">Duration</dt>
                    <dd className="font-medium text-text-primary">
                      {formatDuration(summary.duration_seconds)}
                    </dd>
                  </div>
                )}
                {summary.protocol_name && (
                  <div className="flex justify-between">
                    <dt className="text-text-secondary">Protocol</dt>
                    <dd className="font-medium text-text-primary">{summary.protocol_name}</dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          <p className="text-text-secondary text-sm mb-8">
            Your responses have been recorded.
          </p>

          {/* Return Home */}
          <button
            onClick={() => navigate('/')}
            className="py-4 px-8 rounded-xl text-lg font-semibold bg-primary text-white hover:bg-primary-light active:bg-primary-dark shadow-md transition-all duration-200 cursor-pointer"
          >
            Return to Home
          </button>
        </div>
      </div>
    </PageLayout>
  );
}
