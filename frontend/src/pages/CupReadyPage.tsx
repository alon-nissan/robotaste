import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';

export default function CupReadyPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (!sessionId || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/sessions/${sessionId}/confirm-cup-ready`);
      navigate(`/subject/${sessionId}/preparing`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to confirm. Please try again.');
      setSubmitting(false);
    }
  }

  return (
    <PageLayout showLogo={false}>
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="text-6xl mb-6">🥤</div>

        <h2 className="text-2xl font-semibold text-text-primary mb-4">
          Place a clean cup under the spout
        </h2>

        <p className="text-base text-text-secondary mb-8 max-w-md text-center">
          Make sure a clean cup is positioned correctly before dispensing begins.
        </p>

        <button
          onClick={handleConfirm}
          disabled={submitting}
          className="px-8 py-3 bg-primary text-white text-lg font-medium rounded-xl hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {submitting ? 'Starting...' : 'Yes, dispense'}
        </button>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm max-w-md">
            {error}
          </div>
        )}
      </div>
    </PageLayout>
  );
}
