"""Build a WordNet 3.1 semantic relations dataset (JSONL) for probing.

This script pulls relation edges from the local NLTK WordNet corpus and writes a
JSONL file with fields:
    head: lemma for source synset
    tail: lemma for target synset
    relation: WordNet relation name (e.g., hypernym, meronym_part)
    head_synset: synset id (offset-pos)
    tail_synset: synset id (offset-pos)

It supports filtering by pillar (12 canonical groups) and per-relation limits.

Note: Requires nltk with the wordnet corpus installed. For WordNet 3.1 alignment
you may need the latest NLTK data; by default NLTK ships 3.0. This script does
not download data automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import hashlib
import sys
from typing import Iterable, List, Tuple

try:
    from nltk.corpus import wordnet as wn
except Exception as exc:  # pragma: no cover - optional dependency
    raise SystemExit("NLTK wordnet is required. Install nltk and download wordnet corpus.") from exc


RELATION_MAP = {
    "hypernym": lambda s: s.hypernyms(),
    "hyponym": lambda s: s.hyponyms(),
    "instance_hypernym": lambda s: s.instance_hypernyms(),
    "instance_hyponym": lambda s: s.instance_hyponyms(),
    "meronym_member": lambda s: s.member_meronyms(),
    "meronym_part": lambda s: s.part_meronyms(),
    "meronym_substance": lambda s: s.substance_meronyms(),
    "holonym_member": lambda s: s.member_holonyms(),
    "holonym_part": lambda s: s.part_holonyms(),
    "holonym_substance": lambda s: s.substance_holonyms(),
    "antonym": lambda s: [l.antonyms()[0].synset() for l in s.lemmas() if l.antonyms()],
    "troponym": lambda s: s.hyponyms() if s.pos() == "v" else [],
    "entailment": lambda s: s.entailments(),
    "cause": lambda s: s.causes(),
    "similar_to": lambda s: s.similar_tos(),
    "also_see": lambda s: s.also_sees(),
    "attribute": lambda s: s.attributes(),
    "pertainym": lambda s: [p.synset() for l in s.lemmas() for p in l.pertainyms()],
    "derivationally_related_form": lambda s: [d.synset() for l in s.lemmas() for d in l.derivationally_related_forms()],
    "domain_topic": lambda s: s.topic_domains(),
    "member_topic": lambda s: s.topic_members(),
    "domain_region": lambda s: s.region_domains(),
    "member_region": lambda s: s.region_members(),
    "domain_usage": lambda s: s.usage_domains(),
    "member_usage": lambda s: s.usage_members(),
}

# Pillars: 12 groups covering all WordNet semantic relations
PILLAR_MAP = {
    "taxonomy": [
        "hypernym",
        "hyponym",
        "instance_hypernym",
        "instance_hyponym",
    ],
    "meronym": ["meronym_member", "meronym_part", "meronym_substance"],
    "holonym": ["holonym_member", "holonym_part", "holonym_substance"],
    "opposition": ["antonym"],
    "troponym": ["troponym"],
    "entailment": ["entailment"],
    "cause": ["cause"],
    "similarity": ["similar_to", "also_see"],
    "attribute": ["attribute"],
    "pertainym": ["pertainym"],
    "derivational": ["derivationally_related_form"],
    "domains": [
        "domain_topic",
        "member_topic",
        "domain_region",
        "member_region",
        "domain_usage",
        "member_usage",
    ],
}

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _synset_id(s) -> str:
    return f"{s.offset():08d}-{s.pos()}"


def _pick_lemma(s) -> str:
    # Use first lemma name as a canonical label
    return s.lemma_names()[0] if s.lemma_names() else s.name()


def _iter_relations(limit_per_relation: int | None = None, allowed: set[str] | None = None) -> Iterable[dict]:
    for relation, fn in RELATION_MAP.items():
        if allowed is not None and relation not in allowed:
            continue
        count = 0
        for syn in wn.all_synsets():
            targets = fn(syn)
            for target in targets:
                yield {
                    "head": _pick_lemma(syn),
                    "tail": _pick_lemma(target),
                    "relation": relation,
                    "head_synset": _synset_id(syn),
                    "tail_synset": _synset_id(target),
                }
                count += 1
                if limit_per_relation and count >= limit_per_relation:
                    break
            if limit_per_relation and count >= limit_per_relation:
                break


def build_dataset(output_path: Path, limit_per_relation: int | None, relations: set[str] | None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for row in _iter_relations(limit_per_relation, allowed=relations):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    metadata = {
        "authority": "WordNet",
        "version": getattr(wn, "get_version", lambda: "unknown")(),
        "relations": sorted(relations) if relations else sorted(RELATION_MAP.keys()),
        "pillar": None,
        "limit_per_relation": limit_per_relation,
        "records": count,
        "output": str(output_path),
    }
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    if relations:
        # best-effort pillar inference
        for pillar, rels in PILLAR_MAP.items():
            if set(relations).issubset(set(rels)):
                metadata["pillar"] = pillar
                break
    if output_path.exists():
        metadata["sha256"] = _sha256_file(output_path)
        # verify non-empty
        if metadata["records"] == 0:
            raise RuntimeError("WordNet dump produced zero records; aborting.")
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if metadata["version"] != "3.1":
        print(f"WARNING: WordNet version reported as {metadata['version']} (expected 3.1)")
    print(f"Wrote relations to {output_path} ({count} rows)")
    print(f"Wrote metadata to {meta_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump WordNet semantic relations to JSONL for probing.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/datasets/wordnet_relations.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--limit-per-relation",
        type=int,
        default=None,
        help="Optional limit per relation (omit for full dump; can be very large).",
    )
    parser.add_argument(
        "--pillar",
        choices=sorted(PILLAR_MAP.keys()),
        help="Restrict to a pillar (group of relations).",
    )
    parser.add_argument(
        "--relations",
        help="Comma-separated explicit relations (overrides pillar).",
    )
    parser.add_argument(
        "--list-pillars",
        action="store_true",
        help="List pillar → relations and exit.",
    )
    args = parser.parse_args()
    if args.list-pillars:
        for name, rels in sorted(PILLAR_MAP.items()):
            print(f"{name}: {', '.join(rels)}")
        return
    version = getattr(wn, "get_version", lambda: "unknown")()
    if version != "3.1":
        print(f"WARNING: WordNet version reported as {version}, expected 3.1. Aborting.")
        sys.exit(1)
    relations: set[str] | None = None
    if args.relations:
        relations = {rel.strip() for rel in args.relations.split(",") if rel.strip()}
    elif args.pillar:
        relations = set(PILLAR_MAP[args.pillar])
    build_dataset(args.output, args.limit_per_relation, relations)


if __name__ == "__main__":
    main()
