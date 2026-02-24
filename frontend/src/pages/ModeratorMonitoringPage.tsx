/**
 * ModeratorMonitoringPage — Live experiment monitoring (Page II from sketch)
 *
 * === WHAT THIS PAGE DOES ===
 * This is the live monitoring dashboard shown after starting a session.
 * It matches the hand-drawn sketch "Moderator_monitoring_view_draft":
 *
 * ┌──────────────────────────────────────────────┐
 * │ [Logo]                                       │
 * │                                              │
 * │ ┌──────────────────────────────────────────┐ │
 * │ │    Mode-Specific Monitoring Chart        │ │
 * │ │    (large visualization area)            │ │
 * │ └──────────────────────────────────────────┘ │
 * │                                              │
 * │ ┌─────────────────┐  Pump Status:           │
 * │ │ Cycle: 1/X      │  Sol I  [████░░] XX%   │
 * │ │ Status: active   │  Sol II [██████] XX%   │
 * │ │ Phase: selection  │  [Refill] [Refill]     │
 * │ └─────────────────┘                          │
 * │                                              │
 * │ [End Session]                                │
 * └──────────────────────────────────────────────┘
 *
 * === KEY CONCEPTS ===
 *
 * POLLING:
 * Unlike Streamlit which reruns the entire script, React components
 * stay alive in memory. We use setInterval() to poll the API every
 * few seconds and update state, which triggers a re-render.
 *
 * URL QUERY PARAMETERS:
 * The session ID comes from the URL: /moderator/monitoring?session=abc-123
 * We extract it using React Router's useSearchParams() hook.
 *
 * CONDITIONAL RENDERING:
 * We show different content based on state:
 *   {loading && <Spinner />}           — Show while loading
 *   {error && <ErrorMessage />}        — Show if error
 *   {data && <MainContent />}          — Show when data is ready
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { SessionStatus, PumpGlobalStatus, ModeInfo, Sample } from '../types';

import PageLayout from '../components/PageLayout';
import SubjectConnectionCard from '../components/SubjectConnectionCard';
import RefillWizard from '../components/RefillWizard';

export default function ModeratorMonitoringPage() {
  // ─── URL PARAMS ────────────────────────────────────────────────────────
  // useSearchParams reads query parameters from the URL.
  // Example URL: /moderator/monitoring?session=abc-123
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session');  // Extract session ID from URL
  const navigate = useNavigate();

  // ─── STATE ─────────────────────────────────────────────────────────────
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [globalPumpStatus, setGlobalPumpStatus] = useState<PumpGlobalStatus | null>(null);
  const [modeInfo, setModeInfo] = useState<ModeInfo | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);

  // Refill wizard state
  const [refillTarget, setRefillTarget] = useState<{
    ingredient: string;
    pumpAddress: number;
  } | null>(null);

  // ─── FETCH DATA ────────────────────────────────────────────────────────
  // This function fetches all monitoring data from the API.
  // It's wrapped in useCallback so it can be used in useEffect and setInterval.
  const fetchData = useCallback(async () => {
    if (!sessionId) return;

    try {
      // Fetch all data in parallel using Promise.all
      // This sends all 3 requests simultaneously (much faster than sequential)
      const [statusRes, modeRes, samplesRes] = await Promise.all([
        api.get(`/sessions/${sessionId}/status`),
        api.get(`/sessions/${sessionId}/mode-info`),
        api.get(`/sessions/${sessionId}/samples`),
      ]);

      setStatus(statusRes.data);
      setModeInfo(modeRes.data);
      setSamples(samplesRes.data.samples || []);

      // Fetch global pump status using protocol_id from experiment_config
      const protocolId = statusRes.data?.experiment_config?.protocol_id;
      if (protocolId) {
        try {
          const pumpRes = await api.get<PumpGlobalStatus>(`/pump/global-status/${protocolId}`);
          setGlobalPumpStatus(pumpRes.data);
        } catch {
          setGlobalPumpStatus(null);
        }
      }

      setError(null);

    } catch (err) {
      console.error('Error fetching monitoring data:', err);
      setError('Failed to fetch session data');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);


  // ─── POLLING (auto-refresh every 5 seconds) ───────────────────────────
  useEffect(() => {
    if (!sessionId) {
      setError('No session ID provided');
      setLoading(false);
      return;
    }

    // Fetch immediately
    fetchData();

    // Then fetch every 5 seconds
    // setInterval: Calls a function repeatedly at a fixed interval.
    // This is like Streamlit's `time.sleep(5); st.rerun()` pattern.
    const interval = setInterval(fetchData, 5000);

    // Cleanup: when the component unmounts (user navigates away),
    // stop the polling to prevent memory leaks.
    // This return function is called automatically by React.
    return () => clearInterval(interval);
  }, [sessionId, fetchData]);


  // ─── END SESSION HANDLER ──────────────────────────────────────────────
  async function handleEndSession() {
    if (!sessionId) return;

    // Confirm with the user before ending
    const confirmed = window.confirm(
      'Are you sure you want to end this session? This cannot be undone.'
    );
    if (!confirmed) return;

    setEnding(true);
    try {
      await api.post(`/sessions/${sessionId}/end`);
      // Navigate back to setup page
      navigate('/moderator/setup');
    } catch (err) {
      setError('Failed to end session');
    } finally {
      setEnding(false);
    }
  }


  // ─── REFRESH PUMP STATUS ─────────────────────────────────────────────
  const refreshPumpStatus = useCallback(() => {
    const protocolId = (status?.experiment_config as Record<string, unknown>)?.protocol_id as string;
    if (protocolId) {
      api.get<PumpGlobalStatus>(`/pump/global-status/${protocolId}`)
        .then(({ data }) => setGlobalPumpStatus(data))
        .catch(() => {});
    }
  }, [status?.experiment_config]);


  // ─── LOADING STATE ────────────────────────────────────────────────────
  if (loading) {
    return (
      <PageLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-text-secondary text-lg">Loading session data...</div>
        </div>
      </PageLayout>
    );
  }

  if (error && !status) {
    return (
      <PageLayout>
        <div className="p-6 bg-red-50 rounded-xl text-red-700">
          <h2 className="font-semibold mb-2">Error</h2>
          <p>{error}</p>
          <button
            onClick={() => navigate('/moderator/setup')}
            className="mt-4 px-4 py-2 bg-primary text-white rounded-lg"
          >
            ← Back to Setup
          </button>
        </div>
      </PageLayout>
    );
  }

  // ─── DERIVED VALUES ───────────────────────────────────────────────────
  const maxCycles = (status?.experiment_config as Record<string, unknown>)
    ?.stopping_criteria
    ? ((status?.experiment_config as Record<string, Record<string, number>>)
        ?.stopping_criteria?.max_cycles || 0)
    : 0;


  // ─── RENDER ────────────────────────────────────────────────────────────
  return (
    <PageLayout>
      {/* ═══ SESSION CODE BANNER ═══ */}
      {status?.session_code && (
        <div className="flex items-center gap-3 mb-6 p-3 bg-surface rounded-xl border border-border">
          <span className="text-sm text-text-secondary">Session Code:</span>
          <span className="text-xl font-bold tracking-widest text-primary">{status.session_code}</span>
        </div>
      )}

      {/* ═══ MONITORING CHART (large area) ═══ */}
      <div className="bg-surface rounded-xl border border-border p-6 mb-6 min-h-[300px]">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          {modeInfo?.current_mode
            ? `${modeInfo.current_mode.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())} Mode`
            : 'Monitoring'}
        </h2>

        {/* Samples table */}
        {samples.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-2 text-text-secondary font-medium">Cycle</th>
                  <th className="text-left p-2 text-text-secondary font-medium">Concentrations</th>
                  <th className="text-left p-2 text-text-secondary font-medium">Response</th>
                  <th className="text-left p-2 text-text-secondary font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((sample, i) => (
                  <tr key={i} className="border-b border-border/50">
                    <td className="p-2 font-medium">{sample.cycle_number}</td>
                    <td className="p-2 text-text-secondary">
                      {Object.entries(sample.ingredient_concentration || {})
                        .map(([name, val]) => `${name}: ${(val as number).toFixed(2)} mM`)
                        .join(', ')}
                    </td>
                    <td className="p-2">
                      {sample.questionnaire_answer
                        ? Object.entries(sample.questionnaire_answer)
                            .filter(([k]) => !['questionnaire_type', 'participant_id', 'timestamp', 'is_final'].includes(k))
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(', ')
                        : '—'}
                    </td>
                    <td className="p-2 text-text-secondary text-xs">
                      {sample.created_at?.slice(0, 19) || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 text-text-secondary">
            <p>No samples yet. Waiting for participant to start tasting...</p>
          </div>
        )}
      </div>

      {/* ═══ BOTTOM ROW: Status Card + Pump Status + Subject Connection ═══ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">

        {/* LEFT: Cycle Status Card */}
        <div className="bg-surface rounded-xl border border-border p-6">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
            Session Status
          </h3>

          <div className="space-y-3">
            {/* Cycle counter */}
            <div className="flex justify-between items-center">
              <span className="text-text-secondary">Cycle</span>
              <span className="text-2xl font-bold text-text-primary">
                {status?.current_cycle || 0}
                {maxCycles > 0 && <span className="text-text-secondary text-base font-normal"> / {maxCycles}</span>}
              </span>
            </div>

            {/* Status */}
            <div className="flex justify-between items-center">
              <span className="text-text-secondary">Status</span>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                status?.state === 'active'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {status?.state || 'unknown'}
              </span>
            </div>

            {/* Phase */}
            <div className="flex justify-between items-center">
              <span className="text-text-secondary">Phase</span>
              <span className="text-sm font-medium text-text-primary">
                {status?.current_phase?.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Unknown'}
              </span>
            </div>

            {/* Mode */}
            <div className="flex justify-between items-center">
              <span className="text-text-secondary">Mode</span>
              <span className="text-sm font-medium text-text-primary">
                {modeInfo?.current_mode?.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Unknown'}
              </span>
            </div>
          </div>
        </div>

        {/* MIDDLE: Pump Status (global cross-session volumes) */}
        <div className="bg-surface rounded-xl border border-border p-6">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
            Pump Status
          </h3>

          {globalPumpStatus?.pump_enabled ? (
            <div className="space-y-4">
              {Object.entries(globalPumpStatus.ingredients).map(([name, ingStatus]) => (
                <div key={name}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm font-medium text-text-primary">
                      {ingStatus.alert_active && '⚠️ '}{name}
                    </span>
                    <span className="text-sm text-text-secondary">
                      {ingStatus.percent_remaining.toFixed(0)}%
                    </span>
                  </div>

                  <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        ingStatus.alert_active ? 'bg-red-500' : 'bg-primary'
                      }`}
                      style={{ width: `${Math.min(100, ingStatus.percent_remaining)}%` }}
                    />
                  </div>

                  <div className="flex justify-between items-center mt-1">
                    <span className="text-xs text-text-secondary">
                      {(ingStatus.current_ul / 1000).toFixed(1)} / {(ingStatus.max_capacity_ul / 1000).toFixed(1)} mL
                    </span>
                    <button
                      onClick={() => setRefillTarget({ ingredient: name, pumpAddress: ingStatus.pump_address })}
                      className="text-xs text-primary hover:text-primary-light underline"
                    >
                      Refill
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-text-secondary">
              Pumps not enabled for this session
            </div>
          )}
        </div>

        {/* RIGHT: Subject Connection */}
        <SubjectConnectionCard />
      </div>

      {/* ═══ END SESSION BUTTON ═══ */}
      <div className="flex justify-end">
        <button
          onClick={handleEndSession}
          disabled={ending}
          className="px-6 py-3 bg-red-600 text-white rounded-lg font-medium
                     hover:bg-red-700 active:bg-red-800 transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {ending ? 'Ending...' : '🛑 End Session'}
        </button>
      </div>

      {/* Refill Wizard Modal */}
      {refillTarget && status?.experiment_config && (
        <RefillWizard
          protocolId={(status.experiment_config as Record<string, unknown>).protocol_id as string}
          pumpAddress={refillTarget.pumpAddress}
          ingredient={refillTarget.ingredient}
          onComplete={() => {
            setRefillTarget(null);
            refreshPumpStatus();
          }}
          onCancel={() => setRefillTarget(null)}
        />
      )}
    </PageLayout>
  );
}
