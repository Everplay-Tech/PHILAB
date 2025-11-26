"""SQLAlchemy schema for the Phi-2 Atlas."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ModelInfo(Base):
    __tablename__ = "model_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    layers: Mapped[list["LayerInfo"]] = relationship("LayerInfo", back_populates="model", cascade="all, delete-orphan")
    directions: Mapped[list["AtlasDirection"]] = relationship(
        "AtlasDirection", back_populates="model", cascade="all, delete-orphan"
    )


class LayerInfo(Base):
    __tablename__ = "layer_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("model_info.id"))
    index: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, default="")

    model: Mapped[ModelInfo] = relationship("ModelInfo", back_populates="layers")
    heads: Mapped[list["HeadInfo"]] = relationship("HeadInfo", back_populates="layer", cascade="all, delete-orphan")


class HeadInfo(Base):
    __tablename__ = "head_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    layer_id: Mapped[int] = mapped_column(ForeignKey("layer_info.id"))
    index: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")
    importance: Mapped[dict | None] = mapped_column(JSON, default=dict)
    behaviors: Mapped[list[str]] = mapped_column(JSON, default=list)

    layer: Mapped[LayerInfo] = relationship("LayerInfo", back_populates="heads")


class ExperimentRecord(Base):
    __tablename__ = "experiment_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spec_id: Mapped[str] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    result_path: Mapped[str] = mapped_column(String(512), default="")
    key_findings: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AtlasDirection(Base):
    __tablename__ = "atlas_direction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("model_info.id"))
    name: Mapped[str] = mapped_column(String(256), unique=True)
    layer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    component: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    vector: Mapped[list[float]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(256), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    model: Mapped[ModelInfo] = relationship("ModelInfo", back_populates="directions")


class SemanticCode(Base):
    __tablename__ = "semantic_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(String(512))
    payload_ref: Mapped[str] = mapped_column(String(256), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
