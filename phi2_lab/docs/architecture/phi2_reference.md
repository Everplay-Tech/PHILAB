# Phi-2 Architecture Reference

This note captures the fixed architectural properties that Phi-2 exposes to the
rest of the lab. The values mirror the release specification from Microsoft and
are also encoded in `models/phi2/architecture.py` so tools can reason about the
shape programmatically.

## Core hyper-parameters

| Property | Value | Notes |
| --- | --- | --- |
| Parameters | ~2.7B | Derived from 32 layers × 2560 hidden dim × 32 heads |
| Hidden size | 2560 | Model width per token representation |
| Intermediate size | 10240 | 4× expansion for gated MLP |
| Layers | 32 transformer blocks | Each layer combines rotary attention + MLP |
| Attention heads | 32 per layer | Balanced with hidden size ⇒ 80-d head dim |
| Context window | 2048 tokens | Controlled via rotary embeddings |
| Vocab size | 51,200 | SentencePiece vocabulary used by Phi-2 |

## Layer structure

Each transformer block follows the canonical order:

1. **Rotary-positioned self-attention** with QK normalization disabled but using
   a `partial_rotary_factor` of 0.5 and `rope_theta` of 10,000.
2. **Residual gated MLP** implemented as a GELU-new approximation in the codebase.
3. **LayerNorm** (pre-norm configuration) on both sublayers.

## Attention head semantics

* 32 heads split the 2,560-d hidden state into 80-d subspaces.
* Heads 0–7 typically track lexical patterns and repeated tokens.
* Heads 8–15 prefer mathematical operators and numeral span continuation.
* Heads 16–23 focus on code delimiters and indentation cues.
* Heads 24–31 participate in reasoning/memory routing, often co-activating on
  chain-of-thought prompts.

## MLP block characteristics

* Feed-forward dimension expands to 10,240 with gated SiLU mixing, but we expose
  it via GELU-new for easier simulation.
* Lower layers (0–7) respond strongly to punctuation perturbations.
* Middle layers (8–23) encode entity and relation binding; ablations degrade
  factual consistency the most here.
* Upper layers (24–31) amplify reasoning heuristics; the final two layers drive
  short-horizon planning and speculative sampling corrections.

These descriptions are grounded in the interpretability notebooks under
`notebooks/interpretability/`, which summarize ablation sweeps and probing logs.
