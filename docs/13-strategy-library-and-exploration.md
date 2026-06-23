# 13 — Strategy Library, Exploration & Manual Backtest

Closes three gaps: (1) the seed knowledge that tells the app what to look for, (2) a UI to browse the
universe of strategy archetypes/themes, (3) a hands-on way to backtest a strategy on a ticker + date range.

## Design principle (read first)
We seed a WIDE catalog of archetypes and let the agent explore aggressively from day one — but aggression
is in *hypothesis generation only*. Every trial (archetype × ticker × param set) is logged to the
search-budget ledger (doc 08 §6); effective-N rises with exploration; DSR/PBO thresholds deflate harder
automatically. Nothing reaches paper or live without the full gauntlet (doc 08) AND human approval. A wider
catalog therefore *raises* the bar, never lowers it. The per-period search budget caps how aggressive a
cycle is — set it high, but the ledger keeps deflation honest. Archetypes never auto-deploy.

## 1. Strategy Library (the seed knowledge)
A curated, versioned catalog of strategy archetypes, each a DSL template (doc 07) plus a scan playbook.
Seeds live as YAML in `config/library/*.yaml`, loaded into a `library_archetypes` table on init; editable;
the evolution loop appends *proven, human-approved* discoveries (Tier-3) back into the library.

### Library entry schema
```yaml
id: range_fade
name: Range mean-reversion
family: mean_reversion          # see catalog families below
horizon: both                   # intraday | swing | both
thesis: "Oversold extensions to a range edge fade; liquidity provision vs transient noise."
watches: [close, range_detect, atr, rsi, avg_volume, realized_vol]   # DSL features it uses
regime: { all_of: [ {range_detect(20).in_range: true},
                    {between: ["realized_vol(20)", 0.12, 0.45]} ] }   # when the archetype is valid
entry:  { when: {lt: ["close", {expr: "rolling_low(20) + 0.4*atr(14)"}]},
          action: enter_long, sizing: {vol_scaled: {target_vol: 0.10}} }
exits:  [ {stop_loss: {atr_mult: 0.9, ref: "rolling_low(20)"}},
          {take_profit: {ref: "range_detect(20).mid"}},
          {time_stop: {sessions: 7}}, {regime_break_exit: true} ]
param_grid:                     # the search space exploration sweeps within
  rolling_n: {min: 10, max: 40, step: 5}
  entry_atr: {min: 0.2, max: 0.8, step: 0.1}
  stop_atr:  {min: 0.6, max: 1.4, step: 0.2}
scan:                           # the screen that surfaces candidate tickers at a point in time
  all_of: [ {gt: ["avg_volume(20)", 1000000]},
            {range_detect(20).in_range: true},
            {lt: ["zscore(20)", -1.0]} ]
peers_hint: sector_or_corr      # how to build the peer set for peer-testing
default_universe: {min_price: 5, min_dollar_volume: 5000000}
```

### Seed catalog (wide — build all on day one)
Each is a DSL template + scan + param grid following the schema above. Families and members:

| Family | Archetypes (id) | Horizon |
|--------|-----------------|---------|
| mean_reversion | `range_fade`, `rsi_reversion`, `bollinger_reversion`, `zscore_reversion`, `gap_fade`, `vwap_reversion` | swing / both / intraday |
| momentum_trend | `donchian_breakout`, `ma_crossover_trend`, `adx_trend_follow`, `pullback_continuation`, `relative_strength_momentum`, `opening_range_breakout` | swing / intraday |
| volatility | `squeeze_breakout`, `atr_channel_breakout`, `keltner_reversion`, `vol_scaled_exposure` | both |
| time_microstructure | `time_of_day_bias`, `end_of_day_drift`, `intraday_momentum_continuation` | intraday |
| cross_sectional | `pairs_statistical`, `sector_relative_strength` | swing |
| structural_filter | `earnings_proximity_filter`, `liquidity_regime_filter` | modifier (composes with any) |

Notes: `structural_filter` archetypes are regime modifiers (e.g. `days_to_event` avoidance), not standalone
trades. Each archetype's full entry/exit/regime/param_grid/scan ships as its YAML file. Intraday archetypes
require a consolidated intraday feed (see doc 12 data sourcing); they degrade to swing if only EOD is wired.

### The scan playbook = what it surfaces
This is the answer to "what does it scan for." The `universe_scan` tool runs an archetype's `scan` block
across the universe at `as_of` and returns ranked candidate tickers (rank = fit score: how strongly the
scan conditions hold + liquidity). Candidates feed the agent (author thesis + concrete spec) → backtest →
gauntlet → ledger. No scan = no idea what to look for; the playbook IS the day-one knowledge.

### Aggressive exploration workflow (seeded T2; deterministic pipeline, ledger-governed)
```
for archetype in library (budget-ordered):
    candidates = universe_scan(archetype.scan, as_of=now)        # surfaces what to look at
    for ticker in candidates[:k]:
        for params in grid(archetype.param_grid):                # the aggressive sweep
            spec = instantiate(archetype, ticker, params)
            bt   = backtest(spec); ledger.log(spec, family=archetype.family)   # every trial counted
            if bt.passes_cheap_screen: report = validate(spec)   # full gauntlet (doc 08)
    surface survivors where survivor_count > expected_false_discoveries(α, n_eff(family))
```
- N_eff per family rises with the sweep → DSR `expected_max_sharpe` bar rises → harder to pass. By design.
- Survivors go to the Review Queue with their deflated confidence; you approve; paper precedes live.
- Budget cap (config) bounds aggression per cycle; the agent may also *compose across* archetypes (T2) and
  *propose new* archetypes (T3, human-gated) — both ledger-tracked, never relaxing thresholds.

## 2. Library / Explore UI (extends the Registry screen)
Registry gains two tabs: **Instantiated** (today's registry: all strategies across the lifecycle) and
**Library** (the archetype catalog).
- **Library view:** archetype cards grouped by family/theme; filter by family + horizon. Each card shows
  name, thesis (one line), watched features, horizon, and status: `unexplored` / `explored` /
  `has-survivors (n)` / `has-live`. Surfaces the universe of themes at a glance.
- **Archetype detail:** full thesis, watched features, the scan logic (human-readable), the param grid, and
  the exploration funnel for it (trials → backtested → validated → survivors, pulled from the ledger).
  Actions: **Run scan** (surface candidate tickers now), **Explore** (queue the aggressive sweep for this
  archetype, budget-aware), **Author from this** (seed the research agent), **Open in Sandbox** (#3).
- Read/scan/backtest are agent-free reads; nothing here deploys.

## 3. Backtest Sandbox (new screen) + ad-hoc backtest endpoint
A hands-on screen to test without going through the agent flow.
- **Source:** a registry strategy version, OR a library archetype + chosen params, OR a pasted/edited DSL spec.
- **Inputs:** ticker(s), date range, bar timeframe, mode = `backtest_only` | `full_gauntlet`.
- **Run → results:** equity curve, trade list, core metrics; in `full_gauntlet` mode also DSR, PBO, robustness,
  and the deflated confidence (doc 08). Deterministic; runs on whichever `Backtester` impl is active behind
  the interface (custom Python today; nautilus_trader when wired in M9) + the real harness, so sandbox
  results are trustworthy, not a toy.
- **Guardrail:** the sandbox can promote a result into Research/Registry, but NEVER to live — live still
  requires the full validation + human Approval gates. Every run logs to the ledger (it's still search).

## API additions (doc 09 surface)
```
GET    /library                      # archetypes + status
GET    /library/{id}                 # detail + exploration funnel
POST   /library/{id}/scan            # body {universe?, as_of?} -> ranked candidates
POST   /library/{id}/explore         # body {budget, param_grid?} -> job_id (ledger-tracked sweep)
POST   /backtest                     # body {source: spec|{archetype_id,params}|strategy_version_id,
                                      #       tickers[], start, end, timeframe, mode} -> job_id -> results
```

## Data model additions (doc 09)
```
library_archetypes(id pk, name, family, horizon, thesis, template jsonb, scan jsonb,
                   param_grid jsonb, source enum(seed,evolved), status, created_at)
exploration_runs(id pk, archetype_id fk, budget_spent, trials int, survivors int, ts)
```
(Trials themselves live in the existing `search_ledger`; archetype family = `hypothesis_family`.)

## Build sequence placement (doc 06)
- After **M4 (DSL)**: load the seed library (archetypes are DSL templates) + `universe_scan` over scans.
- After **M3 + M4**: Backtest Sandbox endpoint + the manual run path (engine + harness already exist).
- In **M7 (UI)**: Library/Explore tabs on Registry + the Backtest Sandbox screen.
- In **M8 (Evolution)**: the aggressive exploration workflow (seeded wide), governed by the ledger + budget;
  Tier-3 promotes proven discoveries into the library.

## Safety invariants (unchanged)
Archetypes are DSL templates (type-checked, no executable code) and scans are DSL conditions (deterministic).
Exploration is a deterministic pipeline; the LLM authors theses/specs but never sizes/places orders. Every
trial counts toward N_eff; thresholds never relax. Nothing auto-deploys; live needs the gauntlet + Approval.
