# ATP Project Alignment
### GNN + PLN Hybrid Theorem Prover — Team Reference Document

---

## Table of Contents

1. [What We're Building](#1-what-were-building)
2. [The Four Phases](#2-the-four-phases)
3. [The DAG Builder — What It Is and Why It Matters](#3-the-dag-builder--what-it-is-and-why-it-matters)
4. [Key Findings from the Papers](#4-key-findings-from-the-papers)
5. [How All the Papers Connect](#5-how-all-the-papers-connect)
6. [Q1 Remaining Work](#6-q1-remaining-work)
7. [Numbers to Aim For](#7-numbers-to-aim-for)
8. [Critical Design Decisions](#8-critical-design-decisions)

---

## 1. What We're Building

A **hybrid ATP system** that combines three components:

```
Lean 4 proof state (text string from LeanDojo)
        │
┌───────▼────────┐
│   DAG Builder   │  ← DONE: hash-consing, shared subexpressions
│ (lean_to_graph) │
└───────┬────────┘
        │  graph (nodes + edges → PyTorch Geometric Data object)
┌───────▼────────┐
│      GNN        │  ← Phase 1 goal: train baseline for tactic prediction
│                 │     subexpression sharing is the key design choice
└───┬─────────┬──┘
    │         │
tactic     state embedding
score      [128-dim vector]
    │         │
┌───▼──┐  ┌───▼──────────────┐
│  RL  │  │  PLN (AtomSpace)  │  ← Phase 2 & 3
│agent │  │  symbolic prover  │
└──────┘  └──────────────────┘
                │
          Lean 4 kernel  ← verifies every step, ground truth
```

**The core innovation** is the **Revision Rule**: if the GNN assigns low probability to a proof path but PLN formally validates it, PLN wins and the graph weights update — without retraining the GNN. The two systems check each other.

The GNN is the **statistical engine** — fast, pattern-matching, trained on 251k proof steps. The PLN is the **symbolic engine** — slow, exact, formally sound. Together they cover each other's blind spots.

---

## 2. The Four Phases

### Phase 1 — Foundations and GNN Baseline (Months 1–3) ← YOU ARE HERE

**Goal:** Working Lean 4 + LeanDojo environment. Data pipeline. Baseline GNN predicting next tactics from proof state DAGs.

Key activities:
- `lean_to_graph.py` — DAG builder (✓ done)
- Build vocabulary from dataset, serialize 251k DAGs to disk
- Train baseline GNN (3–5 GCN layers, hidden dim 128)
- AtomSpace "Truth Bridge" stub: `gnn_score → PLN TruthValue`
- Test LeanDojo interaction (programmatic tactic application)

Milestone: GNN achieves ~30–40% top-1 tactic prediction accuracy on validation set.

---

### Phase 2 — RL-Enhanced Proof Search (Months 4–6)

**Goal:** GNN becomes a policy + value network inside a reinforcement learning loop.

- Proof state = RL observation
- Tactic application = RL action
- Reward = progress toward goal closure (validated by Lean kernel)
- Algorithm: PPO or GRPO with online exploration / self-play
- Search: Monte Carlo Tree Search guided by GNN scores
- Symbolic pruning: PLN eliminates formally invalid branches early

Milestone: RL agent solves an acceptable range of miniF2F-easy theorems.

---

### Phase 3 — PLN Probabilistic Lemma Generation (Months 7–9)

**Goal:** When RL gets stuck, trigger the PLN module to hypothesize intermediate lemmas.

- GNN estimates P(∃ proof path) to prioritize which branches PLN explores
- PLN applies formal inference rules (deduction, abduction, transitive inference)
- Successfully proven lemmas are added to the proof context recursively
- APOLLO-style proof repair: error localization + targeted correction

Milestone: System solves a range of harder theorems via automatically generated lemmas.

---

### Phase 4 — Evaluation and Dissemination (Months 10–12)

**Goal:** Benchmark, paper, open-source release.

- Benchmarks: miniF2F, PutnamBench, selected IMO-level problems
- Metrics: proof success rate, proof length, generalization to unseen theorems
- Compare against: LeanCopilot, hammer tactics, ReProver, DeepSeek-Prover
- Deliverables: final paper, open-source repository, demo

---

## 3. The DAG Builder — What It Is and Why It Matters

### What it does

The `lean_to_graph.py` file takes a raw proof state string like this:

```
A : Type u_1
inst✝ : CommRing A
x : B
⊢ (intTrace A B) x = (trace A B) x
```

And converts it into a **Directed Acyclic Graph (DAG)** where every unique subexpression is a node and edges represent "is used by" relationships.

### Why a DAG instead of a tree

In a naive tree, the variable `A` appearing in 30 typeclass hypotheses would produce 30 separate leaf nodes. The GNN's message passing **cannot link separate nodes** — it has no way to learn that they're all the same thing.

With the DAG and hash-consing, there is **exactly one node** for `A`, and all 30 hypotheses point to it. When the GNN runs message passing, `A`'s embedding aggregates information from every expression that references it — which is precisely the structural context needed for good tactic prediction.

### The hash-consing mechanism

```python
def get_or_create(self, label: str, children: tuple) -> int:
    key = (label, children)

    if key in self._memo:
        return self._memo[key]      # ← reuse existing node

    node_id = len(self.nodes)
    self.nodes.append({"id": node_id, "label": label, ...})
    for child_id in children:
        self.edges.append((child_id, node_id))

    self._memo[key] = node_id
    return node_id
```

One dict lookup. That's the entire sharing mechanism.

### The PLN pipeline connection

The DAG feeds directly into the Truth Bridge described in the quarter plan:

```python
dag   = proof_state_to_dag(state_str)       # DAG builder
data  = dag_to_pyg(dag, vocab)              # PyG format
vec   = gnn_model(data)                     # [128-dim embedding]
score = mlp_head(vec)                       # scalar probability

# This is the "Truth Bridge" from the quarter plan
tv    = AtomSpace.TruthValue(
            strength=score,
            confidence=0.9
        )
```

The 128-dim vector from GNN pooling IS the `Vector(Current State)` the quarter plan describes as input to the Truth Bridge.

### Running the code

```bash
pip install datasets torch torch-geometric

python lean_to_graph.py              # first row of real dataset, opens browser
python lean_to_graph.py --row 42     # specific row
python lean_to_graph.py --demo       # simple Even(n+m) example, no download
python lean_to_graph.py --no-viz     # just print stats
```

---

## 4. Key Findings from the Papers

### Paliwal et al. (AAAI 2020) — Graph Representations for Higher-Order Logic

**This is the direct predecessor of your GNN module.**

| Representation | 12-hop accuracy |
|---|---|
| S-expression as string (WaveNet baseline) | 32.65% |
| Bag of words | 37.98% |
| Plain AST | 45.67% |
| **Subexpression sharing (your approach)** | **49.95%** |

**Finding 1 — Subexpression sharing is the single most important design choice.** Same architecture, same hyperparameters, only the graph representation changes. +4.3 percentage points over plain AST, +17 over string baseline.

**Finding 2 — Top-down message passing beats bottom-up.** Top-down (context flows root→leaf): 48.40%. Bottom-up (TreeRNN style, leaf→root): 40.99%. Knowing *where* a subexpression appears matters more than knowing *what* it contains. **Implication: use bidirectional edges in your GNN, not just upward.**

**Finding 3 — More hops = better, saturating around 12.** Their appendix shows graph depths of 10–30 nodes. 12 hops isn't even sufficient to fully propagate from leaf to root. Start with 5 hops in your baseline, plan for 8–12 in the final model.

**Finding 4 — Variable names carry real signal.** Variable blinding (replacing all variable names with `x`) drops performance from 49.95% to 37.36%. Human-chosen names like `CommRing`, `IsDomain`, `IsLocalization` are semantically meaningful. **Do not abstract them away in your vocabulary.**

**Finding 5 — Two GNNs, not one.** GNN-1 embeds the current goal. GNN-2 embeds candidate premises. A combiner network scores (goal, premise) pairs. The tactic classifier uses only the goal embedding. When you add premise selection in Phase 2, you'll need this dual-GNN architecture.

---

### Whalen (2016) — Holophrasm

A neural ATP for Metamath using a bandit-based proof tree search. Three neural networks:

- **Payoff network** — estimates if a subgoal is provable (directly analogous to your GNN-to-TruthValue bridge)
- **Relevance network** — predicts which theorems are useful next (analogous to your tactic classifier)
- **Generative network** — produces candidate substitutions (analogous to Phase 3 lemma generation)

The UCT-based tree search is a simplified version of the MCTS your Phase 2 will use. Read this before implementing Phase 2 search.

---

### Li et al. (COLM 2024) — Survey on Deep Learning for Theorem Proving

The most comprehensive map of the field. Key takeaways for your project:

**Current state of the art on LeanDojo benchmark:**
- Temperature scaling (Gloeckle 2023): 57.7% pass@1
- ReProver (Yang 2023 — the paper behind your dataset): ~52%
- DeepSeek-Prover: 57.7% on LeanDojo random split

**Where GNNs fit vs LLMs:** LLM-based approaches currently achieve higher raw numbers on standard benchmarks. GNN approaches are more interpretable, faster at inference, and architecturally suited to the hybrid neuro-symbolic setting your project targets. The novelty is the **PLN+GNN Revision Rule architecture**, not out-competing GPT-4 on pass@1.

**Key task taxonomy from the survey:**
- Autoformalization: informal → formal math (not your focus)
- Premise selection: given a goal, which lemmas are useful
- Proofstep generation: predict the next tactic ← **your Phase 1**
- Proof search: traverse proof tree to find valid paths ← **your Phase 2**

---

### Yang et al. (NeurIPS 2023) — LeanDojo

The paper that created your dataset. ReProver is the LM-based baseline you're comparing against. Understanding its evaluation protocol is essential — the 251k-row dataset is the extracted proof traces from Mathlib, and the train/val/test split is designed so test theorems are genuinely unseen.

---

## 5. How All the Papers Connect

```
FormulaNet (Wang 2017)
  └─ first GNN for ATP, premise selection only
       │
       ▼
Paliwal et al. (2020)  ← READ THIS FIRST
  └─ extends to tactic prediction + premise scoring
  └─ proves subexpression sharing is the key design choice
  └─ two-GNN architecture (goal GNN + premise GNN)
       │
       ▼
Holophrasm (Whalen 2016)
  └─ bandit search over proof trees
  └─ payoff/relevance/generative networks
  └─ template for your Phase 2 RL search
       │
       ▼
LeanDojo (Yang 2023)
  └─ your dataset
  └─ LM-based baseline to beat
  └─ evaluation protocol for Lean 4
       │
       ▼
Li et al. Survey (2024)
  └─ comprehensive map: where your work sits
  └─ state-of-the-art numbers across all benchmarks
       │
       ▼
YOUR PROJECT
  └─ GNN (from Paliwal architecture) +
  └─ RL search (from Holophrasm + MCTS) +
  └─ PLN symbolic validation (novel: Revision Rule)
```

---

## 6. Q1 Remaining Work

### Done ✓
- `lean_to_graph.py` — full DAG builder with hash-consing, PyG output, browser visualization
- Understanding of proof state structure, tokenization, hash-consing, shared nodes

### Still needed for Q1

**1. Build and cache the full dataset**
```python
# Don't rebuild DAGs every training run
from datasets import load_dataset
from lean_to_graph import proof_state_to_dag, build_vocab, dag_to_pyg
import torch

ds = load_dataset("cat-searcher/leandojo-benchmark-4-random", split="train")
all_dags = [proof_state_to_dag(row["state"]) for row in ds]
vocab = build_vocab(all_dags)

# Cache to disk
pyg_graphs = [dag_to_pyg(dag, vocab) for dag in all_dags]
torch.save(pyg_graphs, "cached_graphs.pt")
```

**2. Build tactic vocabulary**
```python
# Map tactic strings → integer labels
tactic_strings = [row["tactic"] for row in ds]
# Simplify: strip arguments, keep tactic name only
# e.g. "ext x" → "ext", "simp only [...]" → "simp"
tactic_vocab = {t: i for i, t in enumerate(sorted(set(tactic_strings)))}
```

**3. Train the baseline GNN**
```python
class ProofStateGNN(torch.nn.Module):
    def __init__(self, vocab_size, hidden=128, num_tactics=5000):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, hidden)
        self.conv1 = GCNConv(hidden, hidden)
        self.conv2 = GCNConv(hidden, hidden)
        self.conv3 = GCNConv(hidden, hidden)
        self.head  = nn.Linear(hidden, num_tactics)

    def forward(self, data):
        x = self.embed(data.x)
        x = self.conv1(x, data.edge_index).relu()
        x = self.conv2(x, data.edge_index).relu()
        x = self.conv3(x, data.edge_index).relu()
        x = global_mean_pool(x, data.batch)
        return self.head(x)
```

**4. AtomSpace Truth Bridge stub**
```python
def gnn_score_to_truth_value(state_str: str, proposed_tactic: str) -> dict:
    """
    Stub for the PLN Truth Bridge.
    Returns a dict compatible with AtomSpace TruthValue format.
    Replace internals with real GNN call once model is trained.
    """
    dag   = proof_state_to_dag(state_str)
    data  = dag_to_pyg(dag, vocab)
    vec   = gnn_model(data)
    score = float(torch.sigmoid(mlp_head(vec)))
    return {"strength": score, "confidence": 0.9}
```

**5. LeanDojo interaction test**
```python
from lean_dojo import LeanGitRepo, Dojo, TacticState
# Confirm you can: load a theorem → apply a tactic → get new state back
# This is required for Phase 2 RL environment
```

---

## 7. Numbers to Aim For

| Metric | Target for Q1 | Context |
|---|---|---|
| Top-1 tactic accuracy (val) | ~30–40% | Paliwal bag-of-words baseline: 33% |
| Sharing ratio on real data | >1.5 | Shows hash-consing is working |
| Graph build time per state | <50ms | Needed for RL interactive speed |
| GNN inference time | <10ms | Same |

**End-to-end proof rate is NOT a Q1 metric.** That requires proof search (Phase 2). Single-step tactic accuracy is the right target for Phase 1.

Current SOTA for context:
- ReProver (LM): ~52% end-to-end proof rate on LeanDojo
- DeepSeek-Prover: 57.7% pass@1
- Paliwal GNN (HOList, different benchmark): 49.95% proofs closed

Your GNN baseline will be below these numbers because it has no proof search — that's expected and fine.

---

## 8. Critical Design Decisions

### Edge directionality
Use **bidirectional edges** — both child→parent and parent→child. Paliwal showed top-down (parent→child) information flow is more important than bottom-up, but the best model uses both. In PyG, add reverse edges to `edge_index`.

### Number of message passing hops
Start with **5 hops**. Most proof state graphs have depth 10–30. Plan to increase to 8–12 as you scale up. More hops = significantly better performance in Paliwal's experiments.

### Pooling strategy
Try **global mean pooling** first (simplest, good baseline). Then try using the **State root node** embedding directly — it has already aggregated everything through message passing. For the PLN bridge, root node pooling may give a more structured embedding.

### Tactic vocabulary size
The full tactic vocabulary in Mathlib is in the thousands. For a baseline, **cluster by tactic name** (strip arguments). `simp only [X, Y, Z]` and `simp only [A, B]` both become `simp`. This reduces the classification problem dramatically. You can add argument prediction later.

### Don't block on PLN
From the quarter plan fallback: *"if the current architecture of Hyperon (PLN and MORK) is not feasible, the experiment will proceed with priority given to the GNN implementation and Lean kernel integration."* **This is the right call.** Get the GNN working and producing real TruthValue scores first. PLN integration is Phase 3. Build the interface now, fill it in later.

---

*Document covers work from Months 1–3, Q1. Dataset: `cat-searcher/leandojo-benchmark-4-random`. Papers: Paliwal et al. 2020, Whalen 2016, Li et al. 2024, Yang et al. 2023.*
