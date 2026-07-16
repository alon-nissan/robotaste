/**
 * BOProgressChart — Optimization-progress line chart for the moderator
 * monitoring view.
 *
 * Plots, per BO cycle: predicted value (with ±uncertainty band), the
 * best-observed-so-far value, and the acquisition value on a secondary
 * panel. Data comes from GET /sessions/{id}/bo-status, which is a thin
 * wrapper around get_convergence_metrics() (robotaste/core/bo_utils.py) —
 * itself reading the acquisition_* fields persisted on each bo_selected
 * sample's selection_data.
 */

import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { BOStatus } from '../types';
import {
  Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ComposedChart, Area,
} from 'recharts';

interface Props {
  sessionId: string;
}

const PRIMARY = '#521924';
const ACCENT = '#fda50f';

const POLL_INTERVAL_MS = 8_000;

export default function BOProgressChart({ sessionId }: Props) {
  const [status, setStatus] = useState<BOStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.get(`/sessions/${sessionId}/bo-status`);
      setStatus(res.data);
      setError(null);
    } catch {
      setError('Failed to load BO progress');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading) {
    return (
      <div className="p-6 bg-surface rounded-xl border border-border">
        <p className="text-text-secondary text-center py-8">Loading BO progress…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-surface rounded-xl border border-border">
        <p className="text-red-500 text-center py-8">{error}</p>
      </div>
    );
  }

  if (!status || status.n_bo_samples === 0) {
    return (
      <div className="p-6 bg-surface rounded-xl border border-border">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
          Optimization Progress
        </h3>
        <p className="text-text-secondary text-center py-8">
          No BO cycles completed yet.
        </p>
      </div>
    );
  }

  const data = status.predicted_values.map((predicted, i) => ({
    bo_cycle: i + 1,
    predicted,
    best: status.best_values[i] ?? null,
    upper: predicted + (status.uncertainties[i] ?? 0),
    lower: predicted - (status.uncertainties[i] ?? 0),
    acquisition: status.acquisition_values[i] ?? null,
  }));

  return (
    <div className="p-6 bg-surface rounded-xl border border-border">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          Optimization Progress
        </h3>
        {!status.has_sufficient_data && (
          <span className="text-xs text-text-secondary">
            Still gathering data ({status.n_bo_samples} BO sample{status.n_bo_samples === 1 ? '' : 's'})
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Predicted value + uncertainty band + best-so-far */}
        <div className="h-[280px]">
          <p className="text-xs text-text-secondary mb-2">Predicted vs. Best-So-Far</p>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="bo_cycle"
                label={{ value: 'BO Cycle', position: 'bottom', offset: 0, style: { fill: '#7F8C8D', fontSize: 12 } }}
                tick={{ fill: '#7F8C8D', fontSize: 11 }}
              />
              <YAxis tick={{ fill: '#7F8C8D', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 12 }}
                formatter={(value, name) => [
                  typeof value === 'number' ? value.toFixed(3) : value,
                  name === 'predicted' ? 'Predicted' : name === 'best' ? 'Best So Far' : name,
                ]}
              />
              <Legend verticalAlign="top" height={30} />
              {/* Uncertainty band */}
              <Area dataKey="upper" stroke="none" fill={PRIMARY} fillOpacity={0.1} connectNulls type="monotone" legendType="none" />
              <Area dataKey="lower" stroke="none" fill="#ffffff" fillOpacity={1} connectNulls type="monotone" legendType="none" />
              <Line
                dataKey="predicted"
                name="Predicted"
                stroke={PRIMARY}
                strokeWidth={2}
                dot={{ r: 3, fill: PRIMARY }}
                connectNulls
                type="monotone"
              />
              <Line
                dataKey="best"
                name="Best So Far"
                stroke={ACCENT}
                strokeWidth={2}
                strokeDasharray="4 3"
                dot={{ r: 3, fill: ACCENT }}
                connectNulls
                type="monotone"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Acquisition value */}
        <div className="h-[280px]">
          <p className="text-xs text-text-secondary mb-2">Acquisition Value (Expected Improvement)</p>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="bo_cycle"
                label={{ value: 'BO Cycle', position: 'bottom', offset: 0, style: { fill: '#7F8C8D', fontSize: 12 } }}
                tick={{ fill: '#7F8C8D', fontSize: 11 }}
              />
              <YAxis tick={{ fill: '#7F8C8D', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 12 }}
                formatter={(value) => [typeof value === 'number' ? value.toExponential(2) : value, 'Acquisition']}
              />
              <Line
                dataKey="acquisition"
                name="Acquisition"
                stroke={ACCENT}
                strokeWidth={2}
                dot={{ r: 3, fill: ACCENT }}
                connectNulls
                type="monotone"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
