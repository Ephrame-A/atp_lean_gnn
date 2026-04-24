# Tactic Argument Resolver Architecture

This document outlines the architecture and mechanics of the Pointer Network (Cross-Attention) mechanism added to the GNN. This addition enables the model to predict not just a tactic family (like `rw` or `apply`), but also the specific nodes in the graph that should be used as arguments for that tactic.

The changes are entirely **additive**, meaning the baseline `GraphSAGEStateClassifier` is wrapped and remains fully intact.

---

## 1. Data Processing: Finding the Ground Truth

Before the neural network trains, we must resolve the human-written string arguments (e.g., `"Nat.add_comm"`) into absolute node indices within the generated DAG. This occurs during the `process_split` phase.

### A. Best-Effort Regular Expression Parser (`labels.py`)
Since Lean 4 syntax is highly complex, the `parse_tactic_arguments` function operates as a "best-effort" heuristic:
1. It strips out the tactic name and noise words (e.g., "only", "with", "using").
2. It looks for the outermost brackets `[` or `(`.
3. Using the Regex `[A-Za-z0-9_.']+`, it isolates any unbroken string of valid identifier characters, effectively using spaces, commas, and operators as delimiters.
4. **Example:** `"simp only [h1, Nat.add_comm]"` is successfully parsed into the tokens `["h1", "Nat.add_comm"]`.

### B. DAG Node Matching (`preprocess.py`)
Inside `_resolve_arg_node_indices`, the system builds a lookup dictionary of every node in that specific proof state's DAG, mapping the node's `label` property to its integer ID.
* It iteratively attempts to look up each parsed string token in the dictionary.
* If a DAG node label perfectly matches the string token, its integer `node_id` is recorded.
* If the token is not found in the graph (e.g. it was a garbage token from a bad regex match, or a global theorem not in the local context), it records `-1`.

### C. Storage
These indices are saved to the PyG `Data` object as `data.arg_node_indices` alongside `data.arg_count`.

---

## 2. Model Forward Pass: The Pointer Head

The new module `TacticWithArgsClassifier` and its pointer head `ArgumentSelector` (in `argument_selector.py`) handle the inference.

### A. Dynamic Loop Size
Tactics require different numbers of arguments (`simp` requires 0, `apply` requires 1, `have` requires 2). When a batch of graphs is passed in, the model determines `n_steps` dynamically:
```python
n_steps = max(get_tactic_arity(name) for name in tactic_names)
```
The pointer network loop runs exactly `n_steps` times.

### B. Autoregressive Node Selection
For each step in the loop, the `ArgumentSelector` executes scaled dot-product cross-attention:
1. **Query Formulation:** The query is constructed by concatenating the global `state_emb`, the `tactic_emb`, and crucially, the embedding of the **previously selected argument** (`prev_arg_emb`). This autoregressive context prevents the model from blindly picking the same argument twice and allows it to condition on past choices.
2. **Logit Computation:** The query vector executes a dot-product against the embeddings of *every single node* in the Megagraph, outputting a probability logit for each node.

### C. Syntax Node Masking (`premise_mask`)
In `pyg.py`, a static `build_premise_mask` function flags leaf-like nodes (`var`, `predicate`, `type`, `Hyp`) as `True` and structural nodes (`App`, `Arrow`, `State`) as `False`.

Inside the `ArgumentSelector`, before the probabilities are returned, a `.masked_fill_` runs using this mask, forcing all structural nodes' logits to `-inf`. This guarantees the model physically cannot select a syntax node as a tactic argument.

---

## 3. Loss Computation: Masking the Unknowns

Because we batch varying tactics together (some needing 0 args, some 2) and rely on a "best effort" string parser that can fail (`-1`), the loss function must be highly dynamic.

In `compute_combined_loss`, a boolean `valid` mask is built *per-step* for the batch:

1. **Parser Failure Masking:** If a sample's ground-truth target is `-1`, `valid` is set to `False`. The neural network is fully protected from being penalized by bad parser outputs.
2. **Zero-Arity Masking:** If the step loop is on `k=1` (predicting the 2nd argument), but Graph B used the tactic `apply` (which only requires 1 argument), `valid` is set to `False` for Graph B.
3. **Cross Entropy:** Finally, `F.cross_entropy(arg_logits_k[valid], gt_k[valid])` is evaluated. 

By filtering the logits down to only the valid `[V]` samples, graphs that do not require an argument at step `k` are entirely removed from the tensor, ensuring they do not unfairly skew the gradients.
