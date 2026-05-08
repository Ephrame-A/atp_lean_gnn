"""
atomic_tactics.py
-----------------
Implements the Nazrin atomic tactic set (paper §4.1) and the
expression-tree → atomic tactic decomposition (paper §4.2, Table 1).

Nazrin's Table 1 maps every Lean 4 expression constructor to an atomic tactic:

  Constructor       | Atomic Tactic
  ------------------|-----------------------------
  .bvar             | INVALID  (bound var, never at top-level)
  .mvar             | INVALID  (open metavar, not a solution)
  .sort             | inhabit  (e.g. Type, Prop)
  λ x . y           | intro
  .fvar / .const    | exact  or  apply  (constant/free-var)
  .lit              | inhabit  (literal value)
  ∀ x . y           | pi      (type-level forall)
  .app f a          | tailArg (apply f, peel off one argument)
  .letE             | unfold  (let-in binder → substitute)
  .mdata            | unfold  (metadata wrapper → strip)
  .proj             | apply or cases (structure projection)

The atomizer walks the *proof term* top-down and emits one AtomicStep
per constructor node.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# 1.  Lean expression node types (mirrors Lean 4 Expr inductive)
# ──────────────────────────────────────────────────────────────────────────────

class ExprKind(str, Enum):
    BVAR    = "bvar"    # bound variable — invalid at top-level of proof term
    MVAR    = "mvar"    # metavariable   — invalid in a completed proof term
    SORT    = "sort"    # Sort / Type / Prop
    LAMBDA  = "lambda"  # λ x : T, body
    FORALL  = "forall"  # ∀ x : T, body  (Π-type)
    FVAR    = "fvar"    # free variable (hypothesis in local context)
    CONST   = "const"   # global constant / theorem name
    APP     = "app"     # function application f a
    LIT     = "lit"     # literal (Nat.lit, String.lit, …)
    LETE    = "letE"    # let x := v; body
    MDATA   = "mdata"   # metadata wrapper (annotations, etc.)
    PROJ    = "proj"    # structure field projection  (.1, .2, .fst, …)


@dataclass
class LeanExpr:
    """
    Minimal Python representation of a Lean 4 kernel expression.
    Built from Pantograph's JSON output (see pantograph_bridge.py).
    """
    kind:     ExprKind
    # For CONST / FVAR: the name string
    name:     Optional[str]       = None
    # For LAMBDA / FORALL: binder name, domain type, body
    binder:   Optional[str]       = None
    domain:   Optional["LeanExpr"] = None
    body:     Optional["LeanExpr"] = None
    # For APP: function and argument
    func:     Optional["LeanExpr"] = None
    arg:      Optional["LeanExpr"] = None
    # For PROJ: structure name + field index
    struct:   Optional[str]       = None
    field_idx: Optional[int]      = None
    # For SORT: universe level (string)
    level:    Optional[str]       = None
    # For LIT: the literal value (as string)
    lit_val:  Optional[str]       = None
    # For LETE: let-binding variable, value, body
    let_name: Optional[str]       = None
    let_val:  Optional["LeanExpr"] = None
    # For MDATA: wrapped expression
    inner:    Optional["LeanExpr"] = None
    # Raw string form (delaborated), useful for exact/apply args
    raw:      Optional[str]       = None


# ──────────────────────────────────────────────────────────────────────────────
# 2.  Atomic tactic types (Nazrin §4.1, Figures 2 & 3)
# ──────────────────────────────────────────────────────────────────────────────

class AtomicTacticKind(str, Enum):
    # ── from the expression-tree mapping (Table 1) ──
    INTRO        = "intro"        # introduce λ-binder:  intro x
    EXACT        = "exact"        # close goal with constant/fvar: exact f
    APPLY        = "apply"        # apply function, create arg subgoals: apply f
    CASES        = "cases"        # case-split on an inductive: cases h
    INDUCTION    = "induction"    # structural induction: induction h
    REVERT       = "revert"       # push hypothesis back to goal: revert h
    PI           = "pi"           # introduce Π-type as goal: (internal)
    TAIL_ARG     = "tailArg"      # peel one APP argument off goal
    INHABIT      = "inhabit"      # provide default/Inhabited value
    UNFOLD       = "unfold"       # unfold let / strip mdata
    # ── additional completeness tactics (Figure 3) ──
    RFL          = "rfl"          # reflexivity
    ASSUMPTION   = "assumption"   # close from local context
    DECIDE       = "decide"       # decidable computation
    CONTRADICTION = "contradiction"  # close contradictory context
    REDUCE_BETA  = "reduceBeta"   # β-reduce subexpression
    REDUCE_PROJ  = "reduceProj"   # unfold projection


@dataclass
class AtomicStep:
    """
    One training sample: a (goal_state, atomic_tactic, argument) triple.
    `goal_state_str`   — Pantograph presentation-view string of the goal.
    `goal_expr`        — optional parsed LeanExpr of the goal type.
    `tactic`           — which atomic tactic fires.
    `argument`         — the argument (constant name, fvar name, etc.) or None.
    `new_goal_count`   — how many new subgoals this step creates (≥0).
    `source_tactic`    — the original human tactic this was derived from.
    `theorem_name`     — parent theorem fully qualified name.
    """
    tactic:          AtomicTacticKind
    goal_state_str:  str
    argument:        Optional[str]   = None
    new_goal_count:  int             = 0
    goal_expr:       Optional[LeanExpr] = None
    source_tactic:   Optional[str]   = None
    theorem_name:    Optional[str]   = None


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Core atomization: proof-term expression → sequence of AtomicSteps
# ──────────────────────────────────────────────────────────────────────────────

def atomize_expr(
    expr:          LeanExpr,
    goal_state_str: str,
    source_tactic:  str,
    theorem_name:   str,
) -> list[AtomicStep]:
    """
    Walk the proof-term expression top-down and emit one AtomicStep per node.

    This implements the *atomization* phase of Nazrin §4.2 (after transposition).
    The proof term `expr` is what Lean's kernel has assigned to a metavariable;
    we decompose it into primitive constructors, each becoming one atomic tactic.

    Traversal is DFS pre-order (root first → left → right), which corresponds
    to the natural search order: decide the head constructor, then fill arguments.
    """
    steps: list[AtomicStep] = []
    _walk(expr, goal_state_str, source_tactic, theorem_name, steps)
    return steps


def _walk(
    expr:          LeanExpr,
    ctx_state:     str,
    source_tactic: str,
    theorem_name:  str,
    out:           list[AtomicStep],
) -> None:
    """Recursive DFS walker."""

    def step(tactic: AtomicTacticKind, arg: Optional[str] = None, n_new: int = 0):
        out.append(AtomicStep(
            tactic=tactic,
            goal_state_str=ctx_state,
            argument=arg,
            new_goal_count=n_new,
            source_tactic=source_tactic,
            theorem_name=theorem_name,
            goal_expr=expr,
        ))

    kind = expr.kind

    # ── Table 1 mapping ──────────────────────────────────────────────────────

    if kind == ExprKind.BVAR:
        # Bound variable at top-level is invalid in a complete proof term.
        # If it appears, the term is malformed — skip silently.
        return

    elif kind == ExprKind.MVAR:
        # Open metavariable — not a completed proof term.
        return

    elif kind == ExprKind.SORT:
        # Proving a Sort/Prop/Type: use inhabit (provides Inhabited.default)
        step(AtomicTacticKind.INHABIT, arg=f"Sort({expr.level})", n_new=0)

    elif kind == ExprKind.LAMBDA:
        # λ x : T, body  →  intro x ; then recurse into body
        step(AtomicTacticKind.INTRO, arg=expr.binder, n_new=1)
        if expr.body:
            _walk(expr.body, ctx_state, source_tactic, theorem_name, out)

    elif kind == ExprKind.FORALL:
        # ∀ x : T, body  at proof-term level →  pi tactic (creates type subgoals)
        step(AtomicTacticKind.PI, arg=expr.binder, n_new=2)
        # Recurse: domain type subgoal, then body subgoal
        if expr.domain:
            _walk(expr.domain, ctx_state, source_tactic, theorem_name, out)
        if expr.body:
            _walk(expr.body, ctx_state, source_tactic, theorem_name, out)

    elif kind == ExprKind.FVAR:
        # Free variable (local hypothesis) — use exact if it closes the goal,
        # apply if it produces subgoals.  We conservatively emit exact here;
        # the caller can upgrade to apply based on arity inspection.
        step(AtomicTacticKind.EXACT, arg=expr.name, n_new=0)

    elif kind == ExprKind.CONST:
        # Global constant (theorem / definition name).
        # If the constant has arity > 0, this is an apply (creates arg subgoals).
        # We emit APPLY for non-nullary constants; the replayer will verify.
        # We use a heuristic: if it's the leaf of an APP chain, prefer EXACT.
        # The _walk_app helper handles the spine correctly.
        step(AtomicTacticKind.EXACT, arg=expr.name, n_new=0)

    elif kind == ExprKind.APP:
        # Function application  f a1 a2 … an
        # Decompose the left-spine: collect (func, [arg1, arg2, …, argN])
        func, args = _collect_app_spine(expr)
        # The head of the spine gets apply; each argument becomes a subgoal.
        head_arg = func.name if func.name else (func.raw or "?")
        n_subgoals = len(args)
        step(AtomicTacticKind.APPLY, arg=head_arg, n_new=n_subgoals)
        # Now recurse into each argument expression (filling subgoals left-to-right)
        for a in args:
            _walk(a, ctx_state, source_tactic, theorem_name, out)

    elif kind == ExprKind.LIT:
        # Literal value — inhabit with the concrete literal
        step(AtomicTacticKind.INHABIT, arg=expr.lit_val, n_new=0)

    elif kind == ExprKind.LETE:
        # let x := v; body  →  unfold the let, then recurse into body
        step(AtomicTacticKind.UNFOLD, arg=f"let {expr.let_name}", n_new=1)
        if expr.let_val:
            _walk(expr.let_val, ctx_state, source_tactic, theorem_name, out)
        if expr.body:
            _walk(expr.body, ctx_state, source_tactic, theorem_name, out)

    elif kind == ExprKind.MDATA:
        # Metadata wrapper — strip it and recurse
        step(AtomicTacticKind.UNFOLD, arg="mdata", n_new=1)
        if expr.inner:
            _walk(expr.inner, ctx_state, source_tactic, theorem_name, out)

    elif kind == ExprKind.PROJ:
        # Structure projection  e.field_idx
        step(AtomicTacticKind.APPLY, arg=f"{expr.struct}.{expr.field_idx}", n_new=1)


def _collect_app_spine(expr: LeanExpr) -> tuple[LeanExpr, list[LeanExpr]]:
    """
    Left-spine decomposition of an APP chain.
    APP(APP(APP(f, a1), a2), a3)  →  (f, [a1, a2, a3])
    """
    args: list[LeanExpr] = []
    cur = expr
    while cur.kind == ExprKind.APP:
        args.append(cur.arg)
        cur = cur.func
    args.reverse()   # arguments are collected right-to-left; reverse for natural order
    return cur, args


# ──────────────────────────────────────────────────────────────────────────────
# 4.  High-level tactic-string → AtomicSteps  (presentation → atomic)
# ──────────────────────────────────────────────────────────────────────────────

def atomize_tactic_string(
    tactic_str:    str,
    goal_state_str: str,
    theorem_name:  str,
) -> list[AtomicStep]:
    """
    Lightweight pattern-based atomizer that works directly on tactic *strings*
    (from LeanDojo data) without requiring a live Lean process.

    This is Phase 1 of the pipeline: it handles the most common high-level
    tactic patterns that can be decomposed statically.  For tactics requiring
    kernel-level expression trees (e.g. `simp`, `omega`), this returns a
    single APPLY step and marks it for live-replay refinement.

    Handles:
      rw [a, b, c]            → [APPLY Eq.mpr(a), APPLY Eq.mpr(b), ...]
      rw [← a]                → [APPLY Eq.mpr(Eq.symm(a)), ...]
      apply f                 → [APPLY f]
      exact e                 → [EXACT e]
      intro x y z             → [INTRO x, INTRO y, INTRO z]
      cases h                 → [CASES h]
      induction h             → [INDUCTION h]
      constructor             → [APPLY And.intro]  or similar
      simp [...]              → [APPLY simp_lemma] (needs refinement)
      ring / omega / linarith → [DECIDE]  (decidable closer)
      rfl                     → [RFL]
      assumption              → [ASSUMPTION]
      contradiction           → [CONTRADICTION]
    """
    t = tactic_str.strip()
    steps: list[AtomicStep] = []

    def mk(kind: AtomicTacticKind, arg=None, n=0):
        return AtomicStep(
            tactic=kind,
            goal_state_str=goal_state_str,
            argument=arg,
            new_goal_count=n,
            source_tactic=tactic_str,
            theorem_name=theorem_name,
        )

    # ── rfl ──────────────────────────────────────────────────────────────────
    if t == "rfl":
        steps.append(mk(AtomicTacticKind.RFL))

    # ── assumption ───────────────────────────────────────────────────────────
    elif t == "assumption":
        steps.append(mk(AtomicTacticKind.ASSUMPTION))

    # ── contradiction ─────────────────────────────────────────────────────────
    elif t == "contradiction":
        steps.append(mk(AtomicTacticKind.CONTRADICTION))

    # ── decide / ring / omega / linarith / norm_num ──────────────────────────
    elif any(t.startswith(kw) for kw in ("decide", "ring", "omega", "linarith", "norm_num", "norm_cast", "positivity")):
        steps.append(mk(AtomicTacticKind.DECIDE, arg=t.split()[0]))

    # ── constructor ──────────────────────────────────────────────────────────
    elif t == "constructor":
        # Splits the goal into two subgoals (And.intro, Iff.intro, etc.)
        steps.append(mk(AtomicTacticKind.APPLY, arg="constructor", n=2))

    # ── intro x y z ──────────────────────────────────────────────────────────
    elif t.startswith("intro ") or t == "intro":
        parts = t.split()[1:]  # variable names
        if not parts:
            steps.append(mk(AtomicTacticKind.INTRO, arg="_"))
        for v in parts:
            steps.append(mk(AtomicTacticKind.INTRO, arg=v, n=1))

    # ── revert h ─────────────────────────────────────────────────────────────
    elif t.startswith("revert "):
        for v in t.split()[1:]:
            steps.append(mk(AtomicTacticKind.REVERT, arg=v, n=0))

    # ── exact e ──────────────────────────────────────────────────────────────
    elif t.startswith("exact "):
        arg = t[len("exact "):].strip()
        steps.append(mk(AtomicTacticKind.EXACT, arg=arg))

    # ── apply f ──────────────────────────────────────────────────────────────
    elif t.startswith("apply "):
        arg = t[len("apply "):].strip()
        # We don't know arity statically; mark n_new as -1 (unknown)
        steps.append(mk(AtomicTacticKind.APPLY, arg=arg, n=-1))

    # ── cases h / rcases h ───────────────────────────────────────────────────
    elif t.startswith("cases ") or t.startswith("rcases "):
        parts = t.split()
        h = parts[1] if len(parts) > 1 else "?"
        steps.append(mk(AtomicTacticKind.CASES, arg=h, n=-1))

    # ── induction h / induction h using r ────────────────────────────────────
    elif t.startswith("induction "):
        parts = t.split()
        h = parts[1] if len(parts) > 1 else "?"
        r = parts[3] if "using" in parts and len(parts) > 3 else None
        steps.append(mk(AtomicTacticKind.INDUCTION, arg=h if not r else f"{h},{r}", n=-1))

    # ── rw [a, b, c] / rw [←a] ───────────────────────────────────────────────
    elif t.startswith("rw ") or t.startswith("rw["):
        lemmas = _parse_rw_list(t)
        for lemma, symm in lemmas:
            if symm:
                arg = f"Eq.symm({lemma})"
            else:
                arg = lemma
            # Each rewrite is an Eq.mpr application
            steps.append(mk(AtomicTacticKind.APPLY, arg=f"Eq.mpr[{arg}]", n=1))

    # ── simp [a, b] / simp only [a, b] ───────────────────────────────────────
    elif t.startswith("simp"):
        lemmas = _parse_rw_list(t)  # reuse parser for lemma list
        if lemmas:
            for lemma, symm in lemmas:
                arg = f"Eq.symm({lemma})" if symm else lemma
                steps.append(mk(AtomicTacticKind.APPLY, arg=f"simp[{arg}]", n=1))
        else:
            # Plain `simp` with no explicit lemmas — needs live replay
            steps.append(mk(AtomicTacticKind.APPLY, arg="simp", n=-1))

    # ── unfold f / delta f ───────────────────────────────────────────────────
    elif t.startswith("unfold ") or t.startswith("delta "):
        arg = " ".join(t.split()[1:])
        steps.append(mk(AtomicTacticKind.UNFOLD, arg=arg, n=0))

    # ── have h : T := ... ───────────────────────────────────────────────────
    elif t.startswith("have "):
        # Introduces an intermediate lemma — creates two subgoals
        steps.append(mk(AtomicTacticKind.APPLY, arg="have", n=2))

    # ── obtain ⟨a, b⟩ := h ──────────────────────────────────────────────────
    elif t.startswith("obtain "):
        steps.append(mk(AtomicTacticKind.CASES, arg="obtain", n=-1))

    # ── use e ────────────────────────────────────────────────────────────────
    elif t.startswith("use "):
        arg = t[len("use "):].strip()
        steps.append(mk(AtomicTacticKind.APPLY, arg=f"Exists.intro[{arg}]", n=1))

    # ── refine e ─────────────────────────────────────────────────────────────
    elif t.startswith("refine "):
        arg = t[len("refine "):].strip()
        steps.append(mk(AtomicTacticKind.APPLY, arg=arg, n=-1))

    # ── push_neg / pull_neg ───────────────────────────────────────────────────
    elif t.startswith("push_neg") or t.startswith("pull_neg"):
        steps.append(mk(AtomicTacticKind.APPLY, arg=t.split()[0], n=0))

    # ── ext / funext ─────────────────────────────────────────────────────────
    elif t in ("ext", "funext") or t.startswith("ext ") or t.startswith("funext "):
        parts = t.split()
        arg = parts[1] if len(parts) > 1 else "_"
        steps.append(mk(AtomicTacticKind.INTRO, arg=arg, n=1))

    # ── trivial / tauto ───────────────────────────────────────────────────────
    elif t in ("trivial", "tauto", "aesop", "decide"):
        steps.append(mk(AtomicTacticKind.DECIDE, arg=t))

    # ── fallback: unrecognised compound tactic ────────────────────────────────
    else:
        # Emit as a single APPLY with the raw tactic string.
        # These need live-replay refinement (see pipeline.py).
        steps.append(mk(AtomicTacticKind.APPLY, arg=t, n=-1))

    return steps


# ──────────────────────────────────────────────────────────────────────────────
# 5.  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_rw_list(tactic: str) -> list[tuple[str, bool]]:
    """
    Parse the lemma list from  rw [a, ←b, c]  or  simp [a, b].
    Returns list of (lemma_name, is_symm) tuples.
    """
    import re
    m = re.search(r'\[(.*)\]', tactic, re.DOTALL)
    if not m:
        return []
    content = m.group(1)
    results = []
    for item in content.split(','):
        item = item.strip()
        if not item:
            continue
        symm = item.startswith('←') or item.startswith('<-')
        name = item.lstrip('←').lstrip('<-').strip()
        if name:
            results.append((name, symm))
    return results