import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';
import type { CycleInfo, TastingScreenConfig } from '../types';

/**
 * TastingPage — "Taste the sample" step before each questionnaire.
 *
 * Pump flow: reached after the robot dispenses the sample.
 * No-pump flow (hand-served, pre-prepared solutions): reached right after the
 * (auto-submitted) selection. Shows the cup code the moderator is serving,
 * configurable via the protocol's `tasting_screen` block. If
 * `tasting_screen.enabled === false`, skips straight to the questionnaire.
 */

const DEFAULT_TITLE_WITH_ID = 'Please taste cup {sample_id}';
const DEFAULT_TITLE = 'Taste the sample';
const DEFAULT_TEXT =
  'Take a sip and evaluate the sample carefully. Press the button when you are done tasting.';

function fill(template: string, sampleId: string | null): string {
  return template.replace(/\{sample_id\}/g, sampleId ?? '').replace(/\s+$/, '');
}

export default function TastingPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [ready, setReady] = useState(false);
  const [config, setConfig] = useState<TastingScreenConfig>({});
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [cycle, setCycle] = useState<number | null>(null);
  const [totalCycles, setTotalCycles] = useState<number | null>(null);

  async function goToQuestionnaire() {
    try {
      await api.post(`/sessions/${sessionId}/phase`, { phase: 'questionnaire' });
    } catch {
      // best-effort — navigate regardless
    }
    navigate(`/subject/${sessionId}/questionnaire`);
  }

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    (async () => {
      try {
        const [sessionRes, cycleRes] = await Promise.all([
          api.get(`/sessions/${sessionId}`),
          api.get<CycleInfo>(`/sessions/${sessionId}/cycle-info`),
        ]);
        if (cancelled) return;
        const expConfig = sessionRes.data?.experiment_config ?? {};
        const tastingScreen: TastingScreenConfig = expConfig.tasting_screen ?? {};
        const pumpEnabled = Boolean(expConfig.pump_config?.enabled);

        if (!pumpEnabled && tastingScreen.enabled === false) {
          await goToQuestionnaire();
          return;
        }

        setConfig(tastingScreen);
        setSampleId(cycleRes.data?.metadata?.sample_id ?? null);
        setCycle(cycleRes.data?.current_cycle ?? null);
        setTotalCycles(expConfig.stopping_criteria?.max_cycles ?? null);
      } catch {
        // Fall back to the generic tasting screen
      }
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function handleDone() {
    if (!sessionId || submitting) return;
    setSubmitting(true);
    await goToQuestionnaire();
  }

  const showId = config.show_sample_id !== false && Boolean(sampleId);
  const title = fill(
    config.title ?? (showId ? DEFAULT_TITLE_WITH_ID : DEFAULT_TITLE),
    showId ? sampleId : null,
  );
  const text = fill(config.text ?? DEFAULT_TEXT, showId ? sampleId : null);

  if (!ready) {
    return (
      <PageLayout showLogo={false}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-text-secondary text-lg">Loading...</div>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout showLogo={false}>
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        {cycle !== null && (
          <p className="text-sm uppercase tracking-wide text-text-secondary mb-4">
            Sample {cycle}{totalCycles ? ` of ${totalCycles}` : ''}
          </p>
        )}

        <div className="text-6xl mb-6">👅</div>

        <h2 className="text-3xl font-bold text-text-primary mb-4 text-center">
          {title}
        </h2>

        {showId && !(config.title ?? DEFAULT_TITLE_WITH_ID).includes('{sample_id}') && (
          <div className="text-6xl font-bold text-primary mb-6">{sampleId}</div>
        )}

        <p className="text-xl text-text-secondary mb-10 max-w-md text-center whitespace-pre-line">
          {text}
        </p>

        <button
          onClick={handleDone}
          disabled={submitting}
          className="px-10 py-4 bg-primary text-white text-xl font-semibold rounded-xl hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {submitting ? 'Loading...' : (config.button_label ?? 'Done tasting')}
        </button>
      </div>
    </PageLayout>
  );
}
