# Stage 4 Candidate Vetting: Feature Schema Audit

## 1. Executive Summary

The Stage 4 candidate vetting schema consists of **exactly 52 deterministic features**:
- **22 Baseline Features**: Preserved identically from Stage 3 (`FeatureExtractor`).
- **30 New Transit Morphology & Context Features**: Developed to address BLS periodic false alarms on real TESS data.

All features are computed label-blind and strictly per-light-curve using each candidate's detected BLS parameters $(P, t_0, T_{\text{dur}}, \delta)$.

## 2. Feature Schema Table

| Index | Feature Name | Group | Physical Category | Expected Physical Utility | Edge-Case / Missing Contract |
| :---: | :--- | :---: | :---: | :--- | :--- |
| 1 | `bls_sde` | `baseline` | BLS Peak Prominence | Primary spectral detection efficiency | Always defined (finite float) |
| 2 | `bls_snr` | `baseline` | BLS Transit SNR | Transit depth over photometric error in transit | Always defined (finite float) |
| 3 | `bls_period` | `baseline` | BLS Period | Detected period in days | Always defined (finite float) |
| 4 | `bls_depth` | `baseline` | BLS Depth | Detected fractional depth | Always defined (finite float) |
| 5 | `bls_duration` | `baseline` | BLS Duration | Detected transit duration in days | Always defined (finite float) |
| 6 | `bls_duty_cycle` | `baseline` | BLS Duty Cycle | Detected duration / period | Always defined (finite float) |
| 7 | `bls_max_power` | `baseline` | BLS Power | Peak periodogram objective power | Always defined (finite float) |
| 8 | `flux_std` | `baseline` | Flux Distribution | Overall standard deviation of light curve | Always defined (finite float) |
| 9 | `flux_skewness` | `baseline` | Flux Distribution | Sample skewness of flux | 0.0 if cadences < 5 |
| 10 | `flux_kurtosis` | `baseline` | Flux Distribution | Sample kurtosis of flux | 0.0 if cadences < 5 |
| 11 | `flux_mad` | `baseline` | Flux Distribution | Median absolute deviation of flux | Always defined (finite float) |
| 12 | `flux_p1` | `baseline` | Flux Distribution | 1st percentile of flux | Always defined (finite float) |
| 13 | `flux_p5` | `baseline` | Flux Distribution | 5th percentile of flux | Always defined (finite float) |
| 14 | `flux_iqr` | `baseline` | Flux Distribution | Interquartile range (p75 - p25) | Always defined (finite float) |
| 15 | `flux_min` | `baseline` | Flux Distribution | Minimum flux value | Always defined (finite float) |
| 16 | `flux_depth_robust` | `baseline` | Flux Distribution | Median minus 1st percentile | Always defined (finite float) |
| 17 | `von_neumann_ratio` | `baseline` | Dynamics | Serial correlation metric (eta) | 2.0 if cadences < 4 |
| 18 | `outlier_fraction_low` | `baseline` | Outliers | Fraction of flux points < med - 3 sigma | Always defined (finite float) |
| 19 | `outlier_fraction_high` | `baseline` | Outliers | Fraction of flux points > med + 3 sigma | Always defined (finite float) |
| 20 | `folded_transit_depth` | `baseline` | Folded Diagnostics | Median out minus median in flux | 0.0 if P <= 0 |
| 21 | `odd_even_depth_ratio` | `baseline` | Folded Diagnostics | Odd vs even depth min/max ratio | 1.0 if P <= 0 or duration <= 0 |
| 22 | `secondary_eclipse_depth` | `baseline` | Folded Diagnostics | Depth at phase 0.5 | 0.0 if P <= 0 or duration <= 0 |
| 23 | `shape_depth_to_local_mad` | `shape` | Geometry | Detected depth divided by local out-of-transit scatter | np.nan if local cadences < 5 |
| 24 | `shape_candidate_duty_cycle` | `shape` | Geometry | Candidate duration / period | np.nan if P <= 0 or T_dur <= 0 |
| 25 | `shape_in_out_contrast` | `shape` | Geometry | Contrast between in-transit and out-of-transit flux | np.nan if in < 3 or out < 10 |
| 26 | `shape_ingress_ratio` | `shape` | Geometry | Estimated ingress+egress width / total duration | np.nan if unresolvable; [0, 1] |
| 27 | `shape_in_transit_fraction` | `shape` | Geometry | Fraction of valid cadences inside transit | Always defined [0, 1] |
| 28 | `shape_in_transit_mad` | `shape` | Geometry | MAD dispersion inside transit window | np.nan if in < 5 |
| 29 | `shape_mad_ratio` | `shape` | Geometry | Ratio of in-transit to out-of-transit MAD | np.nan if in < 5 or out < 10 |
| 30 | `morph_symmetry` | `morphology` | Profile | Correlation between folded ingress and flipped egress | np.nan if bins < 5 or zero var |
| 31 | `morph_ingress_egress_diff` | `morphology` | Profile | Flux difference between ingress and egress wings / depth | np.nan if wing cadences < 3 |
| 32 | `morph_flat_bottom_kurtosis` | `morphology` | Profile | Excess kurtosis of in-transit flux points | np.nan if in-transit cadences < 10 |
| 33 | `morph_broad_depression_ratio` | `morphology` | Profile | Dip in 3x duration window vs 1x duration window | np.nan if duty cycle >= 0.30 |
| 34 | `morph_core_to_wing_ratio` | `morphology` | Profile | Core transit depth / (core + wing depth) | np.nan if core < 3 or wings < 3 |
| 35 | `event_n_observed` | `event_consistency` | Events | Count of transit windows crossing data baseline | Always defined integer >= 0 |
| 36 | `event_n_adequate` | `event_consistency` | Events | Count of transit windows with >=5 cadences & >=50% coverage | Always defined integer >= 0 |
| 37 | `event_adequate_fraction` | `event_consistency` | Events | Ratio of adequate events to observed events | Always defined [0, 1] |
| 38 | `event_depth_scatter_mad` | `event_consistency` | Events | MAD scatter of individual transit depths / median depth | np.nan if adequate events < 3 |
| 39 | `event_single_event_dominance` | `event_consistency` | Events | Max event depth / sum of positive event depths | 1.0 if 1 event; np.nan if 0 events |
| 40 | `odd_even_depth_difference` | `odd_even` | Alternation | Absolute difference between odd and even transit depths | np.nan if odd or even missing |
| 41 | `odd_even_depth_ratio_v2` | `odd_even` | Alternation | Min(odd, even) / Max(odd, even) depth ratio | np.nan if odd or even missing |
| 42 | `odd_even_significance` | `odd_even` | Alternation | Depth difference normalized by combined standard error | np.nan if odd < 2 or even < 2 |
| 43 | `secondary_eclipse_max_depth_ratio` | `odd_even` | Alternation | Secondary eclipse depth at phase 0.5 / primary depth | np.nan if duty cycle >= 0.35 |
| 44 | `var_global_to_local_std` | `variability` | Activity | Total light curve std / local moving scatter | Always defined >= 1.0 |
| 45 | `var_autocorr_peak` | `variability` | Activity | Peak prominence of autocorrelation function at non-zero lag | np.nan if baseline < 5 days |
| 46 | `var_has_autocorr_modulation` | `variability` | Activity | Binary flag indicating autocorrelation peak >= 0.20 | np.nan if ACF undefined |
| 47 | `var_flare_cadence_rate` | `variability` | Activity | Fraction of cadences exceeding median + 4 sigma | Always defined [0, 1] |
| 48 | `var_out_of_transit_smoothness` | `variability` | Activity | Von Neumann ratio on out-of-transit cadences | 2.0 if out < 10 |
| 49 | `local_variance_contrast` | `localization` | Concentration | Fraction of variance in transit / duty cycle | np.nan if in < 5 or var <= 0 |
| 50 | `local_flux_deficit_concentration` | `localization` | Concentration | Flux deficit inside transit / total flux deficit | Always defined [0, 1] |
| 51 | `local_dip_isolation` | `localization` | Concentration | Transit depth / deepest out-of-transit dip depth | Always defined >= 0.0 |
| 52 | `local_baseline_flatness` | `localization` | Concentration | Standard deviation of binned out-of-transit profile / noise | np.nan if out < 5 |

## 3. Schema Invariants

- Total feature count: `52`
- Unique feature count: `52`
- Deterministic ordering: Fixed and preserved across all pipelines.
- Missingness: Explicit `np.nan` values handled via median imputation with missing indicator for RF/LR, and natively in HistGradientBoosting.
