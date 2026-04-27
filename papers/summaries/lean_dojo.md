# LeanDojo & ReProver: A Deep Review
### *Theorem Proving with Retrieval-Augmented Language Models (NeurIPS 2023)*
**Yang et al. — Caltech, NVIDIA, MIT, UC Santa Barbara, UT Austin**

---

## 0. Historical Context and What Kind of Paper This Is

```
1986 — Resolution Method — pure logic, no learning
2016 — Holophrasm — GRUs + UCT search, Metamath
2019 — GNN paper — graph representations, HOL Light
2023 — THIS PAPER — LeanDojo + ReProver, Lean
2025 — Aristotle, DeepSeekMath-V2 — IMO gold
```

This paper is architecturally different from every other paper in this series. Every other paper focused on **how to prove theorems** — search algorithms, neural network architectures, verification mechanisms. This paper's primary contribution is **infrastructure**: how do you get the data, tooling, and benchmarks needed to train and evaluate a theorem prover in the first place?

The secondary contribution is ReProver — a prover built on that infrastructure that introduces **retrieval-augmented generation** as the core mechanism for premise selection.

Two problems this paper is solving simultaneously:
1. The entire field has no open, reproducible infrastructure — all existing LLM-based provers use private code, private data, and require thousands of GPU days to reproduce
2. A key bottleneck in theorem proving — knowing which premise to use — hasn't been addressed directly by any existing LLM prover

---

## 1. What a Premise Is and Why It's Hard

### The Core Concept

When proving a theorem in Lean, at some point your proof needs to **use an existing result** — something proved earlier, either by you or by someone else in the math library. That existing result is a **premise**.

The paper's running example proves `gcd_self`: for all natural numbers n, `gcd n n = n`. The proof uses two premises:

```lean
mod_self      — ∀n, n % n = 0
gcd_zero_left — ∀x, gcd 0 x = x
```

The tactic `rewrite mod_self` says: use this already-proven fact to simplify my current goal. Without knowing that `mod_self` exists and is useful here, you cannot write this proof step.

A premise is therefore: **any previously defined theorem, lemma, or definition invoked during a proof**.

### Why Premise Selection is Hard

The scale: Lean's math library (Mathlib) contains roughly **130,000 premises** — theorems, lemmas, definitions, all potentially usable at any step.

When you're at an intermediate proof state like:
```
k : ℕ
⊢ gcd ((k + 1) % (k + 1)) (k + 1) = k + 1
```

You need to determine: out of 130,000 available premises, which one is useful right now?

Three things make this hard:

**Scale:** 130,000 premises is far too many to fit in a transformer's context window. You must narrow it down before the model can use them.

**Novelty:** A model trained before certain premises were added to Mathlib has never seen those names. It cannot memorize what it hasn't seen. This is the fundamental failure mode of memorization-based approaches.

**Locality:** The right premise depends on the exact current sub-goal, which changes after every tactic. The need is dynamic — at one step you need `mod_self`, three steps later you need `gcd_zero_left`.

### Two Paradigms: Memorization vs Retrieval

**Memorization (old approach):** Train on enough (proof state, tactic) pairs that the model implicitly learns which premises to invoke. Works when the premise appears in training data. Fails completely on novel premises — from new domains or newly added to the library.

**Retrieval (this paper):** Given the current proof state, search the entire math library for semantically matching premises, retrieve the most relevant ones, and give them to the model explicitly.

```
Current proof state
        ↓
   [Retriever]  ← searches 130,000 premises
        ↓
Top-k most relevant premises
        ↓
[Tactic Generator]  ← uses state + retrieved premises
        ↓
Next tactic (e.g., "rewrite mod_self")
```

This is **Retrieval-Augmented Generation (RAG)** — augmenting a model at inference time with explicitly retrieved information rather than relying purely on memorized training associations. A doctor who can look up a reference is better than one who must remember everything.

---

## 2. LeanDojo — The Infrastructure

LeanDojo serves two essential functions: **data extraction** and **programmatic interaction** with Lean.

### 2.1 Why Raw Lean Code Is Insufficient for Training

Lean repos contain human-written source code. But raw code is unsuitable for training a prover. It lacks runtime information that humans access when using Lean interactively — most critically, the **intermediate proof states between proof steps**.

When a human writes a proof, they see the proof state change after each tactic. The raw `.lean` file only shows the final sequence of tactics, not what the state looked like before each one. A machine learning model needs to learn from (state, tactic) pairs — which are only visible at runtime.

### 2.2 What LeanDojo Extracts

LeanDojo processes Lean repos and extracts three categories of information not visible in the raw code:

**File dependencies and ASTs:** LeanDojo produces a directed acyclic graph where nodes are files and edges are import relations. It also produces the abstract syntax tree of each file. This enables program analysis — determining which theorems are defined in a file and which premises are accessible to each theorem.

**States and tactics:** For each tactic in every proof, LeanDojo extracts the proof state before and after the tactic. This allows reconstruction of the full proof tree — the sequence of (state, tactic, new state) triples that constitute the proof.

**Premises:** For each premise used in a proof, LeanDojo records where it is defined (file and location) and where it is used (across all files). This required modifying Lean's internal elaboration process — a non-trivial engineering contribution.

The premise extraction is the paper's most technically novel piece of infrastructure. Lean performs **name resolution** during elaboration: the short name `mod_self` in a tactic is resolved to the fully-qualified name `nat.mod_self`. This resolution happens internally and isn't exported by default. LeanDojo intercepts Lean's elaborator to capture input/output of name resolution, recording both where premises are used and their full qualified names.

### 2.3 Reliable Interaction with Lean

LeanDojo also turns Lean into a **gym-like environment** for inference and RL. The interface has two operations:

- `initialize(theorem)` — given a theorem to prove, return the initial proof state
- `run_tac(state, tactic)` — apply a tactic to a state, return the new state or an error

The previous tool for this (lean-gym) had a critical flaw: **21.1% of correct proofs were misjudged as incorrect**. The root cause was a namespace handling bug. When lean-gym constructed the proof environment, it would `open` a namespace rather than be `inside` it — a subtle distinction that changes how name resolution works, causing valid tactics to fail unexpectedly.

LeanDojo fixes this by wrapping its interaction code as a Lean tactic inserted directly into the correct location in the proof, guaranteeing the environment matches the original human-written proof. This reduces misjudgments from 21.1% to 1.4% — a critical improvement for both evaluation accuracy and RL training signal quality.

### 2.4 LeanDojo Benchmark

Using LeanDojo, the paper constructs a benchmark containing:
- **98,734 theorems and proofs** extracted from Mathlib
- **217,776 tactics**
- **129,243 premises** (with definitions)

The benchmark has two data splits:

**Random split:** Theorems randomly assigned to train/validation/test. This is the standard approach but leads to overestimated performance — similar theorems cluster in Lean code, so the model can prove test theorems by memorizing proofs of nearly-identical training theorems.

**Novel premises split:** Test proofs must use at least one premise never used in training. This directly tests whether the prover can generalize to truly new scenarios. A block of similar theorems sharing the same premise (like `conj_mul`) must all be in training if any one is.

The novel premises split is the paper's most important methodological contribution to benchmarking. It reveals that the field has been systematically overestimating prover performance.

---

## 3. ReProver — The Retrieval-Augmented Prover

ReProver has two components trained sequentially: a **retriever** and a **tactic generator**.

### 3.1 Dense Premise Retrieval

The retriever is based on Dense Passage Retriever (DPR). Given a proof state `s` as the query and the library of candidate premises `{p_i}`, it embeds both into a shared vector space and retrieves premises by maximum cosine similarity.

Formally, a function `f` parameterized by θ embeds both states and premises into a h-dimensional space:

```
f(s, θ), f(p_i, θ) ∈ R^h
```

The retriever is a Transformer encoder followed by average pooling. Premise embeddings can be **pre-computed and cached** since they don't change during a proving session. At inference time, only one forward pass is needed to embed the current state, then fast dot products with cached premise embeddings give the ranking.

The retriever is trained with a contrastive loss: maximize similarity between a state and its ground-truth premise, minimize similarity with negative premises.

### 3.2 Two Key Innovations Over Standard DPR

**Accessible premises only:** Not all premises in Mathlib are accessible when proving a given theorem. Premises defined after the current theorem in the file, or in files not imported, cannot be used. LeanDojo's program analysis capability computes accessible premises for each theorem. This reduces the average retrieval corpus from 128,000 premises to **33,000** — dramatically simplifying the retriever's task without losing valid candidates.

**In-file negative examples:** DPR's performance depends critically on the quality of negative training examples. Random negatives are too easy — the model learns to distinguish anything from the ground truth. The paper discovers that the model tends to confuse premises defined in the same file as the ground truth premise. The fix: sample `k` "in-file negatives" (premises from the same file as the correct one) alongside random negatives. These are **hard negatives** — semantically similar but wrong — that force the retriever to develop fine-grained discrimination.

### 3.3 Tactic Generation

Retrieved premises are concatenated with the current proof state and fed to an encoder-decoder Transformer (ByT5-small, 299M parameters). The model generates the next tactic, trained to minimize cross-entropy loss against human-written tactics.

ByT5 operates directly on UTF-8 bytes without tokenization. This is important because Lean code uses extensive Unicode math symbols that standard tokenizers handle poorly.

The full ReProver pipeline at inference:

```
1. Given proof state s
2. Retriever ranks all accessible premises by cosine similarity to s
3. Top-100 retrieved premises concatenated with s (truncated to 2,300 tokens)
4. ByT5 generates 64 tactic candidates via beam search
5. Best-first search assembles tactics into complete proofs
6. Lean verifies each completed proof
```

### 3.4 Training Details

Training takes **5 days on a single A100 GPU** — contrasted with thousands of GPU days required by prior closed-source methods. This is the paper's accessibility claim in concrete form.

The model uses no domain-specific pretraining (unlike competitors that pretrained on private math/code datasets), no auxiliary tasks, and no reinforcement learning or online interaction with Lean. These are deliberate simplicity choices to establish an accessible baseline, not limitations of the approach.

---

## 4. Results

### 4.1 Premise Selection

| Method | R@1 (random) | R@10 (random) | R@1 (novel) | R@10 (novel) |
|---|---|---|---|---|
| BM25 (no ML) | 6.7% | 17.2% | 5.9% | 15.5% |
| ReProver (all premises) | 11.7% | 36.2% | 7.1% | 23.1% |
| ReProver (w/o in-file neg) | 10.8% | 33.1% | 7.9% | 25.7% |
| **ReProver (full)** | **13.5%** | **38.4%** | **9.1%** | **27.6%** |

Both innovations (accessible premises and in-file negatives) contribute independently. The drop from random to novel_premises is significant for all methods — confirming that novel premise generalization is genuinely harder.

### 4.2 Theorem Proving (Pass@1)

| Method | Random split | Novel premises split |
|---|---|---|
| tidy (heuristic, no ML) | 23.8% | 5.3% |
| GPT-4 (zero-shot) | 29.0% | 7.4% |
| ReProver (w/o retrieval) | 47.6% | 23.2% |
| **ReProver (full)** | **51.2%** | **26.3%** |

Three observations worth sitting with:

**Retrieval helps:** 51.2% vs 47.6% — a 3.6 percentage point improvement from retrieval. Larger on novel_premises: 26.3% vs 23.2% — a 3.1 point improvement where generalization matters most.

**GPT-4 is surprisingly weak:** 29.0% on random, 7.4% on novel_premises. Despite potential data contamination (many proofs were on GitHub before GPT-4's cutoff), a 299M parameter finetuned model beats GPT-4 dramatically. Theorem proving is not solvable out-of-the-box by large general models.

**Novel premises is genuinely harder for everyone:** All methods degrade substantially. This validates the benchmark design — the novel_premises split is measuring something real and difficult.

### 4.3 MiniF2F and ProofNet

ReProver achieves Pass@1 of **26.5% on MiniF2F** (competitive with prior non-RL state-of-the-art at 25.9%) and **13.8% on ProofNet** (first reported result on this dataset).

Crucially, ReProver discovers **65 new proofs** across MiniF2F and ProofNet that had no existing Lean proofs — demonstrating practical utility beyond benchmark performance.

---

## 5. The Novel Premises Data Split — A Methodological Contribution

This deserves its own section because it identifies a systematic problem in how the field has been measuring progress.

In Lean code, a common idiom is blocks of similar theorems for slightly different properties of the same concept. Consider three conjugation lemmas in `src/algebra/quaternion.lean`:

```lean
lemma conj_mul : (a * b).conj = b.conj * a.conj
lemma conj_conj_mul : (a.conj * b).conj = b.conj * a
lemma conj_mul_conj : (a * b.conj).conj = b * a.conj
```

The last two have **identical proofs** using the same premises. If `conj_conj_mul` is in training, a model can prove `conj_mul_conj` purely by memorization — without any genuine mathematical understanding.

Random splits allow this. The novel_premises split prevents it: if two theorems share a premise, they must both be in training or both in test. The result is a benchmark that tests whether the model can reason about mathematics it hasn't seen, not just recall proofs it has.

The performance gap between random and novel_premises splits across all methods confirms that prior benchmarks were measuring memorization as much as reasoning.

---

## 6. The ChatGPT Experiment — An Illuminating Failure

The paper includes a qualitative study of ChatGPT (GPT-3.5 and GPT-4) interacting with Lean via LeanDojo as a plugin. This reveals something important about the state of general LLMs for theorem proving.

**What ChatGPT did well:**
- Interpreted Lean error messages accurately in natural language
- Interleaved informal mathematical reasoning with formal proof steps
- Adapted its strategy based on feedback

**Where it failed:**
- Went in circles — applied rewrites that undid previous rewrites, returning to the original goal
- Then falsely claimed the theorem was proved (Figure L), even though LeanDojo's response clearly showed `proof_finished: False`
- Could not search systematically — stuck on unpromising paths when backtracking was needed

The loop failure is particularly instructive. ChatGPT rewrote `a + b + c = a + c + b` to `b + a + c = a + c + b` to `b + a + c = c + a + b` to `a + b + c = c + a + b` and back to the start — four rewrites, no progress. And it didn't notice.

This directly demonstrates what the paper argues: theorem proving needs **systematic search with backtracking**, not just a model that generates plausible-looking text. The Lean compiler provides an objective signal (`proof_finished: True/False`) that general LLMs ignore at their peril.

---

## 7. Limitations and What They Point Toward

**Data scarcity relative to model hunger:** 98,734 proofs covers most of Lean's available data as of 2023. This is small by LLM standards. Performance cannot keep improving simply by scaling model size.

**Human proofs only show successful trajectories:** The proof file records the final working tactic sequence, not the intermediate exploration of failed attempts. The model learns from success without seeing why certain paths were dead ends. This makes individual tactics opaque — a tactic that appears in the proof because of a long chain of reasoning appears with no explanation of that reasoning.

**Context window bottleneck:** With 2,300 tokens of input, only 10-15 retrieved premises fit. More sophisticated architectures that fuse retrieved premises in hidden space (rather than concatenating in the input) could scale retrieval to larger candidate sets.

**No RL or online interaction:** ReProver is trained only on human-written proofs. Existing systems improve further by training on proofs the model itself discovers through online interaction with Lean. This is acknowledged but deliberately excluded as a simplicity choice.

---

## 8. Where This Sits in the Broader Progression

```
Holophrasm (2016)
  Problem: No principled way to select which theorem to apply
  Solution: Relevance network ranks theorems
  Limitation: Separate networks, no structured retrieval

GNN paper (2019)
  Problem: How to represent formulas for neural networks
  Solution: Graph representations with message passing
  Limitation: HOL Light only, no open infrastructure

LeanDojo + ReProver (2023)
  Problem 1: No open infrastructure for Lean-based learning
  Solution: Open toolkit, benchmark, interaction environment
  Problem 2: Premise selection via memorization doesn't generalize
  Solution: Explicit retrieval from accessible premises
  Limitation: Small model, no RL, context window bottleneck

Aristotle (2025)
  Builds on: Lean infrastructure (like LeanDojo provides)
  Adds: MCGS search, lemma decomposition, test-time training
  Result: IMO gold
```

LeanDojo's infrastructure contribution directly enables the work that follows. Aristotle's system requires exactly what LeanDojo provides: reliable interaction with Lean, data extraction including proof states, and accessible premise information. The open infrastructure this paper provides is part of what makes the 2025 results possible.

The retrieval insight also persists: the ability to explicitly look up relevant lemmas rather than memorize them is a key part of how systems like Aristotle handle Mathlib's scale.

---

## 9. Summary

LeanDojo makes three durable contributions:

**Infrastructure:** An open, reproducible toolkit for data extraction and Lean interaction that reduces proof-checking errors from 21.1% to 1.4%, supports Lean 4, and works on any Lean repo — not just Mathlib.

**Benchmark design:** The novel_premises split identifies and corrects a systematic overestimation of prover performance in the field. The distinction between memorization and generalization is now a standard concern in ATP benchmarking.

**Retrieval-augmented proving:** The demonstration that explicit premise retrieval improves theorem proving — especially on novel premises — introduces a paradigm that scales better than memorization as math libraries grow. The two innovations (accessible premises and in-file hard negatives) are both principled and practically effective.

The model itself (ReProver) is deliberately modest — small, cheap to train, no private data, no RL. This is a feature, not a limitation. It establishes an accessible baseline that the field can reproduce and build on, which is the paper's stated goal.