/**
 * WizardSidebar — Step indicator for the protocol creation wizard.
 * Shows all steps with current/visited/skipped states.
 */

import { useWizard, WIZARD_STEPS } from '../../context/WizardContext';

export default function WizardSidebar() {
  const { state, dispatch, needsBO, needsPumps } = useWizard();

  function isStepVisible(index: number): boolean {
    const step = WIZARD_STEPS[index];
    if (step.id === 'optimization' && !needsBO) return false;
    if (step.id === 'pumps' && !needsPumps) return false;
    return true;
  }

  function handleClick(index: number) {
    dispatch({ type: 'SET_STEP', step: index });
  }

  return (
    <nav className="w-64 shrink-0 border-r border-gray-200 bg-gray-50 p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-4">
        Protocol Steps
      </h2>
      <ol className="space-y-1">
        {WIZARD_STEPS.map((step, index) => {
          if (!isStepVisible(index)) return null;

          const isCurrent = state.currentStep === index;
          const isVisited = state.visitedSteps.has(index);

          return (
            <li key={step.id}>
              <button
                type="button"
                onClick={() => handleClick(index)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isCurrent
                    ? 'bg-blue-50 text-blue-700 font-medium border border-blue-200'
                    : isVisited
                      ? 'text-gray-700 hover:bg-gray-100'
                      : 'text-gray-400 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium shrink-0 ${
                      isCurrent
                        ? 'bg-blue-600 text-white'
                        : isVisited
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    {isVisited && !isCurrent ? '✓' : getVisibleIndex(index)}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate">{step.label}</div>
                    <div className="text-xs text-gray-400 truncate">{step.description}</div>
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );

  /** Compute display number (skipping hidden steps) */
  function getVisibleIndex(index: number): number {
    let count = 0;
    for (let i = 0; i <= index; i++) {
      if (isStepVisible(i)) count++;
    }
    return count;
  }
}
