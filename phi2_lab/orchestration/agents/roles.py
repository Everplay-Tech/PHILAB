"""Structured metadata describing Phi-2 Lab agent roles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class AgentRoleDefinition:
    """Declarative description of a logical agent role."""

    id: str
    label: str
    responsibilities: str
    default_toolchain: Tuple[str, ...]


ROLE_DEFINITIONS: Dict[str, AgentRoleDefinition] = {
    "architecture": AgentRoleDefinition(
        id="architecture",
        label="Architecture",
        responsibilities="Break large goals into layered Phi-2 subsystems and dependency graphs.",
        default_toolchain=("retrieval", "context", "planner"),
    ),
    "experiments": AgentRoleDefinition(
        id="experiments",
        label="Experiments",
        responsibilities="Translate architecture intents into executable experiment plans and metrics.",
        default_toolchain=("retrieval", "spec", "atlas"),
    ),
    "atlas": AgentRoleDefinition(
        id="atlas",
        label="Atlas",
        responsibilities="Maintain the Phi-2 Atlas by summarizing outcomes and decision logs.",
        default_toolchain=("context", "compression"),
    ),
    "compression": AgentRoleDefinition(
        id="compression",
        label="Compression / DSL",
        responsibilities="Refine DSL snippets and compression passes for storing Phi-2 insight.",
        default_toolchain=("dsl", "analysis"),
    ),
    "adapter": AgentRoleDefinition(
        id="adapter",
        label="Adapter Tuning",
        responsibilities="Plan adapter/LoRA tuning cycles and enforce guard-rails for activation lenses.",
        default_toolchain=("lora", "safety"),
    ),
    "orchestration": AgentRoleDefinition(
        id="orchestration",
        label="Orchestration",
        responsibilities="Coordinate role sequencing, exchange signals, and consolidate final recommendations.",
        default_toolchain=("planner", "reporting"),
    ),
}


def get_role_definition(role_id: str) -> AgentRoleDefinition:
    """Return the :class:`AgentRoleDefinition` for *role_id* with validation."""

    try:
        return ROLE_DEFINITIONS[role_id]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown agent role '{role_id}'. Known roles: {sorted(ROLE_DEFINITIONS)}") from exc
