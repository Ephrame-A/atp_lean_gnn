Let me go deep on this — building everything from scratch, then connecting ideas, then speculating clearly.

---

# Estimating Conjecture Probability with PLN — Full Deep Dive

## 0. The Problem Being Solved — Why This Paper Exists

Every theorem prover you've studied has the same fundamental challenge: the search space is enormous. At each step, there are thousands of possible tactics, lemmas, or proof paths. How do you decide which one to try first?

The papers you've studied answer this with **learned value functions** — neural networks trained to predict which states are "closer to a proof." Holophrasm's payoff network, Aristotle's value function, Nazrin's NPA — all of these learn implicitly from data: "states that look like this tend to lead to successful proofs."

This paper asks a different question: **what if instead of implicitly learning to predict which paths are promising, you explicitly reason about the probability that a conjecture is provable?**

The distinction seems subtle but is actually deep. Let me build it up carefully.

---

## 1. The Background You Need — PLN

### What PLN Is

**Probabilistic Logic Networks (PLN)** is a reasoning system developed by Ben Goertzel (the same person behind Hyperon/MeTTa) that extends classical logic with probabilistic truth values. It's designed to handle the kind of uncertain, incomplete knowledge that real intelligence must deal with.

In classical logic, every statement is either True or False. In PLN, every statement has a **truth value** that is a pair `<strength, confidence>`:

- **Strength** (s ∈ [0,1]): how often or how strongly is this statement true? Think of it as a probability.
- **Confidence** (c ∈ [0,1]): how sure are we about that strength estimate? Low confidence means we've seen little evidence. High confidence means we've seen a lot.

So `<0.8, 0.9>` means "this is probably true (80% strength) and we're quite confident in that estimate (90% confidence)."

But underneath, PLN's truth value is actually a **second-order probability distribution** — a distribution over possible strength values. The strength and confidence are parameters of a Beta distribution. This is important: it means PLN can represent "I don't know" (a flat Beta distribution, low confidence) differently from "this is uncertain but I have evidence" (a peaked Beta distribution, higher confidence even if strength is 0.5).

### PLN's Inference Rules

PLN has inference rules that propagate truth values through logical reasoning:

**Deduction (if A→B and B→C, derive A→C):** The strength and confidence of the conclusion depend on the strengths and confidences of the premises. PLN has formulas for computing this.

**Induction:** Given many examples of "P(a₁) is true, P(a₂) is true, ..., P(aₙ) is true", PLN induces a probability for "∀x P(x)" with a confidence that grows with n.

**Abduction:** Given that A→C is true and C is true, abductively infer something about the probability of A being true. This is backward reasoning under uncertainty.

**Conjunction:** Given `<s₁,c₁>` for A and `<s₂,c₂>` for B, derive a truth value for A∧B.

The key point: PLN's reasoning is **structured uncertainty propagation**. When you combine multiple pieces of evidence, PLN computes the resulting uncertainty using principled probabilistic formulas, not just a neural network that produces a number.

### NAL — The Related System

The paper also mentions NAL (Non-Axiomatic Logic) by Pei Wang. NAL is similar in spirit — a logic designed for reasoning with limited resources and uncertain knowledge. The key idea in NAL is that intelligence must work with incomplete information under resource constraints. Both PLN and NAL are "uncertainty-aware logics" designed for systems that can't wait for complete information before acting.

---

## 2. The Curry-Howard Correspondence — Why Types Matter

The paper opens with: "From a type theoretic perspective, propositions are types, theories are collections of typing relationships, and proofs are terms inhabiting types."

This is the **Curry-Howard correspondence** — a deep mathematical equivalence between logic and type theory. Let me make it concrete.

In Lean4 (which you know), when you write:

```lean
theorem add_comm (a b : ℕ) : a + b = b + a := by
  ...
```

The type `a + b = b + a` IS the proposition. The proof term you construct IS the proof. The theorem is "inhabited" — there exists a term of that type.

This means the question "is proposition P provable?" is exactly the question "does the type P have any inhabitants (terms of that type)?"

The paper uses this to define the central object:

```
Θ : Theory × Proof × Proposition → Bool
```

Θ(Γ, p, C) = True means: in theory Γ (a collection of typing rules and axioms), the term p is a valid proof of proposition C (p is a member of type C).

This is just the type-checking relation — exactly what Lean's kernel does when it verifies a proof. The paper is formalizing this as a mathematical object that PLN can reason about.

---

## 3. Encoding Logic Rules as PLN Statements

Now the paper does something elegant. It takes standard inference rules and expresses them as PLN statements with truth values.

### Modus Ponens in PLN

```
Θ(Γ, f, a→b) ∧ Θ(Γ, x, a) ⇒ Θ(Γ, f(x), b)  ≞  <1, 1>
```

Breaking this down:

- `Θ(Γ, f, a→b)` — f is a proof of (a→b) in theory Γ
- `Θ(Γ, x, a)` — x is a proof of a in theory Γ  
- `Θ(Γ, f(x), b)` — f(x) is a proof of b in theory Γ (function application!)
- `⇒` — logical implication at the meta level
- `≞ <1, 1>` — this implication holds with strength 1 and confidence 1 (certainty)

The `≞` symbol (read as "measured by") connects a PLN statement to its truth value. This is PLN's way of attaching uncertainty to logical formulas. In this case, Modus Ponens is certain — if the premises hold, the conclusion holds with probability 1.

This is actually the Curry-Howard version of Modus Ponens: if f is a function from a to b, and x is an element of a, then f(x) is an element of b. Function application IS Modus Ponens.

### Why Encoding Rules This Way Matters

Once you have the inference rules as PLN statements, PLN can:

1. **Apply them forward** to derive what is provable from known facts
2. **Apply them backward** to find what premises would be needed to prove a goal
3. **Apply them inductively** to estimate probabilities from partial evidence

The key is that PLN doesn't just execute these rules — it propagates uncertainty through them. If you're only 70% confident that Θ(Γ, f, a→b), PLN knows the confidence of the conclusion Θ(Γ, f(x), b) should be lower than 70%.

---

## 4. The Central Query — Estimating Provability

The heart of the paper is this PLN query:

```
∃p Θ(Γ, p, C)  ≞  $tv
```

"In theory Γ, what is the probability that there exists some proof p of conjecture C?"

`$tv` is a "hole" — a variable PLN needs to fill in by reasoning.

### How PLN Fills This In

PLN can combine multiple sources of evidence:

**Evidence from specific examples:**
If you know that similar propositions (by some measure of similarity) were provable, induction gives you:
```
P(a₁), P(a₂), ..., P(aₙ) are all theorems
→ P(aₙ₊₁) has truth value <s, c>
where s ≈ n/(n+k) and c grows with n
```

**Evidence from structural analysis:**
If you know that C has the form "∀x Q(x)" and you know how many such propositions are provable in theory Γ in general, abduction gives you a prior.

**Evidence from partial proofs:**
If you've found a proof of some sub-goal of C, that updates the probability upward.

**Evidence from failed attempts:**
If multiple proof strategies for C have failed, that should lower the probability. PLN can incorporate this as negative evidence.

The strength of this: PLN aggregates all these heterogeneous evidence sources into one coherent truth value, with a confidence that reflects how much evidence has been gathered.

---

## 5. Using Provability Estimates for Search Guidance

Now we get to the practical application. Given conjecture C, you want to prove it. You can try different proof paths. The paper proposes evaluating each path's probability before committing to it.

### A-path vs B-path

```
A-path: prove A → C, then prove A, then apply modus ponens
B-path: prove B → C, then prove B, then apply modus ponens
```

You run PLN queries:
```
∃pA Θ(Γ, pA, A) ∧ ∃pAC Θ(Γ, pAC, A→C)  ≞  $tvA
∃pB Θ(Γ, pB, B) ∧ ∃pBC Θ(Γ, pBC, B→C)  ≞  $tvB
```

PLN evaluates both queries — possibly running some inference for a limited time — and fills in `$tvA` and `$tvB`. Whichever has higher truth value gets explored first.

This is essentially **Bayesian search**: you're maintaining a probability distribution over which proof paths are fruitful, updating it as you gather evidence, and always exploring the most promising path first.

### Going Deeper — Quantifying Over Premises

The paper goes one level further. Instead of choosing between specific A-path and B-path, you can ask:

```
∃a (∃pa Θ(Γ, pa, a) ∧ ∃paC Θ(Γ, paC, a→C))  ≞  $tva
```

"What is the probability that there EXISTS some intermediate lemma a that (a) is provable and (b) implies C?"

This is a much more ambitious query. PLN would need to instantiate `a` with actual candidates — searching the space of possible intermediate lemmas and scoring each one. Over time, the query progressively specializes: first the agent considers all possible `a`, then specific candidates, then the most promising ones.

---

## 6. What Makes This Different from Neural Value Functions

Now I want to be precise about the distinction between what this paper proposes and what the other papers you've studied do.

**Neural value functions (Holophrasm, Aristotle, Nazrin):**

```
Input: proof state S
Output: scalar v ∈ [0,1]
Training: supervised on (state, did_proof_succeed) pairs
```

The network learns correlations. It doesn't know *why* certain states are promising — just that states that look like this tend to lead to success. The "probability" it outputs is an approximation learned through gradient descent.

**PLN provability estimation (this paper):**

```
Input: conjecture C + all available evidence
Output: truth value <strength, confidence>
Computation: structured logical inference + statistical reasoning
```

PLN computes its estimate by actually reasoning — applying deduction, induction, abduction — over the known properties of Θ. The estimate is transparent: you can inspect which pieces of evidence contributed what, and why the conclusion has the confidence it does.

The key differences:

| | Neural Value Function | PLN Provability Estimate |
|---|---|---|
| How computed | Black-box gradient descent | Explicit inference rules |
| Evidence aggregation | Implicit in weights | Explicit truth value propagation |
| Interpretability | None | Full — inspect the inference chain |
| Handles new theories | Requires retraining | Can reason about novel axiom sets |
| Incorporates symbolic reasoning | No | Yes — uses actual logic rules |
| Uncertainty representation | Single scalar | Second-order distribution |

---

## 7. The Connection to Hyperon/MeTTa

*Now I'm going to connect this to what you've been studying — this is straightforward, not speculation.*

The paper's GitHub reference points to: `https://github.com/trueagi-io/chaining/tree/main/experimental/pln-inf-ctl`

That's the **trueagi** repository — OpenCog/Hyperon's codebase. PLN is a native component of Hyperon. MeTTa is the language that PLN runs inside. This isn't a coincidence — this paper is essentially proposing to use Hyperon's built-in probabilistic reasoning system as a theorem proving heuristic.

In the Hyperon 2025 whitepaper you've been studying, PLN plays a role in the PRIMUS cognitive architecture — it handles uncertain inference in the cognitive cycle. This paper is showing one specific concrete application of exactly that capability: using PLN's inductive and abductive reasoning to guide mathematical proof search.

The ternary predicate Θ expressed in MeTTa would look something like:

```metta
(= (Theta $theory $proof $proposition) 
   (if (type-check $theory $proof $proposition) True False))
```

And the PLN query for provability would be a backward chaining query asking MeTTa to find a term inhabiting the given type, with PLN estimating probabilities for each candidate.

---

## 8. My Own Analysis — What the Paper Gets Right

*This is my assessment, clearly marked.*

**The insight about uncertainty structure is correct.** A single scalar from a neural network genuinely loses information. The difference between "I'm 50% confident this is hard to prove" and "I've never seen anything like this so I have no idea" is real and important. PLN's `<strength, confidence>` pair captures this in a way a scalar doesn't. Low confidence should trigger exploration; low strength with high confidence should trigger abandonment. A neural value function conflates these.

**The recursive application is the right shape.** The paper's suggestion to break a conjecture into sub-lemmas and estimate each sub-lemma's provability, then recurse, matches how human mathematicians actually think. You don't search blindly — you ask "what would I need to prove to get this result?" and estimate which intermediate step is tractable.

**The connection to MCTS is clean.** In standard MCTS (which Holophrasm and Aristotle use), the value function scores leaf nodes. PLN could slot directly into this role — instead of a neural network scoring a proof state, you run PLN inference for some time budget and use the resulting truth value as the score. The architecture is the same, the scoring mechanism is different.

---

## 9. Where I Think the Paper Falls Short

*This is my critique, clearly marked.*

**The computation problem is not addressed.** The paper proposes running PLN queries to evaluate proof paths before choosing them. But PLN inference is itself a search problem — filling in `$tv` for `∃p Θ(Γ, p, C) ≞ $tv` requires PLN to reason over a potentially infinite space of proofs and propositions. This might be just as expensive as the original proof search.

The paper doesn't give any indication of how fast PLN can produce useful truth value estimates, or what the trade-off is between inference time and estimate quality. In Aristotle and Holophrasm, a neural network scores a state in milliseconds. If PLN takes seconds, the overhead might dominate.

**Induction over what corpus?** The paper says PLN can use inductive reasoning from "a corpus of examples of Θ" — meaning examples of (theory, proof, proposition) triples where Θ holds. But where does this corpus come from? For novel mathematical theories, you'd have very few examples. The confidence would be low, making the truth values uninformative early in the search when you need guidance most.

**The formalization is incomplete.** Modus Ponens is given as a PLN statement, but the full set of type-theoretic rules needed to reason about Lean's Calculus of Inductive Constructions is enormous. Universe polymorphism, inductive types, dependent types — all of these would need PLN formulations. The paper gives one example and gestures at the rest.

---

## 10. My Speculation — Where This Could Go

*This is speculative — clearly marked as such.*

**Speculation 1: Hybrid Architecture**

The most promising direction, in my view, is not replacing neural value functions with PLN, but combining them. Neural networks are fast and good at pattern matching over seen data. PLN is slow but good at structured reasoning about novel situations. A hybrid system could:

- Use a neural value function for fast first-pass scoring of common proof patterns (seen in training)
- Use PLN for slow but structured reasoning when the neural network's confidence is low (novel territory)

This matches how the Hyperon PRIMUS architecture is designed — neural systems handle perception and fast pattern matching; PLN handles slower deliberate reasoning. Applying the same dual-process architecture to proof search guidance feels natural and could be powerful.

**Speculation 2: PLN as the Meta-Verifier**

Recall from DeepSeekMath-V2 the meta-verifier — the system that checks whether the verifier's critiques are faithful. What if PLN played that role? Instead of a learned neural meta-verifier, you use PLN's logical structure to check whether a critique actually identifies a real logical gap in a proof. PLN could apply type-theoretic reasoning to evaluate whether "step 3 makes an unsupported claim about X" is actually true — using Θ to verify whether the claim at step 3 follows from the available hypotheses.

This would give the meta-verification process the same interpretability advantage that PLN has over neural networks.

**Speculation 3: Provability Estimation as Lemma Discovery**

The paper's most ambitious query is `∃a (∃pa Θ(Γ, pa, a) ∧ ∃paC Θ(Γ, paC, a→C))` — find an intermediate lemma that is both provable and implies C. If PLN could efficiently search this space, it would be doing **lemma discovery** — automatically generating the key intermediate results needed for a proof. This is exactly what Aristotle does informally (the lemma generation pipeline) but with natural language and neural networks. PLN could do it formally, with explicit uncertainty estimates for each candidate lemma. The challenge is computational — searching the space of all possible intermediate propositions is vast. But with good abductive reasoning seeded by the structure of C, PLN might narrow it down effectively.

**Speculation 4: Integration with Hyperon for ATP**

Given that this work is from SingularityNET and uses MeTTa/PLN, the most natural trajectory is integration into Hyperon as an ATP module. Hyperon's metagraph could store Θ facts as edges, PLN could reason over them, and MeTTa's pattern matching could efficiently retrieve relevant facts. The `∃p Θ(Γ, p, C)` query would be a native MeTTa backward chaining query. This would make Hyperon's own reasoning system (PLN) guide its own formal verification system — a genuinely self-referential and elegant architecture. Whether PLN is currently fast enough and expressive enough for this to work in practice is an open question.

---

## 11. Where This Sits in the Full ATP Progression

```
Resolution Method (1986)
  Search guidance: none — brute force over all resolutions

Holophrasm (2016)
  Search guidance: neural payoff network predicts provability
  Limitation: black box, no uncertainty structure

GNN paper (2019)
  Search guidance: GNN scores goal states for premise selection
  Limitation: black box, no uncertainty structure

LeanDojo/ReProver (2023)
  Search guidance: DPR retriever ranks premises by similarity
  Limitation: no explicit probability, no reasoning about provability

Nazrin (2026)
  Search guidance: NPA generates tactics from finite action space
  Limitation: no explicit probability, no reasoning about provability

THIS PAPER (Geisweiller, SingularityNET)
  Search guidance: PLN reasons explicitly about P(conjecture is theorem)
  Advantage: structured uncertainty, interpretable, can handle novel theories
  Limitation: computational cost unaddressed, formalization incomplete
```

The paper sits outside the mainstream ML-for-ATP line — it's proposing a fundamentally different kind of guidance mechanism. Not "learn from data what looks promising" but "reason about what is likely to be true." It's asking a harder question more carefully, at the cost of computational tractability. Whether that trade-off is worth it is genuinely open.

---

## Summary

This paper's contribution is a **conceptual framework** rather than a working system. It says: the right way to guide proof search is to maintain an explicit probabilistic model of which conjectures are provable, update it with all available evidence using structured logical inference (PLN), and use it to prioritize which proof paths to explore. The framework is principled, interpretable, and connects naturally to Hyperon/MeTTa's architecture. The gap between the framework and a practical implementation is substantial — computational efficiency, corpus construction, and full formalization are all unresolved. But the conceptual direction is interesting and underexplored, especially in the context of Hyperon where PLN is a native component that could plausibly be integrated with formal proof search.