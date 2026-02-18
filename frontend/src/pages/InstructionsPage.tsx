/**
 * InstructionsPage — Display experiment instructions before starting.
 *
 * Fetches instruction content from the session's experiment_config.
 * Participant must acknowledge understanding before proceeding.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';

interface InstructionContent {
  title: string;
  text: string;
  callout: string | null;
  confirm_label: string;
  button_label: string;
}

const DEFAULT_INSTRUCTIONS: InstructionContent = {
  title: 'Experiment Instructions',
  text: [
    'Welcome to this taste experiment. You will be asked to evaluate a series of samples.',
    'For each round, you will be presented with a sample to taste. Please take your time and focus on the flavors you experience.',
    'After tasting each sample, you will be asked to answer a few questions about your experience.',
    'Please be honest and rely on your own perception — there are no right or wrong answers.',
  ].join('\n\n'),
  callout: 'Important: Rinse your mouth with water between each sample to ensure accurate results.',
  confirm_label: 'I have read and understand the above instructions',
  button_label: 'Start Experiment →',
};

export default function InstructionsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  // ─── STATE ──────────────────────────────────────────────────────────────
  const [instructions, setInstructions] = useState<InstructionContent>(DEFAULT_INSTRUCTIONS);
  const [understood, setUnderstood] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // ─── FETCH INSTRUCTIONS ─────────────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) return;

    async function fetchInstructions() {
      try {
        const res = await api.get(`/sessions/${sessionId}`);
        const config = res.data?.experiment_config;
        if (!config) {
          setLoading(false);
          return;
        }

        // Look for instruction content in protocol config
        const screen = config.instructions_screen;

        if (screen) {
          setInstructions({
            title: screen.title || DEFAULT_INSTRUCTIONS.title,
            text: screen.text || DEFAULT_INSTRUCTIONS.text,
            callout: screen.callout || DEFAULT_INSTRUCTIONS.callout,
            confirm_label: screen.confirm_label || DEFAULT_INSTRUCTIONS.confirm_label,
            button_label: screen.button_label || DEFAULT_INSTRUCTIONS.button_label,
          });
        }
      } catch {
        // Use default instructions on fetch failure
      } finally {
        setLoading(false);
      }
    }

    fetchInstructions();
  }, [sessionId]);

  // ─── PROCEED ────────────────────────────────────────────────────────────
  async function handleProceed() {
    if (!understood || !sessionId) return;

    setSubmitting(true);
    setError(null);

    try {
      // Get cycle info to determine selection mode
      const cycleRes = await api.get(`/sessions/${sessionId}/cycle-info`);
      const cycleInfo = cycleRes.data;
      const mode: string = cycleInfo.mode || 'user_selected';
      const isPredetermined = mode.startsWith('predetermined');

      if (isPredetermined && cycleInfo.concentrations) {
        // Auto-submit the predetermined selection and skip to next phase
        const selRes = await api.post(`/sessions/${sessionId}/selection`, {
          concentrations: cycleInfo.concentrations,
          selection_mode: mode,
        });
        const pumpEnabled = selRes.data.pump_enabled;
        if (pumpEnabled) {
          navigate(`/subject/${sessionId}/preparing`);
        } else {
          navigate(`/subject/${sessionId}/questionnaire`);
        }
      } else {
        // User-selected or BO mode: go to selection page
        await api.post(`/sessions/${sessionId}/phase`, { phase: 'selection' });
        navigate(`/subject/${sessionId}/select`);
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to proceed. Please try again.';
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  // ─── RENDER ─────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <PageLayout>
        <div className="max-w-2xl mx-auto text-center py-12 text-text-secondary">
          Loading instructions...
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <div className="max-w-2xl mx-auto">
        <div className="p-6 bg-surface rounded-xl border border-border">
          {/* Title */}
          <h1 className="text-2xl font-light text-text-primary tracking-wide mb-4">
            {instructions.title}
          </h1>
          <hr className="border-border mb-6" />

          {/* Instruction text — render paragraphs split by newlines */}
          <div className="space-y-4 text-text-primary leading-relaxed mb-6">
            {instructions.text.split('\n\n').map((paragraph, i) => (
              <p key={i}>{paragraph}</p>
            ))}
          </div>

          {/* Callout */}
          {instructions.callout && (
            <div className="p-4 bg-surface rounded-lg border-l-4 border-primary mb-6">
              <p className="text-text-primary text-sm">
                {instructions.callout}
              </p>
            </div>
          )}

          {/* Acknowledgement checkbox */}
          <label className="flex items-start gap-3 cursor-pointer mb-6 select-none">
            <input
              type="checkbox"
              checked={understood}
              onChange={(e) => setUnderstood(e.target.checked)}
              className="mt-0.5 h-5 w-5 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-sm text-text-primary">
              {instructions.confirm_label}
            </span>
          </label>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm mb-4">
              {error}
            </div>
          )}

          {/* Proceed button */}
          <button
            onClick={handleProceed}
            disabled={!understood || submitting}
            className={`
              w-full py-4 px-8 rounded-xl text-lg font-semibold
              shadow-md transition-all duration-200
              ${understood && !submitting
                ? 'bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }
            `}
          >
            {submitting ? 'Starting...' : instructions.button_label}
          </button>
        </div>
      </div>
    </PageLayout>
  );
}
