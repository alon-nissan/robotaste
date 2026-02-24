import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { phaseToPath } from '../utils/phases';
import type { QuestionConfig, QuestionnaireConfig } from '../types';
import PageLayout from '../components/PageLayout';

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

function SliderQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: number;
  onChange: (v: number) => void;
}) {
  const min = question.min ?? 0;
  const max = question.max ?? 10;
  const step = question.step ?? 1;
  const labels = question.scale_labels ?? {};

  // Collect all labeled keys sorted numerically
  const labelKeys = Object.keys(labels)
    .map(Number)
    .filter((n) => !isNaN(n))
    .sort((a, b) => a - b);

  // Thumb position as a percentage
  const thumbPercent = ((value - min) / (max - min)) * 100;

  return (
    <div>
      {/* Scale labels evenly spaced above the slider */}
      {labelKeys.length > 0 && (
        <div className="flex justify-between text-sm text-text-secondary mb-1">
          {labelKeys.map((key) => (
            <span key={key} className="text-center flex-1">
              {labels[String(key)]}
            </span>
          ))}
        </div>
      )}

      {/* Current value floating above the thumb */}
      <div className="relative mb-1">
        <div
          className="text-center text-sm font-semibold text-primary"
          style={{ marginLeft: `calc(${thumbPercent}% - 1rem)`, width: '2rem' }}
        >
          {typeof value === 'number' ? value.toFixed(step < 1 ? 2 : 0) : value}
        </div>
      </div>

      {/* Styled range slider */}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="slider-range w-full"
      />

      {/* Fallback: show only min/max if no scale labels defined */}
      {labelKeys.length === 0 && (
        <div className="flex justify-between text-sm text-text-secondary mt-1">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      )}
    </div>
  );
}

function PillboxQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: number | string | undefined;
  onChange: (v: number | string) => void;
}) {
  const labels = question.scale_labels ?? {};

  // Build pills from options or min/max range
  let pills: { key: string; label: string }[] = [];
  if (question.options && question.options.length > 0) {
    pills = question.options.map((opt) => ({
      key: opt,
      label: labels[opt] ?? opt,
    }));
  } else if (question.min !== undefined && question.max !== undefined) {
    for (let i = question.min; i <= question.max; i++) {
      pills.push({ key: String(i), label: labels[String(i)] ?? String(i) });
    }
  }

  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {pills.map((pill) => {
        const selected = String(value) === pill.key;
        return (
          <button
            key={pill.key}
            type="button"
            onClick={() =>
              onChange(question.options ? pill.key : Number(pill.key))
            }
            className={`
              px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200
              border cursor-pointer
              ${
                selected
                  ? 'bg-primary/10 border-2 border-primary text-primary'
                  : 'border-border bg-white text-text-primary hover:border-primary/40'
              }
            `}
          >
            {pill.label}
          </button>
        );
      })}
    </div>
  );
}

function DropdownQuestion({
  question,
  value,
  onChange,
}: {
  question: QuestionConfig;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
    >
      <option value="">Select...</option>
      {(question.options ?? []).map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

function TextInputQuestion({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
    />
  );
}

function TextAreaQuestion({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={3}
      className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary resize-y"
    />
  );
}

function renderQuestion(
  question: QuestionConfig,
  value: unknown,
  onChange: (v: unknown) => void
) {
  switch (question.type) {
    case 'slider':
      return (
        <SliderQuestion
          question={question}
          value={typeof value === 'number' ? value : question.default as number ?? question.min ?? 5}
          onChange={onChange}
        />
      );
    case 'pillbox':
      return (
        <PillboxQuestion
          question={question}
          value={value as number | string | undefined}
          onChange={onChange}
        />
      );
    case 'dropdown':
      return (
        <DropdownQuestion
          question={question}
          value={typeof value === 'string' ? value : ''}
          onChange={onChange}
        />
      );
    case 'text_input':
      return (
        <TextInputQuestion
          value={typeof value === 'string' ? value : ''}
          onChange={onChange}
        />
      );
    case 'text_area':
      return (
        <TextAreaQuestion
          value={typeof value === 'string' ? value : ''}
          onChange={onChange}
        />
      );
    default:
      return null;
  }
}

export default function QuestionnairePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [questions, setQuestions] = useState<QuestionConfig[]>(DEFAULT_QUESTIONS);
  const [title, setTitle] = useState('How did you find this sample?');
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    api
      .get(`/sessions/${sessionId}`)
      .then((res) => {
        const config = res.data.experiment_config;

        const qConfig: QuestionnaireConfig | undefined = config?.questionnaire;
        if (qConfig?.questions?.length) {
          setQuestions(qConfig.questions);
          if (qConfig.title) setTitle(qConfig.title);

          // Initialize default values
          const defaults: Record<string, unknown> = {};
          qConfig.questions.forEach((q) => {
            if (q.default !== undefined) defaults[q.id] = q.default;
          });
          setAnswers(defaults);
        }
      })
      .catch(() => {
        // Use defaults on error
      });
  }, [sessionId]);

  function updateAnswer(id: string, value: unknown) {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }

  async function handleSubmit() {
    if (!sessionId) return;

    setSubmitting(true);
    setError(null);

    try {
      const res = await api.post(`/sessions/${sessionId}/response`, {
        answers,
        is_final: true,
      });

      const nextPhase: string = res.data.next_phase;

      if (nextPhase === 'complete' || nextPhase === 'completion') {
        navigate(phaseToPath(nextPhase, sessionId!));
        return;
      }

      // Next cycle: check mode to decide routing
      const cycleRes = await api.get(`/sessions/${sessionId}/cycle-info`);
      const cycleInfo = cycleRes.data;
      const mode: string = cycleInfo.mode || 'user_selected';
      const isPredetermined = mode.startsWith('predetermined');

      if (isPredetermined && cycleInfo.concentrations) {
        // Auto-submit predetermined selection
        const selRes = await api.post(`/sessions/${sessionId}/selection`, {
          concentrations: cycleInfo.concentrations,
          selection_mode: mode,
        });
        const pumpEnabled = selRes.data.pump_enabled;
        navigate(pumpEnabled
          ? `/subject/${sessionId}/cup-ready`
          : `/subject/${sessionId}/questionnaire`
        );
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

  return (
    <PageLayout showLogo={false}>
      <div className="max-w-4xl mx-auto mt-8">
        <div className="p-6 bg-surface rounded-xl border border-border">
          <h2 className="text-xl font-semibold text-text-primary mb-6">
            {title}
          </h2>

          <div className="space-y-8">
            {questions.map((q) => (
              <div key={q.id}>
                <label className="block text-sm font-medium text-text-primary mb-3">
                  {q.label}
                  {q.required === false ? '' : ''}
                </label>
                {renderQuestion(q, answers[q.id], (v) =>
                  updateAnswer(q.id, v)
                )}
              </div>
            ))}
          </div>

          {error && (
            <div className="mt-6 p-3 bg-red-50 text-red-700 rounded-lg text-base">
              {error}
            </div>
          )}

          <div className="mt-8 flex justify-center">
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
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
