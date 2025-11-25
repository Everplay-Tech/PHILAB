# Phi-2 Atlas storage helpers

The Atlas database is SQLite backed and powered by SQLAlchemy models in
`phi2_lab/phi2_atlas/schema.py`.  Agents previously had to open sessions
manually to persist experiment data; the `AtlasStorage` and
`AtlasWriter` APIs wrap that boilerplate and should be used instead of
writing ad-hoc SQL.

## Quick start

```python
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_atlas.writer import AtlasWriter

storage = AtlasStorage(path="/tmp/phi2_atlas.sqlite")
writer = AtlasWriter(storage)

# Describe a layer
writer.write_layer_summary(
    model_name="phi-2",
    layer_index=12,
    summary="Looks like a multilingual dictionary head",
)

# Capture an experiment result
writer.record_experiment_findings(
    spec_id="exp-001",
    exp_type="activation-patching",
    payload={"prompt": "..."},
    key_findings="Patch on layer 12 boosts accuracy by 4%",
    tags=["layer12", "patching"],
)

# Register a semantic code entry
writer.register_semantic_code(
    code="L12-H3",
    title="Layer 12 head 3",
    summary="Fires on bilingual dictionary lookups",
    payload="/artifacts/run42/activations.json",
)
```

## Storage-level helpers

`AtlasStorage` can be used directly when finer control is required.  The
following high-level methods wrap a full SQLAlchemy session lifecycle and
return the ORM objects that were persisted:

- `save_layer_info(model_name, layer_index, summary, model_description="")`
- `save_head_info(model_name, layer_index, head_index, note=..., importance=..., behaviors=...)`
- `save_experiment_record(spec_id, exp_type, payload, result_path=..., key_findings=..., tags=...)`
- `save_semantic_code(code, title=..., summary=..., payload=..., payload_ref=..., tags=...)`

All helper methods are idempotent with respect to their natural primary
keys (e.g. model name + layer index) and will update existing rows rather
than inserting duplicates.

Use these helpers from agents and scripts so new experiments can be
recorded with a single function call instead of hand-written SQL.
