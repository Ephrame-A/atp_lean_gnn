from __future__ import annotations

import re
from enum import IntEnum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .graph import DAGBuilder

# ─────────────────────────────────────────────────────────────────────────────
# Original ExprParser — unchanged
# ─────────────────────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(
    r"""
    (?P<LPAREN> \( ) |
    (?P<RPAREN> \) ) |
    (?P<ARROW>  \u2192|-> ) |
    (?P<AT>     @ ) |
    (?P<IDENT>  [^\s()\u2192@\[\]\u27e8\u27e9,;]+ )
    """,
    re.VERBOSE,
)


def tokenize(expr: str) -> list[tuple[str, str]]:
    return [(match.lastgroup, match.group()) for match in _TOKEN_RE.finditer(expr)]


class ExprParser:
    """
    Recursive descent parser for a Lean-style expression.

    Grammar (simplified):
        expr  := arrow
        arrow := app ( ("->" | "→") app )*
        app   := atom+
        atom  := IDENT | "(" expr ")" | "@" atom
    """

    def __init__(self, dag: "DAGBuilder"):
        self.dag = dag
        self.tokens: list[tuple[str, str]] = []
        self.pos = 0

    def parse(self, expr_str: str) -> int:
        self.tokens = tokenize(expr_str)
        self.pos = 0
        return self._parse_arrow()

    def _parse_arrow(self) -> int:
        left = self._parse_app()
        while self._peek_type() == "ARROW":
            self._consume()
            right = self._parse_app()
            left = self.dag.get_or_create("Arrow", (left, right))
        return left

    def _parse_app(self) -> int:
        func = self._parse_atom()
        if func is None:
            return self.dag.get_or_create("?", ())
        while True:
            arg = self._parse_atom()
            if arg is None:
                break
            func = self.dag.get_or_create("App", (func, arg))
        return func

    def _parse_atom(self) -> int | None:
        token = self._peek()
        if token is None:
            return None
        token_type, token_value = token

        if token_type == "LPAREN":
            self._consume()
            node = self._parse_arrow()
            if self._peek_type() == "RPAREN":
                self._consume()
            return node

        if token_type == "AT":
            self._consume()
            inner = self._parse_atom()
            if inner is None:
                return self.dag.get_or_create("@", ())
            return self.dag.get_or_create("Explicit", (inner,))

        if token_type == "IDENT":
            self._consume()
            return self.dag.get_or_create(token_value, ())

        return None

    def _peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _peek_type(self) -> str | None:
        token = self._peek()
        return token[0] if token else None

    def _consume(self) -> tuple[str, str]:
        token = self.tokens[self.pos]
        self.pos += 1
        return token


# ─────────────────────────────────────────────────────────────────────────────
# Tactic filter
# ─────────────────────────────────────────────────────────────────────────────

class Tactic(IntEnum):
    # Takes one premise  (your premise selector provides the argument)
    EXACT        = 0   # exact <premise>
    APPLY        = 1   # apply <premise>
    REWRITE      = 2   # rw [<premise>]
    REWRITE_SYMM = 3   # rw [← <premise>]
    CASES        = 4   # cases <local_hyp>
    INDUCTION    = 5   # induction <local_hyp_or_recursor>
    # Takes no premise
    INTRO        = 6   # intro / rintro / intros
    RFL          = 7   # rfl
    ASSUMPTION   = 8   # assumption
    CONTRADICTION= 9   # contradiction
    DECIDE       = 10  # decide
    RING         = 11  # ring
    OMEGA        = 12  # omega

N_TACTIC_CLASSES = len(Tactic)       # 13 — the GNN output size
NEEDS_PREMISE    = frozenset(range(6))  # labels 0-5 call the premise selector


def get_premises(tactic_raw: str) -> list[str]:
    """
    Extract fully-qualified premise names from LeanDojo's <a>Name</a> tags.

    LeanDojo resolves short names to fully-qualified names at extraction
    time and wraps them in <a> tags inline in the tactic string.
    These are the ground-truth labels for your premise selector.

    "rw [<a>Nat.add_comm</a>, ← <a>Nat.add_assoc</a>]"
    → ["Nat.add_comm", "Nat.add_assoc"]
    """
    return re.findall(r'<a>(.*?)</a>', tactic_raw)


def clean_tactic(tactic_raw: str) -> str:
    """
    Strip <a>...</a> tags, leaving the plain tactic string.

    "exact <a>mul_pos</a> had hbd"  →  "exact mul_pos had hbd"
    """
    return re.sub(r'</?a>', '', tactic_raw).strip()


def filter_tactic(
    tactic_raw: str,
) -> list[tuple[Tactic, Optional[str]]]:
    """
    Map one raw tactic string from the parquet file to training samples.

    Calls get_premises() and clean_tactic() internally — you pass the
    raw string directly from row['tactic'], nothing else needed.

    Returns
    -------
    []                              tactic is dropped
    [(Tactic.RFL, None)]            zero-premise
    [(Tactic.APPLY, "Nat.succ")]    single-premise
    [(Tactic.REWRITE, "a"),
     (Tactic.REWRITE_SYMM, "b")]   rw decomposed into one entry per lemma

    Dataset loop
    ------------
    for _, row in df.iterrows():
        for tactic, premise in filter_tactic(row['tactic']):
            graph = build_graph(row['state'])
            dataset.add(graph, int(tactic), premise)
    """
    premises = get_premises(tactic_raw)
    tactic   = clean_tactic(tactic_raw)
    head     = tactic.split()[0].rstrip('?!') if tactic.strip() else ''

    match head:

        # ── zero-premise closers ─────────────────────────────────────────────

        case 'rfl':
            return [(Tactic.RFL, None)]

        case 'assumption':
            return [(Tactic.ASSUMPTION, None)]

        case 'contradiction':
            return [(Tactic.CONTRADICTION, None)]

        case 'decide':
            return [(Tactic.DECIDE, None)]

        case 'ring' | 'ring_nf':
            return [(Tactic.RING, None)]

        case 'omega':
            return [(Tactic.OMEGA, None)]

        # ── intro family ─────────────────────────────────────────────────────
        # All introduce variables/hypotheses into the local context.
        # rintro is "rcases-style intro": destructs immediately while introducing.
        # ext / ext1 / funext prove extensionality by introducing an argument.
        # All are zero-premise: the variable name is locally invented, not selected.
        # One INTRO entry per variable introduced (len(args) or 1 if bare).

        case 'intro' | 'intros' | 'rintro' | 'ext' | 'ext1' | 'funext':
            n = max(1, len(tactic.split()) - 1)
            return [(Tactic.INTRO, None)] * n

        # ── exact ─────────────────────────────────────────────────────────────

        case 'exact':
            return [(Tactic.EXACT, _pick_global(premises, tactic, 'exact'))]

        # ── apply ─────────────────────────────────────────────────────────────

        case 'apply':
            return [(Tactic.APPLY, _pick_global(premises, tactic, 'apply'))]

        # ── cases family ──────────────────────────────────────────────────────
        # cases h          — split on local hyp h
        # cases' h with .. — Lean 3-style variant, same semantics
        # rcases h with .. — also splits h, pattern on the right is for naming
        # When LeanDojo annotates a premise (e.g. cases' <a>lt_or_le</a> i l),
        # it means the *expression* being cased on is a global term, not a hyp.
        # In that case use the LJ name; otherwise extract the local ident.

        case 'cases' | "cases'":
            arg = _pick_cases(premises, tactic, head)
            return [(Tactic.CASES, arg)] if arg else []

        case 'rcases':
            arg = _pick_cases(premises, tactic, 'rcases')
            return [(Tactic.CASES, arg)] if arg else []

        # ── induction family ──────────────────────────────────────────────────
        # induction n               — induct on local var n (default recursor)
        # induction n using Rec     — induct on n with custom recursor Rec
        # induction' n using <a>Rec</a>  — LeanDojo annotates the recursor
        #
        # What should the premise be?
        #   • If a custom recursor is present (annotated in <a> tags),
        #     the recursor IS the meaningful choice — use it.
        #     (The variable n is just whatever is in context; the recursor
        #      is the real mathematical decision.)
        #   • If no recursor, the target variable is the premise (local hyp).

        case 'induction' | "induction'":
            arg = _pick_induction(premises, tactic, head)
            return [(Tactic.INDUCTION, arg)] if arg else []

        # ── rw family ─────────────────────────────────────────────────────────
        # rw      — rewrite at all positions
        # rwa     — rewrite then assumption (we emit the rewrite steps; the
        #           implicit assumption close is ignored — it contributes no
        #           premise-selector signal)
        # erw     — extensional rw (same bracket syntax)
        # nth_rw  — rewrite n-th occurrence: nth_rw 1 [f] → same as rw [f]
        # simp_rw — rewrite under binders (same bracket syntax)
        # All decompose into one (REWRITE or REWRITE_SYMM, premise) per lemma.

        case 'rw' | 'rwa' | 'erw' | 'nth_rw' | 'simp_rw':
            return _decompose_rw(tactic, premises)

        # ── everything else: drop ─────────────────────────────────────────────

        case _:
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pick_global(premises: list[str], tactic: str, head: str) -> str:
    """
    Premise for exact / apply.
    LeanDojo's resolved name (premises[0]) is always preferred.
    Raw fallback: strip everything after the first whitespace and leading @.
    """
    if premises:
        return premises[0]
    return tactic[len(head):].strip().lstrip('@').split()[0]


def _pick_cases(premises: list[str], tactic: str, head: str) -> Optional[str]:
    """
    Premise for cases / cases' / rcases.
    If LeanDojo annotated a premise, use it (e.g. cases' <a>lt_or_le</a> i l).
    Otherwise extract the first local identifier after the keyword.
    """
    if premises:
        return premises[0]
    return _first_ident(tactic, head)


def _pick_induction(premises: list[str], tactic: str, head: str) -> Optional[str]:
    """
    Premise for induction / induction'.
    If `using <Recursor>` is present and LeanDojo annotated it, use the recursor.
    Otherwise use the target variable (local hyp).
    """
    if premises and 'using' in tactic:
        return premises[0]     # annotated recursor is the meaningful choice
    return _first_ident(tactic, head)


def _first_ident(tactic: str, head: str) -> Optional[str]:
    """
    Extract the first Lean identifier after `head`.
    Stops at keywords that introduce sub-patterns, not the target:
    'with', 'using', 'generalizing'.
    Strips leading @ (explicit argument syntax).
    """
    rest = tactic[len(head):].strip().lstrip('@').strip()
    m = re.match(r'^([\w.\']+)', rest)
    if not m:
        return None
    ident = m.group(1)
    if ident in ('with', 'using', 'generalizing'):
        return None
    return ident


def _decompose_rw(tactic: str, premises: list[str]) -> list[tuple[Tactic, Optional[str]]]:
    """
    Decompose  rw [a, ← b, @c _ _, d]  into one entry per lemma.

    For each item in the bracket list:
      - Detect REWRITE_SYMM if the item starts with ← or <-.
      - Strip ← / @ / trailing arguments to get the bare name.
      - Use premises[i] (LeanDojo-resolved) when available; fallback to raw name.

    The "at h" suffix (rw [...] at h) is outside the brackets and is
    never seen by this function — regex stops at the first ].
    """
    m = re.search(r'\[(.*?)\]', tactic, re.DOTALL)
    if not m:
        return []

    result    = []
    prem_iter = iter(premises)

    for item in m.group(1).split(','):
        item = item.strip()
        if not item:
            continue

        symm = item.startswith('←') or item.startswith('<-')
        raw  = re.sub(r'^(←|<-)\s*', '', item).strip()
        raw  = raw.lstrip('@').split()[0]   # drop trailing args like "_ _ z"

        resolved = next(prem_iter, None) or raw
        result.append((Tactic.REWRITE_SYMM if symm else Tactic.REWRITE, resolved))

    return result