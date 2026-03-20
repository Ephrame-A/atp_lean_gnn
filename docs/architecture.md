# Architecture Guide

## Purpose

This document explains the current architecture of the repository and the target architecture we want to grow into.

The main objective is to keep the project modular as it expands from graph construction into data preparation, supervised learning, search, and symbolic integration.

## Design Goals

- Small modules with single responsibilities
- Clear data contracts between stages
- Easy-to-test core logic
- Cheap reuse of cached artifacts
- Thin CLI and orchestration layers
- Future-proof interfaces for model and search code

## Current Module Layout

### `atp_lean_gnn/state.py`

Responsibility:
Parse raw Lean proof-state text into a structured `ProofState`.

Key objects:

- `Hypothesis`
- `ProofState`
- `parse_state(state: str) -> ProofState`

This module should remain free of graph or training concerns.

### `atp_lean_gnn/parser.py`

Responsibility:
Parse Lean-style expressions into graph nodes through the DAG builder interface.

Key objects:

- `tokenize`
- `ExprParser`

This module should stay focused on expression parsing, not proof-state orchestration.

### `atp_lean_gnn/graph.py`

Responsibility:
Build the shared DAG and compute graph-level statistics.

Key objects:

- `GraphNode`
- `GraphStats`
- `DAGBuilder`
- `proof_state_to_dag`
- `dag_to_dict`
- `write_dag_json`

This is the representation core of the project.

### `atp_lean_gnn/pyg.py`

Responsibility:
Map DAGs into PyTorch Geometric `Data` objects.

Key functions:

- `build_vocab`
- `dag_to_pyg`

This module is the boundary between symbolic structure and learned models.

### `atp_lean_gnn/visualize.py`

Responsibility:
Turn a DAG into an interactive HTML visualization.

Key functions:

- `build_visualization_html`
- `visualize_dag`

This should stay presentation-oriented and not become a general graph API.

### `atp_lean_gnn/dataset.py`

Responsibility:
Load rows from LeanDojo-backed datasets.

Key objects:

- `DatasetRow`
- `load_dataset_row`

This module should eventually support richer dataset utilities, but it should not contain training logic.

### `atp_lean_gnn/reporting.py`

Responsibility:
User-facing summaries and console-safe formatting.

This module exists so the rest of the system does not need to worry about terminal encoding and report formatting.

### `atp_lean_gnn/cli.py`

Responsibility:
Coordinate input source selection, graph building, export, and reporting.

Rule:
Keep the CLI thin. Business logic should live in reusable modules.

## Core Data Flow

The current pipeline is:

1. raw Lean proof-state text
2. `parse_state` produces `ProofState`
3. `ExprParser` plus `DAGBuilder` produces a shared DAG
4. one DAG can then be exported to:
   - JSON
   - HTML visualization
   - PyG `Data`

The future pipeline should be:

1. raw dataset rows
2. parsed proof states
3. DAG cache
4. label assignment
5. PyG dataset
6. GNN training and evaluation
7. LeanDojo execution and search
8. symbolic bridge and hybrid experiments

## Core Invariants

These invariants should stay stable unless there is a deliberate design change.

### Graph edges

Stored edge direction is:

`child_id -> parent_id`

This is the representation-level convention. Model code can add reverse edges at export time, but the stored DAG should keep this meaning consistent.

### Reused-node semantics

A reused node is a subexpression that is referenced by more than one parent.

Operationally:

- outgoing count from a node measures how many parents use it
- reused nodes are those with outgoing count greater than 1

### Parse once, export many

The proof state should be parsed and turned into a DAG once.
Every later representation should derive from the DAG rather than reparsing the original string repeatedly.

### CLI thinness

The CLI should coordinate work, not contain domain logic.

## Planned Module Additions

The next architecture expansion should add the following modules.

### `atp_lean_gnn/labels.py`

Purpose:
Normalize tactics and build label vocabularies.

### `atp_lean_gnn/cache.py`

Purpose:
Save and load cached graph artifacts, manifests, and vocabularies.

### `atp_lean_gnn/model.py`

Purpose:
Define the baseline GNN and related prediction heads.

### `atp_lean_gnn/training.py`

Purpose:
Contain reusable training loops, batching helpers, and evaluation utilities.

### `atp_lean_gnn/lean_env.py`

Purpose:
Wrap LeanDojo or related execution APIs for theorem replay and tactic application.

### `atp_lean_gnn/search.py`

Purpose:
Implement proof search strategies over predicted tactics and resulting states.

### `atp_lean_gnn/symbolic_bridge.py`

Purpose:
Map model outputs into symbolic confidence or truth-value structures.

## Recommended Repository Layout

Target structure for the next stage:

```text
atp_lean_gnn/
  __init__.py
  __main__.py
  cli.py
  state.py
  parser.py
  graph.py
  pyg.py
  dataset.py
  reporting.py
  visualize.py
  labels.py
  cache.py
  model.py
  training.py
  lean_env.py
  search.py
  symbolic_bridge.py
scripts/
  prepare_dataset.py
  train_baseline.py
  evaluate_baseline.py
docs/
  roadmap.md
  architecture.md
  open_questions.md
tests/
  ...
```

The package should hold reusable logic.
The `scripts` directory should hold thin workflow entrypoints.

## Artifact Layout

Once preprocessing and training begin, the project should adopt stable artifact directories.

Recommended structure:

```text
artifacts/
  graphs/
    train/
    val/
    test/
  vocab/
    node_vocab.json
    tactic_vocab.json
  manifests/
    dataset_manifest.json
runs/
  baseline_gnn/
    run_001/
      config.json
      metrics.json
      checkpoint.pt
      notes.md
```

This matters because the project will quickly become hard to reason about if generated outputs are scattered around the repository.

## Testing Strategy

Testing should be layered.

### Unit tests

Examples:

- proof-state parsing
- tokenizer behavior
- reused-node detection
- JSON export
- PyG export shape checks

### Integration tests

Examples:

- dataset row to DAG
- DAG to cached artifact
- cached artifact to model input

### Smoke tests

Examples:

- preprocess a small dataset sample
- run one training step
- replay one theorem in LeanDojo

## Extension Guidelines

### If adding parser support

- add the smallest change needed
- add regression tests with real proof-state examples
- avoid leaking parser-specific assumptions into unrelated modules

### If adding new exports

- derive from `DAGBuilder`
- keep export logic outside `graph.py` unless it is representation-neutral

### If adding model code

- depend on `pyg.py`, not on CLI helpers
- keep model definitions separate from training loops

### If adding search code

- depend on a stable theorem-execution interface
- do not call model internals directly from search logic when a prediction interface can be used instead

## Architectural Rule of Thumb

Whenever a new feature is proposed, ask:

1. Is this representation logic?
2. Is this export logic?
3. Is this training logic?
4. Is this orchestration logic?

If a file starts answering too many of those at once, it is becoming the next monolith.
