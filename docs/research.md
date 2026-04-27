# Hybrid Neural-Symbolic Proving
# Backward + Forward Chaining Design Guide

## 0. Why This Document Exists

This document is intentionally long.
It is designed for deep understanding.
It starts from almost zero assumptions.
It moves from intuition to rigor step by step.
It gives concrete designs, not vague claims.
It includes many worked examples.

If you are early in theorem proving research,
this should still feel readable.
If you are already technical,
this should still give a rigorous framework.

The central question is:

How do we blend a neural model
with symbolic backward and forward chaining
in a way that is practical,
correct,
and research-grade?

This guide answers that in layers.

## 1. Reader Map

If you want only the high-level idea,
read Sections 2 to 5.

If you want formal definitions,
read Sections 6 to 9.

If you want concrete architecture choices,
read Sections 10 to 16.

If you want implementation mapping to this repo,
read Section 17.

If you want examples only,
read Section 18.

If you want experiments and metrics,
read Sections 19 to 21.

## 2. Big Picture in One Page

The symbolic system is the judge.
The neural model is the guide.

Symbolic system responsibilities:

- represent exact proof state
- enumerate legal actions
- execute actions
- verify correctness
- decide solved or not solved

Neural model responsibilities:

- rank action families
- rank premise candidates
- prioritize branches
- estimate state promise

So the split is:

- symbolic = validity
- neural = prioritization

This split matters because theorem proving is exact.
Near-correct is still wrong.

## 3. Intuition: Proving As A Maze

Imagine a giant maze.
You start at the entrance.
The exit is a completed proof.

At each intersection,
you can choose many corridors.

- A symbolic engine tells you which corridors are legal.
- A neural model tells you which corridors look promising.

If you only use symbolic logic,
you may still solve the maze,
but you might inspect too many corridors.

If you only use neural guesses,
you may run fast,
but you can walk into invalid corridors.

The hybrid gives speed plus correctness.

## 4. Intuition: Backward Chaining

Backward chaining starts from the goal.
It asks:

"What would have to be true
for this goal to be true?"

That creates subgoals.
Then it repeats.

Toy example:

Goal: `R`
Hypotheses: `P -> Q`, `Q -> R`, `P`

Backward reasoning:

1. To prove `R`, it is enough to prove `Q`.
2. To prove `Q`, it is enough to prove `P`.
3. `P` is already known.
4. Done.

Why backward is strong:

- goal-driven
- avoids irrelevant exploration
- naturally aligned with tactics like `apply`

Where backward alone can struggle:

- hard intermediate constructions
- huge premise sets
- many local branches with similar surface forms

## 5. Intuition: Forward Chaining

Forward chaining starts from known facts.
It asks:

"What new facts can I derive now?"

It expands outward,
building a closure of consequences.

Toy example:

Known:

- `A`
- `A -> B`
- `B -> C`

Forward steps:

1. derive `B`
2. derive `C`

Why forward is strong:

- finds useful derived facts early
- good when target structure is not obvious
- good for transitive or algebraic chains

Where forward alone can struggle:

- combinatorial explosion
- many derived facts are irrelevant
- memory and compute growth

## 6. Why Blend Backward And Forward

The two methods complement each other.

Backward gives focus.
Forward gives construction power.

Hybrid idea:

1. Backward search drives the target.
2. Forward module proposes intermediate facts.
3. Neural relevance filter keeps only useful facts.
4. Symbolic executor validates everything.

This gives a practical compromise:

- not blind enumeration
- not unconstrained generation

## 7. Transition To Formal Thinking

Now we move from intuition
to formal definitions.

We will keep notation simple.
We will still tie each definition to practical code decisions.

## 8. Formal Objects

Let proof state be:

$$
S = (\Gamma, G, M)
$$

where:

- $\Gamma$ = local context (hypotheses, local constants)
- $G$ = active goals (ordered list or multiset)
- $M$ = metadata (depth, trace id, parent pointer, hash)

Let action be:

$$
a \in A(S)
$$

where $A(S)$ is the set of legal actions in state $S$.

Transition function:

$$
T(S, a) \in \{S', \text{Error}, \text{Solved}\}
$$

Symbolic soundness rule:

- if $T(S,a)=S'$, then step is valid
- if $T(S,a)=\text{Error}$, step is invalid
- only symbolic engine decides this

Neural modules:

- policy $\pi_\theta(a|S)$
- value $V_\phi(S)$
- relevance $R_\psi(f|S)$ for candidate fact $f$

## 9. Action Schema vs Free Text

Do not start with free-form tactic string generation.
Start with structured actions.

Recommended schema:

- `IntroAction(var_hint)`
- `ApplyAction(premise_id)`
- `ExactAction(premise_id)`
- `RewriteAction(eq_id, direction, locus)`
- `CasesAction(var_id)`
- `InductionAction(var_id, principle_id?)`
- `TerminalAction(name)` where name in `{rfl, assumption, contradiction}`

Advantages:

- lower entropy
- easier supervision
- better diagnostics
- cleaner search branching

## 10. Shared Hybrid Architecture

All concrete designs in this document
reuse these components.

### 10.1 State Encoder

Input:

- graph of proof state
- optional goal index
- optional context annotations

Output:

- node embeddings
- graph embedding
- goal-focused embeddings

### 10.2 Candidate Generator

This is the most important symbolic component.
It must turn a huge tactic space into a tractable legal candidate set.

The key idea is staged narrowing:

1. define a structured action grammar
2. enumerate only admissible action templates from goal shape
3. build a bounded premise pool
4. instantiate templates with pool elements
5. perform cheap static checks
6. perform symbolic dry-run validation
7. keep only validated actions

In short:

huge tactic language -> small typed action grammar -> legal candidate set.

#### 10.2.1 Action Grammar

Use a compact grammar rather than unrestricted text:

- IntroAction(var_hint)
- ApplyAction(premise_id)
- ExactAction(premise_id)
- RewriteAction(eq_premise_id, direction, locus)
- CasesAction(var_id)
- InductionAction(var_id, principle_id)
- TerminalAction(kind)

where TerminalAction(kind) can be one of:

- rfl
- assumption
- contradiction
- trivial

This grammar is intentionally small for Design 1.
You can expand it later after logging and ablations.

#### 10.2.2 Goal-Shape Admissibility Rules

Before touching premises, use goal shape to activate tactic families.

Examples:

- if goal is forall or implication, enable IntroAction
- if goal is conjunction, enable constructor-like split actions
- if goal head symbol is equality, enable RewriteAction and TerminalAction(rfl)
- if goal head can unify with conclusion of a premise, enable ApplyAction
- if local context contains exact goal type, enable ExactAction
- if local variable has inductive type, enable CasesAction
- if local variable is Nat or inductive and theorem family suggests recursion, enable InductionAction

These checks are cheap and remove many impossible families early.

#### 10.2.3 Premise Universe Construction

Define premise universe U(S) for state S as:

U(S) = local_hypotheses(S) union retrieved_globals(S)

where retrieved_globals(S) is bounded.

Recommended retrieval stack:

1. namespace and theorem-context prefilter
2. head-symbol index lookup from goal and hypotheses
3. lexical token overlap fallback
4. optional embedding retrieval for recall

Typical cap for Design 1:

- local hypotheses: all
- global premises: top 200 to 1000 (configurable)

#### 10.2.4 Template Instantiation Per Family

ApplyAction instantiation:

- for each premise p in U(S):
  - parse type of p as A1 -> A2 -> ... -> B
  - keep p only if B is unifiable with current goal target
  - create ApplyAction(p)

ExactAction instantiation:

- keep p if type(p) is definitionally equal or unifiable with goal
- create ExactAction(p)

RewriteAction instantiation:

- keep only premises typed as equalities lhs = rhs (or iff when enabled)
- detect occurrences of lhs or rhs in goal/hypotheses
- generate direction in {forward, reverse}
- generate locus from matched occurrence indices
- create RewriteAction(eq, direction, locus)

CasesAction instantiation:

- for each local variable v with inductive type:
  - create CasesAction(v)

InductionAction instantiation:

- for each induction-eligible variable v:
  - retrieve principle candidates
  - create InductionAction(v, principle)

TerminalAction instantiation:

- rfl if goal reducible to reflexive equality
- assumption if goal appears in local context
- contradiction if explicit contradiction evidence exists

#### 10.2.5 Static Pruning Rules

Before dry-run execution, apply cheap pruning:

- arity sanity checks
- metavariable explosion guard
- max-subgoal estimate guard
- duplicate normalized action removal
- rewrite loop guard (same rewrite toggled repeatedly)

These checks keep dry-run cost manageable.

#### 10.2.6 Dry-Run Validation (Legality Gate)

An action is considered legal only if dry-run elaboration succeeds.

Procedure:

1. serialize structured action to tactic term
2. run symbolic executor in sandbox mode
3. if elaboration or execution fails, reject action
4. if succeeds, keep resulting transition metadata

So legal means "accepted by symbolic engine now," not "looks plausible."

#### 10.2.7 Bounded Candidate Set

After validation, cap actions per family and overall.

Example configuration:

- max_apply_candidates = 64
- max_exact_candidates = 32
- max_rewrite_candidates = 64
- max_cases_candidates = 8
- max_induction_candidates = 8
- max_total_candidates = 128

This bound is essential for predictable runtime.

#### 10.2.8 Candidate Generation Pseudocode

```text
function symbolic_candidates(S):
    families <- admissible_families_from_goal_shape(S)
    U <- build_premise_universe(S)
    A <- []

    if Apply enabled:
        A += instantiate_apply(S, U)
    if Exact enabled:
        A += instantiate_exact(S, U)
    if Rewrite enabled:
        A += instantiate_rewrite(S, U)
    if Cases enabled:
        A += instantiate_cases(S)
    if Induction enabled:
        A += instantiate_induction(S)
    A += instantiate_terminal(S)

    A <- static_prune(A, S)
    A <- dry_run_validate(A, S)
    A <- cap_per_family_and_total(A)
    return A
```

#### 10.2.9 Worked Legality Examples

Example 1: Apply legality

- goal: Even (n + m)
- premise type: forall a b, Even a -> Even b -> Even (a + b)
- unification succeeds with a:=n, b:=m
- ApplyAction(even_add) is legal

Example 2: Rewrite legality

- goal: f x = f y
- premise: h : x = y
- occurrence of x found in goal at locus 0
- RewriteAction(h, forward, locus=0) is legal

Example 3: Rewrite non-legality

- goal: g x = g y
- premise: h : a = b
- no occurrence of a or b in goal/hypotheses
- rewrite action rejected before dry-run

Example 4: Cases legality

- local variable: h : A or B
- CasesAction(h) is legal
- local variable: z : Nat
- CasesAction(z) may be legal but lower-priority by heuristics

Example 5: Exact legality

- goal: P y
- local hypothesis: h2 : P y
- ExactAction(h2) is legal and terminal

#### 10.2.10 Why This Solves The Vast-Space Problem

The action space is vast only if treated as raw syntax.
With this pipeline, complexity is controlled by explicit caps and typing gates.

So the practical search unit is not arbitrary tactics.
It is a bounded, validated set of structured symbolic actions.

### 10.3 Neural Scorers

Policy scorer:

- ranks candidate actions

Value scorer:

- estimates success potential of resulting state

Relevance scorer:

- ranks derived facts or premise candidates

### 10.4 Symbolic Executor

Executes action on real proof state.
Returns next state or error.
Tracks proof completion.

### 10.5 Frontier Manager

Supports:

- beam queue
- best-first queue
- MCTS tree
- dedup cache

### 10.6 Logging Layer

At each expansion store:

- state id
- action
- policy score
- value score
- symbolic result
- elapsed time

This is required for debugging and training data refresh.

## 11. Design 1: Backward Beam Search With Policy Guidance

This is the recommended first production design.

### 11.1 Core Idea

Run backward search only.
Use neural policy to rank actions.
Optionally use value for tie-breaking.

Crucially, the policy never ranks arbitrary syntax.
It ranks the legal set returned by Section 10.2.

So Design 1 is formally:

1. generate legal actions with symbolic candidate generator
2. rank only those actions with neural policy
3. execute top-k with symbolic transition function
4. enqueue resulting valid states

No undefined free-form generation step exists in this design.

### 11.2 Scoring Function

Use:

$$
Score(S, a) = \alpha \log \pi_\theta(a|S) + \beta V_\phi(T(S,a)) - \gamma d(S) - \delta \cdot repeat(S)
$$

where:

- $d(S)$ is depth
- $repeat(S)$ penalizes revisits

### 11.3 Pseudocode

```text
frontier <- PriorityQueue()
push(frontier, root_state)

while frontier not empty and budget left:
    S <- pop_best(frontier)
    actions <- symbolic_candidates(S)
    ranked <- rank_with_policy(S, actions)
    for a in top_k(ranked):
        outcome <- symbolic_execute(S, a)
        if outcome == Solved:
            return proof_trace
        if outcome is valid state S2:
            score <- combine(policy, value, penalties)
            push(frontier, S2, score)

return failure_or_timeout
```

### 11.4 Example A

State:

- `h1 : P -> Q`
- `h2 : Q -> R`
- `hp : P`
- goal `R`

Top candidate actions:

1. `apply h2`
2. `exact hp`
3. `simp`

Policy ranks `apply h2` highest.
Symbolic execution reduces goal to `Q`.
Next step `apply h1`.
Next step `exact hp`.
Solved.

### 11.5 Example B

State:

- `n m : Nat`
- `hn : Even n`
- `hm : Even m`
- goal `Even (n + m)`

Top candidate actions:

1. `apply even_add`
2. `simp`
3. `rw [Nat.add_comm]`

`apply even_add` creates subgoals `Even n` and `Even m`.
Both solved by `exact hn`, `exact hm`.

### 11.6 Strengths

- simple to implement
- directly uses current model signal
- clear diagnostics
- strong baseline for ablations

### 11.7 Weaknesses

- weak when intermediate facts are not obvious
- still premise-heavy in large libraries

## 12. Design 2: Backward Search With Explicit Premise Reranking

This extends Design 1.
Main addition is a dedicated premise ranking head.

### 12.1 Core Idea

Separate "choose tactic family"
from "choose which premise".

This is crucial when thousands of premises are legal.

### 12.2 Two-Stage Retrieval

Stage 1 symbolic prefilter:

- by type compatibility
- by namespace scope
- by shape heuristics

Stage 2 neural rerank:

- score with bi-encoder or cross-encoder style features

### 12.3 Example A

Goal:

- `List.length (xs ++ ys) = List.length xs + List.length ys`

Symbolic prefilter returns 120 candidates.
Reranker places `List.length_append` at rank 1.
Search closes in 2 steps.

Without reranking,
branching factor remains too high.

### 12.4 Example B

Goal:

- `a <= c`
Hypotheses:

- `h1 : a <= b`
- `h2 : b <= c`
- plus 400 irrelevant lemmas in scope

Reranker prioritizes transitivity lemma and local hypotheses.
Proof found quickly with `exact le_trans h1 h2`.

### 12.5 Extra Logging Needed

Store per-step:

- candidate count prefilter
- top-20 reranked premises
- selected premise rank at success

This allows true retrieval diagnostics.

## 13. Design 3: Forward Assistant With Relevance Filtering

This adds a bounded forward module.

### 13.1 Core Idea

Generate forward facts under strict budget.
Keep only facts likely useful to active goals.

### 13.2 Forward Budget Controls

- max new facts per state
- max derivation depth
- max per-rule expansions
- dedup by canonical hash

### 13.3 Relevance Scoring

For each derived fact $f$:

$$
keep(f) = [R_\psi(f|S) > \tau]
$$

where $\tau$ is a tunable threshold.

### 13.4 Example A: Transitive Chain

Known:

- `a < b`
- `b < c`
- `c < d`

Goal:

- `a < d`

Forward module derives:

- `a < c`
- `b < d`
- maybe others

Relevance keeps `a < c` and `b < d`.
Backward closes `a < d` quickly.

### 13.5 Example B: Algebraic Bridge

Known:

- `h : x = y + 1`

Goal:

- `x^2 - 2*x*y + y^2 = 1`

Forward derives simplification bridge:

- `h_sub : x - y = 1`

Backward can factor left side and rewrite by `h_sub`.

### 13.6 Strengths

- finds useful intermediates
- helps deep algebraic chains
- keeps backward focus

### 13.7 Weaknesses

- needs careful budget tuning
- risk of over-pruning if relevance head is weak

## 14. Design 4: Bidirectional Meet-In-The-Middle Search

This runs both backward and forward frontiers.

### 14.1 Core Idea

Backward frontier starts from goal.
Forward frontier starts from known facts.
Stop when frontiers meet.

### 14.2 Meeting Criteria

Possible criteria:

- exact normalized term match
- unification-compatible pattern
- learned similarity plus symbolic check

### 14.3 Example A

Goal:

- `P c`

Backward frontier reaches subgoal `P b`.
Forward frontier derives `P b`.
Frontiers meet.
Trace composed and validated.

### 14.4 Example B

Goal:

- `f (g (h x)) = t`

Backward reaches requirement `g (h x) = u`.
Forward derives same intermediate from hypotheses.
Bridge formed.

### 14.5 Strengths

- shorter effective depth on hard tasks
- can solve problems backward-only misses

### 14.6 Weaknesses

- highest engineering burden before MCTS
- requires robust canonicalization

## 15. Design 5: Hierarchical Action Construction

This is about action modeling,
not search topology.

It can be combined with Designs 1 to 4.

### 15.1 Core Idea

Factor action prediction into stages.

$$
P(a|S)=P(family|S)P(premise|family,S)P(direction|family,premise,S)P(locus|...)
$$

### 15.2 Why This Matters

Flat text generation is noisy.
Hierarchical prediction is easier to train.

### 15.3 Example A: Rewrite

1. family head predicts `rw`
2. premise head predicts `h_eq`
3. direction head predicts reverse
4. locus head predicts goal node 42
5. symbolic executor applies rewrite

### 15.4 Example B: Apply

1. family head predicts `apply`
2. premise head ranks lemma candidates
3. executor checks goal compatibility

### 15.5 Diagnostics

If step fails,
you know exactly which subdecision failed:

- wrong family?
- wrong premise?
- wrong rewrite location?

## 16. Design 6: MCTS With Neural Priors

Use this after earlier designs stabilize.

### 16.1 Core Idea

Use tree search with PUCT.

$$
U(S,a)=Q(S,a)+c\,P(S,a)\frac{\sqrt{\sum_b N(S,b)}}{1+N(S,a)}
$$

### 16.2 Example A: Induction Proof

Goal:

- `forall n, sum_to n = n*(n+1)/2`

MCTS explores `induction n` branch heavily,
but still explores alternatives due to exploration term.

### 16.3 Example B: Deep Rewriting

Many valid rewrites exist.
MCTS avoids over-committing early,
and gradually concentrates visits on productive branch patterns.

### 16.4 Strengths

- better long-horizon planning
- strong exploration/exploitation balance

### 16.5 Weaknesses

- compute heavy
- difficult hyperparameter tuning
- more complex logging requirements

## 17. Repository Integration Plan

This section maps design pieces to this repo.

### 17.1 Existing Assets You Already Have

- proof state parsing
- graph conversion
- PyG data path
- baseline model training
- run analysis and ablation scripts

### 17.2 Proposed New Modules

Recommended additions:

- `atp_lean_gnn/lean_env.py`
- `atp_lean_gnn/search.py`
- `atp_lean_gnn/symbolic_bridge.py`

### 17.3 Suggested Responsibilities

`lean_env.py`:

- load theorem
- expose current state
- apply structured action
- return transition result

`search.py`:

- frontier data structures
- search loop implementations
- dedup cache
- budget controls

`symbolic_bridge.py`:

- state fingerprints
- canonicalization helpers
- relevance integration helpers

### 17.4 Script-Level Entrypoints

Possible scripts:

- `scripts/run_search.py`
- `scripts/replay_trace.py`
- `scripts/eval_search_suite.py`

### 17.5 Artifact Layout Suggestion

```text
runs/
  search/
    run_<timestamp>/
      config.json
      trace_index.jsonl
      expansions.jsonl
      solved.jsonl
      failed.jsonl
      summary.json
      summary.md
```

### 17.6 Trace Event Schema

Each event should include:

- run_id
- theorem_id
- state_id
- depth
- candidate_count
- selected_action
- selected_rank
- policy_score
- value_score
- transition_status
- elapsed_ms

This one schema will save weeks of debugging later.

## 18. Worked Example Bank

This section intentionally contains many examples.
Each example is short and concrete.

### Example 1: Modus Ponens Chain

Context:

- `h1 : P -> Q`
- `h2 : Q -> R`
- `hp : P`
Goal:

- `R`

Backward plan:

1. `apply h2`
2. `apply h1`
3. `exact hp`

Forward plan:

1. derive `Q`
2. derive `R`
3. close by exact

Hybrid behavior:

Backward picks `apply h2`.
Forward not needed.

### Example 2: Conjunction Build

Context:

- `ha : A`
- `hb : B`
Goal:

- `A and B`

Backward:

1. `constructor`
2. subgoal `A` solved by `exact ha`
3. subgoal `B` solved by `exact hb`

Forward:

1. derive `A and B`
2. `exact` it

Hybrid:

Policy likely prefers `constructor` route.

### Example 3: Disjunction Left

Context:

- `ha : A`
Goal:

- `A or B`

Backward:

1. `left`
2. `exact ha`

Forward:

1. derive `A or B` from `A`

Hybrid:

Either route works.
Policy should learn cheap constructor tactics.

### Example 4: Equality Rewriting in Goal

Context:

- `h : x = y`
Goal:

- `f x = f y`

Backward:

1. `rw [h]`
2. goal becomes `f y = f y`
3. `rfl`

Forward:

1. derive transformed forms from `h`
2. may still need target alignment

Hybrid:

Backward is naturally efficient.

### Example 5: Rewrite in Hypothesis Then Use It

Context:

- `h1 : x = y`
- `h2 : P x`
Goal:

- `P y`

Backward:

1. `rw [<- h1]` in goal or `rw [h1] at h2`
2. then `exact h2`

Forward:

1. derive `P y` from `h1` and `h2`

Hybrid:

Hierarchical action helps choose rewrite locus correctly.

### Example 6: Chain of Less-Than Facts

Context:

- `a < b`
- `b < c`
- `c < d`
Goal:

- `a < d`

Backward only:

May branch on unknown intermediates.

Forward assistance:

Derive `a < c` and `b < d`.
Backward then closes quickly.

### Example 7: Simple Arithmetic Identity

Goal:

- `n + 0 = n`

Backward:

1. `rw [Nat.add_zero]`
2. `rfl`

Hybrid:

Policy should strongly prioritize canonical simp/rewrite lemmas.

### Example 8: Symmetry via Existing Lemma

Context:

- `h : a = b`
Goal:

- `b = a`

Backward:

1. `exact Eq.symm h` or `symm; exact h`

Forward:

1. derive symmetric form once

Hybrid:

Premise head should score symmetry tools highly.

### Example 9: Existential Witness

Context:

- `n : Nat`
Goal:

- `exists m, m = n`

Backward:

1. `refine Exists.intro n ?_`
2. `rfl`

Hybrid:

Action family must include witness-construction style actions.

### Example 10: Contradiction Closure

Context:

- `h1 : P`
- `h2 : not P`
Goal:

- `False`

Backward:

1. `exact h2 h1`

Hybrid:

Policy should learn contradiction motifs.

### Example 11: Cases Split

Context:

- `h : A or B`
Goal:

- `B or A`

Backward:

1. `cases h with`
2. branch 1 `A` -> prove `B or A` by `right`
3. branch 2 `B` -> prove `B or A` by `left`

Hybrid:

Branch prioritization matters if many `cases` options exist.

### Example 12: Induction Skeleton

Goal:

- `forall n, P n`

Backward:

1. `intro n`
2. `induction n with`
3. solve base and step

Hybrid:

Value head helps prioritize promising step-case tactics.

### Example 13: Function Congruence

Context:

- `h : x = y`
Goal:

- `g (f x) = g (f y)`

Backward:

1. `rw [h]`
2. `rfl`

Forward:

Could derive congruence facts,
but backward is shorter.

### Example 14: Local Hypothesis Better Than Library Lemma

Context:

- `hlocal : A -> C`
- many global lemmas `A -> C`
Goal:

- `C`

Hybrid lesson:

Premise reranker should often prefer local hypothesis over distant library theorem.

### Example 15: Rewrite Direction Sensitivity

Context:

- `h : x = y`
Goal:

- `y = x`

Need reverse direction.

Hierarchical action:

1. choose `rw`
2. choose premise `h`
3. choose reverse direction

Without direction head,
flat policies make many avoidable mistakes.

### Example 16: Goal Ordering With Multiple Goals

State has goals:

1. easy arithmetic goal
2. hard structural goal

Hybrid lesson:

Value-guided search may solve easy goal first
to simplify context for hard goal.

### Example 17: Forward Fact Is Irrelevant

Forward module derives 50 facts.
Only 2 are relevant.

Relevance filter should discard 48.
This is where forward module wins or loses.

### Example 18: Dedup Needed

Two different tactic sequences produce same normalized state.

Without dedup:

- frontier bloats

With hash-based dedup:

- only one copy kept
- compute saved

### Example 19: Branch Loop

Rewrite A then rewrite back to original.

Need loop detection and repeat penalties.

### Example 20: Timeout Case

No proof found within budget.

A good system still returns:

- best partial trace
- top failed branches
- diagnostics for future training

## 19. Training Strategy

Do this in phases.

### 19.1 Phase 1: Supervised Policy Bootstrap

Use existing step data.
Train tactic-family prediction first.

### 19.2 Phase 2: Premise Ranking Supervision

Collect positive premise labels from successful traces.
Construct hard negatives from same candidate set.

### 19.3 Phase 3: Value Head Supervision

Label states by downstream outcomes:

- solved within budget
- not solved

Use calibrated probability targets.

### 19.4 Phase 4: Search-Generated Fine-Tuning

Run search.
Collect on-policy traces.
Fine-tune policy and value.

This reduces distribution shift between training and deployment.

### 19.5 Data Hygiene Notes

- stratify by theorem family
- keep splits fixed
- version datasets and parser state
- log environment versions

## 20. Evaluation Framework

Measure both quality and efficiency.

### 20.1 Primary Metrics

- solve rate within timeout
- median expansions per solved theorem
- median wall-clock per solved theorem

### 20.2 Secondary Metrics

- invalid-action rate
- average branch factor after filtering
- premise rank of successful action
- loop rate
- timeout rate

### 20.3 Required Baselines

Compare against:

1. symbolic-only heuristic search
2. neural one-step greedy rollout
3. backward-only hybrid
4. backward+forward hybrid

### 20.4 Ablation Grid

At minimum:

- forward off vs on
- relevance off vs on
- value head off vs on
- hierarchical actions off vs on
- beam vs MCTS

### 20.5 Robustness Checks

- run multiple seeds
- evaluate across theorem families
- evaluate across difficulty buckets

## 21. Failure Modes And Mitigations

### 21.1 Premise Explosion

Symptom:

- too many candidate premises

Mitigation:

- strict symbolic prefilter
- neural rerank top-k

### 21.2 Forward Explosion

Symptom:

- forward module generates too many facts

Mitigation:

- budget caps
- relevance threshold
- dedup hashes

### 21.3 Overconfident Wrong Policy

Symptom:

- high policy scores on invalid actions

Mitigation:

- symbolic legality gate
- confidence calibration
- hard negative mining

### 21.4 Looping

Symptom:

- repeated state cycles

Mitigation:

- transposition table
- repeat penalties
- no-op detector

### 21.5 Sparse Reward

Symptom:

- little learning signal on hard proofs

Mitigation:

- shaped proxies
- curriculum by difficulty
- richer trace-level supervision

## 22. Suggested Roadmap (Practical)

### Milestone M1

Backward beam + policy only.

Deliverables:

- runnable search script
- trace logs
- initial solve-rate benchmark

### Milestone M2

Add premise reranker.

Deliverables:

- candidate retrieval report
- premise rank metrics

### Milestone M3

Add value head and best-first scoring.

Deliverables:

- value calibration plots
- efficiency lift report

### Milestone M4

Add bounded forward assistant.

Deliverables:

- relevance precision/recall on kept facts
- solve-rate delta on hard subset

### Milestone M5

Try bidirectional meet-in-the-middle.

Deliverables:

- meet statistics
- canonicalization error report

### Milestone M6

Try MCTS if M1-M5 saturate.

Deliverables:

- compute vs quality tradeoff curves

## 23. Config Template Suggestions

Use explicit config keys.

```json
{
  "search": {
    "algorithm": "backward_beam",
    "max_expansions": 2000,
    "max_depth": 40,
    "beam_width": 32,
    "timeout_seconds": 60,
    "dedup": true,
    "repeat_penalty": 0.2
  },
  "scoring": {
    "alpha_policy": 1.0,
    "beta_value": 0.5,
    "gamma_depth": 0.05,
    "delta_repeat": 0.2
  },
  "forward": {
    "enabled": false,
    "max_new_facts": 20,
    "max_rule_depth": 2,
    "relevance_threshold": 0.7
  },
  "model": {
    "policy_checkpoint": "runs/.../best.pt",
    "value_checkpoint": "runs/.../value.pt"
  }
}
```

## 24. Pseudocode Library

### 24.1 Backward Beam

```text
function backward_beam(root):
    frontier <- [root]
    visited <- {}
    while budget_ok:
        S <- pop_best(frontier)
        if is_solved(S): return success
        if hash(S) in visited: continue
        visited.add(hash(S))
        C <- symbolic_candidates(S)
        C <- top_k_policy(S, C)
        for a in C:
            O <- execute(S, a)
            if O == Solved: return success
            if O is state S2:
                push(frontier, S2, score(S2))
    return fail
```

### 24.2 Forward Assistant

```text
function forward_assist(S):
    facts <- generate_forward_facts(S, budget)
    kept <- []
    for f in facts:
        if relevance(f, S) > tau:
            kept.append(f)
    return augment_state(S, kept)
```

### 24.3 Bidirectional Meet

```text
function bidirectional_search(S0):
    B <- init_backward(S0)
    F <- init_forward(S0.context)
    while budget_ok:
        expand(B)
        expand(F)
        m <- find_meeting(B, F)
        if m exists:
            trace <- compose_trace(m)
            if validate(trace):
                return success
    return fail
```

## 25. FAQ

### Q1. Why not just generate full tactics with an LLM?

Because legality and precision are strict,
and unconstrained generation adds huge variance.

Structured actions with symbolic gates are safer and easier to improve.

### Q2. Should forward chaining be always on?

No.
Use it when backward-only plateaus,
or on theorem families known to require intermediates.

### Q3. Is value head necessary early?

Not mandatory for first milestone,
but usually helpful once branch count grows.

### Q4. When is MCTS worth it?

When beam and best-first are saturated,
and you can afford higher compute.

### Q5. What is the minimum hybrid system worth publishing?

A backward neural-guided symbolic search
with strong baselines,
good trace diagnostics,
and reproducible solve-rate gains.

## 26. Glossary

Action:
An executable tactic choice in a proof state.

Backward chaining:
Reason from goal to required subgoals.

Forward chaining:
Reason from known facts to new facts.

Candidate generator:
Symbolic step that proposes legal actions.

Dedup hash:
Canonical fingerprint for state equivalence.

Frontier:
Set of search states waiting expansion.

Policy:
Model that ranks actions.

Premise reranking:
Model that ranks candidate facts/lemmas.

Relevance filtering:
Model that keeps only useful forward-derived facts.

Symbolic executor:
Lean-backed transition engine.

Value:
Model estimate of future solvability.

## 27. Quick Start Checklist

If you are building this now,
follow this order:

1. implement backward beam with symbolic legality
2. add policy ranking
3. add full trace logging
4. benchmark vs symbolic baseline
5. add premise reranker
6. add value scoring
7. add forward assistant with strict budget
8. run ablations
9. only then consider bidirectional or MCTS

## 28. Final Takeaway

The strongest practical path is not:

- pure neural generation
- pure brute-force symbolic search

The strongest practical path is:

- symbolic core for correctness
- neural guidance for ranking
- backward focus for target alignment
- forward assistance for intermediate construction
- disciplined logging and ablations for science

If you build in that order,
you will get a system that is:

- understandable
- debuggable
- improvable
- and actually useful for ATP research.
