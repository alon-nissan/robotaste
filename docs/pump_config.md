# Pump Configuration (Protocol JSON)

This section describes the pump configuration fields that can appear inside a
protocol JSON under `pump_config`.

## Example

```json
{
  "pump_config": {
    "enabled": true,
    "serial_port": "/dev/cu.PL2303G-USBtoUART120",
    "baud_rate": 19200,
    "total_volume_ml": 10.0,
    "dispensing_rate_ul_min": 2000,
    "simultaneous_dispensing": true,
    "use_burst_mode": true,
    "pumps": [
      {
        "address": 0,
        "ingredient": "Sugar",
        "syringe_diameter_mm": 29.0,
        "volume_unit": "ML"
      },
      {
        "address": 1,
        "ingredient": "Water",
        "syringe_diameter_mm": 29.0,
        "volume_unit": "UL"
      }
    ]
  }
}
```

## Pump Fields

- `address`: Pump address (0-99). Burst mode requires 0-9.
- `ingredient`: Ingredient name (must match protocol `ingredients`).
- `syringe_diameter_mm`: Syringe inner diameter (0.1-50.0 mm).
- `volume_unit`: Volume unit for the pump. Must be `ML` or `UL`.
  - `ML` uses milliliters for `VOL` commands.
  - `UL` uses microliters for `VOL` commands (max 9999).
- `dual_syringe`: *(optional, default `false`)* When `true`, indicates that two
  identical syringes are loaded on the same pump body. The system halves the
  commanded volume (both syringes dispense the same amount) and doubles the
  effective capacity for volume tracking.

## Dual Syringe Mode

The NE-4000 pump can hold two syringes that operate simultaneously with
identical parameters. When you set `VOL 5.000` and `RUN`, **both** syringes
dispense 5 mL each, delivering 10 mL total.

To enable dual syringe for a specific pump, add `"dual_syringe": true`:

```json
{
  "address": 0,
  "ingredient": "Sugar",
  "syringe_diameter_mm": 29.0,
  "dual_syringe": true
}
```

**Behavior when enabled:**
- Commanded volume is halved: to dispense 10 mL total, the pump receives `VOL 5.000`.
- Volume tracking capacity is doubled: a 50 mL syringe tracks as 100 mL capacity.
- Syringe diameter stays the same (both syringes are identical).
- The setting is per-pump: some pumps can use dual while others use single.

## Notes

- `volume_unit` is per pump and applied during both initialization and dispense.
- When `use_burst_mode` is enabled, the system will send a single burst command
  to configure diameter, rate, direction, volume unit, and volume for all pumps
  with addresses 0-9.
