#!/usr/bin/env python3
"""Run tactic inference on a single proof state interactively."""

import argparse
import sys
from pathlib import Path

import torch

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

from atp_lean_gnn.cli import DEMO_STATE
from atp_lean_gnn.inference import InferencePipeline
from atp_lean_gnn.lemma_index import LemmaIndex
from atp_lean_gnn.training import load_prepared_metadata, load_baseline_config
from atp_lean_gnn.model import build_model
from atp_lean_gnn.premise_scoring import PremiseScorer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactive Tactic Inference")
    parser.add_argument("--config", type=str, required=True, help="Path to config.json (e.g. from runs/baseline_gnn/run_*/config.json)")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to best.pt checkpoint")
    parser.add_argument("--scorer-mode", type=str, default="dot", choices=["dot", "mlp"], help="Scorer mode")
    parser.add_argument("--index-path", type=str, help="Path to FAISS index. If missing, retrieval will return nothing.")
    parser.add_argument("--k", type=int, default=500, help="Number of lemmas to retrieve")
    parser.add_argument("--state", type=str, default=DEMO_STATE, help="Raw Lean proof state string")
    args = parser.parse_args(argv)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading on {device}...")

    # Load baseline config and metadata
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}")
        return 1

    config = load_baseline_config(config_path)
    metadata = load_prepared_metadata(config.prepared_root)

    # Build and load model
    model = build_model(metadata, config)
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    
    # Check if the checkpoint contains a full model or just the state dict
    if "model_state_dict" in ckpt:
        # Checkpoint from our custom training loop
        # It might be a TacticWithArgsClassifier or GraphSAGEStateClassifier
        # We handle this by loading into whatever build_model returned.
        # But wait, build_model returns TacticWithArgsClassifier if config.model_type == "pointer",
        # else GraphSAGEStateClassifier.
        model.load_state_dict(ckpt["model_state_dict"])
    else:
        # Bare state dict
        model.load_state_dict(ckpt)
    
    model = model.to(device)

    # Build scorer (using randomly initialized weights for demo if not loaded)
    scorer = PremiseScorer(hidden_dim=config.model.hidden_dim, mode=args.scorer_mode).to(device)
    
    # Load index if provided
    lemma_index = None
    if args.index_path:
        index_path = Path(args.index_path)
        if index_path.exists():
            lemma_index = LemmaIndex.load(index_path)
            print(f"Loaded index with {len(lemma_index)} lemmas.")
        else:
            print(f"WARNING: index path {index_path} not found.")
            
    if lemma_index is None:
        # Create an empty index as fallback
        from atp_lean_gnn.lemma_index import LemmaIndexConfig
        lemma_index = LemmaIndex(LemmaIndexConfig(hidden_dim=config.model.hidden_dim))

    # Initialize Pipeline
    pipeline = InferencePipeline(
        model=model,
        scorer=scorer,
        lemma_index=lemma_index,
        node_vocab=metadata.node_vocab,
        tactic_vocab=metadata.tactic_vocab,
        device=device,
        k=args.k,
    )

    print("\n--- Input State ---")
    print(args.state)
    print("-------------------\n")

    prediction = pipeline.predict_tactic(args.state)
    
    print(f"Predicted Tactic:  \033[1;32m{prediction}\033[0m")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
