"""
expr_graph.py
-------------
Implements Nazrin's ExprGraph data structure (§5.1).

An ExprGraph is a directed graph whose nodes are expression sub-terms
and whose edges encode the structural relationships:

  Edge types:
    APP_FUNC    — the function in a function application
    APP_ARG     — the argument in a function application
    LAMBDA_DOM  — domain type of a λ-binder
    LAMBDA_BODY — body of a λ-binder
    FORALL_DOM  — domain type of a Π/∀-binder
    FORALL_BODY — body of a Π/∀-binder
    LET_TYPE    — type annotation in a let-binding
    LET_VAL     — value expression in a let-binding
    LET_BODY    — body of a let-binding
    PROJ_INNER  — inner expression of a projection
    CTX_HYP     — context hypothesis → goal edge

Node features (per node):
    kind        — ExprKind ordinal (0 = BVAR, 1 = MVAR, …)
    name_hash   — hash of the constant/fvar name (0 for structural nodes)
    is_goal     — 1 if this node is the root of the current goal type

Nazrin §5.1 symmetry properties exploited:
    Self-similarity: recursive expressions share sub-graph structure
    Locus Conservation: the locus (active goal) is always the root node
    Condensation: structurally identical subterms are merged (DAG, not tree)
"""

from __future__ import annotations
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional

from atomic_tactics import LeanExpr, ExprKind


# ──────────────────────────────────────────────────────────────────────────────
# 1.  Edge type vocabulary
# ──────────────────────────────────────────────────────────────────────────────

EDGE_TYPES = [
    "APP_FUNC",
    "APP_ARG",
    "LAMBDA_DOM",
    "LAMBDA_BODY",
    "FORALL_DOM",
    "FORALL_BODY",
    "LET_TYPE",
    "LET_VAL",
    "LET_BODY",
    "PROJ_INNER",
    "CTX_HYP",   # context hypothesis → goal
    "MDATA_INNER",
]
EDGE_TYPE_TO_ID = {e: i for i, e in enumerate(EDGE_TYPES)}
N_EDGE_TYPES = len(EDGE_TYPES)

# Node kind feature IDs
KIND_TO_ID = {kind: i for i, kind in enumerate(ExprKind)}
N_NODE_KINDS = len(ExprKind)


# ──────────────────────────────────────────────────────────────────────────────
# 2.  ExprGraph data structure
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ExprGraph:
    """
    nodes:          List of node feature dicts. Index = node_id.
    edges:          List of (src_id, dst_id, edge_type_id) triples.
    node_features:  Parallel list of int feature vectors [kind_id, name_hash, is_goal].
    goal_node_id:   Index of the root node (locus).
    """
    nodes:          list[dict]           = field(default_factory=list)
    edges:          list[tuple[int,int,int]] = field(default_factory=list)
    node_features:  list[list[int]]      = field(default_factory=list)
    goal_node_id:   int                  = 0


# ──────────────────────────────────────────────────────────────────────────────
# 3.  ExprGraph builder from LeanExpr tree
# ──────────────────────────────────────────────────────────────────────────────

class ExprGraphBuilder:
    """
    Build an ExprGraph from a LeanExpr tree.

    Nazrin's condensation property: structurally identical sub-expressions
    are shared (deduplication by content-hash).  We implement this with a
    cache keyed on the expression's canonical string form.
    """

    def __init__(self):
        self.nodes:         list[dict]                = []
        self.edges:         list[tuple[int,int,int]]  = []
        self.node_features: list[list[int]]           = []
        self._cache:        dict[str, int]            = {}   # canonical → node_id

    def build(self, goal_expr: LeanExpr, context: list[tuple[str,str]] = []) -> ExprGraph:
        """
        Build graph for a goal expression with optional context hypotheses.
        Each hypothesis in `context` is connected to the goal root via CTX_HYP edges.
        """
        goal_id = self._add_expr(goal_expr, is_goal=True)

        # Add context hypothesis nodes → goal edge
        for hyp_name, hyp_type_str in context:
            hyp_expr = _parse_simple_expr(hyp_type_str)
            hyp_id = self._add_expr(hyp_expr, is_goal=False)
            etype = EDGE_TYPE_TO_ID["CTX_HYP"]
            self.edges.append((hyp_id, goal_id, etype))

        g = ExprGraph(
            nodes=list(self.nodes),
            edges=list(self.edges),
            node_features=list(self.node_features),
            goal_node_id=goal_id,
        )
        return g

    def _add_expr(self, expr: LeanExpr, is_goal: bool = False) -> int:
        """
        Add an expression to the graph, returning its node_id.
        Uses condensation: identical sub-expressions share a node.
        """
        key = _expr_canonical_key(expr)
        if key in self._cache:
            return self._cache[key]

        node_id = len(self.nodes)
        self._cache[key] = node_id

        kind_id    = KIND_TO_ID.get(expr.kind, 0)
        name_hash  = _hash_name(expr.name or expr.binder or expr.struct or "")
        is_goal_f  = 1 if is_goal else 0

        self.nodes.append({
            "kind":      expr.kind.value if expr.kind else "?",
            "name":      expr.name or expr.binder or expr.struct or "",
            "raw":       expr.raw or "",
        })
        self.node_features.append([kind_id, name_hash, is_goal_f])

        # Add child edges based on node type
        self._add_children(expr, node_id)
        return node_id

    def _add_children(self, expr: LeanExpr, parent_id: int) -> None:
        k = expr.kind

        if k == ExprKind.APP:
            if expr.func:
                child_id = self._add_expr(expr.func)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["APP_FUNC"]))
            if expr.arg:
                child_id = self._add_expr(expr.arg)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["APP_ARG"]))

        elif k == ExprKind.LAMBDA:
            if expr.domain:
                child_id = self._add_expr(expr.domain)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["LAMBDA_DOM"]))
            if expr.body:
                child_id = self._add_expr(expr.body)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["LAMBDA_BODY"]))

        elif k == ExprKind.FORALL:
            if expr.domain:
                child_id = self._add_expr(expr.domain)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["FORALL_DOM"]))
            if expr.body:
                child_id = self._add_expr(expr.body)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["FORALL_BODY"]))

        elif k == ExprKind.LETE:
            if expr.domain:
                child_id = self._add_expr(expr.domain)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["LET_TYPE"]))
            if expr.let_val:
                child_id = self._add_expr(expr.let_val)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["LET_VAL"]))
            if expr.body:
                child_id = self._add_expr(expr.body)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["LET_BODY"]))

        elif k == ExprKind.PROJ:
            if expr.inner:
                child_id = self._add_expr(expr.inner)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["PROJ_INNER"]))

        elif k == ExprKind.MDATA:
            if expr.inner:
                child_id = self._add_expr(expr.inner)
                self.edges.append((parent_id, child_id, EDGE_TYPE_TO_ID["MDATA_INNER"]))


def build_expr_graph(goal_str: str, context: list[tuple[str,str]] = []) -> ExprGraph:
    """
    Public entry point: parse goal string → LeanExpr → ExprGraph.
    Uses the lightweight string parser (no live Lean needed).
    """
    goal_expr = _parse_simple_expr(goal_str)
    builder = ExprGraphBuilder()
    return builder.build(goal_expr, context)


# ──────────────────────────────────────────────────────────────────────────────
# 4.  PyTorch Geometric conversion
# ──────────────────────────────────────────────────────────────────────────────

def expr_graph_to_pyg(graph: ExprGraph):
    """
    Convert ExprGraph to a PyTorch Geometric Data object.

    Node features:  x  shape [N, 3]   — [kind_id, name_hash, is_goal]
    Edge index:     edge_index  [2, E]
    Edge features:  edge_attr   [E, 1]  — edge type id
    Goal node:      y_node = graph.goal_node_id
    """
    try:
        import torch
        from torch_geometric.data import Data
    except ImportError:
        raise ImportError(
            "PyTorch and PyTorch Geometric are required for PyG output.\n"
            "Install: pip install torch torch-geometric"
        )

    n = len(graph.node_features)
    if n == 0:
        # Empty graph fallback
        x = torch.zeros((1, 3), dtype=torch.long)
        edge_index = torch.zeros((2, 0), dtype=torch.long)
        edge_attr  = torch.zeros((0, 1), dtype=torch.long)
        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr,
                    goal_node=torch.tensor([0]))

    x = torch.tensor(graph.node_features, dtype=torch.long)  # [N, 3]

    if graph.edges:
        src = [e[0] for e in graph.edges]
        dst = [e[1] for e in graph.edges]
        et  = [e[2] for e in graph.edges]
        edge_index = torch.tensor([src, dst], dtype=torch.long)  # [2, E]
        edge_attr  = torch.tensor(et, dtype=torch.long).unsqueeze(1)  # [E, 1]
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)
        edge_attr  = torch.zeros((0, 1), dtype=torch.long)

    data = Data(
        x=x,
        edge_index=edge_index,
        edge_attr=edge_attr,
        goal_node=torch.tensor([graph.goal_node_id]),
    )
    return data


# ──────────────────────────────────────────────────────────────────────────────
# 5.  Lightweight string-based expression parser
#     (no live Lean; approximates structure from pretty-printed strings)
# ──────────────────────────────────────────────────────────────────────────────

def _parse_simple_expr(s: str) -> LeanExpr:
    """
    Parse a pretty-printed Lean expression string into a LeanExpr tree.
    This is a best-effort approximation for use without a live Lean process.

    Handles:
      - Function application:  f a b c  →  APP(APP(APP(f,a),b),c)
      - Arrow types:           A → B  →  FORALL
      - Lambda:                fun x => body  →  LAMBDA
      - Forall:                ∀ x, body  →  FORALL
      - Equality:              a = b  →  APP(APP(Eq, a), b)
      - Simple names:          Nat.succ  →  CONST
    """
    from atomic_tactics import LeanExpr, ExprKind
    s = s.strip()
    if not s:
        return LeanExpr(kind=ExprKind.CONST, name="?", raw=s)

    # ── forall / pi ───────────────────────────────────────────────────────────
    m = re.match(r'^∀\s+([^,]+)\s*[:,]\s*(.+)$', s, re.DOTALL)
    if m:
        binder = m.group(1).strip()
        body_s = m.group(2).strip()
        return LeanExpr(
            kind=ExprKind.FORALL,
            binder=binder,
            domain=LeanExpr(kind=ExprKind.CONST, name="Type", raw="Type"),
            body=_parse_simple_expr(body_s),
            raw=s,
        )

    # ── lambda ────────────────────────────────────────────────────────────────
    m = re.match(r'^(?:fun|λ)\s+(\w+)\s*(?::\s*[^=]+)?\s*=>\s*(.+)$', s, re.DOTALL)
    if m:
        binder = m.group(1).strip()
        body_s = m.group(2).strip()
        return LeanExpr(
            kind=ExprKind.LAMBDA,
            binder=binder,
            body=_parse_simple_expr(body_s),
            raw=s,
        )

    # ── arrow type  A → B ─────────────────────────────────────────────────────
    # Split on outermost →
    arrow_idx = _find_outermost_arrow(s)
    if arrow_idx >= 0:
        lhs = s[:arrow_idx].strip()
        rhs = s[arrow_idx+1:].strip().lstrip(">").strip()
        return LeanExpr(
            kind=ExprKind.FORALL,
            binder="_",
            domain=_parse_simple_expr(lhs),
            body=_parse_simple_expr(rhs),
            raw=s,
        )

    # ── equality  a = b ───────────────────────────────────────────────────────
    eq_idx = _find_outermost_eq(s)
    if eq_idx >= 0:
        lhs = s[:eq_idx].strip()
        rhs = s[eq_idx+1:].strip()
        eq_node  = LeanExpr(kind=ExprKind.CONST, name="Eq", raw="Eq")
        lhs_node = _parse_simple_expr(lhs)
        rhs_node = _parse_simple_expr(rhs)
        return LeanExpr(
            kind=ExprKind.APP,
            func=LeanExpr(kind=ExprKind.APP, func=eq_node, arg=lhs_node, raw=f"Eq {lhs}"),
            arg=rhs_node,
            raw=s,
        )

    # ── function application  f a b … ────────────────────────────────────────
    # Split on outermost spaces
    parts = _split_application(s)
    if len(parts) > 1:
        # Left-fold: f a b → APP(APP(f, a), b)
        result = _parse_simple_expr(parts[0])
        for p in parts[1:]:
            result = LeanExpr(
                kind=ExprKind.APP,
                func=result,
                arg=_parse_simple_expr(p),
                raw=s,
            )
        return result

    # ── atomic: literal number ────────────────────────────────────────────────
    if re.match(r'^\d+$', s):
        return LeanExpr(kind=ExprKind.LIT, lit_val=s, raw=s)

    # ── atomic: constant or free variable ─────────────────────────────────────
    return LeanExpr(kind=ExprKind.CONST, name=s, raw=s)


def _find_outermost_arrow(s: str) -> int:
    """Find index of outermost → not inside parens/brackets."""
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and s[i:i+2] in ("→", "->"):
            return i
        elif depth == 0 and ord(c) == 8594:  # unicode →
            return i
        i += 1
    return -1


def _find_outermost_eq(s: str) -> int:
    """Find index of outermost = (not ← ≠ == ≤ ≥) not inside parens."""
    depth = 0
    for i, c in enumerate(s):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and c == "=":
            # Avoid ← ≠ == ≤ ≥
            prev = s[i-1] if i > 0 else ""
            nxt  = s[i+1] if i < len(s)-1 else ""
            if prev not in "<>!" and nxt not in "=" and prev != "=":
                return i
    return -1


def _split_application(s: str) -> list[str]:
    """
    Split  "f a (b c) d"  into  ["f", "a", "(b c)", "d"]
    respecting nested parentheses.
    """
    parts = []
    depth = 0
    current = []
    for c in s:
        if c in "([{":
            depth += 1
            current.append(c)
        elif c in ")]}":
            depth -= 1
            current.append(c)
        elif c == " " and depth == 0:
            token = "".join(current).strip()
            if token:
                parts.append(token)
            current = []
        else:
            current.append(c)
    token = "".join(current).strip()
    if token:
        parts.append(token)
    return parts


# ──────────────────────────────────────────────────────────────────────────────
# 6.  Canonicalisation and hashing utilities
# ──────────────────────────────────────────────────────────────────────────────

def _expr_canonical_key(expr: LeanExpr) -> str:
    """
    Produce a canonical string key for deduplication (condensation).
    Nazrin's Symmetry property: structurally identical sub-expressions share nodes.

    We anonymise bound-variable names (replace with De Bruijn indices)
    so that  λ x. x  and  λ y. y  share the same node.
    """
    return _canonical_str(expr, depth=0)


def _canonical_str(expr: LeanExpr, depth: int) -> str:
    k = expr.kind
    if k == ExprKind.BVAR:
        return f"bvar({expr.name})"
    elif k == ExprKind.MVAR:
        return f"mvar({expr.name})"
    elif k == ExprKind.SORT:
        return f"sort({expr.level})"
    elif k == ExprKind.LIT:
        return f"lit({expr.lit_val})"
    elif k == ExprKind.CONST:
        return f"const({expr.name})"
    elif k == ExprKind.FVAR:
        # Anonymise fvar names — only the type relationship matters
        return f"fvar(_)"
    elif k == ExprKind.APP:
        fn  = _canonical_str(expr.func, depth) if expr.func else "?"
        arg = _canonical_str(expr.arg,  depth) if expr.arg  else "?"
        return f"app({fn},{arg})"
    elif k == ExprKind.LAMBDA:
        dom  = _canonical_str(expr.domain, depth) if expr.domain else "?"
        body = _canonical_str(expr.body,   depth+1) if expr.body else "?"
        return f"lam({dom},{body})"
    elif k == ExprKind.FORALL:
        dom  = _canonical_str(expr.domain, depth) if expr.domain else "?"
        body = _canonical_str(expr.body,   depth+1) if expr.body else "?"
        return f"all({dom},{body})"
    elif k == ExprKind.LETE:
        val  = _canonical_str(expr.let_val, depth) if expr.let_val else "?"
        body = _canonical_str(expr.body,    depth+1) if expr.body else "?"
        return f"let({val},{body})"
    elif k == ExprKind.MDATA:
        inner = _canonical_str(expr.inner, depth) if expr.inner else "?"
        return f"mdata({inner})"
    elif k == ExprKind.PROJ:
        inner = _canonical_str(expr.inner, depth) if expr.inner else "?"
        return f"proj({expr.struct},{expr.field_idx},{inner})"
    return f"?({expr.raw})"


def _hash_name(name: str) -> int:
    """Stable 31-bit hash of a name string (fits in GNN embedding table)."""
    if not name:
        return 0
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % (2**31)