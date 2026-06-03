# Premise Selection Architecture & Pipeline

This document explains the end-to-end flow for how the GNN predicts premises (both local hypotheses and external library lemmas) to solve Lean 4 proof states. It breaks down the entire pipeline and exactly what each file is responsible for.

## High-Level Pipeline

The premise selection pipeline is built in **four main stages**:

1. **Corpus Extraction**: Extracting a mapping of all mathematical lemmas available in Mathlib from the LeanDojo Hugging Face dataset.
2. **Baseline GNN (Frozen)**: A `GraphSAGEStateClassifier` that encodes Lean 4 abstract syntax trees (DAGs) into 512-dimensional vector embeddings. 
3. **Lemma Indexing**: Passing all lemmas from the Corpus through the Baseline GNN to create static embeddings, which are stored in a highly-optimized FAISS vector database.
4. **Premise Scorer Training**: Training a lightweight neural network (the Scorer) on top of the frozen GNN. It retrieves the top $K$ lemmas from FAISS, combines them with local hypotheses in the proof state, and ranks them to find the true premise.
5. **Inference**: Passing a new proof state through the pipeline to predict the best tactic and its exact arguments.

---

## 1. Data Preparation

### `scripts/extract_lemma_corpus_from_hf.py` & `scripts/build_lemma_corpus.py`
These scripts download the raw LeanDojo training dataset from Hugging Face and extract every single theorem and lemma it contains. 
- **Output:** `artifacts/lemmas/v1/corpus/lemmas.jsonl`
- **Why it matters:** The FAISS index only understands IDs (e.g., Lemma #425). We need this corpus so that when FAISS returns ID #425, we know it corresponds to `Algebra.add_comm`.

---

## 2. Indexing the Math Library

### `scripts/build_lemma_index.py` & `atp_lean_gnn/lemma_index.py`
Once you have a trained baseline GNN (`best.pt`), we need to encode all the lemmas in the corpus so we can quickly search them later.
- `build_lemma_index.py` loads the corpus and passes each lemma's graph representation through the frozen GNN.
- `lemma_index.py` wraps the `faiss` library. It takes the 512-dimensional vector outputs from the GNN and builds an optimized similarity search index.
- **Output:** `artifacts/lemmas/v1/index/lemma_index.faiss`
- **Why it matters:** Instead of comparing a proof state against 60,000 lemmas one-by-one (which is computationally impossible during training), we can query the FAISS index to instantly get the Top-500 most mathematically similar lemmas.

---

## 3. Training the Premise Scorer

This is the most complex part of the pipeline. We freeze the heavy GNN backbone and only train the tactic and premise selection heads.

### `scripts/train_scorer.py`
The entry point for training. It loads the frozen baseline model, the FAISS index, and the datasets, and initializes the `TacticWithArgsClassifier` and `PremiseScorer`.

### `atp_lean_gnn/argument_selector.py`
Contains the `TacticWithArgsClassifier`. This wraps the baseline GNN. 
- It encodes the nodes in the graph (`model.backbone.encode_nodes`).
- It extracts the single vector representing the entire proof state (`model.backbone.readout`).
- It predicts the tactic (e.g., `rw`, `apply`).

### `atp_lean_gnn/premise_pool.py`
Contains `build_unified_pools()`.
For every proof state in a training batch, this file is responsible for gathering the "candidates".
1. It queries FAISS with the proof state embedding to get the top 500 **library lemmas**.
2. It extracts the embeddings for the **local hypotheses** (nodes in the graph that belong to the current context).
3. It merges them into a single `CandidatePool`.

### `atp_lean_gnn/premise_scoring.py`
Contains the `PremiseScorer` neural network and the loss function.
- `PremiseScorer.score()` takes the proof state embedding, the tactic embedding, and the `CandidatePool`. It computes a score for every candidate.
- `compute_premise_ranking_loss()` looks at the ground-truth targets (which premise was *actually* used by the human to solve this step). It finds where that premise is inside the `CandidatePool`, and penalizes the network if the true premise isn't ranked #1.

### `atp_lean_gnn/premise_training.py`
The actual training loop (`train_one_epoch_with_premises`).
1. It handles PyTorch Geometric's complex batching (unflattening 1D variable-length lists into 2D padded matrices using `arg_count`).
2. It runs the forward passes.
3. It combines the loss from predicting the tactic with the loss from ranking the premises.

---

## 4. Inference (Prediction)

When you want to solve a brand new theorem interactively, the pipeline runs the reverse process.

### `scripts/run_inference.py`
The CLI tool. You pass it a JSON proof state, and it loads the model, FAISS index, and the corpus. 

### `atp_lean_gnn/inference.py`
Contains `InferencePipeline`.
1. It converts your JSON proof state into a PyTorch Geometric DAG.
2. It passes the DAG through the GNN to get the proof state embedding.
3. It asks the model: *"What tactic should I use?"* -> Model says: `rw`.
4. It checks the arity (how many arguments does `rw` need? It needs 1).
5. It queries the FAISS index with the proof state embedding to get the top 500 lemmas.
6. It merges the FAISS lemmas with your local variables into a `CandidatePool`.
7. It asks the `PremiseScorer` to score the pool.
8. It takes the highest-scoring candidate. If it's a local variable, it returns the variable ID. If it's a FAISS lemma, it looks up the ID in the Corpus to return the human-readable string (e.g., `Algebra.add_comm`).
9. **Result:** `rw [Algebra.add_comm]`

---

## Quick Start / Execution Commands

Here are the exact commands to run the pipeline end-to-end:

**1. Extract Lemma Corpus:**
```bash
python scripts/extract_lemma_corpus_from_hf.py \
    --dataset artifacts/leandojo_data/leandojo_benchmark_4/random/train.json \
    --output artifacts/lemmas/v1/corpus/lemmas.jsonl
```

**2. Build FAISS Index (Requires a frozen baseline checkpoint):**
```bash
python scripts/build_lemma_index.py \
    --corpus artifacts/lemmas/v1/corpus/lemmas.jsonl \
    --config configs/pointer_graphsage_state.json \
    --checkpoint run_20260602_155913/best.pt \
    --output-dir artifacts/lemmas/v1/index
```

**3. Train the Premise Scorer:**
```bash
python scripts/train_scorer.py \
    --config configs/pointer_graphsage_state.json \
    --checkpoint runs/pointer_gnn/baseline_best.pt \
    --index-path artifacts/lemmas/v1/index
```

**4. Run Inference (Evaluation):**
```bash
python scripts/run_inference.py \
    --config runs/premise_gnn/run_latest/config.json \
    --checkpoint runs/premise_gnn/run_latest/best.pt \
    --index-path artifacts/lemmas/v1/index \
    --corpus artifacts/lemmas/v1/corpus/lemmas.jsonl \
    --test-file path/to/proof_state.json
```

---