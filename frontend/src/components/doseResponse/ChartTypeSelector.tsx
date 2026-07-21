export type DRChartType = 'mean' | 'subjects' | 'distribution' | 'surface3d';

interface ChartTypeOption {
  id: DRChartType;
  label: string;
}

const OPTIONS: ChartTypeOption[] = [
  { id: 'mean', label: 'Mean ± SEM' },
  { id: 'subjects', label: 'Individual Subjects' },
  { id: 'distribution', label: 'Distribution' },
  { id: 'surface3d', label: '3D Surface' },
];

interface ChartTypeSelectorProps {
  value: DRChartType;
  onChange: (chartType: DRChartType) => void;
  /** 3D surface only makes sense for mixture protocols (2+ ingredients). */
  allowSurface3d: boolean;
}

export default function ChartTypeSelector({ value, onChange, allowSurface3d }: ChartTypeSelectorProps) {
  return (
    <div className="inline-flex rounded-lg border border-border overflow-hidden">
      {OPTIONS.map(opt => {
        const disabled = opt.id === 'surface3d' && !allowSurface3d;
        const active = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(opt.id)}
            title={disabled ? 'Requires a mixture protocol with 2+ ingredients' : undefined}
            className={`px-3 py-2 text-xs font-medium transition-colors whitespace-nowrap ${
              active
                ? 'bg-primary text-white'
                : disabled
                  ? 'bg-surface text-text-secondary/40 cursor-not-allowed'
                  : 'bg-surface text-text-secondary hover:bg-gray-100'
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
