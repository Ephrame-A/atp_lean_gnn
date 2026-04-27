# Nazrin: Atomic Tactics for GNNs for Theorem Proving in Lean 4
### *A Deep Review (2026)*
**Aniva, Oikawa, Dill, Barrett — Stanford University & Northeastern University**

---

## 0. Historical Context and Core Claim

```
1986 — Resolution Method — pure logic, no learning
2016 — Holophrasm — GRUs + UCT search, Metamath
2019 — GNN paper — graph representations, HOL Light
2023 — LeanDojo/ReProver — retrieval-augmented LLMs, Lean
2026 — THIS PAPER — atomic tactics + GNNs, Lean 4
```

Every paper before this one either uses language models treating proofs as free-form text, or search algorithms over a large unbounded tactic space. Nazrin takes a fundamentally different path: **shrink the action space first, then apply a small fast GNN over that reduced space**.

The central problem: Lean's tactic space is effectively unbounded. `simp` takes arbitrarily long argument lists. `conv` allows arbitrary navigation sequences. LLMs generate tactics as free strings. This makes training noisy, classical RL intractable, and existing proofs hard to learn from.

Nazrin's solution: design a **finite, complete set of atomic tactics** — small enough for a GNN to output a probability distribution over them, powerful enough to prove anything provable in Lean. The paper makes five concrete contributions:

1. **Atomic Tactics** — a small finite set of tactics capable of proving any provable Lean statement
2. **Transposing Atomization** — an algorithm converting arbitrary proofs into atomic tactic sequences
3. **ExprGraph** — a graph representation of Lean expressions that respects mathematical symmetries
4. **Nazrin Prover** — a GNN-based prover using atomic tactics and ExprGraphs
5. **Evaluation** — demonstrating complementary capabilities with existing Lean automation

---

## 1. Background — Three Concepts You Need First

### 1.1 Metavariables and Coupling

In Lean, a **goal** is a placeholder for a proof term we need to find. These placeholders are called **metavariables**, written `?g`. Each metavariable has:
- A **type** — the statement to prove (the target)
- A **context** — the hypotheses and free variables available

For example, to prove `p ∧ q`, Lean creates goal `?g : p ∧ q`. Applying the `constructor` tactic assigns:
```
?g := ∧.intro(?hp, ?hq)
```
and generates two new goals: `?hp : p` and `?hq : q`. Both must be proved.

**Coupling** occurs when one metavariable's type mentions another. The simplest example: proving `∃x ∈ ℕ, x - 2 = 0`. The constructor tactic generates:
```
?g := ∃.intro(?x, ?p)
?x : ℕ              ← witness goal
?p : ?x - 2 = 0    ← proof goal, mentions ?x
```

`?p`'s type contains `?x`. They are **coupled** — the solution of `?x` directly affects what `?p` requires. If you set `?x := 5`, then `?p` becomes `5 - 2 = 0`. If you set `?x := 3`, `?p` becomes `3 - 2 = 0`.

This coupling is why proof search is not a simple tree but a **directed acyclic graph (DAG)**. You must track which goals depend on which, and solving one goal can cascade into solving or reshaping others.

**Cross-section** is the paper's measure of coupling complexity: the number of goals coupled to a given goal and its ancestors. A cross-section of 1 means goals are independent — easy. A cross-section of 10 means many goals are mutually entangled — hard. As a general rule: tactics that reduce cross-section are preferable to those that increase it.

### 1.2 The Three Proof Views

This distinction is one of the paper's most important conceptual contributions.

**Kernel View:** How Lean internally stores proofs — as sets of assigned and unassigned metavariables. This is Lean's ground truth, used for verification. Dense with detail, contains all metavariable coupling information.

**Presentation View:** What humans read and write. Concise, elegant, optimized for communication. Coupling is typically resolved before writing. The problem: presentation view proofs make mysterious jumps — witnesses appear from nowhere, the proof skips over the author's reasoning process. Learning from presentation view is like learning to cook from a restaurant menu — you see the final dish but not how it was made.

**Search View:** The representation that corresponds to *how you find a proof* — tracking the trajectory of an agent searching, including coupling, backtracking, and incremental construction. Consider a classic ε-δ convergence proof: you don't know δ upfront. You leave it as a placeholder `?δ`, apply the triangle inequality, work backward through the constraints, and only at the end can you solve for δ. A search view proof captures this trajectory.

The insight: **existing formalized proofs are in presentation view, but training data should be in search view**. Atomization is the algorithm that converts one to the other.

### 1.3 What "Atomic" Means

A tactic set is **atomic** if it satisfies two requirements:

**Finite:** Each atomic tactic has only a finite number of parameter possibilities. No tactic takes an arbitrary string, an arbitrary list, or an arbitrary navigation sequence. Every choice a model must make is drawn from a finite set.

**Complete:** The set is expressive enough to prove any valid Lean theorem. At least one atomic tactic corresponds to each top-level expression constructor that can appear in a proof term.

Additionally, atomic tactics should have four formal properties:
1. **Invariance:** A tactic never changes an already-assigned goal
2. **Completeness:** If a tactic removes a goal, it must assign it (no silent failures)
3. **Progress:** A tactic never produces a state containing only the goal it was just applied to (no no-ops)
4. **Determinism:** Same input always gives same output

---

## 2. Atomic Tactics — The Action Space

### 2.1 The Correspondence with Expression Constructors

The key insight behind completeness: in Lean, every proof term is built from a small set of expression constructors — lambda abstractions, function applications, constants, sorts, let binders, etc. If you have one tactic per constructor, you can build any proof.

Table 1 in the paper makes this explicit:

| Constructor | Atomic Tactic |
|---|---|
| `.sort` (type sort) | `inhabit` |
| Lambda `λx.y` | `intro` |
| Free variable | `exact`/`apply` |
| Literal | `inhabit` |
| Constant | `exact`/`apply` |
| `∀x.y` (function signature) | `pi` |
| `.app` (function application) | `tailArg` |
| `.letE` (let binder) | `unfold` |
| `.proj` (projection) | `apply`/`cases` |

Constructors labeled "Invalid" cannot appear at the top level of a proof term. Constructors labeled "Unfold" can be transformed into a different constructor first.

### 2.2 The Built-in Atomic Tactics

These are standard Lean tactics with restrictions making them finite:

**`intro`:** Applies to goal `?g : ∀x : X. Y`. Assigns `?g := λx.?h[x]` and generates new goal `?h : Y`. This is the tactic for proving universally quantified statements — introduce the variable.

**`exact(x)`:** Closes goal `?g : X` immediately by assigning `?g := x`, where `x` must already be a constant or free variable in scope. The restriction to constants/free variables already in context is what makes this finite — you're choosing from a bounded set.

**`decide`:** For decidable propositions `X`, closes the goal mechanically.

**`contradiction`:** Closes any goal when the context contains a contradiction.

**`rfl`:** Closes goal `?g : X = Y` when X and Y can be unified (definitionally equal).

**`assumption`:** Closes goal `?g : X` when some `xi : Xi` in context has `Xi = X`.

**`apply(f)`:** The most general tactic. Given `?g : Y` and `f : X1 → ... → Xn` with some suffix unifying with Y, assigns `?g := f ?g1 ... ?gi` and generates new goals for the remaining arguments.

**`cases(m)`:** Destructs a value `m : M` into its constructors, generating one subgoal per constructor.

**`induction(m, r)`:** Applies an induction principle `r` to `m`, generating one subgoal per induction case.

**`revert(i)`:** Moves a hypothesis from the context back into the goal — the inverse of `intro`.

### 2.3 The Synthetic Atomic Tactics

These are hand-crafted tactics for handling cases that the built-in tactics miss:

**`pi`:** Generates a raw `∀` binder without involving the type unification that `intro` uses. Necessary when unification would cause problems.

**`inhabit`:** For a goal whose type is a known inhabited type, fills it with the default value. No argument needed — the type determines the default.

**`reduceBeta`:** β-reduces all subexpressions in the current goal. Cleanup tactic.

**`normalize`:** Unfolds type class function calls. Necessary for goals involving arithmetic operators, which are implemented as type class methods in Lean.

**`tailArg`:** Introduces a raw unary function application. Given `?y : Y`, assigns `?y := ?f ?x` with new goals `?f : ?X → Y` and `?x : ?X`. This is a last-resort tactic that generates high cross-section — used when cleaner tactics are unavailable.

**`motivatedApply(f)`:** Like `apply`, but handles cases where the result type doesn't directly unify with the goal. Introduces an equality conduit `?c : B = Y` to bridge the gap. Also a last-resort tactic.

**`rewritePos(heq, locus, symm)`:** Rewrites using a lemma `heq` at a specific subexpression position (locus) rather than finding all matches. This is critical for neural network compatibility — the GNN can attend to a specific node in the ExprGraph and point to it directly, avoiding the complex navigation (`conv`, `congr`) that standard rewrite requires.

**`generalizeAt(locus)`:** Replaces a specific subexpression with a fresh variable. For example, replaces `2x + 3` with a fresh `y` everywhere in the goal. Again uses positions rather than pattern matching.

The positional tactics (`rewritePos` and `generalizeAt`) are a deliberate design choice enabling GNNs to work naturally: a GNN can select a node in the expression graph and say "rewrite here" without generating any navigation sequence.

---

## 3. Transposing Atomization

### 3.1 What It Does

Atomization solves the training data problem. You have 170,000+ human-written Lean proofs, all in presentation view with arbitrary complex tactics. You need search view proofs using only atomic tactics. Atomization converts one to the other.

Input: a ground-truth proof expression `proofexpr : T` (the full proof term Lean has already verified)
Output: a sequence of `(goal, atomic_tactic)` pairs that reconstruct the proof step-by-step

The key insight: if you already have a proof term, you don't need to search — you can read the proof term's structure to determine which atomic tactic was "responsible" for each piece. The proof term is essentially the answer key.

### 3.2 The Algorithm

```
function atomize(proofexpr):
    goal := Goal(infer_type(proofexpr))
    pending := [(goal, [preprocess(proofexpr)])]
    
    while (goal, solution) := pending.pop():
        if Some((tactic, goals, solutions)) := atomize_step(goal, solution):
            yield (goal, tactic)
            for (g, s) in order_predecessor(goals, solutions):
                pending.push(g, s)
        else:
            yield (goal, :defer)
```

**Preprocessing:** Before atomization, the proof expression is cleaned up. Auxiliary `simp` lemmas are unfolded (their presence in the proof term is an artifact of Lean automation, not genuine mathematical reasoning). Automatically generated matcher lemmas are unfolded. Congruence operations are standardized to `Eq.mpr` form.

**atomize_step:** Given a goal and its solution expression, tries to find an atomic tactic that (a) applies to this goal and (b) generates sub-solutions matching the sub-structure of the solution expression. Two strategies: `try_semigrade` (for tactics acting on parts of a goal) and `try_holograde` (for tactics acting on whole goals or variables).

**Example — intro:** Goal `?g : ∀(x : X), Y` with solution `λ x ↦ body`. The intro tactic corresponds to the lambda constructor. atomize_step returns `(intro, {?h : Y}, {body})` — the new goal has type Y and its solution is the lambda body. Clean and straightforward.

### 3.3 Transposition — Converting Presentation to Search Order

This is the "transposing" part of transposing atomization. In a presentation view proof, tactics appear in a logical reading order that humans find clear. In search view, the order should follow the natural discovery order — process successor goals (those that provide information about their predecessors) before predecessor goals.

**State-level transposition:** When there are multiple goals, atomize them in successor-first order. If goal `?h` is a predecessor of goal `?g` (meaning `?g`'s type mentions `?h`), atomize `?g` first. The solution of `?g` may either implicitly solve `?h` or provide crucial information about what `?h` needs to be.

This mirrors how human mathematicians actually work: in an ε-δ proof, you leave δ as a blank, work through the proof, and only fill in δ at the end when all constraints are clear. The algorithm reproduces this reasoning order.

**Goal-level transposition:** Within the sequence of tactics applied to a single goal, reorder them when safe to do so. The paper categorizes tactics by their "grade":

| Grade | Meaning | Example |
|---|---|---|
| Prograde | Acts on a free variable | `rewrite` on hypothesis |
| Retrograde | Acts on the target | `rewrite` on goal |
| Holograde | Acts on a whole variable or target | `apply`, `intro` |
| Semigrade | Acts on part of a variable or target | `rewritePos` |
| Bigrade | Acts on both target and free variable | `revert`, `induction` |
| Terminal | Closes the goal | `decide`, `rfl` |

Two semigrade tactics with non-overlapping areas of effect can be swapped freely. A prograde and retrograde tactic can be swapped. This flexibility is exploited to dispatch as many tactics as possible on a goal before deferring to predecessor goals, reducing the need for backtracking.

### 3.4 Atomization as a Difficulty Metric

A useful side effect: atomization traces give a principled measure of proof difficulty. A proof with high maximum cross-section requires simultaneous consideration of many interdependent goals. A proof with a long atomization trace requires many steps. This is more honest than "number of lines" — a proof with few but complex tactics (like `omega` closing a complicated arithmetic goal in one step) has hidden difficulty that atomization exposes.

---

## 4. ExprGraph — Representing Lean Expressions for GNNs

### 4.1 The Problem with Raw Representations

Standard string representations of Lean goals contain noise irrelevant to the mathematical argument: variable names (`a`, `b`, `x123`), metavariable names, elaboration artifacts. Two mathematically identical goals might look different as strings due to variable naming conventions.

ExprGraph is designed to capture exactly the essential mathematical structure — nothing more.

### 4.2 The Essentialization Process

Before building an ExprGraph, the expression is **essentialized** — irrelevant information is stripped:

**Variable names are erased:** Instead of named variables, ExprGraph uses positional indices. This means `∫f(x)dx` and `∫f(y)dy` produce identical ExprGraphs — they're mathematically the same.

**Proof obligations are erased:** Consider `List.head a h` — accessing the head of list `a` with certificate `h` that `a` is non-empty. How `h` was derived is irrelevant to any goal containing this expression. `h` is removed from the graph.

**Search-view equivalence:** Two goals that require the same proof steps — even if they look different in the kernel view due to auxiliary metavariables — are represented identically. This avoids training noise from irrelevant internal distinctions.

### 4.3 ExprGraph Properties

An ExprGraph `G(e)` of expression `e` has four designed properties:

**Symmetry:** α-equivalent or search-view-equivalent expressions have the same ExprGraph. Variable renaming doesn't matter.

**Self-Similarity:** If `e₁` is a subexpression of `e₂`, then `G(e₁)` is a subgraph of `G(e₂)`. This enables the GNN to naturally reason about subexpressions.

**Locus Conservation:** Every rewritable subexpression position (locus) corresponds to a unique vertex in the graph. This is critical for the positional atomic tactics — when the model selects a node in the ExprGraph for `rewritePos`, it's directly selecting the locus to rewrite.

**Condensation:** All references to the same constant, sort, or literal are merged into one shared node. This captures sharing — if the constant `Nat.add` appears three times in an expression, it's one node with three edges.

### 4.4 Why These Properties Matter Together

Self-similarity and Condensation together give ExprGraph its compression power. The example from Figure 7: the goal `gcd(x, ?f[x]) = 0` involves the metavariable `?f` and the constant `gcd`. In the ExprGraph, both the metavariable goal and the main goal share their `x : Nat` node — the GNN receives information about both goals simultaneously through this shared node.

Locus Conservation is what makes positional tactics tractable. The GNN doesn't need to generate a navigation path to find a subexpression — it directly selects the corresponding graph node.

---

## 5. The Nazrin Prover Architecture

### 5.1 The Core Challenge: GNNs Can't Generate Sequences

A language model can generate a tactic like `simp [lemma1, lemma2, ...]` as a free string. A GNN cannot — it produces a fixed-size output (embeddings, attention weights, classification probabilities), not a sequence.

Atomic tactics solve this: each tactic has only a finite number of parameters, each with a finite number of choices. So instead of generating a string, the model makes a finite sequence of categorical choices.

### 5.2 The Neural Probabilistic Automaton (NPA)

The NPA is the architecture that generates atomic tactics step by step. It's an autoregressive model where each state makes one categorical choice conditioned on the ExprGraph embedding:

```
Kind State → selects which tactic to use
   ├── intro → Exit (no parameters needed)
   ├── apply → Apply State → selects constant to apply
   ├── induction → Induction State → Major State → selects induction principle + variable
   └── rewrite → Rewrite State → Locus State → Direction State → exit
```

**Kind state:** First choice — which tactic type? Output is a categorical distribution over all atomic tactics.

**Apply state (green — premise selection):** If `apply` was chosen, select which constant/lemma to apply. This is a retrieval problem: the query is the goal's ExprGraph embedding, the keys are embeddings of all usable constants, the values are Lean constant names. The model computes dot products between the query and each constant's embedding and picks the highest-scoring one.

**Locus state (yellow — position selection):** For `rewritePos` and `generalizeAt`, select which node in the ExprGraph to act on. The GNN's per-node embeddings naturally support this — each node is a candidate, and the model scores all nodes and picks one.

**Direction state (white — fixed categorical):** For `rewrite`, select forward or backward (`←`). Binary choice.

Tactics without parameters (like `intro`, `rfl`, `decide`) go directly from Kind to Exit — no additional states needed.

### 5.3 The Four GNN Components

**Embedding layer:** Trainable embedding vectors for all known constants in the training set. On standard library: 1.5M parameters total. On Mathlib: 11M parameters — most of which are in this embedding layer.

**Core equivariant GNN:** 5 attention convolution layers, 4 heads each, GELU activation, embedding dimension 32. This is the main reasoning component — processes the ExprGraph with bidirectional message passing to produce node embeddings capturing mathematical context.

**Fixed-point invariant GNN:** Handles constants not seen during training. Given an unseen constant `c` with type `T`, constructs the ExprGraph of `T` and runs it through the core GNN, then applies a fixed-point iteration until embeddings converge. This gives every constant an embedding based on its type — even completely novel theorems from new Mathlib files the model never trained on.

**Tactic heads:** Individual small networks for each NPA state (kind, apply, locus, direction). Each head takes the aggregate graph embedding and outputs probabilities for its specific choice.

### 5.4 Rainbow Guidance

When the NPA needs to select which goal to work on (the "guidance generation problem"), Nazrin uses **rainbow guidance**: a mechanical ordering rule rather than a learned one.

If `?g ≺ ?h` (meaning `?h` is a predecessor of `?g` — `?g`'s type mentions `?h`), then assign `?h` a higher priority score. Process successors before predecessors.

This directly implements the state-level transposition idea from atomization: work on the goals that provide information about their predecessors, letting those predecessors get solved "in passing" when possible.

If there's a tie, use the ordering of goals within the current state as a tiebreaker.

### 5.5 The Abandon Action

On any goal, the model can emit a special `abandon` signal. This means: "no progress can be made here right now." Two cases:

1. The model believes the goal is currently unsolvable (wrong path — backtrack)
2. The goal's predecessors need more progress before this goal becomes tractable

The second case is subtle. Consider a coupled goal where `?x` hasn't been instantiated yet — tactics on `?x`'s dependent goal will be uninformed until `?x` is resolved. Rather than trying random tactics, abandon and work on `?x`'s predecessor first.

### 5.6 Mechanical Assistance for Simple Tactics

The `intro` tactic (strip a universal quantifier or implication) and terminal tactics (`rfl`, `decide`, `contradiction`, `assumption`) are **automatically tried** before consulting the GNN. These are cheap to try and succeed frequently. If they succeed, no GNN call is needed. This is a simple heuristic that dramatically reduces the number of expensive GNN calls in practice.

---

## 6. Evaluation

### 6.1 Setup

- Lean v4.25.2, Julia v1.12.4
- 170,180 user-defined theorems atomized from Lean standard library + Mathlib
- Atomization success rate: ~58% (42% fail due to step limit or unhandled heuristics)
- Maximum 3,000 steps per atomization
- GNN: 1.5M parameters (standard library), 11M parameters (Mathlib)
- Runs on consumer-grade CPU — no GPU required

### 6.2 Generalization Test Design

The paper tests **generalization across theorem slices**: train on slice `i`, evaluate on slice `i+1`. Theorems in later slices build on concepts introduced in earlier slices, so this tests whether Nazrin can prove theorems that use concepts it has seen but in new combinations.

Standard library: 2 slices (~10,000 theorems each)
Mathlib: 10 slices (~10,000 theorems each)

### 6.3 Results

**Standard library:** 57% accuracy on stdlib slice 2 after training on stdlib slice 1.

**Mathlib:** 34% accuracy on slice 4 after training on slice 3.

**Comparison with Aesop and Grind:** Figure 10 plots Nazrin's proving time against Aesop (a white-box best-first search tactic) and Grind (a powerful heuristic tactic). The key observation is the bottom-right data points — theorems Nazrin can prove that Aesop/Grind cannot. This demonstrates **complementary capabilities**: Nazrin succeeds on some theorems where rule-based automation fails, suggesting it has learned genuinely different proof strategies.

### 6.4 Throughput Advantage

A critical practical advantage: GNNs generate tactics in **thousands per minute**, versus seconds per tactic for LLMs. This makes highly parallelized proof search viable on modest hardware — you can explore vastly more of the search tree per unit time. A 1.5M parameter GNN on CPU is faster than a 7B parameter LLM on GPU for generating individual tactics.

### 6.5 What Cross-Section Tells Us

Figure 9 shows that most atomized theorems have low cross-section (below 10), but a long tail reaches cross-sections of 40+. Empirically, Nazrin performs worst on theorems with high cross-section and long atomization traces — confirming the theoretical expectation that coupled goals with many interdependencies are the hardest class.

---

## 7. Limitations

**Atomization coverage is 58%.** Nearly half of Lean theorems in Mathlib cannot currently be atomized — the heuristics in `atomize_step` aren't complete, and some proof terms exceed the 3,000 step limit. Future work needs to close this gap.

**High cross-section proofs remain hard.** When many goals are deeply coupled, even the best ordering heuristics can't fully tame the complexity. The model struggles most here.

**No conditioning between tactic parameters.** In an NPA state with multiple parameters (e.g., selecting the induction variable AND the induction principle), later parameters are not conditioned on earlier choices. This simplification was made for training speed but may hurt correctness — choosing the wrong induction principle should affect the variable choice.

**Numbers and strings are not handled.** The GNN doesn't process numeric literals or string arguments. These are handled by a workaround — letting Lean's type unification system solve goals involving specific numeric values "in passing" rather than explicitly.

**No online training data.** Nazrin is trained purely on supervised atomization data, not on proofs it discovers during search. Incorporating online RL from successful proofs would likely improve performance significantly.

---

## 8. Where Nazrin Sits in the Full Progression

```
Holophrasm (2016)
  Action space: all Metamath theorems (thousands)
  Selection: relevance network picks top theorems
  Generation: seq2seq generates unconstrained substitutions
  Problem: substitution space is infinite

GNN paper (2019)
  Focus: how to represent HOL formulas for neural networks
  Key insight: bidirectional message passing, context > content
  Not a complete prover — only premise selection

LeanDojo/ReProver (2023)
  Action space: all Lean tactics as free strings (unbounded)
  Selection: DPR retriever picks relevant premises
  Generation: LLM generates tactic strings
  Problem: action space is unbounded, memorization-dependent

Nazrin (2026)
  Action space: ~15 atomic tactics with finite parameters
  Selection: NPA makes categorical choices
  Generation: GNN + NPA, finite and enumerable
  Key insight: shrink the action space before training
```

The fundamental trade-off Nazrin is making: **expressiveness for tractability**. A language model can, in principle, generate any valid Lean tactic in one step. Nazrin requires multiple atomic steps to express what one complex tactic does. But each atomic step is a tractable finite choice — and the atomization algorithm proves you never lose expressiveness.

The fixed-point invariant GNN for new constants is also a meaningful contribution toward the open problem of generalization to new mathematics. Rather than failing on unseen lemmas (as LLMs trained on a fixed corpus would), Nazrin derives embeddings for new constants from their types — a form of structural generalization.

---

## 9. Summary

Nazrin's core argument is that the unbounded tactic space in Lean is not an intrinsic difficulty of theorem proving — it's an artifact of how proofs are presented. By atomizing proofs into a finite set of primitive actions, the learning problem becomes tractable for small, fast GNNs running on consumer hardware.

The five contributions form a coherent pipeline:

```
Existing human proofs (presentation view)
        ↓ Transposing Atomization
Atomic tactic sequences (search view)
        ↓ Essentialization
ExprGraphs (noise-free graph representations)
        ↓ GNN + NPA
Categorical tactic choices
        ↓ Contextualization
Valid Lean 4 tactics
```

The result is a prover that is small (1.5M–11M parameters), fast (thousands of tactics per minute), runs without a GPU, and proves theorems that Aesop and Grind cannot — demonstrating genuine complementarity with existing Lean automation.