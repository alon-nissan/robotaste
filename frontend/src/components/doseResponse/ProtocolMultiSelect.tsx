import type { DRProtocolInfo } from '../../types';

interface ProtocolMultiSelectProps {
  protocols: DRProtocolInfo[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  colorFor: (protocolId: string) => string;
}

/** Checkbox multi-select for comparing several protocols at once — mirrors the Subjects list. */
export default function ProtocolMultiSelect({ protocols, selected, onChange, colorFor }: ProtocolMultiSelectProps) {
  function toggle(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    onChange(next);
  }

  return (
    <div>
      <div className="flex gap-2 mb-2">
        <button type="button" onClick={() => onChange(new Set(protocols.map(p => p.protocol_id)))}
          className="px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary-light transition-colors">
          All
        </button>
        <button type="button" onClick={() => onChange(new Set())}
          className="px-2 py-1 text-xs bg-surface text-text-primary rounded border border-border hover:bg-gray-100 transition-colors">
          None
        </button>
      </div>
      <div className="space-y-1 max-h-[160px] overflow-y-auto">
        {protocols.map(p => (
          <label key={p.protocol_id} className="flex items-center gap-2 py-1 px-1 rounded hover:bg-gray-50 cursor-pointer">
            <input
              type="checkbox"
              checked={selected.has(p.protocol_id)}
              onChange={() => toggle(p.protocol_id)}
              className="w-4 h-4 rounded accent-primary"
            />
            <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: colorFor(p.protocol_id) }} />
            <span className="text-sm text-text-primary truncate">{p.name}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
