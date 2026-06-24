# 07 — Strategy DSL Reference (implementation depth)

The DSL is the language strategies are written in. The LLM composes references to registered, pre-tested
primitives; it never emits executable code. A spec is parsed → type-checked against this catalog →
interpreted deterministically by the backtest and execution engines. Same spec, both engines.

## Type system
- `Series` — a time-indexed float series (e.g., a price or indicator stream).
- `Scalar` — a single float (a threshold, a multiple).
- `Bool` — a time-indexed boolean (a condition stream).
- `Param` — a tunable input with `{type, min, max, step, default}`; the optimizer/agent may vary it only within range.
- Every primitive declares input types and an output type. Type-checking fails the spec if a `Series`
  is used where a `Scalar` is required, an out-of-range `Param`, an unknown name, or a missing required arg.

## Feature primitives  (output `Series` unless noted)
| Name | Args | Notes |
|------|------|-------|
| `close` `open` `high` `low` `volume` | — | raw OHLCV |
| `vwap` | `(window=session)` | volume-weighted avg price |
| `dollar_volume` | `()` | close·volume |
| `sma(n)` `ema(n)` | `n:int 2..400` | moving averages |
| `atr(n)` | `n:int 2..100` | average true range |
| `realized_vol(n)` | `n:int 5..252` | annualized stდ of returns |
| `bollinger(n,k)` | `n:int, k:float 1..3` | returns `{mid, upper, lower}` (a record of Series) |
| `rsi(n)` | `n:int 2..50` | 0..100 |
| `macd(f,s,sig)` | ints | returns `{macd, signal, hist}` |
| `adx(n)` | `n:int 5..50` | trend strength 0..100 |
| `stochastic(n)` | `n:int` | returns `{k, d}` |
| `rolling_high(n)` `rolling_low(n)` | `n:int` | range extremes |
| `range_detect(n)` | `n:int` | returns `{low, high, in_range:Bool}` |
| `zscore(n)` | `n:int` | (close − mean)/std over n |
| `avg_volume(n)` | `n:int` | liquidity |
| `time_of_day` | — | minutes since open (`Series`) |
| `session_phase` | — | `open|mid|close` enum series |
| `days_to_event(kind)` | `kind:str` | sessions to next scheduled event (requires event-enriched bars) |
| `is_index_add` | — | 1.0 on dates where the symbol is a confirmed index addition, 0.0 otherwise |
| `is_index_delete` | — | 1.0 on dates where the symbol is a confirmed index deletion, 0.0 otherwise |

**Event features** (`days_to_event`, `is_index_add`, `is_index_delete`) read from event-calendar columns
injected into bars by `enrich_bars_with_events()` before interpretation.  Without enrichment they
gracefully fall back to NaN / 0.0.  The reconstitution calendar is point-in-time: events are only
revealed once `as_of >= final_list_date` (see doc 12 §6).  Added in DSL vocabulary version 2.

## Condition primitives  (output `Bool`)
`eq(a,b)` · `gt(a,b)` `lt(a,b)` `between(a,lo,hi)` · `crosses_above(a,b)` `crosses_below(a,b)` ·
`within_band(a,lo,hi)` `outside_band(a,lo,hi)` · `held_for(cond,n)` (cond true for n consecutive bars) ·
combinators `all_of([...])` `any_of([...])` `not(cond)`. Args accept `Series` or `Scalar`.

`eq` compares for equality — use with boolean features: `{eq: ["is_index_add", 1]}`.

## Action primitives
- Entry: `enter_long(when:Bool, sizing)` · `enter_short(when:Bool, sizing)`.
- Sizing: `fixed_pct(p)` · `vol_scaled(target_vol)` (size ∝ 1/atr) · `kelly_capped(frac, cap)`.
- Exits (ordered; `stop_loss` is REQUIRED): `take_profit(level|atr_mult)` · `stop_loss(level|atr_mult)` ·
  `trailing_stop(atr_mult)` · `time_stop(n_sessions)` · `regime_break_exit()` (auto-derived from `regime`).
- `scale_in(...)` exists but is **disabled by default** (martingale/averaging-down risk); enabling it is a
  Tier-3 capability change requiring approval.

## Regime gate
`regime: { all_of: [<Bool conditions>] }`. The strategy is active only while all hold. The same
conditions drive `regime_break_exit` and are monitored live; a break triggers a flatten of that strategy.

## Persistence thesis (required on archetypes, gates_version 4+)
Archetype YAML files must include a `persistence_thesis` block declaring *why the edge survives an
efficient market* and *what kills it*. This is validated at load time — archetypes missing a well-formed
thesis are excluded from exploration. See doc 13 §1 for the full sub-field schema (`edge_type`,
`structural_reason`, `forced_counterparty`, `death_condition`, `capacity_ceiling_usd`,
`monitorable_as_regime`). Instantiated strategy specs do not carry the thesis (it lives on the
archetype); the spec's `thesis` field remains the one-line trading idea.

## Risk envelope (must be ⊆ global guardrails — may be tighter, never looser)
`risk: { max_position_pct, per_trade_stop_pct, max_gross_exposure }`. Validated at parse time against the
global limits in `config/guardrails.yaml`; a looser value is rejected.

## Spec schema (canonical JSON)
```json
{
  "id": "uuid", "version": 3, "tickers": ["XYZ"],
  "author": {"model": "claude-...", "research_run": "uuid"},
  "thesis": "string (required, non-empty)",
  "regime": {"all_of": [
    {"within_band": ["close", 47.0, 55.0]},
    {"between": ["realized_vol(20)", 0.18, 0.32]},
    {"gt": ["avg_volume(20)", 2000000]}
  ]},
  "entry": {"when": {"lt": ["close", {"expr": "rolling_low(20) + 0.4*atr(14)"}]},
            "action": "enter_long", "sizing": {"fixed_pct": {"pct": 5.0}}},
  "exits": [
    {"stop_loss": {"atr_mult": 0.8, "ref": "rolling_low(20)"}},
    {"take_profit": {"ref": "range_detect(20).mid"}},
    {"time_stop": {"sessions": 7}},
    {"regime_break_exit": true}
  ],
  "risk": {"max_position_pct": 5.0, "per_trade_stop_pct": 3.1, "max_gross_exposure": 40.0},
  "universe": {"primary": "XYZ", "peers": ["KO","PEP","MDLZ","GIS"]},
  "validation": {"targets": [{"R": 0.02, "H": 7}, {"R": 0.05, "H": 7}], "thresholds": "inherit"}
}
```

## Parse / type-check rules (the validator must enforce)
1. `thesis` present and non-empty, else reject.
2. Every primitive name exists in the registered catalog at the spec's DSL version.
3. Arg arity + types match the primitive signature; `Param` values within declared ranges.
4. Exactly one entry; at least one `stop_loss` exit present.
5. `risk` ⊆ global guardrails.
6. `regime.all_of` non-empty (a strategy must declare when it is valid).
7. Unknown fields rejected (strict schema). Output a structured error listing each failure.

## Interpreter contract
`interpret(spec, bars) -> signals` is pure and deterministic: given identical bars it yields identical
entry/exit signals. No I/O, no randomness, no LLM. The same function feeds the backtester (historical
bars) and the execution runtime (live bars). Stops are evaluated bar-by-bar (first-passage correct).

## Extending the vocabulary (Tier-3, gated)
A new primitive is: (1) deterministic, unit-tested code implementing the primitive interface;
(2) registered with a typed signature and param ranges; (3) version-bumps the DSL vocabulary;
(4) approved by a human and meta-validated (improves OOS on the meta-lockbox). Existing validated specs
pin their DSL version and are unaffected.

Current `DSL_VOCABULARY_VERSION = 2` (`app/core/dsl/primitives.py`).  Version history:
v1 = initial 22 feature + 10 condition primitives; v2 = `eq` condition, `is_index_add`,
`is_index_delete` features, `days_to_event` unstubbed (event-calendar integration).
