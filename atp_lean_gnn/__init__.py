from .argument_selector import (
    ArgumentSelector,
    TacticWithArgsClassifier,
    TacticWithArgsConfig,
    compute_combined_loss,
    resolve_arg_targets_to_padded,
)
from .argument_training import (
    evaluate_model_with_args,
    train_one_epoch_with_args,
)
from .audit import DEFAULT_AUDIT_OUTPUT_ROOT, ParserAuditConfig, run_parser_audit
from .analysis import analyze_saved_run, compare_saved_runs, load_metrics_history, load_run_summary, render_run_comparison_markdown
from .cache import SplitReport, build_failure_record, build_json_payload
from .cli import DEMO_STATE
from .dataset import DatasetRow, iter_dataset_rows
from .graph import DAGBuilder, GraphNode, GraphStats, dag_to_dict, graph_stats, proof_state_to_dag, write_dag_json
from .labels import (
    DEFAULT_ARITY,
    EMPTY_TACTIC,
    TACTIC_ARITY,
    UNKNOWN_TACTIC,
    build_tactic_vocab,
    encode_tactic_name,
    get_tactic_arity,
    label_example,
    normalize_tactic,
    parse_tactic_arguments,
)
from .model import GraphSAGEClassifierConfig, GraphSAGEStateClassifier
from .preprocess import DEFAULT_OUTPUT_ROOT, PreprocessConfig, prepare_example, run_preprocessing
from .pyg import NODE_TYPE_TO_ID, build_premise_mask, build_vocab, build_vocab_from_labels, dag_to_pyg
from .preparation import PreparedExample, prepare_example
from .preprocess import DEFAULT_OUTPUT_ROOT, PreprocessConfig, run_preprocessing
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
    "ArgumentSelector",
    "BaselineConfig",
    "DAGBuilder",
    "DEFAULT_ARITY",
    "DEMO_STATE",
    "DEFAULT_AUDIT_OUTPUT_ROOT",
    "DEFAULT_BASELINE_CONFIG_PATH",
    "DEFAULT_OUTPUT_ROOT",
    "DEMO_STATE",
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
    "PreparedExample",
    "ProofState",
    "ParserAuditConfig",
    "PreprocessConfig",
    "TACTIC_ARITY",
    "TacticWithArgsClassifier",
    "TacticWithArgsConfig",
    "TrainingLoopConfig",
    "analyze_saved_run",
    "build_visualization_html",
    "build_dataloaders",
    "build_failure_record",
    "build_json_payload",
    "build_premise_mask",
    "build_tactic_vocab",
    "build_vocab",
    "build_vocab_from_labels",
    "compute_combined_loss",
    "compare_saved_runs",
    "compute_eval_metrics_from_logits",
    "dag_to_dict",
    "dag_to_pyg",
    "encode_tactic_name",
    "evaluate_baseline_run",
    "evaluate_model",
    "evaluate_model_with_args",
    "get_tactic_arity",
    "graph_stats",
    "iter_dataset_rows",
    "label_example",
    "load_metrics_history",
    "load_baseline_config",
    "load_prepared_metadata",
    "load_run_summary",
    "normalize_tactic",
    "parse_state",
    "parse_tactic_arguments",
    "prepare_example",
    "proof_state_to_dag",
    "resolve_arg_targets_to_padded",
    "render_run_comparison_markdown",
    "run_parser_audit",
    "run_preprocessing",
    "SplitReport",
    "train_baseline",
    "train_one_epoch_with_args",
    "UNKNOWN_TACTIC",
    "visualize_dag",
    "write_dag_json",
]

