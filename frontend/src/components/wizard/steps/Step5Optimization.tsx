/**
 * Step 5: Smart Optimization (conditional — only if bo_selected used).
 * Presents 3 presets with plain-English descriptions, plus an expert panel
 * exposing the full adaptive-exploration schedule, advanced GP settings, and
 * convergence-detection tuning. Ported from the original moderator UI
 * (see robotaste/config/bo_config.py::DEFAULT_BO_CONFIG for the backend
 * defaults every field here maps to).
 */

import { useEffect, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import type { BayesianOptimizationConfig, StoppingCriteria } from '../../../types';

const PRESETS: {
  id: string;
  label: string;
  tag: string;
  description: string;
  config: BayesianOptimizationConfig;
}[] = [
  {
    id: 'balanced',
    label: 'Balanced',
    tag: 'Recommended',
    description:
      'Equal exploration and exploitation. Good for most experiments. The algorithm tries new regions while also refining promising ones.',
    config: {
      enabled: true,
      acquisition_function: 'ei',
      adaptive_acquisition: true,
      min_samples_for_bo: 3,
      ei_xi: 0.01,
      exploration_budget: 0.25,
      xi_exploration: 0.1,
      xi_exploitation: 0.01,
      kernel_nu: 2.5,
      alpha: 0.001,
      n_restarts_optimizer: 10,
    },
  },
  {
    id: 'explore',
    label: 'Explore More',
    tag: 'More cycles',
    description:
      'Tries more diverse samples before narrowing down. Better when you have many cycles and want to understand the full taste landscape.',
    config: {
      enabled: true,
      acquisition_function: 'ucb',
      adaptive_acquisition: true,
      min_samples_for_bo: 3,
      ucb_kappa: 3.0,
      exploration_budget: 0.4,
      kappa_exploration: 4.0,
      kappa_exploitation: 1.5,
      kernel_nu: 2.5,
      alpha: 0.001,
      n_restarts_optimizer: 10,
    },
  },
  {
    id: 'exploit',
    label: 'Exploit Fast',
    tag: 'Fewer cycles',
    description:
      'Quickly converges on the best sample. Better for shorter experiments where you want to find the optimum fast.',
    config: {
      enabled: true,
      acquisition_function: 'ei',
      adaptive_acquisition: true,
      min_samples_for_bo: 2,
      ei_xi: 0.001,
      exploration_budget: 0.1,
      xi_exploration: 0.05,
      xi_exploitation: 0.001,
      kernel_nu: 2.5,
      alpha: 0.001,
      n_restarts_optimizer: 10,
    },
  },
];

export default function Step5Optimization() {
  const { state, dispatch, needsBO } = useWizard();
  const bo = state.protocol.bayesian_optimization ?? { enabled: true };
  const stopping = state.protocol.stopping_criteria ?? { max_cycles: 6, min_cycles: 1 };
  const [selectedPreset, setSelectedPreset] = useState<string>('balanced');
  const [showExpert, setShowExpert] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showConvergence, setShowConvergence] = useState(false);

  function setBo(config: BayesianOptimizationConfig) {
    dispatch({ type: 'SET_BO_CONFIG', payload: config });
  }

  function applyPreset(presetId: string) {
    const preset = PRESETS.find((p) => p.id === presetId);
    if (preset) {
      setBo(preset.config);
      setSelectedPreset(presetId);
    }
  }

  function updateBo(updates: Partial<BayesianOptimizationConfig>) {
    setBo({ ...bo, ...updates });
    setSelectedPreset('');
  }

  function updateStopping(updates: Partial<StoppingCriteria>) {
    dispatch({ type: 'SET_STOPPING_CRITERIA', payload: { ...stopping, ...updates } });
  }

  // Guard against the silent-never-runs trap: a bo_selected schedule block
  // validates fine even with bayesian_optimization.enabled left at its
  // WizardContext default (false) — BO then just never produces a suggestion
  // at runtime. If this step is reached at all, a bo_selected block exists
  // (see needsBO), so make sure BO is actually enabled.
  useEffect(() => {
    if (needsBO && !bo.enabled) {
      applyPreset('balanced');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsBO, bo.enabled]);

  const acqFunc = bo.acquisition_function ?? 'ei';
  const isAdaptive = bo.adaptive_acquisition ?? true;
  const explorationBudget = bo.exploration_budget ?? 0.25;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Smart Optimization</h2>
        <p className="text-sm text-gray-500">
          Your experiment includes algorithm-optimized cycles. Choose how the algorithm explores
          taste preferences.
        </p>
      </div>

      {/* Preset cards */}
      <div className="grid grid-cols-3 gap-4">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => applyPreset(preset.id)}
            className={`text-left p-4 border rounded-lg transition-colors ${
              selectedPreset === preset.id
                ? 'border-blue-300 bg-blue-50 ring-1 ring-blue-200'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">{preset.label}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  preset.id === 'balanced'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {preset.tag}
              </span>
            </div>
            <p className="text-xs text-gray-500">{preset.description}</p>
          </button>
        ))}
      </div>

      {/* Expert toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowExpert(!showExpert)}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          {showExpert ? '▾ Hide expert settings' : '▸ Expert settings'}
        </button>

        {showExpert && (
          <div className="mt-4 space-y-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
            {/* Core algorithm settings */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Acquisition Function
                </label>
                <select
                  value={acqFunc}
                  onChange={(e) =>
                    updateBo({ acquisition_function: e.target.value as 'ei' | 'ucb' })
                  }
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ei">Expected Improvement (EI)</option>
                  <option value="ucb">Upper Confidence Bound (UCB)</option>
                </select>
                <p className="mt-1 text-[11px] text-gray-400">
                  EI: balanced exploration-exploitation. UCB: more exploration of uncertain regions.
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Min Samples Before Optimization
                </label>
                <input
                  type="number"
                  value={bo.min_samples_for_bo ?? 3}
                  onChange={(e) =>
                    updateBo({ min_samples_for_bo: parseInt(e.target.value) || 2 })
                  }
                  min={2}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="mt-1 text-[11px] text-gray-400">
                  Random exploration samples collected before the algorithm starts suggesting.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Kernel Smoothness (ν)
                </label>
                <select
                  value={bo.kernel_nu ?? 2.5}
                  onChange={(e) =>
                    updateBo({ kernel_nu: parseFloat(e.target.value) as 0.5 | 1.5 | 2.5 })
                  }
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={0.5}>0.5 — Rough (noisy data)</option>
                  <option value={1.5}>1.5 — Moderate (threshold effects)</option>
                  <option value={2.5}>2.5 — Smooth (recommended)</option>
                </select>
                <p className="mt-1 text-[11px] text-gray-400">
                  How smooth taste preferences are assumed to be across the space.
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Noise Tolerance (alpha)
                </label>
                <input
                  type="number"
                  value={bo.alpha ?? 0.001}
                  onChange={(e) => updateBo({ alpha: parseFloat(e.target.value) || 0.001 })}
                  step={0.001}
                  min={0.001}
                  max={1}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="mt-1 text-[11px] text-gray-400">
                  Higher = more tolerant of inconsistent ratings. Raise for untrained panels.
                </p>
              </div>
            </div>

            {/* Adaptive exploration strategy */}
            <div className="pt-2 border-t border-gray-200">
              <h4 className="text-xs font-semibold text-gray-700 mb-1">
                🎯 Adaptive Exploration Strategy
              </h4>
              <p className="text-[11px] text-gray-500 mb-3">
                Adjusts exploration automatically over the session: early cycles explore broadly to
                map the taste space, later cycles fine-tune around the best region. Based on
                Benjamins et al. 2022 (arXiv:2211.01455).
              </p>

              <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer mb-3">
                <input
                  type="checkbox"
                  checked={isAdaptive}
                  onChange={(e) => updateBo({ adaptive_acquisition: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Enable adaptive acquisition
              </label>

              {isAdaptive ? (
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-gray-600">
                        Exploration Budget
                      </label>
                      <span className="text-xs text-gray-500">
                        {Math.round(explorationBudget * 100)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={explorationBudget}
                      onChange={(e) => updateBo({ exploration_budget: parseFloat(e.target.value) })}
                      className="w-full accent-blue-600"
                    />
                    <p className="mt-1 text-[11px] text-gray-400">
                      Fraction of the session spent in high-exploration mode before shifting to
                      exploitation.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="block text-xs font-medium text-blue-700 mb-2">
                        🔵 Early Phase (Exploration)
                      </span>
                      {acqFunc === 'ei' ? (
                        <SliderField
                          label="xi (exploration)"
                          value={bo.xi_exploration ?? 0.1}
                          min={0}
                          max={0.2}
                          step={0.01}
                          onChange={(v) => updateBo({ xi_exploration: v })}
                        />
                      ) : (
                        <SliderField
                          label="kappa (exploration)"
                          value={bo.kappa_exploration ?? 3.0}
                          min={0.1}
                          max={5.0}
                          step={0.1}
                          onChange={(v) => updateBo({ kappa_exploration: v })}
                        />
                      )}
                      <p className="mt-1 text-[11px] text-gray-400">Higher → more exploration.</p>
                    </div>
                    <div>
                      <span className="block text-xs font-medium text-emerald-700 mb-2">
                        🟢 Late Phase (Exploitation)
                      </span>
                      {acqFunc === 'ei' ? (
                        <SliderField
                          label="xi (exploitation)"
                          value={bo.xi_exploitation ?? 0.01}
                          min={0}
                          max={0.1}
                          step={0.005}
                          onChange={(v) => updateBo({ xi_exploitation: v })}
                        />
                      ) : (
                        <SliderField
                          label="kappa (exploitation)"
                          value={bo.kappa_exploitation ?? 1.0}
                          min={0.1}
                          max={3.0}
                          step={0.1}
                          onChange={(v) => updateBo({ kappa_exploitation: v })}
                        />
                      )}
                      <p className="mt-1 text-[11px] text-gray-400">Lower → finer tuning.</p>
                    </div>
                  </div>

                  <PhaseTimeline budget={explorationBudget} />
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    Static mode: a fixed exploration level is used for the whole session. Consider
                    enabling adaptive mode for better convergence within limited cycles.
                  </div>
                  {acqFunc === 'ei' ? (
                    <SliderField
                      label="Exploration parameter (xi) — static"
                      value={bo.ei_xi ?? 0.01}
                      min={0}
                      max={0.1}
                      step={0.01}
                      onChange={(v) => updateBo({ ei_xi: v })}
                    />
                  ) : (
                    <SliderField
                      label="Exploration parameter (kappa) — static"
                      value={bo.ucb_kappa ?? 2.0}
                      min={0.1}
                      max={5.0}
                      step={0.1}
                      onChange={(v) => updateBo({ ucb_kappa: v })}
                    />
                  )}
                </div>
              )}
            </div>

            {/* Advanced GP settings */}
            <div className="pt-2 border-t border-gray-200">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                {showAdvanced ? '▾ Hide advanced settings' : '▸ Advanced settings'}
              </button>

              {showAdvanced && (
                <div className="mt-3 grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Hyperparameter Optimizer Restarts
                    </label>
                    <input
                      type="number"
                      value={bo.n_restarts_optimizer ?? 10}
                      onChange={(e) =>
                        updateBo({ n_restarts_optimizer: parseInt(e.target.value) || 1 })
                      }
                      min={1}
                      max={50}
                      className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="mt-1 text-[11px] text-gray-400">
                      More restarts = better-fit GP kernel, slower training. Default: 10.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Convergence detection */}
            <div className="pt-2 border-t border-gray-200">
              <button
                type="button"
                onClick={() => setShowConvergence(!showConvergence)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                {showConvergence ? '▾ Hide convergence detection' : '▸ Convergence detection'}
              </button>
              <p className="mt-1 text-[11px] text-gray-400">
                Cycle limits and the stop mode are set in the Schedule step. These fields tune when
                the algorithm considers itself converged within that range.
              </p>

              {showConvergence && (
                <div className="mt-3 space-y-4">
                  <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={stopping.convergence_detection ?? true}
                      onChange={(e) => updateStopping({ convergence_detection: e.target.checked })}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    Enable automatic convergence detection
                  </label>

                  {(stopping.convergence_detection ?? true) && (
                    <>
                      <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={stopping.early_termination_allowed ?? false}
                          onChange={(e) =>
                            updateStopping({ early_termination_allowed: e.target.checked })
                          }
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        Allow ending before minimum cycles if strongly converged
                      </label>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Expected Improvement Threshold
                          </label>
                          <input
                            type="number"
                            value={stopping.ei_threshold ?? 0.001}
                            onChange={(e) =>
                              updateStopping({ ei_threshold: parseFloat(e.target.value) || 0.001 })
                            }
                            step={0.0001}
                            min={0.0001}
                            max={0.1}
                            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <p className="mt-1 text-[11px] text-gray-400">
                            Below this, the next sample is expected to gain little. Lower = stop
                            sooner. Default: 0.001.
                          </p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Stability Threshold
                          </label>
                          <input
                            type="number"
                            value={stopping.stability_threshold ?? 0.05}
                            onChange={(e) =>
                              updateStopping({
                                stability_threshold: parseFloat(e.target.value) || 0.05,
                              })
                            }
                            step={0.01}
                            min={0.01}
                            max={0.5}
                            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <p className="mt-1 text-[11px] text-gray-400">
                            Std. deviation of recent best values below this = stable optimum.
                            Default: 0.05.
                          </p>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Slider field (labeled range input, value shown inline) ─────────────────

function SliderField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-[11px] text-gray-500">{label}</label>
        <span className="text-[11px] text-gray-500">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-blue-600"
      />
    </div>
  );
}

// ─── Phase progression timeline ──────────────────────────────────────────────

function PhaseTimeline({ budget }: { budget: number }) {
  const explorationPct = Math.round(budget * 100);
  const exploitationPct = 100 - explorationPct;
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-gray-400 min-w-[32px]">Early</span>
        <div className="flex flex-1 h-9 rounded-lg overflow-hidden border border-gray-200">
          <div
            style={{ flexGrow: budget, flexBasis: 0 }}
            className="flex items-center justify-center bg-gradient-to-r from-blue-500 to-teal-400 text-white text-[11px] font-medium px-1"
          >
            🔵 Exploration ({explorationPct}%)
          </div>
          <div
            style={{ flexGrow: 1 - budget, flexBasis: 0 }}
            className="flex items-center justify-center bg-gradient-to-r from-emerald-500 to-emerald-300 text-white text-[11px] font-medium px-1"
          >
            🟢 Exploitation ({exploitationPct}%)
          </div>
        </div>
        <span className="text-[11px] text-gray-400 min-w-[24px] text-right">Late</span>
      </div>
      <p className="mt-2 text-[11px] text-gray-400 text-center">
        ← Broad exploration to map taste space · Gradual linear decay · Fine-tuning around optimum →
      </p>
    </div>
  );
}
