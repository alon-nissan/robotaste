/**
 * PumpSetup Component — Initial syringe volume inputs.
 *
 * === WHAT THIS DOES ===
 * When pumps are enabled in the selected protocol, this shows
 * input fields for each ingredient's initial syringe volume (in mL).
 * The moderator enters how much solution is loaded in each syringe
 * before starting the experiment.
 *
 * === KEY CONCEPT: Controlled Inputs ===
 * In React, form inputs can be "controlled" — their value comes from state,
 * and changes go through a handler function. This is different from HTML
 * where inputs manage their own value.
 *
 * The pattern is:
 *   <input value={state} onChange={(e) => setState(e.target.value)} />
 *
 * This ensures React always knows the current value (useful for validation).
 */

import type { Protocol } from '../types';

interface Props {
  protocol: Protocol | null;  // Currently selected protocol
  volumes: Record<string, number>;  // Current volume values { "Sugar": 50, "Salt": 50 }
  onVolumesChange: (volumes: Record<string, number>) => void;  // Callback when values change
}

export default function PumpSetup({ protocol, volumes, onVolumesChange }: Props) {
  // Don't show if no protocol selected or pumps not enabled
  if (!protocol) return null;

  const pumpEnabled = protocol.pump_config?.enabled ?? false;
  const ingredients = protocol.ingredients || [];

  if (!pumpEnabled || ingredients.length === 0) return null;

  // Handle volume input change for a specific ingredient
  function handleVolumeChange(ingredientName: string, value: string) {
    const numValue = parseFloat(value) || 0;

    // Create a new volumes object with the updated value
    // The spread operator { ...volumes } copies all existing values,
    // then [ingredientName]: numValue overrides the specific one.
    // This is like Python's: {**volumes, ingredient_name: num_value}
    onVolumesChange({
      ...volumes,
      [ingredientName]: numValue,
    });
  }

  return (
    <div>
      <h3 className="text-lg font-semibold text-text-primary mb-3">
        Pump Setup
      </h3>

      {/* One input per ingredient */}
      <div className="space-y-3">
        {ingredients.map((ing, index) => (
          // Each ingredient gets a row with label + input
          <div key={ing.name} className="flex items-center gap-3">
            {/* Label: "Sol I", "Sol II", etc. */}
            <label className="text-sm text-text-secondary w-32 shrink-0">
              Sol {index + 1} — {ing.name}
            </label>

            {/* Volume input */}
            <input
              type="number"
              value={volumes[ing.name] || ''}
              onChange={(e) => handleVolumeChange(ing.name, e.target.value)}
              placeholder="0.00"
              step="0.01"
              min="0"
              className="w-32 p-2 border border-border rounded-lg text-sm
                         text-text-primary bg-white
                         focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
            />

            {/* Unit label */}
            <span className="text-sm text-text-secondary">mL</span>
          </div>
        ))}
      </div>
    </div>
  );
}
