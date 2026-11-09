/**
 * AnchorEditor — edit the labelled points of a line scale (value + label).
 * Rows are kept sorted by value on blur so positions read top-to-bottom as
 * low-to-high; out-of-range and duplicate values are flagged inline.
 */
import { useState } from 'react';
import type { ScaleAnchor } from '../../../types';
import { smallInputClass } from './styles';

interface AnchorEditorProps {
  anchors: ScaleAnchor[];
  min: number | undefined;
  max: number | undefined;
  onChange: (anchors: ScaleAnchor[]) => void;
}

export default function AnchorEditor({ anchors, min, max, onChange }: AnchorEditorProps) {
  const [newValue, setNewValue] = useState('');
  const [newLabel, setNewLabel] = useState('');

  const sortAnchors = (list: ScaleAnchor[]) => [...list].sort((a, b) => a.value - b.value);

  function update(index: number, patch: Partial<ScaleAnchor>) {
    onChange(anchors.map((a, i) => (i === index ? { ...a, ...patch } : a)));
  }

  function remove(index: number) {
    onChange(anchors.filter((_, i) => i !== index));
  }

  function add() {
    const v = parseFloat(newValue);
    if (Number.isNaN(v) || !newLabel.trim()) return;
    onChange(sortAnchors([...anchors, { value: v, label: newLabel.trim() }]));
    setNewValue('');
    setNewLabel('');
  }

  const counts = new Map<number, number>();
  anchors.forEach((a) => counts.set(a.value, (counts.get(a.value) ?? 0) + 1));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className="w-20">Position</span>
        <span>Label</span>
      </div>
      {anchors.map((a, i) => {
        const outOfRange =
          min !== undefined && max !== undefined && (a.value < min || a.value > max);
        const duplicate = (counts.get(a.value) ?? 0) > 1;
        return (
          <div key={i} className="flex items-center gap-2" data-testid="anchor-row">
            <input
              type="number"
              step="any"
              aria-label={`Anchor ${i + 1} position`}
              value={Number.isFinite(a.value) ? a.value : ''}
              onChange={(e) => update(i, { value: parseFloat(e.target.value) })}
              onBlur={() => onChange(sortAnchors(anchors))}
              className={`${smallInputClass} w-20 ${outOfRange || duplicate ? 'border-red-400' : ''}`}
            />
            <input
              type="text"
              aria-label={`Anchor ${i + 1} label`}
              value={a.label}
              onChange={(e) => update(i, { label: e.target.value })}
              className={`${smallInputClass} flex-1`}
            />
            <button
              type="button"
              onClick={() => remove(i)}
              aria-label={`Remove anchor ${a.label}`}
              className="text-gray-400 hover:text-red-500 px-1"
            >
              ×
            </button>
            {(outOfRange || duplicate) && (
              <span className="text-xs text-red-600">{outOfRange ? 'out of range' : 'duplicate'}</span>
            )}
          </div>
        );
      })}
      <div className="flex items-center gap-2 pt-1">
        <input
          type="number"
          step="any"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          placeholder="Value"
          aria-label="New anchor position"
          className={`${smallInputClass} w-20`}
        />
        <input
          type="text"
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder="New anchor label"
          aria-label="New anchor label"
          className={`${smallInputClass} flex-1`}
        />
        <button type="button" onClick={add} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
          Add
        </button>
      </div>
    </div>
  );
}
