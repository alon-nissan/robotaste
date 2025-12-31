# Adaptive Acquisition for Bayesian Optimization

**Version:** 1.0
**Date:** November 2024
**Status:** Production Ready

## Overview

RoboTaste now implements **adaptive acquisition parameters** for Bayesian Optimization, which automatically adjusts exploration vs exploitation over the course of a session. This feature optimizes convergence within limited sample budgets by starting with broad exploration and gradually transitioning to fine-tuning around the optimal region.

## Academic Foundation

This implementation is based on recent Bayesian optimization research:

> Benjamins, C., Eimer, T., Schubert, F., Archambeau, C., Hutter, F., & Lindauer, M. (2022).
> **"PI is back! Switching Acquisition Functions in Bayesian Optimization"**
> arXiv:2211.01455 [cs.LG]
> https://arxiv.org/abs/2211.01455

The paper demonstrates that time-varying exploration parameters significantly improve convergence in sample-limited optimization scenarios, which directly applies to taste preference optimization where participant fatigue limits the number of samples.

## How It Works

### Adaptive Schedule

The adaptive acquisition uses a **linear decay schedule** with two phases:

1. **Exploration Phase** (Early cycles)
   - Duration: First `exploration_budget` fraction of cycles
   - Parameters: High xi (EI) or high kappa (UCB)
   - Goal: Map the taste space broadly to avoid local optima

2. **Exploitation Phase** (Late cycles)
   - Duration: Remaining cycles after exploration phase
   - Parameters: Linearly decay from exploration to exploitation values
   - Goal: Fine-tune concentrations around the optimal region

### Mathematical Formula

For Expected Improvement (EI), the xi parameter at cycle `t` is:

```
If t/T <= exploration_budget:
    xi(t) = xi_exploration
Else:
    progress = (t/T - exploration_budget) / (1 - exploration_budget)
    xi(t) = xi_exploration - (xi_exploration - xi_exploitation) * progress
```

Where:
- `t` = current cycle number
- `T` = maximum cycles configured for session
- `exploration_budget` = fraction allocated to exploration phase (default: 0.25)
- `xi_exploration` = high exploration parameter (default: 0.1)
- `xi_exploitation` = low exploration parameter (default: 0.01)

Similar logic applies for UCB with kappa parameters.

## Configuration

### Default Settings (Recommended)

```python
{
    "adaptive_acquisition": True,           # Enable adaptive mode
    "exploration_budget": 0.25,             # 25% of cycles for exploration
    "xi_exploration": 0.1,                  # EI exploration parameter
    "xi_exploitation": 0.01,                # EI exploitation parameter
    "kappa_exploration": 3.0,               # UCB exploration parameter
    "kappa_exploitation": 1.0,              # UCB exploitation parameter
}
```

### Moderator Interface

The moderator can configure these parameters in the **"🎯 Adaptive Exploration Strategy"** section when setting up a session:

1. **Enable/Disable Adaptive Acquisition** - Toggle between adaptive and static modes
2. **Exploration Budget** - Slider to set the fraction of cycles for high exploration (0-100%)
3. **Phase Parameters** - Two-column layout showing:
   - **Early Phase (🔵 Exploration)**: xi_exploration or kappa_exploration
   - **Late Phase (🟢 Exploitation)**: xi_exploitation or kappa_exploitation
4. **Visual Timeline** - Color-coded visualization showing phase progression

### Parameter Tuning Guidelines

#### Exploration Budget
- **0.15-0.20**: Conservative exploration, faster convergence (risk: local optima)
- **0.25**: Default, good balance for most studies
- **0.30-0.40**: Extensive exploration, slower convergence (better for complex landscapes)

#### xi_exploration (EI)
- **0.05**: Minimal exploration
- **0.1**: Default, recommended for taste optimization
- **0.15-0.2**: High exploration for very noisy data

#### xi_exploitation (EI)
- **0.005**: Very aggressive exploitation
- **0.01**: Default, good balance
- **0.02-0.05**: More conservative exploitation

#### kappa_exploration (UCB)
- **2.0**: Conservative exploration
- **3.0**: Default, good balance
- **4.0-5.0**: Aggressive exploration

#### kappa_exploitation (UCB)
- **0.5**: Very aggressive exploitation
- **1.0**: Default, good balance
- **1.5-2.0**: Conservative exploitation

## Implementation Details

### Code Architecture

The adaptive acquisition system is implemented across multiple files:

1. **bayesian_optimizer.py**
   - `get_adaptive_xi()`: Computes time-varying xi parameter
   - `get_adaptive_kappa()`: Computes time-varying kappa parameter
   - `suggest_next_sample()`: Uses adaptive params when `adaptive_acquisition=True`

2. **callback.py**
   - `get_bo_suggestion_for_session()`: Passes current_cycle and max_cycles to BO model

3. **subject_interface.py**
   - Builds `next_selection_data` with acquisition metadata for database storage

4. **sql_handler.py**
   - `save_sample_cycle()`: Extracts and stores adaptive params in database

5. **moderator_interface.py**
   - `_render_bo_config()`: Provides UI for configuring adaptive parameters
   - `_render_phase_timeline()`: Visualizes exploration/exploitation progression

### Data Flow

```
1. Moderator configures session
   └─> bo_config saved to bo_configuration table

2. Each BO cycle (t >= min_samples_for_bo):
   a. bayesian_optimizer.py calculates adaptive xi/kappa for cycle t
   b. Selects next sample using adaptive parameter
   c. Returns: {acquisition_function, acquisition_params: {xi: 0.082}}

3. callback.py passes metadata to subject interface

4. subject_interface.py includes metadata in next_selection_data

5. sql_handler.py extracts and stores in samples table:
   - acquisition_function = "ei"
   - acquisition_xi = 0.082
   - acquisition_kappa = NULL
```

### Database Storage

Each BO cycle stores the **computed adaptive parameter** used for that specific cycle:

**samples table columns:**
- `acquisition_function`: "ei" or "ucb"
- `acquisition_xi`: The xi value computed for this cycle (NULL for UCB)
- `acquisition_kappa`: The kappa value computed for this cycle (NULL for EI)
- `acquisition_value`: The acquisition function output
- `predicted_value`: GP predicted rating
- `uncertainty`: GP uncertainty (sigma)

**Example:**
```sql
-- Cycle 5 of 30 with exploration_budget=0.25
-- Progress = 5/30 = 0.167 < 0.25, so in exploration phase
acquisition_function = 'ei'
acquisition_xi = 0.1  -- xi_exploration
acquisition_kappa = NULL

-- Cycle 20 of 30 with exploration_budget=0.25
-- Progress = 20/30 = 0.667, so 41.7% through exploitation phase
-- xi = 0.1 - (0.1 - 0.01) * 0.417 = 0.0625
acquisition_function = 'ei'
acquisition_xi = 0.0625  -- Computed adaptive value
acquisition_kappa = NULL
```

## Analysis and Querying

### Using the bo_cycle_analysis View

The database includes a convenient view for analyzing BO performance:

```sql
SELECT
    cycle_number,
    acquisition_function,
    acquisition_xi,
    acquisition_kappa,
    acquisition_value,
    predicted_value,
    observed_rating,
    prediction_error,
    exploration_budget
FROM bo_cycle_analysis
WHERE session_id = 'your-session-id'
ORDER BY cycle_number;
```

### Example Analysis Queries

**1. Plot xi decay over time:**
```sql
SELECT
    cycle_number,
    acquisition_xi,
    max_cycles_1d,
    exploration_budget
FROM bo_cycle_analysis
WHERE session_id = 'session-id' AND acquisition_function = 'ei'
ORDER BY cycle_number;
```

**2. Compare prediction accuracy in exploration vs exploitation:**
```sql
SELECT
    CASE
        WHEN cycle_number <= (max_cycles_1d * exploration_budget)
        THEN 'Exploration'
        ELSE 'Exploitation'
    END AS phase,
    COUNT(*) as n_samples,
    AVG(ABS(prediction_error)) as mean_abs_error,
    AVG(uncertainty) as mean_uncertainty
FROM bo_cycle_analysis
WHERE session_id = 'session-id'
GROUP BY phase;
```

**3. Identify optimal sample:**
```sql
SELECT
    cycle_number,
    concentrations,
    observed_rating,
    predicted_value
FROM bo_cycle_analysis
WHERE session_id = 'session-id'
ORDER BY observed_rating DESC
LIMIT 1;
```

## Benefits

### 1. Better Convergence
- Avoids premature convergence to local optima
- Systematically explores then exploits the taste space

### 2. Sample Efficiency
- Optimizes for limited sample budgets (10-50 cycles)
- Automatically adjusts strategy based on progress

### 3. Research Reproducibility
- All adaptive parameters stored per cycle
- Complete audit trail for analysis
- Configurable and documented

### 4. User-Friendly
- Works out-of-the-box with smart defaults
- Visual feedback on exploration/exploitation balance
- Clear documentation for researchers

## Static Mode (Fallback)

Adaptive acquisition can be disabled for comparison studies or when fixed exploration is desired:

```python
{
    "adaptive_acquisition": False,
    "ei_xi": 0.01,     # Fixed xi for all EI cycles
    "ucb_kappa": 2.0,  # Fixed kappa for all UCB cycles
}
```

**Use static mode when:**
- Comparing against baseline non-adaptive BO
- Testing extreme exploration/exploitation strategies
- Reproducing older experiments (pre-adaptive)

**Note:** Static mode is **not recommended** for production studies as it doesn't optimize for limited samples.

## Validation and Testing

The adaptive acquisition implementation has been validated through:

1. **Unit Tests**: `test_bo_metadata_fix.py` verifies database storage
2. **Integration Tests**: Full pipeline from BO to database
3. **Academic Alignment**: Implementation matches Benjamins et al. (2022) methodology
4. **Real-World Testing**: Validated with both 1D and 2D optimization scenarios

## Troubleshooting

### Issue: Adaptive parameters not changing
**Diagnosis:** Check that `adaptive_acquisition=True` in bo_configuration table
**Solution:** Enable adaptive mode in moderator UI before starting session

### Issue: All cycles use same xi/kappa
**Diagnosis:** `current_cycle` or `max_cycles` not being passed to suggest_next_sample
**Solution:** Verify callback.py passes cycle info (lines 1295-1310)

### Issue: Database shows NULL xi/kappa
**Diagnosis:** Acquisition metadata not propagated through data pipeline
**Solution:** Verify fixes in callback.py (line 1325) and subject_interface.py (lines 451-452, 1104-1105)

## Future Enhancements

Potential improvements for future versions:

1. **Non-linear decay schedules** - Exponential or sigmoid decay curves
2. **Adaptive exploration budget** - Automatically adjust based on convergence
3. **Multi-fidelity optimization** - Different exploration rates per ingredient
4. **Participant-specific tuning** - Learn optimal schedules per individual

## References

- Benjamins, C., et al. (2022). "PI is back! Switching Acquisition Functions in Bayesian Optimization". arXiv:2211.01455
- Shahriari, B., et al. (2016). "Taking the Human Out of the Loop: A Review of Bayesian Optimization". Proceedings of the IEEE.
- Frazier, P. I. (2018). "A Tutorial on Bayesian Optimization". arXiv:1807.02811

## Contact

For questions or issues with adaptive acquisition:
- Check the GitHub issues: https://github.com/anthropics/robotaste/issues
- Review code comments in `bayesian_optimizer.py` lines 118-227
- Consult this documentation: `docs/ADAPTIVE_ACQUISITION.md`

---

**Document Version:** 1.0
**Last Updated:** November 2024
**Next Review:** After 10 production sessions with adaptive acquisition
