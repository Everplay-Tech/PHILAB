"""Service helpers for aggregating Atlas coverage."""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from .query import fetch_semantic_codes, find_experiments
from .schema import LayerInfo, ModelInfo
from .storage import AtlasStorage


def collect_experiment_coverage(
    storage: AtlasStorage, focus_tags: Sequence[str]
) -> Tuple[List[str], set[int]]:
    mapped_layers: set[int] = set()
    experiments: List[str] = []
    for record in find_experiments(storage, tags=list(focus_tags)):
        experiments.append(record.spec_id)
        payload_layers = record.payload.get("layers") or []
        payload_layer_idx = record.payload.get("layer_idx")
        if isinstance(payload_layer_idx, int):
            mapped_layers.add(payload_layer_idx)
        for layer in payload_layers:
            try:
                mapped_layers.add(int(layer))
            except (TypeError, ValueError):
                continue
    return experiments, mapped_layers


def collect_layer_notes(
    storage: AtlasStorage, model_name: str
) -> Tuple[Dict[int, str], set[int]]:
    layer_notes: Dict[int, str] = {}
    mapped_layers: set[int] = set()
    with storage.session() as session:
        model = session.query(ModelInfo).filter(ModelInfo.name == model_name).one_or_none()
        if not model:
            return layer_notes, mapped_layers
        for layer in session.query(LayerInfo).filter(LayerInfo.model_id == model.id):
            if layer.summary:
                layer_notes[layer.index] = layer.summary
                mapped_layers.add(layer.index)
    return layer_notes, mapped_layers


def collect_semantic_codes(storage: AtlasStorage, focus_tags: Sequence[str]) -> List[str]:
    entries = fetch_semantic_codes(storage, tag_filter=list(focus_tags) or None)
    return [entry.code for entry in entries]
