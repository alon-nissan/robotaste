/**
 * ProtocolWizardPage — Multi-step protocol creation wizard.
 *
 * Guides non-technical users through building a valid protocol JSON
 * by asking questions in plain English across themed steps.
 *
 * Routes:
 *   /protocols/new         — create a new protocol
 *   /protocols/:id/edit    — edit an existing protocol (future)
 */

import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { ProtocolDraft } from '../types';
import { WizardProvider, useWizard, WIZARD_STEPS } from '../context/WizardContext';
import WizardShell from '../components/wizard/WizardShell';
import Step1Overview from '../components/wizard/steps/Step1Overview';
import Step2Ingredients from '../components/wizard/steps/Step2Ingredients';
import Step3Schedule from '../components/wizard/steps/Step3Schedule';
import Step4Questionnaire from '../components/wizard/steps/Step4Questionnaire';
import Step5Optimization from '../components/wizard/steps/Step5Optimization';
import Step6Experience from '../components/wizard/steps/Step6Experience';
import Step7Pumps from '../components/wizard/steps/Step7Pumps';
import ReviewStep from '../components/wizard/steps/ReviewStep';

interface ProtocolValidationResponse {
  valid: boolean;
  errors: string[];
}

function WizardContent({ isEdit, protocolId }: { isEdit: boolean; protocolId?: string }) {
  const { state } = useWizard();
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      // Strip undefined values before server-side validation/persist.
      const protocol = JSON.parse(JSON.stringify(state.protocol));
      const validation = await api.post<ProtocolValidationResponse>('/protocols/validate', protocol);
      if (!validation.data.valid) {
        setError(validation.data.errors.join(' | '));
        return;
      }
      if (isEdit && protocolId) {
        await api.put(`/protocols/${protocolId}`, protocol);
      } else {
        await api.post('/protocols', protocol);
      }
      navigate('/protocols');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      const msg = typeof detail === 'string'
        ? detail
        : err instanceof Error
          ? err.message
          : 'Failed to save protocol';
      setError(msg);
    } finally {
      setSaving(false);
    }
  }, [state.protocol, navigate, isEdit, protocolId]);

  const stepId = WIZARD_STEPS[state.currentStep]?.id;

  return (
    <WizardShell onSave={handleSave} saving={saving}>
      {error && (
        <div className="mb-6 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
          {error}
        </div>
      )}
      {stepId === 'overview' && <Step1Overview />}
      {stepId === 'ingredients' && <Step2Ingredients />}
      {stepId === 'schedule' && <Step3Schedule />}
      {stepId === 'questionnaire' && <Step4Questionnaire />}
      {stepId === 'optimization' && <Step5Optimization />}
      {stepId === 'experience' && <Step6Experience />}
      {stepId === 'pumps' && <Step7Pumps />}
      {stepId === 'review' && <ReviewStep />}
    </WizardShell>
  );
}

export default function ProtocolWizardPage() {
  const { id } = useParams<{ id: string }>();
  const [initialProtocol, setInitialProtocol] = useState<ProtocolDraft | undefined>(undefined);
  const [loadingProtocol, setLoadingProtocol] = useState(!!id);

  useEffect(() => {
    if (!id) return;
    api.get(`/protocols/${id}`)
      .then((res) => setInitialProtocol(res.data as ProtocolDraft))
      .catch(() => { /* proceed with empty draft on error */ })
      .finally(() => setLoadingProtocol(false));
  }, [id]);

  if (loadingProtocol) {
    return <div className="flex items-center justify-center h-screen text-text-secondary">Loading protocol…</div>;
  }

  return (
    <WizardProvider initialProtocol={initialProtocol}>
      <WizardContent isEdit={!!id} protocolId={id} />
    </WizardProvider>
  );
}
