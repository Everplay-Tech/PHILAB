"""Read helpers for the Atlas."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator, List, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .schema import ExperimentRecord, HeadInfo, LayerInfo, ModelInfo, SemanticCode
from .storage import AtlasStorage


@contextmanager
def _as_session(handle: Session | AtlasStorage) -> Iterator[Session]:
    """Resolve *handle* to a SQLAlchemy :class:`Session` context."""

    if isinstance(handle, AtlasStorage):
        with handle.session() as session:
            yield session
    else:
        yield handle


def _json_array_contains(column, value: str):
    """Build a correlated EXISTS clause that asserts ``value`` is in ``column``."""

    column_expr = getattr(column, "expression", column)
    json_each = func.json_each(column_expr).table_valued("key", "value").alias()
    parent_table = column_expr.table
    return (
        select(1)
        .select_from(json_each)
        .where(json_each.c.value == value)
        .correlate(parent_table)
        .exists()
    )


def list_models(handle: Session | AtlasStorage) -> List[ModelInfo]:
    with _as_session(handle) as session:
        stmt = select(ModelInfo)
        return list(session.scalars(stmt))


def list_experiments(handle: Session | AtlasStorage) -> List[ExperimentRecord]:
    with _as_session(handle) as session:
        stmt = select(ExperimentRecord).order_by(ExperimentRecord.created_at.desc())
        return list(session.scalars(stmt))


def search_heads(
    handle: Session | AtlasStorage,
    model_id: int,
    *,
    tag: str | None = None,
    min_importance: float | None = None,
    importance_key: str = "mean",
) -> List[HeadInfo]:
    """Return heads for ``model_id`` filtered by behaviors and importance.

    Parameters
    ----------
    model_id:
        Identifier of the :class:`ModelInfo` entry to search within.
    tag:
        Optional behavior/semantic tag that must be present in the ``behaviors``
        JSON column for the head to match.
    min_importance:
        If provided, the JSON ``importance`` column must contain ``importance_key``
        with a value greater than or equal to this threshold.
    importance_key:
        Key used inside the ``importance`` JSON payload when applying the numeric
        filter. Defaults to ``"mean"`` which is what the aggregation utilities
        emit today.
    """

    with _as_session(handle) as session:
        stmt = (
            select(HeadInfo)
            .join(LayerInfo)
            .where(LayerInfo.model_id == model_id)
            .order_by(LayerInfo.index.asc(), HeadInfo.index.asc())
        )
        if tag:
            stmt = stmt.where(_json_array_contains(HeadInfo.behaviors, tag))
        if min_importance is not None:
            stmt = stmt.where(
                func.coalesce(
                    HeadInfo.importance[importance_key].as_float(),
                    0.0,
                )
                >= float(min_importance)
            )
        return list(session.scalars(stmt))


def find_experiments(
    handle: Session | AtlasStorage,
    *,
    layer_idx: int | None = None,
    tags: Sequence[str] | None = None,
) -> List[ExperimentRecord]:
    """Return experiments filtered by layer indices or semantic tags."""

    with _as_session(handle) as session:
        stmt = select(ExperimentRecord).order_by(ExperimentRecord.created_at.desc())
        if layer_idx is not None:
            stmt = stmt.where(
                ExperimentRecord.payload["layer_idx"].as_integer() == layer_idx
            )
        if tags:
            for tag in tags:
                stmt = stmt.where(_json_array_contains(ExperimentRecord.tags, tag))
        return list(session.scalars(stmt))


def fetch_semantic_codes(
    handle: Session | AtlasStorage, tag_filter: str | Sequence[str] | None = None
) -> List[SemanticCode]:
    """Return semantic codes optionally filtered by one or more tags."""

    with _as_session(handle) as session:
        stmt = select(SemanticCode).order_by(SemanticCode.code)
        if tag_filter:
            tags: Iterable[str]
            if isinstance(tag_filter, str):
                tags = (tag_filter,)
            else:
                tags = tag_filter
            for tag in tags:
                stmt = stmt.where(_json_array_contains(SemanticCode.tags, tag))
        return list(session.scalars(stmt))


# Backwards-compatibility aliases used by CLI scripts.
list_semantic_codes = fetch_semantic_codes
