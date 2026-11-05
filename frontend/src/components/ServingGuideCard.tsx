/**
 * ServingGuideCard — moderator guide for hand-served (no-pump) experiments.
 *
 * Shows which pre-prepared solution to hand the participant right now
 * ("Serve now") and the full per-participant serving order, so the
 * experimenter can lay out cups in advance. Polls GET /sessions/{id}/serving-plan.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ServingPlan, ServingPlanEntry } from '../types';

interface Props {
  sessionId: string;
  sessionCode?: string;
  /** Concentration formatter shared with the monitoring page */
  formatConcentration: (val: number) => string;
}

function concentrationText(
  entry: ServingPlanEntry,
  fmt: (val: number) => string,
): string {
  if (!entry.concentrations) return '';
  return Object.entries(entry.concentrations)
    .map(([name, val]) => `${name}: ${fmt(val)}`)
    .join(', ');
}

function modeText(mode: string): string {
  if (mode === 'bo_selected') return 'Chosen by optimizer';
  if (mode === 'user_selected') return 'Chosen by participant';
  return '';
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export default function ServingGuideCard({ sessionId, sessionCode, formatConcentration }: Props) {
  const [plan, setPlan] = useState<ServingPlan | null>(null);

  const fetchPlan = useCallback(async () => {
    try {
      const res = await api.get<ServingPlan>(`/sessions/${sessionId}/serving-plan`);
      setPlan(res.data);
    } catch {
      // keep last known plan
    }
  }, [sessionId]);

  useEffect(() => {
    const first = setTimeout(fetchPlan, 0);
    const interval = setInterval(fetchPlan, 3000);
    return () => {
      clearTimeout(first);
      clearInterval(interval);
    };
  }, [fetchPlan]);

  if (!plan || plan.entries.length === 0) return null;

  const current = plan.entries.find((e) => e.status === 'current');
  const next = plan.entries.find((e) => e.status === 'upcoming' && (!current || e.cycle > current.cycle));

  function handlePrint() {
    if (!plan) return;
    const rows = plan.entries
      .map(
        (e) =>
          `<tr><td>${e.cycle}</td><td><b>${escapeHtml(e.sample_id ?? '—')}</b></td>` +
          `<td>${escapeHtml(e.sample_label ?? '')}</td>` +
          `<td>${escapeHtml(concentrationText(e, formatConcentration) || modeText(e.mode))}</td>` +
          `<td>☐</td></tr>`,
      )
      .join('');
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(
      `<html><head><title>Serving plan ${escapeHtml(sessionCode ?? '')}</title>` +
        `<style>body{font-family:sans-serif;padding:24px}table{border-collapse:collapse;width:100%}` +
        `td,th{border:1px solid #999;padding:8px;text-align:left}</style></head><body>` +
        `<h2>Serving plan — session ${escapeHtml(sessionCode ?? '')}</h2>` +
        `<table><thead><tr><th>Cycle</th><th>Cup</th><th>Description</th><th>Concentrations</th><th>Served</th></tr></thead>` +
        `<tbody>${rows}</tbody></table></body></html>`,
    );
    win.document.close();
    win.print();
  }

  return (
    <div className="bg-surface rounded-xl border border-border p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-text-primary">Serving Guide</h2>
        <button
          onClick={handlePrint}
          className="text-sm text-primary hover:text-primary-light underline"
        >
          Print serving plan
        </button>
      </div>

      {/* Serve now */}
      {current ? (
        <div className="p-4 mb-4 rounded-xl border-2 border-primary bg-primary/5">
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">
            Serve now — cycle {current.cycle} of {plan.total_cycles}
          </div>
          <div className="flex items-baseline gap-4 flex-wrap">
            <span className="text-4xl font-bold text-primary">
              {current.sample_id ? `Cup ${current.sample_id}` : modeText(current.mode) || 'Sample'}
            </span>
            {current.sample_label && (
              <span className="text-xl font-medium text-text-primary">{current.sample_label}</span>
            )}
          </div>
          {concentrationText(current, formatConcentration) && (
            <div className="text-sm text-text-secondary mt-1">
              {concentrationText(current, formatConcentration)}
            </div>
          )}
          {next && (
            <div className="text-sm text-text-secondary mt-3">
              Next: {next.sample_id ? `Cup ${next.sample_id}` : modeText(next.mode)}
              {next.sample_label ? ` — ${next.sample_label}` : ''}
            </div>
          )}
        </div>
      ) : (
        <div className="p-4 mb-4 rounded-xl border border-border text-text-secondary">
          All samples served.
        </div>
      )}

      {/* Full order */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left p-2 text-text-secondary font-medium">Cycle</th>
              <th className="text-left p-2 text-text-secondary font-medium">Cup</th>
              <th className="text-left p-2 text-text-secondary font-medium">Description</th>
              <th className="text-left p-2 text-text-secondary font-medium">Concentrations</th>
              <th className="text-left p-2 text-text-secondary font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {plan.entries.map((e) => (
              <tr
                key={e.cycle}
                className={`border-b border-border/50 ${
                  e.status === 'current' ? 'bg-primary/10 font-semibold' : ''
                } ${e.status === 'done' ? 'text-text-secondary' : ''}`}
              >
                <td className="p-2">{e.cycle}</td>
                <td className="p-2 font-bold">{e.sample_id ?? '—'}</td>
                <td className="p-2">{e.sample_label ?? ''}</td>
                <td className="p-2 text-text-secondary">
                  {concentrationText(e, formatConcentration) || modeText(e.mode)}
                </td>
                <td className="p-2">
                  {e.status === 'done' ? '✓ Done' : e.status === 'current' ? '▶ Now' : 'Upcoming'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
