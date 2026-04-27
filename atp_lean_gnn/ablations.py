from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from .analysis import compare_saved_runs
from .reporting import console_print
from .training import BaselineConfig, train_baseline


DEFAULT_ABLATION_SUITE_CONFIG_PATH = Path("configs") / "ablations" / "issue4_suite.json"
DEFAULT_ABLATION_OUTPUT_ROOT = Path("runs") / "ablations"
NEUTRAL_DELTA_THRESHOLD = 0.005


@dataclass(frozen=True)
class AblationVariant:
    name: str
    description: str
    overrides: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "overrides": self.overrides,
        }


@dataclass(frozen=True)
class AblationSuiteConfig:
    suite_name: str
    base_config: Path
    output_root: Path
    seeds: tuple[int, ...]
    variants: tuple[AblationVariant, ...]

    @property
    def suite_root(self) -> Path:
        return self.output_root / self.suite_name

    def to_dict(self) -> dict[str, object]:
        return {
            "suite_name": self.suite_name,
            "base_config": str(self.base_config),
            "output_root": str(self.output_root),
            "seeds": list(self.seeds),
            "variants": [variant.to_dict() for variant in self.variants],
        }


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _resolve_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_ablation_suite_config(
    suite_config_path: str | Path = DEFAULT_ABLATION_SUITE_CONFIG_PATH,
) -> AblationSuiteConfig:
    config_path = _resolve_path(suite_config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Ablation suite config '{config_path}' does not exist.")

    payload = _read_json(config_path)
    suite_name = str(payload.get("suite_name", "")).strip()
    if not suite_name:
        raise ValueError("Ablation suite config must define a non-empty 'suite_name'.")

    raw_base_config = payload.get("base_config")
    if not raw_base_config:
        raise ValueError("Ablation suite config is missing the required 'base_config' field.")
    base_config = _resolve_path(str(raw_base_config))
    if not base_config.exists():
        raise FileNotFoundError(f"Ablation suite base config '{base_config}' does not exist.")

    output_root = _resolve_path(str(payload.get("output_root", DEFAULT_ABLATION_OUTPUT_ROOT)))

    raw_seeds = payload.get("seeds", [42])
    if not isinstance(raw_seeds, list) or not raw_seeds:
        raise ValueError("Ablation suite config field 'seeds' must be a non-empty list.")
    seeds = tuple(int(seed) for seed in raw_seeds)
    if any(seed < 0 for seed in seeds):
        raise ValueError("Ablation suite seeds must be non-negative integers.")
    if len(set(seeds)) != len(seeds):
        raise ValueError("Ablation suite seeds must not contain duplicates.")

    raw_variants = payload.get("variants", [])
    if not isinstance(raw_variants, list) or not raw_variants:
        raise ValueError("Ablation suite config field 'variants' must be a non-empty list.")

    variants: list[AblationVariant] = []
    seen_names: set[str] = set()
    for item in raw_variants:
        if not isinstance(item, dict):
            raise ValueError("Each ablation suite variant must be a JSON object.")
        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError("Every ablation suite variant must define a non-empty 'name'.")
        if name in seen_names:
            raise ValueError(f"Ablation suite variant names must be unique; duplicate '{name}' found.")
        description = str(item.get("description", "")).strip()
        if not description:
            raise ValueError(f"Ablation suite variant '{name}' must define a non-empty 'description'.")
        overrides = item.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError(f"Ablation suite variant '{name}' field 'overrides' must be a JSON object.")
        seen_names.add(name)
        variants.append(
            AblationVariant(
                name=name,
                description=description,
                overrides=copy.deepcopy(overrides),
            )
        )

    if "baseline" not in seen_names:
        raise ValueError("Ablation suite config must include a 'baseline' variant.")

    return AblationSuiteConfig(
        suite_name=suite_name,
        base_config=base_config,
        output_root=output_root,
        seeds=seeds,
        variants=tuple(variants),
    )


def _find_variant(config: AblationSuiteConfig, name: str) -> AblationVariant:
    for variant in config.variants:
        if variant.name == name:
            return variant
    raise ValueError(
        f"Ablation suite '{config.suite_name}' does not define variant '{name}'."
    )


def _load_base_training_payload(base_config_path: Path) -> dict[str, object]:
    return _read_json(base_config_path)


def _resolve_variant_training_config(
    base_payload: dict[str, object],
    *,
    seed: int,
    variant: AblationVariant,
    variant_run_root: Path,
) -> BaselineConfig:
    merged = _deep_merge(base_payload, variant.overrides)
    merged["seed"] = seed
    merged["run_root"] = str(variant_run_root)
    return BaselineConfig.from_dict(merged)


def _initial_run_index(config: AblationSuiteConfig) -> dict[str, object]:
    return {
        "suite_name": config.suite_name,
        "suite_root": str(config.suite_root),
        "base_config": str(config.base_config),
        "entries": [],
    }


def _load_run_index(config: AblationSuiteConfig) -> dict[str, object]:
    path = config.suite_root / "run_index.json"
    if not path.exists():
        return _initial_run_index(config)
    payload = _read_json(path)
    if str(payload.get("suite_name")) != config.suite_name:
        raise ValueError(
            f"Run index '{path}' belongs to suite '{payload.get('suite_name')}', "
            f"expected '{config.suite_name}'."
        )
    return payload


def _write_run_index(config: AblationSuiteConfig, run_index: dict[str, object]) -> Path:
    return _write_json(config.suite_root / "run_index.json", run_index)


def _ensure_suite_root(config: AblationSuiteConfig) -> None:
    config.suite_root.mkdir(parents=True, exist_ok=True)
    suite_config_path = config.suite_root / "suite_config.json"
    serialized = config.to_dict()
    if suite_config_path.exists():
        existing = _read_json(suite_config_path)
        if existing != serialized:
            raise ValueError(
                f"Suite root '{config.suite_root}' already contains a different suite config. "
                "Use a different suite name or clean the existing suite root."
            )
    else:
        _write_json(suite_config_path, serialized)


def _find_run_entry(
    run_index: dict[str, object],
    *,
    variant_name: str,
    seed: int,
) -> dict[str, object] | None:
    for entry in list(run_index.get("entries", [])):
        if str(entry.get("variant")) == variant_name and int(entry.get("seed", -1)) == seed:
            return dict(entry)
    return None


def _upsert_run_entry(run_index: dict[str, object], entry: dict[str, object]) -> None:
    entries = list(run_index.get("entries", []))
    for index, existing in enumerate(entries):
        if (
            str(existing.get("variant")) == str(entry.get("variant"))
            and int(existing.get("seed", -1)) == int(entry.get("seed", -1))
        ):
            entries[index] = entry
            run_index["entries"] = entries
            return
    entries.append(entry)
    run_index["entries"] = entries


def _metric_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0}
    if len(values) == 1:
        return {"mean": float(values[0]), "std": 0.0}
    return {"mean": float(mean(values)), "std": float(pstdev(values))}


def _format_metric(mean_value: float, std_value: float, *, multi_seed: bool) -> str:
    if not multi_seed:
        return f"{mean_value:.4f}"
    return f"{mean_value:.4f} ± {std_value:.4f}"


def _build_axis_conclusion(
    *,
    axis: str,
    baseline_variant: dict[str, object] | None,
    alternative_variant: dict[str, object] | None,
    baseline_setting: str,
    alternative_setting: str,
) -> dict[str, object]:
    if baseline_variant is None or alternative_variant is None:
        return {
            "axis": axis,
            "status": "incomplete",
            "statement": f"Comparison is incomplete because the required runs for '{axis}' are missing.",
        }

    baseline_test = float(baseline_variant["test_top1"]["mean"])
    alternative_test = float(alternative_variant["test_top1"]["mean"])
    delta = alternative_test - baseline_test
    if abs(delta) < NEUTRAL_DELTA_THRESHOLD:
        verdict = "neutral"
        statement = (
            f"{axis}: `{alternative_setting}` is effectively neutral versus "
            f"`{baseline_setting}` on test top-1 (delta={delta:+.4f})."
        )
    elif delta > 0:
        verdict = "alternative_better"
        statement = (
            f"{axis}: `{alternative_setting}` outperformed `{baseline_setting}` "
            f"on test top-1 (delta={delta:+.4f})."
        )
    else:
        verdict = "baseline_better"
        statement = (
            f"{axis}: `{baseline_setting}` outperformed `{alternative_setting}` "
            f"on test top-1 (delta={delta:+.4f})."
        )

    return {
        "axis": axis,
        "status": verdict,
        "baseline_setting": baseline_setting,
        "alternative_setting": alternative_setting,
        "delta_test_top1": delta,
        "statement": statement,
    }


def _render_suite_markdown(summary: dict[str, object]) -> str:
    lines = [
        f"# Ablation Suite: {summary['suite_name']}",
        "",
        f"- suite root: `{summary['suite_root']}`",
        f"- base config: `{summary['base_config']}`",
        f"- seeds requested: `{', '.join(str(seed) for seed in summary['seeds_requested'])}`",
        f"- completed runs: `{summary['completed_run_count']}/{summary['expected_run_count']}`",
        f"- official baseline to beat: `{summary['official_baseline_to_beat']}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Seeds | Val Top-1 | Val Top-5 | Test Top-1 | Test Top-5 | Δ Val Top-1 | Δ Test Top-1 | Edge | Readout | Node Type |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]

    multi_seed = bool(summary["multi_seed"])
    variant_summaries = list(summary["variant_summaries"])
    if variant_summaries:
        for item in variant_summaries:
            lines.append(
                f"| {item['variant']} | {', '.join(str(seed) for seed in item['seeds'])} | "
                f"{_format_metric(float(item['val_top1']['mean']), float(item['val_top1']['std']), multi_seed=multi_seed)} | "
                f"{_format_metric(float(item['val_top5']['mean']), float(item['val_top5']['std']), multi_seed=multi_seed)} | "
                f"{_format_metric(float(item['test_top1']['mean']), float(item['test_top1']['std']), multi_seed=multi_seed)} | "
                f"{_format_metric(float(item['test_top5']['mean']), float(item['test_top5']['std']), multi_seed=multi_seed)} | "
                f"{float(item['delta_vs_baseline']['val_top1']):+.4f} | "
                f"{float(item['delta_vs_baseline']['test_top1']):+.4f} | "
                f"{item['edge_mode']} | {item['readout']} | {item['use_node_type']} |"
            )
    else:
        lines.append("| none | - | 0.0000 | 0.0000 | 0.0000 | 0.0000 | +0.0000 | +0.0000 | - | - | - |")

    lines.extend(["", "## Axis Conclusions", ""])
    for conclusion in list(summary["axis_conclusions"]):
        lines.append(f"- {conclusion['statement']}")

    lines.extend(["", "## Missing Runs", ""])
    missing_runs = list(summary["missing_runs"])
    if missing_runs:
        for item in missing_runs:
            lines.append(f"- `{item['variant']}` seed `{item['seed']}`")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def _build_suite_summary(
    config: AblationSuiteConfig,
    run_index: dict[str, object],
) -> dict[str, object]:
    entries = list(run_index.get("entries", []))
    completed_entries: list[dict[str, object]] = []
    missing_runs: list[dict[str, object]] = []

    for variant in config.variants:
        for seed in config.seeds:
            entry = _find_run_entry(run_index, variant_name=variant.name, seed=seed)
            if entry is None:
                missing_runs.append({"variant": variant.name, "seed": seed})
                continue
            run_dir = Path(str(entry.get("run_dir", "")))
            if not run_dir.exists() or not (run_dir / "summary.json").exists():
                missing_runs.append({"variant": variant.name, "seed": seed})
                continue
            completed_entries.append(entry)

    raw_run_records: list[dict[str, object]] = []
    if completed_entries:
        comparison = compare_saved_runs([str(entry["run_dir"]) for entry in completed_entries])
        by_run_dir = {str(item["run_dir"]): item for item in comparison["runs"]}
        for entry in completed_entries:
            compare_record = by_run_dir[str(entry["run_dir"])]
            raw_run_records.append(
                {
                    "variant": str(entry["variant"]),
                    "description": str(entry.get("description", "")),
                    "seed": int(entry["seed"]),
                    "run_dir": str(entry["run_dir"]),
                    "best_epoch": int(compare_record["best_epoch"]),
                    "val_top1": float(compare_record["val_top1"]),
                    "val_top5": float(compare_record["val_top5"]),
                    "test_top1": float(compare_record["test_top1"]),
                    "test_top5": float(compare_record["test_top5"]),
                    "edge_mode": str(compare_record["edge_mode"]),
                    "readout": str(compare_record["readout"]),
                    "use_node_type": bool(compare_record["use_node_type"]),
                    "hidden_dim": int(compare_record["hidden_dim"]),
                    "num_layers": int(compare_record["num_layers"]),
                }
            )

    grouped: dict[str, list[dict[str, object]]] = {}
    for record in raw_run_records:
        grouped.setdefault(str(record["variant"]), []).append(record)

    variant_summaries: list[dict[str, object]] = []
    baseline_summary: dict[str, object] | None = None
    for variant in config.variants:
        variant_records = sorted(grouped.get(variant.name, []), key=lambda item: int(item["seed"]))
        if not variant_records:
            continue
        summary = {
            "variant": variant.name,
            "description": variant.description,
            "seed_count": len(variant_records),
            "seeds": [int(item["seed"]) for item in variant_records],
            "edge_mode": str(variant_records[0]["edge_mode"]),
            "readout": str(variant_records[0]["readout"]),
            "use_node_type": bool(variant_records[0]["use_node_type"]),
            "hidden_dim": int(variant_records[0]["hidden_dim"]),
            "num_layers": int(variant_records[0]["num_layers"]),
            "val_top1": _metric_stats([float(item["val_top1"]) for item in variant_records]),
            "val_top5": _metric_stats([float(item["val_top5"]) for item in variant_records]),
            "test_top1": _metric_stats([float(item["test_top1"]) for item in variant_records]),
            "test_top5": _metric_stats([float(item["test_top5"]) for item in variant_records]),
        }
        if variant.name == "baseline":
            baseline_summary = summary
        variant_summaries.append(summary)

    for summary in variant_summaries:
        if baseline_summary is None:
            summary["delta_vs_baseline"] = {
                "val_top1": 0.0,
                "val_top5": 0.0,
                "test_top1": 0.0,
                "test_top5": 0.0,
            }
            continue
        summary["delta_vs_baseline"] = {
            "val_top1": float(summary["val_top1"]["mean"]) - float(baseline_summary["val_top1"]["mean"]),
            "val_top5": float(summary["val_top5"]["mean"]) - float(baseline_summary["val_top5"]["mean"]),
            "test_top1": float(summary["test_top1"]["mean"]) - float(baseline_summary["test_top1"]["mean"]),
            "test_top5": float(summary["test_top5"]["mean"]) - float(baseline_summary["test_top5"]["mean"]),
        }

    variant_summaries.sort(
        key=lambda item: (
            -float(item["test_top1"]["mean"]),
            -float(item["val_top1"]["mean"]),
            str(item["variant"]),
        )
    )

    recommended = "incomplete"
    if variant_summaries:
        recommended = str(variant_summaries[0]["variant"])

    by_variant = {str(item["variant"]): item for item in variant_summaries}
    axis_conclusions = [
        _build_axis_conclusion(
            axis="Edge Direction",
            baseline_variant=by_variant.get("baseline"),
            alternative_variant=by_variant.get("forward_edges"),
            baseline_setting="bidirectional",
            alternative_setting="forward",
        ),
        _build_axis_conclusion(
            axis="Readout",
            baseline_variant=by_variant.get("baseline"),
            alternative_variant=by_variant.get("mean_pool"),
            baseline_setting="state",
            alternative_setting="mean",
        ),
        _build_axis_conclusion(
            axis="Node Type Embeddings",
            baseline_variant=by_variant.get("baseline"),
            alternative_variant=by_variant.get("no_node_type"),
            baseline_setting="enabled",
            alternative_setting="disabled",
        ),
    ]

    return {
        "suite_name": config.suite_name,
        "suite_root": str(config.suite_root),
        "base_config": str(config.base_config),
        "seeds_requested": list(config.seeds),
        "multi_seed": len(config.seeds) > 1,
        "expected_run_count": len(config.variants) * len(config.seeds),
        "completed_run_count": len(completed_entries),
        "missing_runs": missing_runs,
        "raw_run_records": raw_run_records,
        "variant_summaries": variant_summaries,
        "axis_conclusions": axis_conclusions,
        "official_baseline_to_beat": recommended,
    }


def run_ablation_suite(
    suite_config_path: str | Path = DEFAULT_ABLATION_SUITE_CONFIG_PATH,
    *,
    variant: str | None = None,
    compare_only: bool = False,
) -> dict[str, object]:
    config = load_ablation_suite_config(suite_config_path)
    if compare_only and variant is not None:
        raise ValueError("The ablation suite '--compare-only' mode cannot be combined with '--variant'.")

    _ensure_suite_root(config)
    run_index = _load_run_index(config)

    if not compare_only:
        target_variants = [(_find_variant(config, variant),)] if variant is not None else [(item,) for item in config.variants]
        base_payload = _load_base_training_payload(config.base_config)
        for (variant_config,) in target_variants:
            for seed in config.seeds:
                existing_entry = _find_run_entry(run_index, variant_name=variant_config.name, seed=seed)
                if existing_entry is not None:
                    run_dir = Path(str(existing_entry.get("run_dir", "")))
                    if run_dir.exists() and (run_dir / "summary.json").exists():
                        console_print(
                            f"  Skipping {variant_config.name} seed {seed}: "
                            f"run already completed at {run_dir}"
                        )
                        continue

                variant_run_root = config.suite_root / "variant_runs" / variant_config.name / f"seed_{seed}"
                training_config = _resolve_variant_training_config(
                    base_payload,
                    seed=seed,
                    variant=variant_config,
                    variant_run_root=variant_run_root,
                )
                console_print(
                    f"\n  Running ablation variant '{variant_config.name}' "
                    f"(seed={seed}, readout={training_config.model.readout}, "
                    f"edge_mode={training_config.edge_mode}, node_type={training_config.use_node_type})"
                )
                summary = train_baseline(training_config)
                _upsert_run_entry(
                    run_index,
                    {
                        "variant": variant_config.name,
                        "description": variant_config.description,
                        "seed": seed,
                        "run_root": str(variant_run_root),
                        "run_dir": str(summary["run_dir"]),
                    },
                )
                _write_run_index(config, run_index)

    summary = _build_suite_summary(config, run_index)
    summary_json_path = _write_json(config.suite_root / "suite_summary.json", summary)
    summary_md_path = _write_text(config.suite_root / "suite_summary.md", _render_suite_markdown(summary))
    console_print(f"\n  Wrote suite summary JSON : {summary_json_path}")
    console_print(f"  Wrote suite summary MD   : {summary_md_path}")
    return summary


def build_ablation_suite_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or summarize a baseline ablation suite")
    parser.add_argument(
        "--suite-config",
        type=str,
        default=str(DEFAULT_ABLATION_SUITE_CONFIG_PATH),
        help="Path to the ablation suite JSON manifest",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default=None,
        help="Run only one named variant from the suite",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Skip training and rebuild suite summary artifacts from completed runs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_ablation_suite_arg_parser()
    args = parser.parse_args(argv)

    try:
        run_ablation_suite(
            args.suite_config,
            variant=args.variant,
            compare_only=bool(args.compare_only),
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        console_print(f"  ERROR: {exc}")
        return 1

    return 0
