# Changelog

## v2.0.0 — the broadcast redesign, the neutralisation model, and a chatbot (2026-07-31)

71 commits. Synced through the 2026 Hungarian GP (round 11). Major, not minor:
the interface was rebuilt, the simulator learned three race states it had been
ignoring, and the app grew a natural-language front door.

### Ask — plain English, against the same engine
- New **Ask** view: *"fastest strategy for Monza"*, *"lap 30, I'm on hards 20
  laps old, Norris on mediums 6 — do I box?"*. Six intents, routed to the
  existing engine; `api.py` and the view stay thin.
- Every answer shows **what was understood** — intent, slots, which parser
  answered. A fuzzy parse that mishears a circuit is visible, not silent.
- Missing details are **asked for, not guessed**, and follow-ups accumulate
  client-side so a stateless API can still hold a thread.
- Two parsers built and benchmarked against phrasings written before either was
  scored: a hand-written rule/slot-filler, and a **450k-parameter transformer
  written from scratch** — own tokeniser, attention, training loop, served by a
  numpy forward pass so deployment needs no torch. Both reachable at runtime.

### The simulator learned three states it had been ignoring
- **Virtual safety car** modelled as its own track state. The safety-car hazard
  had never counted VSC periods at all, understating the chance of a cheap-stop
  window by roughly half.
- **Red flags** priced: the free tyre change the engine had never modelled.
- VSC pit loss was a **fixed 16.0 s while full-SC loss scaled per circuit** — an
  18% discount at Spa and 44% at Imola, and it would have inverted anywhere the
  green-flag loss fell below 16 s. Now a fraction of the measured loss.
- Neutralisations priced **inside the undercut duel**; tyre-set limits enforced
  so the optimiser can't propose a plan no team could actually field.
- The duel now **says when it is extrapolating** past any stint the field has run.

### Corrections to published numbers
- **A leaked shrinkage benchmark.** The headline +16% was in-sample: the shrunk
  model had been fitted on the 2026 laps it was scored on while the baseline was
  out-of-sample. Leave-one-race-out truth is **+14.4%** over no-degradation and
  **+1.0%** over the prior (winning 8/11 races). The in-sample figure was 13.5%
  optimistic.
- **The LSTM re-measured** across all 11 unseen 2026 races: mean **+13.4%** vs
  persistence, 11/11 wins — the previously quoted +18% was the best single race.
- **Ingest was silently dropping seasons** it wasn't asked about, rebuilding the
  combined dataset from only the years passed. Now merges, with a shrink guard.

### Rejected, with evidence
- Training the deployed model on the season it predicts (better in **0 of 11**).
- Per-compound shrinkage *k* (gain 0.48% < the 0.78% spread across the grid).
- Retraining the LSTM on 2025 — **+51% data, +0.00%**.
- A pre-registered Hungarian GP call scored **1/3**, no better than the grid
  baseline, and is published as such.

### The interface
- **V2 broadcast redesign**: black surfaces, runtime-swappable gold accent,
  driver cutouts, circuit outlines drawn from FastF1 telemetry, F1 start-lights
  loader, collapsible rail, command palette (Ctrl+K), Settings.
- **Emoji removed** throughout, replaced with real line icons.
- **Design system**: a `Button` primitive (25 raw buttons had already drifted
  into three different paddings), chart tokens, a real type scale that removed
  124 arbitrary pixel sizes, and `docs/DESIGN_SYSTEM.md`.
- **Accessibility**: four WCAG 2.1 AA failures fixed, a skip link, accessible
  names on tables and controls, and the app's first `aria-live` region — an
  audit found **zero** across all twelve views.
- Race-day mode on Home; upcoming-race predictions now auto-feed the **real
  qualifying grid** when it exists.

### Numbers
- **224 no-network tests** (was 146). CI runs the Python suite and the frontend
  build.

Full receipts, including every rejection: `docs/METHODOLOGY.md`.

## v1.0.0 — the F1 OS (2026-07-10)

The project's first tagged release: the pit-strategy engine, grown into a full
F1 OS, deployed and synced through the 2026 British GP (round 9).

### The engine (the moat)
- Tyre-degradation model — per-circuit/compound, era-shrunk across the 2026
  regulation reset, recency-weighted for mid-season upgrades.
- Monte-Carlo race simulator + strategy optimiser (coarse-to-fine search),
  per-circuit safety-car hazard and pit loss **measured** from 78+ races.
- Labelled priors for what data can't show: tyre cliff, thermal (track-temp)
  degradation, track-position cost per stop, and **compound censoring**
  (avoidance-aware stint caps + slope/base repair).
- LSTM next-lap forecaster (+8.5% vs persistence), exported torch-free.
- Podium + championship models, always validated forward-in-time; title odds
  bootstrap driver-strength uncertainty.

### The OS
Home (next race + countdown + the model's podium call) · Strategy · Undercut ·
Calendar · Race Hub (pre-race prediction vs actual result, scored hit@3) ·
Live Race replay with LSTM nowcast · Standings (sprint-inclusive, live
title odds, one-click refresh from FastF1) · Drivers & Teams · News · About.

### Numbers (leakage-safe, forward-tested)
- Strategy stop-count: 8/9 vs the field's dominant choice, 7/9 vs the winner
  (leave-one-race-out over 2026).
- Podium model ROC-AUC 0.93 (forward split); degradation MAE 0.069 s/lap on
  unseen races.
- 146 no-network tests; CI runs the Python suite and the frontend build.

Full receipts and the accepted/rejected-model history: `docs/METHODOLOGY.md`.
