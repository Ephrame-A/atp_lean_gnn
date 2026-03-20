# ATP Lean GNN

Toolkit for turning Lean proof states into shared DAGs that can be:

- inspected in the terminal
- visualized in the browser
- exported as JSON
- converted into PyTorch Geometric graphs for GNN experiments

## Project layout

The implementation now lives in the `atp_lean_gnn` package:

- `state.py`: parse Lean proof states into structured hypotheses and goals
- `parser.py`: tokenize and parse Lean-style expressions
- `graph.py`: build the shared DAG and compute graph statistics
- `pyg.py`: convert DAGs into PyG `Data` objects
- `visualize.py`: generate the interactive HTML visualization
- `dataset.py`: load examples from the LeanDojo dataset
- `reporting.py`: terminal-safe summaries and output helpers
- `cli.py`: command-line entrypoint

`main.py` remains as a thin compatibility wrapper, so `python main.py ...` still works.

## Common commands

Run the built-in demo:

```bash
python main.py --demo --no-viz
```

Load a custom proof state from a file and export the graph:

```bash
python -m atp_lean_gnn --state-file path/to/state.txt --json-out graph.json --no-viz
```

Inspect the PyG conversion with bidirectional edges:

```bash
python -m atp_lean_gnn --demo --pyg-summary --bidirectional --no-viz
```

## Documentation

The planning and architecture docs live in `docs/`:

- `docs/roadmap.md`
- `docs/architecture.md`
- `docs/open_questions.md`

## Why the DAG matters

The graph uses hash-consing, which means identical subexpressions are stored once and reused by multiple parents. That gives the GNN a better view of repeated mathematical structure than a plain tree.

## Current focus

This repo is now a cleaner foundation for the next steps in the project:

1. cache large batches of LeanDojo states as graphs
2. build tactic labels and training datasets
3. train a baseline GNN for next-tactic prediction
4. connect the graph pipeline to the larger hybrid GNN + symbolic prover plan
