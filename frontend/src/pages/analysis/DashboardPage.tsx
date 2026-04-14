import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import StatCard from '../../components/analysis/StatCard';
import type { DashboardStats } from '../../types';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get('/analysis/dashboard-stats')
      .then((res) => setStats(res.data as DashboardStats))
      .catch(() => setError('Failed to load dashboard stats'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-semibold text-text-primary mb-6">Dashboard</h2>

      {loading && (
        <div className="text-text-secondary text-sm">Loading stats...</div>
      )}

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Sessions"
            value={stats.total_sessions}
            subtitle="All time"
          />
          <StatCard
            label="Subjects"
            value={stats.total_subjects}
            subtitle="Registered participants"
          />
          <StatCard
            label="Samples"
            value={stats.total_samples}
            subtitle="Taste trials recorded"
          />
          <StatCard
            label="Completion Rate"
            value={`${stats.completion_rate}%`}
            subtitle="Sessions completed"
          />
        </div>
      )}
    </div>
  );
}
