# Open Questions

## Purpose

This document tracks the questions that still need explicit decisions or experiments.

Not every question needs an answer immediately. The point is to keep uncertainty visible so the project does not drift on hidden assumptions.

## Decisions Already Locked

These are current working decisions unless new evidence forces a revision.

- The canonical stored DAG edge direction is `child -> parent`.
- Reused nodes are detected by parent reuse count, not child count.
- Variable and constant names are kept in the graph.
- The first supervised task should be tactic-name prediction, not full tactic-string generation.
- The next milestone is dataset preparation, not RL or symbolic work.

## Priority 0 Questions

These block the next implementation sprint.

### Q0.1: How much real Lean syntax does the current parser cover?

Status: open

Why it matters:
The dataset-preparation stage depends on parser coverage. If real proof states contain many unsupported constructs, preprocessing will fail or silently distort structure.

Next action:
Run a parser coverage study over a sampled subset of the dataset and save categorized failure cases.

### Q0.2: What exact tactic normalization policy should define the first label space?

Status: open

Why it matters:
The first supervised baseline depends heavily on whether labels are raw tactic strings, tactic names, or a hybrid representation.

Next action:
Write a draft normalization function and measure resulting vocabulary size and class skew.

### Q0.3: What artifact format should be treated as canonical for caching?

Status: open

Candidate options:

- JSON graphs plus a separate label manifest
- serialized PyG objects
- both, with JSON for debugging and PyG for training

Why it matters:
Cache design affects preprocessing speed, disk usage, reproducibility, and debugging convenience.

Next action:
Prototype both JSON and PyG artifact generation on a sample and compare size and ease of reuse.

## Representation Questions

### Q1.1: Should node types remain hand-authored coarse categories, or grow richer?

Status: open

Why it matters:
The current categories are useful, but they may be too coarse for the learning task.

Possible directions:

- keep the current type categories for the baseline
- add richer syntactic roles later
- store both coarse and fine node annotations

### Q1.2: How should binder-heavy constructs be represented?

Status: open

Why it matters:
Lean proof states can include quantifiers, implicit arguments, and typeclass-heavy expressions that the simplified parser may not capture precisely.

Next action:
Collect real examples from preprocessing failures and design targeted parser extensions.

### Q1.3: Should graph-level metadata include theorem context beyond the raw state?

Status: open

Why it matters:
The theorem name, file path, namespace, and local context might all be useful later for analysis or training.

Next action:
Decide the minimum metadata schema for cached artifacts.

## Dataset and Label Questions

### Q2.1: What should count as one training example?

Status: open

Possibilities:

- every proof step
- only selected tactic-producing steps
- goal-focused subsets

Why it matters:
The example definition shapes dataset size and label distribution.

### Q2.2: What should we do with rare tactics?

Status: open

Possible policies:

- keep all tactics
- bucket rare classes into `<OTHER>`
- drop extremely rare classes for the first baseline

Why it matters:
A huge sparse label space may obscure whether the graph representation itself is working.

### Q2.3: Should arguments ever be predicted in the first baseline?

Status: deferred

Current recommendation:
No. Start with tactic names only.

Reason:
Argument prediction is a second problem and can wait until the first classifier is trustworthy.

## Model Questions

### Q3.1: What is the best baseline pooling strategy?

Status: open

Candidate options:

- global mean pooling
- global attention pooling
- use the `State` node embedding directly

Why it matters:
Pooling defines how local graph structure becomes a graph-level prediction signal.

### Q3.2: How many message-passing layers should the baseline use?

Status: open

Working starting point:
3 to 5 layers

Why it matters:
Too shallow may miss structure. Too deep may over-smooth or overcomplicate the first baseline.

### Q3.3: Which graph convolution should be the first baseline?

Status: open

Candidate options:

- GCNConv
- GraphSAGE
- GAT

Recommendation:
Start simple with GCN or GraphSAGE before trying attention-heavy variants.

### Q3.4: Should reverse edges be enabled by default during training?

Status: open

Why it matters:
The literature and the project plan suggest top-down context matters, which argues for bidirectional message passing.

Next action:
Make this a first-class ablation in the baseline experiments.

## LeanDojo and Search Questions

### Q4.1: What is the smallest reliable proof-replay harness we need?

Status: open

Why it matters:
Search and RL should be built on a stable environment wrapper, not ad hoc scripts.

Next action:
Define a minimal interface:

- load theorem
- get current state
- apply tactic
- inspect result
- detect completion or failure

### Q4.2: Should beam search come before MCTS?

Status: tentatively answered

Current recommendation:
Yes.

Reason:
Beam search is simpler to implement and debug, and it is a better first test of whether the tactic model is useful beyond one-step prediction.

## Symbolic Integration Questions

### Q5.1: What is the minimum viable truth-value interface?

Status: open

Why it matters:
Symbolic integration should start from a stable contract, not from model-specific code.

Next action:
Draft a small interface that maps predicted tactic confidence or state score into a symbolic confidence record.

### Q5.2: When should symbolic validation enter the loop?

Status: deferred

Reason:
This question becomes concrete only after search produces candidate proof traces worth validating.

## Evaluation Questions

### Q6.1: Which metric should define success for the first learning milestone?

Status: answered

Current answer:
Validation top-1 and top-5 tactic prediction accuracy.

Why:
That is the cleanest measure for the first supervised phase.

### Q6.2: What parser-quality metric should be reported with every dataset build?

Status: open

Recommendation:
Always report:

- number of rows attempted
- number of rows parsed successfully
- number of failures
- top failure categories

## Operational Questions

### Q7.1: How should cache versions be tracked?

Status: open

Why it matters:
If parser logic changes, old caches may become invalid without obvious signs.

Next action:
Add a manifest with parser version, vocab version, dataset split, and build timestamp.

### Q7.2: Where should generated artifacts live?

Status: partially answered

Current recommendation:
Use dedicated `artifacts/` and `runs/` directories rather than writing outputs into arbitrary working paths.

## What To Revisit Before Phase 2

Before starting search or RL, confirm the following:

- dataset preprocessing is stable
- tactic labels are versioned
- baseline metrics are reproducible
- graph exports are not the source of hidden errors
- LeanDojo replay works on selected examples

If those conditions are not met, the project is not ready for Phase 2 yet.
