/**
 * ModeratorSetupPage — Protocol Selection Dashboard (Page I from sketch)
 *
 * === WHAT THIS PAGE DOES ===
 * This is the main moderator page for setting up an experiment.
 * It matches the hand-drawn sketch "Moderator_protocol_selection_view_draft":
 *
 * ┌──────────────────────────────────────────────┐
 * │ [Logo]                                       │
 * │ Moderator Dashboard                          │
 * │                                              │
 * │ ┌───────────────────┐  ┌───────────────────┐ │
 * │ │ Select Protocol   │  │ Pump Status        │ │
 * │ │ [dropdown ▼]      │  │ Sol I  [████░░] XX%│ │
 * │ │ [summary card]    │  │ Sol II [██████] XX%│ │
 * │ └───────────────────┘  └───────────────────┘ │
 * │                                              │
 * │ ┌───────────────────┐  ┌───────────────────┐ │
 * │ │ Import / Upload   │  │                    │ │
 * │ │ [drag-drop zone]  │  │   [Start Button]  │ │
 * │ │ [Documentation]   │  │                    │ │
 * │ └───────────────────┘  └───────────────────┘ │
 * └──────────────────────────────────────────────┘
 *
 * === KEY CONCEPTS ===
 *
 * STATE LIFTING:
 * This page "owns" the state (selected protocol, volumes, session).
 * Child components receive data via props and report changes via callbacks.
 * This is the standard React pattern — state lives in the nearest common
 * ancestor of all components that need it.
 *
 * LAYOUT WITH CSS GRID:
 * We use Tailwind's grid classes to create the 2-column layout:
 *   `grid grid-cols-2 gap-6` = 2 equal columns with 24px gaps
 * This gives us the spatial control that Streamlit's st.columns() lacks.
 *
 * useNavigate:
 * React Router's hook for programmatic navigation.
 * Like st.rerun() but navigates to a different URL.
 */

import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Protocol, PumpGlobalStatus } from '../types';

// Import our child components
import PageLayout from '../components/PageLayout';
import ProtocolSelector from '../components/ProtocolSelector';
import ProtocolUpload from '../components/ProtocolUpload';
import DocumentationLinks from '../components/DocumentationLinks';
import PumpSetup from '../components/PumpSetup';
import RefillWizard from '../components/RefillWizard';

export default function ModeratorSetupPage() {
  // ─── STATE ─────────────────────────────────────────────────────────────
  // This page owns all the state that child components need

  // The selected protocol (null = nothing selected)
  const [selectedProtocol, setSelectedProtocol] = useState<Protocol | null>(null);

  // Pump volumes per ingredient { "Sugar": 50.0, "Salt": 50.0 }
  const [pumpVolumes, setPumpVolumes] = useState<Record<string, number>>({});

  // Session ID (set after creating a session)
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Session code (6-char code for subjects to join)
  const [sessionCode, setSessionCode] = useState<string | null>(null);

  // UI state
  const [starting, setStarting] = useState(false);         // Is the start button loading?
  const [error, setError] = useState<string | null>(null);  // Error message

  // Counter to force ProtocolSelector to re-fetch after upload
  const [refreshKey, setRefreshKey] = useState(0);

  // Global pump status (cross-session volume tracking)
  const [globalPumpStatus, setGlobalPumpStatus] = useState<PumpGlobalStatus | null>(null);

  // Refill wizard state
  const [refillTarget, setRefillTarget] = useState<{
    ingredient: string;
    pumpAddress: number;
  } | null>(null);

  // React Router's navigation hook — lets us redirect to the monitoring page
  const navigate = useNavigate();

  // Fetch global pump status when protocol changes
  useEffect(() => {
    if (!selectedProtocol?.pump_config?.enabled || !selectedProtocol.protocol_id) {
      setGlobalPumpStatus(null);
      return;
    }

    async function fetchGlobalStatus() {
      try {
        const { data } = await api.get<PumpGlobalStatus>(
          `/pump/global-status/${selectedProtocol!.protocol_id}`
        );
        setGlobalPumpStatus(data);

        // Sync pumpVolumes from global state so Start Session uses real values
        if (data.pump_enabled && data.ingredients) {
          const synced: Record<string, number> = {};
          for (const [name, info] of Object.entries(data.ingredients)) {
            synced[name] = info.current_ul / 1000; // µL → mL
          }
          if (Object.keys(synced).length > 0) {
            setPumpVolumes(synced);
          }
        }
      } catch {
        setGlobalPumpStatus(null);
      }
    }

    fetchGlobalStatus();
  }, [selectedProtocol?.protocol_id, selectedProtocol?.pump_config?.enabled]);


  // ─── HANDLERS ──────────────────────────────────────────────────────────

  // Called when user selects a protocol from the dropdown
  // useCallback: Memoizes the function so it doesn't get recreated every render.
  // This is a performance optimization — not strictly necessary but good practice.
  const handleProtocolSelect = useCallback((protocol: Protocol | null) => {
    setSelectedProtocol(protocol);
    setError(null);

    // Initialize pump volumes with defaults when protocol changes
    if (protocol?.pump_config?.enabled && protocol.ingredients) {
      const defaults: Record<string, number> = {};
      protocol.ingredients.forEach(ing => {
        defaults[ing.name] = 50.0;  // Default 50 mL
      });
      setPumpVolumes(defaults);
    } else {
      setPumpVolumes({});
    }
  }, []);

  // Called when upload succeeds — increment key to force re-fetch
  function handleUploadSuccess() {
    setRefreshKey(prev => prev + 1);
  }

  // Called when the Start button is clicked
  async function handleStart() {
    if (!selectedProtocol) {
      setError('Please select a protocol first');
      return;
    }

    setStarting(true);
    setError(null);

    try {
      // Step 1: Create a new session
      const sessionRes = await api.post('/sessions', {
        moderator_name: 'Research Team',  // Could add an input for this later
      });
      const newSessionId = sessionRes.data.session_id;
      const newSessionCode = sessionRes.data.session_code;
      setSessionId(newSessionId);
      setSessionCode(newSessionCode);

      // Step 2: Start the session with the selected protocol
      // Only send pump_volumes when the moderator entered them via PumpSetup
      // (i.e. no existing global state). When global state exists, send undefined
      // so the API carries over volumes from pump_global_state.
      const hasGlobalState = globalPumpStatus?.pump_enabled &&
        Object.keys(globalPumpStatus.ingredients).length > 0;
      const pumpVols = selectedProtocol.pump_config?.enabled && !hasGlobalState
        ? pumpVolumes
        : undefined;
      await api.post(`/sessions/${newSessionId}/start`, {
        protocol_id: selectedProtocol.protocol_id,
        pump_volumes: pumpVols,
      });

      // Step 3: Navigate to the monitoring page
      // The session ID is passed as a URL query parameter so the monitoring
      // page knows which session to display.
      navigate(`/moderator/monitoring?session=${newSessionId}`);

    } catch (err: unknown) {
      const errorDetail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to start session';
      setError(errorDetail);
    } finally {
      setStarting(false);
    }
  }


  // ─── RENDER ────────────────────────────────────────────────────────────
  return (
    <PageLayout>
      {/* Page title */}
      <h1 className="text-2xl font-light text-text-primary tracking-wide mb-8">
        Moderator Dashboard
      </h1>

      {/* ═══ TOP ROW: Protocol Selection + Pump Status (2-column grid) ═══ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">

        {/* LEFT COLUMN: Protocol Selector */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          {/* key={refreshKey} forces React to recreate this component when the key changes,
              which triggers a fresh API fetch after uploading a new protocol */}
          <ProtocolSelector
            key={refreshKey}
            onSelect={handleProtocolSelect}
          />
        </div>

        {/* RIGHT COLUMN: Pump Status (only shows when pumps are enabled) */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          {selectedProtocol?.pump_config?.enabled ? (
            <div className="space-y-6">
              {/* Global pump status (cross-session volumes) — shown when state exists */}
              {globalPumpStatus?.pump_enabled && Object.keys(globalPumpStatus.ingredients).length > 0 ? (
                <div>
                  <h3 className="text-lg font-semibold text-text-primary mb-3">
                    Pump Volume Status
                  </h3>
                  <div className="space-y-3">
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
                </div>
              ) : (
                /* No global state yet — show initial volume inputs */
                <PumpSetup
                  protocol={selectedProtocol}
                  volumes={pumpVolumes}
                  onVolumesChange={setPumpVolumes}
                />
              )}
            </div>
          ) : (
            <div className="text-base text-text-secondary">
              {selectedProtocol
                ? '🔧 Pumps not enabled in this protocol'
                : 'Select a protocol to see pump configuration'}
            </div>
          )}
        </div>
      </div>

      {/* ═══ BOTTOM ROW: Import/Docs + Start Button (2-column grid) ═══ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* LEFT COLUMN: Import + Documentation */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          <ProtocolUpload onUploadSuccess={handleUploadSuccess} />
          <DocumentationLinks />
        </div>

        {/* RIGHT COLUMN: Start Button */}
        <div className="p-6 flex flex-col justify-center items-center">
          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-base w-full">
              {error}
            </div>
          )}

          {/* Start button */}
          <button
            onClick={handleStart}
            disabled={!selectedProtocol || starting}
            className={`
              w-full max-w-xs py-4 px-8 rounded-xl text-lg font-semibold
              transition-all duration-200 shadow-md
              ${selectedProtocol && !starting
                ? 'bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }
            `}
          >
            {starting ? 'Starting...' : '▶ Start Session'}
          </button>

          {/* Session info (shown after session is created) */}
          {sessionId && (
            <div className="mt-4 p-4 bg-surface rounded-xl border border-border text-center w-full max-w-xs">
              <p className="text-sm text-text-secondary mb-1">Session Code (share with participants)</p>
              <p className="text-3xl font-bold tracking-widest text-primary">{sessionCode}</p>
            </div>
          )}
        </div>
      </div>

      {/* Refill Wizard Modal */}
      {refillTarget && selectedProtocol && (
        <RefillWizard
          protocolId={selectedProtocol.protocol_id}
          pumpAddress={refillTarget.pumpAddress}
          ingredient={refillTarget.ingredient}
          onComplete={() => {
            setRefillTarget(null);
            // Refresh global pump status
            if (selectedProtocol?.protocol_id) {
              api.get<PumpGlobalStatus>(`/pump/global-status/${selectedProtocol.protocol_id}`)
                .then(({ data }) => setGlobalPumpStatus(data))
                .catch(() => {});
            }
          }}
          onCancel={() => setRefillTarget(null)}
        />
      )}
    </PageLayout>
  );
}
