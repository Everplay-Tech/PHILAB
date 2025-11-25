# Phi-2 Architecture Atlas Entry

## Overview
- Phi-2 is a 32-layer, 2.7B parameter decoder-only transformer with 2,560 hidden
dimensions, 10,240-wide MLPs, and 32 attention heads per block, providing an
80-dimension slice per head for rotary self-attention. The compression DSL
codifies this layout as semantic code `§ARCH` so downstream tools can request
the same layer catalog that powers this Atlas entry.【F:docs/architecture/phi2_reference.md†L3-L36】【F:phi2_lab/config/codebook.yaml†L1-L17】
- The programmable representation mirrors the dataclasses in
`models/phi2/architecture.py`, enabling tooling to iterate over layers, heads,
and MLP blocks directly from `build_phi2_architecture`.【F:models/phi2/architecture.py†L13-L151】

## Layer and block catalog
| Layer range | Dominant function | Sensitivity pattern | Notes |
| --- | --- | --- | --- |
| 0–7 | Lexical cleanup + punctuation-aware MLPs | Heads/MLPs react sharply to punctuation or whitespace edits, increasing repetition when perturbed.【F:docs/architecture/phi2_reference.md†L31-L44】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L15-L30】 | Good candidates for tokenizer-alignment ablations.
| 8–15 | Symbolic and arithmetic routing | Head group tracks operators; MLPs encode entity bindings, so zeroing causes factual drift.【F:docs/architecture/phi2_reference.md†L31-L44】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L15-L30】 | Pair with math probes.
| 16–23 | Code + structure maintenance | Attention enforces indentation; MLPs stabilize relation frames, so ablations corrupt code layout and narrative consistency.【F:docs/architecture/phi2_reference.md†L32-L44】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L15-L30】 | Ideal for code-style adapters.
| 24–31 | Reasoning routers and planner MLPs | Head/MLP interventions dramatically alter chain-of-thought depth and planning quality.【F:docs/architecture/phi2_reference.md†L33-L46】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L15-L30】 | Reserve for reasoning experiments.

Each catalog entry is instantiated in the architecture builder, so experiments
can iterate over `Phi2Architecture.layers` to attach hooks or ablations without
manually specifying indices; in practice this is the same lookup performed by
`§ARCH` when regenerating the DSL tables.【F:models/phi2/architecture.py†L48-L150】【F:phi2_lab/config/codebook.yaml†L1-L17】

## Attention head roles
- Heads 0–7: lexical repetition control; best ablated for studying detokenization
drifts.【F:docs/architecture/phi2_reference.md†L31-L33】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L15-L18】
- Heads 8–15: math/operator tracking; amplifies symbol integrity.【F:docs/architecture/phi2_reference.md†L33-L34】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L15-L18】
- Heads 16–23: code delimiter sentinels; removing them collapses indentation and
block structure.【F:docs/architecture/phi2_reference.md†L34-L35】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L16-L19】
- Heads 24–31: reasoning/memory routers; central to long-form scratchpad
behavior.【F:docs/architecture/phi2_reference.md†L35-L36】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L17-L20】

## MLP focus areas
- 0–7: punctuation-aware gating; adjust prompts to test lexical stability.【F:docs/architecture/phi2_reference.md†L40-L43】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L26-L29】
- 8–23: entity/relation storage; logistic probes show clean separability.【F:docs/architecture/phi2_reference.md†L41-L44】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L26-L29】
- 24–31: reasoning heuristics and planning buffers; final block saturates on
planner prompts.【F:docs/architecture/phi2_reference.md†L44-L46】【F:notebooks/interpretability/phi2_layer_sensitivity.ipynb†L27-L30】

## Flow diagram
```
Token Embedding (51,200 vocab) → LayerNorm →
Repeat 32× {
  Rotary Self-Attention (32 heads, 80-d each)
  Residual + LayerNorm
  Gated MLP (2560 → 10240 → 2560, GELU-new approx)
  Residual + LayerNorm
}
→ Output projection
```
The diagram reinforces the same ordering documented in the architecture note,
ensuring Atlas queries surface the canonical compute path.【F:docs/architecture/phi2_reference.md†L20-L27】
