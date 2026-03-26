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

Prepare cached dataset artifacts from LeanDojo:

```bash
python scripts/prepare_dataset.py --sample-per-split 100 --output-root artifacts/prepared/v1 --force
```

Train the baseline GraphSAGE classifier from a prepared cache:

```bash
python scripts/train_baseline.py --config configs/baseline_graphsage_state.json
```

Resume an interrupted run from its existing `last.pt` checkpoint:

```bash
python scripts/train_baseline.py --resume-run-dir runs/baseline_gnn/run_YYYYMMDD_HHMMSS
```

Evaluate the best saved checkpoint for a completed run:

```bash
python scripts/evaluate_baseline.py --run-dir runs/baseline_gnn/run_YYYYMMDD_HHMMSS --split test
```

Generate detailed error-analysis artifacts for a finished run:

```bash
python scripts/analyze_run.py --run-dir runs/baseline_gnn/run_YYYYMMDD_HHMMSS --split both
```

Compare multiple finished runs side by side:

```bash
python scripts/compare_runs.py runs/baseline_gnn/run_A runs/baseline_gnn/run_B
```

## Documentation

The planning and architecture docs live in `docs/`:

- `docs/roadmap.md`
- `docs/architecture.md`
- `docs/open_questions.md`
- `docs/lean_for_atp.md`
- `docs/issue_backlog.md`
- `docs/github_issue_specs.md`

## Why the DAG matters

The graph uses hash-consing, which means identical subexpressions are stored once and reused by multiple parents. That gives the GNN a better view of repeated mathematical structure than a plain tree.

## Current focus

This repo is now a cleaner foundation for the next steps in the project:

1. cache large batches of LeanDojo states as graphs
2. build tactic labels and training datasets
3. train a baseline GNN for next-tactic prediction
4. connect the graph pipeline to the larger hybrid GNN + symbolic prover plan

## Training artifacts

The baseline training flow expects a prepared cache under `artifacts/prepared/...` and writes run outputs under `runs/baseline_gnn/...`:

```text
runs/
  baseline_gnn/
    run_<timestamp>/
      config.json
      metrics.jsonl
      best.pt
      last.pt
      summary.json
      eval_val.json
      eval_test.json
      analysis_val.json
      analysis_val.md
      analysis_test.json
      analysis_test.md
      predictions_val.jsonl
      predictions_test.jsonl
```

The baseline config also exposes data-loading and runtime knobs that matter for GPU utilization:

- `training.num_workers`
- `training.pin_memory`
- `training.persistent_workers`
- `training.prefetch_factor`
- `training.use_amp`
