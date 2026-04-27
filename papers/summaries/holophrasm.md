# Holophrasm: A Deep Review
### *A Neural Automated Theorem Prover for Higher-Order Logic (2016)*
**Daniel P.Z. Whalen — Stanford University**

---

## 0. Historical Context

Holophrasm was published in 2016 — the same year AlphaGo beat Lee Sedol. Transformers didn't exist yet. The system uses GRUs (Gated Recurrent Units). There was no Lean4, no Mathlib. The formal system used here is **Metamath** — a much more primitive language than modern proof assistants.

The field's state of the art at the time: systems that proved ~40% of Mizar theorems, all relying on hand-crafted features engineered by human experts.

Holophrasm's core claim: **the first effective complete Automated Theorem Prover to not exploit hand-crafted features.** Everything is learned from data. That's its historical significance.

---

## 1. The Metamath Format — Understanding the Arena

Before the algorithm, you need to understand what Metamath is, because it is fundamentally different from tactic-based systems like Lean4.

In Lean4, you write proofs using *tactics* — high-level commands like `intro`, `cases`, `ring`. In Metamath, there are no tactics. There are only **metatheorems and substitutions**. Everything reduces to one primitive operation: find a theorem whose assertion matches your goal after substitution, then discharge all its hypotheses.

### 1.1 Structure of a Metamath Theorem

Every theorem `T` has four components:

- **Assertion (aT):** The claim being made — a well-formed formula (wff)
- **Hypotheses (eT):** What you're allowed to assume
- **Free variables (fT):** Variables appearing in the theorem, each with a type
- **Disjoint variable conditions (dT):** Pairs of variables that must remain distinct after substitution

**Example — Modus Ponens (ax-mp):**
```
Hypotheses:  ⊢ φ
             ⊢ φ ⇒ ψ
Assertion:   ⊢ ψ
```

To prove some target `⊢ ψ`, you apply Modus Ponens. This reduces proving `ψ` to proving both `φ` AND `φ ⇒ ψ` for some expression `φ` you choose. One obligation becomes two.

### 1.2 Constrained vs Unconstrained Substitutions

This distinction is the most important conceptual point in the paper.

**Constrained substitutions** — variables that appear in the assertion of `T`. When you apply `T` to prove target `a`, these variables get their values *forced* by the requirement that `T`'s assertion matches `a` after substitution. They're determined by pure pattern matching. No creativity required.

**Unconstrained substitutions** — variables that appear only in hypotheses of `T`, not in its assertion. These are *not* determined by the matching requirement. You must choose them freely.

This is where the difficulty lives. Consider Modus Ponens applied to prove `⊢ (2 + 2 = 4)`:

- `ψ` appears in the assertion `⊢ ψ`. To match your target, you're forced to set `ψ = (2 + 2 = 4)`. **Constrained — no choice.**
- `φ` appears only in the hypotheses `⊢ φ` and `⊢ φ ⇒ ψ`. It doesn't appear in the assertion at all. `φ` could be anything. **Unconstrained — must invent.**

A bad choice: `φ = "the sky is blue"` → you now need to prove sky-being-blue implies 2+2=4. Absurd.

A good choice: `φ = "1 + 1 = 2 and 1 + 1 = 2"` → leads to provable subgoals.

Choosing `φ` well requires genuine mathematical understanding of what intermediate fact would bridge to your goal. This is what the generative network is trained to do.

---

## 2. Proof Trees — The Data Structure

A Metamath proof has natural tree structure. Holophrasm makes this explicit with a **bipartite tree** of two alternating node types:

**Red nodes** — expressions to be proven. The root is the target theorem. Leaves are hypotheses of the context (assumed true without further proof).

**Blue nodes** — proof steps. Each blue node is labeled by a `(theorem T, substitution φ)` pair. A blue node says: "I will prove my parent red node by applying theorem T with substitution φ."

```
Red node: ⊢ ψ  (expression to prove)
    └── Blue node: (Modus Ponens, φ = "some_intermediate_fact")
            ├── Red node: ⊢ φ              (first hypothesis)
            └── Red node: ⊢ φ ⇒ ψ         (second hypothesis)
```

In a *partial proof tree* — the search space — red nodes can have **multiple blue children**, each representing a different attempted proof strategy. The search explores this partial tree, expanding it until the root is proven.

### 2.1 The AND/OR Structure

This is the structural insight that connects Holophrasm to all modern ATP systems:

**Red nodes are OR nodes:** A red node is proven if ANY single blue child is proven. You need one working strategy — not all of them.

**Blue nodes are AND nodes:** A blue node is proven if ALL of its red children are proven. Every hypothesis must be discharged.

This AND/OR structure means:
- At a red node: success requires finding *one* path through the OR
- At a blue node: success requires closing *every* branch of the AND
- The search must respect both conditions simultaneously

The critical consequence: when choosing which child of an AND (blue) node to explore, you should always go to the **weakest child first**. If one branch of an AND node is impossible, the whole action fails regardless of how easy the other branches are. Discovering impossibility early saves enormous compute.

---

## 3. The Search Algorithm — UCT Over Proof Trees

Holophrasm uses **UCT (Upper Confidence bound applied to Trees)** — the algorithm behind AlphaGo, adapted here for proof search. The algorithm works in passes, each pass traversing the partial proof tree downward and expanding or revisiting a node.

### 3.1 At Each Node Type

**At a red node (OR):** Two options:
1. Create a new blue child — try a new theorem not yet attempted
2. Visit the best existing blue child — go deeper into an existing strategy

**At a blue node (AND):** Always visit the **least promising child** — the unproven red child with the lowest average payoff. Always attack the bottleneck first.

### 3.2 When to Create vs Visit

The creation decision is a simple threshold rule separate from the priority formula:

```
target children = ⌈ n_a / 3 ⌉
```

Where `n_a` is the visit count of the red node.

```
if current children < ⌈ n_a / 3 ⌉:  → CREATE a new blue child
else:                                  → USE priority formula on existing children
```

This implements **progressive widening** — early visits go deep into the first few strategies before broadening. Later visits gradually add new theorems as more compute is available. The factor of 3 is a hyperparameter controlling this balance.

When a new blue child is created, the theorem chosen is the next highest-probability theorem from the relevance network's ranked expansion queue — not random.

### 3.3 The Priority Formula

When visiting existing blue children, the formula determines which to visit:

```
priority(b) = x_b/n_b  +  β · v_b/n_b  +  α · √(log n_a / n_b)
```

**Term 1: `x_b / n_b` — Average payoff (Exploitation)**

`x_b` is the total payoff accumulated under blue node `b`. `n_b` is its visit count. Their ratio is the average payoff — how well this proof strategy has been working.

This term drives the search toward strategies that have historically been productive. But used alone, it would permanently ignore underexplored branches.

**Term 2: `β · v_b / n_b` — Neural network prior (Early guidance)**

`v_b` is the initial value assigned to this blue node by the relevance and generative networks — the neural network's prior confidence in this strategy before any search has been done.

Dividing by `n_b` causes this term to shrink as evidence accumulates. Early on, when you have little data, trust the neural network. Later, trust actual search results. The constant `β = 0.5` weights this term relative to the others.

**Term 3: `α · √(log n_a / n_b)` — Exploration bonus (UCB)**

This is the mathematical core of UCT. The ratio `n_a / n_b` measures how underexplored child `b` is relative to the parent. When `n_b` is small and `n_a` is large — the parent has been visited many times but this child rarely — the bonus is large.

The logarithm makes the bonus grow slowly. The algorithm is guaranteed to revisit every child eventually — no strategy is permanently abandoned — but it does so at a measured pace.

**Concrete example with numbers:**

Parent red node visited `n_a = 20` times. Three blue children:

```
         n_b   Avg payoff   v_b    Term1   Term2   Term3   Total
B1 (MP):  15      0.80      0.9    0.80    0.03    0.16    0.99
B2 (∧I):   4      0.60      0.7    0.60    0.09    0.55    1.24
B3 (∨E):   1      0.40      0.3    0.40    0.15    1.23    1.78  ← WINS
```

B3 has the lowest average payoff and the neural network doesn't favor it — but it's only been visited once while the parent has been visited 20 times. The exploration bonus forces a revisit. If B3 is truly bad, future visits will lower its average payoff and it won't win again. If it was just unlucky, this second chance might find the proof.

### 3.4 Practical Details

**Circularity prevention:** If the search would create a red node with the same expression as one of its ancestors — a logical loop — the parent blue node is killed and the next theorem in the expansion queue is tried instead.

**Node death:** When the generative network exhausts all viable (theorem, substitution) pairs for a red node without proving it, the node is *dead*. A blue node with any dead red child is also dead. Dead nodes propagate upward and are pruned, focusing compute on viable branches.

**Parallelization:** Multiple threads traverse the tree simultaneously. The priority formula penalizes nodes with active threads exploring them — preventing all threads from piling onto the same branch.

---

## 4. The Three Neural Networks

Where Aristotle (2025) uses one unified transformer model for everything, Holophrasm uses three specialized networks. Each answers a different question at a different point in the search.

### 4.1 The Payoff Network — Is This Provable?

**Question:** Given this expression and these hypotheses, how likely is this to be provable?

**Input:** A red node — the expression + current hypotheses

**Output:** A probability ∈ [0,1]

**Role:** This is the value function. When a new red node is created, the payoff network immediately estimates its difficulty. This estimate propagates up through the AND/OR tree to guide which branches the search prioritizes.

**Training:** Positive examples = real proof steps from the training corpus. Negative examples = wrong steps generated by the relevance and generative networks (hard negatives — nearly-correct but wrong). The network learns to distinguish genuinely provable expressions from plausible-looking dead ends.

Architecture: GRU encoder over tokens, two fully-connected layers, sigmoid output.

### 4.2 The Relevance Network — Which Theorem to Apply?

**Question:** Given this expression, which theorem in the library is most likely to be useful?

**Input:** Expression `a` + hypotheses `eC`

**Output:** Probability distribution over all theorems

**Role:** Reduces the search from thousands of theorems to a small ranked list. Without this, at every red node you'd need to consider the entire Metamath library — computationally impossible.

**The caching architecture:** This is the network's most important design decision.

The network has two branches:
- Branch 1 encodes the current expression into a 128-dimensional vector `v` — computed once per red node
- Branch 2 encodes each theorem into a 128-dimensional vector `w_T` — computed once and **cached permanently**

The score for theorem T is then:
```
score(T) = v^T · W · w_T
```

Where `W` is a learned weight matrix defining what "relevant" means in this geometric space.

Since theorem vectors never change during a search session, they're precomputed before search begins. At each red node, you run Branch 1 once, then compute fast matrix products against cached theorem vectors. The computational cost is dominated by one forward pass per node, not thousands.

The learned geometry: after training, theorems about arithmetic cluster near expressions about arithmetic. Theorems about set membership cluster near set-theoretic expressions. The 128 dimensions capture mathematical relevance structure that no human engineered.

**Training:** Negative sampling loss with 4 randomly sampled viable-but-wrong theorems per positive example. This forces the network to develop fine-grained discrimination — not just "arithmetic vs logic" but which specific arithmetic theorem applies here.

**Performance:** 55.3% top-1 accuracy, 72.8% top-5, 87.4% top-20. The fact that the right theorem is only top-1 slightly over half the time is precisely why you need search — the network guides but doesn't dictate.

### 4.3 The Generative Network — What Are the Unconstrained Substitutions?

**Question:** Given this expression, these hypotheses, and a chosen theorem — what are the unconstrained variables?

**Input:** Expression `a`, hypotheses `eC`, theorem `T` to apply

**Output:** Expressions for all unconstrained free variables in `T`

**Role:** Invents the mathematically creative part of each proof step. Constrained substitutions are forced by pattern matching. Unconstrained substitutions require genuine mathematical insight — choosing the intermediate lemma that bridges hypotheses to the goal.

**Architecture:** Sequence-to-sequence model (state-of-the-art for translation in 2016). Unconstrained variables are generated one at a time. One variable is designated the TARGET. The network autoregressively generates an expression for it, conditioning on everything known. Then the next variable becomes TARGET. This continues until all unconstrained variables have substitutions.

**Beam search:** Multiple candidate substitutions are generated simultaneously. Beam width 1, 5, or 20 in experiments. More width = better coverage of possible substitutions, higher cost.

**Performance:** 39.1% accuracy at beam width 1, 51.3% at width 5, 57.5% at width 20. Without beam search, the network fails to find correct unconstrained substitutions most of the time — beam search is essential.

### 4.4 How the Three Networks Work Together

In one search pass arriving at a red node that needs a new blue child:

```
1. Relevance network → ranked list of theorems [T₁, T₂, T₃, ...]
2. Pick T₁ (next in expansion queue)
3. Constrained substitutions → determined by pattern matching (no network needed)
4. Generative network → invents unconstrained substitutions φ
5. Blue node (T₁, φ) created
6. Blue node's red children created → Payoff network evaluates each immediately
7. UCT proceeds
```

Three separate competencies, each specialized for its role.

---

## 5. Results and Honest Assessment

The system proves **14.3% of 2720 test theorems** under a budget of 10,000 passes or 5 minutes. On the first 5000 theorems in the database (simpler ones near the beginning), it reaches **45.1%**.

For 2016 with no hand-crafted features, this is a genuine achievement. The system is also efficient when it works — discovered proofs were found with a **median of only 17 passes**.

### 5.1 Where It Fails and Why

Three clear bottlenecks:

**Relevance accuracy is only 55% top-1.** Nearly half the time, the first theorem tried at a node is wrong. The search has to compensate with UCT exploration.

**Generative accuracy is only 39% at beam width 1.** Without beam search, the unconstrained substitutions are wrong most of the time. With beam width 20 it reaches 57.5% — still far from perfect.

**Deep proofs are out of reach.** A 5-minute budget or 10,000 passes isn't enough for theorems requiring hundreds of tactic steps with the right intermediate lemmas chosen throughout.

### 5.2 What Each Failure Mode Motivated

Every weakness of Holophrasm directly motivated the next decade of research:

| Holophrasm Weakness | Modern Response |
|---|---|
| Low relevance accuracy (55% top-1) | Large pretrained transformers with rich mathematical knowledge |
| Poor unconstrained substitution (39% beam-1) | LLMs with mathematical pretraining generating full proof sketches |
| Can't handle deep proofs | Lemma decomposition (Aristotle), proof repair (APOLLO) |
| Three separate networks | One unified model — policy + value from same transformer |
| No informal reasoning | Interleaved chain-of-thought + inline comments (Aristotle) |
| Tree search only | Graph search with state deduplication (Aristotle) |
| No test-time adaptation | Test-time training on specific problem (Aristotle) |

---

## 6. The Direct Line to Aristotle (2025)

Holophrasm established the paradigm. Everything since has been engineering that paradigm to scale.

**What stayed the same across a decade:**
- AND/OR proof tree structure (red=OR, blue=AND)
- UCT-based search with exploration-exploitation balance (PUCT in Aristotle)
- Neural value estimation (payoff network → value function)
- Neural action generation (generative network → policy)
- Prioritize weakest AND-child first (bottleneck-first search)
- Progressive widening of actions at each node

**What changed:**
- Three separate GRU networks → one unified transformer (policy + value from same model)
- Metamath primitive substitutions → Lean4 rich tactic language
- No informal reasoning → full chain-of-thought + inline comments co-trained with formal proof
- No lemma decomposition → full informal proof planning before formal search (Aristotle Section 2.2)
- No test-time adaptation → fine-tune on specific problem before main search
- Tree → Graph (equivalent state deduplication eliminates redundant search)
- 14% on Metamath test set → Gold medal at IMO 2025

The core algorithmic insight — that proving theorems is an AND/OR search problem amenable to UCT with learned policy and value functions — is Holophrasm's. Nine years of scaling, better models, richer formal languages, and informal reasoning integration turned 14% on Metamath into gold at the IMO.

---

## 7. Summary — One-Page Version

Holophrasm treats automated theorem proving as a search problem over a bipartite AND/OR tree of proof steps. Red nodes are expressions to prove (OR — need one strategy to work). Blue nodes are proof steps (AND — need all subgoals to close). UCT navigates this tree, balancing exploitation of promising strategies against exploration of untried ones.

Three neural networks provide the intelligence: the payoff network estimates how provable each subgoal looks; the relevance network identifies which theorem to apply next (with a caching architecture that precomputes theorem vectors to make library-scale ranking fast); and the generative network invents the unconstrained substitutions — the mathematically creative choices that constrained pattern matching cannot determine.

The key insight about unconstrained substitutions: applying a theorem requires filling in variables that don't appear in its assertion. These are genuinely free choices. Choosing well requires mathematical understanding of what intermediate fact would bridge your hypotheses to your goal. This is where the generative network operates, and where mathematical creativity lives in the Metamath formalism.

The system proves 14.3% of test theorems — modest by modern standards, but historically significant as the first complete ATP without hand-crafted features. Its architecture established the paradigm that every subsequent system in formal theorem proving — HyperTree Proof Search, AlphaProof, Aristotle — has built upon.