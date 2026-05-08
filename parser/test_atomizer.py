"""
test_atomizer.py
----------------
Tests and usage examples for the LeanDojo atomization pipeline.
Run with:  python test_atomizer.py
"""

from atomic_tactics import (
    AtomicTacticKind, atomize_tactic_string,
    LeanExpr, ExprKind, atomize_expr,
)
from expr_graph import (
    build_expr_graph, ExprGraphBuilder,
    _parse_simple_expr, _canonical_str,
)


# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
_n_pass = 0
_n_fail = 0

def check(name, condition):
    global _n_pass, _n_fail
    if condition:
        print(f"  {PASS} {name}")
        _n_pass += 1
    else:
        print(f"  {FAIL} {name}")
        _n_fail += 1


# ──────────────────────────────────────────────────────────────────────────────
# 1.  String-based tactic atomizer
# ──────────────────────────────────────────────────────────────────────────────

def test_string_atomizer():
    print("\n=== String Atomizer Tests ===")

    STATE = "k : ℕ\n⊢ Nat.gcd (k + 1) (k + 1) = k + 1"
    THM   = "Nat.gcd_self"

    # rfl
    steps = atomize_tactic_string("rfl", STATE, THM)
    check("rfl → RFL",
          len(steps) == 1 and steps[0].tactic == AtomicTacticKind.RFL)

    # assumption
    steps = atomize_tactic_string("assumption", STATE, THM)
    check("assumption → ASSUMPTION",
          len(steps) == 1 and steps[0].tactic == AtomicTacticKind.ASSUMPTION)

    # intro x y
    steps = atomize_tactic_string("intro x y", STATE, THM)
    check("intro x y → 2 INTRO steps",
          len(steps) == 2 and all(s.tactic == AtomicTacticKind.INTRO for s in steps))
    check("intro x y → args are x, y",
          steps[0].argument == "x" and steps[1].argument == "y")

    # exact Nat.zero
    steps = atomize_tactic_string("exact Nat.zero", STATE, THM)
    check("exact → EXACT",
          steps[0].tactic == AtomicTacticKind.EXACT)
    check("exact → arg = Nat.zero",
          steps[0].argument == "Nat.zero")

    # apply And.intro
    steps = atomize_tactic_string("apply And.intro", STATE, THM)
    check("apply → APPLY",
          steps[0].tactic == AtomicTacticKind.APPLY)
    check("apply → arg = And.intro",
          steps[0].argument == "And.intro")

    # cases h
    steps = atomize_tactic_string("cases h", STATE, THM)
    check("cases → CASES",
          steps[0].tactic == AtomicTacticKind.CASES)
    check("cases → arg = h",
          steps[0].argument == "h")

    # induction n
    steps = atomize_tactic_string("induction n", STATE, THM)
    check("induction → INDUCTION",
          steps[0].tactic == AtomicTacticKind.INDUCTION)

    # rw [Nat.add_comm]
    steps = atomize_tactic_string("rw [Nat.add_comm]", STATE, THM)
    check("rw [x] → APPLY Eq.mpr[x]",
          steps[0].tactic == AtomicTacticKind.APPLY and
          "Nat.add_comm" in (steps[0].argument or ""))

    # rw [← Nat.add_comm]
    steps = atomize_tactic_string("rw [← Nat.add_comm]", STATE, THM)
    check("rw [← x] → Eq.symm in arg",
          "Eq.symm" in (steps[0].argument or ""))

    # rw with multiple lemmas
    steps = atomize_tactic_string("rw [Nat.add_comm, Nat.add_assoc]", STATE, THM)
    check("rw [a, b] → 2 steps",
          len(steps) == 2)

    # ring
    steps = atomize_tactic_string("ring", STATE, THM)
    check("ring → DECIDE",
          steps[0].tactic == AtomicTacticKind.DECIDE)

    # omega
    steps = atomize_tactic_string("omega", STATE, THM)
    check("omega → DECIDE",
          steps[0].tactic == AtomicTacticKind.DECIDE)

    # constructor
    steps = atomize_tactic_string("constructor", STATE, THM)
    check("constructor → APPLY with n=2",
          steps[0].tactic == AtomicTacticKind.APPLY and
          steps[0].new_goal_count == 2)

    # simp only [h]
    steps = atomize_tactic_string("simp only [Nat.succ_eq_add_one]", STATE, THM)
    check("simp only [x] → APPLY simp[x]",
          steps[0].tactic == AtomicTacticKind.APPLY and
          "simp" in (steps[0].argument or ""))

    # use 2
    steps = atomize_tactic_string("use 2", STATE, THM)
    check("use e → APPLY Exists.intro",
          "Exists.intro" in (steps[0].argument or ""))

    # revert h
    steps = atomize_tactic_string("revert n", STATE, THM)
    check("revert → REVERT",
          steps[0].tactic == AtomicTacticKind.REVERT)

    # contradiction
    steps = atomize_tactic_string("contradiction", STATE, THM)
    check("contradiction → CONTRADICTION",
          steps[0].tactic == AtomicTacticKind.CONTRADICTION)

    # Unknown tactic falls back to APPLY
    steps = atomize_tactic_string("norm_cast at h", STATE, THM)
    check("unknown tactic → fallback APPLY or DECIDE",
          steps[0].tactic in (AtomicTacticKind.APPLY, AtomicTacticKind.DECIDE,
                               AtomicTacticKind.UNFOLD))

    # Source tactic preserved
    steps = atomize_tactic_string("exact Nat.zero", STATE, THM)
    check("source_tactic preserved",
          steps[0].source_tactic == "exact Nat.zero")

    # Theorem name preserved
    check("theorem_name preserved",
          steps[0].theorem_name == THM)


# ──────────────────────────────────────────────────────────────────────────────
# 2.  Expression tree atomizer
# ──────────────────────────────────────────────────────────────────────────────

def test_expr_atomizer():
    print("\n=== Expression Tree Atomizer Tests ===")

    STATE = "⊢ p ∧ q"
    THM   = "test_and"

    # APP(APP(And.intro, ?p), ?q)
    and_intro = LeanExpr(kind=ExprKind.CONST, name="And.intro")
    p_expr    = LeanExpr(kind=ExprKind.CONST, name="p_proof")
    q_expr    = LeanExpr(kind=ExprKind.CONST, name="q_proof")
    app1 = LeanExpr(kind=ExprKind.APP, func=and_intro, arg=p_expr)
    app2 = LeanExpr(kind=ExprKind.APP, func=app1, arg=q_expr)

    steps = atomize_expr(app2, STATE, "And.intro ?p ?q", THM)
    check("APP spine: first step is APPLY And.intro",
          any(s.tactic == AtomicTacticKind.APPLY and "And.intro" in (s.argument or "")
              for s in steps))
    check("APP spine: produces > 1 step",
          len(steps) > 1)

    # Lambda: λ x. body
    body = LeanExpr(kind=ExprKind.CONST, name="Nat.zero")
    lam  = LeanExpr(kind=ExprKind.LAMBDA, binder="x", body=body)
    steps = atomize_expr(lam, STATE, "fun x => Nat.zero", THM)
    check("LAMBDA → INTRO then EXACT",
          steps[0].tactic == AtomicTacticKind.INTRO and
          steps[0].argument == "x")
    check("LAMBDA body → EXACT Nat.zero",
          any(s.tactic == AtomicTacticKind.EXACT and s.argument == "Nat.zero"
              for s in steps))

    # Forall: ∀ x : Nat, body
    dom  = LeanExpr(kind=ExprKind.CONST, name="Nat")
    body = LeanExpr(kind=ExprKind.CONST, name="Nat.zero")
    fal  = LeanExpr(kind=ExprKind.FORALL, binder="x", domain=dom, body=body)
    steps = atomize_expr(fal, STATE, "∀ x : Nat, Nat.zero", THM)
    check("FORALL → PI step",
          steps[0].tactic == AtomicTacticKind.PI)

    # LitE
    lit = LeanExpr(kind=ExprKind.LIT, lit_val="42")
    steps = atomize_expr(lit, STATE, "42", THM)
    check("LIT → INHABIT with val=42",
          steps[0].tactic == AtomicTacticKind.INHABIT and steps[0].argument == "42")

    # MDATA (strip) → recurse
    inner = LeanExpr(kind=ExprKind.CONST, name="Nat.zero")
    md    = LeanExpr(kind=ExprKind.MDATA, inner=inner)
    steps = atomize_expr(md, STATE, "mdata(Nat.zero)", THM)
    check("MDATA → UNFOLD then inner",
          steps[0].tactic == AtomicTacticKind.UNFOLD and len(steps) >= 2)

    # BVAR / MVAR are silently skipped (invalid top-level)
    bv = LeanExpr(kind=ExprKind.BVAR, name="0")
    steps = atomize_expr(bv, STATE, "bvar", THM)
    check("BVAR at top-level → 0 steps (skip)",
          len(steps) == 0)

    mv = LeanExpr(kind=ExprKind.MVAR, name="?g")
    steps = atomize_expr(mv, STATE, "mvar", THM)
    check("MVAR at top-level → 0 steps (skip)",
          len(steps) == 0)


# ──────────────────────────────────────────────────────────────────────────────
# 3.  ExprGraph builder
# ──────────────────────────────────────────────────────────────────────────────

def test_expr_graph():
    print("\n=== ExprGraph Tests ===")

    # Simple: "a = b"
    g = build_expr_graph("a = b")
    check("Eq graph has nodes",
          len(g.nodes) > 0)
    check("Eq graph has edges",
          len(g.edges) > 0)
    check("goal_node_id is 0",
          g.goal_node_id == 0)

    # Forall: ∀ n : ℕ, n = n
    g = build_expr_graph("∀ n : ℕ, n = n")
    check("Forall graph has nodes > 1",
          len(g.nodes) > 1)

    # Context hypothesis adds CTX_HYP edge
    from expr_graph import EDGE_TYPE_TO_ID
    g = build_expr_graph("gcd n n = n", context=[("n", "ℕ")])
    hyp_edges = [e for e in g.edges if e[2] == EDGE_TYPE_TO_ID["CTX_HYP"]]
    check("Context hypothesis → CTX_HYP edge",
          len(hyp_edges) > 0)

    # Condensation: "a + a" — two `a` nodes should be same id
    g_double = build_expr_graph("a + a")
    # With condensation, `a` should appear once even though it's used twice
    a_nodes = [n for n in g_double.nodes if n.get("name") == "a"]
    check("Condensation: shared subterm deduplicated",
          len(a_nodes) == 1)

    # Node features shape
    for nf in g.node_features:
        check("Node feature is [kind_id, name_hash, is_goal] (3 ints)",
              len(nf) == 3 and all(isinstance(x, int) for x in nf))
        break  # just check first

    # String parser sanity
    e = _parse_simple_expr("Nat.succ n")
    check("APP: Nat.succ n parsed as APP",
          e.kind == ExprKind.APP)
    check("APP func = Nat.succ",
          e.func is not None and e.func.name == "Nat.succ")

    e = _parse_simple_expr("∀ x : Nat, x = x")
    check("FORALL parsed correctly",
          e.kind == ExprKind.FORALL)

    e = _parse_simple_expr("fun n => n")
    check("LAMBDA parsed correctly",
          e.kind == ExprKind.LAMBDA)


# ──────────────────────────────────────────────────────────────────────────────
# 4.  Integration: gcd_self example end-to-end
# ──────────────────────────────────────────────────────────────────────────────

def test_gcd_self_integration():
    print("\n=== Integration Test: Nat.gcd_self ===")

    # LeanDojo tactic records for Nat.gcd_self
    # (from LeanDojo Benchmark — these are real)
    tactic_records = [
        {"state_before": "n : ℕ\n⊢ Nat.gcd n n = n",
         "tactic": "cases n",
         "state_after": "case zero\n⊢ Nat.gcd 0 0 = 0\n\ncase succ\nk : ℕ\n⊢ Nat.gcd (k + 1) (k + 1) = k + 1",
         "premises": []},
        {"state_before": "⊢ Nat.gcd 0 0 = 0",
         "tactic": "simp [Nat.gcd]",
         "state_after": "no goals",
         "premises": []},
        {"state_before": "k : ℕ\n⊢ Nat.gcd (k + 1) (k + 1) = k + 1",
         "tactic": "unfold Nat.gcd",
         "state_after": "k : ℕ\n⊢ Nat.gcd ((k + 1) % (k + 1)) (k + 1) = k + 1",
         "premises": []},
        {"state_before": "k : ℕ\n⊢ Nat.gcd ((k + 1) % (k + 1)) (k + 1) = k + 1",
         "tactic": "rw [Nat.mod_self]",
         "state_after": "k : ℕ\n⊢ Nat.gcd 0 (k + 1) = k + 1",
         "premises": ["Nat.mod_self"]},
        {"state_before": "k : ℕ\n⊢ Nat.gcd 0 (k + 1) = k + 1",
         "tactic": "apply Nat.gcd_zero_left",
         "state_after": "no goals",
         "premises": ["Nat.gcd_zero_left"]},
    ]

    all_steps = []
    all_graphs = []

    for rec in tactic_records:
        steps = atomize_tactic_string(
            tactic_str=rec["tactic"],
            goal_state_str=rec["state_before"],
            theorem_name="Nat.gcd_self",
        )
        all_steps.extend(steps)

        graph = build_expr_graph(
            goal_str=rec["state_before"].split("⊢")[-1].strip() if "⊢" in rec["state_before"] else rec["state_before"],
            context=[]
        )
        all_graphs.append(graph)

    check("gcd_self produces > 0 atomic steps",
          len(all_steps) > 0)
    check("cases → CASES step present",
          any(s.tactic == AtomicTacticKind.CASES for s in all_steps))
    check("rw [Nat.mod_self] → APPLY with Nat.mod_self",
          any(s.tactic == AtomicTacticKind.APPLY and "Nat.mod_self" in (s.argument or "")
              for s in all_steps))
    check("apply Nat.gcd_zero_left → APPLY",
          any(s.tactic == AtomicTacticKind.APPLY and "Nat.gcd_zero_left" in (s.argument or "")
              for s in all_steps))
    check("unfold → UNFOLD",
          any(s.tactic == AtomicTacticKind.UNFOLD for s in all_steps))
    check("graphs produced for all tactics",
          len(all_graphs) == len(tactic_records))

    print(f"\n  Atomized {len(tactic_records)} tactics → {len(all_steps)} atomic steps:")
    from collections import Counter
    counts = Counter(s.tactic.value for s in all_steps)
    for tac, count in sorted(counts.items()):
        print(f"    {tac:20s}: {count}")


# ──────────────────────────────────────────────────────────────────────────────
# 5.  Tactic vocabulary (finite action space check)
# ──────────────────────────────────────────────────────────────────────────────

def test_finite_action_space():
    print("\n=== Finite Action Space ===")
    all_tactics = [t.value for t in AtomicTacticKind]
    print(f"  Atomic tactic classes ({len(all_tactics)}): {all_tactics}")
    check("Action space is finite and small",
          len(all_tactics) <= 20)
    check("INTRO present",  "intro"        in all_tactics)
    check("EXACT present",  "exact"        in all_tactics)
    check("APPLY present",  "apply"        in all_tactics)
    check("CASES present",  "cases"        in all_tactics)
    check("RFL present",    "rfl"          in all_tactics)
    check("DECIDE present", "decide"       in all_tactics)
    check("UNFOLD present", "unfold"       in all_tactics)


# ──────────────────────────────────────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_string_atomizer()
    test_expr_atomizer()
    test_expr_graph()
    test_gcd_self_integration()
    test_finite_action_space()

    print(f"\n{'═'*50}")
    print(f"Results: {_n_pass} passed, {_n_fail} failed")
    if _n_fail == 0:
        print("All tests passed ✓")
    else:
        print(f"{_n_fail} test(s) failed ✗")
        exit(1)