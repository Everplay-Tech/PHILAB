"""Resource loader for static data files."""
from __future__ import annotations

import json
from importlib import resources

def _load_json(name: str) -> dict:
    with resources.files(__package__).joinpath(name).open("r", encoding="utf-8") as fh:
        return json.load(fh)

wordnet_relations = _load_json("wordnet_relations.json")

__all__ = ["wordnet_relations"]
