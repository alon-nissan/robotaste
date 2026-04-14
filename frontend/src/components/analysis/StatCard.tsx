interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
}

export default function StatCard({ label, value, subtitle }: StatCardProps) {
  return (
    <div className="p-6 bg-surface rounded-xl border border-border">
      <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1">{label}</p>
      <p className="text-3xl font-light text-text-primary">{value}</p>
      {subtitle && <p className="text-xs text-text-secondary mt-1">{subtitle}</p>}
    </div>
  );
}
