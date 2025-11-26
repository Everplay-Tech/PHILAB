"""Minimal SVG plotting helpers for geometry experiments."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from .analysis import GeometryReport

COLORS = {
    "base": "#1f77b4",
    "adapter": "#d62728",
    "dsl": "#2ca02c",
}

WIDTH = 720
HEIGHT = 420
PADDING = 64


def _project(
    layer_idx: int,
    value: float,
    layers: List[int],
    y_min: float,
    y_max: float,
) -> Tuple[float, float]:
    span_x = max(layers) - min(layers) or 1
    norm_x = (layer_idx - min(layers)) / span_x
    px = PADDING + norm_x * (WIDTH - 2 * PADDING)
    norm_y = (value - y_min) / (y_max - y_min)
    py = HEIGHT - PADDING - norm_y * (HEIGHT - 2 * PADDING)
    return px, py


def _line_path(points: List[Tuple[float, float]]) -> str:
    if not points:
        return ""
    segments = [f"M {points[0][0]:.1f},{points[0][1]:.1f}"]
    segments.extend(f"L {x:.1f},{y:.1f}" for x, y in points[1:])
    return " ".join(segments)


def _axis_lines(y_min: float, y_max: float, ticks: int = 5) -> List[str]:
    lines = []
    for idx in range(ticks + 1):
        value = y_min + idx * (y_max - y_min) / ticks
        py = HEIGHT - PADDING - (value - y_min) / (y_max - y_min) * (HEIGHT - 2 * PADDING)
        lines.append(
            f'<line x1="{PADDING}" y1="{py:.1f}" x2="{WIDTH - PADDING}" y2="{py:.1f}" '
            f'stroke="#ddd" stroke-width="1" />'
        )
        lines.append(
            f'<text x="{PADDING - 10}" y="{py + 4:.1f}" '
            f'font-size="12" text-anchor="end">{value:.2f}</text>'
        )
    return lines


def _layer_labels(layers: List[int]) -> List[str]:
    labels = []
    for layer in layers:
        px, py = _project(layer, 0, layers, 0, 1)
        labels.append(
            f'<text x="{px:.1f}" y="{HEIGHT - PADDING + 24}" font-size="12" '
            f'text-anchor="middle">{layer}</text>'
        )
    return labels


def _legend(entries: List[Tuple[str, str]]) -> List[str]:
    lines = []
    for idx, (label, color) in enumerate(entries):
        y = PADDING + idx * 18
        lines.append(
            f'<rect x="{WIDTH - PADDING + 10}" y="{y - 10}" width="18" height="12" fill="{color}" />'
        )
        lines.append(
            f'<text x="{WIDTH - PADDING + 34}" y="{y}" font-size="12" text-anchor="start">{label}</text>'
        )
    return lines


def _render_svg(
    layers: List[int],
    series: Dict[str, List[float]],
    title: str,
    y_label: str,
    y_min: float,
    y_max: float,
    output_path: Path,
) -> None:
    axis_lines = _axis_lines(y_min, y_max)
    layer_labels = _layer_labels(layers)
    legend_entries = _legend([(label, COLORS[label]) for label in series.keys()])
    paths = []
    for label, values in series.items():
        points = [_project(layer, value, layers, y_min, y_max) for layer, value in zip(layers, values)]
        path = _line_path(points)
        paths.append(
            f'<path d="{path}" fill="none" stroke="{COLORS[label]}" stroke-width="2" />'
        )
    svg = [
        f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'xmlns="http://www.w3.org/2000/svg">',
        f'<style>text {{ font-family: "DejaVu Sans", sans-serif; }}</style>',
        f'<text x="{WIDTH/2:.1f}" y="{PADDING/2:.1f}" font-size="16" text-anchor="middle">{title}</text>',
        f'<text x="{PADDING/4}" y="{HEIGHT/2:.1f}" font-size="12" transform="rotate(-90 {PADDING/4},{HEIGHT/2:.1f})">{y_label}</text>',
        f'<line x1="{PADDING}" y1="{HEIGHT - PADDING}" x2="{WIDTH - PADDING}" y2="{HEIGHT - PADDING}" stroke="#555" stroke-width="1.5" />',
        f'<line x1="{PADDING}" y1="{PADDING}" x2="{PADDING}" y2="{HEIGHT - PADDING}" stroke="#555" stroke-width="1.5" />',
    ]
    svg.extend(axis_lines)
    svg.extend(layer_labels)
    svg.extend(paths)
    svg.extend(legend_entries)
    svg.append('</svg>')
    output_path.write_text("\n".join(svg), encoding="utf-8")


def plot_energy_profiles(report: GeometryReport, output_dir: str | Path) -> Path:
    layers = [layer.layer for layer in report.layers]
    series = {
        "base": [layer.base_energy[0] for layer in report.layers],
        "adapter": [layer.adapter_energy[0] for layer in report.layers],
        "dsl": [layer.dsl_energy[0] for layer in report.layers],
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "principal_energy.svg"
    _render_svg(
        layers,
        series,
        title="Principal direction energy across layers",
        y_label="Variance explained",
        y_min=0.0,
        y_max=1.0,
        output_path=path,
    )
    return path


def plot_alignment_profiles(report: GeometryReport, output_dir: str | Path) -> Path:
    layers = [layer.layer for layer in report.layers]
    series = {
        "adapter": [layer.adapter_alignment for layer in report.layers],
        "dsl": [layer.dsl_alignment for layer in report.layers],
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "subspace_alignment.svg"
    _render_svg(
        layers,
        series,
        title="Adapter vs DSL subspace overlap with base",
        y_label="Mean subspace overlap",
        y_min=0.5,
        y_max=1.0,
        output_path=path,
    )
    return path
