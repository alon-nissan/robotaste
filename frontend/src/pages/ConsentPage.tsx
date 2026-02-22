/**
 * ConsentPage — Informed consent screen before participation.
 *
 * Displays consent information from the protocol config (or sensible defaults)
 * and requires the participant to agree before proceeding to registration.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { ConsentConfig } from '../types';

import PageLayout from '../components/PageLayout';
import { MarkdownText } from '../components/MarkdownText';

const DEFAULT_EXPLANATION =
  'This experiment investigates taste perception. You will be asked to taste ' +
  'small samples of flavored solutions and provide your feedback through a ' +
  'short questionnaire after each sample.';

const DEFAULT_BULLETS = [
  'You will taste multiple small samples during the session.',
  'After each sample, you will answer a brief questionnaire.',
  'You may withdraw from the study at any time without penalty.',
  'All responses are recorded anonymously.',
];

const DEFAULT_MEDICAL_NOTICE =
  'If you have any food allergies, dietary restrictions, or medical conditions ' +
  'that may be affected by tasting flavored solutions, please inform the ' +
  'researcher before proceeding.';

const DEFAULT_CONTACT = 'researcher@university.edu';

export default function ConsentPage() {
  // ─── STATE ─────────────────────────────────────────────────────────────
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [consent, setConsent] = useState<ConsentConfig | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ─── FETCH SESSION CONSENT CONFIG ──────────────────────────────────────
  useEffect(() => {
    async function fetchConsent() {
      try {
        const res = await api.get(`/sessions/${sessionId}`);
        const config = res.data.experiment_config?.consent_form as ConsentConfig | undefined;
        setConsent(config ?? null);
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail || 'Failed to load session';
        setError(detail);
      } finally {
        setLoading(false);
      }
    }
    fetchConsent();
  }, [sessionId]);

  // ─── HANDLERS ──────────────────────────────────────────────────────────

  async function handleContinue() {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/sessions/${sessionId}/consent`, { consent_given: true });
      await api.post(`/sessions/${sessionId}/phase`, { phase: 'registration' });
      navigate(`/subject/${sessionId}/register`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to record consent';
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  // ─── DERIVED VALUES ────────────────────────────────────────────────────
  const explanation = consent?.explanation || DEFAULT_EXPLANATION;
  const disclaimers = consent?.medical_disclaimers;
  const contact = consent?.contact_info || DEFAULT_CONTACT;
  const checkboxLabel = consent?.consent_label || 'I have read and agree to participate';

  // ─── RENDER ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center py-20">
          <p className="text-base text-text-secondary">Loading consent information...</p>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <div className="max-w-3xl mx-auto">
        <div className="p-6 bg-surface rounded-xl border border-border">
          <h1 className="text-2xl font-light text-text-primary tracking-wide mb-8">
            Informed Consent
          </h1>

          {/* Error */}
          {error && (
            <div className="mb-6 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Study Purpose */}
          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">Study Purpose</h2>
            <MarkdownText content={explanation} className="text-base text-text-primary" />
          </section>

          {/* What to Expect */}
          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">What to Expect</h2>
            <ul className="list-disc list-inside space-y-1 text-base text-text-primary">
              {DEFAULT_BULLETS.map((bullet, i) => (
                <li key={i}>{bullet}</li>
              ))}
            </ul>
          </section>

          {/* Medical Notice */}
          <section className="mb-6">
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <h3 className="text-sm font-semibold text-amber-800 mb-1">⚠️ Medical Notice</h3>
              <p className="text-sm text-amber-700">
                {disclaimers && disclaimers.length > 0
                  ? disclaimers.join(' ')
                  : DEFAULT_MEDICAL_NOTICE}
              </p>
            </div>
          </section>

          {/* Contact */}
          <section className="mb-8">
            <h2 className="text-lg font-semibold mb-1">Contact</h2>
            <MarkdownText content={contact} className="text-base text-text-primary" />
          </section>

          {/* Consent Checkbox */}
          <label className="flex items-center gap-3 mb-6 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={agreed}
              onChange={e => setAgreed(e.target.checked)}
              className="w-5 h-5 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-text-primary text-sm">{checkboxLabel}</span>
          </label>

          {/* Continue Button */}
          <button
            onClick={handleContinue}
            disabled={!agreed || submitting}
            className={`
              w-full py-4 px-8 rounded-xl text-lg font-semibold
              transition-all duration-200 shadow-md
              ${agreed && !submitting
                ? 'bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }
            `}
          >
            {submitting ? 'Submitting...' : 'Continue'}
          </button>
        </div>
      </div>
    </PageLayout>
  );
}
