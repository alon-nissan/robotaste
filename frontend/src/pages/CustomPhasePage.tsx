import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { CustomPhaseConfig, QuestionConfig } from '../types';
import PageLayout from '../components/PageLayout';
import { MarkdownText } from '../components/MarkdownText';

// ─── PHASE TYPE RENDERERS ──────────────────────────────────────────────────

function TextPhase({
  config,
  onContinue,
}: {
  config: CustomPhaseConfig;
  onContinue: () => void;
}) {
  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="p-6 bg-surface rounded-xl border border-border">
        {config.title && (
          <h2 className="text-xl font-semibold text-text-primary mb-4">
            {config.title}
          </h2>
        )}

        {config.body && (
          <MarkdownText
            content={config.body}
            className="text-base text-text-primary mb-4"
          />
        )}

        {config.image_url && (
          <img
            src={config.image_url}
            alt={config.title ?? 'Phase image'}
            className="max-w-full rounded-lg mb-4"
          />
        )}

        <div className="flex justify-center mt-6">
          <button
            onClick={onContinue}
            className="py-4 px-8 rounded-xl text-lg font-semibold bg-primary text-white hover:bg-primary-light active:bg-primary-dark shadow-md transition-all duration-200 cursor-pointer"
          >
            Continue →
          </button>
        </div>
      </div>
    </div>
  );
}

function BreakPhase({
  config,
  onComplete,
}: {
  config: CustomPhaseConfig;
  onComplete: () => void;
}) {
  const duration = config.duration_seconds ?? 60;
  const [timeRemaining, setTimeRemaining] = useState(duration);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const completedRef = useRef(false);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setTimeRemaining((prev) => {
        const next = prev - 1;
        if (next <= 0 && !completedRef.current) {
          completedRef.current = true;
          setTimeout(onComplete, 0);
        }
        return Math.max(next, 0);
      });
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [duration, onComplete]);

  const elapsed = duration - timeRemaining;
  const progressPct = duration > 0 ? (elapsed / duration) * 100 : 100;
  const minutes = Math.floor(timeRemaining / 60);
  const seconds = timeRemaining % 60;
  const timeStr = `${minutes}:${String(seconds).padStart(2, '0')}`;
  const message = config.message ?? 'Please rinse your mouth with water';

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh]">
      <div className="text-6xl mb-6">☕</div>

      <h2 className="text-2xl font-semibold text-text-primary mb-2">
        Take a Break
      </h2>

      <p className="text-base text-text-primary mb-6">{message}</p>

      <div className="text-3xl font-mono text-text-primary mb-6">
        {timeStr} remaining
      </div>

      <div className="w-full max-w-md">
        <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${Math.min(progressPct, 100)}%` }}
          />
        </div>
        <p className="text-sm text-text-secondary text-center mt-2">
          {Math.round(progressPct)}%
        </p>
      </div>
    </div>
  );
}

function MediaPhase({
  config,
  onContinue,
}: {
  config: CustomPhaseConfig;
  onContinue: () => void;
}) {
  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="p-6 bg-surface rounded-xl border border-border">
        {config.title && (
          <h2 className="text-xl font-semibold text-text-primary mb-4">
            {config.title}
          </h2>
        )}

        {config.media_type === 'video' && config.media_url && (
          <video
            src={config.media_url}
            controls
            className="w-full rounded-lg mb-4"
          />
        )}

        {config.media_type === 'image' && config.media_url && (
          <img
            src={config.media_url}
            alt={config.caption ?? 'Media'}
            className="max-w-full rounded-lg mb-4"
          />
        )}

        {config.caption && (
          <MarkdownText
            content={config.caption}
            className="text-base text-text-primary mb-4"
          />
        )}

        <div className="flex justify-center mt-6">
          <button
            onClick={onContinue}
            className="py-4 px-8 rounded-xl text-lg font-semibold bg-primary text-white hover:bg-primary-light active:bg-primary-dark shadow-md transition-all duration-200 cursor-pointer"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}

function SurveyPhase({
  config,
  onSubmit,
}: {
  config: CustomPhaseConfig;
  onSubmit: (answers: Record<string, unknown>) => void;
}) {
  const questions = config.questions ?? [];
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [submitting, setSubmitting] = useState(false);

  function updateAnswer(id: string, value: unknown) {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }

  function handleSubmit() {
    setSubmitting(true);
    onSubmit(answers);
  }

  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="p-6 bg-surface rounded-xl border border-border">
        {config.title && (
          <h2 className="text-xl font-semibold text-text-primary mb-6">
            {config.title}
          </h2>
        )}

        <div className="space-y-6">
          {questions.map((q: QuestionConfig) => (
            <div key={q.id}>
              <label className="block text-sm font-medium text-text-primary mb-2">
                {q.label}
              </label>
              {renderSurveyQuestion(q, answers[q.id], (v) =>
                updateAnswer(q.id, v)
              )}
            </div>
          ))}
        </div>

        <div className="flex justify-center mt-8">
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className={`
              py-4 px-8 rounded-xl text-lg font-semibold shadow-md transition-all duration-200
              ${
                submitting
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer'
              }
            `}
          >
            {submitting ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
}

// Simplified question renderer for survey sub-phase
function renderSurveyQuestion(
  q: QuestionConfig,
  value: unknown,
  onChange: (v: unknown) => void
) {
  switch (q.type) {
    case 'slider': {
      const min = q.min ?? 0;
      const max = q.max ?? 10;
      const step = q.step ?? 1;
      const numVal = typeof value === 'number' ? value : (q.default as number) ?? min;
      const labels = q.scale_labels ?? {};
      return (
        <div>
          <div className="flex justify-between text-sm text-text-secondary mb-1">
            <span>{labels[String(min)] ?? min}</span>
            <span>{labels[String(max)] ?? max}</span>
          </div>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={numVal}
            onChange={(e) => onChange(Number(e.target.value))}
            className="w-full accent-primary"
          />
          <div className="text-center text-sm font-medium text-text-primary mt-1">
            {labels[String(numVal)] ?? numVal}
          </div>
        </div>
      );
    }

    case 'pillbox': {
      const labels = q.scale_labels ?? {};
      let pills: { key: string; label: string }[] = [];
      if (q.options?.length) {
        pills = q.options.map((opt) => ({ key: opt, label: labels[opt] ?? opt }));
      } else if (q.min !== undefined && q.max !== undefined) {
        for (let i = q.min; i <= q.max; i++) {
          pills.push({ key: String(i), label: labels[String(i)] ?? String(i) });
        }
      }
      return (
        <div className="flex flex-wrap gap-2">
          {pills.map((p) => {
            const selected = String(value) === p.key;
            return (
              <button
                key={p.key}
                type="button"
                onClick={() => onChange(q.options ? p.key : Number(p.key))}
                className={`px-4 py-2 rounded-xl text-sm font-medium border transition-all duration-200 cursor-pointer ${
                  selected
                    ? 'bg-primary/10 border-2 border-primary text-primary'
                    : 'border-border bg-white text-text-primary hover:border-primary/40'
                }`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      );
    }

    case 'dropdown':
      return (
        <select
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
        >
          <option value="">Select...</option>
          {(q.options ?? []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );

    case 'text_input':
      return (
        <input
          type="text"
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
        />
      );

    case 'text_area':
      return (
        <textarea
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary resize-y"
        />
      );

    default:
      return null;
  }
}

// ─── MAIN COMPONENT ────────────────────────────────────────────────────────

export default function CustomPhasePage() {
  const { sessionId, phaseId } = useParams<{
    sessionId: string;
    phaseId: string;
  }>();
  const navigate = useNavigate();

  const [phaseConfig, setPhaseConfig] = useState<CustomPhaseConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId || !phaseId) return;

    api
      .get(`/sessions/${sessionId}`)
      .then((res) => {
        const config = res.data.experiment_config;
        const phases: Array<{ id?: string; phase_id?: string } & CustomPhaseConfig> =
          config?.phase_sequence ?? config?.custom_phases ?? [];

        const match = phases.find(
          (p) => (p.id ?? p.phase_id) === phaseId
        );

        if (match) {
          setPhaseConfig(match);
        } else {
          setError(`Phase "${phaseId}" not found in protocol configuration.`);
        }
      })
      .catch(() => {
        setError('Failed to load phase configuration.');
      })
      .finally(() => setLoading(false));
  }, [sessionId, phaseId]);

  async function advancePhase() {
    if (!sessionId) return;
    try {
      const res = await api.post(`/sessions/${sessionId}/phase`, {
        phase: 'next',
      });
      const nextPhase: string | undefined = res.data?.current_phase;

      // Route based on the phase the backend returned
      if (!nextPhase || nextPhase === 'complete') {
        navigate(`/subject/${sessionId}/complete`);
      } else if (nextPhase === 'selection') {
        navigate(`/subject/${sessionId}/select`);
      } else if (nextPhase === 'questionnaire') {
        navigate(`/subject/${sessionId}/questionnaire`);
      } else if (nextPhase === 'instructions') {
        navigate(`/subject/${sessionId}/instructions`);
      } else if (nextPhase === 'robot_preparing') {
        navigate(`/subject/${sessionId}/preparing`);
      } else {
        // Assume custom phase
        navigate(`/subject/${sessionId}/phase/${nextPhase}`);
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || 'Failed to advance phase';
      setError(detail);
    }
  }

  async function handleSurveySubmit(answers: Record<string, unknown>) {
    if (!sessionId) return;
    try {
      await api.post(`/sessions/${sessionId}/response`, {
        answers,
        phase_id: phaseId,
        is_final: true,
      });
      await advancePhase();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || 'Failed to submit survey';
      setError(detail);
    }
  }

  if (loading) {
    return (
      <PageLayout showLogo={false}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <p className="text-base text-text-secondary">Loading...</p>
        </div>
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout showLogo={false}>
        <div className="max-w-2xl mx-auto mt-8">
          <div className="p-3 bg-red-50 text-red-700 rounded-lg text-base">
            {error}
          </div>
        </div>
      </PageLayout>
    );
  }

  if (!phaseConfig) return null;

  return (
    <PageLayout showLogo={false}>
      {phaseConfig.type === 'text' && (
        <TextPhase config={phaseConfig} onContinue={advancePhase} />
      )}

      {phaseConfig.type === 'break' && (
        <BreakPhase config={phaseConfig} onComplete={advancePhase} />
      )}

      {phaseConfig.type === 'media' && (
        <MediaPhase config={phaseConfig} onContinue={advancePhase} />
      )}

      {phaseConfig.type === 'survey' && (
        <SurveyPhase config={phaseConfig} onSubmit={handleSurveySubmit} />
      )}
    </PageLayout>
  );
}
