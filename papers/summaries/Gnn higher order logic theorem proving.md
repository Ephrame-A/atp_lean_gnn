# Graph Representations for Higher-Order Logic and Theorem Proving

**Authors:** Aditya Paliwal, Sarah Loos, Markus Rabe, Kshitij Bansal, Christian Szegedy (Google Research)
**Venue:** AAAI 2020
**arXiv:** [1905.10006](https://arxiv.org/abs/1905.10006)

---

## 1. Background and Motivation

### What Is Higher-Order Logic?

Higher-order logic (HOL) is a formal language that generalizes first-order logic by allowing quantification not only over individuals (as in first-order logic) but also over functions and predicates themselves. This expressiveness makes HOL powerful enough to formalize most of mathematics — including real analysis, topology, measure theory, and complex analysis — but also makes automated reasoning over it significantly harder.

HOL Light is an interactive theorem prover built on HOL. A user interacts with it by applying **tactics** — proof commands that transform a current proof goal into zero or more subgoals. For example, applying the tactic `REWRITE_TAC [lemma_A]` rewrites the goal using `lemma_A` and may simplify or close it. Proving a theorem is the process of reducing the initial goal to nothing (zero subgoals) via a sequence of such tactic applications.

The challenge for automation: at each step, the prover must choose *which tactic* to apply and *which premises* (previously proven theorems or definitions) to supply as arguments to that tactic. With 19,262 eligible premises and 41 possible tactics at each step, the search space is enormous.

### The HOList Benchmark

The paper uses the **HOList** benchmark (Bansal et al. 2019), which wraps HOL Light in a stateless API and provides a dataset of over 20,000 theorems with their human-written proofs. The corpus focuses on **complex analysis**, making it a mathematically rich and challenging domain.

The pre-existing neural prover **DeepHOL** also comes with HOList. DeepHOL uses a WaveNet-style sequence model to embed theorem statements as strings, then does tactic and premise prediction. The WaveNet model closes **32.65%** of validation theorems — the baseline this paper seeks to improve upon.

### Why Prior Approaches Fall Short

**Sequence models (WaveNet, LSTM):** These treat a formula as a flat sequence of tokens (characters or words). While this captures local token patterns, it entirely ignores the **hierarchical syntactic structure** of the formula. Two syntactically very different formulas that encode the same mathematical object can look very different as strings. Conversely, two strings that look similar can encode very different mathematical objects. The sequential representation has no way to encode the recursive tree structure of formal expressions.

**TreeRNNs (Tree-structured Recurrent Neural Networks):** These are the natural step up — they process the abstract syntax tree (AST) of a formula recursively. A TreeRNN computes the embedding of each internal node from the embeddings of its children, working from the leaves upward to the root. The final root embedding represents the whole formula.

The problem with TreeRNNs is subtle but important: because they are purely **bottom-up**, every subexpression gets exactly one fixed embedding, regardless of the context in which it appears. Consider the variable `x` appearing in three different positions within the formula `∀x : x = x`. In a TreeRNN, every occurrence of `x` gets the same embedding — the TreeRNN cannot distinguish "x in the left side of the equation" from "x in the right side." More broadly, a TreeRNN encodes what a subexpression *is*, but not *where it is* or *how it is used* in the larger formula.

The paper's central hypothesis is that **context** — where a subexpression appears — is at least as important as **content** — what the subexpression itself is. This hypothesis is validated experimentally, and is the paper's most important finding.

---

## 2. The Setting in Detail

### HOL Light Formulas as S-expressions

HOL Light provides all theorem statements and proof goals as **S-expressions** — a parenthesized prefix notation that directly encodes the abstract syntax tree. For example, the formula `f(x)` (function `f` applied to argument `x`) is written:

```
(a (v (fun A B) f) (v A x))
```

Breaking this down:
- `a` — function application node, always with exactly 2 children
- `(v (fun A B) f)` — variable `f` of type `fun A B` (a function from type `A` to type `B`)
- `(v A x)` — variable `x` of type `A`

The full vocabulary of node types is small:
- `a` — function application
- `v` — variable (carries name and type)
- `l` — lambda abstraction (anonymous function)
- `c` — constant (a named globally defined symbol)
- `fun` — function type constructor
- Additional type constructors (e.g., `bool`, `prod`)

Crucially, all higher-order constructs reduce to these primitives. Even the universal quantifier `∀` is not a built-in; it is defined as a higher-order function: `∀ ≡ λf. (f = λx. True)`. So every formula, however complex mathematically, is just a tree of `a`, `v`, `l`, `c`, and type nodes.

### What the Model Must Do at Each Proof Step

At every step of proof search, the system receives the **current goal** — an S-expression representing the formula to be proved right now — and must output:

1. **A tactic prediction:** Which of the 41 available tactics to apply (e.g., `REWRITE_TAC`, `MESON_TAC`, `SIMP_TAC`, `ARITH_TAC`). This is a 41-class classification.

2. **A premise ranking:** For each of the 19,262 theorems/definitions in the library, a relevance score estimating how useful that premise is as an argument to the chosen tactic. The top 20 scoring premises are selected as tactic arguments.

Both outputs are computed simultaneously at each step, and the proof search continues (branching over multiple tactic/premise combinations) until a branch closes the goal or a search budget is exhausted.

This is harder than standard premise selection tasks, which only predict premises once at the top-level theorem. Here, premise prediction must work correctly at every subgoal generated during the proof, including subgoals the human proof never explicitly considered.

---

## 3. Converting Formulas to Graphs

The paper's first major contribution is a systematic study of how to represent HOL S-expressions as graphs for GNN processing.

### 3.1 The Plain AST Graph

The most direct approach: take the S-expression tree and convert it into a directed graph. Each node in the S-expression becomes a graph node. Edges are added in **both directions**:
- Parent → child edges (so each node knows about its children)
- Child → parent edges (so each node knows about its parent)

Edge labels encode the child index (0 for left child, 1 for right child), preserving the original tree structure so the formula can be reconstructed from the graph.

This bidirectional graph is the baseline graph representation. It already differs from TreeRNNs by allowing information to flow both downward (from parent to child) and upward (from child to parent) during message passing.

### 3.2 Subexpression Sharing — The Key Innovation

In the plain AST, if the same subexpression appears multiple times in a formula, it is represented as multiple separate subtrees. For example, in `∀x : x = x`, the variable `x` appears three times, and each occurrence is a separate node (or subtree) in the plain AST.

**Subexpression sharing** merges all nodes (and subtrees) that represent syntactically identical subexpressions into a single node. After merging, the single `x` node has three incoming parent edges — one from each position where `x` originally appeared.

This transforms the tree into a **Directed Acyclic Graph (DAG)**. The effects are significant:

**Graph compression:** The shared representation is much smaller. The paper's appendix shows that subexpression sharing nearly eliminates the long tail of very large graphs. Formulas that would have had hundreds or thousands of nodes in the plain AST are compressed to tens or low hundreds of nodes.

**Richer signal:** A shared node receives gradient information from all its occurrences simultaneously during training. The model learns an embedding for a subexpression that must be coherent across all the contexts where it appears — a form of consistency constraint that the plain AST cannot enforce.

**Type sharing:** Sharing also happens over types. If variable `x` has type `A`, then every other expression with type or sub-type `A` is now connected through the same type node. This implicitly encodes type-level structural similarity between different parts of the formula.

Concretely: the formula `∀x : x = x` has 27 nodes in the plain AST, but only 15 nodes under subexpression sharing (Figure 1 in the paper). As formulas grow longer and more complex, the compression becomes more dramatic.

### 3.3 Leaf Sharing — A Cautionary Example

Leaf sharing is a weaker version: only merge *leaf nodes* (nodes with no children) that have the same token, such as the type variable `A`, the type `bool`, or a variable name `x`. Internal nodes are not merged.

Intuitively this seems like a reasonable middle ground. Experimentally, it is **catastrophic** — leaf sharing models with any message passing are *worse* than the 0-hop (no message passing) baseline in all configurations.

Why? Because leaf sharing merges semantically unrelated things. Every occurrence of the token `x` — whether it refers to the same variable or different variables in different scopes — gets merged into a single node. Every occurrence of type `A` — whether it refers to the same type or different type variables named `A` — gets merged. This destroys the structural distinctiveness that GNNs rely on to learn meaningful representations. The message passing then propagates corrupted information across the graph, making things worse than not passing messages at all.

This is a strong lesson: **sharing must be semantically principled**. Subexpression sharing is principled because it respects the formal syntax (two identical S-expressions are genuinely identical objects). Leaf sharing is not principled — it conflates structurally different occurrences that happen to use the same token.

### 3.4 Variable Blinding

After constructing the graph (with subexpression sharing), replace all variable name tokens with a single uniform token `x`. Nodes representing different variables are still distinct graph nodes with distinct positions and connections — only their name labels are erased.

This ablation tests whether human-assigned variable names carry learning signal. The result is a large performance drop, showing that yes, variable names are meaningful. Mathematicians tend to choose names that reflect the mathematical role of a variable (`n` for integers, `f` for functions, `ε` for small quantities, etc.), and the model learns to exploit these naming conventions.

### 3.5 Top-Down vs. Bottom-Up Message Passing

These ablations are the most conceptually important in the paper.

**Top-down only:** Remove all child→parent edges from the graph. Only parent→child edges remain. Information flows from the root of the formula downward to the leaves. A leaf node can learn from its context (where it sits in the formula) but cannot contribute information back upward.

**Bottom-up only:** Remove all parent→child edges. Only child→parent edges remain. This exactly mimics the information flow of a TreeRNN — leaves propagate information up to the root, but the root cannot push context back down.

The results:

| Direction | 8 Hops | 12 Hops |
|---|---|---|
| Bidirectional (full) | 47.22% | **49.95%** |
| Top-down only | **48.24%** | 48.40% |
| Bottom-up only | 41.86% | 40.99% |

**Top-down substantially outperforms bottom-up.** Even though top-down prevents nodes from seeing their children's content, it performs far better than bottom-up, which prevents nodes from seeing their context. This is the opposite of what TreeRNNs assume.

The interpretation: the mathematical role of a subexpression — the context in which it is used — is more informative than the subexpression's own internal structure. When deciding whether a particular sub-formula is relevant to a proof step, what matters most is *where in the goal that sub-formula appears*, not just what it contains.

Bidirectional message passing is best overall, as it combines both kinds of information. But the dramatic gap between top-down and bottom-up motivates a clear design recommendation: any formula encoder should prioritize contextual (top-down) information, not just content (bottom-up).

### 3.6 Random Edges

Add 3 random outgoing edges per node to random other nodes in the graph, labeled distinctly so the GNN can distinguish them from structural edges. This approximates an **expander graph** — a graph with excellent connectivity properties where information can travel across the graph in few hops.

Result: random edges help for shallow networks (2 hops) — they extend the effective receptive field of each node. But for deep networks (8–12 hops), they hurt, presumably because spurious connections inject noise into the embeddings as the GNN has already accumulated sufficient structural information through legitimate edges.

---

## 4. Model Architecture in Detail

### 4.1 GNN Message Passing

The GNN processes a labeled graph `G = (V, E, l_V, l_E)` where:
- `V` = set of nodes (AST nodes)
- `E` = set of directed edges
- `l_V` = node label (maps each node to a token in the vocabulary of ~1,200 symbols)
- `l_E` = edge label (0 or 1, encoding left vs. right child)

**Initialization:** Each node `v` and each edge `e` is embedded into a 128-dimensional vector by a small MLP:

```
h¹_v = MLP_V(x_{l_V(v)})     (node initial embedding from token lookup)
h_e  = MLP_E(l_E(e))          (edge embedding from label)
```

**Message passing (rounds t = 2 to T):** For each edge `(u → v)`, compute a message that depends on both the source node's embedding, the target node's embedding, and the edge embedding. Crucially, the model uses **two separate MLPs** for messages coming from parent nodes vs. messages coming from child nodes:

```
s^t_{u,v} = MLP^t_edge([h^{t-1}_u, h^{t-1}_v, h_e])       (parent-to-child message)
ŝ^t_{u,v} = MLP̂^t_edge([h^{t-1}_u, h^{t-1}_v, h_e])      (child-to-parent message)
```

**Aggregation:** For each node `v`, sum all messages from parents separately from all messages from children, then update the node's embedding with a residual connection:

```
h^t_v = h^{t-1}_v + MLP_aggr(h^{t-1}_v, Σ s^t_{u,v} over parents, Σ ŝ^t_{u,v} over children)
```

The residual connection (`h^{t-1}_v + ...`) prevents vanishing gradients and ensures that deeper rounds refine rather than replace earlier representations.

After T=12 rounds, each node has a 128-dimensional embedding that incorporates information from its 12-hop neighborhood — every node reachable within 12 edges.

**Why separate parent/child MLPs?** This is what makes the GNN respect the directionality of the AST. A standard GNN would treat all neighbors symmetrically. By using different MLPs for upward vs. downward messages, the model can learn to treat "I am being used as an argument to this function" differently from "I contain this subexpression as a component."

### 4.2 Graph Pooling

After message passing, there is one 128-dimensional embedding per node. The whole formula needs to be compressed into a single fixed-size vector (the formula embedding).

The paper uses **max pooling** over all node embeddings, preceded by two 1×1 convolution layers that expand the dimension:

```
128-d node embeddings
    → Conv 1×1 → 512-d
    → Conv 1×1 → 1024-d
    → max pool over all nodes
    → single 1024-d formula embedding
```

Max pooling is chosen over mean pooling or sum pooling because it selects the most active feature across all nodes for each dimension — effectively asking "does any part of this formula have property X?" rather than averaging or accumulating. This is well-suited to premise selection, where one particularly relevant subexpression might determine the whole relevance of a premise.

### 4.3 The Full Dual-GNN Architecture

The full model uses **two separate GNNs** (GNN-1 and GNN-2), one for encoding the current proof goal and one for encoding candidate premises. They have identical architectures but **do not share weights**. This is important: the model learns that "being a goal" and "being a premise" are different roles that require different representation strategies.

After embedding:

**Tactic Classifier:** Takes only the goal embedding → two fully connected layers → softmax over 41 tactics.

**Premise Scorer (Combiner Network):** Takes the goal embedding G and premise embedding P → concatenates `[G, P, G⊙P]` (where `⊙` is element-wise multiplication, a standard way to capture interaction between two vectors) → three fully connected layers → sigmoid score.

The sigmoid score represents "how useful is this premise for proving this goal?" A score close to 1 means the premise is likely relevant; close to 0 means not relevant.

### 4.4 Inference Efficiency via Pre-computation

At inference time (during proof search), the model needs to score all 19,262 premises against the current goal. This would be expensive if both the goal and all premises needed to be re-embedded for every goal.

The solution: premise embeddings `P(p_i)` are **pre-computed once** for all premises and cached. When a new goal arrives, only the goal embedding `G(g)` is computed fresh via GNN-1. Then the combiner network — which is small — runs on `[G(g), P(p_i)]` for each premise. The expensive GNN computation is amortized across all proof steps.

---

## 5. Training

### Imitation Learning

The model is trained purely by **imitation learning** — learning to replicate the choices made by human mathematicians in the HOList training proofs. There is no reinforcement learning, no exploration, and no interaction with the prover during training. The model sees (goal, tactic, premises-used) triples and learns to predict the human's choice.

This is intentionally limited — human proofs may not be the only valid proofs, and the model is never rewarded for finding better proofs. The paper notes that combining imitation learning with RL is future work, but the imitation-only model already substantially outperforms DeepHOL's best RL model (49.95% vs. 38.9%).

### Positive and Negative Examples for Premise Scoring

For each proof step:
- **Positive premise:** A premise that the human actually used at this step (sampled uniformly from the set of used premises if multiple were used)
- **Negative premises:** 15 randomly sampled theorems from the full library

To make training more efficient, the batch reuse trick is applied: all 256 premises embedded in a batch (16 positive + 15×16=240 negatives) serve as negative examples for all 16 goals in the batch. This gives each goal 255 negative examples instead of 15, at no additional computation. The effective batch size for the premise scorer becomes 4,096 (16 goals × 256 premise comparisons).

### Loss Functions

Three losses are combined:

**1. Tactic cross-entropy (weight 1.0):** Standard classification loss. The predicted tactic distribution should put high probability on the tactic the human used. Note: this is an approximation, since other tactics may also be valid — but the training data only records one proof per theorem.

**2. Pairwise premise cross-entropy (weight 0.2):** For each (goal, positive premise, negative premise) triple, the positive should score higher. A standard binary cross-entropy loss.

**3. AUCROC loss (weight 4.0):** This is the dominant loss for premise scoring. For each positive premise i and each negative premise j in the batch, the loss penalizes cases where the negative scores higher than the positive:

```
AUCROC_batch = Σ_i Σ_j loss(logit_i - logit_j)
loss(l) = ln(1 + e^{-l})
```

The loss for pairs comparing a positive and negative *for the same goal* is doubled, since the final task is to rank premises for a single goal. The AUCROC loss directly optimizes the ranking of positives above negatives, which aligns better with the downstream task (selecting top-k premises) than cross-entropy alone.

---

## 6. Results and Analysis

### Main Results

| Model | % Proofs Closed (Validation) |
|---|---|
| WaveNet — DeepHOL baseline, S-expression as string | 32.65% |
| Bag-of-words + max pooling | 37.98% |
| **Subexpression sharing, 12-hop GNN** | **49.95%** |

The bag-of-words result (37.98%) is already notable — it beats the WaveNet model while being architecturally simpler. This suggests the WaveNet's sequential processing of the S-expression string was actively harmful, perhaps because the string encoding of a tree introduces spurious long-range dependencies. A bag-of-words model that ignores all sequential structure performs better.

The GNN result (49.95%) is then a large jump over bag-of-words, demonstrating that structural information — specifically, the graph structure of the formula — provides substantial signal that bag-of-words cannot capture.

### Ablation Results in Full

| Representation | 0 Hops | 2 Hops | 4 Hops | 8 Hops | 12 Hops |
|---|---|---|---|---|---|
| AST (plain) | 40.18% | 43.84% | 44.58% | 46.66%* | 45.67%* |
| Leaf sharing | 41.76% | 33.89% | 29.24% | 29.51% | 30.51% |
| Leaf sharing + var. blinding | 31.78% | 32.18% | 32.80% | 30.04% | 31.00% |
| **Subexpression sharing** | **40.86%** | **42.94%** | **46.94%** | **47.22%** | **49.95%** |
| Subexp. + var. blinding | 31.75% | 34.44% | 35.96% | 34.07% | 37.36% |
| Subexp. + random edges | 41.24% | 43.68% | 43.84% | 42.63% | 42.94% |
| Subexp. + top-down only | 40.55% | 43.59% | 45.51% | 48.24% | 48.40% |
| Subexp. + bottom-up only | 39.72% | 40.58% | 41.16% | 41.86% | 40.99% |

*Asterisked results required smaller batch size due to memory constraints on larger graphs.

### Reading the Ablation Table — Key Patterns

**Scaling with hops:** For both plain AST and subexpression sharing, performance consistently increases with more hops (more rounds of message passing). Each additional hop extends the neighborhood each node can see — at 12 hops, a node can incorporate information from any other node within 12 edges. This confirms that the structural information propagated by message passing is genuinely useful, and more of it is better.

**Subexpression sharing scales better than plain AST:** At 0 hops (essentially a bag-of-nodes model), both representations perform similarly (~40%). But as hops increase, subexpression sharing pulls ahead. At 12 hops, subexpression sharing reaches 49.95% while plain AST only reaches 45.67% (and begins declining, likely due to memory constraints forcing smaller batch sizes). Subexpression sharing creates a denser, more connected graph where information travels more efficiently.

**The catastrophic effect of leaf sharing with message passing:** Leaf sharing at 0 hops is fine (41.76%), but adding even 2 hops drops performance to 33.89%, well below the no-message-passing baseline. The message passing actively destroys the representation. This is because leaf sharing creates false connections between unrelated nodes, and message passing then spreads this confusion throughout the graph.

**Variable blinding (subexp. + var. blinding vs. subexp.):** At 12 hops, removing variable names drops performance from 49.95% to 37.36% — a 12.6 percentage point drop. Variable names account for a substantial fraction of the total performance. Mathematicians' naming conventions encode domain knowledge that the model exploits.

**Top-down dominates bottom-up at scale:** At 12 hops, top-down (48.40%) vs. bottom-up (40.99%) is an 7.4 percentage point gap. This is the key experimental result supporting the paper's central thesis about the importance of context.


## 7. Implementation Details

**GNN hyperparameters:**
- Node/edge embedding dimension: 128
- MLP layers: 2 hidden layers with sizes 256 and 128, ReLU activations
- MLPs do not share weights across message passing rounds
- Dropout of 0.5 inside all GNN MLPs

**Training:**
- Adam optimizer, learning rate 0.0001, decay rate 0.98
- Dropout of 0.3 (keep prob 0.7) before every dense layer outside the GNN
- Exponential moving average (EMA/Polyak averaging) at rate 0.9999 per step for evaluation checkpoints

**Hardware:** 8 NVIDIA Tesla V100 GPUs for distributed training, plus a separate GPU for evaluation and a CPU parameter server.

**Evaluation:** Because running the full theorem prover on the validation set takes several hours (even distributed), proxy metrics (tactic accuracy, pairwise ranking accuracy) are used during training, and the full prover evaluation is run only on the best checkpoint.

---

## 8. Key Conceptual Contributions

### 8.1 Representation Design Is as Important as Architecture

The ablation results show that the choice of graph representation has a larger effect on performance than architectural variations or even the number of message passing rounds. Subexpression sharing vs. leaf sharing vs. plain AST produce dramatically different results for the same GNN architecture. This lesson generalizes: for any application of GNNs to structured symbolic data, the design of the graph representation deserves at least as much attention as the GNN architecture itself.

### 8.2 Context Beats Content for Logical Subexpressions

The top-down > bottom-up result is the paper's most important conceptual contribution. It overturns the implicit assumption behind TreeRNNs (and many formula encoders) that the meaning of a formula is computed compositionally from its parts. Instead, the paper shows that the role of a subexpression — its place in the larger formula — is more informative than its own internal structure.

This has an intuitive interpretation: in a proof context, the goal is a specific mathematical statement, and what matters for finding the right premise is understanding the high-level structure of the goal and where the parts that need to be addressed are located. A subexpression like `x + 1` means something different as the left side of an inequality than as an argument to a function — and that difference is about context, not content.

### 8.3 Subexpression Sharing Encodes a Semantic Inductive Bias

When two occurrences of the same subexpression are merged into one node, the model is given an explicit structural signal that they are the same mathematical object. This is semantically true — in formal logic, two syntactically identical subexpressions are definitionally equal. Representing them as the same node leverages this fact. TreeRNNs and plain ASTs cannot express this relationship.

The value of this inductive bias grows with more message passing rounds. At 0 hops, shared and unshared representations perform similarly. At 12 hops, shared representations are significantly better because the dense cross-occurrence connections created by sharing allow information to flow much more efficiently through the graph.

### 8.4 End-to-End Proof Evaluation Is the Right Metric

Previous work (including Wang et al. 2017, who also used GNNs for premise selection in HOL) evaluated only by measuring prediction accuracy against human proofs — a proxy metric that does not directly measure whether the model can prove new theorems. This paper evaluates all models by actually running the prover, using each model to guide proof search, and counting how many held-out theorems are closed.

This is the correct metric because it captures the full complexity of proof generation. A model could score highly on premise prediction accuracy (by memorizing common patterns) but fail to guide useful proof search. End-to-end evaluation prevents this. It also allows meaningful comparison with classical automated theorem provers, which are also evaluated by theorem count.

---

## 9. Limitations

**Local hypotheses ignored:** The model embeds only the *conclusion* of the current goal — the formula to be proved — and ignores the list of local hypotheses (previously derived facts available in the current proof context). In practice, local hypotheses are often critical: if hypothesis `H : a > 0` is available, the relevant premises are those that work with positivity assumptions. This is flagged explicitly as a major limitation and left as future work. The paper notes that GNNs can naturally extend to handle multiple formulas (goal + hypotheses) by including them all in a combined graph.

**Insufficient hop depth:** The distribution of graph depths shows that many formulas have trees of depth 20–60. With only 12 message passing rounds, information cannot propagate from the deepest leaves to the root in a single pass. The model noted in the appendix that even more hops would likely improve performance.

**Single corpus:** All experiments are on HOL Light's complex analysis corpus. Higher-order provers like Lean, Coq, and Isabelle/HOL use different logics, different representation conventions, and different mathematical libraries. Whether these findings generalize — especially the subexpression sharing and top-down advantages — is untested.

**Imitation learning only:** The model is trained on human proofs and never interacts with the prover during training. It cannot discover proof strategies that humans don't use. DeepHOL's best RL model reaches 38.9% despite being architecturally weaker — combining this paper's representations with RL exploration is a natural extension.

**Static premise set:** The model treats all 19,262 premises as a fixed set. It does not model dependencies between premises or use the fact that some premises are proved using others.

---

