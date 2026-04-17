# Detailed GitHub Issue Specifications

## Purpose

This document is the detailed source of truth for the live GitHub issues in this repository.

The goal is to make every issue clear enough that a contributor can read it, understand why it exists, understand what is and is not included, understand what must be done before starting, and understand what "done" means without needing a long back-and-forth discussion first.

Each issue body below is wrapped in markers so it can be synced directly to GitHub if needed.

## Writing Principles

Each issue should try to answer these questions explicitly:

- Why does this matter now?
- What background should the contributor know?
- What must already exist before starting?
- What is in scope?
- What is out of scope?
- What are concrete examples of the problem?
- What files or modules are likely involved?
- What artifacts or deliverables should be produced?
- What exact conditions count as complete?
- Can this issue run in parallel with other work?

## Detailed Issue Bodies

## Issue #1: Run a parser coverage audit on real LeanDojo states

<!-- ISSUE:1:start -->
## Summary

We need a careful, evidence-based parser coverage audit on real LeanDojo proof states so we know exactly what the current parser handles well, what it partially handles, and what still fails outright.

This issue is about measurement and visibility first, not about immediately fixing every parser limitation.

## Why This Matters

The parser is one of the deepest foundation layers in the repository.

Almost every later phase depends on it:

- proof-state graph construction depends on it
- prepared dataset quality depends on it
- model inputs depend on it
- later execution and search tooling depend on it

If the parser silently fails, distorts structure, or drops important syntax, then later model results can become difficult to trust. A model can look good while still being trained on a biased subset of "easy" states.

This issue exists so the project stops guessing about parser quality and starts measuring it directly.

## Background

The repository already has:

- proof-state parsing in `atp_lean_gnn/state.py`
- expression parsing in `atp_lean_gnn/parser.py`
- dataset preparation in `atp_lean_gnn/preprocess.py`
- failure logging in the prepared-data pipeline

What is still missing is a dedicated parser audit that answers questions like:

- What percentage of real dataset states parse successfully?
- Which syntax families fail most often?
- Are failures concentrated in train, validation, or test?
- Are there "partial success" cases where parsing succeeds syntactically but loses important structure?

## Prerequisites

Required before starting:

- a working prepared-data command
- access to the LeanDojo dataset or a representative prepared sample
- familiarity with the current parser modules

Helpful but not strictly required:

- familiarity with Lean proof-state syntax
- familiarity with the current failure logs written during preprocessing

## In Scope

- run parser coverage over a meaningful sample first
- optionally extend the audit to full prepared splits if runtime allows
- categorize failures by type rather than leaving them as raw tracebacks
- save the results in both machine-readable and human-readable formats
- collect representative example states for each major failure category
- identify a prioritized shortlist of syntax families for follow-up parser work

## Out of Scope

- fixing every parser failure during this same issue
- redesigning the full graph representation
- changing the training pipeline beyond what is needed to support the audit

## Concrete Examples

Examples of syntax families we may discover as failure categories:

- binder-heavy expressions like `forall` or dependent binders
- typeclass-heavy terms
- implicit arguments
- notation that the simplified parser tokenizes badly
- goals or hypotheses containing nested logical structure that parse only partially

Example of why categorization matters:

If ten failures all come from the same root cause, like poorly handled binders, then that is one parser task, not ten unrelated bugs.

## Suggested Implementation Shape

Possible directions include:

- a dedicated audit script
- an extension of the existing preprocessing report
- or a report-generation mode built into the current pipeline

The exact implementation is flexible, but the final output should make it easy to answer:

- how many examples were attempted
- how many succeeded
- how many failed
- what the main failure families are
- which examples illustrate each family

## Likely File Touch Points

- `atp_lean_gnn/preprocess.py`
- `atp_lean_gnn/parser.py`
- `atp_lean_gnn/state.py`
- `atp_lean_gnn/cache.py`
- `scripts/prepare_dataset.py`
- `tests/` for any new reporting-related coverage

## Deliverables

- one parser coverage report in JSON
- one parser coverage report in Markdown
- representative example rows or state snippets for major failure families
- a short prioritized list of recommended parser follow-ups

## Acceptance Criteria

- parser success rate is reported clearly on a real dataset sample
- failure categories are grouped and named, not just listed as raw exceptions
- at least one saved report artifact is added under `artifacts/` or `runs/`
- the report is detailed enough to drive follow-up parser issues with confidence

## Parallelization Notes

This issue can run in parallel with:

- baseline ablations
- deeper run analysis
- contributor documentation

It should happen before major parser-extension work, because it determines where effort is best spent.
<!-- ISSUE:1:end -->

## Issue #2: Extend parser support for binder-heavy and currently failing constructs

<!-- ISSUE:2:start -->
## Summary

Use the evidence from the parser coverage audit to extend parser support for the most important currently failing Lean constructs, especially binder-heavy and structurally rich expressions.

This issue is about targeted improvement, not about building a full Lean parser from scratch.

## Why This Matters

Once the coverage audit identifies the most common failure families, the next step is to remove those blockers so the graph pipeline works on a broader and more representative slice of theorem-proving states.

Without this work:

- prepared datasets may systematically exclude harder states
- training results may reflect parser bias rather than modeling quality
- later execution and search phases may inherit brittle assumptions

## Background

The current parser is intentionally simplified. That was a good choice for bootstrapping the project, but now the repo is past the pure prototype stage.

We do not need a perfect full Lean front end here. We do need a parser that is robust enough for the project’s next research phases.

## Prerequisites

Required:

- Issue #1 should be completed first
- major failure categories should be known

Helpful:

- a small bank of real failing proof states saved from the audit
- a clear ranking of which syntax families occur most often

## In Scope

- extend parser behavior for the top failing syntax families from the audit
- add focused regression tests for each supported failure class
- confirm that the preprocessing pipeline handles those cases after the fix

## Out of Scope

- fully matching Lean’s own elaboration behavior
- solving every rare corner case in one pass
- changing training architecture

## Concrete Examples

Examples of the kind of improvement this issue may need:

- better handling of `∀ x, ...` and binder structures
- more robust parsing of nested implication and quantifier combinations
- handling of implicit-argument syntax where it appears in proof states
- better tokenization around punctuation or notation-heavy expressions

The important rule is that improvements should come from real observed failures, not from speculative parser expansion.

## Suggested Work Strategy

1. Take the top failure family from the audit.
2. Save a few minimal reproducing examples.
3. Extend parser logic carefully.
4. Add regression tests immediately.
5. Rerun the relevant sample.
6. Move to the next category only after the previous one is stable.

## Likely File Touch Points

- `atp_lean_gnn/parser.py`
- `atp_lean_gnn/state.py`
- `tests/test_graph_pipeline.py`
- possibly `tests/test_dataset_preparation.py`

## Deliverables

- parser updates for the targeted failure families
- regression tests covering each addressed family
- before/after notes showing the improvement in parse success

## Acceptance Criteria

- previously failing sample cases now parse successfully
- each addressed syntax family has test coverage
- a follow-up coverage run shows a measurable improvement
- no major regressions are introduced in existing parser behavior

## Parallelization Notes

This should not start before the audit, but it can proceed in parallel with:

- training ablations
- run-analysis improvements
- contributor docs
<!-- ISSUE:2:end -->

## Issue #3: Strengthen cache versioning and artifact schema metadata

<!-- ISSUE:3:start -->
## Summary

Add explicit schema and build-version metadata to prepared artifacts and training inputs so collaborators can trace exactly how a cache was built and detect incompatible versions early.

## Why This Matters

The repository now has real prepared datasets and real training runs. That means cache compatibility is no longer a theoretical concern.

Without explicit versioning, several bad things can happen:

- a prepared cache built with old parser logic gets reused silently
- a training run compares results across incompatible vocabularies
- new contributors cannot tell whether artifacts are stale
- debugging becomes much harder because artifact provenance is unclear

## Background

The repo already writes:

- prepared manifests
- vocab files
- graph artifacts
- training runs and configs

What is still weak is the contract that explains:

- which parser logic produced this cache
- which label normalization logic produced this vocab
- which schema version training expects

## Prerequisites

Required:

- familiarity with the prepared-artifact layout under `artifacts/prepared/...`
- familiarity with how training reads manifests and vocab files

Helpful:

- awareness of recent parser and label changes

## In Scope

- add explicit parser/cache/schema version fields to manifests
- store enough build metadata to trace prepared artifacts
- make training fail fast when incompatible schemas are detected
- document the version fields clearly

## Out of Scope

- rebuilding all historical caches automatically
- designing a heavy artifact registry system
- changing model logic unrelated to schema compatibility

## Concrete Example

Suppose node vocab construction changes in a future commit.

Without cache versioning, an older `.pt` artifact may still load, but:

- `x` ids may mean different symbols than expected
- `State` may still exist but other ids may be shifted
- model behavior may become hard to interpret

Good schema metadata makes that mismatch obvious and actionable.

## Suggested Version Fields

Examples of useful metadata:

- cache schema version
- parser version
- label/vocab version
- build timestamp
- dataset name and split
- build command or config summary

## Likely File Touch Points

- `atp_lean_gnn/cache.py`
- `atp_lean_gnn/preprocess.py`
- `atp_lean_gnn/training.py`
- tests covering manifest compatibility checks

## Deliverables

- updated manifests with version metadata
- training-time compatibility checks
- documentation of the schema/version contract

## Acceptance Criteria

- prepared manifests expose schema and build versions clearly
- training raises actionable errors when a cache is incompatible
- contributors can tell how a prepared cache was produced

## Parallelization Notes

This can run in parallel with ablations and documentation work.
It is a good collaboration issue because it has a well-bounded scope and helps everyone else.
<!-- ISSUE:3:end -->

## Issue #4: Run the first ablation suite for edge direction, readout, and node-type usage

<!-- ISSUE:4:start -->
## Summary

Run the first disciplined ablation suite around the current supervised baseline so we can identify which architectural choices are actually helping.

This issue should produce a scientific comparison, not just more trained checkpoints.

## Why This Matters

The repo already has a good first baseline run.
That is a milestone, but it is not yet a strong scientific foundation.

Right now we know:

- one GraphSAGE configuration works

We do not yet know:

- whether bidirectional edges are crucial
- whether the `State` node readout is better than a simpler pooling strategy
- whether node-type embeddings are contributing materially

Until those questions are answered, later architecture discussions remain too speculative.

## Background

The current baseline uses:

- GraphSAGE
- a `State` node readout
- bidirectional training-time edges
- node-type embeddings

Those were sensible defaults, but now they need to be tested systematically.

## Prerequisites

Required:

- a stable prepared dataset
- at least one completed reference baseline run
- working train/evaluate scripts

Helpful:

- a consistent hardware setup or documented hardware notes
- a clean naming scheme for runs

## In Scope

- compare bidirectional vs forward edges
- compare `State`-node readout vs mean pooling
- compare node-type embeddings on vs off
- keep the rest of the baseline fixed as much as possible
- summarize results in one comparison artifact

## Out of Scope

- trying every possible GNN architecture
- changing multiple unrelated variables at once
- moving to search or execution work before the comparisons are summarized

## Concrete Example

If the model performs almost the same with forward-only edges as with bidirectional edges, then the added complexity may not be doing much.

If removing node-type embeddings hurts performance noticeably, then that tells us the model uses syntactic role information in a meaningful way.

This issue exists to convert those intuitions into measured evidence.

## Suggested Experimental Shape

A good first suite would vary one factor at a time around the current baseline:

1. forward edges only
2. mean pooling instead of `State` readout
3. node-type embeddings disabled

Optional follow-up, if budget allows:

- a small combined comparison for the best observed alternative settings

## Likely File Touch Points

- `configs/baseline_graphsage_state.json`
- possibly new config variants under `configs/`
- `atp_lean_gnn/model.py`
- `atp_lean_gnn/training.py`
- `scripts/compare_runs.py`
- `atp_lean_gnn/analysis.py` if comparison reporting needs improvement

## Deliverables

- one run per ablation setting
- one comparison report or markdown summary
- a final recommendation naming the baseline to beat

## Acceptance Criteria

- each run is reproducible and stored with config and summary artifacts
- results are summarized in one place rather than scattered across directories
- a clear conclusion is written for each comparison axis
- the project has a documented official baseline after the issue is complete

## Parallelization Notes

This can run immediately and in parallel with:

- parser auditing
- analysis enhancements
- contributor documentation
<!-- ISSUE:4:end -->

## Issue #5: Deepen run analysis with confusion reports and tactic-family failure summaries

<!-- ISSUE:5:start -->
## Summary

Expand the analysis layer so finished runs explain not only aggregate accuracy, but also which tactic classes are hard, which tactics are commonly confused, and what representative mistakes actually look like.

## Why This Matters

Top-1 and top-5 accuracy are necessary, but they are not enough for real understanding.

Two models can have similar aggregate accuracy while behaving very differently:

- one may be strong on common tactics and weak on rare ones
- one may systematically confuse `rw` and `simp`
- one may fail mostly on states with deeper logical structure

If the analysis layer stays shallow, contributors will end up making changes without knowing what they are improving.

## Background

The repo already has:

- `summary.json`
- `eval_val.json`
- `eval_test.json`
- analysis scripts for finished runs

This issue is about making that analysis much more decision-useful.

## Prerequisites

Required:

- at least one completed run with saved evaluation outputs
- familiarity with the current analysis scripts

Helpful:

- a completed ablation run or two to compare

## In Scope

- summarize hardest tactic classes with support counts
- surface common confusions for high-support tactics
- save representative errors in both machine-readable and readable formats
- make outputs easy to compare across runs

## Out of Scope

- changing the underlying model architecture as part of this issue
- premise-selection analysis
- search-level metrics

## Concrete Examples

Useful analysis questions include:

- Does the model confuse `rw` with `simp` when both are plausible?
- Are `exact` errors mostly due to missing local-context understanding?
- Are low-support tactic classes dominating the worst metrics?

Examples of outputs that would help:

- "Top 10 confusion pairs"
- "Hardest tactics with support >= N"
- "Representative false positives for `apply`"

## Likely File Touch Points

- `atp_lean_gnn/analysis.py`
- `scripts/analyze_run.py`
- `scripts/compare_runs.py`
- tests for run analysis

## Deliverables

- richer per-run analysis artifacts
- confusion summaries
- hardest-class summaries
- representative error exports

## Acceptance Criteria

- analysis outputs make common failure modes obvious
- reports are readable without manually inspecting raw predictions
- the same analysis format can be reused for future runs and ablations

## Parallelization Notes

This can run in parallel with parser auditing, ablations, and contributor documentation.
It is especially valuable while ablations are running because it helps interpret their outcomes.
<!-- ISSUE:5:end -->

## Issue #6: Improve training throughput and runtime ergonomics

<!-- ISSUE:6:start -->
## Summary

Improve baseline training throughput and make long-running training more practical, especially on modest hardware such as laptop GPUs or CPU-only setups.

## Why This Matters

Once a repo starts supporting real experiments, slow turnaround becomes a collaboration problem.

When runs take too long:

- contributors avoid ablations
- interrupted runs waste momentum
- reproducibility becomes harder because fewer people can afford to rerun experiments

This issue is about making the training workflow more usable, not about chasing micro-optimizations for their own sake.

## Background

The repo already supports:

- checkpointing
- resume from `last.pt`
- dataloader worker tuning
- pinned memory
- AMP on CUDA

That is a strong start, but there is still room to:

- benchmark current throughput more clearly
- document recommended settings for common hardware profiles
- remove avoidable friction from long runs

## Prerequisites

Required:

- one or more completed or interrupted baseline training runs
- access to at least one realistic hardware setup

Helpful:

- familiarity with the current config knobs in `configs/baseline_graphsage_state.json`

## In Scope

- benchmark current training throughput
- document recommended configs for common hardware situations
- validate interruption and resume behavior
- make runtime feedback more practical if needed

## Out of Scope

- replacing the whole training stack
- changing the scientific target of the baseline
- large architecture redesigns

## Concrete Examples

Useful practical improvements might include:

- a documented "laptop GPU" config
- a documented "CPU-only smoke run" config
- better guidance around `batch_size`, `num_workers`, and AMP
- a clearer summary of what to monitor during long training

Example problem this issue should reduce:

A contributor sees low apparent GPU usage in Task Manager and has no clear guidance on whether the bottleneck is dataloading, batch size, or the wrong monitoring view.

## Likely File Touch Points

- `configs/baseline_graphsage_state.json`
- `atp_lean_gnn/training.py`
- `README.md`
- possibly additional config files under `configs/`

## Deliverables

- throughput notes or benchmarks
- recommended runtime configs
- verified checkpoint/resume guidance

## Acceptance Criteria

- there is documented guidance for at least two hardware profiles
- resume behavior has been tested and described clearly
- contributors can choose a sensible runtime configuration without guesswork

## Parallelization Notes

This can run in parallel with ablations and analysis work.
It should stay coordinated with any training-config changes made for Issue #4.
<!-- ISSUE:6:end -->

## Issue #7: Define and implement a minimal Lean environment wrapper

<!-- ISSUE:7:start -->
## Summary

Build the first minimal environment wrapper that lets the repository interact with Lean theorem states programmatically instead of only operating on offline cached proof states.

This is the bridge from supervised learning infrastructure into executable theorem proving.

## Why This Matters

The current repo can:

- represent proof states
- train a model to predict tactic heads
- evaluate those predictions offline

What it cannot yet do is:

- load a theorem interactively
- apply a tactic
- observe the resulting next state

That missing layer is the biggest conceptual gap between the current baseline and an actual theorem-proving system.

## Background

Later work on:

- proof replay
- search
- premise-aware execution

all depends on a stable environment wrapper.

This issue should create that foundation in the smallest reliable form possible.

## Prerequisites

Required:

- familiarity with the project’s current proof-state representation
- basic understanding of Lean proof states and tactics

Helpful:

- familiarity with LeanDojo or the chosen interaction mechanism
- awareness of how proof-state text currently enters the graph pipeline

## In Scope

- define a minimal environment API
- load a theorem or selected proof target
- expose the current proof state
- apply a tactic string
- return the next proof state or failure information
- detect when the theorem is solved

## Out of Scope

- full proof search
- premise selection
- reinforcement learning
- heavy optimization or distributed execution

## Concrete Example

We want an interaction pattern conceptually like:

```text
env = load_theorem(...)
state0 = env.current_state()
result1 = env.apply_tactic("rw [h]")
state1 = result1.next_state
done = result1.completed
```

The exact API can differ, but it should support the same reasoning flow.

## Design Expectations

The wrapper should make the following easy to inspect:

- current theorem identifier
- current proof state text
- tactic attempted
- success vs failure
- next state text if successful
- whether the proof is complete

Failures should be explicit and debuggable rather than silent.

## Likely File Touch Points

- a new execution module such as `atp_lean_gnn/lean_env.py`
- supporting scripts for environment smoke tests or demos
- docs explaining the environment contract
- tests for at least basic stepping behavior

## Deliverables

- a documented minimal environment wrapper
- one or more smoke commands or scripts
- tests or at least deterministic validation around stepping

## Acceptance Criteria

- the repo can load at least one theorem programmatically
- one tactic can be applied and the resulting state can be inspected
- success, failure, and completion are represented clearly
- downstream code has a stable enough API to build replay and search on top of it

## Parallelization Notes

This issue can begin before search, but it should stay coordinated with any later replay implementation.
It does not depend on ablations finishing, which makes it a good separate workstream.
<!-- ISSUE:7:end -->

## Issue #8: Add gold-trace proof replay for selected theorems

<!-- ISSUE:8:start -->
## Summary

Add the ability to replay known-good proof traces over selected theorems so the repository can verify execution correctness before attempting model-guided search.

## Why This Matters

Before asking a model to guide theorem proving, the repo should first prove that it can reliably replay tactics that are already known to work.

Gold-trace replay gives us a debugging baseline:

- if replay fails, the environment layer is not stable enough yet
- if replay succeeds, later search failures can be interpreted more confidently

## Background

This issue sits directly after the minimal environment wrapper.

The idea is simple:

- choose a theorem with a known tactic trace
- apply each tactic in order
- verify that each transition behaves as expected

## Prerequisites

Required:

- Issue #7 should be done first
- the environment wrapper should expose state, tactic application, and completion detection

Helpful:

- a small bank of selected example theorems
- known tactic traces from LeanDojo data or another source

## In Scope

- replay selected gold tactic sequences
- report step-by-step success or failure
- summarize replay success rate
- log mismatch details with enough context to debug

## Out of Scope

- beam search
- tactic prediction from the model
- premise selection

## Concrete Example

If the gold trace is:

```text
apply h
exact hp
```

then replay should show:

1. initial state
2. result after `apply h`
3. result after `exact hp`
4. proof completion

If any step fails, the output should make it obvious:

- which theorem
- which step index
- which tactic
- what the state was before the failure

## Likely File Touch Points

- execution-layer module
- replay script such as `scripts/replay_proof.py`
- docs for running replay
- tests around deterministic replay cases

## Deliverables

- a replay command or script
- replay summaries
- saved failure details for mismatches

## Acceptance Criteria

- selected proofs can be replayed end to end
- replay success and failure are summarized clearly
- failures are detailed enough to debug without reproducing blindly

## Parallelization Notes

This depends on Issue #7.
Once the execution wrapper exists, replay work can proceed without waiting for search or premise-selection tasks.
<!-- ISSUE:8:end -->

## Issue #9: Implement a beam-search baseline over tactic predictions

<!-- ISSUE:9:start -->
## Summary

Implement the first proof-search baseline by combining the trained tactic model with environment stepping in a beam-search loop.

This is the first issue that turns the project from single-step prediction into multi-step proof attempts.

## Why This Matters

A next-tactic classifier is useful, but theorem proving is usually not solved by one greedy action.

Beam search is the simplest strong next step because it:

- explores multiple candidate tactic paths
- remains much easier to debug than MCTS
- tests whether the model is useful beyond offline accuracy

## Background

By the time this issue begins, the repo should already have:

- a measured baseline model
- an execution wrapper
- gold-trace replay confidence

Beam search should be treated as the first search baseline, not the final search design.

## Prerequisites

Required:

- Issue #7 minimal environment wrapper
- Issue #8 gold-trace replay
- a trained model checkpoint that can rank tactics

Helpful:

- analysis outputs showing which tactics are common and reliable

## In Scope

- implement beam-search expansion over candidate tactic predictions
- make beam width and search depth configurable
- save traces for solved and failed attempts
- compare beam behavior against greedy behavior where sensible

## Out of Scope

- MCTS
- RL
- symbolic validation
- full tactic-argument generation if the repo is not ready for that yet

## Concrete Example

At a high level, the loop should look like:

1. start from the current proof state
2. ask the model for top candidate tactics
3. expand the best few candidates
4. apply them through the environment
5. keep the most promising resulting states
6. repeat until solved or budget exhausted

This issue should keep the implementation explainable and inspectable.

## Likely File Touch Points

- a new search module such as `atp_lean_gnn/search.py`
- execution wrapper integration
- model scoring integration
- scripts for running beam search on selected theorems

## Deliverables

- beam-search implementation
- configurable search settings
- saved search traces

## Acceptance Criteria

- beam search runs end to end on selected examples
- search traces are saved for solved and failed attempts
- the implementation is documented well enough for later extension

## Parallelization Notes

This depends on the execution layer and replay reliability.
Search metrics and trace-format work can overlap with this once the basic loop shape is stable.
<!-- ISSUE:9:end -->

## Issue #10: Add search metrics and trace logging

<!-- ISSUE:10:start -->
## Summary

Add structured metrics and trace logging for search runs so proof attempts can be debugged, compared, and summarized systematically.

## Why This Matters

Search without observability quickly becomes frustrating.

If a proof attempt fails, we need to know:

- where it failed
- how deep it went
- which tactics were tried
- whether the beam collapsed too early
- whether timeouts or invalid tactics dominated

Without trace logging, search becomes a black box. This issue exists to prevent that.

## Background

This issue becomes relevant as soon as beam search or any other search loop exists.

The repo already has good discipline around training artifacts. Search should get the same treatment:

- structured metrics
- structured traces
- readable summaries

## Prerequisites

Required:

- a working search loop, likely from Issue #9

Helpful:

- a small set of benchmark theorems to run search on repeatedly

## In Scope

- report proof success rate
- report average and max search depth
- report timeout and failure counts
- save search traces in an inspectable format
- make outputs easy to compare across runs

## Out of Scope

- redesigning the search algorithm itself
- symbolic reasoning
- premise-selection modeling

## Concrete Example

A useful trace should let a contributor inspect:

- theorem identifier
- initial state
- beam expansions per depth
- tactic tried at each branch
- branch outcome
- final solve/fail result

This should be possible without rerunning the whole search just to remember what happened.

## Likely File Touch Points

- search module
- run artifact writers
- analysis/reporting utilities
- scripts for running search

## Deliverables

- structured search metrics
- saved trace files
- readable search summaries

## Acceptance Criteria

- search metrics are written automatically after runs
- traces distinguish solved, failed, and timed-out attempts
- contributors can inspect a failed search attempt without digging through raw logs only

## Parallelization Notes

This is downstream of the first search loop, but parts of the trace format can be designed in parallel once the search structure is known.
<!-- ISSUE:10:end -->

## Issue #11: Define the premise-selection task and dataset contract

<!-- ISSUE:11:start -->
## Summary

Define exactly what premise selection means in this repository, decide the first premise-selection task to support, and write the corresponding dataset contract so the later implementation phase is not based on vague assumptions.

## Why This Matters

The current model predicts tactic heads only.

That is good for a first milestone, but many executable proof steps require more detail:

- `rw [h]` needs the premise `h`
- `apply foo` needs the theorem `foo`
- `exact hp` needs the hypothesis `hp`

So there is a gap between:

- tactic-family prediction
- executable tactic generation

Premise selection is one of the main ways to close that gap.

## Background

Premise selection means choosing which fact is useful for the current proof state.

A fact may be:

- a local hypothesis already in the context
- a previously proved theorem from a library

These are different problem sizes.

Local-hypothesis selection is a smaller and more controlled task.
Library-premise retrieval is larger and more open-ended.

This issue should decide where the project starts.

## Prerequisites

Required:

- a solid understanding of the current tactic-head baseline
- familiarity with Lean proof states and local context

Helpful:

- basic familiarity with the upcoming execution layer
- awareness of how tactics like `rw`, `apply`, and `exact` use facts

## In Scope

- define what counts as a premise in this repo
- separate local-hypothesis selection from library-premise retrieval
- choose the first premise-selection task to implement
- specify the dataset contract for that task

## Out of Scope

- implementing the full premise-selection model
- solving all tactic-argument generation immediately
- symbolic integration

## Concrete Examples

Example 1:

```text
h : a = b
|- f a = f b
```

Tactic prediction may say:

- `rw`

Premise selection must answer:

- use `h`

Example 2:

```text
h : P -> Q
hp : P
|- Q
```

Tactic prediction may say:

- `apply`

Premise selection must answer:

- use `h`

Example 3:

```text
h : P
g : Q
|- P
```

Tactic prediction may say:

- `exact`

Premise selection must answer:

- use `h`, not `g`

These examples show why premise selection is a distinct task.

## Questions This Issue Should Answer

- Are we selecting only local hypotheses first?
- Do we include library lemmas in the first version?
- What training example shape will we use?
- How will candidate premises be represented?
- What evaluation metric makes sense for this task?

## Likely File Touch Points

- `docs/`
- future training and dataset modules
- possibly `atp_lean_gnn/dataset.py` if metadata needs expansion later

## Deliverables

- a written problem definition
- a chosen first-scope premise-selection task
- a dataset contract for future implementation

## Acceptance Criteria

- local vs library premise handling is explicitly separated
- the first premise-selection task is narrow enough to implement cleanly
- the output is specific enough that a later implementation issue can begin without ambiguity

## Parallelization Notes

This can begin before a full premise-selection implementation exists.
It is a good research-and-design issue to run alongside execution and search work.
<!-- ISSUE:11:end -->

## Issue #12: Define a minimal symbolic-confidence interface

<!-- ISSUE:12:start -->
## Summary

Define the smallest useful interface that maps neural model outputs into a symbolic-confidence representation, so later neuro-symbolic work has a stable boundary to build on.

## Why This Matters

The long-term vision of the project includes a symbolic or neuro-symbolic layer.

That future layer should not depend directly on the internals of:

- the current GraphSAGE implementation
- specific training scripts
- ad hoc output shapes

It should depend on a stable contract instead.

This issue exists to design that boundary early, before symbolic work becomes tangled with model internals.

## Background

Right now the repo is still mostly in the supervised-learning phase.

That is good. It means this issue should stay small and architectural:

- define an interface
- do not prematurely build a large symbolic system

## Prerequisites

Required:

- understanding of the current training outputs
- understanding of the project’s long-term symbolic direction

Helpful:

- familiarity with later search and execution plans

## In Scope

- define a symbolic-confidence record or interface
- explain how tactic scores or state scores map into that interface
- keep the contract independent from model-specific implementation details

## Out of Scope

- implementing full symbolic reasoning
- designing revision-rule systems in full detail
- changing the training architecture around this issue

## Concrete Example

At a conceptual level, the symbolic side may eventually want something like:

- candidate action
- confidence score
- provenance
- optional explanation or metadata

This issue should define that shape without overcommitting to a huge symbolic stack too early.

## Likely File Touch Points

- `docs/`
- possibly a small interface module or typed record later

## Deliverables

- a written interface proposal
- a simple record format or contract sketch
- notes on how current model outputs would map into it

## Acceptance Criteria

- the interface is small, explicit, and stable enough to reference later
- it does not require refactoring the current training pipeline
- symbolic work can point to it as the agreed boundary

## Parallelization Notes

This can run in parallel with execution and search work because it is primarily an interface-design task.
It should remain lightweight at this stage.
<!-- ISSUE:12:end -->

## Issue #13: Add contributor guidance for picking up issues and running the stack

<!-- ISSUE:13:start -->
## Summary

Create contributor-facing guidance so new collaborators can understand the repository structure, set up the environment, run the key workflows, and choose an issue without needing direct handholding first.

## Why This Matters

The repo now has:

- multiple major workstreams
- prepared-data workflows
- training scripts
- analysis scripts
- a public issue backlog

That is great for growth, but it also means new contributors can get lost quickly unless there is a clear entry path.

Good contributor docs reduce repeated onboarding overhead and make parallel work more realistic.

## Background

The README already explains common commands and the high-level repo layout.

What is still missing is a collaborator-oriented guide that answers practical questions like:

- How do I set up the environment?
- What should I run first?
- Which issues are good for a first contribution?
- Which generated directories should I expect?
- How do I avoid stepping on long-running experiment work?

## Prerequisites

Required:

- familiarity with the current repo workflows

Helpful:

- awareness of the new GitHub issue hierarchy and labels

## In Scope

- add contributor setup guidance
- summarize how to prepare data, train, evaluate, and run tests
- document labels and how to choose work
- make the contribution path obvious for both research and engineering tasks

## Out of Scope

- a full governance system
- CI/CD automation if it is not already planned
- rewriting all existing docs

## Concrete Example

A good contributor guide should let a newcomer answer questions like:

- "If I want a documentation issue, where do I start?"
- "If I want a parser issue, what files matter?"
- "How do I run the baseline without downloading everything first?"
- "Which commands are safe smoke tests?"

## Likely File Touch Points

- `CONTRIBUTING.md` or equivalent
- `README.md`
- docs that explain issue structure or common workflows

## Deliverables

- contributor guide
- issue-label explanation
- practical setup and workflow notes

## Acceptance Criteria

- a new contributor can identify a suitable issue and first command path quickly
- the guide explains the main workflows without assuming deep prior knowledge
- contributors can understand where outputs and artifacts will appear

## Parallelization Notes

This can run immediately and in parallel with almost everything else.
It is especially valuable while the backlog is fresh and other contributors are beginning to engage.
<!-- ISSUE:13:end -->

## Issue #14: Epic: Representation and baseline-quality hardening

<!-- ISSUE:14:start -->
## Summary

This epic groups the work needed to make the current representation and supervised-learning foundation scientifically trustworthy and easier to build on.

The repo already has a successful baseline. This epic exists to make that baseline more reliable, more interpretable, and easier to trust as the reference point for later phases.

## Why This Epic Exists

Before moving deeper into:

- live execution
- search
- premise selection
- symbolic integration

we need confidence in the layers that already exist.

That means:

- measuring parser quality on real data
- fixing important parser gaps
- making caches traceable
- understanding which modeling choices matter
- improving experimental interpretation

This epic is the "solid ground" phase.

## Prerequisites

The repo already has the main prerequisites for this epic:

- proof-state graph construction
- dataset preparation
- baseline training
- run analysis

## Child Issues

- [ ] #1 Run a parser coverage audit on real LeanDojo states
- [ ] #2 Extend parser support for binder-heavy and currently failing constructs
- [ ] #3 Strengthen cache versioning and artifact schema metadata
- [ ] #4 Run the first ablation suite for edge direction, readout, and node-type usage
- [ ] #5 Deepen run analysis with confusion reports and tactic-family failure summaries
- [ ] #6 Improve training throughput and runtime ergonomics

## What Is In Scope

- parser quality and parser follow-up
- dataset/cache hygiene
- training baseline ablations
- deeper analysis and experiment discipline
- runtime usability improvements for training

## What Is Out of Scope

- live Lean execution
- search
- premise-selection implementation
- symbolic integration

## Exit Criteria

This epic is complete when:

- parser quality is measured on real data
- major parser gaps have targeted follow-up work
- cache compatibility is explicit
- the baseline to beat is backed by ablations
- analysis outputs are rich enough to interpret results well

## Parallelization Notes

Several child issues can run at the same time:

- #1 parser audit
- #4 ablations
- #5 deeper run analysis
- #6 runtime ergonomics

That makes this epic a good first collaboration wave.
<!-- ISSUE:14:end -->

## Issue #15: Epic: LeanDojo execution and proof replay foundation

<!-- ISSUE:15:start -->
## Summary

This epic groups the work needed to move from offline proof-state classification into live theorem-state interaction and replay.

## Why This Epic Exists

The current repo predicts next tactics from cached proof states.
That is an important milestone, but it is still offline learning.

To become a usable theorem-proving system, the project must support:

- loading theorem states
- applying tactics programmatically
- observing state transitions
- replaying known proof traces

This epic creates that execution foundation.

## Prerequisites

Helpful foundations that already exist:

- graph-based proof-state representation
- baseline training and evaluation
- documentation of the larger roadmap

Required child dependency order:

- environment wrapper first
- proof replay second

## Child Issues

- [ ] #7 Define and implement a minimal Lean environment wrapper
- [ ] #8 Add gold-trace proof replay for selected theorems

## What Is In Scope

- minimal executable interaction with theorem states
- proof replay for debugging and validation
- stable state-transition interfaces for later search code

## What Is Out of Scope

- search
- model-guided theorem proving
- premise selection
- symbolic integration

## Exit Criteria

This epic is complete when:

- the repo can load at least selected theorems programmatically
- tactics can be applied and next states inspected
- known proof traces can be replayed reliably

## Parallelization Notes

This epic is a separate workstream from parser auditing and baseline ablations, so it can proceed in parallel once someone owns the execution side.
<!-- ISSUE:15:end -->

## Issue #16: Epic: Search and tactic-argument bridge

<!-- ISSUE:16:start -->
## Summary

This epic groups the first search work and the early design work needed to bridge from tactic-family prediction toward executable tactic selection.

## Why This Epic Exists

Once execution and replay are stable, the next real jump is from:

- "predict the next tactic head"

to:

- "attempt whole proofs over multiple steps"

That requires:

- search over candidate actions
- metrics and traces for understanding search behavior
- a clear plan for premise selection and tactic arguments

## Prerequisites

Required:

- execution wrapper
- proof replay confidence

Helpful:

- an official supervised baseline to score candidate tactics

## Child Issues

- [ ] #9 Implement a beam-search baseline over tactic predictions
- [ ] #10 Add search metrics and trace logging
- [ ] #11 Define the premise-selection task and dataset contract

## What Is In Scope

- first search baseline
- traceability of proof attempts
- early design boundary for tactic arguments and premise selection

## What Is Out of Scope

- advanced search such as MCTS unless clearly justified later
- RL
- full symbolic reasoning

## Exit Criteria

This epic is complete when:

- a first beam-search baseline exists
- search attempts are inspectable through metrics and traces
- the project has a clear, concrete premise-selection scope for the next implementation phase

## Parallelization Notes

Issue #11 can run partly in parallel with early search work because it is mostly problem-definition work.
<!-- ISSUE:16:end -->

## Issue #17: Epic: Symbolic bridge and contributor readiness

<!-- ISSUE:17:start -->
## Summary

This epic groups two enabling tasks that prepare the repo for broader collaboration and later neuro-symbolic work.

## Why This Epic Exists

The project has two important medium-term needs:

1. a cleaner contributor path so more people can work effectively
2. an early interface boundary for later symbolic integration

Neither one is the main proof-search bottleneck today, but both will matter more and more as the repo grows.

## Prerequisites

No strict technical prerequisites beyond familiarity with the current roadmap.

## Child Issues

- [ ] #12 Define a minimal symbolic-confidence interface
- [ ] #13 Add contributor guidance for picking up issues and running the stack

## What Is In Scope

- interface-design work for symbolic integration
- contributor onboarding and collaboration hygiene

## What Is Out of Scope

- implementing the full symbolic system
- major execution or search features

## Exit Criteria

This epic is complete when:

- symbolic work has a documented interface boundary
- new contributors can pick up an issue and run the main workflows with much less confusion

## Parallelization Notes

Both child issues can run in parallel with almost every other workstream in the repository.
<!-- ISSUE:17:end -->
