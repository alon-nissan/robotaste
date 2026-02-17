import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';

const POLL_INTERVAL_MS = 2000;
const FALLBACK_TIMEOUT_MS = 30000;

export default function RobotPreparingPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('Preparing your sample...');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fallbackRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigatedRef = useRef(false);

  function advance() {
    if (navigatedRef.current || !sessionId) return;
    navigatedRef.current = true;
    navigate(`/subject/${sessionId}/questionnaire`);
  }

  useEffect(() => {
    if (!sessionId) return;

    // Poll pump status
    intervalRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/pump/status/${sessionId}`);
        const data = res.data;

        if (data.progress !== undefined) setProgress(data.progress);
        if (data.status_message) setStatus(data.status_message);

        if (
          data.status === 'completed' ||
          data.progress >= 100
        ) {
          advance();
        }
      } catch {
        // Also check session phase as fallback
        try {
          const sessionRes = await api.get(`/sessions/${sessionId}/status`);
          const phase = sessionRes.data.current_phase;
          if (phase === 'questionnaire') {
            advance();
          }
        } catch {
          // Ignore polling errors
        }
      }
    }, POLL_INTERVAL_MS);

    // Fallback: auto-advance after 30 seconds
    fallbackRef.current = setTimeout(() => {
      advance();
    }, FALLBACK_TIMEOUT_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (fallbackRef.current) clearTimeout(fallbackRef.current);
    };
  }, [sessionId]);

  return (
    <PageLayout showLogo={false}>
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="text-6xl mb-6">🤖 ⏳</div>

        <p className="text-xl text-text-primary mb-4">{status}</p>

        {/* Progress bar */}
        <div className="w-full max-w-md">
          <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          <p className="text-sm text-text-secondary text-center mt-2">
            {Math.round(progress)}%
          </p>
        </div>

        <p className="text-sm text-text-secondary mt-4">
          Please wait, do not touch the cups
        </p>
      </div>
    </PageLayout>
  );
}
