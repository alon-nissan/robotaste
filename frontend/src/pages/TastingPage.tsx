import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';

export default function TastingPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  async function handleDone() {
    if (!sessionId || submitting) return;
    setSubmitting(true);
    try {
      await api.post(`/sessions/${sessionId}/phase`, { phase: 'questionnaire' });
    } catch {
      // best-effort — navigate regardless
    }
    navigate(`/subject/${sessionId}/questionnaire`);
  }

  return (
    <PageLayout showLogo={false}>
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="text-6xl mb-6">👅</div>

        <h2 className="text-3xl font-bold text-text-primary mb-4 text-center">
          Taste the sample
        </h2>

        <p className="text-xl text-text-secondary mb-10 max-w-md text-center">
          Take a sip and evaluate the sample carefully. Press the button when you are done tasting.
        </p>

        <button
          onClick={handleDone}
          disabled={submitting}
          className="px-10 py-4 bg-primary text-white text-xl font-semibold rounded-xl hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {submitting ? 'Loading...' : 'Done tasting'}
        </button>
      </div>
    </PageLayout>
  );
}
