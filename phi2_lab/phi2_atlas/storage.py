"""Atlas storage helpers."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .schema import (
    AtlasDirection,
    Base,
    ExperimentRecord,
    HeadInfo,
    LayerInfo,
    ModelInfo,
    SemanticCode,
)


class AtlasStorage:
    """Wraps the SQLAlchemy engine/session lifecycle."""

    def __init__(self, path: str | Path) -> None:
        """Create a storage handle backed by a SQLite database file.

        The parent directory is created automatically so callers only need to
        provide a file path. Tables are created on first use via SQLAlchemy's
        metadata helpers.
        """

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.path}")
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    def save_layer_info(
        self,
        model_name: str,
        layer_index: int,
        *,
        summary: str = "",
        model_description: str = "",
    ) -> LayerInfo:
        """Create or update a layer summary entry.

        Parameters
        ----------
        model_name:
            Name of the model the layer belongs to. The model will be
            created automatically if it does not exist yet.
        layer_index:
            Numerical index of the layer to update.
        summary:
            Optional natural language description of the layer.
        model_description:
            Optional description stored on the ``ModelInfo`` row if the
            model needs to be created.
        """

        with self.session() as session:
            model = self._get_or_create_model(session, model_name, model_description)
            layer = (
                session.query(LayerInfo)
                .filter(LayerInfo.model_id == model.id, LayerInfo.index == layer_index)
                .one_or_none()
            )
            if layer is None:
                layer = LayerInfo(model=model, index=layer_index)
                session.add(layer)

            if summary:
                layer.summary = summary

            session.flush()
            session.refresh(layer)
            return layer

    def save_head_info(
        self,
        model_name: str,
        layer_index: int,
        head_index: int,
        *,
        note: str = "",
        importance: dict | None = None,
        behaviors: Sequence[str] | None = None,
        model_description: str = "",
    ) -> HeadInfo:
        """Create or update a head level annotation."""

        with self.session() as session:
            model = self._get_or_create_model(session, model_name, model_description)
            layer = self._get_or_create_layer(session, model, layer_index)
            head = (
                session.query(HeadInfo)
                .filter(HeadInfo.layer_id == layer.id, HeadInfo.index == head_index)
                .one_or_none()
            )
            if head is None:
                head = HeadInfo(layer=layer, index=head_index)
                session.add(head)

            if note:
                head.note = note
            if importance is not None:
                head.importance = dict(importance)
            if behaviors is not None:
                head.behaviors = list(behaviors)

            session.flush()
            session.refresh(head)
            return head

    def save_experiment_record(
        self,
        spec_id: str,
        exp_type: str,
        payload: dict,
        *,
        result_path: str = "",
        key_findings: str = "",
        tags: Iterable[str] | None = None,
    ) -> ExperimentRecord:
        """Insert or update an experiment record.

        Records are keyed by ``spec_id`` and ``type``; subsequent calls will
        update the existing entry while keeping the creation timestamp.
        """

        tag_list = list(tags or [])
        with self.session() as session:
            record = (
                session.query(ExperimentRecord)
                .filter(
                    ExperimentRecord.spec_id == spec_id,
                    ExperimentRecord.type == exp_type,
                )
                .one_or_none()
            )

            if record is None:
                record = ExperimentRecord(
                    spec_id=spec_id,
                    type=exp_type,
                    payload=payload,
                    result_path=result_path,
                    key_findings=key_findings,
                    tags=tag_list,
                )
                session.add(record)
            else:
                if payload:
                    record.payload = payload
                if result_path:
                    record.result_path = result_path
                if key_findings:
                    record.key_findings = key_findings
                if tag_list:
                    record.tags = tag_list

            session.flush()
            session.refresh(record)
            return record

    def save_semantic_code(
        self,
        code: str,
        *,
        title: str,
        summary: str,
        payload: str,
        payload_ref: str = "",
        tags: Iterable[str] | None = None,
    ) -> SemanticCode:
        """Insert or update a semantic code entry."""

        tag_list = list(tags or [])
        with self.session() as session:
            entry = session.query(SemanticCode).filter(SemanticCode.code == code).one_or_none()
            if entry is None:
                entry = SemanticCode(
                    code=code,
                    title=title,
                    summary=summary,
                    payload=payload,
                    payload_ref=payload_ref,
                    tags=tag_list,
                )
                session.add(entry)
            else:
                entry.title = title or entry.title
                entry.summary = summary or entry.summary
                entry.payload = payload or entry.payload
                if payload_ref:
                    entry.payload_ref = payload_ref
                if tag_list:
                    entry.tags = tag_list

            session.flush()
            session.refresh(entry)
            return entry

    def save_direction(
        self,
        *,
        model_name: str,
        name: str,
        layer_index: int | None,
        component: str | None,
        vector: Sequence[float],
        source: str = "",
        score: float | None = None,
        tags: Iterable[str] | None = None,
        model_description: str = "",
    ) -> AtlasDirection:
        """Insert or update a principal direction entry."""

        tag_list = list(tags or [])
        with self.session() as session:
            model = self._get_or_create_model(session, model_name, model_description)
            entry = session.query(AtlasDirection).filter(AtlasDirection.name == name).one_or_none()
            if entry is None:
                entry = AtlasDirection(
                    model=model,
                    name=name,
                    layer_index=layer_index,
                    component=component,
                    vector=list(vector),
                    source=source,
                    score=score,
                    tags=tag_list,
                )
                session.add(entry)
            else:
                entry.layer_index = layer_index
                entry.component = component
                entry.vector = list(vector)
                entry.source = source or entry.source
                entry.score = score if score is not None else entry.score
                if tag_list:
                    entry.tags = tag_list
                if entry.model_id != model.id:
                    entry.model = model
            session.flush()
            session.refresh(entry)
            return entry

    def load_direction(self, name: str) -> AtlasDirection | None:
        with self.session() as session:
            direction = session.query(AtlasDirection).filter(AtlasDirection.name == name).one_or_none()
            if direction is not None:
                session.expunge(direction)
            return direction

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_or_create_model(
        session: Session, name: str, description: str = ""
    ) -> ModelInfo:
        model = session.query(ModelInfo).filter(ModelInfo.name == name).one_or_none()
        if model is None:
            model = ModelInfo(name=name, description=description)
            session.add(model)
            session.flush()
        elif description:
            model.description = description
        return model

    @staticmethod
    def _get_or_create_layer(
        session: Session, model: ModelInfo, layer_index: int
    ) -> LayerInfo:
        layer = (
            session.query(LayerInfo)
            .filter(LayerInfo.model_id == model.id, LayerInfo.index == layer_index)
            .one_or_none()
        )
        if layer is None:
            layer = LayerInfo(model=model, index=layer_index)
            session.add(layer)
            session.flush()
        return layer
