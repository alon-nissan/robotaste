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
 * │ │ Select Protocol   │  │ Import / Upload    │ │
 * │ │ [dropdown ▼]      │  │ [drag-drop zone]   │ │
 * │ │ [summary card]    │  │ [Documentation]    │ │
 * │ └───────────────────┘  └───────────────────┘ │
 * │                                              │
 * │ ┌───────────────────┐  ┌───────────────────┐ │
 * │ │ Pump Setup        │  │                    │ │
 * │ │ Sol I [XX.XX mL]  │  │   [Start Button]  │ │
 * │ │ Sol II [XX.XX mL] │  │                    │ │
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

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Protocol } from '../types';

// Import our child components
import PageLayout from '../components/PageLayout';
import ProtocolSelector from '../components/ProtocolSelector';
import ProtocolUpload from '../components/ProtocolUpload';
import DocumentationLinks from '../components/DocumentationLinks';
import PumpSetup from '../components/PumpSetup';

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

  // React Router's navigation hook — lets us redirect to the monitoring page
  const navigate = useNavigate();


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
      const pumpVols = selectedProtocol.pump_config?.enabled ? pumpVolumes : undefined;
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

      {/* ═══ TOP ROW: Protocol Selection + Import (2-column grid) ═══ */}
      {/* grid grid-cols-2: Creates a 2-column grid layout */}
      {/* gap-6: 24px spacing between columns */}
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

        {/* RIGHT COLUMN: Import + Documentation */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          <ProtocolUpload onUploadSuccess={handleUploadSuccess} />
          <DocumentationLinks />
        </div>
      </div>

      {/* ═══ BOTTOM ROW: Pump Setup + Start Button (2-column grid) ═══ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* LEFT COLUMN: Pump Setup (only shows when pumps are enabled) */}
        <div className="p-6 bg-surface rounded-xl border border-border">
          {selectedProtocol?.pump_config?.enabled ? (
            <PumpSetup
              protocol={selectedProtocol}
              volumes={pumpVolumes}
              onVolumesChange={setPumpVolumes}
            />
          ) : (
            <div className="text-base text-text-secondary">
              {selectedProtocol
                ? '🔧 Pumps not enabled in this protocol'
                : 'Select a protocol to see pump configuration'}
            </div>
          )}
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
    </PageLayout>
  );
}
