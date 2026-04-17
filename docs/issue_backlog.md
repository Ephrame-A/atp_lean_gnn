# Collaboration Backlog and Issue Map

## Purpose

This document translates the current project state into a GitHub-friendly backlog so contributors can work in parallel without losing the overall architecture.

The repository has already completed the first major phase:

- proof-state parsing
- shared DAG construction
- dataset preparation and caching
- baseline GNN training
- run evaluation and analysis

The remaining work is no longer "build the first thing." It is now:

- harden what exists
- understand the baseline scientifically
- connect the model to executable Lean interaction
- move toward actual proof search
- prepare the later neuro-symbolic bridge

## How To Use This Backlog

Each issue should have:

- a clear owner or volunteer
- a narrow deliverable
- an explicit dependency status
- acceptance criteria
- labels that make parallel work obvious

Recommended label scheme:

- `epic`
- `parallel`
- `research`
- `priority:p0`
- `priority:p1`
- `priority:p2`
- `area:representation`
- `area:dataset`
- `area:training`
- `area:execution`
- `area:search`
- `area:symbolic`

## Live GitHub Issue Set

The current GitHub issue hierarchy is:

- `#14` Epic: Representation and baseline-quality hardening
- `#15` Epic: LeanDojo execution and proof replay foundation
- `#16` Epic: Search and tactic-argument bridge
- `#17` Epic: Symbolic bridge and contributor readiness

The highest-value first parallel wave is:

- `#1` Run a parser coverage audit on real LeanDojo states
- `#4` Run the first ablation suite for edge direction, readout, and node-type usage
- `#5` Deepen run analysis with confusion reports and tactic-family failure summaries
- `#13` Add contributor guidance for picking up issues and running the stack

For the detailed source-of-truth issue bodies, including prerequisites, scope boundaries, examples, deliverables, and acceptance criteria, see:

- `docs/github_issue_specs.md`

## Dependency View

The intended dependency order is:

`Representation hardening -> Baseline ablations and analysis -> LeanDojo execution -> Search -> Premise selection and tactic arguments -> Symbolic bridge`

Some of this can happen in parallel:

- representation hardening can run in parallel with baseline analysis
- search logging design can begin while LeanDojo execution is being implemented
- symbolic interface design can be drafted before full search is ready

## Epic 1: Representation and Dataset Hardening

Goal:
Make sure the proof-state representation is reliable enough to support all later phases.

### Issue 1.1: Run a parser coverage audit on real LeanDojo states

Area:
`representation`, `dataset`

Priority:
`p0`

Can run now:
Yes

Why it matters:
The parser is the foundation of every downstream phase. If it silently mishandles real syntax, later model and search work will be harder to trust.

Acceptance criteria:

- sample and full-split parser success rates are recorded
- failure cases are categorized
- at least one report is added to `artifacts/` or `runs/`
- the top unsupported syntax families are identified explicitly

### Issue 1.2: Extend parser support for binder-heavy and currently failing constructs

Area:
`representation`

Priority:
`p0`

Blocked by:
Issue 1.1

Why it matters:
Binder-heavy Lean expressions, quantifiers, and implicit/typeclass-heavy states are likely to appear in realistic theorem-proving data.

Acceptance criteria:

- parser coverage improves on the failure classes found in Issue 1.1
- regression tests are added for each fixed syntax family
- the preprocessing pipeline succeeds on the previously failing sample cases

### Issue 1.3: Strengthen cache versioning and artifact schema metadata

Area:
`dataset`

Priority:
`p1`

Can run now:
Yes

Why it matters:
When parser logic or vocab logic changes, prepared caches need version visibility or collaborators will compare incompatible runs by accident.

Acceptance criteria:

- manifests include parser/cache/schema version fields
- prepared artifacts record enough metadata to trace how they were built
- training code fails clearly when schema versions are incompatible

## Epic 2: Baseline Science and Experiment Discipline

Goal:
Turn the current baseline into a trustworthy reference point rather than a one-off successful run.

### Issue 2.1: Run the first ablation suite for graph direction, readout, and node-type usage

Area:
`training`

Priority:
`p0`

Can run now:
Yes

Parallel-friendly:
Yes

Why it matters:
Right now the repo has one strong baseline configuration, but we do not yet know which design choices matter most.

Required comparisons:

- bidirectional vs forward edges
- `State` node readout vs mean pooling
- node-type embeddings on vs off

Acceptance criteria:

- each run is saved with config and summary artifacts
- a comparison report is written
- one configuration is named as the official next baseline

### Issue 2.2: Deepen run analysis with confusion reports and tactic-family failure summaries

Area:
`training`

Priority:
`p1`

Can run now:
Yes

Parallel-friendly:
Yes

Why it matters:
Top-1 and top-5 accuracy are useful, but collaborators also need to see what the model confuses and where it fails structurally.

Acceptance criteria:

- confusion-style summaries exist for the most common tactics
- hardest tactic classes are reported with support counts
- representative errors are saved in machine-readable and human-readable form

### Issue 2.3: Improve training throughput and runtime ergonomics

Area:
`training`

Priority:
`p1`

Can run now:
Yes

Parallel-friendly:
Yes

Why it matters:
Long-running experiments reduce iteration speed and collaboration throughput.

Acceptance criteria:

- baseline training throughput is measured before and after changes
- recommended configs for laptop GPU and CPU-only execution are documented
- checkpointing and resume paths are tested on interrupted runs

## Epic 3: LeanDojo Execution Layer

Goal:
Move from offline next-tactic prediction to live theorem-state interaction.

### Issue 3.1: Define and implement a minimal Lean environment wrapper

Area:
`execution`

Priority:
`p0`

Blocked by:
None

Why it matters:
Search and executable proving should be built on a stable interface, not ad hoc scripts.

Minimum interface:

- load theorem
- expose current proof state
- apply tactic
- return next state or failure
- detect proof completion

Acceptance criteria:

- an environment module exists with a documented API
- at least one theorem can be loaded and stepped programmatically
- failures and state transitions are logged cleanly

### Issue 3.2: Add gold-trace proof replay over selected examples

Area:
`execution`

Priority:
`p0`

Blocked by:
Issue 3.1

Why it matters:
Before search, the repo should be able to replay known proof traces reliably.

Acceptance criteria:

- a replay script runs gold tactic sequences on selected theorems
- replay success/failure rate is reported
- mismatches are logged with enough detail to debug

## Epic 4: Search Foundation

Goal:
Turn single-step predictions into multi-step proof attempts.

### Issue 4.1: Implement a beam-search baseline over tactic predictions

Area:
`search`

Priority:
`p1`

Blocked by:
Issue 3.2

Why it matters:
Beam search is the simplest serious test of whether the learned tactic model helps beyond one-step accuracy.

Acceptance criteria:

- beam search can consume model predictions and environment transitions
- configurable beam width and search depth are supported
- traces are saved for solved and failed attempts

### Issue 4.2: Add search metrics and trace logging

Area:
`search`

Priority:
`p1`

Blocked by:
Issue 4.1

Parallel-friendly:
Partly

Why it matters:
Search without observability becomes impossible to debug or compare.

Acceptance criteria:

- proof success rate is reported
- average search depth and timeout/failure counts are reported
- trace artifacts are easy to inspect after a run

## Epic 5: Premise Selection and Tactic Arguments

Goal:
Close the gap between tactic-family prediction and executable tactic generation.

### Issue 5.1: Define the premise-selection problem for this repo

Area:
`execution`, `training`

Priority:
`p1`

Can run partly in parallel:
Yes

Why it matters:
The project currently predicts tactic heads only. Real theorem proving usually needs facts, lemmas, or hypotheses to fill tactic arguments.

Acceptance criteria:

- local hypotheses vs library premises are scoped explicitly
- the first premise-selection task is chosen
- a dataset contract is written for future training

### Issue 5.2: Build a local-hypothesis premise ranking baseline

Area:
`training`, `execution`

Priority:
`p2`

Blocked by:
Issue 5.1 and Issue 3.1

Why it matters:
Ranking local hypotheses is the simplest useful premise-selection baseline and a good stepping stone before large-scale library retrieval.

Acceptance criteria:

- local hypotheses can be scored against a proof state
- a simple evaluation protocol exists
- the ranked hypotheses can be surfaced to downstream tactic code

## Epic 6: Symbolic Interface Preparation

Goal:
Prepare the boundary between neural outputs and later symbolic reasoning.

### Issue 6.1: Define a minimal symbolic-confidence interface

Area:
`symbolic`

Priority:
`p2`

Can run in parallel:
Yes

Why it matters:
Symbolic integration should consume a stable contract, not training-specific internals.

Acceptance criteria:

- a small interface is documented
- model confidence can be converted into a symbolic record format
- the interface does not require changing the existing graph/training pipeline

## Epic 7: Collaboration and Project Hygiene

Goal:
Make outside contributions easier to coordinate.

### Issue 7.1: Add contributor guidance for picking up issues and running the stack

Area:
`documentation`

Priority:
`p1`

Can run now:
Yes

Parallel-friendly:
Yes

Why it matters:
Once GitHub issues exist, contributors need a simple guide for environment setup, prepared data expectations, and where to start.

Acceptance criteria:

- a `CONTRIBUTING.md` or equivalent exists
- issue labels and recommended workflow are documented
- "how to run tests / prepare data / train baseline" is summarized for contributors

## Recommended First Parallel Wave

These can be worked on at the same time with low overlap:

- Issue 1.1: parser coverage audit
- Issue 2.1: baseline ablation suite
- Issue 2.2: deeper run analysis
- Issue 7.1: contributor guide

These should follow next:

- Issue 1.2: parser extensions
- Issue 3.1: Lean environment wrapper
- Issue 2.3: throughput tuning

## Recommended Ownership Pattern

If several people collaborate, a clean split would be:

- Contributor A: representation and parser quality
- Contributor B: training ablations and analysis
- Contributor C: LeanDojo execution wrapper
- Contributor D: docs and contributor hygiene

This keeps write scopes and architectural concerns relatively separated.
