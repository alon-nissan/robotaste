interface Column {
  key: string;
  label: string;
  type?: string;
}

interface DataTableProps {
  columns: Column[];
  rows: Record<string, unknown>[];
  sortColumn?: string;
  sortDir?: 'asc' | 'desc';
  onSort?: (col: string) => void;
  onRowClick?: (row: Record<string, unknown>) => void;
  loading?: boolean;
  emptyMessage?: string;
}

function truncate(val: unknown): string {
  if (val === null || val === undefined) return '—';
  const str = typeof val === 'object' ? JSON.stringify(val) : String(val);
  return str.length > 60 ? str.slice(0, 60) + '…' : str;
}

export default function DataTable({
  columns,
  rows,
  sortColumn,
  sortDir,
  onSort,
  onRowClick,
  loading,
  emptyMessage = 'No data.',
}: DataTableProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 text-text-secondary text-sm">
        Loading...
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`text-left p-2 text-text-secondary font-medium whitespace-nowrap ${
                  onSort ? 'cursor-pointer hover:text-text-primary select-none' : ''
                }`}
                onClick={() => onSort?.(col.key)}
              >
                {col.label}
                {sortColumn === col.key && (
                  <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="p-4 text-center text-text-secondary"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr
                key={i}
                className={`border-b border-border/50 ${
                  onRowClick ? 'cursor-pointer hover:bg-surface' : ''
                }`}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td key={col.key} className="p-2 text-text-primary">
                    {truncate(row[col.key])}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
