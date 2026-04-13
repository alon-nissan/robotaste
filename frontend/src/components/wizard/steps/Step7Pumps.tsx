/**
 * Step 7: Pump Hardware (conditional — only if user enables pumps).
 * Serial port, pump-to-ingredient mapping, dispensing settings.
 */

import { useWizard } from '../../../context/WizardContext';
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

export default function Step7Pumps() {
  const { state, dispatch } = useWizard();
  const pump = state.protocol.pump_config ?? { enabled: false };
  const ingredients = state.protocol.ingredients ?? [];

  function setPump(config: PumpConfig) {
    dispatch({ type: 'SET_PUMP_CONFIG', payload: config });
  }

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
        serial_port: pump.serial_port || '/dev/cu.PL2303G-USBtoUART120',
        baud_rate: pump.baud_rate || 19200,
        pumps,
        total_volume_ml: pump.total_volume_ml || 10,
        dispensing_rate_ul_min: pump.dispensing_rate_ul_min || 90000,
        simultaneous_dispensing: pump.simultaneous_dispensing ?? true,
        use_burst_mode: pump.use_burst_mode ?? false,
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
                <label className="block text-xs font-medium text-gray-600 mb-1">Serial Port</label>
                <input
                  type="text"
                  value={pump.serial_port ?? ''}
                  onChange={(e) => setPump({ ...pump, serial_port: e.target.value })}
                  placeholder="/dev/cu.PL2303G-USBtoUART120"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
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
