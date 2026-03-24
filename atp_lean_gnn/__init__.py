from .analysis import analyze_saved_run, compare_saved_runs, load_metrics_history, load_run_summary, render_run_comparison_markdown
from .cache import SplitReport, build_failure_record, build_json_payload
from .cli import DEMO_STATE
from .dataset import DatasetRow, iter_dataset_rows
from .graph import DAGBuilder, GraphNode, GraphStats, dag_to_dict, graph_stats, proof_state_to_dag, write_dag_json
from .labels import EMPTY_TACTIC, UNKNOWN_TACTIC, build_tactic_vocab, encode_tactic_name, label_example, normalize_tactic
from .model import GraphSAGEClassifierConfig, GraphSAGEStateClassifier
from .preprocess import DEFAULT_OUTPUT_ROOT, PreprocessConfig, prepare_example, run_preprocessing
from .pyg import NODE_TYPE_TO_ID, build_vocab, build_vocab_from_labels, dag_to_pyg
from .state import Hypothesis, ProofState, parse_state
from .training import (
    DEFAULT_BASELINE_CONFIG_PATH,
    BaselineConfig,
    PreparedGraphDataset,
    PreparedMetadata,
    TrainingLoopConfig,
    build_dataloaders,
    compute_eval_metrics_from_logits,
    evaluate_baseline_run,
    evaluate_model,
    load_baseline_config,
    load_prepared_metadata,
    train_baseline,
)
from .visualize import build_visualization_html, visualize_dag

__all__ = [
    "BaselineConfig",
    "DAGBuilder",
    "DEMO_STATE",
    "DEFAULT_BASELINE_CONFIG_PATH",
    "DEFAULT_OUTPUT_ROOT",
    "DatasetRow",
    "EMPTY_TACTIC",
    "GraphNode",
    "GraphSAGEClassifierConfig",
    "GraphSAGEStateClassifier",
    "GraphStats",
    "Hypothesis",
    "NODE_TYPE_TO_ID",
    "PreparedGraphDataset",
    "PreparedMetadata",
    "ProofState",
    "PreprocessConfig",
    "TrainingLoopConfig",
    "analyze_saved_run",
    "build_visualization_html",
    "build_dataloaders",
    "build_failure_record",
    "build_vocab",
    "build_vocab_from_labels",
    "build_json_payload",
    "build_tactic_vocab",
    "compare_saved_runs",
    "compute_eval_metrics_from_logits",
    "dag_to_dict",
    "dag_to_pyg",
    "encode_tactic_name",
    "evaluate_baseline_run",
    "evaluate_model",
    "graph_stats",
    "iter_dataset_rows",
    "label_example",
    "load_metrics_history",
    "load_baseline_config",
    "load_prepared_metadata",
    "load_run_summary",
    "normalize_tactic",
    "parse_state",
    "prepare_example",
    "proof_state_to_dag",
    "render_run_comparison_markdown",
    "run_preprocessing",
    "SplitReport",
    "train_baseline",
    "UNKNOWN_TACTIC",
    "visualize_dag",
    "write_dag_json",
]
