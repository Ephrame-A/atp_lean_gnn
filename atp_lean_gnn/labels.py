from __future__ import annotations

import re
from collections.abc import Iterable


EMPTY_TACTIC = "<EMPTY_TACTIC>"
UNKNOWN_TACTIC = "<UNK_TACTIC>"
TACTIC_TOKEN_RE = re.compile(r"[A-Za-z0-9_.'!?]+")


def normalize_tactic(raw: str) -> str:
    text = raw.strip()
    if not text:
        return EMPTY_TACTIC

    match = TACTIC_TOKEN_RE.search(text)
    if match is None:
        return EMPTY_TACTIC
    return match.group(0)


def build_tactic_vocab(labels: Iterable[str]) -> dict[str, int]:
    vocab = {UNKNOWN_TACTIC: 0}
    for index, label in enumerate(sorted(set(labels)), start=1):
        vocab[label] = index
    return vocab


def label_example(raw_tactic: str) -> dict[str, object]:
    tactic_name = normalize_tactic(raw_tactic)
    return {
        "tactic_raw": raw_tactic,
        "tactic_name": tactic_name,
    }


def encode_tactic_name(tactic_name: str, tactic_vocab: dict[str, int]) -> int:
    return tactic_vocab.get(tactic_name, tactic_vocab[UNKNOWN_TACTIC])
