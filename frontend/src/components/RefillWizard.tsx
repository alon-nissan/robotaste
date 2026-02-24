/**
 * RefillWizard Component — Multi-step guided syringe refill flow.
 *
 * Steps:
 * 1. Withdrawing — pump pulls liquid back from tubes (reduces spillage)
 * 2. Swap Syringe — moderator physically replaces the syringe
 * 3. Purging — pump pushes liquid through tubes (expels air)
 * 4. Enter Volume — moderator enters new syringe volume (mL)
 * 5. Done — refill complete with final volume confirmation
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';
import type { RefillStep, RefillOperationStatus } from '../types';

interface Props {
  protocolId: string;
  pumpAddress: number;
  ingredient: string;
  onComplete: () => void;
  onCancel: () => void;
}

export default function RefillWizard({
  protocolId,
  pumpAddress,
  ingredient,
  onComplete,
  onCancel,
}: Props) {
  const [step, setStep] = useState<RefillStep>('idle');
  const [, setOperationId] = useState<number | null>(null);
  const [operationStatus, setOperationStatus] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [newVolumeMl, setNewVolumeMl] = useState<string>('');
  const [finalResult, setFinalResult] = useState<{
    loaded_volume_ml: number;
    purge_volume_ul: number;
    final_volume_ml: number;
  } | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Poll refill operation status
  const pollStatus = useCallback(
    (opId: number, nextStep: RefillStep) => {
      if (pollRef.current) clearInterval(pollRef.current);

      pollRef.current = setInterval(async () => {
        try {
          const { data } = await api.get<RefillOperationStatus>(
            `/pump/refill/status/${opId}`
          );
          setOperationStatus(data.status);

          if (data.status === 'completed') {
            if (pollRef.current) clearInterval(pollRef.current);
            setStep(nextStep);
          } else if (data.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            setError(data.error_message || 'Operation failed');
          }
        } catch {
          // Keep polling on network errors
        }
      }, 1500);
    },
    []
  );

  // Step 1: Start withdraw
  async function startWithdraw() {
    setError('');
    setStep('withdrawing');

    try {
      const { data } = await api.post('/pump/refill/withdraw', {
        protocol_id: protocolId,
        pump_address: pumpAddress,
        ingredient,
      });
      setOperationId(data.operation_id);
      pollStatus(data.operation_id, 'swap_syringe');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start withdraw';
      setError(msg);
      setStep('idle');
    }
  }

  // Step 2: After syringe swap, start purge
  async function startPurge() {
    setError('');
    setStep('purging');

    try {
      const { data } = await api.post('/pump/refill/purge', {
        protocol_id: protocolId,
        pump_address: pumpAddress,
        ingredient,
      });
      setOperationId(data.operation_id);
      pollStatus(data.operation_id, 'enter_volume');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start purge';
      setError(msg);
      setStep('swap_syringe');
    }
  }

  // Step 3: Complete refill with new volume
  async function completeRefill() {
    const vol = parseFloat(newVolumeMl);
    if (isNaN(vol) || vol <= 0) {
      setError('Please enter a valid volume');
      return;
    }

    setError('');

    try {
      const { data } = await api.post('/pump/refill/complete', {
        protocol_id: protocolId,
        pump_address: pumpAddress,
        ingredient,
        new_volume_ml: vol,
      });
      setFinalResult({
        loaded_volume_ml: data.loaded_volume_ml,
        purge_volume_ul: data.purge_volume_ul,
        final_volume_ml: data.final_volume_ml,
      });
      setStep('done');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to complete refill';
      setError(msg);
    }
  }

  // ─── RENDER ────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-primary px-6 py-4">
          <h2 className="text-lg font-semibold text-white">
            Refill: {ingredient}
          </h2>
          <p className="text-sm text-white/70">Pump address {pumpAddress}</p>
        </div>

        <div className="p-6">
          {/* Step indicator */}
          <div className="flex items-center justify-center gap-2 mb-6">
            {(['withdrawing', 'swap_syringe', 'purging', 'enter_volume'] as const).map(
              (s, i) => (
                <div key={s} className="flex items-center gap-2">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      step === s
                        ? 'bg-primary text-white'
                        : step === 'done' ||
                          (['withdrawing', 'swap_syringe', 'purging', 'enter_volume'].indexOf(step) >
                            ['withdrawing', 'swap_syringe', 'purging', 'enter_volume'].indexOf(s))
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-200 text-text-secondary'
                    }`}
                  >
                    {i + 1}
                  </div>
                  {i < 3 && <div className="w-6 h-0.5 bg-gray-200" />}
                </div>
              )
            )}
          </div>

          {/* Error display */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg">
              {error}
            </div>
          )}

          {/* Step content */}
          {step === 'idle' && (
            <div className="text-center">
              <p className="text-text-secondary mb-4">
                This will guide you through the refill process:
              </p>
              <ol className="text-left text-sm text-text-secondary space-y-1 mb-6">
                <li>1. Withdraw liquid from tubes</li>
                <li>2. Replace the syringe</li>
                <li>3. Purge air from tubes</li>
                <li>4. Enter new volume</li>
              </ol>
              <div className="flex gap-3 justify-center">
                <button
                  onClick={onCancel}
                  className="px-4 py-2 text-sm text-text-secondary border border-border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={startWithdraw}
                  className="px-6 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-light"
                >
                  Start Refill
                </button>
              </div>
            </div>
          )}

          {step === 'withdrawing' && (
            <div className="text-center">
              <div className="text-4xl mb-3">⬅️</div>
              <p className="font-medium text-text-primary mb-2">
                Withdrawing liquid from tubes...
              </p>
              <p className="text-sm text-text-secondary mb-4">
                Please wait while the pump pulls liquid back.
              </p>
              <div className="flex items-center justify-center gap-2 text-sm text-text-secondary">
                <div className="animate-spin w-4 h-4 border-2 border-primary border-t-transparent rounded-full" />
                {operationStatus === 'in_progress' ? 'In progress...' : 'Waiting for pump...'}
              </div>
            </div>
          )}

          {step === 'swap_syringe' && (
            <div className="text-center">
              <div className="text-4xl mb-3">🔄</div>
              <p className="font-medium text-text-primary mb-2">
                Replace the syringe now
              </p>
              <p className="text-sm text-text-secondary mb-6">
                Remove the empty syringe and load a new one with fresh solution.
                Press "Continue" when the new syringe is installed.
              </p>
              <button
                onClick={startPurge}
                className="px-6 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-light"
              >
                Syringe Replaced — Continue
              </button>
            </div>
          )}

          {step === 'purging' && (
            <div className="text-center">
              <div className="text-4xl mb-3">➡️</div>
              <p className="font-medium text-text-primary mb-2">
                Purging air from tubes...
              </p>
              <p className="text-sm text-text-secondary mb-4">
                Pushing liquid through the tubes to expel air.
              </p>
              <div className="flex items-center justify-center gap-2 text-sm text-text-secondary">
                <div className="animate-spin w-4 h-4 border-2 border-primary border-t-transparent rounded-full" />
                {operationStatus === 'in_progress' ? 'In progress...' : 'Waiting for pump...'}
              </div>
            </div>
          )}

          {step === 'enter_volume' && (
            <div className="text-center">
              <div className="text-4xl mb-3">📏</div>
              <p className="font-medium text-text-primary mb-2">
                Enter new syringe volume
              </p>
              <p className="text-sm text-text-secondary mb-4">
                How much solution is now in the syringe? Enter the volume
                remaining after the purge.
              </p>
              <div className="flex items-center justify-center gap-2 mb-4">
                <input
                  type="number"
                  value={newVolumeMl}
                  onChange={(e) => setNewVolumeMl(e.target.value)}
                  placeholder="e.g. 60"
                  step="0.1"
                  min="0"
                  className="w-32 p-2 border border-border rounded-lg text-sm text-text-primary
                             focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
                  autoFocus
                />
                <span className="text-sm text-text-secondary">mL</span>
              </div>
              <button
                onClick={completeRefill}
                className="px-6 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-light"
              >
                Confirm Volume
              </button>
            </div>
          )}

          {step === 'done' && finalResult && (
            <div className="text-center">
              <div className="text-4xl mb-3">✅</div>
              <p className="font-medium text-text-primary mb-4">
                Refill complete!
              </p>
              <div className="text-sm text-text-secondary space-y-1 mb-6">
                <p className="font-medium text-text-primary">
                  Available: {finalResult.final_volume_ml.toFixed(1)} mL
                </p>
              </div>
              <button
                onClick={onComplete}
                className="px-6 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-light"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
