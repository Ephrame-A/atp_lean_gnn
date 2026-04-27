# 🧠 Deep Dive — DeepSeekMath-V2

---

## PART 1 — The Problem Being Solved

### Why did this paper need to exist?

The standard way to train LLMs to do math with RL is called **outcome reward**: you give the model a problem, it produces an answer, and if the final answer matches the ground truth, you reward it. That's it. This is how DeepSeek-R1 and similar models are trained.

This methodology is enough to let frontier LLMs fully saturate competitions like AIME and HMMT — competitions that primarily care about final numerical answers.

But there are **two deep problems** with this approach:

**Problem 1 — Correct answer ≠ correct reasoning**
A model can arrive at a correct answer through flawed logic or lucky errors. Final answer rewards are an unreliable proxy for reasoning quality.

Think about it: if a student's answer is "42" and the correct answer is "42", outcome reward gives them full marks — even if their entire proof was nonsense that happened to produce the right number.

**Problem 2 — Many math tasks have no "final answer" to check**
Theorem proving tasks may not produce a numerical final answer at all — rigorous step-by-step derivation IS the objective. So the reward mechanism simply doesn't apply.

There's a third consequence that flows from these two: models trained this way exhibit high false-positive rates, often claiming incorrect proofs are valid even when they contain obvious logical flaws. They never learned to spot errors because they were never trained to.

---

## PART 2 — The Core Insight: The Generation-Verification Gap

The paper makes an observation borrowed from how human mathematicians actually work:

> *"Humans can identify issues in proofs even without reference solutions."*

This is profound. If you give a human mathematician a flawed proof, they can point to the exact broken step — **without needing the correct solution**. That's what the paper wants to replicate.

From this comes three cascading observations that structure the whole paper:

1. A proof is **more credible** when even heavy scrutiny fails to find issues with it.
2. The **effort required** to find issues is itself a signal of proof quality.
3. If a model can evaluate proofs like this, it can use that same skill to **improve its own proofs** — check itself, find the flaw, fix it, repeat.

This is the **generation-verification gap**: the verifier needs to be slightly "smarter" or more critical than the generator, so it can catch what the generator can't see in its own work.

---

## PART 3 — Section 2.1.1: Training the Verifier

### What should the verifier do?

Given a problem X and a proof Y, the verifier is designed to produce a proof analysis that first summarizes any identified issues, then assigns a score on three levels: **1** for complete and rigorous proofs; **0.5** for proofs with sound overall logic but minor errors or omitted details; and **0** for fundamentally flawed proofs with fatal logical errors or critical gaps.

So the verifier's output is two things: a **natural language critique** + a **score from {0, 0.5, 1}**.

### Step 1: Cold Start Data — Where does training data come from?

You can't train a verifier from scratch with pure RL — you need some initial labeled data to bootstrap from. Here's exactly what they did:

They crawled 17,503 problems from Art of Problem Solving (AoPS), prioritizing math olympiads, team selection tests, and post-2010 problems explicitly requiring proofs. Call this dataset **𝒟ₚ**.

Then they generated candidate proofs using an early variant of DeepSeek-V3.2-Exp-Thinking. But there was a catch — this model was not optimized for theorem proving and tended to produce concise but error-prone outputs, so they prompted it to iteratively refine its proofs over multiple rounds.

Finally, human math experts manually scored a sample of these proofs using the rubrics, producing the dataset **𝒟ᵥ = {(Xᵢ, Yᵢ, sᵢ)}** — problem, proof, expert score.

### Step 2: The RL Training Objective

Starting from DeepSeek-V3.2-Exp-SFT, they trained the verifier with RL using two reward components:

- **Format reward (R_format)**: an indicator that enforces the model to output a structured response containing "Here is my evaluation of the solution:" and a score inside `\boxed{}`.
- **Score reward (R_score)**: rewards based on how close the predicted score is to the expert-annotated score, computed as `1 - |predicted - annotated|`.

The full RL objective multiplies the two:

```
max over πφ:
  E[ R_format(V') · R_score(s', s) ]
```

This means: **you only get score reward if you also formatted correctly**. Format is a gating condition. If the model outputs a valid structure AND gets the score right, it gets rewarded proportionally.

The RL algorithm used throughout the paper is **GRPO (Group Relative Policy Optimization)** — the same algorithm from DeepSeek-R1.

---

## PART 4 — Section 2.1.2: The Critical Vulnerability + Meta-Verification

### The loophole

Here's the subtle problem that emerges. The reward only cares about:
1. Did you format correctly?
2. Did you predict the right score?

It does **not** care about whether the issues you identified actually exist.

So what can a model do? When evaluating a flawed proof, the verifier can receive full reward by predicting the correct score while hallucinating non-existent issues — fabricating fake criticisms that justify the score without being real.

This is the key faithfulness problem. The model can be **accurate** (gets scores right) while being **completely unfaithful** (the reasoning is made-up). And faithfulness is what you actually need when using the verifier to guide proof improvement.

### The fix: Meta-Verification

They introduce meta-verification: a secondary evaluation process that checks whether the issues identified by the verifier actually exist, and whether those issues logically justify the predicted proof score.

The meta-verifier **πη** takes as input: the original problem X, the proof Y, and the verifier's analysis V. It outputs: a critique of the analysis itself + a **meta quality score**.

### How the Meta-Verifier is trained (step by step):

1. Train an initial verifier πφ using the basic RL objective from Section 2.1.1.
2. Have human experts score the *quality of that verifier's analyses* — not whether the scores were right, but whether the identified issues were real and well-justified. This creates dataset **𝒟ₘᵥ = {(Xᵢ, Yᵢ, Vᵢ, msᵢ)}**.
3. Train the meta-verifier πη on 𝒟ₘᵥ with the same GRPO structure (format + score rewards, but now the "score" is the meta quality score).

### Incorporating meta-verification back into verifier training

The enhanced reward for training the verifier becomes:

```
R_V = R_format · R_score · R_meta
```

R_meta is the quality score from the meta-verifier. The enhanced verifier is then trained on both 𝒟ᵥ and 𝒟ₘᵥ, and the resulting model can perform both proof verification AND meta-verification.

### What's the payoff?

The average quality score of the verifier's analyses (as evaluated by the meta-verifier) improved from **0.85 to 0.96**, while maintaining the same accuracy in proof score prediction.

---

## Full Picture So Far — Visualized

```
 ┌─────────────────────────────────────────────────────────┐
 │                   COLD START DATA                        │
 │  17,503 AoPS problems → generate proofs → expert scores  │
 │  Dataset: 𝒟ᵥ = {problem, proof, score}                  │
 └────────────────────────┬────────────────────────────────┘
                          │
                          ▼
 ┌─────────────────────────────────────────────────────────┐
 │              VERIFIER v1 (Basic RL)                      │
 │  Reward: R_format × R_score                              │
 │  Problem: can hallucinate fake issues and still score    │
 └────────────────────────┬────────────────────────────────┘
                          │ Verifier outputs analyzed
                          ▼
 ┌─────────────────────────────────────────────────────────┐
 │         Human experts score quality of analyses          │
 │         Dataset: 𝒟ₘᵥ = {problem, proof, analysis, mscore}│
 └────────────────────────┬────────────────────────────────┘
                          │
                          ▼
 ┌─────────────────────────────────────────────────────────┐
 │              META-VERIFIER (RL trained)                  │
 │  Takes: (Problem, Proof, Verifier's analysis)            │
 │  Outputs: critique of the analysis + meta quality score  │
 └────────────────────────┬────────────────────────────────┘
                          │ R_meta fed back into training
                          ▼
 ┌─────────────────────────────────────────────────────────┐
 │         FINAL VERIFIER (Enhanced RL)                     │
 │  Reward: R_format × R_score × R_meta                     │
 │  Can now do BOTH verification AND meta-verification      │
 │  Quality score: 0.85 → 0.96                              │
 └─────────────────────────────────────────────────────────┘
```

---

This is the full foundation. The verifier is now both **accurate** (predicts correct scores) and **faithful** (its reasoning actually identifies real issues).


# 🔧 PART 2 — Section 2.2: Proof Generation

Now that you understand the verifier, here's the key question: **what do you do with it?**

The answer has two stages — first train a generator using the verifier as a reward signal, then teach the generator to *be its own verifier* at inference time.

---

## Section 2.2.1 — Training the Generator

### The setup

With the verifier πφ in hand, the proof generator πθ(·|X) is trained with a straightforward RL objective: maximize the expected proof score that the verifier assigns to generated proofs, over the full set of 17,503 AoPS problems 𝒟ₚ.

Formally:
```
max over πθ:
  E[ R_Y ]  where R_Y = verifier score for proof Y on problem X
```

This is conceptually clean: **the verifier IS the reward model**. The generator gets rewarded not for matching a known answer (which often doesn't exist in theorem proving), but for writing proofs that the verifier can't fault.

### Why this is powerful

Think about what this unlocks. Previously, the only way to reward a model was if you had a ground-truth answer to compare against. That works for AIME ("the answer is 42"), but falls apart for IMO proof problems where the whole solution *is* the reasoning.

Now the reward signal generalizes: any problem that the verifier can evaluate becomes a valid training signal. The 17,503 AoPS problems all become usable training data — including open-ended proof problems that never had a numerical answer.

---

## Section 2.2.2 — Self-Verification: Teaching the Generator to Be Its Own Critic

This is the most philosophically interesting part of the paper. And it builds on one key idea from the introduction:

> *"We make the model explicitly aware of its reward function and enable it to maximize this reward through deliberate reasoning rather than blind trial-and-error."*

### The problem with one-shot generation

For challenging competition problems, a generator frequently fails to produce a completely correct proof in a single attempt.

So what do you do when the first proof is imperfect? Blind trial-and-error (just sampling many proofs and picking the best-scored one) is expensive and doesn't use the structure of *why* a proof failed.

### The insight: make the generator internalize verification

Rather than having the verifier exist as a separate external system, the paper teaches the generator to **apply verification logic to its own outputs during generation**. The model learns to:

1. Write a draft proof
2. Internally critique it — identifying issues just like the verifier would
3. Revise specifically to fix those issues
4. Repeat until no more issues are identifiable

The paper incentivizes the generator to identify and resolve as many issues as possible in its own proofs before finalizing them.

This is trained using an RL objective where the reward for the **entire generate-verify-refine trajectory** is the score on the final proof. So the model learns that spending tokens on internal self-critique is worth it if it leads to a cleaner final proof.

### Why "deliberate reasoning" rather than "blind trial-and-error"

Here's the contrast the paper is making very deliberately:

| Approach | What the model knows | Strategy |
|---|---|---|
| Outcome RL (old way) | Just: "this answer was right/wrong" | Random sampling, hope for the best |
| Self-verifiable RL (this paper) | The full rubric — *why* something is wrong | Targeted, deliberate self-improvement |

The model isn't just trying random proofs until one scores well. It's reading its own work through the verifier's eyes, finding the exact line where the logic broke, and fixing it. That's the difference between a student who keeps retaking a test hoping to get lucky vs. one who studies their mistakes.

---

## Section 2.3 — The Synergy: Keeping the Verifier Ahead of the Generator

Here's a problem that emerges once this system is running: **as the generator gets better, the verifier's training data becomes stale**.

The verifier was trained on proofs from an early, weaker version of the generator. Once the generator improves, it starts producing proofs that are harder to evaluate — the kinds of near-correct, subtly-flawed proofs that weren't well-represented in 𝒟ᵥ. The generation-verification gap starts to close, and the verifier starts making mistakes on the hard new proofs.

The solution the paper proposes is to **scale verification compute** to automatically create new verifier training data:

To maintain the generation-verification gap as the generator becomes stronger, they scale verification compute to auto-label hard-to-verify new proofs — using many verifier samples to aggregate a robust score — creating new training data to further improve the verifier, which then enables another round of generator improvement.

The full cycle looks like this:

```
┌─────────────────────────────────────────────────────────────┐
│                   THE FULL ITERATIVE CYCLE                   │
│                                                             │
│  ① Train Verifier (rubrics + RL + meta-verification)        │
│           │                                                  │
│           ▼                                                  │
│  ② Use Verifier as reward to train Generator                 │
│           │                                                  │
│           ▼                                                  │
│  ③ Generator gets stronger → produces harder proofs          │
│           │                                                  │
│           ▼                                                  │
│  ④ Scale verification compute on new hard proofs             │
│     (many verifier samples → aggregate score → label)        │
│           │                                                  │
│           ▼                                                  │
│  ⑤ New data → retrain stronger Verifier                      │
│           │                                                  │
│           └──────────────────────► back to ②                 │
└─────────────────────────────────────────────────────────────┘
```

This is the **self-improving flywheel**. The verifier and generator co-evolve. Neither plateaus because each one forces the other to improve.

---

## The Big Conceptual Picture — What the Paper Has Built

Let's step back and look at what all of this amounts to:

**Before this paper:** You train a model by rewarding correct final answers. The model learns to produce correct-looking outputs but has no internal model of correctness. It can't verify itself. It can't explain *why* a proof failed.

**After this paper:** The model has internalized what a good proof *is* (via the rubrics). It can critique its own work with real, grounded reasoning. Its training reward is itself a learned capability, not a lookup table. And because verification scales independently of generation, you can keep improving the system even without more human-labeled data.

The result is a model that can assess and iteratively improve its own proofs — achieving gold-level performance at IMO 2025 and CMO 2024, and scoring 118/120 on Putnam 2024, exceeding the highest human score of 90.


# 🔬 Phase 3 — Self-Verification, Fully Decomposed

## First: Why Phase 3 even needs to exist

After Phase 2, you have a generator πθ that writes proofs and gets rewarded by the verifier. But the interaction is **external**:

```
Problem X → [Generator πθ] → Proof Y → [Verifier πφ] → Score R_Y
                                                              ↓
                                              GRPO updates πθ weights
```

The generator improves, but it does so **blindly**. It never sees *why* a proof scored 0.5 instead of 1. It just knows "that proof got a bad score, try something different." It's like a student who only ever sees their grade, never the marked-up paper.

The generator also has another problem: **at inference time, there is no training loop**. Once deployed on a real competition problem, it gets one shot. If the proof has a flaw, the generator has no mechanism to catch it and fix it before submitting.

Phase 3 solves both of these simultaneously.

---

## The Core Idea: Make Verification Part of the Generation

A reliable proof verifier enables teaching proof generators to evaluate proofs exactly as the verifier does — allowing a proof generator to iteratively refine its proofs until it can no longer identify or resolve any issues. In essence, the model is made explicitly aware of its reward function and enabled to maximize this reward through deliberate reasoning rather than blind trial-and-error.

So the goal is not just to have a generator that produces good proofs. It's to have a generator that **reasons about the quality of its own proofs as part of generating them**.

---

## What a Training Trajectory Actually Looks Like

In Phase 2, a single training sample is:
```
Input:  Problem X
Output: Proof Y
Reward: R_Y (from verifier)
```

In Phase 3, a single training sample is a **full multi-step trajectory**:

```
Input:   Problem X

Step 1 — DRAFT:
  Generator produces first proof attempt Y₁
  
Step 2 — SELF-CRITIQUE:
  Generator applies verifier logic to its OWN Y₁:
  "In step 3, I claimed that f(x) is bounded above by g(x),
   but I only showed this holds for x > 0. The case x = 0 
   was never handled. This is a critical gap."
  → Generator assigns itself a score: s₁ = 0.5

Step 3 — REVISION:
  Generator produces revised proof Y₂, specifically addressing
  the identified gap:
  "...we now handle the case x = 0 separately..."

Step 4 — SELF-CRITIQUE AGAIN:
  Generator evaluates Y₂:
  "The logic now appears complete. All cases are covered.
   Steps are each justified. No gaps identified."
  → Generator assigns itself: s₂ = 1

Step 5 — STOP:
  Generator decides: no more issues found, submit Y₂

Reward: Assigned on Y₂ (the FINAL proof only)
```

This is the critical thing: **the reward lands only at the end**. The generator is never told "your step 2 critique was good" or "your revision improved things by X." It only knows whether the final proof was good. All the intermediate critique and revision work is only valuable to the extent it results in a better final output.

---

## What GRPO Actually Does With This

GRPO works by sampling **multiple trajectories** for the same problem, then updating the model to assign higher probability to trajectories that resulted in higher rewards, relative to the group average.

So for one problem X, you might sample:

```
Trajectory A: Draft → Critique → Revise → Critique → Submit   Final score: 1.0
Trajectory B: Draft → Critique → Revise → Submit               Final score: 0.5
Trajectory C: Draft → Submit (no self-critique at all)          Final score: 0.0
```

GRPO looks at this group and says: Trajectory A was best. What did it do differently? It ran two rounds of critique-and-revise before submitting. Increase the probability of that behavior pattern.

Over thousands of problems, the generator learns:

1. Submitting without self-critiquing is correlated with bad outcomes
2. Critiquing but not fixing identified issues is correlated with bad outcomes
3. Critiquing thoroughly, fixing specifically what was identified, then re-checking — is correlated with good outcomes

These patterns get baked into the weights.

---

## What the Generator is Actually Learning — Three Separate Skills

Phase 3 trains the generator on three genuinely different cognitive operations, all within one model:

**Skill 1 — Proof Writing**
Producing a coherent, step-by-step mathematical argument from scratch. This was mostly developed in Phase 2.

**Skill 2 — Self-Critique**
Reading its own output and applying the verifier's rubric to it. The generator must identify the *exact location* of the logical gap (not just "this proof is bad"), and articulate *why* it's a gap. This is the verifier's skill, now re-learned inside the generator.

**Skill 3 — Targeted Revision**
Given a specific identified flaw, producing a proof that keeps all the working parts and surgically fixes only what was broken. This is different from starting over — it's more like editing than rewriting.

The interplay between these three skills is what makes Phase 3 non-trivial. The generator has to do all three well for the trajectory to earn a high reward.

---

## The Token Budget Implication

Here's something subtle: self-critique and revision **cost tokens**. The model generates more text per problem. GRPO is implicitly teaching the model to decide: *is it worth spending tokens on another round of critique, or is this proof good enough to submit?*

If the proof looks solid after one draft, spending tokens on a redundant critique that finds nothing is wasteful and adds noise. If the proof has a real gap, spending tokens on a targeted fix is worth it because it can change the final score from 0.5 to 1.0.

The model learns this cost-benefit calibration entirely from the reward signal — no explicit instruction about when to keep critiquing or when to stop.

---

## How This Changes Inference (At Test Time)

Once Phase 3 training is complete, at inference you don't need the external verifier at all for the self-refinement process. The generator runs the full loop internally:

```
Problem X given
      ↓
Generator thinks: [draft proof]
      ↓
Generator thinks: [self-critique — does this proof hold up?]
      ↓
 If issues found:
      Generator thinks: [targeted revision]
      Generator thinks: [re-critique]
      Repeat...
 If no issues found:
      Output final proof
```

This is why the paper calls it **self-verifiable** — the verification capability is *inside* the generator. It doesn't need an external judge at inference time to decide whether to keep refining.

---

## The Crucial Distinction From "Chain of Thought" or "Reflection"

You might wonder: isn't this just like making the model "think longer" or "reflect" on its output? The answer is no, and the difference matters.

Generic reflection training just rewards the model for producing any kind of thinking before the answer. The model might learn to produce fluent-sounding "reflection" that doesn't actually catch real errors.

Phase 3 is different because the self-critique is grounded in the **verifier's rubric** — the same structured evaluation criteria that a human math expert would use. The model isn't just saying "let me reconsider." It's applying a specific, trained judgment about what constitutes a logical gap, an unjustified claim, or an omitted case. And because that judgment was trained under meta-verification (Phase 1D), it's faithful — the issues it identifies actually exist.

The reward signal ruthlessly filters out surface-level reflection: if the self-critique is just cosmetic but the final proof still has real gaps, the verifier will catch it and the score will be low. The model only gets rewarded for critique that actually led to a better proof.

---

## Summary of Phase 3 in One Tight Picture

```
TRAINING:
  For each problem X:
    Sample multiple full trajectories:
      [Draft Y₁] → [Self-critique: real issues identified?] 
                 → [Revise Y₂] → [Re-critique] → ... → [Final Yₙ]
    
    Reward = verifier score on Yₙ only
    GRPO: increase probability of trajectories that led to higher final scores

WHAT THE MODEL LEARNS:
  Skill 1: Write coherent proofs
  Skill 2: Identify real logical gaps in its own proofs (verifier logic internalized)
  Skill 3: Revise surgically to fix exactly what was identified
  Skill 4: Know when to stop (no more issues = submit)

INFERENCE:
  No external verifier needed
  Generator runs the full loop inside its own token stream
  Stops when self-critique finds nothing more to fix
```

The payoff is a model that doesn't just produce proofs — it produces proofs that it has *genuinely scrutinized and is confident in*. That's a qualitatively different kind of output from anything that came before it.



# 📊 Section 3 — Experiments

The paper evaluates the model in **three distinct modes**. Each mode uses progressively more compute at inference time. Understanding why there are three modes is key — they're not just running the same thing three times, they're testing three fundamentally different operating conditions.

---

## 3.1 — What Benchmarks They Test On

Before the results, understand what they're measuring against. The paper uses four evaluation sets, ordered by difficulty:

**Putnam 2024** — 12 problems from the premier undergraduate math competition in North America. These are hard but not IMO-level.

**IMO Shortlist 2024 (ISL)** — 31 problems. The pool from which IMO problems are selected. Harder than Putnam.

**IMO 2025** — 6 problems. The actual competition. Extremely hard.

**CMO 2024** — 6 problems. China Mathematical Olympiad. Comparably elite.

**IMO-ProofBench** — a benchmark of 60 problems developed by the DeepMind team, split into a basic set of 30 problems (pre-IMO to IMO-Medium difficulty) and an advanced set of 30 problems simulating complete IMO examinations up to IMO-Hard level.

One important detail: for the in-house competition problems, 8 proof samples are generated per problem, and correctness is measured by majority voting across 8 verification analyses produced by the final verifier. So even in the simplest mode, it's not a single shot — it's 8 attempts with a voting mechanism.

---

## 3.2 — The Three Evaluation Modes

### Mode 1 — One-Shot Generation (baseline)

This is the simplest operating mode. The generator produces a proof. The verifier scores it. No iteration.

This tells you: **how good is the model at writing proofs cold, without any self-refinement?**

It's the baseline you compare everything else against.

### Mode 2 — Sequential Refinement with Self-Verification

This activates everything from Phase 3. The model:
1. Writes a proof
2. Self-critiques
3. Revises
4. Repeats up to some maximum number of iterations

On IMO Shortlist 2024, sequential refinement with self-verification improves both pass@1 and best@32 quality metrics as the maximum number of refinement iterations increases.

This tells you: **does self-verification actually help, and does more iterations keep helping?**

### Mode 3 — High-Compute Search

This is the full system with no compute budget constraints. Here's exactly what it does:

Each proof-analysis pair is used to generate one refined proof, which then updates the candidate pool. This process continues for up to 16 iterations or until a proof successfully passes all 64 verification attempts, indicating high confidence in correctness.

Two things to notice here. First, the stopping criterion is very precise — not "16 iterations elapsed" but "passes all 64 verification attempts." This is the paper's probabilistic confidence threshold: if 64 independent verifier samples all say the proof is correct, you can be highly confident it's actually correct.

Second, all experiments used a single model — the final proof generator — which performs both proof generation and verification. This is the payoff of Phase 3. One model does everything. No separate verifier needed at inference.

---

## 3.3 — The Results

### Competition Results (High-Compute Mode)

The approach solved 5 of 6 problems from IMO 2025 and 4 problems plus partial credit on another from CMO 2024, achieving gold medal performance in both competitions. On Putnam 2024, the model solved 11 of 12 problems completely and the remaining problem with minor errors, scoring 118/120 and surpassing the highest human score of 90.

To feel the weight of the Putnam number: the best human score that year was 90. The model scored 118. That's not a narrow margin.

### IMO-ProofBench (Comparison to Other Models)

DeepSeekMath-V2 outperforms DeepMind DeepThink IMO Gold on the Basic subset and remains competitive on the Advanced subset, while clearly beating other large models.

This is notable because DeepThink IMO Gold was specifically built for IMO problems. DeepSeekMath-V2 beats it on the easier set and matches it on the hardest problems, despite being a more general system.

### What the Three Modes Tell You Comparatively

This is the most structurally interesting result. The paper is implicitly asking three questions:

| Mode | Question being answered |
|---|---|
| One-shot | How good is the proof quality from training alone? |
| Sequential refinement | Does self-critique + revision improve over one-shot, and by how much? |
| High-compute search | What's the ceiling when you throw maximum compute at it? |

Sequential refinement via self-verification demonstrates significant increases in both pass@1 and best-of-k verification scores across high-difficulty benchmarks.

The progression one-shot → refinement → high-compute search is also the paper's argument for **test-time scaling** — the idea that you can trade compute for accuracy at inference time. And crucially, this test-time scaling works because the verifier is reliable. If the verifier gave noisy or unfaithful scores, running 64 verification attempts and taking a majority would just amplify the noise. The whole scaling argument depends on the verifier being trustworthy — which brings you all the way back to why Phases 1 and 1D (meta-verification) were necessary in the first place.

---

Everything connects. The verifier's faithfulness (Phase 1D) is what makes the high-compute search mode meaningful. The self-verification training (Phase 3) is what lets a single model do both jobs at inference. And the iterative flywheel (Phase 4) is what lets the system keep improving past what human annotation alone could support.

What questions does this raise for you?


# 🔄 The Full Iterative Cycle — Every Input, Every Output, Every Transformation

---

## The Cast of Characters (Models)

Before the cycle, understand who the players are:

| Symbol | Name | What it does |
|---|---|---|
| **πφ** | Verifier | Takes (problem, proof) → outputs critique + score |
| **πη** | Meta-Verifier | Takes (problem, proof, critique) → outputs quality score of the critique |
| **πθ** | Generator | Takes (problem) → outputs proof |

All three are initialized from the same base: **DeepSeek-V3.2-Exp-SFT** (a model already SFT'd on math and code reasoning data). They diverge through separate RL training.

---

## PHASE 1 — Build the Verifier πφ

### Step 1A — Cold Start Data Construction

```
INPUT:
  - 17,503 AoPS contest problems (𝒟ₚ)
  - DeepSeek-V3.2-Exp-Thinking (a weak, pre-optimization model)
  - Human math experts

PROCESS:
  1. Feed each problem to the weak model → generate candidate proofs
     (multiple rounds of self-refinement prompted, since model is error-prone)
  2. Sample a subset of (problem, proof) pairs across diverse types
  3. Human experts score each proof: s ∈ {0, 0.5, 1}

OUTPUT:
  𝒟ᵥ = { (Xᵢ, Yᵢ, sᵢ) }
  Each item = one problem, one proof, one expert score
```

This is your **ground truth** for what good vs. bad proofs look like.

---

### Step 1B — Train Verifier v1 (Basic RL)

```
INPUT:
  - Base model: DeepSeek-V3.2-Exp-SFT
  - Dataset 𝒟ᵥ = { (problem, proof, expert_score) }
  - Rubrics 𝓘ᵥ (evaluation guidelines, in the prompt)

RL TRAINING LOOP (GRPO):
  For each training sample (X, Y, s):
    1. Feed (problem X, proof Y, rubrics 𝓘ᵥ) into the model
    2. Model generates response V' containing:
         - Natural language critique ("The issue is that step 3 skips...")
         - A predicted score s' ∈ {0, 0.5, 1} inside \boxed{}
    3. Compute reward:
         R_format = 1 if output has required structure, else 0
         R_score  = 1 - |s' - s|       ← continuous, 0 to 1
         R_total  = R_format × R_score  ← gated: no structure = no reward
    4. GRPO updates model weights to increase probability of high-reward outputs

OUTPUT:
  πφ (v1) — a verifier that predicts correct scores
  ⚠️ PROBLEM: it may hallucinate fake issues to justify its scores
```

---

### Step 1C — Train the Meta-Verifier πη

```
INPUT:
  - πφ (v1) — the verifier just trained above
  - 𝒟ᵥ — the same problems and proofs
  - Human experts (again)

PROCESS:
  1. Run πφ (v1) on each (X, Y) → produces critique Vᵢ
  2. Human experts score the QUALITY of each critique: ms ∈ {0, 0.5, 1}
     (Not "was the proof score right?" but "were the identified issues real
      and do they actually justify the score?")
  3. This creates 𝒟ₘᵥ = { (Xᵢ, Yᵢ, Vᵢ, msᵢ) }

RL TRAINING (same GRPO structure):
  Feed (problem X, proof Y, critique V, meta-rubrics 𝓘ₘᵥ) into a fresh model
  Model outputs: meta-critique + meta quality score
  Reward = same format × score structure, but now "score" = meta quality score

OUTPUT:
  πη — a meta-verifier that outputs R_meta ∈ [0, 1]
  This is the model that catches hallucinated issues
```

---

### Step 1D — Retrain Enhanced Verifier πφ (v2)

```
INPUT:
  - Base model: DeepSeek-V3.2-Exp-SFT (fresh start)
  - 𝒟ᵥ AND 𝒟ₘᵥ (both datasets)
  - Trained meta-verifier πη (now frozen, used only as a reward signal)

RL TRAINING:
  For each (X, Y, s) from 𝒟ᵥ:
    1. Model generates critique V' and predicted score s'
    2. Compute rewards:
         R_format = structure check (same as before)
         R_score  = 1 - |s' - s|
         R_meta   = πη( X, Y, V' ) → quality score of the critique
         R_total  = R_format × R_score × R_meta  ← NEW: meta gates everything
    3. GRPO update

  For each (X, Y, V, ms) from 𝒟ₘᵥ:
    Same training, but now the model also learns to DO meta-verification

OUTPUT:
  πφ (v2) — one model that can do BOTH:
    • Verify proofs (score 0/0.5/1 with real, faithful reasoning)
    • Meta-verify critiques (score the quality of any analysis)
  
  Quality score: 0.85 → 0.96 on validation set
  Proof score accuracy: unchanged ✓
```

---

## PHASE 2 — Train the Generator πθ

```
INPUT:
  - Base model: DeepSeek-V3.2-Exp-SFT (fresh start again)
  - Problem set 𝒟ₚ (all 17,503 AoPS problems)
  - Trained verifier πφ (v2) — now FROZEN, used only as reward signal

RL TRAINING (GRPO):
  For each problem Xᵢ:
    1. Generator produces proof Yᵢ
    2. Feed (Xᵢ, Yᵢ) to frozen πφ → get score R_Y ∈ {0, 0.5, 1}
    3. R_Y is the entire reward signal
    4. GRPO updates generator to produce higher-scoring proofs

OUTPUT:
  πθ (v1) — a proof generator trained to write proofs
             that satisfy the verifier's rubrics
  
  Key property: reward signal exists for ALL proof problems,
  not just ones with numerical answers
```

---

## PHASE 3 — Self-Verification: Generator Internalizes the Verifier

This is where it gets deep. Instead of always calling the external verifier, the generator is now trained to apply verification *inside its own reasoning*.

```
INPUT:
  - πθ (v1) — trained generator
  - πφ (v2) — trained verifier  
  - Problem set 𝒟ₚ

TRAINING SETUP:
  The model is trained on trajectories of the form:
  
  [Draft proof] → [Self-critique] → [Revised proof] → [Self-critique] → ... → [Final proof]
  
  The reward is assigned on the FINAL proof only.
  So the model learns: spending compute on self-critique is worth it
  if the final proof improves.

WHAT THE MODEL LEARNS TO DO (at inference):
  1. Write a draft proof for problem X
  2. Apply verifier logic to its own draft:
       "Step 3 assumes Y is bounded, but I never proved that..."
  3. Revise the proof to fix the identified issue
  4. Check again: "Is there anything else wrong?"
  5. Repeat until it can no longer find any issues
  6. Output the final proof

OUTPUT:
  πθ (v2) — a generator that can self-verify and self-refine
  The model now "knows" its reward function and can deliberately
  optimize toward it, not through random sampling but through
  targeted self-correction
```

---

## PHASE 4 — Maintaining the Gap: Scaling Verification Compute

As πθ gets stronger, the proofs it generates become harder to evaluate correctly. The verifier's training data (from the weak early generator) no longer covers the kinds of subtle near-correct proofs the better generator now produces.

```
PROBLEM:
  Strong generator produces hard proofs
  → Verifier hasn't seen this difficulty level
  → Verifier starts making wrong calls
  → Bad reward signal → generator training degrades

SOLUTION — Auto-labeling hard proofs:

INPUT:
  - New hard proofs from the improved πθ
  - πφ (v2) — current verifier

PROCESS:
  For each hard new proof Y on problem X:
    Run πφ many times (scale compute)
    → get many score samples {s₁, s₂, s₃, ...}
    → aggregate into a robust consensus score s*
    
  This gives you (X, Y, s*) without human annotation

OUTPUT:
  New expanded 𝒟ᵥ with hard-to-verify proofs included
  → Retrain πφ → get πφ (v3) that handles harder proofs
  → Use πφ (v3) to train πθ further → πθ (v3)
  → Repeat
```

---

## The Complete Flywheel, All Together

```
                    ┌─────────────────────────────┐
                    │   HUMAN EXPERTISE (once)     │
                    │  Score proofs + critiques     │
                    │  𝒟ᵥ and 𝒟ₘᵥ created         │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   PHASE 1: BUILD VERIFIER    │
                    │  v1 RL → Meta-verifier RL    │
                    │  v2 RL (with R_meta signal)  │
                    │  → πφ: accurate + faithful   │
                    └──────────────┬──────────────┘
                                   │ reward signal
                    ┌──────────────▼──────────────┐
                    │   PHASE 2: TRAIN GENERATOR   │
                    │  πθ RL using πφ as reward    │
                    │  → can write good proofs     │
                    └──────────────┬──────────────┘
                                   │ internalize verifier
                    ┌──────────────▼──────────────┐
                    │   PHASE 3: SELF-VERIFICATION │
                    │  Train on refine trajectories│
                    │  → πθ self-critiques + fixes │
                    └──────────────┬──────────────┘
                                   │ generator now stronger
                    ┌──────────────▼──────────────┐
                    │   PHASE 4: SCALE VERIFY      │
                    │  New hard proofs auto-labeled│
                    │  → πφ retrained on harder data│
                    └──────────────┬──────────────┘
                                   │ verifier now stronger
                                   └──► back to PHASE 2
```

Each lap around this loop: **both the verifier and generator get stronger**. Human annotation is only needed once to bootstrap. After that, the system is self-sustaining.

---

One thing worth sitting with before we move on: notice that **the generator and verifier are separate models for most of the process**, but by Phase 3 the generator has *internalized* the verifier. This means at inference time, you don't necessarily need to run two separate models — the generator carries the verification capability inside itself. That's the "self-verifiable" in the title.

Does this full picture feel solid, or is there any specific transition between phases you'd want to unpack further before we go to the experiments?