import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { AnswerMeta, CustomPhaseConfig, QuestionConfig } from '../types';
import PageLayout from '../components/PageLayout';
import { MarkdownText } from '../components/MarkdownText';
import QuestionRenderer, { QuestionLabel } from '../components/questions/QuestionRenderer';
import {
  firstUnanswered,
  initialAnswers,
  isAnswered,
  mustAnswer,
  useAnswerMeta,
} from '../utils/questionnaire';

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
  seed,
  onSubmit,
}: {
  config: CustomPhaseConfig;
  seed: string;
  onSubmit: (answers: Record<string, unknown>, answerMeta: Record<string, AnswerMeta>) => Promise<void>;
}) {
  const questions = useMemo(() => config.questions ?? [], [config.questions]);
  const [answers, setAnswers] = useState<Record<string, unknown>>(() => initialAnswers(questions));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const meta = useAnswerMeta();

  useEffect(() => {
    meta.markShown(questions.map((q) => q.id));
  }, [questions, meta]);

  function updateAnswer(id: string, value: unknown) {
    meta.recordChange(id);
    setAnswers((prev) => ({ ...prev, [id]: value }));
    setError(null);
  }

  async function handleSubmit() {
    const missing = firstUnanswered(questions, answers);
    if (missing) {
      setError(`Please answer "${missing.label}" before continuing.`);
      return;
    }
    const payload: Record<string, unknown> = {};
    for (const q of questions) {
      if (isAnswered(q, answers[q.id])) payload[q.id] = answers[q.id];
    }
    setSubmitting(true);
    try {
      await onSubmit(payload, meta.build(questions));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto mt-4 sm:mt-8">
      <div className="p-4 sm:p-6 bg-surface rounded-xl border border-border">
        {config.title && (
          <h2 className="text-xl font-semibold text-text-primary mb-6">
            {config.title}
          </h2>
        )}

        <div className="space-y-8">
          {questions.map((q: QuestionConfig) => (
            <div key={q.id}>
              <QuestionLabel question={q} sequential={false} required={mustAnswer(q)} />
              <QuestionRenderer
                question={q}
                value={answers[q.id]}
                onChange={(v) => updateAnswer(q.id, v)}
                seed={seed}
                onOptionOrder={(order) => meta.recordOptionOrder(q.id, order)}
              />
            </div>
          ))}
        </div>

        {error && (
          <div role="alert" className="mt-6 p-3 bg-red-50 text-red-700 rounded-lg text-base">
            ⚠️ {error}
          </div>
        )}

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

  async function handleSurveySubmit(
    answers: Record<string, unknown>,
    answerMeta: Record<string, AnswerMeta>
  ) {
    if (!sessionId) return;
    try {
      await api.post(`/sessions/${sessionId}/response`, {
        answers,
        answer_meta: answerMeta,
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
        <SurveyPhase
          config={phaseConfig}
          seed={`${sessionId}:${phaseId}`}
          onSubmit={handleSurveySubmit}
        />
      )}
    </PageLayout>
  );
}
