interface JsonRendererProps {
  data: unknown;
  indent?: number;
}

export default function JsonRenderer({ data, indent = 0 }: JsonRendererProps) {
  if (data === null || data === undefined) {
    return <span className="text-gray-400 text-xs">null</span>;
  }
  if (typeof data === 'object' && !Array.isArray(data)) {
    const obj = data as Record<string, unknown>;
    return (
      <div style={{ paddingLeft: indent * 12 }}>
        {Object.entries(obj).map(([k, v]) => (
          <div key={k} className="py-0.5">
            <span className="text-primary font-medium text-xs">{k}: </span>
            <JsonRenderer data={v} indent={indent + 1} />
          </div>
        ))}
      </div>
    );
  }
  if (Array.isArray(data)) {
    return (
      <div style={{ paddingLeft: indent * 12 }}>
        {data.map((item, i) => (
          <div key={i} className="py-0.5">
            <span className="text-text-secondary text-xs">[{i}] </span>
            <JsonRenderer data={item} indent={indent + 1} />
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-text-primary text-xs">{String(data)}</span>;
}
