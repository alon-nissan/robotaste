import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';

const POLL_INTERVAL_MS = 2000;

export default function RobotPreparingPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('Preparing your sample...');
  const [loadingMessage, setLoadingMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const navigatedRef = useRef(false);

  function advance() {
    if (navigatedRef.current || !sessionId) return;
    navigatedRef.current = true;
    // Advance phase in DB before navigating
    api.post(`/sessions/${sessionId}/phase`, { phase: 'questionnaire' })
      .catch(() => {/* best-effort */})
      .finally(() => navigate(`/subject/${sessionId}/questionnaire`));
  }

  // Fetch loading screen message from protocol config
  useEffect(() => {
    if (!sessionId) return;
    api.get(`/sessions/${sessionId}`)
      .then((res) => {
        const loadingScreen = res.data?.experiment_config?.loading_screen;
        if (loadingScreen?.message) {
          setLoadingMessage(loadingScreen.message);
        }
      })
      .catch(() => {/* use default */});
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;

    // Poll pump operation status
    intervalRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/pump/operation/${sessionId}`);
        const data = res.data;

        setProgress(data.progress ?? 0);

        if (data.status === 'completed') {
          setStatus('Sample ready!');
          setProgress(100);
          advance();
        } else if (data.status === 'failed') {
          setStatus('Pump error');
          setError(data.error || 'Pump operation failed');
        } else if (data.status === 'in_progress') {
          setStatus('Dispensing...');
        } else if (data.status === 'pending') {
          setStatus('Waiting for pump service...');
        } else {
          // status === 'none' — no operation found, check session phase as fallback
          try {
            const sessionRes = await api.get(`/sessions/${sessionId}/status`);
            if (sessionRes.data.current_phase === 'questionnaire') {
              advance();
            }
          } catch {
            // ignore
          }
        }
      } catch {
        // Network error — check session phase as fallback
        try {
          const sessionRes = await api.get(`/sessions/${sessionId}/status`);
          if (sessionRes.data.current_phase === 'questionnaire') {
            advance();
          }
        } catch {
          // ignore
        }
      }
    }, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
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

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-base max-w-md">
            <p className="font-medium">⚠️ {error}</p>
            <p className="mt-1 text-sm">Please notify the moderator.</p>
          </div>
        )}

        {/* Protocol loading message */}
        {loadingMessage ? (
          <p className="text-base text-text-primary mt-6 max-w-md text-center leading-relaxed">
            {loadingMessage}
          </p>
        ) : (
          <p className="text-base text-text-secondary mt-4">
            Please wait, do not touch the cups
          </p>
        )}
      </div>
    </PageLayout>
  );
}
