/**
 * BOSurfacesTab — post-hoc analysis of Bayesian Optimization experiments.
 *
 * Analysis Hub tab (see AnalysisHubPage.tsx) inspired by the live
 * BOVisualization2D component, but operating on completed sessions instead
 * of polling a running one. Three modes:
 *
 *   - Compare — two participants' GP response surfaces side by side, plus a
 *     difference heatmap (only shown when their grids are aligned, i.e. same
 *     protocol/ingredient ranges).
 *   - Mean    — an averaged surface across N participants from one protocol,
 *     colored by between-subject disagreement (σ across participants at each
 *     point), with every participant's discovery route overlaid.
 *   - Replay  — one participant's GP retrained on the first N cycles,
 *     scrubbed with a slider (or played back), showing how the model and its
 *     discovery route evolved sample by sample. Paired with a
 *     predicted-vs-observed calibration scatter and a per-cycle summary
 *     table (both walk the same "train on cycles < N, predict cycle N"
 *     history via /analysis/bo-calibration).
 *
 * 2D (2-ingredient) BO experiments only — see plan for rationale.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Plot from 'react-plotly.js';
import { api } from '../../api/client';
import type {
  BOSessionSummary,
  BOSurface2D,
  BOSurfaceMean,
  BOCalibrationRow,
} from '../../types';
import Surface2DPanel, { DifferenceHeatmap, HeatmapPanel, type ObservationPath } from './Surface2DPanel';

const PRIMARY = '#521924';
const PARTICIPANT_COLORS = [
  '#521924', '#2563eb', '#16a34a', '#ea580c', '#7c3aed',
  '#0891b2', '#be123c', '#4f46e5', '#ca8a04', '#0d9488',
];

type Mode = 'compare' | 'mean' | 'replay';
type ProtocolGroup = { protocol_name: string; sessions: BOSessionSummary[] };

// ═══════════════════════════════════════════════════════════════════════════
// MAIN TAB
// ═══════════════════════════════════════════════════════════════════════════

export default function BOSurfacesTab() {
  const [sessions, setSessions] = useState<BOSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('compare');

  useEffect(() => {
    api
      .get('/analysis/bo-sessions')
      .then((r) => setSessions(r.data.sessions || []))
      .catch(() => setError('Failed to load BO sessions.'))
      .finally(() => setLoading(false));
  }, []);

  const byProtocol = useMemo(() => {
    const map = new Map<string, ProtocolGroup>();
    for (const s of sessions) {
      const entry = map.get(s.protocol_id) ?? { protocol_name: s.protocol_name, sessions: [] };
      entry.sessions.push(s);
      map.set(s.protocol_id, entry);
    }
    return map;
  }, [sessions]);

  const sessionColor = useCallback(
    (sessionId: string) => {
      const idx = sessions.findIndex((s) => s.session_id === sessionId);
      return PARTICIPANT_COLORS[Math.max(idx, 0) % PARTICIPANT_COLORS.length];
    },
    [sessions],
  );

  if (loading) return <LoadingState text="Loading BO sessions…" />;
  if (error) return <ErrorState text={error} />;

  if (sessions.length === 0) {
    return (
      <div className="p-6 bg-surface rounded-xl border border-border flex items-center justify-center h-48 text-text-secondary text-sm">
        No 2-ingredient Bayesian Optimization sessions with ≥3 samples yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex gap-2">
        {([
          { id: 'compare', label: 'Compare 2' },
          { id: 'mean', label: 'Mean Surface' },
          { id: 'replay', label: 'Replay' },
        ] as { id: Mode; label: string }[]).map((m) => (
          <button
            key={m.id}
            onClick={() => setMode(m.id)}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              mode === m.id
                ? 'bg-primary text-white'
                : 'bg-surface text-text-secondary border border-border hover:bg-gray-100'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {mode === 'compare' && (
        <CompareMode sessions={sessions} byProtocol={byProtocol} sessionColor={sessionColor} />
      )}
      {mode === 'mean' && <MeanMode byProtocol={byProtocol} sessionColor={sessionColor} />}
      {mode === 'replay' && <ReplayMode sessions={sessions} sessionColor={sessionColor} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MODE: COMPARE
// ═══════════════════════════════════════════════════════════════════════════

function CompareMode({
  sessions,
  byProtocol,
  sessionColor,
}: {
  sessions: BOSessionSummary[];
  byProtocol: Map<string, ProtocolGroup>;
  sessionColor: (id: string) => string;
}) {
  const [selectedA, setSelectedA] = useState('');
  const [selectedB, setSelectedB] = useState('');
  const [surfaceA, setSurfaceA] = useState<BOSurface2D | null>(null);
  const [surfaceB, setSurfaceB] = useState<BOSurface2D | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedA || !selectedB) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.get(`/analysis/bo-surface/${selectedA}`),
      api.get(`/analysis/bo-surface/${selectedB}`),
    ])
      .then(([rA, rB]) => {
        setSurfaceA(rA.data);
        setSurfaceB(rB.data);
      })
      .catch(() => setError('Failed to load one or both surfaces.'))
      .finally(() => setLoading(false));
  }, [selectedA, selectedB]);

  const sessA = sessions.find((s) => s.session_id === selectedA);
  const sessB = sessions.find((s) => s.session_id === selectedB);

  const gridsAligned = useMemo(() => {
    if (!surfaceA || !surfaceB || surfaceA.status !== 'ready' || surfaceB.status !== 'ready') return false;
    if (surfaceA.predictions.x.length !== surfaceB.predictions.x.length) return false;
    return (
      surfaceA.predictions.x.every((v, i) => Math.abs(v - surfaceB.predictions.x[i]) < 1e-6) &&
      surfaceA.predictions.y.every((v, i) => Math.abs(v - surfaceB.predictions.y[i]) < 1e-6)
    );
  }, [surfaceA, surfaceB]);

  const diffGrid = useMemo(() => {
    if (!gridsAligned || !surfaceA || !surfaceB) return null;
    return surfaceA.predictions.mean.map((row, i) =>
      row.map((v, j) => v - surfaceB.predictions.mean[i][j]),
    );
  }, [gridsAligned, surfaceA, surfaceB]);

  const bothReady = surfaceA?.status === 'ready' && surfaceB?.status === 'ready';

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-6 bg-surface rounded-xl border border-border">
        <ParticipantSelect label="Participant A" byProtocol={byProtocol} value={selectedA} onChange={setSelectedA} />
        <ParticipantSelect label="Participant B" byProtocol={byProtocol} value={selectedB} onChange={setSelectedB} />
      </div>

      {!selectedA || !selectedB ? (
        <EmptyHint text="Select two participants to compare their response surfaces." />
      ) : loading ? (
        <LoadingState text="Training GP models…" />
      ) : error ? (
        <ErrorState text={error} />
      ) : !bothReady ? (
        <ErrorState text="One or both sessions have insufficient data for a GP surface." />
      ) : (
        surfaceA &&
        surfaceB && (
          <>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <SurfaceCard
                title={`${sessA?.subject_name ?? 'A'} — ${sessA?.session_code ?? ''}`}
                surface={surfaceA}
                color={sessionColor(selectedA)}
              />
              <SurfaceCard
                title={`${sessB?.subject_name ?? 'B'} — ${sessB?.session_code ?? ''}`}
                surface={surfaceB}
                color={sessionColor(selectedB)}
              />
            </div>

            <div className="p-6 bg-surface rounded-xl border border-border">
              <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
                Difference (A − B mean predicted response)
              </p>
              {gridsAligned && diffGrid ? (
                <DifferenceHeatmap
                  xVals={surfaceA.predictions.x}
                  yVals={surfaceA.predictions.y}
                  diff={diffGrid}
                  xLabel={surfaceA.ingredient_names[0]}
                  yLabel={surfaceA.ingredient_names[1]}
                  uirevision={`${selectedA}-${selectedB}`}
                />
              ) : (
                <p className="text-sm text-text-secondary py-6 text-center">
                  Difference hidden — these two sessions don't share an aligned grid (different
                  protocols or ingredient ranges).
                </p>
              )}
            </div>

            <SummaryTable
              rows={[
                {
                  label: sessA?.subject_name ?? 'A',
                  code: sessA?.session_code ?? '',
                  surface: surfaceA,
                  color: sessionColor(selectedA),
                },
                {
                  label: sessB?.subject_name ?? 'B',
                  code: sessB?.session_code ?? '',
                  surface: surfaceB,
                  color: sessionColor(selectedB),
                },
              ]}
            />
          </>
        )
      )}
    </div>
  );
}

function SurfaceCard({ title, surface, color }: { title: string; surface: BOSurface2D; color: string }) {
  const [xName, yName] = surface.ingredient_names;
  const path: ObservationPath = {
    label: title,
    color,
    points: surface.observations.x.map((x, i) => ({
      x,
      y: surface.observations.y[i],
      z: surface.observations.z[i],
    })),
    showStepLabels: true,
  };
  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">{title}</p>
      <Surface2DPanel
        xVals={surface.predictions.x}
        yVals={surface.predictions.y}
        mean={surface.predictions.mean}
        colorGrid={surface.predictions.std}
        colorLabel="σ"
        xLabel={xName}
        yLabel={yName}
        zLabel={surface.target_column}
        paths={[path]}
        uirevision={title}
      />
      <p className="mt-2 text-xs text-text-secondary">
        {surface.n_cycles_used} cycles · mean σ {surface.mean_sigma.toFixed(3)}
      </p>
    </div>
  );
}

function bestFromGrid(predictions: { x: number[]; y: number[]; mean: number[][] }) {
  let best = -Infinity;
  let bx = 0;
  let by = 0;
  predictions.mean.forEach((row, i) => {
    row.forEach((v, j) => {
      if (v > best) {
        best = v;
        bx = predictions.x[j];
        by = predictions.y[i];
      }
    });
  });
  return { value: best, x: bx, y: by };
}

function SummaryTable({
  rows,
}: {
  rows: { label: string; code: string; surface: BOSurface2D; color: string }[];
}) {
  return (
    <div className="p-6 bg-surface rounded-xl border border-border">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Summary</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left p-2 text-text-secondary font-medium">Participant</th>
              <th className="text-right p-2 text-text-secondary font-medium">Cycles</th>
              <th className="text-right p-2 text-text-secondary font-medium">Best predicted</th>
              <th className="text-right p-2 text-text-secondary font-medium">At (x, y)</th>
              <th className="text-right p-2 text-text-secondary font-medium">Mean σ</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const best = bestFromGrid(r.surface.predictions);
              return (
                <tr key={i} className="border-b border-border/50">
                  <td className="p-2">
                    <span className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: r.color }} />
                      {r.label} <span className="text-xs text-text-secondary">({r.code})</span>
                    </span>
                  </td>
                  <td className="p-2 text-right">{r.surface.n_cycles_used}</td>
                  <td className="p-2 text-right">{best.value.toFixed(2)}</td>
                  <td className="p-2 text-right">
                    {best.x.toFixed(1)}, {best.y.toFixed(1)}
                  </td>
                  <td className="p-2 text-right">{r.surface.mean_sigma.toFixed(3)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MODE: MEAN
// ═══════════════════════════════════════════════════════════════════════════

function MeanMode({
  byProtocol,
  sessionColor,
}: {
  byProtocol: Map<string, ProtocolGroup>;
  sessionColor: (id: string) => string;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [meanData, setMeanData] = useState<BOSurfaceMean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selected.size < 2) {
      setMeanData(null);
      return;
    }
    setLoading(true);
    setError(null);
    api
      .get('/analysis/bo-surface-mean', { params: { session_ids: [...selected].join(',') } })
      .then((r) => setMeanData(r.data))
      .catch((err: unknown) => {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(detail ?? 'Failed to compute mean surface.');
      })
      .finally(() => setLoading(false));
  }, [selected]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="p-6 bg-surface rounded-xl border border-border">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Select participants (must share one protocol)
        </h3>
        <div className="flex flex-col gap-4">
          {[...byProtocol.entries()].map(([pid, group]) => (
            <div key={pid}>
              <div className="text-xs font-medium text-text-secondary mb-2">{group.protocol_name}</div>
              <div className="flex flex-wrap gap-2">
                {group.sessions.map((s) => (
                  <label
                    key={s.session_id}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm cursor-pointer transition-colors ${
                      selected.has(s.session_id)
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(s.session_id)}
                      onChange={() => toggle(s.session_id)}
                      className="w-4 h-4 rounded accent-primary"
                    />
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: sessionColor(s.session_id) }}
                    />
                    {s.subject_name} ({s.session_code})
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selected.size < 2 ? (
        <EmptyHint text="Select at least 2 participants from the same protocol." />
      ) : loading ? (
        <LoadingState text="Averaging GP surfaces…" />
      ) : error ? (
        <ErrorState text={error} />
      ) : (
        meanData?.status === 'ready' && (
          <>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <div className="rounded-lg border border-border bg-background p-4">
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
                  Mean Response Surface + All Discovery Routes
                </p>
                <Surface2DPanel
                  xVals={meanData.predictions.x}
                  yVals={meanData.predictions.y}
                  mean={meanData.predictions.mean}
                  colorGrid={meanData.predictions.between_subject_std}
                  colorLabel="Between-subject σ"
                  xLabel={meanData.ingredient_names[0]}
                  yLabel={meanData.ingredient_names[1]}
                  paths={meanData.sessions.map((s) => ({
                    label: s.session_code,
                    color: sessionColor(s.session_id),
                    points: s.observations.x.map((x, i) => ({
                      x,
                      y: s.observations.y[i],
                      z: s.observations.z[i],
                    })),
                  }))}
                  uirevision={[...selected].join(',')}
                />
              </div>
              <div className="rounded-lg border border-border bg-background p-4">
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
                  Between-Subject Disagreement
                </p>
                <HeatmapPanel
                  xVals={meanData.predictions.x}
                  yVals={meanData.predictions.y}
                  grid={meanData.predictions.between_subject_std}
                  xLabel={meanData.ingredient_names[0]}
                  yLabel={meanData.ingredient_names[1]}
                  colorLabel="σ across participants"
                  uirevision={`${[...selected].join(',')}-std`}
                />
              </div>
            </div>

            <div className="p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
                Included Participants
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left p-2 text-text-secondary font-medium">Participant</th>
                      <th className="text-right p-2 text-text-secondary font-medium">Cycles used</th>
                    </tr>
                  </thead>
                  <tbody>
                    {meanData.sessions.map((s) => (
                      <tr key={s.session_id} className="border-b border-border/50">
                        <td className="p-2">
                          <span className="flex items-center gap-2">
                            <span
                              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                              style={{ backgroundColor: sessionColor(s.session_id) }}
                            />
                            {s.session_code}
                          </span>
                        </td>
                        <td className="p-2 text-right">{s.n_cycles_used}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MODE: REPLAY
// ═══════════════════════════════════════════════════════════════════════════

const MIN_CYCLE = 3;
const PLAY_INTERVAL_MS = 900;

function ReplayMode({
  sessions,
  sessionColor,
}: {
  sessions: BOSessionSummary[];
  sessionColor: (id: string) => string;
}) {
  const [selected, setSelected] = useState('');
  const [cycle, setCycle] = useState(MIN_CYCLE);
  const [maxCycle, setMaxCycle] = useState(MIN_CYCLE);
  const [surface, setSurface] = useState<BOSurface2D | null>(null);
  const [loadingSurface, setLoadingSurface] = useState(false);
  const [calibration, setCalibration] = useState<BOCalibrationRow[] | null>(null);
  const [loadingCalibration, setLoadingCalibration] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);

  const cacheRef = useRef<Map<string, Map<number, BOSurface2D>>>(new Map());
  const playTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const sess = sessions.find((s) => s.session_id === selected);

  // Reset on participant change: fetch full-session surface (for max cycle
  // count) and the calibration walk once. `cancelled` guards against this
  // effect's own async callbacks resolving after a newer selection has
  // already superseded them (see the cycle effect below for why this
  // matters — it's the same race).
  useEffect(() => {
    let cancelled = false;
    setPlaying(false);
    setSurface(null);
    setCalibration(null);
    setError(null);
    if (!selected) return () => { cancelled = true; };

    cacheRef.current.set(selected, cacheRef.current.get(selected) ?? new Map());

    setLoadingSurface(true);
    api
      .get(`/analysis/bo-surface/${selected}`)
      .then((r) => {
        if (cancelled) return;
        const data: BOSurface2D = r.data;
        if (data.status !== 'ready') {
          setError(data.message ?? 'Insufficient data for a BO surface.');
          return;
        }
        cacheRef.current.get(selected)!.set(data.n_cycles_used, data);
        setMaxCycle(data.n_cycles_used);
        setCycle(data.n_cycles_used);
        setSurface(data);
      })
      .catch(() => { if (!cancelled) setError('Failed to load the full-session surface.'); })
      .finally(() => { if (!cancelled) setLoadingSurface(false); });

    setLoadingCalibration(true);
    api
      .get(`/analysis/bo-calibration/${selected}`)
      .then((r) => { if (!cancelled) setCalibration(r.data.status === 'ready' ? r.data.rows : []); })
      .catch(() => { if (!cancelled) setCalibration([]); })
      .finally(() => { if (!cancelled) setLoadingCalibration(false); });

    return () => { cancelled = true; };
  }, [selected]);

  // Fetch (or reuse cached) surface for the current cycle whenever it
  // changes. Guarded with `cancelled` because switching participants resets
  // `selected` before the async participant-bootstrap effect above has a
  // chance to update `cycle` to the new session's cycle count — this effect
  // fires first (still holding the *previous* cycle value), starts an
  // in-flight request for it, and without the guard that stale response can
  // resolve after the bootstrap effect's own request and clobber `surface`
  // with the wrong participant's/cycle's data.
  useEffect(() => {
    let cancelled = false;
    if (!selected) return;
    const cache = cacheRef.current.get(selected)!;
    const cached = cache.get(cycle);
    if (cached) {
      setSurface(cached);
      return;
    }
    setLoadingSurface(true);
    api
      .get(`/analysis/bo-surface/${selected}`, { params: { up_to_cycle: cycle } })
      .then((r) => {
        if (cancelled) return;
        const data: BOSurface2D = r.data;
        if (data.status === 'ready') {
          cache.set(cycle, data);
          setSurface(data);
        }
      })
      .catch(() => { if (!cancelled) setError('Failed to load the surface for this cycle.'); })
      .finally(() => { if (!cancelled) setLoadingSurface(false); });

    return () => { cancelled = true; };
  }, [cycle, selected]);

  // Playback: step the cycle forward on an interval, stop at maxCycle.
  useEffect(() => {
    if (!playing) {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
      return;
    }
    playTimerRef.current = setInterval(() => {
      setCycle((c) => {
        if (c >= maxCycle) {
          setPlaying(false);
          return c;
        }
        return c + 1;
      });
    }, PLAY_INTERVAL_MS);
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [playing, maxCycle]);

  function togglePlay() {
    if (!playing && cycle >= maxCycle) setCycle(MIN_CYCLE);
    setPlaying((p) => !p);
  }

  const path: ObservationPath | null = surface
    ? {
        label: sess?.session_code ?? '',
        color: selected ? sessionColor(selected) : PRIMARY,
        points: surface.observations.x.map((x, i) => ({
          x,
          y: surface.observations.y[i],
          z: surface.observations.z[i],
        })),
        showStepLabels: true,
      }
    : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="p-6 bg-surface rounded-xl border border-border flex flex-col gap-4">
        <div className="max-w-md">
          <ParticipantSelectFlat sessions={sessions} value={selected} onChange={setSelected} />
        </div>

        {selected && (
          <div className="flex items-center gap-4">
            <button
              onClick={togglePlay}
              disabled={loadingSurface || maxCycle <= MIN_CYCLE}
              className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
                playing ? 'bg-gray-200 text-text-primary' : 'bg-primary text-white hover:bg-primary-light'
              } disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              {playing ? '⏸ Pause' : '▶ Play'}
            </button>
            <input
              type="range"
              min={MIN_CYCLE}
              max={Math.max(maxCycle, MIN_CYCLE)}
              step={1}
              value={cycle}
              onChange={(e) => {
                setPlaying(false);
                setCycle(Number(e.target.value));
              }}
              className="flex-1 accent-primary"
            />
            <span className="text-sm text-text-secondary w-32 text-right">
              Cycle {cycle} / {maxCycle}
            </span>
          </div>
        )}
      </div>

      {!selected ? (
        <EmptyHint text="Select a participant to replay their GP model sample-by-sample." />
      ) : error ? (
        <ErrorState text={error} />
      ) : (
        <>
          <div className="rounded-lg border border-border bg-background p-4">
            <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
              GP Surface at Cycle {cycle} — Discovery Route
            </p>
            {loadingSurface && !surface ? (
              <LoadingState text="Training GP model…" />
            ) : (
              surface &&
              path && (
                <Surface2DPanel
                  xVals={surface.predictions.x}
                  yVals={surface.predictions.y}
                  mean={surface.predictions.mean}
                  colorGrid={surface.predictions.std}
                  colorLabel="σ"
                  xLabel={surface.ingredient_names[0]}
                  yLabel={surface.ingredient_names[1]}
                  zLabel={surface.target_column}
                  paths={[path]}
                  uirevision={`${selected}`}
                />
              )
            )}
            {surface && (
              <p className="mt-2 text-xs text-text-secondary">
                Trained on {surface.n_cycles_used} of {surface.n_cycles_total} total cycles · mean σ{' '}
                {surface.mean_sigma.toFixed(3)}
              </p>
            )}
          </div>

          <CalibrationSection loading={loadingCalibration} rows={calibration} targetLabel={surface?.target_column} />
        </>
      )}
    </div>
  );
}

function CalibrationSection({
  loading,
  rows,
  targetLabel,
}: {
  loading: boolean;
  rows: BOCalibrationRow[] | null;
  targetLabel?: string;
}) {
  if (loading) return <LoadingState text="Walking the training history…" />;
  if (!rows || rows.length === 0) {
    return <EmptyHint text="Not enough cycles yet for a predicted-vs-observed calibration walk." />;
  }

  const minV = Math.min(...rows.map((r) => Math.min(r.observed, r.predicted)));
  const maxV = Math.max(...rows.map((r) => Math.max(r.observed, r.predicted)));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="p-6 bg-surface rounded-xl border border-border">
        <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Predicted vs. Observed{targetLabel ? ` (${targetLabel})` : ''}
        </p>
        <Plot
          data={[
            {
              type: 'scatter',
              mode: 'lines',
              x: [minV, maxV],
              y: [minV, maxV],
              line: { color: '#9ca3af', width: 1, dash: 'dot' },
              hoverinfo: 'skip',
              showlegend: false,
            },
            {
              type: 'scatter',
              mode: 'markers+text',
              x: rows.map((r) => r.predicted),
              y: rows.map((r) => r.observed),
              text: rows.map((r) => `C${r.cycle}`),
              textposition: 'top center',
              textfont: { size: 9, color: '#6b7280' },
              marker: {
                color: rows.map((r) => r.uncertainty),
                colorscale: 'YlOrRd',
                size: 10,
                showscale: true,
                colorbar: { title: { text: 'σ', font: { size: 10, color: '#6b7280' } }, thickness: 12, len: 0.8 },
                line: { color: '#ffffff', width: 1 },
              },
              hovertemplate: 'Cycle %{text}<br>Predicted: %{x:.2f}<br>Observed: %{y:.2f}<extra></extra>',
              showlegend: false,
            },
          ]}
          layout={{
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: { l: 50, r: 10, t: 10, b: 40 },
            height: 340,
            xaxis: {
              title: { text: 'Predicted (trained on cycles < N)', font: { size: 11, color: '#6b7280' } },
              gridcolor: '#E5E7EB',
              tickfont: { size: 10, color: '#6b7280' },
            },
            yaxis: {
              title: { text: 'Observed at cycle N', font: { size: 11, color: '#6b7280' } },
              gridcolor: '#E5E7EB',
              tickfont: { size: 10, color: '#6b7280' },
            },
          }}
          style={{ width: '100%', height: '340px' }}
          config={{ displayModeBar: false, responsive: true }}
        />
      </div>

      <div className="p-6 bg-surface rounded-xl border border-border">
        <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Per-Cycle Summary
        </p>
        <div className="overflow-auto max-h-[340px]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface">
              <tr className="border-b border-border">
                <th className="text-right p-2 text-text-secondary font-medium">Cycle</th>
                <th className="text-right p-2 text-text-secondary font-medium">Observed</th>
                <th className="text-right p-2 text-text-secondary font-medium">Predicted</th>
                <th className="text-right p-2 text-text-secondary font-medium">|Error|</th>
                <th className="text-right p-2 text-text-secondary font-medium">σ</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.cycle} className="border-b border-border/50">
                  <td className="p-2 text-right">{r.cycle}</td>
                  <td className="p-2 text-right">{r.observed.toFixed(2)}</td>
                  <td className="p-2 text-right">{r.predicted.toFixed(2)}</td>
                  <td className="p-2 text-right">{r.abs_error.toFixed(2)}</td>
                  <td className="p-2 text-right">{r.uncertainty.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SHARED PICKERS / STATES
// ═══════════════════════════════════════════════════════════════════════════

function ParticipantSelect({
  label,
  byProtocol,
  value,
  onChange,
}: {
  label: string;
  byProtocol: Map<string, ProtocolGroup>;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-primary mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
      >
        <option value="">Select participant…</option>
        {[...byProtocol.entries()].map(([pid, group]) => (
          <optgroup key={pid} label={group.protocol_name}>
            {group.sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.subject_name} — {s.session_code} ({s.n_cycles} cycles)
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}

function ParticipantSelectFlat({
  sessions,
  value,
  onChange,
}: {
  sessions: BOSessionSummary[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-primary mb-1">Participant</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
      >
        <option value="">Select participant…</option>
        {sessions.map((s) => (
          <option key={s.session_id} value={s.session_id}>
            {s.subject_name} — {s.session_code} ({s.n_cycles} cycles, {s.protocol_name})
          </option>
        ))}
      </select>
    </div>
  );
}

function LoadingState({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center h-48">
      <p className="text-text-secondary">{text}</p>
    </div>
  );
}

function ErrorState({ text }: { text: string }) {
  return (
    <div className="p-6 bg-red-50 rounded-xl text-red-700 text-sm">
      <strong>Error:</strong> {text}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div className="p-6 bg-surface rounded-xl border border-border flex items-center justify-center h-32 text-text-secondary text-sm text-center">
      {text}
    </div>
  );
}
