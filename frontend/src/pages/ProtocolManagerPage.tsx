import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';
import type { Protocol } from '../types';
import PageLayout from '../components/PageLayout';

export default function ProtocolManagerPage() {
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [selectedProtocol, setSelectedProtocol] = useState<Protocol | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchProtocols = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get('/protocols');
      setProtocols(res.data);
    } catch (err) {
      setError('Failed to load protocols. Please try again.');
      console.error('Error fetching protocols:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProtocols();
  }, [fetchProtocols]);

  const filteredProtocols = protocols.filter((p) => {
    const q = searchQuery.toLowerCase();
    if (!q) return true;
    return (
      p.name.toLowerCase().includes(q) ||
      (p.description?.toLowerCase().includes(q)) ||
      (p.tags?.some((t) => t.toLowerCase().includes(q)))
    );
  });

  const handleFileUpload = async (file: File) => {
    try {
      setError(null);
      const formData = new FormData();
      formData.append('file', file);
      await api.post('/protocols/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      await fetchProtocols();
    } catch (err) {
      setError('Failed to upload protocol. Check that the JSON is valid.');
      console.error('Error uploading protocol:', err);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
    e.target.value = '';
  };

  const handleDelete = async (protocol: Protocol) => {
    if (!confirm(`Delete "${protocol.name}"? This action cannot be undone.`)) return;
    try {
      await api.delete(`/protocols/${protocol.protocol_id}`).catch(() => {
        // Endpoint may not exist yet — fall through to client-side removal
      });
      setProtocols((prev) => prev.filter((p) => p.protocol_id !== protocol.protocol_id));
      if (selectedProtocol?.protocol_id === protocol.protocol_id) {
        setSelectedProtocol(null);
      }
    } catch (err) {
      console.error('Error deleting protocol:', err);
    }
  };

  const formatCycleRange = (start: number, end: number) =>
    start === end ? `C${start}` : `C${start}–${end}`;

  return (
    <PageLayout>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-light text-text-primary tracking-wide">
          Protocol Manager
        </h1>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="py-4 px-8 rounded-xl text-lg font-semibold bg-primary text-white hover:bg-primary-light active:bg-primary-dark shadow-md transition-all duration-200"
        >
          + New Protocol
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Search bar */}
      <div className="mb-6">
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary">🔍</span>
          <input
            type="text"
            placeholder="Search protocols..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full p-3 pl-10 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
          />
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-12 text-text-secondary">Loading protocols…</div>
      )}

      {/* Empty state */}
      {!loading && protocols.length === 0 && (
        <div className="text-center py-12">
          <p className="text-text-secondary mb-2">No protocols found</p>
          <p className="text-sm text-text-secondary">
            Upload a protocol JSON file to get started.
          </p>
        </div>
      )}

      {/* No search results */}
      {!loading && protocols.length > 0 && filteredProtocols.length === 0 && (
        <div className="text-center py-12 text-text-secondary">
          No protocols match "{searchQuery}"
        </div>
      )}

      {/* Protocol table */}
      {!loading && filteredProtocols.length > 0 && (
        <div className="p-6 bg-surface rounded-xl border border-border mb-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left p-2 text-text-secondary font-medium">Name</th>
                <th className="text-left p-2 text-text-secondary font-medium">Version</th>
                <th className="text-left p-2 text-text-secondary font-medium">Ingredients</th>
                <th className="text-left p-2 text-text-secondary font-medium">Tags</th>
              </tr>
            </thead>
            <tbody>
              {filteredProtocols.map((protocol) => {
                const isSelected = selectedProtocol?.protocol_id === protocol.protocol_id;
                return (
                  <tr
                    key={protocol.protocol_id}
                    onClick={() => setSelectedProtocol(isSelected ? null : protocol)}
                    className={`border-b border-border/50 cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-primary/5 border-l-4 border-l-primary'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <td className="p-2 font-medium text-text-primary">{protocol.name}</td>
                    <td className="p-2 text-text-secondary">{protocol.version ?? '—'}</td>
                    <td className="p-2 text-text-secondary">
                      {protocol.ingredients.map((i) => i.name).join(', ') || '—'}
                    </td>
                    <td className="p-2">
                      {protocol.tags?.length ? (
                        <div className="flex flex-wrap gap-1">
                          {protocol.tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-2 py-0.5 text-xs bg-gray-100 text-text-secondary rounded-full"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-text-secondary">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Selected protocol preview */}
      {selectedProtocol && (
        <div>
          <p className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
            Selected Protocol Preview
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Details card */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-lg font-semibold mb-4">Details</h3>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-text-secondary">Name</dt>
                  <dd className="text-text-primary font-medium">{selectedProtocol.name}</dd>
                </div>
                <div>
                  <dt className="text-text-secondary">Description</dt>
                  <dd className="text-text-primary">
                    {selectedProtocol.description || 'No description'}
                  </dd>
                </div>
                <div>
                  <dt className="text-text-secondary">Version</dt>
                  <dd className="text-text-primary">{selectedProtocol.version ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-text-secondary">Questionnaire</dt>
                  <dd className="text-text-primary">
                    {selectedProtocol.questionnaire_type ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-text-secondary">Pump Config</dt>
                  <dd className="text-text-primary">
                    {selectedProtocol.pump_config?.enabled ? 'Enabled' : 'Disabled'}
                    {selectedProtocol.pump_config?.port && (
                      <span className="text-text-secondary ml-1">
                        ({selectedProtocol.pump_config.port})
                      </span>
                    )}
                  </dd>
                </div>
              </dl>
              <div className="flex items-center gap-2 mt-6 pt-4 border-t border-border">
                <button
                  onClick={() => alert('Editing coming soon')}
                  className="px-4 py-2 text-sm bg-surface text-text-primary rounded-lg border border-border hover:bg-gray-100 transition-colors"
                >
                  Edit
                </button>
                <button
                  onClick={() => alert('Duplication coming soon')}
                  className="px-4 py-2 text-sm bg-surface text-text-primary rounded-lg border border-border hover:bg-gray-100 transition-colors"
                >
                  Duplicate
                </button>
                <button
                  onClick={() => handleDelete(selectedProtocol)}
                  className="px-6 py-3 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 active:bg-red-800 transition-colors ml-auto"
                >
                  🗑️ Delete
                </button>
              </div>
            </div>

            {/* Schedule Timeline card */}
            <div className="p-6 bg-surface rounded-xl border border-border">
              <h3 className="text-lg font-semibold mb-4">Schedule Timeline</h3>
              {selectedProtocol.sample_selection_schedule?.length ? (
                <div className="space-y-3">
                  {selectedProtocol.sample_selection_schedule.map((block, idx) => (
                    <div
                      key={idx}
                      className="p-4 bg-surface rounded-lg border-l-4 border-primary"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-text-primary">
                          {formatCycleRange(block.cycle_range.start, block.cycle_range.end)}
                        </span>
                        <span className="px-2 py-0.5 text-xs bg-gray-100 text-text-secondary rounded-full">
                          {block.mode}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-secondary">No schedule defined</p>
              )}
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  );
}
