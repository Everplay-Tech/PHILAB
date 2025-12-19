#!/usr/bin/env python3
"""
Capture REAL geometry telemetry from phi-2.

This runs actual prompts through phi-2, extracts activations from each layer,
computes geometry metrics, and saves telemetry for the dashboard.
"""

import time
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from pathlib import Path

# Add PHILAB to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from phi2_lab.geometry_viz.recorder import GeometryRecorder
from phi2_lab.geometry_viz.schema import LayerTelemetry, RunTimelinePoint, ResidualMode, ModeSpan
from phi2_lab.geometry_viz.telemetry_store import save_run_summary

def compute_effective_rank(matrix: np.ndarray, epsilon: float = 1e-12) -> float:
    """Compute effective rank via entropy of singular values."""
    if matrix.size == 0:
        return 0.0
    _, s, _ = np.linalg.svd(matrix.reshape(1, -1) if matrix.ndim == 1 else matrix, full_matrices=False)
    total = float(s.sum())
    if total <= 0:
        return 0.0
    probs = s / total
    entropy = -float(np.sum(probs * np.log(probs + epsilon)))
    return float(np.exp(entropy))

def extract_residual_modes(hidden_states: torch.Tensor, num_modes: int = 5) -> list:
    """Extract principal modes from hidden states via PCA."""
    # hidden_states: [batch, seq_len, hidden_dim]
    h = hidden_states.detach().float().cpu().numpy()
    h_flat = h.reshape(-1, h.shape[-1])  # [batch*seq, hidden]

    if h_flat.shape[0] < 2:
        return []

    # Center the data
    h_centered = h_flat - h_flat.mean(axis=0)

    # SVD for PCA
    try:
        U, S, Vt = np.linalg.svd(h_centered, full_matrices=False)
    except:
        return []

    total_var = (S ** 2).sum()
    modes = []

    for i in range(min(num_modes, len(S))):
        var_explained = (S[i] ** 2) / total_var if total_var > 0 else 0

        # Project points onto this mode for visualization
        projections = h_centered @ Vt[i]
        proj_2d = []
        if len(S) > 1:
            proj_other = h_centered @ Vt[min(i+1, len(S)-1)]
            proj_2d = [(float(projections[j]), float(proj_other[j])) for j in range(min(50, len(projections)))]

        modes.append(ResidualMode(
            mode_index=i,
            eigenvalue=float(S[i]),
            variance_explained=float(var_explained),
            token_examples=[f"token_{j}" for j in range(min(5, h_flat.shape[0]))],
            projection_coords=proj_2d,
            description=f"Principal direction {i} ({var_explained*100:.1f}% variance)",
            span_across_layers=[],
            growth_curve=[],
        ))

    return modes

def main():
    print("=" * 60)
    print("PHILAB - Real Geometry Telemetry Capture")
    print("=" * 60)

    # Load model
    print("\nLoading phi-2...")
    tokenizer = AutoTokenizer.from_pretrained('microsoft/phi-2', trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        'microsoft/phi-2',
        trust_remote_code=True,
        torch_dtype=torch.float32,
        output_hidden_states=True
    )
    model.eval()
    print(f"Model loaded: {model.config.model_type}")
    print(f"Layers: {model.config.num_hidden_layers}")

    # Test prompts - epistemology themed
    prompts = [
        "What is knowledge?",
        "How do we know what is true?",
        "What is the relationship between belief and truth?",
        "Can we have certainty about anything?",
        "What distinguishes justified belief from mere opinion?",
    ]

    # Initialize recorder
    recorder = GeometryRecorder(storage_root=Path("phi2_lab/geometry_viz/telemetry_runs"))
    recorder.begin_run(
        run_id="phi2_epistemology_probe",
        description="Real geometry telemetry from phi-2 on epistemology prompts",
        model_name="microsoft/phi-2",
        adapter_ids=["base_model"],
    )

    print(f"\nProcessing {len(prompts)} prompts...")

    all_layer_activations = {i: [] for i in range(model.config.num_hidden_layers + 1)}

    for prompt_idx, prompt in enumerate(prompts):
        print(f"\n[{prompt_idx + 1}/{len(prompts)}] {prompt[:50]}...")

        inputs = tokenizer(prompt, return_tensors="pt")

        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)

        hidden_states = outputs.hidden_states  # tuple of (batch, seq, hidden) per layer

        # Collect activations per layer
        for layer_idx, h in enumerate(hidden_states):
            all_layer_activations[layer_idx].append(h)

    # Now compute telemetry per layer
    print("\nComputing geometry metrics per layer...")

    for layer_idx in range(model.config.num_hidden_layers + 1):
        activations = all_layer_activations[layer_idx]
        if not activations:
            continue

        # Concatenate all activations for this layer
        combined = torch.cat(activations, dim=1)  # [1, total_tokens, hidden]
        combined_np = combined.squeeze(0).detach().float().cpu().numpy()

        # Compute metrics
        weight_norm = float(np.linalg.norm(combined_np))
        eff_rank = compute_effective_rank(combined_np)

        # Extract residual modes
        modes = extract_residual_modes(combined, num_modes=5)

        # Add span info to modes
        for mode in modes:
            mode.span_across_layers = [
                ModeSpan(layer_index=layer_idx, strength=mode.variance_explained)
            ]

        layer_telemetry = LayerTelemetry(
            layer_index=layer_idx,
            adapter_id="base_model",
            adapter_weight_norm=weight_norm / 1000,  # Normalize for display
            effective_rank=eff_rank,
            delta_loss_estimate=np.random.uniform(-0.01, 0.01),  # Placeholder
            residual_modes=modes,
            residual_sample_count=combined_np.shape[0],
        )

        timeline_point = RunTimelinePoint(
            step=prompt_idx,
            timestamp=time.time(),
            layer_index=layer_idx,
            adapter_id="base_model",
            adapter_weight_norm=weight_norm / 1000,
            effective_rank=eff_rank,
        )

        recorder.log_layer_snapshot(layer_telemetry, timeline_point)
        print(f"  Layer {layer_idx}: norm={weight_norm/1000:.3f}, rank={eff_rank:.2f}, modes={len(modes)}")

    # Save telemetry
    print("\nSaving telemetry...")
    save_path = recorder.save()
    print(f"Saved to: {save_path}")

    print("\n" + "=" * 60)
    print("DONE! Now restart the dashboard and uncheck 'Use mock data'")
    print("The real telemetry should appear in the Run dropdown.")
    print("=" * 60)

if __name__ == "__main__":
    main()
