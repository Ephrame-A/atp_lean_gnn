# Project Roadmap

## Mission

Build a Lean-oriented graph representation pipeline that can serve as the foundation for:

1. supervised GNN-based tactic prediction
2. programmatic LeanDojo interaction
3. search over proof states
4. later neuro-symbolic integration

The graph layer is not an isolated visualization toy. It is the representation contract that every later model, search component, and symbolic interface will depend on.

## Current State

The repository already has a modular graph toolkit:

- `atp_lean_gnn/state.py`: parse proof states into structured hypotheses and goals
- `atp_lean_gnn/parser.py`: parse Lean-style expressions
- `atp_lean_gnn/graph.py`: build shared DAGs and compute graph statistics
- `atp_lean_gnn/pyg.py`: export DAGs to PyTorch Geometric
- `atp_lean_gnn/visualize.py`: interactive HTML graph viewer
- `atp_lean_gnn/dataset.py`: load dataset rows from LeanDojo
- `atp_lean_gnn/cli.py`: command-line entrypoint

This means the repository is ready to move from "representation prototype" into "data and learning pipeline."

## Planning Principles

- Correctness before scale
- Stable interfaces before optimization
- Cached artifacts before repeated recomputation
- Reproducible experiments before ambitious claims
- Supervised baseline before RL or symbolic integration

## Near-Term Non-Goals

The next cycle should not try to do the following:

- full end-to-end theorem proving
- full tactic-string generation
- RL training
- deep PLN integration
- benchmark racing against large language model systems

Those are later phases. The current goal is to build a trustworthy baseline stack.

## Workstreams

### Workstream 0: Representation Hardening

Status: active, mostly complete

Goal:
Make sure the graph representation layer is stable enough to support dataset preprocessing at scale.

Deliverables:

- parser support for common Lean proof-state formats
- correct reused-node analysis
- JSON export and visualization
- PyG export with optional reverse edges
- smoke tests and unit tests

Exit criteria:

- demo examples work from CLI
- file-backed proof states work from CLI
- graph statistics are trustworthy
- parser failure modes are explicit and recoverable

### Workstream 1: Dataset Preparation

Status: next

Goal:
Turn LeanDojo proof states into cached graph artifacts that can be reused by training code.

Deliverables:

- `scripts/prepare_dataset.py`
- graph cache format and manifest
- vocabulary files
- dataset summary report
- parse-failure report

Tasks:

- stream rows from LeanDojo
- parse each proof state
- build DAG
- store graph artifacts to disk
- record theorem name, tactic, split, and row id
- log parser failures without aborting the run

Exit criteria:

- preprocessing succeeds on a meaningful sample first
- full train split can be processed reproducibly
- cache can be reused without rebuilding graphs

### Workstream 2: Label Design

Status: next

Goal:
Define the supervised learning target for the first baseline.

Recommended first task:
Predict normalized tactic names rather than full tactic strings.

Deliverables:

- `atp_lean_gnn/labels.py`
- tactic normalization rules
- tactic vocabulary file
- frequency report

Questions this workstream must answer:

- how to normalize `simp only [...]`, `rw [...]`, `ext x`, and similar tactics
- what to do with rare tactics
- whether to collapse aliases

Exit criteria:

- every cached training example gets a stable label
- the label mapping is saved and versioned
- class imbalance is measured, not guessed

### Workstream 3: Baseline GNN

Status: after dataset and labels

Goal:
Train the first reproducible next-tactic classifier over proof-state graphs.

Deliverables:

- `atp_lean_gnn/model.py`
- `scripts/train_baseline.py`
- `scripts/evaluate_baseline.py`
- config file for model and training settings
- checkpoint saving and metric logging

Recommended first baseline:

- node embedding lookup from symbol vocabulary
- 3 to 5 graph convolution layers
- hidden size around 128
- graph pooling layer
- linear classifier head

Core ablations:

- forward edges only vs bidirectional edges
- mean pooling vs root-node pooling
- node labels only vs node labels plus node types
- depth and hidden size

Exit criteria:

- one full training run completes reproducibly
- top-1 and top-5 validation metrics are logged
- checkpoints and configs are saved together

### Workstream 4: Experiment Framework

Status: in parallel with baseline

Goal:
Keep experiments reproducible and comparable.

Deliverables:

- fixed seed support
- split tracking
- run directories
- saved configs and metrics
- experiment summary template

Exit criteria:

- rerunning the same config yields comparable results
- every metric can be traced back to a config and dataset cache version

### Workstream 5: LeanDojo Execution Layer

Status: after baseline

Goal:
Replay theorem states and apply tactics programmatically.

Deliverables:

- `atp_lean_gnn/lean_env.py`
- theorem loader
- tactic application wrapper
- proof replay script

Exit criteria:

- selected proofs can be replayed end to end
- state transitions are available to downstream search code

### Workstream 6: Search Layer

Status: after LeanDojo execution

Goal:
Move from single-step prediction to multi-step proof search.

Recommended order:

1. beam search
2. heuristic search
3. MCTS if justified by the baseline behavior

Exit criteria:

- search improves over greedy single-step selection
- search traces are logged and debuggable

### Workstream 7: Symbolic Bridge

Status: after search foundation

Goal:
Define a minimal interface from model outputs into symbolic confidence objects.

Deliverables:

- bridge interface
- simple truth-value conversion
- symbolic stub integration point

Exit criteria:

- symbolic code can consume model confidence without changing the graph stack

### Workstream 8: Hybrid System

Status: long-term

Goal:
Combine graph-guided learning, search, and symbolic validation in one experimental system.

Deliverables:

- revision-rule experiments
- symbolic pruning or validation loop
- lemma-generation hooks
- benchmark evaluation report

## Dependency Order

The work should proceed in this order:

`Representation -> Dataset -> Labels -> Baseline GNN -> Experiment Framework -> LeanDojo Execution -> Search -> Symbolic Bridge -> Hybrid System`

The key rule is simple:
Do not start RL or symbolic-heavy work until the supervised baseline is measured and trusted.

## Immediate Sprint

The recommended next sprint is:

1. create dataset preprocessing and caching
2. define tactic normalization and label vocabulary
3. run parser coverage over a dataset sample
4. publish a short preprocessing report

This sprint should end with reusable artifacts, not with model code yet.

## Success Metrics

Near-term metrics:

- parser success rate on sampled dataset rows
- median graph build time
- graph size distribution
- number of reused nodes per graph
- cached artifact size on disk
- tactic vocabulary size after normalization

Baseline model metrics:

- top-1 validation accuracy
- top-5 validation accuracy
- per-class support
- training time per epoch

System-level metrics for later phases:

- proof replay success rate
- search success rate
- proof completion rate
- proof length

## Risks and Mitigations

### Risk: parser coverage is weaker than expected

Mitigation:
Build preprocessing with detailed failure logs and add parser support iteratively rather than blocking on perfection.

### Risk: tactic labels are too noisy

Mitigation:
Start with normalized tactic names and save the normalization policy as versioned code.

### Risk: graphs are expensive to rebuild

Mitigation:
Cache everything needed for training and track cache versions explicitly.

### Risk: RL or symbolic work starts too early

Mitigation:
Use the phase gates in this roadmap and require exit criteria before opening the next phase.

## Definition of "Good Progress"

For the next stage, good progress means:

- we can preprocess real theorem-proving data reliably
- we know what label space we are training on
- we can train one honest baseline and evaluate it reproducibly

That is the foundation the rest of the project needs.
