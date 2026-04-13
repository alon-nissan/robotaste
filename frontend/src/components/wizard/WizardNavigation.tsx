/**
 * WizardNavigation — Back / Next / Save buttons at the bottom of the wizard.
 */

import { useWizard, WIZARD_STEPS } from '../../context/WizardContext';

interface Props {
  onSave: () => void;
  saving?: boolean;
}

export default function WizardNavigation({ onSave, saving }: Props) {
  const { state, dispatch, needsBO } = useWizard();

  function isStepVisible(index: number): boolean {
    const step = WIZARD_STEPS[index];
    if (step.id === 'optimization' && !needsBO) return false;
    return true;
  }

  function getNextVisibleStep(from: number): number | null {
    for (let i = from + 1; i < WIZARD_STEPS.length; i++) {
      if (isStepVisible(i)) return i;
    }
    return null;
  }

  function getPrevVisibleStep(from: number): number | null {
    for (let i = from - 1; i >= 0; i--) {
      if (isStepVisible(i)) return i;
    }
    return null;
  }

  const isReviewStep = WIZARD_STEPS[state.currentStep]?.id === 'review';
  const nextStep = getNextVisibleStep(state.currentStep);
  const prevStep = getPrevVisibleStep(state.currentStep);

  return (
    <div className="shrink-0 border-t border-gray-200 bg-white px-6 py-4 flex items-center justify-between">
      <button
        type="button"
        onClick={() => prevStep !== null && dispatch({ type: 'SET_STEP', step: prevStep })}
        disabled={prevStep === null}
        className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Back
      </button>

      <div className="flex gap-3">
        {isReviewStep ? (
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {saving ? 'Saving...' : 'Save Protocol'}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => nextStep !== null && dispatch({ type: 'SET_STEP', step: nextStep })}
            disabled={nextStep === null}
            className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
