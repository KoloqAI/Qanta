# 03 — Engine & Validation

## Strategy DSL
Strategies are declarative specs composed from typed, pre-tested primitives. The LLM composes
references only — it never writes executable logic. A spec is type-checked against the vocabulary
before backtest; malformed specs are rejected at parse time.

Vocabulary (representative):
- Features: `close vwap volume dollar_volume sma(n) ema(n) adx(n) atr(n) realized_vol(n) bollinger(n,k) rsi(n) macd(f,s,sig) stochastic(n) rolling_high(n) rolling_low(n) range_detect(n) zscore(n) avg_volume(n) time_of_day session_phase days_to_event`
- Conditions: `gt lt between crosses_above crosses_below within_band outside_band held_for(cond,n)` + `AND/OR/NOT`
- Actions: entry `enter_long|enter_short`; sizing `fixed_pct|vol_scaled|kelly_capped`; exits `take_profit stop_loss[required] trailing_stop time_stop(n) regime_break_exit`. `scale_in` gated/off (martingale risk).
- Risk envelope: `max_position_pct per_trade_stop_pct max_gross_exposure` (must be ⊆ global guardrails).

Spec schema (yaml/json): `{ id, version, tickers, author(model+run), thesis(required), regime{all_of:[cond]}, entry{when,action,sizing}, exits[], risk{}, universe{primary, peers[]}, validation{targets:[{R,H}], thresholds} }`.

## Backtest
Point-in-time, survivorship-free (include delisted/range-broken names). Cost model: commission + full
spread crossing + slippage; default fill = next-bar open. Report frictionless vs net edge.

## Validation harness (the gauntlet — build & verify first)
1. Leakage & cost screen — point-in-time, no survivorship, no lookahead; Sharpe > ~3 flagged as suspected leak.
2. Purged walk-forward — train → next unseen window → roll; purge overlapping-label samples + embargo; optional combinatorial purged CV. A lockbox holdout the agent never sees, touched once.
3. Deflated Sharpe (DSR) + PBO:
```
DSR = Φ( (SR̂ − SR*)·√(n−1) / √(1 − γ3·SR̂ + ((γ4−1)/4)·SR̂²) )
SR* = σ_SR · [ (1−γ)·Z(1−1/N) + γ·Z(1−1/(N·e)) ]      # γ = Euler–Mascheroni ≈ 0.5772
PBO  = fraction of CSCV splits where the in-sample-best config lands below the OOS median
```
   Negative skew / fat tails lower DSR (intended). N is effective trials (cluster correlated specs).
4. Robustness — parameter sensitivity (plateau not knife-edge), regime tests (incl. 2018Q4/2020/2022), Monte Carlo on the trade sequence (judge the 95th-pct path), min trade count.

Pre-registered pass/fail thresholds (config/validation.yaml, versioned): DSR > 0.95 · PBO < 0.20 ·
slope >= 0 · min trades >= 100 · cost-adjusted edge > 50% of frictionless · peer-hit-rate >= threshold.
**All** must pass.

### Verification suite (ships with the harness — required tests)
- PBO on pure-noise strategies → ≈ 0.5; on seeded-edge strategies → → 0.
- DSR strictly decreasing as N rises (fixed Sharpe); DSR lower for negatively-skewed returns at equal Sharpe.
- Cross-implementation triangulation against an independent impl (PyBroker's walk-forward/bootstrap, or `mlfinpy`) within tolerance.

## Confidence metric (locked definition)
Headline: *Conditional on {regime}, a deflated {C}% OOS probability (90% interval {C_lo}–{C_hi}) of
returning ≥{R} over {H}, against max loss {L} if stopped. Regime held {G}% of {window}; edge generalized
to {f}/{n} peers. (DSR {d}, PBO {p}.)* If gates fail → no number, just "Not validated: {gate}".

- Outcome = strategy net return over H, stop baked into every path (first-passage aware).
- {C} from OOS H-window outcomes (effective-independent), shrunk Bayesian toward a skeptical base rate;
  prior strength grows with effective trials. Report posterior mean + 10th-pct lower bound (act on the lower bound).
- Emission gates: DSR ≥ 0.95, PBO ≤ 0.20, peer-hit ≥ threshold, C_lo ≥ floor.
- Never authored by the LLM. Optionally present a confidence-vs-target curve (modest targets dominate).
- Calibration: log every {C} vs realized outcome (doc 04 / Performance screen); recalibrate OOS only.

## Evolution loop
Tiers with escalating gates:
- T1 Promote/retire (auto): abstract validated + paper-proven winners into templates; retire decayed.
- T2 Discover (budgeted): compose new specs from the vocabulary → full gauntlet; every candidate logged to the search-budget ledger; N_eff feeds deflation; surface survivors that beat the false-discovery expectation (~α·N_eff).
- T3 Expand capability (human-gated + meta-validated): propose a new primitive/tool; code-reviewed + unit-tested + must improve OOS on the meta-lockbox + your approval.

Mechanics: per-tier cadence (T1 nightly/weekly · T2 weekly batch · T3 reviewed monthly · event-driven runs on the calendar). Search-budget ledger (append-only, lifetime, spans model-swaps) computes N_eff and enforces a per-period budget. Meta-lockbox: a held-out recent slice the loop never trains on, evaluated on a slow cadence; a T3 change must not degrade it; erosion across cycles → roll back. Evolution can expand capability but never relax a guardrail, skip the human gate, or self-deploy. Everything versioned + reversible.
