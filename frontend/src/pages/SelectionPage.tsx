/**
 * SelectionPage — Concentration selection for taste experiments.
 *
 * Renders EITHER a 2D SVG grid (2 ingredients) or a single slider
 * (1 ingredient), based on the session's protocol.
 *
 * Data flow:
 *   1. GET /sessions/{id}/status  → cycle, phase, mode
 *   2. GET /sessions/{id}         → experiment_config with ingredients
 *   3. GET /sessions/{id}/bo-suggestion (if bo_selected mode)
 *   4. POST /sessions/{id}/selection   → submit chosen concentrations
 *   5. GET /sessions/{id}/samples      → previous selections history
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type {
  Session,
  SessionStatus,
  Ingredient,
  BOSuggestion,
  Sample,
} from '../types';

import PageLayout from '../components/PageLayout';


// ─── HELPERS ──────────────────────────────────────────────────────────────────

/** Format a selection mode string for display. */
function formatMode(mode: string): string {
  const map: Record<string, string> = {
    user_selected: 'User Selected',
    bo_selected: 'BO Suggested',
    predetermined: 'Predetermined',
  };
  return map[mode] ?? mode.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** Clamp a number between min and max. */
function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

/** Round to one decimal place. */
function round1(val: number): number {
  return Math.round(val * 10) / 10;
}


// ─── CONSTANTS ────────────────────────────────────────────────────────────────

const GRID_SIZE = 400;
const GRID_PADDING = 50; // space for axis labels


// ─── MAIN COMPONENT ──────────────────────────────────────────────────────────

export default function SelectionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  // ─── STATE ──────────────────────────────────────────────────────────────
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [boSuggestion, setBoSuggestion] = useState<BOSuggestion | null>(null);
  const [selectedConcentrations, setSelectedConcentrations] = useState<Record<string, number>>({});
  const [samples, setSamples] = useState<Sample[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [suggestionDismissed, setSuggestionDismissed] = useState(false);

  // ─── FETCH DATA ─────────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    if (!sessionId) return;

    try {
      const [statusRes, sessionRes, samplesRes] = await Promise.all([
        api.get(`/sessions/${sessionId}/status`),
        api.get(`/sessions/${sessionId}`),
        api.get(`/sessions/${sessionId}/samples`),
      ]);

      const statusData: SessionStatus = statusRes.data;
      const sessionData: Session = sessionRes.data;
      const fetchedSamples: Sample[] = samplesRes.data.samples || [];

      setStatus(statusData);
      setSession(sessionData);
      setSamples(fetchedSamples);

      // Extract ingredients from experiment_config
      const config = sessionData.experiment_config as Record<string, unknown> | undefined;
      const ings = (config?.ingredients as Ingredient[]) || [];
      setIngredients(ings);

      // Initialise concentrations with midpoints if not yet set
      setSelectedConcentrations(prev => {
        if (Object.keys(prev).length > 0) return prev;
        const defaults: Record<string, number> = {};
        for (const ing of ings) {
          defaults[ing.name] = round1((ing.min_concentration + ing.max_concentration) / 2);
        }
        return defaults;
      });

      // Determine current mode and fetch BO suggestion if needed
      const schedule = config?.sample_selection_schedule as Array<{
        cycle_range: { start: number; end: number };
        mode: string;
      }> | undefined;
      let currentMode = 'user_selected';
      if (schedule) {
        const cycle = statusData.current_cycle;
        for (const block of schedule) {
          if (cycle >= block.cycle_range.start && cycle <= block.cycle_range.end) {
            currentMode = block.mode;
            break;
          }
        }
      }

      if (currentMode === 'bo_selected') {
        try {
          const boRes = await api.get(`/sessions/${sessionId}/bo-suggestion`);
          setBoSuggestion(boRes.data);
        } catch {
          // BO may not be ready yet — ignore
          setBoSuggestion(null);
        }
      } else {
        setBoSuggestion(null);
      }

      setError(null);
    } catch (err) {
      console.error('Error fetching selection data:', err);
      setError('Failed to load session data');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      setError('No session ID provided');
      setLoading(false);
      return;
    }
    fetchData();
  }, [sessionId, fetchData]);


  // ─── CURRENT MODE (derived) ─────────────────────────────────────────────
  const currentMode = (() => {
    if (!status || !session) return 'user_selected';
    const config = session.experiment_config as Record<string, unknown> | undefined;
    const schedule = config?.sample_selection_schedule as Array<{
      cycle_range: { start: number; end: number };
      mode: string;
    }> | undefined;
    if (!schedule) return 'user_selected';
    const cycle = status.current_cycle;
    for (const block of schedule) {
      if (cycle >= block.cycle_range.start && cycle <= block.cycle_range.end) {
        return block.mode;
      }
    }
    return 'user_selected';
  })();

  const totalCycles = status?.total_cycles
    || ((session?.experiment_config as Record<string, Record<string, number>> | undefined)
        ?.stopping_criteria?.max_cycles)
    || 0;

  // ─── AUTO-SUBMIT FOR PREDETERMINED MODE ─────────────────────────────────
  const autoSubmitDone = useRef(false);
  useEffect(() => {
    if (!sessionId || !session || !status || loading || autoSubmitDone.current) return;
    if (!currentMode.startsWith('predetermined')) return;

    autoSubmitDone.current = true;

    (async () => {
      try {
        // Fetch cycle info for predetermined concentrations
        const cycleRes = await api.get(`/sessions/${sessionId}/cycle-info`);
        const cycleInfo = cycleRes.data;

        if (cycleInfo.concentrations) {
          const selRes = await api.post(`/sessions/${sessionId}/selection`, {
            concentrations: cycleInfo.concentrations,
            selection_mode: cycleInfo.mode,
          });
          const pumpEnabled = selRes.data.pump_enabled;
          navigate(pumpEnabled
            ? `/subject/${sessionId}/preparing`
            : `/subject/${sessionId}/questionnaire`
          );
        }
      } catch (err) {
        console.error('Auto-submit failed:', err);
        setError('Failed to auto-submit predetermined selection');
        autoSubmitDone.current = false;
      }
    })();
  }, [sessionId, session, status, loading, currentMode, navigate]);


  // ─── CONFIRM SELECTION ──────────────────────────────────────────────────
  async function handleConfirm() {
    if (!sessionId || ingredients.length === 0) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await api.post(`/sessions/${sessionId}/selection`, {
        concentrations: selectedConcentrations,
        selection_mode: currentMode,
      });

      const pumpEnabled = res.data.pump_enabled;
      if (pumpEnabled) {
        navigate(`/subject/${sessionId}/preparing`);
      } else {
        navigate(`/subject/${sessionId}/questionnaire`);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to submit selection';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }


  // ─── USE BO SUGGESTION ─────────────────────────────────────────────────
  function applySuggestion() {
    if (!boSuggestion?.concentrations) return;
    setSelectedConcentrations({ ...boSuggestion.concentrations });
    setSuggestionDismissed(true);
  }


  // ─── LOADING / ERROR STATES ─────────────────────────────────────────────
  if (loading) {
    return (
      <PageLayout showLogo={false}>
        <div className="flex items-center justify-center h-64">
          <div className="text-text-secondary text-lg">Loading...</div>
        </div>
      </PageLayout>
    );
  }

  if (error && !session) {
    return (
      <PageLayout showLogo={false}>
        <div className="p-6 bg-red-50 rounded-xl text-red-700">
          <h2 className="font-semibold mb-2">Error</h2>
          <p>{error}</p>
        </div>
      </PageLayout>
    );
  }


  // ─── RENDER ─────────────────────────────────────────────────────────────
  return (
    <PageLayout showLogo={false}>
      <div className="max-w-2xl mx-auto py-6 space-y-6">

        {/* ═══ MAIN CARD ═══ */}
        <div className="p-6 bg-surface rounded-xl border border-border">

          {/* Header: cycle + mode */}
          <div className="flex items-center justify-between mb-6">
            <span className="text-text-secondary text-sm">
              Cycle {status?.current_cycle ?? '–'} of {totalCycles || '–'}
            </span>
            <span className="text-text-secondary text-sm">
              Mode: {formatMode(currentMode)}
            </span>
          </div>

          {/* BO Suggestion box */}
          {currentMode === 'bo_selected' && boSuggestion && !suggestionDismissed && (
            <div className="p-4 bg-blue-50 border-l-4 border-blue-500 rounded-lg mb-6">
              <p className="text-sm font-medium text-blue-800 mb-2">
                🤖 The algorithm suggests:{' '}
                {Object.entries(boSuggestion.concentrations)
                  .map(([name, val]) => `${name} ${(val as number).toFixed(1)} mM`)
                  .join(', ')}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={applySuggestion}
                  className="px-4 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                >
                  Use Suggestion
                </button>
                <button
                  onClick={() => setSuggestionDismissed(true)}
                  className="px-4 py-1.5 rounded-lg text-sm font-medium bg-white text-blue-700 border border-blue-300 hover:bg-blue-50 transition-colors"
                >
                  Choose My Own
                </button>
              </div>
            </div>
          )}

          {/* Render slider or grid */}
          {ingredients.length === 1 ? (
            <SingleSlider
              ingredient={ingredients[0]}
              value={selectedConcentrations[ingredients[0].name] ?? 0}
              onChange={(val) =>
                setSelectedConcentrations(prev => ({ ...prev, [ingredients[0].name]: val }))
              }
            />
          ) : ingredients.length >= 2 ? (
            <Grid2D
              ingredientX={ingredients[0]}
              ingredientY={ingredients[1]}
              selectedX={selectedConcentrations[ingredients[0].name] ?? 0}
              selectedY={selectedConcentrations[ingredients[1].name] ?? 0}
              onSelect={(x, y) =>
                setSelectedConcentrations(prev => ({
                  ...prev,
                  [ingredients[0].name]: x,
                  [ingredients[1].name]: y,
                }))
              }
              previousSamples={samples}
            />
          ) : (
            <p className="text-base text-text-secondary text-center py-8">
              No ingredients configured for this experiment.
            </p>
          )}

          {/* Error message */}
          {error && (
            <div className="mt-4 p-3 bg-red-50 rounded-lg text-red-700 text-base">
              {error}
            </div>
          )}

          {/* Confirm button */}
          {ingredients.length > 0 && (
            <div className="flex justify-center mt-6">
              <button
                onClick={handleConfirm}
                disabled={submitting}
                className="py-4 px-8 rounded-xl text-lg font-semibold bg-primary text-white
                           hover:bg-primary-light active:bg-primary-dark shadow-md
                           transition-all duration-200
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Submitting...' : 'Confirm Selection'}
              </button>
            </div>
          )}
        </div>

        {/* ═══ HISTORY ═══ */}
        {samples.length > 0 && (
          <div className="text-sm text-text-secondary space-y-0.5">
            <p className="font-medium mb-1">Previous selections:</p>
            {samples.map((s) => {
              const concs = Object.entries(s.ingredient_concentration || {})
                .map(([, v]) => (v as number).toFixed(1))
                .join(', ');
              const response = s.questionnaire_answer
                ? Object.entries(s.questionnaire_answer)
                    .filter(([k]) => !['questionnaire_type', 'participant_id', 'timestamp', 'is_final'].includes(k))
                    .map(([, v]) => String(v))
                    .join(', ')
                : '—';
              return (
                <p key={s.cycle_number}>
                  Cycle {s.cycle_number}: ({concs}) → {response}
                </p>
              );
            })}
          </div>
        )}
      </div>
    </PageLayout>
  );
}


// ─── SINGLE SLIDER (1 ingredient) ────────────────────────────────────────────

interface SingleSliderProps {
  ingredient: Ingredient;
  value: number;
  onChange: (val: number) => void;
}

function SingleSlider({ ingredient, value, onChange }: SingleSliderProps) {
  const { name, min_concentration: min, max_concentration: max } = ingredient;
  const step = round1((max - min) / 200) || 0.1;

  return (
    <div className="space-y-6">
      <p className="text-base text-text-secondary">
        Select <span className="font-medium text-text-primary">{name}</span> concentration:
      </p>

      {/* Slider */}
      <div className="px-2">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(round1(parseFloat(e.target.value)))}
          className="w-full h-2 rounded-full appearance-none cursor-pointer
                     bg-gray-200 accent-primary"
        />
        <div className="flex justify-between text-sm text-text-secondary mt-1">
          <span>{min} mM</span>
          <span>{max} mM</span>
        </div>
      </div>

      {/* Large centre display */}
      <div className="flex justify-center">
        <div className="px-8 py-4 bg-surface border border-border rounded-xl text-center">
          <span className="text-3xl font-bold text-primary">{value.toFixed(1)}</span>
          <span className="text-lg text-text-secondary ml-1">mM</span>
        </div>
      </div>
    </div>
  );
}


// ─── 2D GRID (2 ingredients) ─────────────────────────────────────────────────

interface Grid2DProps {
  ingredientX: Ingredient;
  ingredientY: Ingredient;
  selectedX: number;
  selectedY: number;
  onSelect: (x: number, y: number) => void;
  previousSamples: Sample[];
}

function Grid2D({
  ingredientX,
  ingredientY,
  selectedX,
  selectedY,
  onSelect,
  previousSamples,
}: Grid2DProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  const xMin = ingredientX.min_concentration;
  const xMax = ingredientX.max_concentration;
  const yMin = ingredientY.min_concentration;
  const yMax = ingredientY.max_concentration;

  const totalW = GRID_SIZE + GRID_PADDING * 2;
  const totalH = GRID_SIZE + GRID_PADDING * 2;

  // Map concentration → pixel
  function concToPixelX(c: number): number {
    return GRID_PADDING + ((c - xMin) / (xMax - xMin)) * GRID_SIZE;
  }
  function concToPixelY(c: number): number {
    return GRID_PADDING + ((yMax - c) / (yMax - yMin)) * GRID_SIZE; // inverted Y
  }

  // Map pixel → concentration
  function pixelToConcX(px: number): number {
    return round1(clamp(((px - GRID_PADDING) / GRID_SIZE) * (xMax - xMin) + xMin, xMin, xMax));
  }
  function pixelToConcY(py: number): number {
    return round1(clamp((1 - (py - GRID_PADDING) / GRID_SIZE) * (yMax - yMin) + yMin, yMin, yMax));
  }

  function handleClick(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const scaleX = totalW / rect.width;
    const scaleY = totalH / rect.height;
    const px = (e.clientX - rect.left) * scaleX;
    const py = (e.clientY - rect.top) * scaleY;

    // Only register clicks inside the grid area
    if (
      px < GRID_PADDING || px > GRID_PADDING + GRID_SIZE ||
      py < GRID_PADDING || py > GRID_PADDING + GRID_SIZE
    ) return;

    onSelect(pixelToConcX(px), pixelToConcY(py));
  }

  // Generate grid lines (5 divisions)
  const gridLineCount = 5;
  const xTicks: number[] = [];
  const yTicks: number[] = [];
  for (let i = 0; i <= gridLineCount; i++) {
    xTicks.push(round1(xMin + ((xMax - xMin) * i) / gridLineCount));
    yTicks.push(round1(yMin + ((yMax - yMin) * i) / gridLineCount));
  }

  return (
    <div className="space-y-4">
      <p className="text-base text-text-secondary">
        Select your preferred concentration:
      </p>

      {/* SVG Grid */}
      <div className="flex justify-center">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${totalW} ${totalH}`}
          className="w-full max-w-[500px] cursor-crosshair select-none"
          onClick={handleClick}
        >
          {/* Grid background */}
          <rect
            x={GRID_PADDING}
            y={GRID_PADDING}
            width={GRID_SIZE}
            height={GRID_SIZE}
            fill="#fafafa"
            stroke="#e5e7eb"
            strokeWidth={1}
          />

          {/* Vertical grid lines + X-axis labels */}
          {xTicks.map((val) => {
            const px = concToPixelX(val);
            return (
              <g key={`x-${val}`}>
                <line
                  x1={px} y1={GRID_PADDING}
                  x2={px} y2={GRID_PADDING + GRID_SIZE}
                  stroke="#e5e7eb" strokeWidth={0.5}
                />
                <text
                  x={px} y={GRID_PADDING + GRID_SIZE + 16}
                  textAnchor="middle" fontSize={10} fill="#6b7280"
                >
                  {val}
                </text>
              </g>
            );
          })}

          {/* Horizontal grid lines + Y-axis labels */}
          {yTicks.map((val) => {
            const py = concToPixelY(val);
            return (
              <g key={`y-${val}`}>
                <line
                  x1={GRID_PADDING} y1={py}
                  x2={GRID_PADDING + GRID_SIZE} y2={py}
                  stroke="#e5e7eb" strokeWidth={0.5}
                />
                <text
                  x={GRID_PADDING - 8} y={py + 4}
                  textAnchor="end" fontSize={10} fill="#6b7280"
                >
                  {val}
                </text>
              </g>
            );
          })}

          {/* X-axis label */}
          <text
            x={GRID_PADDING + GRID_SIZE / 2}
            y={totalH - 4}
            textAnchor="middle" fontSize={12} fill="#374151" fontWeight={500}
          >
            {ingredientX.name} (mM)
          </text>

          {/* Y-axis label (rotated) */}
          <text
            x={14}
            y={GRID_PADDING + GRID_SIZE / 2}
            textAnchor="middle" fontSize={12} fill="#374151" fontWeight={500}
            transform={`rotate(-90, 14, ${GRID_PADDING + GRID_SIZE / 2})`}
          >
            {ingredientY.name} (mM)
          </text>

          {/* Previous samples (small gray dots) */}
          {previousSamples.map((s) => {
            const sx = s.ingredient_concentration?.[ingredientX.name] as number | undefined;
            const sy = s.ingredient_concentration?.[ingredientY.name] as number | undefined;
            if (sx == null || sy == null) return null;
            return (
              <circle
                key={s.cycle_number}
                cx={concToPixelX(sx)}
                cy={concToPixelY(sy)}
                r={4}
                fill="#9ca3af"
                opacity={0.7}
              />
            );
          })}

          {/* Selected point */}
          <circle
            cx={concToPixelX(selectedX)}
            cy={concToPixelY(selectedY)}
            r={7}
            fill="#521924"
            stroke="#fff"
            strokeWidth={2}
          />
        </svg>
      </div>

      {/* Selected concentrations text */}
      <p className="text-center text-base text-text-primary">
        Selected:{' '}
        <span className="font-semibold">{ingredientX.name}</span>{' '}
        {selectedX.toFixed(1)} mM,{' '}
        <span className="font-semibold">{ingredientY.name}</span>{' '}
        {selectedY.toFixed(1)} mM
      </p>
    </div>
  );
}
