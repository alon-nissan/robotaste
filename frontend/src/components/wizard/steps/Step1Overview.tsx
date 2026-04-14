/**
 * Step 1: Experiment Overview
 * Name, description, tags, and data collection toggles.
 */

import { useWizard } from '../../../context/WizardContext';
import type { DataCollectionConfig } from '../../../types';

export default function Step1Overview() {
  const { state, dispatch } = useWizard();
  const { name, description, tags, sample_temperature_c: sampleTemperatureC } = state.protocol;
  const dc = state.protocol.data_collection ?? {
    track_trajectory: true,
    track_interaction_times: true,
    collect_demographics: true,
  };

  function updateOverview(field: 'name' | 'description', value: string) {
    dispatch({ type: 'UPDATE_OVERVIEW', payload: { [field]: value } });
  }

  function updateSampleTemperature(value: string) {
    const trimmed = value.trim();
    if (trimmed === '') {
      dispatch({ type: 'UPDATE_OVERVIEW', payload: { sample_temperature_c: undefined } });
      return;
    }

    const parsed = Number(trimmed);
    if (Number.isFinite(parsed)) {
      dispatch({ type: 'UPDATE_OVERVIEW', payload: { sample_temperature_c: parsed } });
    }
  }

  function updateTags(value: string) {
    const parsed = value.split(',').map((t) => t.trim()).filter(Boolean);
    dispatch({ type: 'UPDATE_OVERVIEW', payload: { tags: parsed } });
  }

  function updateDC(field: keyof DataCollectionConfig, value: boolean) {
    dispatch({
      type: 'SET_DATA_COLLECTION',
      payload: { ...dc, [field]: value },
    });
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Experiment Overview</h2>
        <p className="text-sm text-gray-500">Start by giving your experiment a name and description.</p>
      </div>

      {/* Name */}
      <div>
        <label htmlFor="protocol-name" className="block text-sm font-medium text-gray-700 mb-1">
          Experiment Name <span className="text-red-500">*</span>
        </label>
        <input
          id="protocol-name"
          type="text"
          value={name ?? ''}
          onChange={(e) => updateOverview('name', e.target.value)}
          placeholder="e.g., Sucrose Preference Study"
          className={`w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
            name === '' ? 'border-gray-300' : name ? 'border-gray-300' : 'border-red-300'
          }`}
          maxLength={200}
        />
      </div>

      {/* Description */}
      <div>
        <label htmlFor="protocol-desc" className="block text-sm font-medium text-gray-700 mb-1">
          Description
        </label>
        <textarea
          id="protocol-desc"
          value={description ?? ''}
          onChange={(e) => updateOverview('description', e.target.value)}
          placeholder="Describe the goal of this experiment..."
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
          maxLength={1000}
        />
      </div>

      {/* Tags */}
      <div>
        <label htmlFor="protocol-tags" className="block text-sm font-medium text-gray-700 mb-1">
          Tags
        </label>
        <input
          id="protocol-tags"
          type="text"
          value={(tags ?? []).join(', ')}
          onChange={(e) => updateTags(e.target.value)}
          placeholder="e.g., taste, sucrose, hedonic, pilot"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <p className="text-xs text-gray-400 mt-1">Comma-separated. Used for searching and filtering protocols.</p>
      </div>

      {/* Sample temperature */}
      <div>
        <label htmlFor="sample-temperature" className="block text-sm font-medium text-gray-700 mb-1">
          Sample Temperature (°C)
        </label>
        <input
          id="sample-temperature"
          type="number"
          step="0.1"
          value={sampleTemperatureC ?? ''}
          onChange={(e) => updateSampleTemperature(e.target.value)}
          placeholder="e.g., 22.0"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <p className="text-xs text-gray-400 mt-1">
          Fixed protocol temperature. This value is logged on every sample in sessions using this protocol.
        </p>
      </div>

      {/* Data Collection */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">Data Collection</h3>
        <div className="space-y-3">
          <Toggle
            label="Collect participant demographics"
            description="Age, gender, and other registration info"
            checked={dc.collect_demographics ?? true}
            onChange={(v) => updateDC('collect_demographics', v)}
          />
          <Toggle
            label="Record slider movement trajectories"
            description="Track how participants move sliders before submitting"
            checked={dc.track_trajectory ?? true}
            onChange={(v) => updateDC('track_trajectory', v)}
          />
          <Toggle
            label="Record response times"
            description="Measure how long participants take to answer each question"
            checked={dc.track_interaction_times ?? true}
            onChange={(v) => updateDC('track_interaction_times', v)}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Toggle component ────────────────────────────────────────────────────────

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <div className="pt-0.5">
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          onClick={() => onChange(!checked)}
          className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors ${
            checked ? 'bg-blue-600' : 'bg-gray-300'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform mt-0.5 ${
              checked ? 'translate-x-4.5 ml-px' : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>
      <div>
        <div className="text-sm text-gray-700 group-hover:text-gray-900">{label}</div>
        <div className="text-xs text-gray-400">{description}</div>
      </div>
    </label>
  );
}
