# Neural vs Symbolic in ATP

This note is a design memo for the project.

Its goal is to answer a recurring architecture question:

> What parts of an automated theorem prover should be neural, what parts should be symbolic, and how should they fit together?

The short answer is:

- pure neural systems are usually too unconstrained
- pure symbolic systems are usually too brittle or too expensive to guide well
- the strongest practical direction is a **symbolic core with neural guidance**

This document explains that claim carefully and connects it to Lean-based ATP in particular.

## The Main Distinction

When people say "neural" in theorem proving, they usually mean:

- learned scoring
- learned retrieval
- learned action ranking
- learned search guidance
- text generation or structured action prediction

When people say "symbolic", they usually mean:

- exact logical objects
- proof states, terms, and environments
- substitutions and unification
- executable tactics
- search trees or DAGs
- correctness checking by a proof assistant

The important point is that these are not competing descriptions of the same thing.
They are different layers of a prover.

In a serious ATP system, the symbolic layer defines what is valid.
The neural layer helps decide what is promising.

## Why Pure Neural Is Not Enough

A purely neural prover is attractive because it is simple to describe:

`proof state text -> model -> next tactic text`

But in practice this runs into several deep problems.

### 1. Validity is exact, not approximate

Theorem proving is not like image classification where "close enough" can still be useful.

If a tactic is malformed, uses the wrong premise, rewrites at the wrong location, or leaves an unclosed side goal, the proof step is wrong.

That means theorem proving has a hard correctness boundary.
The model can suggest candidates, but a symbolic checker must decide validity.

### 2. The action space is too open

Raw Lean tactic syntax is large and messy:

- tactic names
- premise names
- local hypotheses
- rewrite directions
- rewrite locations
- lists of arguments
- nested subcommands
- tactic combinators

If a model must generate all of that as free text, it is solving two problems at once:

- mathematical reasoning
- syntax generation and formatting

That is a poor decomposition.

### 3. Search matters more than one-step prediction

A model may predict a plausible next step that is locally reasonable but globally useless.
Actual proving usually requires:

- branching
- backtracking
- goal ordering
- premise reuse
- intermediate failures

So a one-shot neural predictor is not a prover by itself.

### 4. Neural systems are weak at explicit structural bookkeeping

Proof search needs explicit handling of:

- bound variables
- metavariables
- substitutions
- dependencies between goals
- accessible premises
- exact state transitions

These are symbolic objects with exact semantics.
If they are treated only as text patterns, the prover loses important structure.

## Why Pure Symbolic Is Not Enough

At the same time, symbolic-only systems also hit real limits.

### 1. The choice space is enormous

At many proof states, the symbolic system may have:

- thousands of accessible premises
- many possible rewrites
- many candidate variables to destruct
- many search branches

A symbolic engine can enumerate possibilities, but it often lacks a good learned sense of what is worth trying first.

### 2. Hand-written heuristics do not scale cleanly

Pure symbolic automation can be very strong in narrow domains, but it tends to rely on:

- carefully engineered heuristics
- domain-specific simplifiers
- manually tuned search orderings

These are valuable, but they do not automatically generalize to the full diversity of Lean proofs.

### 3. Ranking is often the real bottleneck

Many theorem-proving problems are not about whether a move is legal.
They are about whether a move is useful.

Examples:

- which of 30,000 accessible premises should be considered first?
- which of 8 possible rewrite locations is promising?
- which subgoal should be attacked before the others?
- which branch of search deserves more budget?

These are exactly the kinds of ranking problems where learned guidance helps.

## The Right Split: Symbolic Core, Neural Guidance

For Lean ATP, the most sensible architecture is:

- **symbolic core** for exact state representation, execution, and validation
- **neural guidance** for ranking and policy decisions over structured symbolic choices

This is the design principle behind many of the strongest ideas across the literature, even when the details differ.

## What Should Be Symbolic

These parts should remain symbolic or strongly symbolically grounded.

### 1. Proof state and environment

The current goal state, local hypotheses, theorem environment, namespace/accessibility rules, and available constants should be treated as exact symbolic objects.

Even if a model later consumes a graph or embedding of the state, the source of truth should remain the symbolic Lean state.

### 2. Correctness checking

Lean should remain the ground-truth judge of:

- tactic validity
- type correctness
- goal closure
- theorem completion

This should never be replaced by a learned guess.

### 3. Search control structure

The search tree or DAG, proof obligations, branching records, backtracking, and visited-state tracking should remain explicit symbolic data structures.

The model can score branches, but it should not secretly own the full search state.

### 4. Action schema

The action vocabulary should be symbolic and structured.

Instead of asking the model to emit arbitrary tactic strings, prefer action forms like:

- `intro`
- `apply(lemma_or_hypothesis)`
- `exact(lemma_or_hypothesis)`
- `rewrite(eq_lemma, locus, direction)`
- `cases(variable)`
- `induction(variable, principle)`
- terminal actions like `rfl`, `assumption`, `contradiction`

This keeps the action space semantically meaningful.

### 5. Premise accessibility and filtering

Which premises are available at a proof state is a symbolic property of the Lean environment.

The model can rank accessible premises, but it should not hallucinate inaccessible ones.

## What Should Be Neural

These are the parts most naturally handled by learned models.

### 1. Premise ranking

Given a state and many candidate premises, a learned model can score which ones are likely relevant.

This is one of the clearest uses of neural guidance.

### 2. Action ranking

Given the current state, the model can rank:

- tactic kind
- candidate lemma for `apply`
- candidate equality for rewrite
- candidate locus for a positional rewrite
- candidate variable for `cases` or `induction`

This is much more natural than free-text generation.

### 3. Search prioritization

When many valid symbolic branches exist, the model can estimate:

- which branch looks most promising
- which subgoal should be tackled first
- which partial proof is worth more budget

### 4. Progress or value estimation

The model can estimate whether a state appears:

- close to closure
- structurally difficult
- similar to previously successful states

This is useful for beam search, MCTS, and proof repair loops.

### 5. Representation learning

Graphs, DAGs, and other structured encodings of proof states are good places for learned models to extract patterns not captured by simple symbolic heuristics.

## Where Finite State Machines Fit

Finite state machines are not a full ATP solution, but they can be genuinely useful.

They are especially relevant for **structured action generation**.

For example, instead of one giant action space over full tactics, an action generator can be organized as a finite control process:

1. choose action kind
2. if `apply`, choose lemma
3. if `rewrite`, choose equality lemma
4. choose rewrite locus
5. choose rewrite direction
6. execute

That is very close to an FSM-like control structure.

FSM ideas are useful for:

- enforcing valid action forms
- factorizing decisions into stages
- constraining decoding
- preventing malformed outputs

They are much less useful as a replacement for proof search or mathematical reasoning itself.

In short:

- FSMs can help structure the policy
- FSMs are not the core source of mathematical intelligence

## Where Byte Pair Encoding Fits

BPE is a tokenization method for text models.
It is helpful when the system is fundamentally text-driven.

It is not a theorem-proving method.

In this project, BPE is only central if we choose a text-first interface for:

- proof state input
- tactic output
- premise names as generated text

If the system moves toward:

- graph states
- structured actions
- premise IDs or embeddings
- explicit loci and symbolic action arguments

then BPE becomes much less central.

So BPE may matter for some model implementations, but it should not drive the architecture.

## What This Means for This Project

The current project already points in a useful direction:

- symbolic Lean proof states are parsed
- states are represented as shared graphs
- a neural model predicts tactic information from those graphs

But the long-term architecture should go further than plain next-tactic classification.

The strongest direction is:

### Symbolic responsibilities

- Lean remains the executor and checker
- proof states remain exact symbolic states
- search remains explicit
- accessible premises are symbolically defined
- actions are represented by structured schemas

### Neural responsibilities

- encode proof states and candidate premises
- score tactic kinds
- score tactic arguments
- score rewrite loci
- prioritize search branches

This is a better design than either:

- free-text tactic generation alone
- hand-coded symbolic search alone

## Recommended Architecture Direction

The project should gradually move toward the following stack:

### Stage 1: structured representation

Keep and improve:

- graph or DAG proof-state representation
- trainable encoders over that representation

### Stage 2: structured action space

Move beyond tactic-head classification toward a factorized action interface such as:

- action kind
- optional premise/lemma selection
- optional variable selection
- optional locus selection
- optional direction flag

This is where FSM-like thinking becomes useful.

### Stage 3: explicit premise selection

Introduce a dedicated premise-ranking component instead of asking tactic prediction to absorb premise choice implicitly.

### Stage 4: search

Use the neural model to guide a symbolic search procedure rather than treating the top prediction as the whole proof strategy.

### Stage 5: repair and critique

Later, incorporate:

- proof repair loops
- branch pruning
- proof-quality estimation
- verifier-like confidence signals

But only after execution and structured search are stable.

## A Useful Rule of Thumb

If a component needs to be:

- exact
- valid
- environment-aware
- reproducible by Lean
- explicitly inspectable

then it should probably be symbolic.

If a component needs to:

- rank many options
- generalize from examples
- prioritize promising moves
- estimate usefulness
- compress structural patterns

then it should probably be neural.

## What We Should Avoid

Three traps are especially common.

### Trap 1: text-first everything

This pushes too much of the problem into syntax generation and hides important structure.

### Trap 2: symbolic-only purism

This often produces systems that are valid but search too blindly.

### Trap 3: vague "neuro-symbolic" language without a boundary

A useful neuro-symbolic design needs a very clear contract:

- what the symbolic layer owns
- what the neural layer scores
- what data moves between them

Without that boundary, the architecture becomes muddy quickly.

## Bottom Line

The right question is not:

> Should this project be neural or symbolic?

The right question is:

> Which parts of theorem proving are fundamentally symbolic, and where can learned models provide the most leverage?

For this project, the best answer is:

- symbolic state, execution, and search structure
- neural scoring over structured symbolic choices

That is the architecture most likely to produce a prover that is:

- correct
- scalable
- interpretable
- efficient enough to improve over time

## Practical Conclusion

If this project continues in a strong direction, it should aim for:

`Lean state -> symbolic structured action candidates -> neural scoring -> symbolic execution in Lean -> search -> proof`

not:

`Lean state text -> free-form neural text -> hope`

That is the most useful design principle to carry forward.
