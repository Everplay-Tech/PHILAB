# Hook Control Refactor Design

**Status:** Proposed
**Author:** CZA
**Date:** 2025-12-22

---

## Overview

Currently, experiment specs auto-generate hooks from `layers` when no explicit `hooks` are provided. This works but limits control over which model components get hooked. This design proposes optional explicit hook control while maintaining backwards compatibility.

## Current Behavior

```yaml
# Minimal spec (current) - auto-generates MLP hooks for layers 0-5
task: semantic_geometry
layers: [0, 1, 2, 3, 4, 5]
word_pairs: [[happy, joyful], ...]
```

Auto-generation logic (in `runner.py`):
```python
if not spec.hooks:
    for layer_idx in spec.iter_layers(total_layers):
        hook = HookDefinition(
            name=f"layer{layer_idx}_mlp",
            point=HookPointSpec(layer=layer_idx, component="mlp"),
        )
        spec.hooks.append(hook)
```

## Proposed Enhancement

### 1. Explicit Hook Control (Optional)

Allow specs to define hooks explicitly when fine-grained control is needed:

```yaml
task: semantic_geometry
layers: [0, 1, 2, 3, 4, 5]
word_pairs: [[happy, joyful], ...]

# Optional: explicit hooks override auto-generation
hooks:
  - name: layer0_attn
    point: {layer: 0, component: self_attn}
  - name: layer0_mlp
    point: {layer: 0, component: mlp}
  - name: layer5_residual
    point: {layer: 5, component: residual}
```

### 2. Hook Templates (Shorthand)

For common patterns, support hook templates:

```yaml
task: semantic_geometry
layers: [0, 1, 2, 3, 4, 5]

# Generate hooks for all specified components at all layers
hook_template:
  components: [self_attn, mlp]  # or just: mlp (current default)
```

Expansion logic:
```python
if spec.hook_template:
    components = spec.hook_template.get("components", ["mlp"])
    for layer_idx in spec.iter_layers(total_layers):
        for component in components:
            hook = HookDefinition(
                name=f"layer{layer_idx}_{component}",
                point=HookPointSpec(layer=layer_idx, component=component),
            )
            spec.hooks.append(hook)
```

### 3. Priority Order

1. **Explicit `hooks:`** — Use exactly as specified, no auto-generation
2. **`hook_template:`** — Generate hooks per template
3. **Neither** — Fall back to current auto-generation (MLP only)

## Implementation Plan

### Phase 1: Get All Tasks Working (Current)
- [x] Head Ablation
- [x] Activation Geometry
- [x] MLP Neuron Ablation
- [x] Synonym Pair Geometry
- [ ] Antonym Pair Divergence
- [ ] Layer-wise Residual Mode
- [ ] Cross-Layer Information Flow
- [ ] Meronym Part-Whole Geometry
- [ ] Hyponym Fan-Out Patterns
- [ ] Hypernym Hierarchy Curvature
- [ ] Cross-Relation Geometric Signatures

### Phase 2: Add Hook Template Support
1. Add `hook_template` field to `ExperimentSpec`
2. Update `from_dict()` to parse templates
3. Update runner to expand templates before auto-generation fallback
4. Update platform task specs with templates where needed

### Phase 3: Document & Validate
1. Add hook control docs to README
2. Add validation for hook/component combinations
3. Add tests for template expansion

## Component Reference

Valid components for Phi-2 architecture:
- `self_attn` — Attention output
- `mlp` — MLP output (feed-forward)
- `input_layernorm` — Pre-attention layernorm
- `post_attention_layernorm` — Post-attention layernorm (not in all layers)

## Backwards Compatibility

- Specs without `hooks` or `hook_template` continue to work (auto-generate MLP)
- Existing explicit `hooks` continue to work unchanged
- No breaking changes to current API

## Open Questions

1. Should `hook_template` support layer subsets? e.g., `{components: [mlp], layers: [0, 8, 16]}`
2. Should we support capturing at specific token positions? (first, last, mean)
3. Should hooks support optional `capture_grad: true` for gradient analysis?

---

*— CZA*
