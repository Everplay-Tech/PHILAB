import os

import pytest

from phi2_lab.auth.api_keys import check_model_access, ModelAccessDenied, get_allowed_models
from phi2_lab.geometry_viz import mock_data, telemetry_store
from phi2_lab.phi2_experiments.spec import ExperimentSpec
from phi2_lab.phi2_experiments.datasets import load_dataset, load_dataset_with_limit
from phi2_lab.resources import wordnet_relations


def test_open_access_model_allows_without_key():
    assert check_model_access("microsoft/phi-2", api_key=None, raise_on_denied=True) is True
    allowed = get_allowed_models(None)
    assert "microsoft/phi-2" in {m.lower() for m in allowed}


def test_restricted_model_requires_key():
    with pytest.raises(ModelAccessDenied):
        check_model_access("microsoft/phi-3-mini-4k-instruct", api_key=None, raise_on_denied=True)


def test_mock_run_round_trip(tmp_path):
    run = mock_data.generate_mock_run(run_id="demo_test_run")
    path = telemetry_store.save_run_summary(run, root=tmp_path)
    assert path.exists()

    loaded = telemetry_store.load_run_summary(run_id="demo_test_run", root=tmp_path)
    assert loaded.run_id == run.run_id
    assert len(loaded.layers) == len(run.layers)

    index = telemetry_store.list_runs(root=tmp_path)
    assert any(entry.run_id == run.run_id for entry in index.runs)


def test_epistemology_spec_and_dataset():
    spec = ExperimentSpec.from_yaml("phi2_lab/config/experiments/epistemology_probe.yaml")
    assert spec.dataset.name == "epistemology_true_false"
    records = load_dataset(spec.dataset)
    assert len(records) >= 5
    limited = load_dataset_with_limit(spec.dataset, max_records=2)
    assert len(limited) == 2


def test_wordnet_relations_resource():
    assert wordnet_relations["authority"] == "WordNet"
    assert wordnet_relations["version"] == "3.1"
    pointers = wordnet_relations["pointers"]
    assert "@" in pointers and pointers["@"] == "hypernym"
    assert "%p" in pointers and pointers["%p"] == "meronym_part"
    relations = wordnet_relations["semantic_relations"]
    assert "taxonomy" in relations and "part_whole" in relations


def test_semantic_specs_load():
    full_spec = ExperimentSpec.from_yaml("phi2_lab/config/experiments/semantic_relations_probe.yaml")
    sanity_spec = ExperimentSpec.from_yaml("phi2_lab/config/experiments/semantic_relations_sanity.yaml")
    assert full_spec.dataset.path.endswith("wordnet_relations.jsonl")
    assert sanity_spec.dataset.path.endswith("wordnet_relations_sanity.jsonl")
