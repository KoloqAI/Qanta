# 08 — Validation Internals (implementation depth)

Build and verify this module before the agent or execution. Pseudocode is illustrative; implement
dependency-light and cover with the verification suite (§7). The module's job: an honest out-of-sample
estimate plus refusal to be fooled by the search that produced a candidate.

## 1. Purged walk-forward (+ embargo)
```
def walk_forward(returns_or_signals, n_splits, embargo_frac, label_horizon):
    folds = contiguous_time_folds(data, n_splits)        # NEVER shuffle; preserve order
    oos_results = []
    for i in range(1, n_splits):
        train = concat(folds[:i])
        test  = folds[i]
        train = purge(train, test, label_horizon)        # drop train samples whose label window
                                                          #   overlaps the test window
        train = embargo(train, test, embargo_frac)        # drop a gap after each test fold
        model = fit_on(train)                             # for rule strategies: no fit; just evaluate OOS
        oos_results.append(evaluate(model, test))
    return concat(oos_results)                            # the OOS performance series
```
- For rule-based DSL strategies there is no model "fit"; walk-forward still matters because parameter
  selection and the agent's search are the thing being validated out-of-sample.
- `purge`/`embargo` exist to kill leakage from overlapping labels and serial correlation.
- Combinatorial purged CV (CPCV): generate many train/test combinations of the folds to produce a
  *distribution* of OOS estimates rather than one path. Use it to feed PBO (below).
- **Lockbox:** reserve a final contiguous slice never used in any walk-forward/CPCV split during research.
  Touch it once, at the end. The research agent must have no read path to it.

## 2. Deflated Sharpe Ratio (DSR)
Built on the Probabilistic Sharpe Ratio. `Φ` = normal CDF, `Z` = inverse normal CDF.
```
def psr(sr_hat, sr_benchmark, n, skew, kurt):
    denom = sqrt(1 - skew*sr_hat + ((kurt-1)/4)*sr_hat**2)
    return Phi( (sr_hat - sr_benchmark) * sqrt(n - 1) / denom )

def expected_max_sharpe(n_eff, sigma_sr):       # deflation benchmark under the null of zero edge
    gamma = 0.5772156649                          # Euler–Mascheroni
    return sigma_sr * ((1-gamma)*Zinv(1 - 1/n_eff) + gamma*Zinv(1 - 1/(n_eff*e)))

def deflated_sharpe(sr_hat, n, skew, kurt, n_eff, sigma_sr):
    sr_star = expected_max_sharpe(n_eff, sigma_sr)
    return psr(sr_hat, sr_star, n, skew, kurt)    # prob the true Sharpe beats the multiple-testing luck bar
```
- `sr_hat` non-annualized per-observation Sharpe; `n` observations; `skew`,`kurt` of the strategy returns
  (kurt is raw, =3 for normal). Negative skew and fat tails lower DSR — intended.
- `sigma_sr` = cross-sectional std of trial Sharpes; `n_eff` = effective independent trials (see §6).
- Accept bar: DSR > 0.95.

## 3. Probability of Backtest Overfitting (PBO via CSCV)
```
def pbo_cscv(M, S):                     # M: T x N matrix of per-period returns for N configs; S even
    if N < 2: return {pbo: None, ...}    # single-config: PBO undefined (see below)
    assert S % 2 == 0
    blocks = split_rows_contiguous(M, S)
    lam = []
    for IS_idx in combinations(range(S), S//2):       # symmetric: choose half as in-sample
        OOS_idx = [b for b in range(S) if b not in IS_idx]
        IS, OOS = stack(blocks, IS_idx), stack(blocks, OOS_idx)
        n_star = argmax_config(sharpe(IS))            # best config in-sample
        r = rank_of(sharpe(OOS), n_star) / N          # its relative rank out-of-sample (via rankdata)
        lam.append(log(r / (1 - r)))                  # logit; <=0 means below OOS median
    pbo = sum(1 for x in lam if x <= 0) / len(lam)   # fraction of splits where IS-best is below OOS median
    deg_slope = ols_slope(perf_IS_best, perf_OOS_same)   # negative = alarm (better IS -> worse OOS)
    prob_loss = mean([oos_sharpe(n_star) < 0 ...])
    return {pbo, deg_slope, prob_loss}
```
- PBO ≈ 0 generalizes; ≈ 0.5 is a coin flip; > 0.5 actively overfit. Accept bar: PBO < 0.20; deg_slope ≥ 0.
- **Multi-config (N ≥ 2):** The T×N matrix comes from the param-grid sweep — each column is one config's
  return series from the same backtest window. Evolution T2 sweeps the **archetype's declared `param_grid`**
  (entry lookbacks, thresholds, stop multipliers — the dimensions the strategy is actually selected on)
  and backtests all variants, then passes the full matrix as `competing_returns` to `validate()`.
  Combinatorial blow-up is bounded by `pbo.max_configs` (config/validation.yaml, default 20): the full
  cartesian product is computed but down-sampled via strided selection (deterministic, seed=42) when it
  exceeds the cap. The base spec is always included as variant 0.
- **Load-time no-op guard:** Archetype templates use explicit `{param_name}` placeholders that the param_grid
  fills via exact string substitution. At load time, `library_loader` validates bidirectional binding: every
  param_grid key must have a `{key}` placeholder in the template, every placeholder must have a param_grid
  entry with a `default:` value, and sampled variants must be distinct. Any archetype failing these checks is
  **excluded from exploration** with a logged error — a declared-but-dead param can never silently feed PBO.
  Competing-returns columns are also deduped at sweep time (identical return vectors are collapsed) so the
  PBO matrix only contains genuinely distinct configs.
- **Single-config (N < 2):** PBO is mathematically undefined (no selection to overfit). Returns `None`;
  PBO gate is skipped. DSR (with `n_eff` counting hypothesis families, not param variants) carries the
  deflation load. The `detail.pbo_note` field documents this.
- **Ledger consistency:** `n_eff` counts independent hypothesis families (one per ticker/archetype in T2),
  NOT individual param configs within a sweep. PBO measures within-family selection-overfitting from the
  param grid. These are orthogonal — no double-counting that would distort either metric.

## 4. Confidence metric (Beta-Binomial, deflated)
```
def confidence(spec, target_R, horizon_H, oos_windows, n_eff, base_rate_p0):
    w = effective_independent_windows(oos_windows, H)     # non-overlapping or autocorr-adjusted
    k = count(window.net_return >= R for window in w)     # successes (stop already baked into return)
    m = len(w)
    s = prior_strength(n_eff)                             # grows with effective trials searched
    a0, b0 = s*base_rate_p0, s*(1-base_rate_p0)            # skeptical Beta prior centered on base rate
    post = Beta(a0 + k, b0 + m - k)
    return {C: post.mean(), C_lo: post.ppf(0.10), C_hi: post.ppf(0.90)}   # act on C_lo
```
- Outcome = strategy net return over H with the stop active (first-passage aware).
- Emission gates: only return a number if DSR ≥ 0.95, PBO ≤ 0.20, peer-hit ≥ 0.60 (config: `peer_hit_rate_min`),
  and C_lo ≥ floor. Otherwise emit "Not validated: {gate}".
- Peer-hit gate: spec is backtested on the N most return-correlated tickers (point-in-time, `as_of` clamped).
  peer_hit = fraction of peers with net_edge > 0. Peers auto-selected via correlation (per archetype `peers_hint`);
  if insufficient peer data (< `min_peers`), gate fails closed. Peer backtests are part of the single validation
  (counted in the search-budget ledger, not a separate multiple-testing backdoor).
  `gates_version` (currently 3) tracks gate-set evolution; reports predating it are stale and blocked from
  approval/deployment until re-validated. Version history: v2 = peer-hit gate added; v3 = explicit `{param}`
  placeholder binding (old naming-convention regex could produce no-op params and duplicate PBO columns).
- Headline: *Conditional on {regime}, deflated {C}% (90% {C_lo}–{C_hi}) of ≥{R} over {H}, max loss {L};
  regime held {G}% of {window}; peers {f}/{n}. (DSR {d}, PBO {p}.)* Optionally a confidence-vs-target curve.
- Never authored by the LLM. Calibration logged vs realized; recalibrate OOS only.

## 5. Robustness battery
- Parameter sensitivity: sweep each Param ±10–20%; require a performance *plateau* (graceful degradation),
  reject knife-edges. Report a sensitivity heatmap.
- Regime tests: slice by vol regime; run explicit windows (2018-Q4, 2020 crash, 2022 drawdown).
- Monte Carlo: resample/reorder the OOS trade sequence ≥2000×; report the distribution of return and the
  95th-percentile max drawdown; size/judge against the bad path.
- Power: reject if effective trade count below the minimum.

## 6. Search-budget ledger & effective N
```
ledger row: {spec_hash, hypothesis_family, data_window, model_version, result_metrics, ts}
def n_eff(family):
    specs = ledger.where(family)
    clusters = cluster_by_return_correlation(specs, threshold=0.9)   # near-duplicate sweeps collapse
    return len(clusters)                                              # effective independent trials
```
- Append-only, lifetime, spans model swaps and re-runs (model-shopping counts).
- Per-period budget cap; exploration pauses when spent.
- False-discovery sanity: expect ≈ α·n_eff false survivors at threshold α; survivor count must exceed it.

## 7. Verification suite (REQUIRED — these are the acceptance-gate tests for M3)
| Test | Input | Expected |
|------|-------|----------|
| PBO on noise | T×N matrix of i.i.d. random returns (N=10) | PBO ≈ 0.5 (±0.2) |
| PBO on seeded edge | T×N matrix, one config with genuine drift | PBO → low (< 0.3) |
| PBO single-config | T×1 or 1-D returns | PBO = None (gate skipped) |
| PBO gate rejects overfit | T×N noise matrix passed as competing_returns | PBO > 0.20 → gate False |
| Entry-param overfit rejected | T×N matrix: one config IS-tuned, poor OOS neighbors | PBO > 0.20 → gate False |
| Robust entry param passes | T×N matrix: genuine edge, graceful degradation | PBO ≤ 0.20 → gate True |
| DSR monotonic in N | fixed sr_hat, increasing n_eff | DSR strictly decreasing |
| DSR skew penalty | equal sr_hat, skew −0.6 vs 0 | skewed scores lower |
| Walk-forward leakage | a strategy using a future value | caught/blocked or OOS collapses |
| Triangulation | same inputs to our impl and an independent one (PyBroker / `mlfinpy`) | agree within tolerance |
| End-to-end | seeded known-good vs known-overfit spec | good passes, overfit fails |

## 8. Meta-lockbox protocol
A held-out recent slice (temporal) the evolution loop never trains/searches on; plus live/paper as the
ultimate forward holdout. Evaluated on a slow cadence (≈quarterly); touching it spends it, so rotate/extend.
A Tier-3 capability change must not degrade meta-lockbox performance. Erosion across cycles → roll back.
