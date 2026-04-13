/**
 * Review Step — Summary of all protocol sections with validation status.
 * Shows accordion sections, allows downloading JSON.
 */

import { useState } from 'react';
import { useWizard } from '../../../context/WizardContext';

export default function ReviewStep() {
  const { state, needsBO, needsPumps } = useWizard();
  const p = state.protocol;

  const errors = validate(p, needsBO);

  function downloadJSON() {
    const json = JSON.stringify(buildFinalProtocol(p), null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(p.name ?? 'protocol').replace(/\s+/g, '_').toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Review Protocol</h2>
        <p className="text-sm text-gray-500">
          Review your protocol before saving. Fix any issues highlighted below.
        </p>
      </div>

      {/* Validation banner */}
      {errors.length > 0 ? (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <h3 className="text-sm font-medium text-amber-800 mb-2">
            {errors.length} issue{errors.length > 1 ? 's' : ''} found
          </h3>
          <ul className="text-xs text-amber-700 space-y-1">
            {errors.map((err, i) => (
              <li key={i}>- {err}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
          <h3 className="text-sm font-medium text-green-800">All good! Your protocol is ready to save.</h3>
        </div>
      )}

      {/* Sections */}
      <div className="space-y-2">
        <Section title="Overview" status={p.name ? 'ok' : 'error'}>
          <Row label="Name" value={p.name || '(empty)'} />
          <Row label="Description" value={p.description || '(none)'} />
          <Row label="Tags" value={(p.tags ?? []).join(', ') || '(none)'} />
        </Section>

        <Section
          title="Ingredients"
          status={(p.ingredients ?? []).length > 0 ? 'ok' : 'error'}
        >
          {(p.ingredients ?? []).map((ing, i) => (
            <Row
              key={i}
              label={ing.name || `Ingredient ${i + 1}`}
              value={`${ing.min_concentration} - ${ing.max_concentration} ${ing.unit ?? 'mM'}`}
            />
          ))}
          {(p.ingredients ?? []).length === 0 && (
            <p className="text-xs text-gray-400">No ingredients defined</p>
          )}
        </Section>

        <Section
          title="Schedule"
          status={(p.sample_selection_schedule ?? []).length > 0 ? 'ok' : 'error'}
        >
          <Row
            label="Cycles"
            value={`${p.stopping_criteria?.min_cycles ?? '?'} - ${p.stopping_criteria?.max_cycles ?? '?'}`}
          />
          {(p.sample_selection_schedule ?? []).map((block, i) => (
            <Row
              key={i}
              label={`Block ${i + 1}`}
              value={`Cycles ${block.cycle_range.start}-${block.cycle_range.end}: ${block.mode}`}
            />
          ))}
        </Section>

        <Section
          title="Questionnaire"
          status={(p.questionnaire?.questions ?? []).length > 0 ? 'ok' : 'error'}
        >
          <Row label="Name" value={p.questionnaire?.name || '(empty)'} />
          <Row
            label="Questions"
            value={`${(p.questionnaire?.questions ?? []).length} question(s)`}
          />
          {p.questionnaire?.bayesian_target?.variable && (
            <Row label="Optimization Target" value={p.questionnaire.bayesian_target.variable} />
          )}
        </Section>

        {needsBO && (
          <Section title="Optimization" status={p.bayesian_optimization?.enabled ? 'ok' : 'warn'}>
            <Row
              label="Acquisition"
              value={p.bayesian_optimization?.acquisition_function?.toUpperCase() ?? 'Not set'}
            />
          </Section>
        )}

        <Section title="Participant Experience" status="ok">
          <Row
            label="Phases"
            value={(p.phase_sequence?.phases ?? []).map((ph) => ph.phase_id).join(' → ')}
          />
          <Row
            label="Loading Duration"
            value={`${p.loading_screen?.duration_seconds ?? 5}s`}
          />
        </Section>

        {needsPumps && (
          <Section title="Pump Hardware" status={p.pump_config?.enabled ? 'ok' : 'warn'}>
            <Row label="Serial Port" value={p.pump_config?.serial_port ?? '(not set)'} />
            <Row label="Pumps" value={`${(p.pump_config?.pumps ?? []).length} pump(s)`} />
            <Row
              label="Volume"
              value={`${p.pump_config?.total_volume_ml ?? 10} mL at ${p.pump_config?.dispensing_rate_ul_min ?? '?'} uL/min`}
            />
          </Section>
        )}
      </div>

      {/* Download button */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={downloadJSON}
          className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Download JSON
        </button>
      </div>
    </div>
  );
}


// ─── Helpers ─────────────────────────────────────────────────────────────────

function validate(p: ReturnType<typeof useWizard>['state']['protocol'], needsBO: boolean): string[] {
  const errors: string[] = [];
  if (!p.name) errors.push('Protocol name is required (Step 1).');
  if ((p.ingredients ?? []).length === 0) errors.push('At least one ingredient is required (Step 2).');
  if ((p.sample_selection_schedule ?? []).length === 0)
    errors.push('At least one schedule block is required (Step 3).');
  if ((p.questionnaire?.questions ?? []).length === 0)
    errors.push('At least one question is required (Step 4).');
  if (needsBO && !p.bayesian_optimization?.enabled)
    errors.push('Bayesian optimization must be enabled for bo_selected mode (Step 5).');

  const stopping = p.stopping_criteria;
  if (stopping && stopping.min_cycles && stopping.max_cycles < stopping.min_cycles)
    errors.push('Max cycles must be >= min cycles (Step 3).');

  return errors;
}

function buildFinalProtocol(p: ReturnType<typeof useWizard>['state']['protocol']) {
  // Strip undefined fields and return clean JSON
  return JSON.parse(JSON.stringify(p));
}


// ─── UI Components ───────────────────────────────────────────────────────────

function Section({
  title,
  status,
  children,
}: {
  title: string;
  status: 'ok' | 'warn' | 'error';
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);

  const icon = status === 'ok' ? '✓' : status === 'warn' ? '!' : '×';
  const iconColor =
    status === 'ok'
      ? 'text-green-600 bg-green-100'
      : status === 'warn'
        ? 'text-amber-600 bg-amber-100'
        : 'text-red-600 bg-red-100';

  return (
    <div className="border border-gray-200 rounded-lg">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <span
          className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${iconColor}`}
        >
          {icon}
        </span>
        <span className="text-sm font-medium text-gray-700 flex-1">{title}</span>
        <span className="text-gray-400 text-xs">{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="px-4 pb-3 space-y-1">{children}</div>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-700 text-right max-w-[60%] truncate">{value}</span>
    </div>
  );
}
