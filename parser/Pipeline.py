"""
pipeline.py
-----------
Main atomization pipeline.

Takes LeanDojo Benchmark data (JSON files) and produces a dataset of
AtomicStep records suitable for training a GNN-based tactic prediction model.

Pipeline stages:
  1. Load LeanDojo benchmark records
  2. For each (state_before, tactic, premises) triple:
       a. Apply string-based atomization (fast, offline, ~95% coverage)
       b. Optionally refine with live Pantograph replay (for compound tactics)
  3. Compute ExprGraph structures from goal states
  4. Write output dataset as JSON / PyTorch Geometric Data objects

Usage:
    python pipeline.py \
        --data_dir  /path/to/leandojo_benchmark_4/random \
        --split     train \
        --out_dir   ./atomized_data \
        --live      False          # set True for Pantograph refinement
"""

from __future__ import annotations
import json
import argparse
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Iterable

# Add repo root to path so we can import atp_lean_gnn
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from atp_lean_gnn.dataset import get_dataset_stream, DATASET_NAME
from atomic_tactics import (
    AtomicStep, AtomicTacticKind,
    atomize_tactic_string,
    LeanExpr, ExprKind,
)
from expr_graph import build_expr_graph, ExprGraph, expr_graph_to_pyg


# ──────────────────────────────────────────────────────────────────────────────
# 1.  LeanDojo data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TacticRecord:
    """One (state_before, tactic, state_after, premises) record from LeanDojo."""
    state_before: str
    tactic:       str
    state_after:  str
    premises:     list[str] = field(default_factory=list)

@dataclass
class TheoremRecord:
    """One theorem with all its tactics."""
    name:                 str
    file:                 str
    split:                str
    tactics:              list[TacticRecord] = field(default_factory=list)
    accessible_premises:  list[str]          = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# 2.  HuggingFace Parquet loader (replaces old LeanDojo JSON loader)
# ──────────────────────────────────────────────────────────────────────────────

def stream_dataset_split(
    split: str,
    dataset_name: str = DATASET_NAME,
    sample_limit: Optional[int] = None,
) -> Iterable[TheoremRecord]:
    """
    Stream theorems from the HuggingFace Parquet dataset.
    
    The Parquet format is already flattened: each row is a single
    (state_before, tactic, theorem_name) triple. We group them by
    theorem to reconstruct the nested TheoremRecord structure.
    
    Args:
        split: "train", "val", or "test"
        dataset_name: HuggingFace dataset identifier
        sample_limit: Max rows to read (for testing)
    
    Yields:
        TheoremRecord objects (one per theorem)
    """
    theorems_dict: dict[str, TheoremRecord] = {}
    row_count = 0
    
    for row in get_dataset_stream(dataset_name, split=split):
        if sample_limit and row_count >= sample_limit:
            break
        row_count += 1
        
        # Extract fields from the Parquet row
        theorem_name = row.get("full_name", "unknown")
        state_before = row.get("state", "")
        tactic_str = row.get("tactic", "")
        file_path = row.get("file_path", "?")
        
        # Create a TacticRecord for this row
        tactic_record = TacticRecord(
            state_before=state_before,
            tactic=tactic_str,
            state_after="",  # Not available in Parquet (not needed for atomization)
            premises=[],  # Not in this format (could extract from <a> tags if needed)
        )
        
        # Group tactics by theorem name
        if theorem_name not in theorems_dict:
            theorems_dict[theorem_name] = TheoremRecord(
                name=theorem_name,
                file=file_path,
                split=split,
                tactics=[],
            )
        
        theorems_dict[theorem_name].tactics.append(tactic_record)
    
    # Yield all accumulated theorems
    for theorem_record in theorems_dict.values():
        yield theorem_record


def load_leandojo_split(data_dir: str, split: str) -> list[TheoremRecord]:
    """
    Load theorems from HuggingFace Parquet dataset (replaces old JSON loader).
    
    The `data_dir` parameter is now ignored (kept for backward compatibility).
    Data is streamed from the HuggingFace cat-searcher/leandojo-benchmark-4-random dataset.
    
    Args:
        data_dir: Ignored (kept for API compatibility)
        split: "train", "val", or "test"
    
    Returns:
        List of TheoremRecord objects
    """
    return list(stream_dataset_split(split))


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Per-theorem atomization
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AtomizedTheoremRecord:
    """Fully atomized training data for one theorem."""
    theorem_name: str
    file:         str
    split:        str
    steps:        list[dict]          # serialized AtomicStep dicts
    graphs:       list[Optional[dict]] = field(default_factory=list)  # ExprGraph dicts


def atomize_theorem(
    record: TheoremRecord,
    use_live_pantograph: bool = False,
    pantograph_session=None,
) -> AtomizedTheoremRecord:
    """
    Atomize all tactics of one theorem into AtomicStep sequences.

    For each tactic record:
      1. Run string-based atomizer (always)
      2. If use_live_pantograph and session provided, refine compound tactics
      3. Build ExprGraph from goal state string
    """
    all_steps: list[AtomicStep] = []
    all_graphs: list[Optional[ExprGraph]] = []

    for tac_rec in record.tactics:
        # Skip empty tactics
        if not tac_rec.tactic.strip():
            continue

        # String-based atomization (fast path)
        steps = atomize_tactic_string(
            tactic_str=tac_rec.tactic,
            goal_state_str=tac_rec.state_before,
            theorem_name=record.name,
        )

        # Attach premise information to steps that use premises
        if tac_rec.premises:
            # If the tactic uses known premises, annotate the first APPLY/EXACT
            for i, step in enumerate(steps):
                if step.tactic in (AtomicTacticKind.APPLY, AtomicTacticKind.EXACT):
                    if step.argument and step.argument in ("?", "simp"):
                        step.argument = tac_rec.premises[0] if tac_rec.premises else step.argument
                    break

        # Build ExprGraph for the goal state
        graph = build_expr_graph_from_state_string(tac_rec.state_before)
        for step in steps:
            all_steps.append(step)
            all_graphs.append(graph)

    # Serialise to plain dicts for JSON output
    step_dicts = []
    for step in all_steps:
        step_dicts.append({
            "tactic":          step.tactic.value,
            "argument":        step.argument,
            "goal_state_str":  step.goal_state_str,
            "new_goal_count":  step.new_goal_count,
            "source_tactic":   step.source_tactic,
            "theorem_name":    step.theorem_name,
        })

    graph_dicts = []
    for g in all_graphs:
        if g is not None:
            graph_dicts.append({
                "nodes": g.nodes,
                "edges": g.edges,
                "node_features": g.node_features,
            })
        else:
            graph_dicts.append(None)

    return AtomizedTheoremRecord(
        theorem_name=record.name,
        file=record.file,
        split=record.split,
        steps=step_dicts,
        graphs=graph_dicts,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4.  ExprGraph builder from goal state strings
# ──────────────────────────────────────────────────────────────────────────────

def build_expr_graph_from_state_string(state_str: str) -> "ExprGraph":
    """
    Build an ExprGraph from a Pantograph goal state string like:
      "k : ℕ\n⊢ gcd ((k + 1) % (k + 1)) (k + 1) = k + 1"

    Since we only have the string (not the kernel expr), we parse it
    with a lightweight symbolic parser and build an approximate graph.
    The full graph requires live Pantograph; this gives a useful approximation.
    """
    from expr_graph import build_expr_graph
    goal_type = _extract_goal_from_state_string(state_str)
    context   = _extract_context_from_state_string(state_str)
    return build_expr_graph(goal_type, context)


def _extract_goal_from_state_string(state_str: str) -> str:
    """Extract the goal (after ⊢) from a state string."""
    for line in reversed(state_str.split("\n")):
        line = line.strip()
        if line.startswith("⊢"):
            return line[1:].strip()
        if line.startswith("|-"):
            return line[2:].strip()
    return state_str.strip()


def _extract_context_from_state_string(state_str: str) -> list[tuple[str, str]]:
    """
    Extract context hypothesis (name, type) pairs from a state string.
    Lines before ⊢ of the form  "x : T".
    """
    context = []
    lines = state_str.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("⊢") or line.startswith("|-"):
            break
        if " : " in line:
            parts = line.split(" : ", 1)
            context.append((parts[0].strip(), parts[1].strip()))
    return context


# ──────────────────────────────────────────────────────────────────────────────
# 5.  Full pipeline runner
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    data_dir:            str,
    split:               str,
    out_dir:             str,
    use_live_pantograph: bool = False,
    mathlib_path:        Optional[str] = None,
    max_theorems:        Optional[int] = None,
    verbose:             bool = True,
) -> None:
    """
    Full atomization pipeline.

    Args:
        data_dir:            Path to LeanDojo benchmark root.
        split:               One of "train", "val", "test".
        out_dir:             Where to write atomized JSON output.
        use_live_pantograph: If True, spawn a Pantograph process for
                             kernel-level expression trees. Requires
                             PyPantograph + Lean 4 + Mathlib installed.
        mathlib_path:        Path to Mathlib build (for Pantograph).
        max_theorems:        Cap the number of theorems (for testing).
        verbose:             Print progress.
    """
    os.makedirs(out_dir, exist_ok=True)
    out_path = Path(out_dir) / f"{split}_atomized.json"

    if verbose:
        print(f"Loading LeanDojo split: {split} from {data_dir}")

    theorems = load_leandojo_split(data_dir, split)
    if max_theorems:
        theorems = theorems[:max_theorems]

    if verbose:
        print(f"Loaded {len(theorems)} theorems")

    # Optionally start Pantograph
    session = None
    if use_live_pantograph:
        if verbose:
            print("Starting Pantograph session...")
        try:
            from pantograph_bridge import PantographSession
            imports = ["Mathlib"] if mathlib_path else ["Init"]
            session = PantographSession.from_imports(imports)
            if verbose:
                print("Pantograph session ready")
        except Exception as e:
            print(f"Warning: Could not start Pantograph: {e}")
            print("Falling back to string-based atomization only.")

    # Atomize
    all_records: list[dict] = []
    n_steps_total = 0

    for i, theorem in enumerate(theorems):
        if verbose and i % 500 == 0:
            print(f"  [{i}/{len(theorems)}] {theorem.name} ...")

        try:
            atomized = atomize_theorem(
                theorem,
                use_live_pantograph=use_live_pantograph,
                pantograph_session=session,
            )
            n_steps_total += len(atomized.steps)
            all_records.append({
                "theorem_name": atomized.theorem_name,
                "file":         atomized.file,
                "split":        atomized.split,
                "steps":        atomized.steps,
                "graphs":       atomized.graphs,
            })
        except Exception as e:
            if verbose:
                print(f"  Warning: failed to atomize {theorem.name}: {e}")
            continue

    # Write output
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\nDone!")
        print(f"  Theorems processed:  {len(all_records)}")
        print(f"  Total atomic steps:  {n_steps_total}")
        print(f"  Output:              {out_path}")

    # Write vocabulary (tactic label set)
    vocab_path = Path(out_dir) / "tactic_vocab.json"
    write_vocabulary(all_records, vocab_path)
    if verbose:
        print(f"  Tactic vocabulary:   {vocab_path}")


def write_vocabulary(records: list[dict], out_path: Path) -> None:
    """Build and save the finite tactic vocabulary (label set for classification)."""
    tactic_counts: dict[str, int] = {}
    arg_counts: dict[str, int] = {}

    for rec in records:
        for step in rec.get("steps", []):
            tac = step.get("tactic", "")
            tactic_counts[tac] = tactic_counts.get(tac, 0) + 1
            arg = step.get("argument")
            if arg:
                # Only count non-compound args as vocabulary items
                if len(arg) < 80 and not arg.startswith("simp[") and "by " not in arg:
                    arg_counts[arg] = arg_counts.get(arg, 0) + 1

    # Tactic class labels (the finite set — this IS the finite action space)
    tactic_to_id = {tac: i for i, tac in enumerate(sorted(tactic_counts.keys()))}

    # Argument vocabulary (top-N for GNN node selection)
    top_args = sorted(arg_counts.items(), key=lambda x: -x[1])[:50000]
    arg_to_id = {arg: i for i, (arg, _) in enumerate(top_args)}

    vocab = {
        "tactic_to_id":  tactic_to_id,
        "id_to_tactic":  {v: k for k, v in tactic_to_id.items()},
        "arg_to_id":     arg_to_id,
        "tactic_counts": tactic_counts,
        "n_tactic_classes": len(tactic_to_id),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# 6.  CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atomize LeanDojo benchmark data")
    parser.add_argument("--data_dir",  required=True,
                        help="Path to LeanDojo benchmark directory (containing random/ or novel_premises/)")
    parser.add_argument("--split",     default="train",
                        choices=["train", "val", "test"],
                        help="Which split to process")
    parser.add_argument("--split_kind", default="random",
                        choices=["random", "novel_premises"],
                        help="LeanDojo split kind")
    parser.add_argument("--out_dir",   required=True,
                        help="Output directory for atomized data")
    parser.add_argument("--live",      action="store_true",
                        help="Use live Pantograph for kernel-level expression trees")
    parser.add_argument("--mathlib",   default=None,
                        help="Path to Mathlib (required for --live)")
    parser.add_argument("--max",       type=int, default=None,
                        help="Max theorems to process (for debugging)")
    parser.add_argument("--quiet",     action="store_true")
    args = parser.parse_args()

    # data_dir should point to the split kind subdirectory
    full_data_dir = os.path.join(args.data_dir, args.split_kind)
    if not os.path.exists(full_data_dir):
        full_data_dir = args.data_dir  # might already point to it

    run_pipeline(
        data_dir=full_data_dir,
        split=args.split,
        out_dir=args.out_dir,
        use_live_pantograph=args.live,
        mathlib_path=args.mathlib,
        max_theorems=args.max,
        verbose=not args.quiet,
    )