/**
 * ProtocolSelector Component — Dropdown to select an experiment protocol.
 *
 * === WHAT THIS COMPONENT DOES ===
 * 1. Fetches the list of protocols from the API on mount
 * 2. Displays a dropdown for the user to pick one
 * 3. Shows a summary card of the selected protocol
 * 4. Calls onSelect(protocol) when the selection changes
 *
 * === KEY CONCEPTS ===
 *
 * HOOKS (functions that start with "use"):
 * - useState: Creates a piece of state (like st.session_state in Streamlit).
 *   Returns [currentValue, setterFunction]. When you call the setter,
 *   React re-renders the component with the new value.
 *
 * - useEffect: Runs code when the component first appears ("mounts") or
 *   when specified values change. We use it to fetch data from the API.
 *   The empty array [] means "run only once when component first renders".
 *
 * PROPS:
 * - Props are parameters passed to a component from its parent.
 *   Like function arguments in Python:
 *     Python:  def greet(name: str): ...
 *     React:   function Greet({ name }: { name: string }) { ... }
 *
 * - `onSelect`: A callback function — the parent passes a function,
 *   and we call it when the user selects a protocol. This is how child
 *   components communicate back to parent components.
 */

import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { Protocol } from '../types';

// Define the props (parameters) this component accepts
interface Props {
  onSelect: (protocol: Protocol | null) => void;  // Callback when selection changes
}

export default function ProtocolSelector({ onSelect }: Props) {
  // ─── STATE ─────────────────────────────────────────────────────────────
  // useState creates reactive state variables.
  // When these change, React automatically re-renders the component.

  // List of all protocols fetched from the API
  const [protocols, setProtocols] = useState<Protocol[]>([]);

  // The currently selected protocol (null = nothing selected)
  const [selected, setSelected] = useState<Protocol | null>(null);

  // Loading state (true while fetching from API)
  const [loading, setLoading] = useState(true);

  // Error message (null = no error)
  const [error, setError] = useState<string | null>(null);


  // ─── FETCH PROTOCOLS ON MOUNT ──────────────────────────────────────────
  // useEffect runs side effects (API calls, timers, etc.)
  // The [] dependency array means: "run this once when the component first appears"
  useEffect(() => {
    // Define an async function to fetch data
    // (useEffect itself can't be async, so we define one inside)
    async function fetchProtocols() {
      try {
        setLoading(true);
        // api.get() returns a response object; .data contains the actual JSON
        const response = await api.get('/protocols');
        setProtocols(response.data);
      } catch (err) {
        setError('Failed to load protocols');
        console.error('Error fetching protocols:', err);
      } finally {
        // 'finally' runs whether the try succeeded or failed
        setLoading(false);
      }
    }

    fetchProtocols();
  }, []); // Empty array = run once on mount


  // ─── HANDLE SELECTION CHANGE ───────────────────────────────────────────
  // Called when the user picks a different option in the dropdown
  function handleChange(event: React.ChangeEvent<HTMLSelectElement>) {
    // event.target.value is the value of the selected <option>
    const protocolId = event.target.value;

    if (!protocolId) {
      setSelected(null);
      onSelect(null);
      return;
    }

    // Find the full protocol object from our list
    const protocol = protocols.find(p => p.protocol_id === protocolId) || null;
    setSelected(protocol);
    onSelect(protocol);  // Notify parent component
  }


  // ─── RENDER ────────────────────────────────────────────────────────────
  // Everything below is JSX — React's HTML-like syntax.
  // className uses Tailwind CSS utility classes for styling.

  if (loading) {
    return (
      <div className="p-4 text-text-secondary">Loading protocols...</div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-600">{error}</div>
    );
  }

  return (
    <div>
      {/* Section title */}
      <h3 className="text-lg font-semibold text-text-primary mb-3">
        Select Protocol
      </h3>

      {/* Dropdown (select element) */}
      {/* Tailwind classes: w-full = full width, p-3 = padding, border = border, rounded-lg = rounded corners */}
      <select
        value={selected?.protocol_id || ''}
        onChange={handleChange}
        className="w-full p-3 border border-border rounded-lg bg-white text-text-primary
                   focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
      >
        <option value="">-- Choose a protocol --</option>
        {/* Map over protocols array to create <option> elements */}
        {/* .map() is like Python's list comprehension: [f(x) for x in list] */}
        {protocols.map(p => (
          <option key={p.protocol_id} value={p.protocol_id}>
            {p.name} (v{p.version || '1.0'})
          </option>
        ))}
      </select>

      {/* Protocol summary card — only shown when a protocol is selected */}
      {selected && (
        // mt-4 = margin-top, p-4 = padding, border-l-4 = thick left border
        <div className="mt-4 p-4 bg-surface rounded-lg border-l-4 border-primary">
          <h4 className="text-base font-medium text-text-primary mb-1">
            {selected.name}
          </h4>
          <p className="text-sm text-text-secondary mb-3">
            {selected.description || 'No description provided.'}
          </p>

          {/* Key metrics in a row */}
          <div className="flex gap-6 text-sm">
            <div>
              <span className="text-text-secondary">Cycles: </span>
              <span className="font-medium">
                {selected.stopping_criteria?.max_cycles || 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-text-secondary">Ingredients: </span>
              <span className="font-medium">
                {selected.ingredients?.length || 0}
              </span>
            </div>
            <div>
              <span className="text-text-secondary">Questionnaire: </span>
              <span className="font-medium">
                {selected.questionnaire_type?.replace('_', ' ') || 'N/A'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Empty state — no protocols in database */}
      {protocols.length === 0 && (
        <p className="mt-3 text-sm text-text-secondary">
          No protocols found. Upload a JSON file to create one.
        </p>
      )}
    </div>
  );
}
