# Lean for ATP: A Beginner-First Guide

## Purpose

This guide is for learning the Lean concepts you need in order to understand this repository and move toward automated theorem proving (ATP).

It is written for the case where Lean still feels unfamiliar.

The main goal is not to make you memorize syntax. The goal is to make the core ideas feel intuitive:

- what a theorem is
- what a proof state is
- what a tactic is
- what hypotheses and goals are
- what lemmas and premises are
- what it means to search for a proof
- how all of that connects to this repo

If you understand this document well, the rest of the project will feel much less mysterious.

## The Big Picture

Lean is a proof assistant. You write mathematical statements and then prove them in a language the computer can check exactly.

The simplest mental model is:

- a theorem is a statement you want to prove
- a proof is a sequence of justified steps
- Lean checks that every step is valid

This is similar to ordinary mathematics, except nothing is allowed to be vague.

In ordinary math, someone might write:

> Clearly, this follows by transitivity.

In Lean, you must tell the system exactly what "this" is and exactly which transitivity fact you are using.

That is why Lean is useful for theorem proving research. It turns proofs into precise computational objects.

## Why Lean Matters for This Repo

This repository is not a generic graph-learning project. It is a Lean-oriented theorem-proving project.

The repo currently does this:

1. read Lean proof states
2. parse them into structured expressions
3. build a graph representation
4. train a graph neural network to predict the next tactic

So if Lean concepts are unclear, the whole repo feels harder than it really is.

The most important thing to understand is:

- Lean gives us the formal proof world
- this repo gives us a graph-based machine-learning view of that world

## The Core Lean Vocabulary

These are the words you should know first.

### Theorem

A theorem is a statement to prove.

Example:

```lean
theorem add_zero_example (n : Nat) : n + 0 = n := by
  simp
```

Here the theorem says: for every natural number `n`, `n + 0 = n`.

### Proof

A proof is the sequence of steps that shows the theorem is true.

In Lean, the proof starts after `:=` or after `by`.

### Goal

A goal is the statement you still need to prove at the current step.

When you are in the middle of a proof, Lean always has a current goal.

### Hypothesis

A hypothesis is a fact already available in the current local context.

Example:

```lean
h : a = b
```

This means you already know `a = b`.

### Context

The context is the list of local variables and hypotheses you currently have.

Example:

```lean
a b : Nat
h : a = b
```

This says the current context contains:

- two natural numbers `a` and `b`
- one hypothesis `h` saying `a = b`

### Proof State

A proof state is:

- the current context
- the current goal

Example:

```lean
a b : Nat
h : a = b
⊢ b = a
```

Read this as:

- I know `a`, `b : Nat`
- I know `h : a = b`
- I still need to prove `b = a`

This is the single most important Lean object for this repo.

### Tactic

A tactic is a proof command that changes the proof state.

Examples:

- `exact h`
- `rw [h]`
- `apply foo`
- `simp`
- `intro x`

Each tactic takes one proof state and turns it into another proof state, or closes the goal completely.

### Lemma

A lemma is just a theorem, usually a smaller helper theorem.

In practice, "lemma" and "theorem" are often similar. The difference is usually about role, not logic.

### Premise

A premise is a fact you might use in a proof.

This may be:

- a local hypothesis
- a previously proved theorem
- a library lemma from Mathlib

Premises matter because many tactics need a fact to act on.

### Premise Selection

Premise selection means:

given the current goal, which fact is the useful one to use next?

This is different from predicting the tactic family.

- tactic prediction asks: what kind of move should I make?
- premise selection asks: which fact should that move use?

For example:

```lean
h : a = b
⊢ f a = f b
```

The tactic family may be `rw`, but the useful premise is `h`, giving `rw [h]`.

## Reading Lean Syntax Slowly

Lean syntax can look intimidating at first, but most lines are just structured versions of very ordinary mathematical ideas.

Take this theorem:

```lean
theorem eq_demo (a b : Nat) (h : a = b) : b = a := by
  rw [h]
```

Read it piece by piece:

- `theorem eq_demo` names the theorem
- `(a b : Nat)` introduces variables `a` and `b` of type `Nat`
- `(h : a = b)` introduces a hypothesis named `h`
- `: b = a` is the statement to prove
- `:= by` means the proof will be written using tactics
- `rw [h]` is the proof step

In English:

For natural numbers `a` and `b`, if `a = b`, then `b = a`.

## Types, Terms, and Propositions

Lean is built on type theory, so types appear everywhere.

At a practical beginner level:

- a **type** is the kind of thing something is
- a **term** is an actual object of a type

Examples:

- `Nat` is the type of natural numbers
- `Bool` is the type of booleans
- `Prop` is the type of propositions
- `3` is a term of type `Nat`

### Why propositions are special

In Lean, a proposition is itself a type.

If `P : Prop`, then a proof of `P` is a term inhabiting the type `P`.

That sounds abstract, but operationally it means:

- proving `P` means constructing evidence for `P`
- hypotheses are pieces of evidence already in the context

Example:

```lean
theorem exact_demo (P : Prop) (h : P) : P := by
  exact h
```

This says:

- `P` is a proposition
- `h` is evidence that `P` is true
- goal is `P`
- `exact h` solves the goal by giving that evidence directly

## Term Style vs Tactic Style

Lean proofs can often be written in two styles.

### Tactic style

```lean
theorem exact_demo (P : Prop) (h : P) : P := by
  exact h
```

### Term style

```lean
theorem exact_demo (P : Prop) (h : P) : P := h
```

These mean the same thing.

Tactic style is often easier for interactive proving and proof-state inspection.
That is why this repo focuses on proof states and tactics.

## The Proof State: The Main Object You Must Understand

Everything in this repo revolves around proof states.

A proof state usually looks like:

```lean
x y : Nat
h1 : x = y
h2 : y = 3
⊢ x = 3
```

Interpretation:

- local variables: `x`, `y`
- local hypotheses: `h1`, `h2`
- goal: `x = 3`

This is exactly the kind of text the repo parses in [`state.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/state.py).

The model never sees "a whole theorem" directly. It sees one proof state at a time.

So the machine-learning question is:

given this proof state, what tactic should come next?

## Common Lean Objects You Will See

### Variables

```lean
x : Nat
```

`x` is a variable of type `Nat`.

### Equality

```lean
h : a = b
```

This says `a` equals `b`.

Equalities are especially important because many proofs use rewriting.

### Implication

```lean
h : P -> Q
```

This says: if `P` holds, then `Q` holds.

This is often used with `apply`.

### Conjunction

```lean
h : P ∧ Q
```

This means both `P` and `Q` are true.

### Disjunction

```lean
h : P ∨ Q
```

This means at least one of `P` or `Q` is true.

### Negation

```lean
h : ¬ P
```

This means `P` is false.

### Universal quantification

```lean
∀ x : Nat, P x
```

This means: for every natural number `x`, `P x` holds.

### Existential quantification

```lean
∃ x : Nat, P x
```

This means: there exists some natural number `x` such that `P x` holds.

## The Most Important Beginner Tactics

These are the tactics you should understand first.

### `exact`

Use `exact` when the goal is already directly available.

Example:

```lean
theorem exact_demo (P : Prop) (h : P) : P := by
  exact h
```

Initial proof state:

```lean
P : Prop
h : P
⊢ P
```

Why it works:

- the goal is `P`
- `h` is a proof of `P`
- so `exact h` closes the goal

Intuition:

> I already have exactly what I need.

### `rw`

Use `rw` to rewrite with an equality.

Example:

```lean
theorem rw_demo (a b : Nat) (h : a = b) : f a = f b := by
  rw [h]
```

Initial proof state:

```lean
a b : Nat
h : a = b
⊢ f a = f b
```

Why it works:

- `h` says `a = b`
- rewrite `a` to `b`
- goal becomes `f b = f b`

Intuition:

> Replace equals by equals.

`rw` is one of the clearest examples of premise selection:

- tactic: `rw`
- chosen premise: `h`

### `apply`

Use `apply` when you have a theorem whose conclusion matches the goal.

Example:

```lean
theorem apply_demo (P Q : Prop) (h : P -> Q) (hp : P) : Q := by
  apply h
  exact hp
```

Initial proof state:

```lean
P Q : Prop
h : P -> Q
hp : P
⊢ Q
```

After `apply h`, the goal becomes:

```lean
⊢ P
```

Then `exact hp` finishes the proof.

Intuition:

> To prove `Q`, it is enough to prove something that implies `Q`.

### `intro`

Use `intro` when the goal is an implication or a universally quantified statement.

Example:

```lean
theorem intro_demo (P Q : Prop) : P -> Q -> P := by
  intro hP
  intro hQ
  exact hP
```

Initial goal:

```lean
⊢ P -> Q -> P
```

After `intro hP`:

```lean
hP : P
⊢ Q -> P
```

After `intro hQ`:

```lean
hP : P
hQ : Q
⊢ P
```

Then `exact hP`.

Intuition:

> If the goal says "assume P", move that assumption into the context.

### `constructor`

Use `constructor` when the goal is something built out of parts, such as a conjunction.

Example:

```lean
theorem and_intro_demo (P Q : Prop) (hP : P) (hQ : Q) : P ∧ Q := by
  constructor
  exact hP
  exact hQ
```

`constructor` splits the conjunction goal into two goals:

- prove `P`
- prove `Q`

### `cases`

Use `cases` to break apart data or hypotheses.

Example:

```lean
theorem and_elim_left (P Q : Prop) (h : P ∧ Q) : P := by
  cases h with
  | intro hP hQ =>
      exact hP
```

Intuition:

> If I know `P ∧ Q`, then I can open it and get both pieces.

### `simp`

Use `simp` for simplification using known simp lemmas.

Example:

```lean
theorem simp_demo (n : Nat) : n + 0 = n := by
  simp
```

Intuition:

> Let Lean do routine simplification.

In practice, `simp` is extremely common.

### `rfl`

Use `rfl` when the goal is true by reflexivity of equality.

Example:

```lean
theorem rfl_demo (n : Nat) : n = n := by
  rfl
```

Intuition:

> Every object equals itself.

## A Walkthrough of a Small Proof

Consider:

```lean
theorem trans_demo (a b c : Nat) (h1 : a = b) (h2 : b = c) : a = c := by
  rw [h1]
  rw [h2]
```

Initial state:

```lean
a b c : Nat
h1 : a = b
h2 : b = c
⊢ a = c
```

After `rw [h1]`:

```lean
a b c : Nat
h1 : a = b
h2 : b = c
⊢ b = c
```

After `rw [h2]`:

```lean
⊢ c = c
```

Then Lean closes it.

This example is very useful for intuition:

- the context contains usable facts
- tactics transform the goal
- proof search is basically the problem of finding the right sequence of transformations

## What Lean Is Actually Checking

Lean is not checking whether your proof "looks plausible." It checks whether each step is type-correct and logically valid.

For example, if you say:

```lean
exact h
```

then Lean checks whether `h` really has the type required by the goal.

If you say:

```lean
rw [h]
```

then Lean checks whether `h` is actually an equality or something rewrite-compatible.

This is why theorem proving in Lean can be studied as a structured search problem.

The system has exact rules for what makes a step valid.

## Local Hypotheses vs Library Theorems

There are two broad sources of facts in a proof.

### Local hypotheses

These are facts in the current context.

Example:

```lean
h : a = b
```

### Library theorems

These are facts imported from Lean or Mathlib.

Example:

```lean
Nat.add_zero : ∀ n : Nat, n + 0 = n
```

In proof automation, both are important.

Local hypotheses are often the most directly useful.
Library theorems provide general-purpose reasoning power.

## Why Premise Selection Matters

Suppose your goal is:

```lean
⊢ n + 0 = n
```

A tactic predictor might say:

- use `rw`

But Lean still needs a fact:

- `rw [Nat.add_zero]`

So merely knowing the tactic family is not enough.

You also need to know which theorem or hypothesis to use.

That is premise selection.

Another example:

```lean
h : P
g : Q
⊢ P
```

The tactic family might be:

- `exact`

But which premise should be used?

- `h`, not `g`

So premise selection can be local, not just library-wide.

## Tactic Prediction vs Premise Selection vs Full Theorem Proving

These are different levels of difficulty.

### Tactic prediction

Question:

> What kind of proof step should come next?

Examples of answers:

- `rw`
- `simp`
- `apply`
- `exact`

This is the task the current repo solves.

### Premise selection

Question:

> Which fact should that tactic use?

Examples of answers:

- `h`
- `Nat.add_zero`
- `foo_trans`

This is not yet implemented in the repo.

### Full theorem proving

Question:

> Can we find and execute a whole sequence of proof steps until the theorem is solved?

That needs:

- tactic prediction
- premise selection
- proof-state transitions
- search over possible steps

## What a Proof Search Problem Looks Like

From an ATP viewpoint, a proof is a path through a space of proof states.

You start with one initial state.

Each valid tactic transforms it into a new state.

Some tactics fail.
Some tactics produce several subgoals.
Some tactics close the goal.

So you can imagine a tree:

- root = initial proof state
- edge = a tactic application
- child = new proof state

The theorem is solved if you reach a state with no remaining goals.

This is why theorem proving becomes a search problem.

## How This Repo Represents a Proof State

This repo does not keep the proof state as raw text forever.
It turns the proof state into a graph.

Why?

Because proof states have structure.

Example:

```lean
h : a = b
⊢ f a = f b
```

The symbols `a`, `b`, `f`, and `=` are not just text characters. They form expressions with relationships.

The repo represents that structure using:

- parsed expressions
- graph nodes for symbols and expression forms
- graph edges for composition
- shared nodes for repeated subexpressions

The shared-DAG part matters because identical structure is reused rather than copied repeatedly.

That lives mainly in:

- [`state.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/state.py)
- [`parser.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/parser.py)
- [`graph.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/graph.py)

## Why a Graph Instead of Plain Text

If you treat the proof state as plain text, repeated symbols and nested structure may be harder for the model to understand explicitly.

A graph can preserve:

- local syntax structure
- repeated subexpressions
- the difference between hypotheses and goal
- a single root `State` node tying the whole proof state together

This is one of the central design ideas of the repo.

## How the Current Learning Task Works

For each training example:

- input = one proof-state graph
- label = the next tactic head used in a real proof

Example:

- proof state graph corresponds to a state where rewriting is appropriate
- target label is `rw`

The label normalization lives in [`labels.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/labels.py).

The graph export lives in [`pyg.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/pyg.py).

The training stack lives in:

- [`model.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/model.py)
- [`training.py`](/C:/Users/LOQ/source/repos/icogLabs/lean/atp_lean_gnn/atp_lean_gnn/training.py)

## Why the Current Model Is Not Yet a Full Prover

Right now the model predicts only the tactic head.

Example:

- it can predict `rw`
- it does not yet predict the exact executable tactic `rw [h]`

So there is still a gap between:

- a useful proof-state classifier
- a system that can actually perform theorem proving end to end

Bridging that gap will require:

- premise selection
- tactic argument generation
- Lean environment interaction
- search over multiple candidate actions

## A Lean Example Mapped to Repo Components

Take this theorem:

```lean
theorem apply_demo (P Q : Prop) (h : P -> Q) (hp : P) : Q := by
  apply h
  exact hp
```

### Step 1: initial proof state

```lean
P Q : Prop
h : P -> Q
hp : P
⊢ Q
```

### Step 2: parsing

The repo parses:

- variables `P`, `Q`
- hypothesis `h : P -> Q`
- hypothesis `hp : P`
- goal `Q`

### Step 3: graph building

The repo builds a graph containing nodes for:

- proposition symbols
- implication structure
- hypothesis wrappers
- the goal wrapper
- the overall `State`

### Step 4: label

The next tactic is:

```lean
apply h
```

The current baseline label becomes:

```text
apply
```

### Step 5: training

The GNN learns that proof states with this kind of structure often want tactic `apply`.

### Step 6: future extension

Later, a stronger system would also need to learn that the useful premise is `h`.

## Common Patterns You Will Meet Often

### Pattern 1: goal already in context

Example:

```lean
h : P
⊢ P
```

Likely tactic:

- `exact`

### Pattern 2: equality can simplify the goal

Example:

```lean
h : a = b
⊢ f a = f b
```

Likely tactic:

- `rw`

### Pattern 3: theorem conclusion matches goal

Example:

```lean
h : P -> Q
⊢ Q
```

Likely tactic:

- `apply`

### Pattern 4: routine simplification

Example:

```lean
⊢ n + 0 = n
```

Likely tactic:

- `simp`

Learning to recognize these patterns is a major part of becoming comfortable with Lean proofs.

## What Makes Lean Hard for Beginners

Lean usually feels hard at first for a few reasons.

### Everything is explicit

Mathematics on paper omits many steps. Lean does not.

### The syntax looks unfamiliar

Symbols like `⊢`, `∀`, `∃`, `∧`, `∨`, `¬` can feel dense until you get used to them.

### Tactics change goals in non-obvious ways

You need practice seeing how a tactic transforms the proof state.

### The library is huge

Even when you know the right idea mathematically, you may not know the exact theorem name in Lean.

This last point is especially important for ATP.

Often the challenge is not just logic, but retrieving the right premise from a large library.

## The Minimum Lean Knowledge You Need for This Repo

To work productively on this repo, you do not need to become a full Lean power user immediately.

You mainly need to understand:

1. how to read a proof state
2. what a tactic does to a proof state
3. the difference between local hypotheses and global lemmas
4. why a tactic head is not enough for full proof execution
5. why premise selection matters
6. why theorem proving is a search problem over proof states

That is the conceptual core.

## Beginner-Friendly Reading of Symbols

These are worth getting comfortable with.

- `:` means "has type"
- `:=` means "is defined as"
- `⊢` means "goal to prove"
- `->` means implication
- `∀` means "for all"
- `∃` means "there exists"
- `∧` means "and"
- `∨` means "or"
- `¬` means "not"
- `=` means equality

Examples:

```lean
n : Nat
```

means:

`n` is a natural number.

```lean
h : P -> Q
```

means:

`h` is evidence that `P` implies `Q`.

```lean
⊢ Q
```

means:

the current goal is to prove `Q`.

## Multi-Goal Intuition

Some tactics split one goal into several subgoals.

Example:

```lean
theorem and_intro_demo (P Q : Prop) (hP : P) (hQ : Q) : P ∧ Q := by
  constructor
```

After `constructor`, Lean gives two goals:

1. `⊢ P`
2. `⊢ Q`

This matters for ATP because theorem proving is not always a straight line.
Sometimes one tactic increases the branching factor.

A good prover must reason over these branches too.

## Why Search Is Needed

Even if your model predicts the next tactic well, theorem proving is usually not solved by greedy one-step prediction.

Why?

- the top-ranked tactic may fail
- several tactics may be plausible
- some tactics create new subgoals
- the best proof may require choosing a temporarily non-obvious step

So later phases of the project need search:

- beam search
- heuristic search
- maybe MCTS

But all of that starts from understanding proof states and tactics first.

## The Relationship Between Lean, LeanDojo, and This Repo

### Lean

The proof assistant and theorem-proving environment.

### LeanDojo

A dataset and interaction framework around Lean theorem-proving traces.

### This repo

A graph-learning layer built on top of Lean-style proof states and LeanDojo data.

The current implemented pipeline is:

- Lean proof state text
- parse into structure
- build graph
- store prepared dataset artifacts
- train GNN for next-tactic prediction

## What You Should Study Next in Lean

Once the material above feels comfortable, the next useful topics are:

### Equality reasoning

Especially `rw`, `rfl`, symmetry, transitivity.

### Implication and assumptions

Especially `intro`, `apply`, `exact`.

### Conjunction and disjunction

How to build and break apart logical structure.

### Quantifiers

How to introduce universally quantified variables and how existence proofs work.

### Inductive types

Especially `Nat`, lists, and recursive reasoning later on.

### Simplification and automation

Especially `simp`, `aesop`, and related tactics.

These topics will make theorem-proving traces much easier to read.

## A Practical Study Order

If you want a concrete beginner path, use this order:

1. read proof states until they feel natural
2. learn `exact`
3. learn `rw`
4. learn `apply`
5. learn `intro`
6. learn `simp`
7. learn conjunction/disjunction basics
8. learn quantifier basics
9. learn how library lemmas are used
10. come back to premise selection and search

That order matches the needs of this repo surprisingly well.

## How to Think About ATP in Lean

The ATP problem in Lean is not "generate impressive text."

It is:

1. observe the current proof state
2. understand its structure
3. choose a useful tactic
4. choose useful premises or arguments when needed
5. apply the tactic
6. repeat until the proof is complete

This is why the project naturally decomposes into phases:

- representation
- tactic prediction
- premise selection
- execution
- search
- later symbolic integration

## What This Repo Already Does Well

The repo already handles the early part of that pipeline:

- parse proof states
- represent them as shared DAGs
- cache large datasets
- train a baseline next-tactic predictor
- evaluate and analyze runs

That means the current repo is already a meaningful research foundation.

## What Still Remains Later

The main missing ATP layers are:

- premise selection
- tactic argument generation
- Lean environment execution
- multi-step search
- neuro-symbolic integration

So if something feels "unfinished," that is normal. The repo is intentionally in the early proof-state-learning phase.

## Frequently Confused Beginner Questions

### "Is a theorem different from a proposition?"

A theorem is a named proved statement. A proposition is the kind of statement that can be true or false.

### "Is a hypothesis just an assumption?"

In local proof-state terms, yes. It is a fact currently available in the context.

### "Why does Lean treat proofs like objects?"

Because in dependent type theory, proving a proposition means constructing a term of that proposition's type.

### "Why do we need tactics if term proofs exist?"

Tactics are often easier for interactive theorem proving and proof search because they work directly with proof states.

### "Why is premise selection separate from tactic prediction?"

Because knowing the kind of move is different from knowing which fact to use for that move.

### "Why is `simp` so common?"

Because many goals can be solved or simplified using routine rewriting and simplification rules.

## A Final Intuition

If you remember only one mental model, use this one:

- the context is what you know
- the goal is what you need
- a tactic is a move
- a premise is the fact used by that move
- a proof is a sequence of state transformations
- theorem proving is search over those transformations

And this repo is trying to learn those moves from graph-structured proof states.

## Recommended Follow-Up

After reading this guide, the best next step is to study one proof and one repo graph side by side:

1. a small Lean theorem
2. its proof states
3. the tactic sequence
4. the graph the repo builds for one of those states
5. the label the model learns from that state

That is the point where Lean, graphs, and ATP all click together.
