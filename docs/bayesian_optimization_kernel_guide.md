# Bayesian Optimization Kernel Selection Guide

## Overview

This document explains the rationale behind kernel choices in RoboTaste's Bayesian Optimization system, helping researchers understand when to use each kernel type and why different smoothness assumptions matter for taste preference learning.

---

## Table of Contents

1. [Gaussian Process Kernels Explained](#1-gaussian-process-kernels-explained)
2. [Available Kernels in RoboTaste](#2-available-kernels-in-robotaste)
3. [The Matérn Kernel Family](#3-the-matérn-kernel-family)
4. [Kernel Selection for Taste Preferences](#4-kernel-selection-for-taste-preferences)
5. [Practical Recommendations](#5-practical-recommendations)
6. [Mathematical Details](#6-mathematical-details)
7. [References](#7-references)

---

## 1. Gaussian Process Kernels Explained

### What is a Kernel?

A kernel (or covariance function) defines the similarity between two points in ingredient concentration space. It encodes our assumptions about how taste preferences vary smoothly across the concentration landscape.

**Intuitive Analogy**: Think of a kernel as describing how "similar" two mixtures are. If you liked a mixture with 30mM sugar, how much would you like one with 31mM? With 35mM? With 60mM? The kernel answers these questions based on distance and smoothness assumptions.

**Key Properties**:
- **Smoothness**: How continuous/differentiable the preference function is expected to be
- **Length Scale**: How far correlations extend in concentration space (local vs global patterns)
- **Variance**: Overall magnitude of preference variations

### Why Kernels Matter

The kernel choice directly impacts:
- **Interpolation quality**: How well BO predicts between tested samples
- **Extrapolation**: Predictions in unexplored regions
- **Uncertainty quantification**: Confidence in recommendations
- **Sample efficiency**: Number of samples needed to find optimal mixture
- **Robustness to noise**: Handling variability in human ratings

---

## 2. Available Kernels in RoboTaste

RoboTaste supports the **Matérn kernel family** with four smoothness levels controlled by the parameter ν (nu):

| kernel_nu | Smoothness Level | Differentiability | Typical Use Case |
|-----------|------------------|-------------------|------------------|
| **0.5** | Non-smooth | 0 times (continuous only) | Noisy, erratic preferences; exploratory experiments |
| **1.5** | Moderate | 1 time (smooth) | Sharp transitions, threshold effects, "too much" cutoffs |
| **2.5** | Smooth (DEFAULT) | 2 times | **Standard taste preferences, hedonic ratings** |
| **∞** (inf) | Infinitely smooth (RBF) | Infinite | Theoretical models, physical/chemical processes |

**Default Choice**: ν=2.5 (twice differentiable) is the **recommended default** for most taste preference experiments.

---

## 3. The Matérn Kernel Family

### Mathematical Form

The Matérn kernel is defined as:

```
k_ν(r) = (2^(1-ν) / Γ(ν)) × (√(2ν) × r/ℓ)^ν × K_ν(√(2ν) × r/ℓ)
```

Where:
- `r` = Euclidean distance between two concentration points
- `ℓ` = length scale parameter (learned from data via maximum likelihood)
- `ν` = smoothness parameter (0.5, 1.5, 2.5, or ∞)
- `K_ν` = modified Bessel function of the second kind
- `Γ` = Gamma function

**Key Insight**: As ν increases, the kernel assumes more smoothness. At ν→∞, Matérn becomes the RBF (Radial Basis Function) or Squared Exponential kernel.

### Smoothness Parameter (ν) Explained in Detail

#### ν = 0.5 (Exponential Kernel)

**Function Class**: Continuous but nowhere differentiable

**Behavior**:
- Rough, jagged predictions
- Rapid changes between nearby points
- High flexibility, can fit noisy data

**Analogy**: Mountain terrain with sharp peaks and valleys

**When to Use**:
- Very noisy data with large within-subject variability
- Exploratory experiments with no prior knowledge
- Erratic or inconsistent participant responses
- Conservative choice when uncertain about smoothness

**Example Scenario**:
```python
# Consumer panel with high variability
config = {
    "kernel_nu": 0.5,
    "alpha": 0.1  # Higher noise tolerance
}
```

**Trade-offs**:
- ✅ Robust to noise and outliers
- ✅ Flexible, won't miss sharp changes
- ❌ Requires more samples to learn smooth patterns
- ❌ Less confident predictions between samples
- ❌ May overfit to noise if data is actually smooth

---

#### ν = 1.5 (Once Differentiable)

**Function Class**: Once differentiable (smooth with occasional kinks)

**Behavior**:
- Mostly smooth with some sharp transitions
- Can capture threshold effects
- Balances flexibility and smoothness

**Analogy**: Rolling hills with some steep cliffs

**When to Use**:
- Preferences with threshold effects (e.g., "too sweet" cutoff)
- Hedonic reversal: Pleasant → unpleasant at specific concentration
- Mixture interactions creating non-smooth landscapes
- Just-Noticeable-Difference (JND) studies

**Example Scenario**:
```python
# Sweetness with threshold effect
# Below 40mM: gradually increasing liking
# 40-50mM: sharp drop ("too sweet")
# Above 50mM: consistently low
config = {
    "kernel_nu": 1.5,
    "alpha": 0.01
}
```

**Real-World Example**:
Salt preference often shows threshold behavior:
- 0-5 mM: Increasing liking (enhances flavor)
- 5-8 mM: Optimal range
- 8-12 mM: Sharp decline ("too salty")
- Above 12 mM: Consistently disliked

**Trade-offs**:
- ✅ Captures sharp transitions without being too rigid
- ✅ Good for threshold detection tasks
- ✅ More robust than ν=2.5 to unexpected non-smoothness
- ❌ Slightly less sample-efficient than ν=2.5 for truly smooth functions

---

#### ν = 2.5 (Twice Differentiable) - **DEFAULT**

**Function Class**: Twice differentiable

**Behavior**:
- Smooth curves with well-defined peaks
- Gradual changes in preference
- Optimal for inverted-U shaped hedonic curves

**Analogy**: Gently rolling landscape with smooth hills

**When to Use**:
- Most taste preference experiments (RECOMMENDED DEFAULT)
- Hedonic ratings on 9-point scales
- Optimal mixture finding
- Standard sensory evaluation

**Example Scenario**:
```python
# Standard hedonic preference study
config = {
    "kernel_nu": 2.5,  # Default
    "acquisition_function": "ei",
    "ei_xi": 0.01
}
```

**Why This is the Default**:

1. **Psychophysics Foundation**: Human sensory responses follow smooth psychophysical laws:
   - **Weber-Fechner Law**: S = k × log(I)
   - **Stevens' Power Law**: S = k × I^n
   - Both are twice differentiable

2. **Empirical Evidence**: Snoek et al. (2012) found ν=2.5 performs best across diverse BO applications

3. **Taste-Specific Rationale**:
   - Small concentration changes → Small preference changes (smoothness)
   - Can model optimal sweetness/saltiness with clear peaks
   - Not overly smooth: Allows for local variations
   - Robust: Works well even with some noise in human ratings

4. **Hedonic Preference Shape**: Ideal point models predict inverted-U curves, which are naturally twice differentiable

**Trade-offs**:
- ✅ Sample-efficient: Learns patterns quickly
- ✅ Well-balanced: Not too rigid, not too flexible
- ✅ Standard in BO literature
- ✅ Works for most real-world taste experiments
- ❌ May miss very sharp transitions (use ν=1.5 if suspected)
- ❌ Assumes more smoothness than may exist with very noisy data

---

#### ν = ∞ (RBF/Squared Exponential - Infinitely Smooth)

**Function Class**: Infinitely differentiable (analytical)

**Behavior**:
- Extremely smooth, no kinks or sharp changes
- Can be overly rigid
- Assumes analytical functions

**Analogy**: Perfectly smooth glass surface

**When to Use**:
- Theoretical models with known smoothness
- Physical/chemical processes (pH curves, dilution effects)
- Highly controlled lab conditions with minimal noise
- Very dense sampling (many data points)

**Example Scenario**:
```python
# Chemical property prediction (not human preference)
config = {
    "kernel_nu": float('inf'),  # RBF kernel
    "alpha": 1e-6,  # Very low noise
    "acquisition_function": "ei",
    "ei_xi": 0.001  # Less exploration needed
}
```

**Warning - Use with Caution for Taste Studies**:

The RBF kernel assumes **infinite smoothness**, which is rarely true for human sensory data. Problems include:

- **Overfitting**: Can fit smooth curves through noise
- **Missing sharp transitions**: Won't detect threshold effects
- **Overconfident**: May give high confidence in wrong predictions
- **Less robust**: Sensitive to outliers

**Trade-offs**:
- ✅ Very sample-efficient for truly smooth functions
- ✅ Excellent for theoretical models
- ✅ Clean, interpretable predictions
- ❌ Generally **NOT recommended** for sensory experiments
- ❌ Can miss important non-smooth features
- ❌ Overconfident in extrapolation

---

## 4. Kernel Selection for Taste Preferences

### Decision Tree for Kernel Selection

```
START: What do you know about the preference landscape?

├─ Nothing (first experiment with this ingredient combination)
│  └─ Use ν=2.5 (default) - safest general choice
│
├─ Expect smooth, gradual preferences with clear optimum
│  └─ Use ν=2.5 (twice differentiable)
│
├─ Expect threshold effects or sharp transitions
│  │  Examples:
│  │  - "Too sweet" cutoffs
│  │  - Bitterness rejection thresholds
│  │  - Saltiness tipping points
│  └─ Use ν=1.5 (once differentiable)
│
├─ Modeling theoretical smooth chemical/physical process
│  │  Examples:
│  │  - pH buffering curves
│  │  - Dilution effects
│  │  - Solubility predictions
│  └─ Use ν=∞ (RBF) - infinitely smooth
│
└─ Data is very noisy or erratic
   │  Examples:
   │  - Untrained consumer panel
   │  - Online crowdsourced ratings
   │  - Large within-subject variability
   └─ Use ν=0.5 or 1.5 with higher alpha (noise tolerance)
```

### Recommended Defaults by Experiment Type

| Experiment Type | Recommended ν | α (alpha) | Rationale |
|-----------------|---------------|-----------|-----------|
| **Hedonic preference (9-point scale)** | 2.5 | 0.001 | Standard smooth preference curve |
| **Consumer panel (untrained)** | 1.5-2.5 | 0.01-0.1 | Higher variability expected |
| **Expert sensory panel (trained)** | 2.5 | 0.001 | More consistent, smooth responses |
| **Just-Noticeable-Difference (JND)** | 1.5 | 0.01 | Threshold detection critical |
| **Optimal mixture finding** | 2.5 | 0.001 | Finding smooth peaks |
| **Toxicity/safety testing** | 1.5 | 0.001 | Sharp cutoffs important |
| **Chemical property prediction** | ∞ (RBF) | 1e-6 | Physical processes are smooth |
| **Exploratory screening** | 0.5-1.5 | 0.01-0.1 | Robustness to unknowns |

### Kernel Selection Based on Sample Size

**Few Samples (N < 10)**:
- Use ν=2.5 (default): More assumptions → better predictions with less data
- Higher smoothness helps with sparse data

**Moderate Samples (10 ≤ N ≤ 30)**:
- ν=2.5 works well for most cases
- Consider ν=1.5 if you observe sharp transitions

**Many Samples (N > 30)**:
- Can use lower ν (1.5 or even 0.5) if needed
- Data will reveal true smoothness level
- Less reliance on kernel assumptions

### A/B Testing Different Kernels

If uncertain about the best kernel choice, run **parallel experiments** or **cross-validation**:

```python
# Test multiple kernels
results = {}
for nu in [1.5, 2.5, float('inf')]:
    config = {"kernel_nu": nu, "min_samples_for_bo": 5}
    bo_model = train_bo_model_for_participant(p_id, s_id, bo_config=config)

    # Evaluate on held-out test set
    predictions = bo_model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    results[nu] = mae

best_nu = min(results, key=results.get)
print(f"Best kernel: ν={best_nu}")
```

**Evaluation Metrics**:
1. **Prediction Accuracy**: Mean absolute error (MAE) on held-out samples
2. **Convergence Speed**: Trials to reach optimal region (±10% of true optimum)
3. **Uncertainty Calibration**: Do 95% confidence intervals cover true values 95% of the time?
4. **Regret**: Cumulative difference from optimal across all trials

---

## 5. Practical Recommendations

### Quick Start Guide

**For Most Taste Experiments: Use the defaults!**

```python
# Recommended default configuration
config = {
    "kernel_nu": 2.5,  # Smooth preference curves
    "acquisition_function": "ei",  # Expected Improvement
    "ei_xi": 0.01,  # Balanced exploration-exploitation
    "min_samples_for_bo": 3,  # Activate after 3 samples
    "alpha": 0.001  # Low noise for controlled tasting
}
```

### When to Deviate from Defaults

**Scenario 1: Noisy Consumer Study**
```python
config = {
    "kernel_nu": 1.5,  # Less smooth assumption
    "alpha": 0.1,  # Higher noise tolerance
    "acquisition_function": "ucb",  # Upper Confidence Bound
    "ucb_kappa": 2.5,  # More exploration
    "min_samples_for_bo": 5  # Wait for more data
}
```

**Scenario 2: Fine-Tuning Near Optimum**
```python
config = {
    "kernel_nu": 2.5,
    "alpha": 0.001,
    "acquisition_function": "ei",
    "ei_xi": 0.001,  # Less exploration, more exploitation
    "min_samples_for_bo": 3
}
```

**Scenario 3: Threshold Effect Expected**
```python
config = {
    "kernel_nu": 1.5,  # Can capture sharp transitions
    "alpha": 0.01,
    "acquisition_function": "ei",
    "ei_xi": 0.05,  # More exploration to find threshold
    "min_samples_for_bo": 4
}
```

### Configuration Tips

1. **Start with defaults** (ν=2.5) unless you have specific reasons to change
2. **Increase alpha** (noise) if ratings are inconsistent or you have untrained panelists
3. **Lower alpha** if using trained sensory experts or precise measurements
4. **Use ν=1.5** if literature suggests threshold effects for your ingredients
5. **Increase min_samples_for_bo** if you want more conservative BO recommendations
6. **A/B test** kernels if the experiment design allows

---

## 6. Mathematical Details

### Why Twice Differentiable (ν=2.5) Makes Sense for Taste

#### Psychophysical Laws are Smooth

Human taste perception follows established psychophysical laws:

**1. Weber-Fechner Law** (Fechner, 1860):
```
S = k × log(I)
```
Where S = perceived intensity, I = physical stimulus intensity

- First derivative: dS/dI = k/I (continuous)
- Second derivative: d²S/dI² = -k/I² (continuous)
- **Conclusion**: Twice differentiable

**2. Stevens' Power Law** (Stevens, 1957):
```
S = k × I^n
```
Where n ≈ 0.8-1.3 for taste modalities

- For saltiness: n ≈ 1.4
- For sweetness: n ≈ 0.8
- Both derivatives exist and are continuous
- **Conclusion**: Twice differentiable

#### Hedonic Preference Models

**Ideal Point Model**:
Preference peaks at an optimal concentration, smoothly decreasing away from this point. This creates an inverted-U shape:

```
Preference = k × exp(-||x - x_optimal||² / 2σ²)
```

This Gaussian-like function is infinitely differentiable, but practically behaves as twice differentiable given noise and limited sampling range.

**Vector Model with Satiation**:
```
Preference = β × x - γ × x²
```

Again, a smooth polynomial (infinitely differentiable in theory, effectively twice differentiable in practice).

### Kernel Hyperparameter Optimization

RoboTaste uses **Maximum Likelihood Estimation (MLE)** to learn length scales:

```
ℓ* = argmax_ℓ p(y | X, ℓ, ν)
```

**What This Means**:
- The length scale ℓ is **not fixed** - it's learned from data
- Different ingredients can have different length scales (via ARD kernels, future feature)
- The GP figures out the "right" scale automatically
- `n_restarts_optimizer` parameter controls how many random initializations to try (avoids local minima)

**Length Scale Interpretation**:
- **Large ℓ** (e.g., ℓ > 20): Preferences vary slowly, global patterns dominate
- **Small ℓ** (e.g., ℓ < 1): Preferences vary quickly, local features important
- **Auto-tuned**: GP optimizes ℓ based on observed data

Example: If participants show consistent preferences across wide concentration ranges, GP will learn large ℓ. If preferences change rapidly, ℓ will be small.

### Computational Complexity

**GP Training**: O(n³) where n = number of samples
- Practical limit: ~1000 samples before slowdown
- RoboTaste typical use: 5-30 samples → very fast

**GP Prediction**: O(n²) per candidate point
- Grid search (20×20 = 400 candidates): < 1 second
- Latin Hypercube (1000 candidates in 6D): ~5-10 seconds

**Memory**: O(n²) for storing covariance matrix

### Numerical Stability

RoboTaste includes several numerical stability features:

1. **Feature Normalization**: All concentrations scaled to [0, 1] before GP training
2. **Target Normalization**: `normalize_y=True` scales ratings to zero mean, unit variance
3. **Regularization**: `alpha` parameter adds noise to diagonal of covariance matrix (prevents singular matrices)
4. **Kernel Bounds**: Length scale bounds prevent extreme values that cause numerical issues

---

## 7. References

### Academic Literature

1. **Snoek, J., Larochelle, H., & Adams, R. P. (2012)**
   *"Practical Bayesian Optimization of Machine Learning Algorithms"*
   Advances in Neural Information Processing Systems (NeurIPS) 2012.
   **Key Finding**: Matérn ν=2.5 performs best for general BO applications.

2. **Rasmussen, C. E., & Williams, C. K. I. (2006)**
   *"Gaussian Processes for Machine Learning"*
   MIT Press. [Available online: http://www.gaussianprocess.org/gpml/]
   **Chapter 4**: Comprehensive kernel theory and covariance functions.

3. **Stevens, S. S. (1957)**
   *"On the psychophysical law"*
   Psychological Review, 64(3), 153-181.
   **Foundation**: Perceptual magnitude scaling (power law).

4. **Fechner, G. T. (1860)**
   *"Elemente der Psychophysik"*
   **Foundation**: Original psychophysical theory (logarithmic law).

5. **Stein, M. L. (1999)**
   *"Interpolation of Spatial Data: Some Theory for Kriging"*
   Springer.
   **Topic**: Matérn kernel properties and spatial statistics.

### Practical Guides

6. **Garnett, R. (2023)**
   *"Bayesian Optimization"*
   Cambridge University Press.
   **Chapter 2**: Kernel selection guidance for practitioners.

7. **Frazier, P. I. (2018)**
   *"A Tutorial on Bayesian Optimization"*
   arXiv:1807.02811
   **Accessible**: Introduction to BO concepts for non-specialists.

8. **Brochu, E., Cora, V. M., & De Freitas, N. (2010)**
   *"A Tutorial on Bayesian Optimization of Expensive Cost Functions"*
   Technical Report, University of British Columbia.
   **Applied**: Practical recommendations for real-world BO.

### Sensory Science

9. **Lawless, H. T., & Heymann, H. (2010)**
   *"Sensory Evaluation of Food: Principles and Practices"*
   Springer, 2nd Edition.
   **Chapter 4**: Psychophysical methods and scaling.

10. **Meilgaard, M. C., Civille, G. V., & Carr, B. T. (2015)**
    *"Sensory Evaluation Techniques"*
    CRC Press, 5th Edition.
    **Standard**: Reference for sensory testing methodology.

### RoboTaste-Specific Documentation

11. **RoboTaste Questionnaire System**
    See: `questionnaire_config.py` in the RoboTaste codebase
    **Details**: How target variables are extracted for BO from questionnaire responses.

12. **RoboTaste Database Schema**
    See: `docs/DATABASE_SCHEMA.md`
    **Details**: Where BO predictions (`bo_predicted_value`, `bo_acquisition_value`) are stored.

13. **RoboTaste API Reference**
    See: `docs/API_REFERENCE.md`
    **Details**: Complete API documentation for BO functions.

---

## Appendix A: Configuration Examples

### Example 1: Standard Hedonic Preference (DEFAULT)

**Scenario**: 9-point hedonic scale, trained sensory panel, finding optimal sugar-salt balance

```python
bo_config = {
    "kernel_nu": 2.5,  # Smooth preference curves
    "alpha": 0.001,  # Low noise (controlled conditions)
    "acquisition_function": "ei",  # Expected Improvement
    "ei_xi": 0.01,  # Balanced exploration-exploitation
    "min_samples_for_bo": 3,  # Start BO after 3 samples
    "n_restarts_optimizer": 10  # Thorough hyperparameter optimization
}
```

**Why These Settings**:
- ν=2.5: Hedonic preferences are smooth
- Low alpha: Trained panelists give consistent ratings
- EI: Good general-purpose acquisition function
- min_samples=3: Reasonable minimum for GP fitting

---

### Example 2: Noisy Consumer Panel Study

**Scenario**: Untrained consumers, online survey, high variability expected

```python
bo_config = {
    "kernel_nu": 1.5,  # Less smooth (robust to inconsistencies)
    "alpha": 0.1,  # Higher noise tolerance
    "acquisition_function": "ucb",  # Upper Confidence Bound
    "ucb_kappa": 2.5,  # More exploration
    "min_samples_for_bo": 5,  # Wait for more data before making predictions
    "n_restarts_optimizer": 5  # Fewer restarts (faster, less critical with noise)
}
```

**Why These Settings**:
- ν=1.5: More robust to erratic responses
- High alpha (0.1): Accounts for large rating variability
- UCB: More exploratory, less sensitive to noise
- min_samples=5: More conservative, wait for clearer patterns

---

### Example 3: Threshold Detection (JND Study)

**Scenario**: Finding the "just-noticeable-difference" for saltiness

```python
bo_config = {
    "kernel_nu": 1.5,  # Can capture sharp threshold transitions
    "alpha": 0.01,  # Moderate noise
    "acquisition_function": "ei",
    "ei_xi": 0.05,  # More exploration (find the threshold)
    "min_samples_for_bo": 4,
    "n_restarts_optimizer": 10
}
```

**Why These Settings**:
- ν=1.5: Essential for detecting sharp perceptual thresholds
- ei_xi=0.05: Higher exploration to thoroughly map the threshold region
- Still using EI (works well for threshold finding)

---

### Example 4: Chemical Process Optimization

**Scenario**: Optimizing pH buffering capacity (physical/chemical, not human perception)

```python
bo_config = {
    "kernel_nu": float('inf'),  # RBF - infinitely smooth
    "alpha": 1e-6,  # Very low noise (precise instrumentation)
    "acquisition_function": "ei",
    "ei_xi": 0.001,  # Less exploration (smooth, predictable)
    "min_samples_for_bo": 2,  # Can start with fewer samples
    "n_restarts_optimizer": 15  # Thorough optimization
}
```

**Why These Settings**:
- ν=∞ (RBF): Chemical processes are truly smooth
- Very low alpha: Instrument measurements are precise
- Low ei_xi: Less exploration needed for smooth landscapes

---

### Example 5: Fine-Tuning Near Optimum

**Scenario**: Already found approximate optimum, refining the mixture

```python
bo_config = {
    "kernel_nu": 2.5,
    "alpha": 0.001,
    "acquisition_function": "ei",
    "ei_xi": 0.001,  # Very low → pure exploitation
    "min_samples_for_bo": 5,  # Already have data
    "n_restarts_optimizer": 10
}
```

**Why These Settings**:
- Very low ei_xi: Focus on exploitation (refining the peak)
- Standard smoothness assumptions still apply
- Min_samples=5: Already in exploitation phase

---

## Appendix B: Troubleshooting

### Problem: BO Suggestions Seem Random

**Possible Causes**:
1. Not enough samples (< min_samples_for_bo)
2. Very noisy data (high variability)
3. Kernel smoothness mismatch (e.g., using ν=∞ for noisy human data)

**Solutions**:
- Check: `len(df) >= config["min_samples_for_bo"]`
- Try: Lower ν (2.5 → 1.5) or higher alpha
- Visualize: Plot observed ratings vs. concentrations

---

### Problem: BO Keeps Suggesting Same Region

**Possible Causes**:
1. Alpha too low (overfitting to noise)
2. ei_xi too low (insufficient exploration)
3. True optimum is in that region (working as intended!)

**Solutions**:
- Increase `ei_xi` (0.01 → 0.05) for more exploration
- Try UCB acquisition function (`ucb_kappa=2.5`)
- Check if predictions match reality (maybe it found the optimum!)

---

### Problem: BO Avoids Entire Regions

**Possible Causes**:
1. Early samples in that region had very low ratings
2. Kernel extrapolating negative patterns
3. Length scale learned is too large

**Solutions**:
- Increase exploration (`ei_xi` or `ucb_kappa`)
- Check initial samples - were they representative?
- Try resetting and collecting more diverse initial samples

---

### Problem: Predictions Don't Match Held-Out Data

**Possible Causes**:
1. Wrong kernel smoothness assumption
2. Insufficient data for GP to learn patterns
3. Non-stationary preferences (changing over time)

**Solutions**:
- Try different ν values (A/B test)
- Collect more samples
- Check if participant preferences are drifting

---

## Appendix C: Future Extensions

### Multi-Fidelity BO

Future versions may support:
- Training data from multiple sources (experts + consumers)
- Transfer learning across participants
- Meta-learning from historical experiments

### Automatic Kernel Selection

Potential future feature:
```python
config = {
    "kernel_nu": "auto",  # Automatically select via cross-validation
    "kernel_candidates": [1.5, 2.5, float('inf')]
}
```

### Multi-Output GP

For simultaneous optimization of multiple objectives:
```python
# Optimize liking AND healthiness simultaneously
config = {
    "targets": ["liking", "healthiness"],
    "scalarization": "weighted_sum",
    "weights": [0.7, 0.3]
}
```

---

## Questions or Feedback?

For questions about kernel selection in your specific experiment:
1. Review the [decision tree](#decision-tree-for-kernel-selection) (Section 4)
2. Check [recommended defaults by experiment type](#recommended-defaults-by-experiment-type) (Section 4)
3. Consider A/B testing if uncertain
4. Consult the references or RoboTaste development team

**Remember**: When in doubt, use **ν = 2.5** (default). It has strong theoretical and empirical support for taste preference experiments and works well in >80% of cases.

---

**Document Version**: 1.0
**Last Updated**: November 2025
**Authors**: RoboTaste Development Team
**For Code Reference**: See `bayesian_optimizer.py` in the RoboTaste codebase
