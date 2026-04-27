from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

import torch

from atp_lean_gnn import DatasetRow, build_tactic_vocab, encode_tactic_name, label_example
from atp_lean_gnn.ablations import load_ablation_suite_config, run_ablation_suite
from atp_lean_gnn.analysis import compare_saved_runs, render_run_comparison_markdown
from atp_lean_gnn.cache import SplitReport, prepare_output_root, write_manifest, write_pyg_artifact, write_vocab
from atp_lean_gnn.graph import proof_state_to_dag
from atp_lean_gnn.pyg import build_vocab_from_labels, dag_to_pyg


class AblationSuiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prepared_root = Path("tests") / "_tmp_prepared_ablation"
        self.workspace_root = Path("tests") / "_tmp_ablation_workspace"
        for path in (self.prepared_root, self.workspace_root):
            if path.exists():
                shutil.rmtree(path)
        self._build_fake_prepared_root()
        self.base_config_path = self.workspace_root / "base_config.json"
        self.suite_config_path = self.workspace_root / "suite_config.json"
        self._write_base_config()
        self._write_suite_config()

    def tearDown(self) -> None:
        for path in (self.prepared_root, self.workspace_root):
            if path.exists():
                shutil.rmtree(path)

    def _split_rows(self) -> dict[str, list[DatasetRow]]:
        return {
            "train": [
                DatasetRow(
                    state="n : Nat\n|- Even n",
                    theorem="demo.train.even",
                    tactic="simp only [h1]",
                    split="train",
                    row_index=0,
                    dataset_name="fake/dataset",
                ),
                DatasetRow(
                    state="State : Nat\n|- State = State",
                    theorem="demo.train.eq",
                    tactic="rw [foo]",
                    split="train",
                    row_index=1,
                    dataset_name="fake/dataset",
                ),
            ],
            "val": [
                DatasetRow(
                    state="m : Nat\n|- Even m",
                    theorem="demo.val.known",
                    tactic="simp",
                    split="val",
                    row_index=0,
                    dataset_name="fake/dataset",
                ),
                DatasetRow(
                    state="y : Nat\n|- y = y",
                    theorem="demo.val.unknown",
                    tactic="aesop?",
                    split="val",
                    row_index=1,
                    dataset_name="fake/dataset",
                ),
            ],
            "test": [
                DatasetRow(
                    state="z : Nat\n|- z = z",
                    theorem="demo.test.known",
                    tactic="rw",
                    split="test",
                    row_index=0,
                    dataset_name="fake/dataset",
                )
            ],
        }

    def _build_fake_prepared_root(self) -> None:
        split_rows = self._split_rows()
        prepare_output_root(self.prepared_root, splits=["train", "val", "test"], force=True)

        node_labels: set[str] = set()
        train_tactic_names: list[str] = []
        dags_by_split: dict[str, list[tuple[DatasetRow, object, str]]] = {
            "train": [],
            "val": [],
            "test": [],
        }

        for split, rows in split_rows.items():
            for row in rows:
                dag = proof_state_to_dag(row.state)
                tactic_name = str(label_example(row.tactic)["tactic_name"])
                dags_by_split[split].append((row, dag, tactic_name))
                if split == "train":
                    node_labels.update(node.label for node in dag.nodes)
                    train_tactic_names.append(tactic_name)

        node_vocab = build_vocab_from_labels(node_labels)
        tactic_vocab = build_tactic_vocab(train_tactic_names)
        write_vocab(self.prepared_root, name="node_vocab.json", vocab=node_vocab)
        write_vocab(self.prepared_root, name="tactic_vocab.json", vocab=tactic_vocab)

        for split in ("train", "val", "test"):
            report = SplitReport(split=split)
            for row, dag, tactic_name in dags_by_split[split]:
                data = dag_to_pyg(dag, node_vocab)
                data.y = torch.tensor(
                    [encode_tactic_name(tactic_name, tactic_vocab)],
                    dtype=torch.long,
                )
                data.split = split
                data.row_index = row.row_index
                data.dataset_name = row.dataset_name
                data.theorem = row.theorem
                data.tactic_raw = row.tactic
                data.tactic_name = tactic_name
                write_pyg_artifact(
                    self.prepared_root,
                    split=split,
                    row_index=row.row_index,
                    data=data,
                )
                report.record_success(dag=dag, tactic_name=tactic_name)

            manifest = report.to_manifest(
                dataset_name="fake/dataset",
                output_root=self.prepared_root,
                vocab_source="train",
                sample_limit=None,
            )
            write_manifest(self.prepared_root, split=split, manifest=manifest)

    def _write_base_config(self) -> None:
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "prepared_root": str(self.prepared_root),
            "run_root": str(self.workspace_root / "unused_run_root"),
            "seed": 42,
            "device": "cpu",
            "edge_mode": "bidirectional",
            "use_node_type": True,
            "model": {
                "hidden_dim": 16,
                "num_layers": 2,
                "dropout": 0.1,
                "readout": "state",
            },
            "training": {
                "batch_size": 2,
                "epochs": 1,
                "learning_rate": 0.001,
                "weight_decay": 0.0001,
                "grad_clip": 1.0,
                "log_every_batches": 1,
                "num_workers": 0,
                "pin_memory": False,
                "persistent_workers": False,
                "prefetch_factor": 2,
                "use_amp": False,
            },
        }
        self.base_config_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def _write_suite_config(
        self,
        *,
        base_config_path: Path | None = None,
        variants: list[dict[str, object]] | None = None,
    ) -> None:
        payload = {
            "suite_name": "issue4_test_suite",
            "base_config": str(base_config_path or self.base_config_path),
            "output_root": str(self.workspace_root / "runs"),
            "seeds": [13],
            "variants": variants
            or [
                {
                    "name": "baseline",
                    "description": "Reference baseline.",
                    "overrides": {
                        "edge_mode": "bidirectional",
                        "use_node_type": True,
                        "model": {"readout": "state"},
                    },
                },
                {
                    "name": "forward_edges",
                    "description": "Forward edges only.",
                    "overrides": {"edge_mode": "forward"},
                },
                {
                    "name": "mean_pool",
                    "description": "Mean pooling.",
                    "overrides": {"model": {"readout": "mean"}},
                },
                {
                    "name": "no_node_type",
                    "description": "Disable node types.",
                    "overrides": {"use_node_type": False},
                },
            ],
        }
        self.suite_config_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def test_load_suite_config_rejects_duplicate_variants(self) -> None:
        self._write_suite_config(
            variants=[
                {
                    "name": "baseline",
                    "description": "Reference baseline.",
                    "overrides": {},
                },
                {
                    "name": "baseline",
                    "description": "Duplicate baseline.",
                    "overrides": {"edge_mode": "forward"},
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "duplicate 'baseline'"):
            load_ablation_suite_config(self.suite_config_path)

    def test_load_suite_config_rejects_missing_base_config(self) -> None:
        missing_base_config = self.workspace_root / "missing_base_config.json"
        self._write_suite_config(base_config_path=missing_base_config)

        with self.assertRaisesRegex(FileNotFoundError, "does not exist"):
            load_ablation_suite_config(self.suite_config_path)

    def test_run_ablation_suite_writes_index_summary_and_compare_data(self) -> None:
        summary = run_ablation_suite(self.suite_config_path)
        suite_root = Path(str(summary["suite_root"]))
        run_index_path = suite_root / "run_index.json"
        suite_summary_path = suite_root / "suite_summary.json"
        suite_markdown_path = suite_root / "suite_summary.md"

        self.assertTrue(run_index_path.exists())
        self.assertTrue(suite_summary_path.exists())
        self.assertTrue(suite_markdown_path.exists())

        run_index = json.loads(run_index_path.read_text(encoding="utf-8"))
        self.assertEqual(len(run_index["entries"]), 4)
        self.assertEqual(int(summary["expected_run_count"]), 4)
        self.assertEqual(int(summary["completed_run_count"]), 4)
        self.assertEqual(len(summary["missing_runs"]), 0)
        self.assertEqual(len(summary["raw_run_records"]), 4)
        self.assertEqual(len(summary["variant_summaries"]), 4)

        run_dirs = [str(entry["run_dir"]) for entry in run_index["entries"]]
        comparison = compare_saved_runs(run_dirs)
        self.assertEqual(len(comparison["runs"]), 4)
        self.assertTrue(all("readout" in item for item in comparison["runs"]))
        self.assertIn("state", {str(item["readout"]) for item in comparison["runs"]})
        self.assertIn("mean", {str(item["readout"]) for item in comparison["runs"]})
        self.assertIn("Readout", render_run_comparison_markdown(comparison))

        markdown = suite_markdown_path.read_text(encoding="utf-8")
        self.assertIn("Variant Summary", markdown)
        self.assertIn("Readout", markdown)
        self.assertIn("official baseline to beat", markdown.lower())

    def test_run_single_variant_and_compare_only(self) -> None:
        first_summary = run_ablation_suite(self.suite_config_path, variant="baseline")
        second_summary = run_ablation_suite(self.suite_config_path, compare_only=True)
        suite_root = Path(str(first_summary["suite_root"]))
        run_index = json.loads((suite_root / "run_index.json").read_text(encoding="utf-8"))

        self.assertEqual(int(first_summary["completed_run_count"]), 1)
        self.assertEqual(int(second_summary["completed_run_count"]), 1)
        self.assertEqual(len(run_index["entries"]), 1)
        self.assertEqual(str(run_index["entries"][0]["variant"]), "baseline")


if __name__ == "__main__":
    unittest.main()
