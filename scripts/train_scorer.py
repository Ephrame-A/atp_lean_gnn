
"""Train the premise scoring head on top of a frozen or fine-tuned baseline model.

Usage::
    python scripts/train_scorer.py \\
        --config configs/pointer_graphsage_state.json \\
        --premise-config configs/premise_scoring.json \\
        --checkpoint runs/pointer_gnn/run_XXX/best.pt \\
        --index-path artifacts/lemmas/v1/index/lemma_index.faiss
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import torch
from torch.optim import AdamW

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

from atp_lean_gnn.lemma_index import LemmaIndex
from atp_lean_gnn.premise_scoring import PremiseScorer, PremiseScorerConfig
from atp_lean_gnn.premise_training import evaluate_model_with_premises, train_one_epoch_with_premises
from atp_lean_gnn.reporting import console_print
from atp_lean_gnn.training import build_dataloaders, load_baseline_config, load_prepared_metadata, build_model


def _create_run_dir(run_root: Path) -> Path:
    run_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = run_root / f"run_{timestamp}"
    suffix = 1
    while candidate.exists():
        candidate = run_root / f"run_{timestamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train Premise Scorer")
    parser.add_argument("--config", type=str, required=True, help="Path to baseline config")
    parser.add_argument("--premise-config", type=str, default="configs/premise_scoring.json", help="Path to premise scoring config")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to baseline checkpoint (best.pt)")
    parser.add_argument("--index-path", type=str, required=True, help="Path to FAISS index built from the baseline")
    parser.add_argument("--run-root", type=str, default="runs/premise_gnn", help="Directory to save run logs and checkpoints")
    parser.add_argument("--freeze-encoder", action="store_true", help="Freeze the GNN backbone and only train the scorer")
    args = parser.parse_args(argv)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"
    
    # Load configs
    config = load_baseline_config(Path(args.config))
    metadata = load_prepared_metadata(config.prepared_root)
    
    with open(args.premise_config, "r") as f:
        p_cfg_dict = json.load(f)
        p_config = PremiseScorerConfig(**p_cfg_dict)

    run_dir = _create_run_dir(Path(args.run_root))
    console_print(f"Saving run to {run_dir}")

    # Load Lemma Index
    console_print(f"Loading lemma index from {args.index_path}...")
    lemma_index = LemmaIndex.load(Path(args.index_path))

    # Build Dataloaders
    datasets, loaders = build_dataloaders(metadata, config)

    # Load baseline model and wrap it in TacticWithArgsClassifier
    from atp_lean_gnn.argument_selector import TacticWithArgsClassifier
    
    model = TacticWithArgsClassifier(
        num_node_labels=len(metadata.node_vocab),
        num_tactics=len(metadata.tactic_vocab),
        hidden_dim=config.model.hidden_dim,
        num_layers=config.model.num_layers,
        dropout=config.model.dropout,
        use_node_type=config.use_node_type,
        max_args=getattr(config, "max_args", 3),
    )
    
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    state_dict = ckpt["model_state_dict"] if "model_state_dict" in ckpt else ckpt
    
    # Adjust state dict keys if they come from a pure baseline (GraphSAGEStateClassifier)
    adjusted_state_dict = {}
    for k, v in state_dict.items():
        if not k.startswith("backbone.") and not k.startswith("tactic_embedding.") and not k.startswith("argument_selector."):
            adjusted_state_dict[f"backbone.{k}"] = v
        else:
            adjusted_state_dict[k] = v
            
    model.load_state_dict(adjusted_state_dict, strict=False)
    
    if args.freeze_encoder:
        console_print("Freezing GNN encoder...")
        for param in model.parameters():
            param.requires_grad = False
            
    model = model.to(device)

    # Build Premise Scorer
    scorer = PremiseScorer(hidden_dim=config.model.hidden_dim, mode=p_config.scoring_mode)
    scorer = scorer.to(device)

    optimizer = AdamW(
        [p for p in list(model.parameters()) + list(scorer.parameters()) if p.requires_grad],
        lr=config.training.learning_rate,
        weight_decay=config.training.weight_decay,
    )
    grad_scaler = torch.amp.GradScaler(device.type, enabled=use_amp)

    best_val_mrr = -1.0

    for epoch in range(1, config.training.epochs + 1):
        train_metrics = train_one_epoch_with_premises(
            model=model,
            scorer=scorer,
            loader=loaders["train"],
            lemma_index=lemma_index,
            optimizer=optimizer,
            grad_scaler=grad_scaler,
            device=device,
            grad_clip=config.training.grad_clip,
            unknown_tactic_id=metadata.unknown_tactic_id,
            arg_loss_weight=config.arg_loss_weight if hasattr(config, "arg_loss_weight") else 0.5,
            premise_loss_weight=p_config.premise_loss_weight,
            k=p_config.k,
            epoch=epoch,
            total_epochs=config.training.epochs,
            log_every_batches=config.training.log_every_batches,
            use_amp=use_amp,
            pin_memory=config.training.pin_memory,
        )

        val_metrics = evaluate_model_with_premises(
            model=model,
            scorer=scorer,
            loader=loaders["val"],
            lemma_index=lemma_index,
            device=device,
            unknown_tactic_id=metadata.unknown_tactic_id,
            arg_loss_weight=config.arg_loss_weight if hasattr(config, "arg_loss_weight") else 0.5,
            premise_loss_weight=p_config.premise_loss_weight,
            k=p_config.k,
            split_name="val",
            log_every_batches=config.training.log_every_batches,
            use_amp=use_amp,
            pin_memory=config.training.pin_memory,
        )

        console_print(
            f"Epoch {epoch} | Val MRR: {val_metrics['premise_mrr']:.4f} | "
            f"Hit@1: {val_metrics['premise_top1_accuracy']:.4f} | "
            f"Hit@5: {val_metrics['premise_top5_accuracy']:.4f} | "
            f"Recall: {val_metrics['premise_recall']:.4f}"
        )

        if val_metrics["premise_mrr"] > best_val_mrr:
            best_val_mrr = val_metrics["premise_mrr"]
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "scorer_state_dict": scorer.state_dict(),
                "val_metrics": val_metrics,
            }, run_dir / "best.pt")

    return 0


if __name__ == "__main__":
    sys.exit(main())
