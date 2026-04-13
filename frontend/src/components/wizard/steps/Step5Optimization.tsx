/**
 * Step 5: Smart Optimization (conditional — only if bo_selected used).
 * Presents 3 presets with plain-English descriptions + expert toggle.
 */

import { useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import type { BayesianOptimizationConfig } from '../../../types';

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
  const { state, dispatch } = useWizard();
  const bo = state.protocol.bayesian_optimization ?? { enabled: true };
  const [selectedPreset, setSelectedPreset] = useState<string>('balanced');
  const [showExpert, setShowExpert] = useState(false);

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
          <div className="mt-4 space-y-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Acquisition Function
                </label>
                <select
                  value={bo.acquisition_function ?? 'ei'}
                  onChange={(e) =>
                    updateBo({ acquisition_function: e.target.value as 'ei' | 'ucb' })
                  }
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="ei">Expected Improvement (EI)</option>
                  <option value="ucb">Upper Confidence Bound (UCB)</option>
                </select>
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
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Kernel Smoothness
                </label>
                <select
                  value={bo.kernel_nu ?? 2.5}
                  onChange={(e) =>
                    updateBo({ kernel_nu: parseFloat(e.target.value) as 0.5 | 1.5 | 2.5 })
                  }
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={0.5}>Rough (0.5)</option>
                  <option value={1.5}>Moderate (1.5)</option>
                  <option value={2.5}>Smooth (2.5)</option>
                </select>
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
              </div>
              <div className="flex items-end pb-0.5">
                <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={bo.adaptive_acquisition ?? true}
                    onChange={(e) => updateBo({ adaptive_acquisition: e.target.checked })}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  Adaptive acquisition
                </label>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
