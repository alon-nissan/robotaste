# RoboTaste Protocol JSON Schema Reference

**Version:** 1.0
**Last Updated:** January 2026

---

## Overview

This document provides a complete reference for the RoboTaste protocol JSON format. Protocols define reusable experiment configurations that control:

- **Ingredients** and their concentration ranges
- **Sample selection schedule** (predetermined/user/BO modes)
- **Questionnaire type** for participant responses
- **Bayesian Optimization** settings
- **Stopping criteria** for experiment completion

---

## Complete Schema Structure

```json
{
  "protocol_id": "uuid-string",
  "name": "string",
  "version": "string",
  "description": "string",
  "tags": ["string", ...],
  "ingredients": [...],
  "sample_selection_schedule": [...],
  "questionnaire_type": "string",
  "bayesian_optimization": {...},
  "stopping_criteria": {...},
  "protocol_hash": "string",
  "created_at": "ISO-8601-datetime",
  "updated_at": "ISO-8601-datetime"
}
```

---

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Protocol name (recommended to be unique) |
| `version` | string | Semantic version (e.g., "1.0", "2.3") |
| `ingredients` | array | List of ingredient definitions |
| `sample_selection_schedule` | array | Sample mode schedule by cycle range |
| `questionnaire_type` | string | Questionnaire identifier |

---

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `protocol_id` | string | auto-generated | UUID for protocol (auto-assigned on creation) |
| `description` | string | "" | Protocol description |
| `tags` | array[string] | [] | Tags for organization and search |
| `bayesian_optimization` | object | {} | BO configuration |
| `stopping_criteria` | object | {} | Experiment stopping rules |
| `protocol_hash` | string | auto-computed | SHA-256 hash of protocol content |
| `created_at` | string | auto-set | ISO-8601 datetime of creation |
| `updated_at` | string | auto-set | ISO-8601 datetime of last update |
| `is_archived` | boolean | false | Archive status |
| `created_by` | string | "" | Creator identifier |
| `derived_from` | string | null | Protocol ID this was derived from |

---

## Ingredients

Defines the taste ingredients and their concentration ranges.

### Structure

```json
{
  "ingredients": [
    {
      "name": "Sugar",
      "min_concentration": 0.0,
      "max_concentration": 100.0
    },
    {
      "name": "Salt",
      "min_concentration": 0.0,
      "max_concentration": 50.0
    }
  ]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✓ | Ingredient name (must match defaults) |
| `min_concentration` | float | ✓ | Minimum concentration in mM |
| `max_concentration` | float | ✓ | Maximum concentration in mM |

### Notes
- Ingredient names must match those defined in `robotaste/config/defaults.py`
- Concentration units are always in millimolar (mM)
- Valid ingredient names: Sugar, Salt, Citric Acid, Caffeine, MSG

---

## Sample Selection Schedule

Defines which selection mode to use for each cycle range.

### Structure

```json
{
  "sample_selection_schedule": [
    {
      "cycle_range": {"start": 1, "end": 2},
      "mode": "predetermined",
      "predetermined_samples": [
        {"cycle": 1, "concentrations": {"Sugar": 10.0, "Salt": 2.0}},
        {"cycle": 2, "concentrations": {"Sugar": 20.0, "Salt": 4.0}}
      ]
    },
    {
      "cycle_range": {"start": 3, "end": 5},
      "mode": "user_selected"
    },
    {
      "cycle_range": {"start": 6, "end": 10},
      "mode": "bo_selected",
      "config": {
        "allow_override": true
      }
    }
  ]
}
```

### Schedule Block Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cycle_range` | object | ✓ | Start and end cycle numbers (inclusive) |
| `cycle_range.start` | integer | ✓ | First cycle (1-indexed) |
| `cycle_range.end` | integer | ✓ | Last cycle (1-indexed, ≥ start) |
| `mode` | string | ✓ | Selection mode (see below) |
| `predetermined_samples` | array | conditional | Required if mode="predetermined" |
| `config` | object | optional | Mode-specific configuration |

### Selection Modes

#### 1. **predetermined** - Fixed Sample Sequence

Pre-defined concentrations for each cycle.

**Use case:** Calibration trials, validation samples, known reference points

**Required fields:**
```json
{
  "mode": "predetermined",
  "predetermined_samples": [
    {
      "cycle": 1,
      "concentrations": {"Sugar": 10.0, "Salt": 2.0}
    }
  ]
}
```

#### 2. **user_selected** - Manual Selection

Subject manually selects sample via UI (grid or sliders).

**Use case:** Exploratory experiments, giving subjects control

**Example:**
```json
{
  "mode": "user_selected"
}
```

#### 3. **bo_selected** - Bayesian Optimization

BO algorithm suggests next sample based on previous responses.

**Use case:** Adaptive optimization, preference learning

**Example:**
```json
{
  "mode": "bo_selected",
  "config": {
    "allow_override": true
  }
}
```

**Config options:**
- `allow_override` (boolean): Allow subject to reject BO suggestion

### Validation Rules

1. **No overlapping ranges:** Cycle ranges cannot overlap
2. **Contiguous cycles:** Recommended (gaps allowed but not recommended)
3. **Predetermined samples:** Must cover all cycles in range
4. **BO mode:** Requires `bayesian_optimization` config in protocol

---

## Questionnaire Type

Specifies which questionnaire to use for participant responses.

### Supported Types

| Type | Description |
|------|-------------|
| `hedonic_continuous` | 9-point hedonic scale (continuous slider) |
| `hedonic_discrete` | 9-point hedonic scale (discrete buttons) |
| `intensity` | Intensity rating scale |
| `liking` | Simple liking scale |

### Example

```json
{
  "questionnaire_type": "hedonic_continuous"
}
```

---

## Bayesian Optimization Configuration

Configures the BO algorithm when using `bo_selected` mode.

### Structure

```json
{
  "bayesian_optimization": {
    "enabled": true,
    "acquisition_function": "ucb",
    "kernel": "rbf",
    "params": {
      "kappa": 2.5,
      "xi": 0.01
    }
  }
}
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable BO |
| `acquisition_function` | string | "ucb" | Acquisition function (ucb, ei, poi) |
| `kernel` | string | "rbf" | GP kernel type |
| `params` | object | {} | Acquisition function parameters |
| `params.kappa` | float | 2.5 | Exploration parameter for UCB |
| `params.xi` | float | 0.01 | Exploration parameter for EI |

### Acquisition Functions

- **UCB** (Upper Confidence Bound): Balances exploration/exploitation via `kappa`
- **EI** (Expected Improvement): Maximizes expected improvement via `xi`
- **POI** (Probability of Improvement): Maximizes probability of finding better point

---

## Pump Configuration

Pump configuration lives under `pump_config` and provides per-pump hardware
settings. The per-pump `volume_unit` controls whether each pump uses `ML` or
`UL` for `VOL` commands.

See `docs/pump_config.md` for the full field list and examples.

## Stopping Criteria

Defines when the experiment should end.

### Structure

```json
{
  "stopping_criteria": {
    "max_cycles": 20,
    "convergence_threshold": 0.01,
    "min_cycles": 5
  }
}
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_cycles` | integer | ∞ | Maximum number of cycles |
| `convergence_threshold` | float | null | BO convergence threshold |
| `min_cycles` | integer | 0 | Minimum cycles before allowing stop |

---

## Loading Screen Configuration

Customizes the loading/preparation screen displayed between experiment cycles.

### Structure

```json
{
  "loading_screen": {
    "message": "Please rinse your mouth with water while the robot prepares the next sample.",
    "duration_seconds": 5,
    "show_progress": true,
    "show_cycle_info": true,
    "message_size": "large"
  }
}
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | string | "Rinse your mouth..." | Instructions displayed during loading |
| `duration_seconds` | integer | 5 | Display duration (1-60 seconds) |
| `show_progress` | boolean | true | Show animated progress bar |
| `show_cycle_info` | boolean | true | Show cycle number (e.g., "Cycle 3 of 10") |
| `message_size` | string | "large" | Font size: "normal" (1.5rem), "large" (2.5rem), "extra_large" (3.5rem) |

### Visual Layout

The loading screen displays:
1. **Cycle Information** (if `show_cycle_info`: true) - Large blue heading showing current cycle
2. **Message** - Instructions text in configurable size
3. **Progress Bar** (if `show_progress`: true) - Animated bar filling over `duration_seconds`

### Example Configurations

**Default (minimal config):**
```json
{
  "loading_screen": {}
}
```
Uses all default values.

**Custom message with longer duration:**
```json
{
  "loading_screen": {
    "message": "Take a moment to rinse thoroughly. The next sample will be ready soon.",
    "duration_seconds": 8
  }
}
```

**Extra large text, no progress bar:**
```json
{
  "loading_screen": {
    "message": "RINSE YOUR MOUTH",
    "message_size": "extra_large",
    "show_progress": false
  }
}
```

### Notes

- If `loading_screen` is omitted entirely, all defaults are used
- Cycle information automatically shows "Cycle X of Y" if `max_cycles` is set in `stopping_criteria`
- Progress bar animates smoothly, updating 10 times per second
- Message supports line breaks and basic formatting

---

## Complete Example Protocol

```json
{
  "name": "Sugar-Salt Preference Learning",
  "version": "1.0",
  "description": "Adaptive experiment to learn subject preference for sugar-salt mixtures",
  "tags": ["preference-learning", "two-ingredient", "bo"],

  "ingredients": [
    {
      "name": "Sugar",
      "min_concentration": 0.0,
      "max_concentration": 100.0
    },
    {
      "name": "Salt",
      "min_concentration": 0.0,
      "max_concentration": 50.0
    }
  ],

  "sample_selection_schedule": [
    {
      "cycle_range": {"start": 1, "end": 2},
      "mode": "predetermined",
      "predetermined_samples": [
        {"cycle": 1, "concentrations": {"Sugar": 10.0, "Salt": 5.0}},
        {"cycle": 2, "concentrations": {"Sugar": 50.0, "Salt": 25.0}}
      ]
    },
    {
      "cycle_range": {"start": 3, "end": 5},
      "mode": "user_selected"
    },
    {
      "cycle_range": {"start": 6, "end": 20},
      "mode": "bo_selected",
      "config": {
        "allow_override": true
      }
    }
  ],

  "questionnaire_type": "hedonic_continuous",

  "bayesian_optimization": {
    "enabled": true,
    "acquisition_function": "ucb",
    "kernel": "rbf",
    "params": {
      "kappa": 2.5,
      "xi": 0.01
    }
  },

  "stopping_criteria": {
    "max_cycles": 20,
    "min_cycles": 8
  }
}
```

---

## Import/Export Format

### Exporting for Sharing

When exporting protocols for sharing (e.g., via clipboard), internal metadata is removed:

**Removed fields:**
- `protocol_id`
- `created_at`
- `updated_at`
- `protocol_hash`
- `is_archived`
- `deleted_at`
- `created_by`
- `derived_from`

### Importing Protocols

When importing, these fields are automatically regenerated:
- `protocol_id` - New UUID assigned
- `protocol_hash` - Computed from content
- `created_at`, `updated_at` - Set to current time

---

## Validation

Protocols are validated against this schema before saving. Validation checks:

1. **Required fields present**
2. **Cycle ranges valid** (start ≤ end, no overlaps)
3. **Predetermined samples complete** (all cycles covered)
4. **BO config present** if using `bo_selected` mode
5. **Ingredient names valid** (match defaults)
6. **Selection modes valid** (predetermined/user_selected/bo_selected)

### Validation Errors

Common validation errors and solutions:

| Error | Solution |
|-------|----------|
| "Missing required field: name" | Add `name` field |
| "Cycle ranges overlap" | Adjust ranges to be non-overlapping |
| "Predetermined mode requires predetermined_samples" | Add `predetermined_samples` array |
| "BO mode requires bayesian_optimization config" | Add `bayesian_optimization` object |
| "Invalid mode" | Use predetermined/user_selected/bo_selected |

---

## Versioning

Protocols use semantic versioning (MAJOR.MINOR):

- **Major version increment** (1.0 → 2.0): Significant changes (ingredient list, core structure)
- **Minor version increment** (1.0 → 1.1): Small tweaks (schedule adjustments, parameter tuning)

Use `increment_protocol_version()` to create new versions programmatically.

---

## See Also

- [Protocol User Guide](protocol_user_guide.md) - Step-by-step usage instructions
- [Project Context](PROJECT_CONTEXT.md) - Architecture overview
- Example protocols in `protocols/test_protocol_mixed_mode_new_format.json`
