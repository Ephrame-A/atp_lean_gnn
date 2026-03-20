"""
Dataset loading and streaming for the LeanDojo benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator


DATASET_NAME = "cat-searcher/leandojo-benchmark-4-random"


@dataclass(frozen=True)
class DatasetRow:
    state: str
    theorem: str
    tactic: str
    split: str
    row_index: int

    def metadata(self) -> dict[str, object]:
        return {
            "source": "dataset",
            "dataset": DATASET_NAME,
            "split": self.split,
            "row_index": self.row_index,
            "theorem": self.theorem,
            "tactic": self.tactic,
        }


def _load_hf_split(split: str, *, dataset_name: str = DATASET_NAME):
    """Return a HuggingFace streaming dataset (lazy import)."""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "The 'datasets' package is required. Run: pip install datasets"
        ) from exc
    return load_dataset(dataset_name, split=split, streaming=True)


def load_dataset_row(row_index: int, *, split: str = "train") -> DatasetRow:
    """Load a single row by index (for the interactive CLI)."""
    ds = _load_hf_split(split)
    for index, sample in enumerate(ds):
        if index == row_index:
            return DatasetRow(
                state=sample["state"],
                theorem=sample.get("full_name", ""),
                tactic=sample.get("tactic", ""),
                split=split,
                row_index=index,
            )
    raise IndexError(f"Row {row_index} not found in split '{split}'.")


def stream_split(
    split: str = "train",
    *,
    limit: int | None = None,
    dataset_name: str = DATASET_NAME,
) -> Generator[DatasetRow, None, None]:
    """
    Yield ``DatasetRow`` objects for every example in *split*.

    Parameters
    ----------
    split : str
        One of ``"train"``, ``"val"``, ``"test"``.
    limit : int or None
        If set, stop after this many rows (useful for dry runs).
    dataset_name : str
        Override the default HuggingFace dataset identifier.
    """
    ds = _load_hf_split(split, dataset_name=dataset_name)
    for index, sample in enumerate(ds):
        if limit is not None and index >= limit:
            return
        yield DatasetRow(
            state=sample["state"],
            theorem=sample.get("full_name", ""),
            tactic=sample.get("tactic", ""),
            split=split,
            row_index=index,
        )
