/**
 * Step 3: Experiment Schedule — Plan the experiment flow.
 * Cycle count, stopping mode, and schedule blocks with mode-specific editors.
 */

import { useWizard } from '../../../context/WizardContext';
import type {
  ScheduleBlock,
  SelectionMode,
  StoppingCriteria,
  PredeterminedSample,
  SampleBankEntry,
  Ingredient,
} from '../../../types';

const MODE_LABELS: Record<SelectionMode, { label: string; description: string }> = {
  predetermined: {
    label: 'Fixed Samples',
    description: 'You define exactly what each participant tastes in each cycle.',
  },
  predetermined_randomized: {
    label: 'Randomized from Sample Set',
    description: 'You provide a pool of samples; the order is randomized per participant (e.g., Latin Square).',
  },
  user_selected: {
    label: 'Participant Chooses',
    description: 'Participants pick their own concentrations using sliders or a grid.',
  },
  bo_selected: {
    label: 'Algorithm Optimizes',
    description: 'A Bayesian optimization algorithm suggests the best sample to try next.',
  },
};

const STOPPING_MODES = [
  { value: 'manual_only' as const, label: "I'll decide when to stop", description: 'You manually end the experiment from the moderator panel.' },
  { value: 'suggest_auto' as const, label: "Suggest when to stop, I'll confirm", description: 'The system notifies you when it thinks the experiment has converged.' },
  { value: 'auto_with_minimum' as const, label: 'Stop automatically when converged', description: 'The experiment ends automatically once convergence criteria are met.' },
];

export default function Step3Schedule() {
  const { state, dispatch } = useWizard();
  const schedule = state.protocol.sample_selection_schedule ?? [];
  const stopping = state.protocol.stopping_criteria ?? { max_cycles: 6, min_cycles: 1 };
  const ingredients = state.protocol.ingredients ?? [];
  const tunableIngredients = ingredients.filter((ing) => !(ing.is_diluent ?? false));

  function updateStopping(updates: Partial<StoppingCriteria>) {
    dispatch({ type: 'SET_STOPPING_CRITERIA', payload: { ...stopping, ...updates } });
  }

  function updateBlock(index: number, updates: Partial<ScheduleBlock>) {
    const updated = schedule.map((b, i) => (i === index ? { ...b, ...updates } : b));
    dispatch({ type: 'SET_SCHEDULE', payload: updated });
  }

  function addBlock() {
    const lastEnd = schedule.length > 0 ? schedule[schedule.length - 1].cycle_range.end : 0;
    const newBlock: ScheduleBlock = {
      cycle_range: { start: lastEnd + 1, end: lastEnd + 4 },
      mode: 'predetermined_randomized',
    };
    dispatch({ type: 'SET_SCHEDULE', payload: [...schedule, newBlock] });
  }

  function removeBlock(index: number) {
    dispatch({ type: 'SET_SCHEDULE', payload: schedule.filter((_, i) => i !== index) });
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Experiment Schedule</h2>
        <p className="text-sm text-gray-500">
          Define how many tasting cycles and how samples are selected in each phase.
        </p>
      </div>

      {/* Cycle count */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Minimum Cycles</label>
          <input
            type="number"
            value={stopping.min_cycles ?? 1}
            onChange={(e) => updateStopping({ min_cycles: parseInt(e.target.value) || 1 })}
            min={1}
            max={100}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Maximum Cycles</label>
          <input
            type="number"
            value={stopping.max_cycles}
            onChange={(e) => updateStopping({ max_cycles: parseInt(e.target.value) || 6 })}
            min={1}
            max={100}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Stopping mode */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">When should the experiment stop?</label>
        <div className="space-y-2">
          {STOPPING_MODES.map((mode) => (
            <label
              key={mode.value}
              className={`flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                stopping.mode === mode.value
                  ? 'border-blue-300 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <input
                type="radio"
                name="stopping-mode"
                checked={stopping.mode === mode.value}
                onChange={() => updateStopping({ mode: mode.value })}
                className="mt-0.5 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <div className="text-sm font-medium text-gray-700">{mode.label}</div>
                <div className="text-xs text-gray-500">{mode.description}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Schedule blocks */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">Cycle Schedule</h3>
        <div className="space-y-4">
          {schedule.map((block, index) => (
            <ScheduleBlockEditor
              key={index}
              block={block}
              index={index}
              ingredients={tunableIngredients}
              canRemove={schedule.length > 1}
              onChange={(updates) => updateBlock(index, updates)}
              onRemove={() => removeBlock(index)}
            />
          ))}

          {schedule.length === 0 && (
            <div className="text-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
              <p className="mb-2">No schedule blocks defined</p>
              <button
                type="button"
                onClick={addBlock}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                Add your first block
              </button>
            </div>
          )}

          {schedule.length > 0 && (
            <button
              type="button"
              onClick={addBlock}
              className="w-full py-2.5 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
            >
              + Add Block
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


// ─── Schedule Block Editor ─────────────────────────────────────────────────

function ScheduleBlockEditor({
  block,
  index,
  ingredients,
  canRemove,
  onChange,
  onRemove,
}: {
  block: ScheduleBlock;
  index: number;
  ingredients: Ingredient[];
  canRemove: boolean;
  onChange: (updates: Partial<ScheduleBlock>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400 uppercase">Block {index + 1}</span>
        {canRemove && (
          <button type="button" onClick={onRemove} className="text-gray-400 hover:text-red-500 text-sm">
            Remove
          </button>
        )}
      </div>

      {/* Cycle range */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Start Cycle</label>
          <input
            type="number"
            value={block.cycle_range.start}
            onChange={(e) =>
              onChange({ cycle_range: { ...block.cycle_range, start: parseInt(e.target.value) || 1 } })
            }
            min={1}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">End Cycle</label>
          <input
            type="number"
            value={block.cycle_range.end}
            onChange={(e) =>
              onChange({ cycle_range: { ...block.cycle_range, end: parseInt(e.target.value) || 1 } })
            }
            min={block.cycle_range.start}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Mode selector */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-2">Sample Selection Mode</label>
        <div className="grid grid-cols-2 gap-2">
          {(Object.entries(MODE_LABELS) as [SelectionMode, { label: string; description: string }][]).map(
            ([mode, info]) => (
              <button
                key={mode}
                type="button"
                onClick={() => onChange({ mode })}
                className={`text-left p-3 border rounded-lg transition-colors ${
                  block.mode === mode
                    ? 'border-blue-300 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-sm font-medium text-gray-700">{info.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{info.description}</div>
              </button>
            )
          )}
        </div>
      </div>

      {/* Mode-specific editors */}
      {block.mode === 'predetermined' && (
        <PredeterminedEditor block={block} ingredients={ingredients} onChange={onChange} />
      )}
      {block.mode === 'predetermined_randomized' && (
        <SampleBankEditor block={block} ingredients={ingredients} onChange={onChange} />
      )}
    </div>
  );
}


// ─── Predetermined Sample Editor ────────────────────────────────────────────

function PredeterminedEditor({
  block,
  ingredients,
  onChange,
}: {
  block: ScheduleBlock;
  ingredients: Ingredient[];
  onChange: (updates: Partial<ScheduleBlock>) => void;
}) {
  const samples = block.predetermined_samples ?? [];
  const cycleCount = block.cycle_range.end - block.cycle_range.start + 1;

  if (ingredients.length === 0) {
    return (
      <p className="text-xs text-gray-500">
        No tunable ingredients available for concentration editing.
      </p>
    );
  }

  function ensureSamples(): PredeterminedSample[] {
    const result: PredeterminedSample[] = [];
    for (let c = block.cycle_range.start; c <= block.cycle_range.end; c++) {
      const existing = samples.find((s) => s.cycle === c);
      const concentrations: Record<string, number> = {};
      ingredients.forEach((ing) => {
        concentrations[ing.name] = existing?.concentrations[ing.name] ?? 0;
      });
      result.push({ cycle: c, concentrations });
    }
    return result;
  }

  const rows = ensureSamples();

  function updateSample(cycleIndex: number, ingredientName: string, value: number) {
    const updated = rows.map((r, i) =>
      i === cycleIndex ? { ...r, concentrations: { ...r.concentrations, [ingredientName]: value } } : r
    );
    onChange({ predetermined_samples: updated });
  }

  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-2">
        Samples ({cycleCount} cycles)
      </label>
      <p className="text-xs text-gray-500 mb-2">
        Enter ingredient concentrations (not percentages). Units are shown in each column header.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left text-xs font-medium text-gray-500 py-1.5 pr-3">Cycle</th>
              {ingredients.map((ing) => (
                <th key={ing.name} className="text-left text-xs font-medium text-gray-500 py-1.5 px-2">
                  {ing.name} ({ing.unit ?? 'mM'})
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={row.cycle} className="border-b border-gray-100">
                <td className="py-1.5 pr-3 text-gray-500">{row.cycle}</td>
                {ingredients.map((ing) => (
                  <td key={ing.name} className="py-1.5 px-2">
                    <input
                      type="number"
                      value={row.concentrations[ing.name] ?? 0}
                      onChange={(e) => updateSample(ri, ing.name, parseFloat(e.target.value) || 0)}
                      step="any"
                      className="w-24 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


// ─── Sample Bank Editor ─────────────────────────────────────────────────────

function SampleBankEditor({
  block,
  ingredients,
  onChange,
}: {
  block: ScheduleBlock;
  ingredients: Ingredient[];
  onChange: (updates: Partial<ScheduleBlock>) => void;
}) {
  if (ingredients.length === 0) {
    return (
      <p className="text-xs text-gray-500">
        No tunable ingredients available for sample bank concentrations.
      </p>
    );
  }

  const bank = block.sample_bank ?? {
    samples: [],
    design_type: 'latin_square' as const,
    constraints: { prevent_consecutive_repeats: true, ensure_all_used_before_repeat: true },
  };

  function updateBank(updates: Partial<typeof bank>) {
    onChange({ sample_bank: { ...bank, ...updates } });
  }

  function addSample() {
    const nextId = String.fromCharCode(65 + bank.samples.length); // A, B, C, ...
    const concentrations: Record<string, number> = {};
    ingredients.forEach((ing) => { concentrations[ing.name] = 0; });
    const newSample: SampleBankEntry = { id: nextId, concentrations, label: '' };
    updateBank({ samples: [...bank.samples, newSample] });
  }

  function removeSample(index: number) {
    updateBank({ samples: bank.samples.filter((_, i) => i !== index) });
  }

  function updateSample(index: number, updates: Partial<SampleBankEntry>) {
    const updated = bank.samples.map((s, i) => (i === index ? { ...s, ...updates } : s));
    updateBank({ samples: updated });
  }

  function updateConcentration(sampleIndex: number, ingredientName: string, value: number) {
    const sample = bank.samples[sampleIndex];
    updateSample(sampleIndex, {
      concentrations: { ...sample.concentrations, [ingredientName]: value },
    });
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">
        Sample values are ingredient concentrations (not percentages). Use the unit shown per column.
      </p>

      {/* Design type */}
      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={bank.design_type === 'latin_square'}
            onChange={() => updateBank({ design_type: 'latin_square' })}
            className="text-blue-600 focus:ring-blue-500"
          />
          Latin Square
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={bank.design_type === 'randomized'}
            onChange={() => updateBank({ design_type: 'randomized' })}
            className="text-blue-600 focus:ring-blue-500"
          />
          Random
        </label>
      </div>

      {/* Constraints */}
      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-xs text-gray-600">
          <input
            type="checkbox"
            checked={bank.constraints?.prevent_consecutive_repeats ?? true}
            onChange={(e) =>
              updateBank({
                constraints: { ...bank.constraints, prevent_consecutive_repeats: e.target.checked },
              })
            }
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          Prevent consecutive repeats
        </label>
        <label className="flex items-center gap-2 text-xs text-gray-600">
          <input
            type="checkbox"
            checked={bank.constraints?.ensure_all_used_before_repeat ?? true}
            onChange={(e) =>
              updateBank({
                constraints: { ...bank.constraints, ensure_all_used_before_repeat: e.target.checked },
              })
            }
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          Use all before repeating
        </label>
      </div>

      {/* Sample table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left text-xs font-medium text-gray-500 py-1.5 pr-2">ID</th>
              <th className="text-left text-xs font-medium text-gray-500 py-1.5 px-2">Label</th>
              {ingredients.map((ing) => (
                <th key={ing.name} className="text-left text-xs font-medium text-gray-500 py-1.5 px-2">
                  {ing.name} ({ing.unit ?? 'mM'})
                </th>
              ))}
              <th className="w-8"></th>
            </tr>
          </thead>
          <tbody>
            {bank.samples.map((sample, si) => (
              <tr key={si} className="border-b border-gray-100">
                <td className="py-1.5 pr-2 text-gray-500 font-mono">{sample.id}</td>
                <td className="py-1.5 px-2">
                  <input
                    type="text"
                    value={sample.label ?? ''}
                    onChange={(e) => updateSample(si, { label: e.target.value })}
                    placeholder="e.g., Low Sugar"
                    className="w-32 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                {ingredients.map((ing) => (
                  <td key={ing.name} className="py-1.5 px-2">
                    <input
                      type="number"
                      value={sample.concentrations[ing.name] ?? 0}
                      onChange={(e) => updateConcentration(si, ing.name, parseFloat(e.target.value) || 0)}
                      step="any"
                      className="w-24 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </td>
                ))}
                <td className="py-1.5">
                  <button
                    type="button"
                    onClick={() => removeSample(si)}
                    className="text-gray-400 hover:text-red-500 text-xs"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={addSample}
        className="text-sm text-blue-600 hover:text-blue-700 font-medium"
      >
        + Add Sample
      </button>
    </div>
  );
}
