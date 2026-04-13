/**
 * Step 7: Pump Hardware.
 * Serial port, pump-to-ingredient mapping, dispensing settings.
 */

import { useState, useEffect } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { api } from '../../../api/client';
import type { PumpConfig, PumpMapping } from '../../../types';

const SYRINGE_PRESETS = [
  { label: '1 mL BD (4.7 mm)', diameter: 4.7 },
  { label: '3 mL BD (8.6 mm)', diameter: 8.6 },
  { label: '5 mL BD (12.0 mm)', diameter: 12.0 },
  { label: '10 mL BD (14.4 mm)', diameter: 14.4 },
  { label: '20 mL BD (19.1 mm)', diameter: 19.1 },
  { label: '30 mL BD (21.6 mm)', diameter: 21.6 },
  { label: '50 mL BD (26.6 mm)', diameter: 26.6 },
  { label: '60 mL BD (29.0 mm)', diameter: 29.0 },
];

interface SerialPort {
  device: string;
  description: string;
  hwid: string;
}

export default function Step7Pumps() {
  const { state, dispatch } = useWizard();
  const pump = state.protocol.pump_config ?? { enabled: false };
  const ingredients = state.protocol.ingredients ?? [];

  const [availablePorts, setAvailablePorts] = useState<SerialPort[]>([]);
  const [portsLoading, setPortsLoading] = useState(false);
  const [manualEntry, setManualEntry] = useState(false);

  function setPump(config: PumpConfig) {
    dispatch({ type: 'SET_PUMP_CONFIG', payload: config });
  }

  async function fetchPorts(applyRecommended = false) {
    setPortsLoading(true);
    try {
      const res = await api.get<{ ports: SerialPort[]; recommended: string | null }>('/pump/ports');
      setAvailablePorts(res.data.ports);
      if (applyRecommended && res.data.recommended && !pump.serial_port) {
        setPump({ ...pump, serial_port: res.data.recommended });
      }
    } catch {
      setAvailablePorts([]);
    } finally {
      setPortsLoading(false);
    }
  }

  // Fetch available ports when pumps are enabled
  useEffect(() => {
    if (pump.enabled) {
      fetchPorts(true);
    }
  }, [pump.enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleEnabled(enabled: boolean) {
    if (enabled) {
      // Auto-generate pump mappings from ingredients
      const pumps: PumpMapping[] = ingredients.map((ing, i) => ({
        address: i,
        ingredient: ing.name,
        syringe_diameter_mm: 29.0,
        max_rate_ul_min: 90000,
        stock_concentration_mM: ing.stock_concentration_mM ?? 0,
      }));
      setPump({
        ...pump,
        enabled: true,
        serial_port: pump.serial_port || '',
        baud_rate: pump.baud_rate || 19200,
        pumps,
        total_volume_ml: pump.total_volume_ml || 10,
        dispensing_rate_ul_min: pump.dispensing_rate_ul_min || 90000,
        simultaneous_dispensing: pump.simultaneous_dispensing ?? true,
        use_burst_mode: pump.use_burst_mode ?? true,
      });
    } else {
      setPump({ enabled: false });
    }
  }

  function updatePumpMapping(index: number, updates: Partial<PumpMapping>) {
    const pumps = (pump.pumps ?? []).map((p, i) => (i === index ? { ...p, ...updates } : p));
    setPump({ ...pump, pumps });
  }

  const hasBurstWarning =
    pump.use_burst_mode && (pump.pumps ?? []).some((p) => p.address > 9);

  const currentPort = pump.serial_port ?? '';
  // Show manual entry if the user has typed a port not in the detected list,
  // or if they explicitly requested manual entry
  const portInList = availablePorts.some((p) => p.device === currentPort);
  const showManual = manualEntry || (currentPort !== '' && !portInList);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Pump Hardware</h2>
        <p className="text-sm text-gray-500">
          Configure syringe pumps if the robot will prepare samples automatically.
        </p>
      </div>

      {/* Enable toggle */}
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium text-gray-700">
          Will this experiment use automated syringe pumps?
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => toggleEnabled(true)}
            className={`px-4 py-1.5 text-sm rounded-lg border transition-colors ${
              pump.enabled
                ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium'
                : 'border-gray-300 text-gray-600 hover:border-gray-400'
            }`}
          >
            Yes
          </button>
          <button
            type="button"
            onClick={() => toggleEnabled(false)}
            className={`px-4 py-1.5 text-sm rounded-lg border transition-colors ${
              !pump.enabled
                ? 'bg-gray-100 border-gray-400 text-gray-700 font-medium'
                : 'border-gray-300 text-gray-600 hover:border-gray-400'
            }`}
          >
            No
          </button>
        </div>
      </div>

      {pump.enabled && (
        <>
          {/* Connection */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Connection</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-medium text-gray-600">Serial Port</label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => fetchPorts(false)}
                      disabled={portsLoading}
                      className="text-xs text-blue-600 hover:text-blue-700 disabled:text-gray-400"
                    >
                      {portsLoading ? 'Scanning…' : 'Refresh'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setManualEntry((v) => !v)}
                      className="text-xs text-gray-500 hover:text-gray-700"
                    >
                      {showManual ? 'Use dropdown' : 'Enter manually'}
                    </button>
                  </div>
                </div>

                {showManual ? (
                  <input
                    type="text"
                    value={currentPort}
                    onChange={(e) => setPump({ ...pump, serial_port: e.target.value })}
                    placeholder="e.g. /dev/ttyUSB0  or  COM3"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                ) : (
                  <select
                    value={currentPort}
                    onChange={(e) => setPump({ ...pump, serial_port: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {availablePorts.length === 0 ? (
                      <option value="">— No serial ports detected —</option>
                    ) : (
                      <>
                        <option value="">Select a port…</option>
                        {availablePorts.map((p) => (
                          <option key={p.device} value={p.device}>
                            {p.device}
                            {p.description && p.description !== 'n/a' ? ` — ${p.description}` : ''}
                          </option>
                        ))}
                      </>
                    )}
                  </select>
                )}

                {availablePorts.length === 0 && !portsLoading && !showManual && (
                  <p className="text-xs text-amber-600 mt-1">
                    No ports found. Make sure the pump is plugged in, then click Refresh.
                  </p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Baud Rate</label>
                <select
                  value={pump.baud_rate ?? 19200}
                  onChange={(e) => setPump({ ...pump, baud_rate: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={9600}>9600</option>
                  <option value={19200}>19200</option>
                </select>
              </div>
            </div>
          </div>

          {/* Pump assignments */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Pump Assignments</h3>
            {ingredients.length === 0 ? (
              <p className="text-sm text-gray-400">
                Add ingredients in Step 2 first — pump assignments are auto-generated from your ingredient list.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left text-xs font-medium text-gray-500 py-2">Ingredient</th>
                      <th className="text-left text-xs font-medium text-gray-500 py-2">Address</th>
                      <th className="text-left text-xs font-medium text-gray-500 py-2">Syringe Size</th>
                      <th className="text-left text-xs font-medium text-gray-500 py-2">Stock Conc. (mM)</th>
                      <th className="text-left text-xs font-medium text-gray-500 py-2">Dual Syringe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(pump.pumps ?? []).map((p, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        <td className="py-2 pr-3 font-medium text-gray-700">{p.ingredient}</td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            value={p.address}
                            onChange={(e) =>
                              updatePumpMapping(i, { address: parseInt(e.target.value) || 0 })
                            }
                            min={0}
                            max={99}
                            className="w-16 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <select
                            value={p.syringe_diameter_mm}
                            onChange={(e) =>
                              updatePumpMapping(i, {
                                syringe_diameter_mm: parseFloat(e.target.value),
                              })
                            }
                            className="w-44 px-2 py-1 border border-gray-300 rounded text-sm bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                          >
                            {SYRINGE_PRESETS.map((s) => (
                              <option key={s.diameter} value={s.diameter}>
                                {s.label}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            value={p.stock_concentration_mM}
                            onChange={(e) =>
                              updatePumpMapping(i, {
                                stock_concentration_mM: parseFloat(e.target.value) || 0,
                              })
                            }
                            step="any"
                            className="w-24 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="checkbox"
                            checked={p.dual_syringe ?? false}
                            onChange={(e) =>
                              updatePumpMapping(i, { dual_syringe: e.target.checked })
                            }
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Dispensing settings */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Dispensing Settings</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Total Sample Volume (mL)
                </label>
                <input
                  type="number"
                  value={pump.total_volume_ml ?? 10}
                  onChange={(e) =>
                    setPump({ ...pump, total_volume_ml: parseFloat(e.target.value) || 10 })
                  }
                  step="any"
                  min={0.1}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Dispensing Rate (uL/min)
                </label>
                <input
                  type="number"
                  value={pump.dispensing_rate_ul_min ?? 90000}
                  onChange={(e) =>
                    setPump({
                      ...pump,
                      dispensing_rate_ul_min: parseInt(e.target.value) || 90000,
                    })
                  }
                  min={1}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex gap-6 mt-3">
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={pump.simultaneous_dispensing ?? true}
                  onChange={(e) =>
                    setPump({ ...pump, simultaneous_dispensing: e.target.checked })
                  }
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Simultaneous dispensing
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={pump.use_burst_mode ?? false}
                  onChange={(e) =>
                    setPump({ ...pump, use_burst_mode: e.target.checked })
                  }
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Burst mode
              </label>
            </div>
            {hasBurstWarning && (
              <p className="text-xs text-amber-600 mt-2">
                Burst mode requires all pump addresses to be 0-9. Some addresses are above 9.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
