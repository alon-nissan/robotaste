import type { ExplorerColumn, ColumnFilter } from '../../types';

interface FilterBarProps {
  columns: ExplorerColumn[];
  filters: ColumnFilter[];
  onFiltersChange: (filters: ColumnFilter[]) => void;
}

export default function FilterBar({ columns, filters, onFiltersChange }: FilterBarProps) {
  function addFilter() {
    const col = columns[0];
    if (!col) return;
    onFiltersChange([...filters, { column: col.key, operator: 'contains', value: '' }]);
  }

  function removeFilter(idx: number) {
    onFiltersChange(filters.filter((_, i) => i !== idx));
  }

  function updateFilter(idx: number, patch: Partial<ColumnFilter>) {
    onFiltersChange(filters.map((f, i) => (i === idx ? { ...f, ...patch } : f)));
  }

  function operatorsForType(type?: string): string[] {
    if (type === 'number') return ['=', '!=', '>', '<', '>=', '<='];
    if (type === 'date') return ['=', 'before', 'after'];
    return ['contains', '=', '!=', 'starts_with'];
  }

  if (columns.length === 0) return null;

  return (
    <div className="space-y-2">
      {filters.map((filter, i) => {
        const col = columns.find((c) => c.key === filter.column);
        const ops = operatorsForType(col?.type);
        return (
          <div key={i} className="flex items-center gap-2">
            <select
              value={filter.column}
              onChange={(e) => {
                const newCol = columns.find((c) => c.key === e.target.value);
                updateFilter(i, {
                  column: e.target.value,
                  operator: operatorsForType(newCol?.type)[0],
                  value: '',
                });
              }}
              className="border border-border rounded px-2 py-1 text-sm bg-white"
            >
              {columns.map((c) => (
                <option key={c.key} value={c.key}>{c.label ?? c.key}</option>
              ))}
            </select>
            <select
              value={filter.operator}
              onChange={(e) => updateFilter(i, { operator: e.target.value })}
              className="border border-border rounded px-2 py-1 text-sm bg-white"
            >
              {ops.map((op) => <option key={op} value={op}>{op}</option>)}
            </select>
            <input
              type="text"
              value={String(filter.value ?? '')}
              onChange={(e) => updateFilter(i, { value: e.target.value })}
              placeholder="value"
              className="border border-border rounded px-2 py-1 text-sm bg-white flex-1 min-w-0"
            />
            <button
              onClick={() => removeFilter(i)}
              className="text-text-secondary hover:text-red-600 transition-colors px-1"
            >
              ✕
            </button>
          </div>
        );
      })}
      <button
        onClick={addFilter}
        className="text-sm text-primary hover:text-primary-light transition-colors"
      >
        + Add filter
      </button>
    </div>
  );
}
