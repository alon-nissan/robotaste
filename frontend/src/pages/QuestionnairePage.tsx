import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { phaseToPath } from '../utils/phases';
import type { QuestionConfig, QuestionnaireConfig } from '../types';
import PageLayout from '../components/PageLayout';
import QuestionRenderer, { QuestionLabel } from '../components/questions/QuestionRenderer';
import {
  firstUnanswered,
  initialAnswers,
  isAnswered,
  mustAnswer,
  useAnswerMeta,
} from '../utils/questionnaire';

function delay(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

const DEFAULT_QUESTIONS: QuestionConfig[] = [
  {
    id: 'overall_liking',
    label: 'Overall Liking',
    type: 'pillbox',
    min: 1,
    max: 5,
    scale_labels: {
      '1': '😖 Hate',
      '2': '🙁 Dislike',
      '3': '😐 Okay',
      '4': '🙂 Like',
      '5': '😄 Love',
    },
  },
];

export default function QuestionnairePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [questions, setQuestions] = useState<QuestionConfig[]>(DEFAULT_QUESTIONS);
  const [title, setTitle] = useState('How did you find this sample?');
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayMode, setDisplayMode] = useState<'all_at_once' | 'one_at_a_time'>('all_at_once');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [seed, setSeed] = useState('');
  const meta = useAnswerMeta();

  useEffect(() => {
    if (!sessionId) return;

    api
      .get(`/sessions/${sessionId}/status`)
      .then((res) => {
        const config = res.data.experiment_config;
        // Seed for randomised option orders: stable within a cycle, different across cycles.
        setSeed(`${sessionId}:${res.data.current_cycle ?? ''}`);

        const qConfig: QuestionnaireConfig | undefined = config?.questionnaire;
        if (qConfig?.questions?.length) {
          setQuestions(qConfig.questions);
          if (qConfig.title) setTitle(qConfig.title);
          if (qConfig.display_mode) setDisplayMode(qConfig.display_mode);
          setAnswers(initialAnswers(qConfig.questions));
          meta.reset();
        }
      })
      .catch(() => {
        // Use defaults on error
      });
  }, [sessionId, meta]);

  // Start each question's response-time clock when it appears on screen.
  useEffect(() => {
    if (displayMode === 'one_at_a_time') {
      const q = questions[currentIndex];
      if (q) meta.markShown([q.id]);
    } else {
      meta.markShown(questions.map((q) => q.id));
    }
  }, [questions, displayMode, currentIndex, meta]);

  function updateAnswer(id: string, value: unknown) {
    meta.recordChange(id);
    setAnswers((prev) => ({ ...prev, [id]: value }));
    setError(null);
  }

  function missingMessage(q: QuestionConfig) {
    return `Please answer "${q.label}" before continuing.`;
  }

  function handleNext() {
    const q = questions[currentIndex];
    if (mustAnswer(q) && !isAnswered(q, answers[q.id])) {
      setError(missingMessage(q));
      return;
    }
    setError(null);
    setCurrentIndex((i) => i + 1);
  }

  function handleBack() {
    setError(null);
    setCurrentIndex((i) => Math.max(0, i - 1));
  }

  async function handleSubmit() {
    if (!sessionId) return;

    const missing = firstUnanswered(questions, answers);
    if (missing) {
      if (displayMode === 'one_at_a_time') {
        setCurrentIndex(questions.findIndex((q) => q.id === missing.id));
      }
      setError(missingMessage(missing));
      return;
    }

    // Only send answers to configured questions; drop unanswered optional ones.
    const payload: Record<string, unknown> = {};
    for (const q of questions) {
      if (isAnswered(q, answers[q.id])) payload[q.id] = answers[q.id];
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await api.post(`/sessions/${sessionId}/response`, {
        answers: payload,
        answer_meta: meta.build(questions),
        is_final: true,
      });

      const nextPhase: string = res.data.next_phase;

      if (nextPhase === 'complete' || nextPhase === 'completion') {
        navigate(phaseToPath(nextPhase, sessionId!));
        return;
      }

      // Next cycle: check mode to decide routing. Both predetermined and BO
      // ('bo_selected') cycles are system-selected and auto-advance without a
      // manual pick; other modes route to the selection page as usual. If BO
      // isn't ready yet (no concentrations returned), fall through to the
      // selection page, which itself retries the auto-submit and falls back
      // to manual selection if BO still isn't ready.
      const cycleRes = await api.get(`/sessions/${sessionId}/cycle-info`);
      const cycleInfo = cycleRes.data;
      const mode: string = cycleInfo.mode || 'user_selected';
      const isPredetermined = mode.startsWith('predetermined');
      const isBO = mode === 'bo_selected';
      const isBOAutoAccept = isBO && Boolean(cycleInfo?.metadata?.auto_accept_suggestion);

      if ((isPredetermined || isBO) && cycleInfo.concentrations) {
        // Auto-submit the system-selected concentrations
        const selRes = await api.post(`/sessions/${sessionId}/selection`, {
          concentrations: cycleInfo.concentrations,
          selection_mode: mode,
          selection_data: cycleInfo.selection_data,
        });
        const pumpEnabled = selRes.data.pump_enabled;
        navigate(pumpEnabled
          ? `/subject/${sessionId}/cup-ready`
          : `/subject/${sessionId}/tasting`
        );
      } else if (isBOAutoAccept) {
        // Auto-accept BO mode should not expose manual selection.
        // Retry briefly, then hand off to selection page which keeps auto-retrying.
        let prepared = false;
        for (let attempt = 0; attempt < 3; attempt++) {
          await delay(1000);
          const retryCycleRes = await api.get(`/sessions/${sessionId}/cycle-info`);
          const retryCycleInfo = retryCycleRes.data;
          if (retryCycleInfo?.concentrations) {
            const selRes = await api.post(`/sessions/${sessionId}/selection`, {
              concentrations: retryCycleInfo.concentrations,
              selection_mode: retryCycleInfo.mode,
              selection_data: retryCycleInfo.selection_data,
            });
            const pumpEnabled = selRes.data.pump_enabled;
            navigate(pumpEnabled
              ? `/subject/${sessionId}/cup-ready`
              : `/subject/${sessionId}/tasting`
            );
            prepared = true;
            break;
          }
        }
        if (!prepared) {
          navigate(`/subject/${sessionId}/select`);
        }
      } else {
        navigate(phaseToPath(nextPhase, sessionId!));
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || 'Failed to submit response';
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  const isSequential = displayMode === 'one_at_a_time';
  const isLastQuestion = currentIndex === questions.length - 1;

  return (
    <PageLayout showLogo={false}>
      <div className="max-w-4xl mx-auto mt-4 sm:mt-8">
        <div className="p-4 sm:p-6 bg-surface rounded-xl border border-border">
          <h2 className="text-xl font-semibold text-text-primary mb-6">
            {title}
          </h2>

          {isSequential ? (
            <>
              <div className="flex items-center justify-between mb-6">
                <span className="text-sm text-text-secondary whitespace-nowrap mr-3">
                  Question {currentIndex + 1} of {questions.length}
                </span>
                <div className="flex gap-1 min-w-0">
                  {questions.map((_, i) => (
                    <div
                      key={i}
                      className={`h-1.5 w-3 sm:w-6 shrink rounded-full transition-colors duration-200 ${
                        i <= currentIndex ? 'bg-primary' : 'bg-border'
                      }`}
                    />
                  ))}
                </div>
              </div>

              <div key={questions[currentIndex].id}>
                <QuestionLabel question={questions[currentIndex]} sequential />
                <QuestionRenderer
                  question={questions[currentIndex]}
                  value={answers[questions[currentIndex].id]}
                  onChange={(v) => updateAnswer(questions[currentIndex].id, v)}
                  seed={seed}
                  onOptionOrder={(order) => meta.recordOptionOrder(questions[currentIndex].id, order)}
                />
              </div>
            </>
          ) : (
            <div className="space-y-10">
              {questions.map((q) => (
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
          )}

          {error && (
            <div role="alert" className="mt-6 p-3 bg-red-50 text-red-700 rounded-lg text-base">
              ⚠️ {error}
            </div>
          )}

          <div className="mt-8 flex justify-center gap-3">
            {isSequential && currentIndex > 0 && (
              <button
                onClick={handleBack}
                className="py-4 px-6 rounded-xl text-lg font-medium border border-border bg-white text-text-primary hover:bg-gray-100 transition-colors cursor-pointer"
              >
                Back
              </button>
            )}
            {isSequential && !isLastQuestion ? (
              <button
                onClick={handleNext}
                className="py-4 px-8 rounded-xl text-lg font-semibold shadow-md transition-all duration-200 bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer"
              >
                Next
              </button>
            ) : (
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
                {submitting ? 'Submitting...' : 'Submit Response'}
              </button>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
