"""
pantograph_bridge.py
--------------------
Interfaces with PyPantograph to:
  1. Replay a proof tactic-by-tactic and capture goal states
  2. Export kernel-level expression trees (as LeanExpr) from the goal
  3. Perform *transposition*: convert presentation-view proof terms to
     search-view metavariable assignments

Pantograph communicates via JSON over subprocess (its REPL mode).
PyPantograph is the Python wrapper: pip install pantograph
(or: uv add git+https://github.com/stanford-centaur/PyPantograph)

Reference: PyPantograph docs at https://centaur.stanford.edu/PyPantograph/
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Optional, Any

from .atomic_tactics import (
    LeanExpr, ExprKind,
    AtomicStep, AtomicTacticKind,
    atomize_expr, atomize_tactic_string,
)


# ──────────────────────────────────────────────────────────────────────────────
# 1.  JSON  →  LeanExpr   (Pantograph expression format)
# ──────────────────────────────────────────────────────────────────────────────

def json_to_lean_expr(obj: Any) -> LeanExpr:
    """
    Convert a Pantograph JSON expression object to our LeanExpr tree.

    Pantograph exports expressions in a recursive JSON structure like:
      {"tag": "app", "fn": {...}, "arg": {...}}
      {"tag": "const", "name": "Nat.succ", "levels": []}
      {"tag": "lam", "bname": "n", "domain": {...}, "body": {...}}
      {"tag": "forallE", "bname": "n", "domain": {...}, "body": {...}}
      {"tag": "fvar", "id": "fvar.42", "name": "n"}
      {"tag": "mvar", "id": "mvar.0"}
      {"tag": "sort", "level": "0"}
      {"tag": "lit", "val": {"tag": "natVal", "val": 42}}
      {"tag": "letE", "name": "x", "type": {...}, "val": {...}, "body": {...}}
      {"tag": "mdata", "expr": {...}}
      {"tag": "proj", "typeName": "Prod", "idx": 0, "expr": {...}}
    """
    if obj is None:
        return LeanExpr(kind=ExprKind.MVAR, raw="<null>")

    if isinstance(obj, str):
        # Sometimes Pantograph sends just the delaborated string
        return LeanExpr(kind=ExprKind.CONST, name=obj, raw=obj)

    tag = obj.get("tag", "")

    if tag == "app":
        fn  = json_to_lean_expr(obj.get("fn"))
        arg = json_to_lean_expr(obj.get("arg"))
        return LeanExpr(kind=ExprKind.APP, func=fn, arg=arg,
                        raw=obj.get("pp"))

    elif tag == "const":
        return LeanExpr(kind=ExprKind.CONST, name=obj.get("name", "?"),
                        raw=obj.get("pp"))

    elif tag == "fvar":
        return LeanExpr(kind=ExprKind.FVAR,
                        name=obj.get("name") or obj.get("id", "?"),
                        raw=obj.get("pp"))

    elif tag == "lam":
        return LeanExpr(
            kind=ExprKind.LAMBDA,
            binder=obj.get("bname", "_"),
            domain=json_to_lean_expr(obj.get("domain")),
            body=json_to_lean_expr(obj.get("body")),
            raw=obj.get("pp"),
        )

    elif tag == "forallE":
        return LeanExpr(
            kind=ExprKind.FORALL,
            binder=obj.get("bname", "_"),
            domain=json_to_lean_expr(obj.get("domain")),
            body=json_to_lean_expr(obj.get("body")),
            raw=obj.get("pp"),
        )

    elif tag == "sort":
        return LeanExpr(kind=ExprKind.SORT, level=str(obj.get("level", "0")),
                        raw=obj.get("pp"))

    elif tag == "lit":
        val_obj = obj.get("val", {})
        if isinstance(val_obj, dict):
            val = str(val_obj.get("val", val_obj.get("str", "?")))
        else:
            val = str(val_obj)
        return LeanExpr(kind=ExprKind.LIT, lit_val=val, raw=obj.get("pp"))

    elif tag == "letE":
        return LeanExpr(
            kind=ExprKind.LETE,
            let_name=obj.get("name", "_"),
            domain=json_to_lean_expr(obj.get("type")),
            let_val=json_to_lean_expr(obj.get("val")),
            body=json_to_lean_expr(obj.get("body")),
            raw=obj.get("pp"),
        )

    elif tag == "mdata":
        return LeanExpr(
            kind=ExprKind.MDATA,
            inner=json_to_lean_expr(obj.get("expr")),
            raw=obj.get("pp"),
        )

    elif tag == "proj":
        return LeanExpr(
            kind=ExprKind.PROJ,
            struct=obj.get("typeName", "?"),
            field_idx=obj.get("idx", 0),
            inner=json_to_lean_expr(obj.get("expr")),
            raw=obj.get("pp"),
        )

    elif tag in ("mvar", "metavar"):
        return LeanExpr(kind=ExprKind.MVAR, name=obj.get("id", "?"),
                        raw=obj.get("pp"))

    elif tag == "bvar":
        return LeanExpr(kind=ExprKind.BVAR, name=str(obj.get("idx", "?")),
                        raw=obj.get("pp"))

    # Fallback: treat as opaque constant
    return LeanExpr(kind=ExprKind.CONST,
                    name=obj.get("name") or obj.get("pp") or str(obj),
                    raw=str(obj))


# ──────────────────────────────────────────────────────────────────────────────
# 2.  GoalState wrapper around PyPantograph's output
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class GoalInfo:
    """One goal extracted from a Pantograph goal state."""
    goal_id:    int
    state_str:  str            # pretty-printed goal string
    target:     Optional[str]  = None  # pp of goal type
    context:    list[dict]     = field(default_factory=list)  # local hypotheses
    expr_tree:  Optional[LeanExpr] = None  # parsed kernel expr (if available)


def parse_pantograph_goal_state(raw_goals: list[dict]) -> list[GoalInfo]:
    """
    Convert Pantograph's raw goals list to GoalInfo objects.
    Pantograph goal format (per goal):
      {
        "goalState": "n : ℕ\n⊢ gcd n n = n",
        "id": 0,
        "target": {"tag": "app", ...},   # expression tree of goal type
        "context": [{"name": "n", "type": {...}}, ...]
      }
    """
    goals = []
    for i, g in enumerate(raw_goals):
        goal_id   = g.get("id", i)
        state_str = g.get("goalState", g.get("pp", str(g)))
        target    = g.get("target")
        ctx       = g.get("context", [])

        expr_tree = None
        if isinstance(target, dict):
            expr_tree = json_to_lean_expr(target)
        elif isinstance(target, str):
            expr_tree = LeanExpr(kind=ExprKind.CONST, name=target, raw=target)

        goals.append(GoalInfo(
            goal_id=goal_id,
            state_str=state_str,
            target=target if isinstance(target, str) else None,
            context=ctx,
            expr_tree=expr_tree,
        ))
    return goals


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Live replay via PyPantograph
# ──────────────────────────────────────────────────────────────────────────────

class PantographSession:
    """
    Thin wrapper around PyPantograph's Server for proof replay.

    Usage:
        session = PantographSession.from_imports(["Mathlib"])
        goals, steps = session.replay_theorem(
            theorem_name="Nat.gcd_self",
            tactics=["cases n", "unfold gcd", "rw [Nat.mod_self]", "apply Nat.gcd_zero_left"]
        )
    """

    def __init__(self, server):
        """Pass in a pantograph.Server instance."""
        self._server = server

    @classmethod
    def from_imports(cls, imports: list[str], project_path: Optional[str] = None) -> "PantographSession":
        """
        Create a session importing the given Lean modules.
        Requires PyPantograph to be installed:
            uv add git+https://github.com/stanford-centaur/PyPantograph
        """
        try:
            from pantograph.server import Server
        except ImportError:
            raise ImportError(
                "PyPantograph is not installed.\n"
                "Install with:  uv add git+https://github.com/stanford-centaur/PyPantograph\n"
                "See: https://github.com/stanford-centaur/PyPantograph"
            )
        server = Server(
            imports=imports,
            project_path=project_path,
            timeout=120,           # give it more time to build/start
        )
        return cls(server)

    def replay_theorem(
        self,
        theorem_name: str,
        tactics: list[str],
    ) -> list[AtomicStep]:
        """
        Replay a theorem proof step by step.
        For each (state_before, tactic) pair, emit atomic steps.

        Returns a flat list of AtomicStep objects.
        """
        all_steps: list[AtomicStep] = []

        # Start proof from theorem name (load from environment)
        try:
            state = self._server.goal_start(
                expr=f"by exact @{theorem_name}",
            )
        except Exception:
            # Fallback: start from theorem statement if available
            return []

        for tactic in tactics:
            if state is None or getattr(state, "is_solved", False):
                break

            # Get current goals
            goals_raw = _extract_goals(state)
            goals = parse_pantograph_goal_state(goals_raw)

            if not goals:
                break

            # Emit atomic steps for this tactic against the first active goal
            active_goal = goals[0]
            steps = atomize_tactic_string(
                tactic_str=tactic,
                goal_state_str=active_goal.state_str,
                theorem_name=theorem_name,
            )

            # If we have an expression tree for the goal, attach it
            if active_goal.expr_tree:
                for s in steps:
                    if s.goal_expr is None:
                        s.goal_expr = active_goal.expr_tree

            all_steps.extend(steps)

            # Advance proof state
            try:
                state = self._server.goal_tactic(state, 0, tactic)
            except Exception as e:
                # Tactic failed — proof replay broken here
                break

        return all_steps

    def atomize_from_proof_term(
        self,
        proof_term: str,
        goal_state_str: str,
        theorem_name: str,
    ) -> list[AtomicStep]:
        """
        Given a proof term expression string, ask Lean to elaborate it
        and return its kernel form, then atomize the expression tree.

        This is the full transposing atomization path.
        """
        try:
            # Ask Pantograph to elaborate the expression
            result = self._server.expr_echo(proof_term)
            if result and hasattr(result, "expr"):
                expr = json_to_lean_expr(result.expr)
                return atomize_expr(expr, goal_state_str, proof_term, theorem_name)
        except Exception:
            pass
        # Fallback to string-based atomization
        return atomize_tactic_string(proof_term, goal_state_str, theorem_name)


def _extract_goals(state) -> list[dict]:
    """Extract goal dicts from a Pantograph state object."""
    if state is None:
        return []
    # PyPantograph State has .goals attribute
    if hasattr(state, "goals"):
        raw = state.goals
        if raw is None:
            return []
        # goals is a list of Goal objects with .goal attribute (string)
        result = []
        for i, g in enumerate(raw):
            if hasattr(g, "goal"):
                result.append({"id": i, "goalState": str(g.goal)})
            elif isinstance(g, dict):
                result.append(g)
            else:
                result.append({"id": i, "goalState": str(g)})
        return result
    # Fallback: try to stringify
    return [{"id": 0, "goalState": str(state)}]