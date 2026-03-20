"""
Compatibility entrypoint for the Lean proof-state graph toolkit.

The implementation now lives in the ``atp_lean_gnn`` package, but this file
keeps the original ``python main.py`` workflow working.
"""

from atp_lean_gnn import (
    DAGBuilder,
    DEMO_STATE,
    build_vocab,
    dag_to_dict,
    dag_to_pyg,
    parse_state,
    proof_state_to_dag,
    visualize_dag,
    write_dag_json,
)
from atp_lean_gnn.cli import main

__all__ = [
    "DAGBuilder",
    "DEMO_STATE",
    "build_vocab",
    "dag_to_dict",
    "dag_to_pyg",
    "main",
    "parse_state",
    "proof_state_to_dag",
    "visualize_dag",
    "write_dag_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
