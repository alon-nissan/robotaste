/**
 * Step 2: Ingredients — Define what you're testing.
 * Card-based list of 1-6 ingredients with concentrations.
 */

import { useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import type { Ingredient } from '../../../types';

const EMPTY_INGREDIENT: Ingredient = {
  name: '',
  min_concentration: 0,
  max_concentration: 100,
  unit: 'mM',
};

export default function Step2Ingredients() {
  const { state, dispatch } = useWizard();
  const ingredients = state.protocol.ingredients ?? [];

  function updateIngredient(index: number, updates: Partial<Ingredient>) {
    const updated = ingredients.map((ing, i) => (i === index ? { ...ing, ...updates } : ing));
    dispatch({ type: 'SET_INGREDIENTS', payload: updated });
  }

  function addIngredient() {
    if (ingredients.length >= 6) return;
    dispatch({ type: 'SET_INGREDIENTS', payload: [...ingredients, { ...EMPTY_INGREDIENT }] });
  }

  function removeIngredient(index: number) {
    if (ingredients.length <= 1) return;
    dispatch({ type: 'SET_INGREDIENTS', payload: ingredients.filter((_, i) => i !== index) });
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Ingredients</h2>
        <p className="text-sm text-gray-500">
          Define the ingredients in your experiment. You can add up to 6 ingredients.
        </p>
      </div>

      <div className="space-y-4">
        {ingredients.map((ing, index) => (
          <IngredientCard
            key={index}
            ingredient={ing}
            index={index}
            canRemove={ingredients.length > 1}
            onChange={(updates) => updateIngredient(index, updates)}
            onRemove={() => removeIngredient(index)}
          />
        ))}

        {ingredients.length === 0 && (
          <div className="text-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
            <p className="mb-2">No ingredients yet</p>
            <button
              type="button"
              onClick={addIngredient}
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              Add your first ingredient
            </button>
          </div>
        )}

        {ingredients.length > 0 && ingredients.length < 6 && (
          <button
            type="button"
            onClick={addIngredient}
            className="w-full py-2.5 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
          >
            + Add Ingredient
          </button>
        )}
      </div>
    </div>
  );
}


function IngredientCard({
  ingredient,
  index,
  canRemove,
  onChange,
  onRemove,
}: {
  ingredient: Ingredient;
  index: number;
  canRemove: boolean;
  onChange: (updates: Partial<Ingredient>) => void;
  onRemove: () => void;
}) {
  const hasError = ingredient.name !== '' &&
    ingredient.max_concentration <= ingredient.min_concentration;
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className={`border rounded-lg p-4 ${hasError ? 'border-red-300 bg-red-50' : 'border-gray-200'}`}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-medium text-gray-400 uppercase">Ingredient {index + 1}</span>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-gray-400 hover:text-red-500 text-sm transition-colors"
          >
            Remove
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4">
        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            type="text"
            value={ingredient.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="e.g., Sucrose, NaCl, Citric Acid"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Concentration range */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Min Concentration</label>
            <input
              type="number"
              value={ingredient.min_concentration}
              onChange={(e) => onChange({ min_concentration: parseFloat(e.target.value) || 0 })}
              min={0}
              step="any"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Concentration</label>
            <input
              type="number"
              value={ingredient.max_concentration}
              onChange={(e) => onChange({ max_concentration: parseFloat(e.target.value) || 0 })}
              min={0}
              step="any"
              className={`w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                hasError ? 'border-red-300' : 'border-gray-300'
              }`}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Unit</label>
            <select
              value={ingredient.unit ?? 'mM'}
              onChange={(e) => onChange({ unit: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="mM">mM</option>
              <option value="g/L">g/L</option>
              <option value="%">%</option>
              <option value="ppm">ppm</option>
            </select>
          </div>
        </div>

        {hasError && (
          <p className="text-xs text-red-600">Max concentration must be greater than min concentration.</p>
        )}

        {/* Advanced toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs text-gray-400 hover:text-gray-600 text-left"
        >
          {showAdvanced ? '▾ Hide advanced' : '▸ Advanced settings'}
        </button>

        {showAdvanced && (
          <div className="grid grid-cols-3 gap-3 pt-1">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Molecular Weight (g/mol)</label>
              <input
                type="number"
                value={ingredient.molecular_weight ?? ''}
                onChange={(e) => onChange({ molecular_weight: parseFloat(e.target.value) || undefined })}
                placeholder="e.g., 342.3"
                step="any"
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Stock Concentration (mM)</label>
              <input
                type="number"
                value={ingredient.stock_concentration_mM ?? ''}
                onChange={(e) => onChange({ stock_concentration_mM: parseFloat(e.target.value) || undefined })}
                placeholder="e.g., 200"
                step="any"
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={ingredient.is_diluent ?? false}
                  onChange={(e) => onChange({ is_diluent: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Diluent (e.g., Water)
              </label>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

