"""Concurrent runner that coordinates logical Phi-2 agents."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from ..phi2_core.adapter_manager import AdapterManager
from ..phi2_agents.base_agent import AgentConfig, BaseAgent, ChatMessage
from ..phi2_atlas.storage import AtlasStorage
from ..phi2_context.codebook import SemanticCodebook
from ..phi2_context.compressor import Compressor
from ..phi2_context.context_builder import ContextBuilder
from ..phi2_context.retriever import SimpleRetriever
from ..phi2_core.config import AppConfig, load_app_config
from ..phi2_core.model_manager import Phi2ModelManager
from ..utils import load_yaml_data
from .agents import AgentRoleDefinition, ROLE_DEFINITIONS, get_role_definition


@dataclass
class AgentResult:
    """Container describing the output of a logical agent invocation."""

    role_id: str
    content: str
    prompt: str
    toolchain: Sequence[str]


class _LogicalAgent:
    """Runtime wrapper that binds a BaseAgent with orchestration metadata."""

    def __init__(
        self,
        role: AgentRoleDefinition,
        agent: BaseAgent,
        task_template: str,
        toolchain: Sequence[str],
        use_context: bool,
    ) -> None:
        self.role = role
        self.agent = agent
        self.task_template = task_template
        self.toolchain = tuple(toolchain)
        self.use_context = use_context

    async def run(self, goal: str, payload: Optional[Mapping[str, str]] = None) -> AgentResult:
        formatted_prompt = self._render_prompt(goal, payload)

        def _invoke() -> str:
            task_spec: MutableMapping[str, str] = {"goal": goal, "role": self.role.id}
            if payload:
                task_spec.update(payload)
            messages = [ChatMessage(role="user", content=formatted_prompt)]
            return self.agent.chat(messages, use_context=self.use_context, task_spec=dict(task_spec))

        content = await asyncio.to_thread(_invoke)
        return AgentResult(
            role_id=self.role.id,
            content=content,
            prompt=formatted_prompt,
            toolchain=self.toolchain,
        )

    def _render_prompt(self, goal: str, payload: Optional[Mapping[str, str]]) -> str:
        variables: Dict[str, str] = {"goal": goal}
        if payload:
            variables.update(payload)
        try:
            return self.task_template.format(**variables)
        except KeyError as exc:  # pragma: no cover - template validation
            missing = str(exc).strip("'")
            raise KeyError(f"Missing template value for '{missing}' in role '{self.role.id}'.") from exc


class OrchestrationRunner:
    """Entry point that wires logical agents to a shared Phi-2 backbone."""

    def __init__(
        self,
        root: Optional[Path] = None,
        agent_cfg_path: Optional[Path] = None,
    ) -> None:
        self.root = root or Path(__file__).resolve().parents[1]
        self.app_cfg: AppConfig = load_app_config(self.root / "config" / "app.yaml")
        self.model_manager = Phi2ModelManager.get_instance(self.app_cfg.model)
        atlas_path = self.app_cfg.atlas.resolve_path(self.root)
        atlas_path.parent.mkdir(parents=True, exist_ok=True)
        self.atlas_storage = AtlasStorage(path=atlas_path)
        codebook = SemanticCodebook(
            self.atlas_storage,
            config_path=self.root / "config" / "codebook.yaml",
        )
        retriever = SimpleRetriever(self.atlas_storage, codebook)
        compressor = Compressor(codebook)
        self.context_builder = ContextBuilder(retriever, compressor)
        self.agent_cfg_path = self._resolve_agent_cfg(agent_cfg_path)
        self.adapter_manager = self._build_adapter_manager()
        self.agents: Dict[str, _LogicalAgent] = self._build_agents()

    # ------------------------------------------------------------------
    # Public APIs
    # ------------------------------------------------------------------
    def list_roles(self) -> List[str]:
        return list(self.agents.keys())

    def list_lenses(self) -> List[str]:
        return sorted(self.adapter_manager.adapters.keys())

    def activate_lenses(self, lens_ids: Iterable[str]) -> None:
        self.adapter_manager.activate(lens_ids)

    def clear_lenses(self) -> None:
        self.adapter_manager.deactivate_all()

    def get_active_lenses(self) -> List[str]:
        return [cfg.id for cfg in self.adapter_manager.get_active_configs()]

    def describe_agents(self) -> str:
        lines = ["Configured Phi-2 agents:"]
        for role_id, logical_agent in self.agents.items():
            lines.append(f"- {role_id}: {logical_agent.role.responsibilities}")
        return "\n".join(lines)

    def run(
        self,
        goal: str,
        payload: Optional[Mapping[str, str]] = None,
        roles: Optional[Iterable[str]] = None,
        lenses: Optional[Iterable[str]] = None,
        clear_lenses: bool = False,
    ) -> Dict[str, AgentResult]:
        """Synchronously execute selected roles by delegating to :meth:`run_async`."""

        return asyncio.run(
            self.run_async(
                goal,
                payload=payload,
                roles=roles,
                lenses=lenses,
                clear_lenses=clear_lenses,
            )
        )

    async def run_async(
        self,
        goal: str,
        payload: Optional[Mapping[str, str]] = None,
        roles: Optional[Iterable[str]] = None,
        lenses: Optional[Iterable[str]] = None,
        clear_lenses: bool = False,
    ) -> Dict[str, AgentResult]:
        available = set(self.agents.keys())
        if roles:
            selected = set(roles)
            missing = selected - available
            if missing:
                raise KeyError(f"Unknown roles requested: {sorted(missing)}")
        else:
            selected = available
        self._apply_lens_selection(lenses, clear_lenses)
        tasks = [
            logical_agent.run(goal, payload)
            for role_id, logical_agent in self.agents.items()
            if role_id in selected
        ]
        results = await asyncio.gather(*tasks)
        return {result.role_id: result for result in results}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_agents(self) -> Dict[str, _LogicalAgent]:
        specs = self._load_agent_specs()
        agents: Dict[str, _LogicalAgent] = {}
        for role_id, payload in specs.items():
            role_def = get_role_definition(role_id)
            agent = BaseAgent(
                config=self._build_agent_config(role_id, payload, role_def),
                model_manager=self.model_manager,
                context_builder=self.context_builder,
                adapter_manager=self.adapter_manager,
            )
            logical_agent = _LogicalAgent(
                role=role_def,
                agent=agent,
                task_template=self._resolve_task_template(role_def, payload),
                toolchain=self._resolve_toolchain(role_def, payload),
                use_context=self._uses_context(payload),
            )
            agents[role_id] = logical_agent
        missing_roles = set(ROLE_DEFINITIONS) - set(agents)
        if missing_roles:
            raise ValueError(
                "Agent configuration is missing role entries: "
                + ", ".join(sorted(missing_roles))
            )
        return agents

    def _load_agent_specs(self) -> Dict[str, dict]:
        data = load_yaml_data(self.agent_cfg_path) or {}
        raw_specs = data.get("agents", {})
        if not isinstance(raw_specs, dict):
            raise ValueError(f"Expected 'agents' mapping in {self.agent_cfg_path}.")
        return raw_specs

    def _build_adapter_manager(self) -> AdapterManager:
        lens_cfg_path = self._resolve_lens_cfg()
        lens_specs = self._load_lens_specs(lens_cfg_path)
        resources = self.model_manager.load()
        model = resources.model
        if model is None:
            raise RuntimeError("Phi-2 model resources are unavailable.")
        return AdapterManager.from_config(model, lens_specs)

    def _build_agent_config(
        self,
        role_id: str,
        payload: Mapping[str, object],
        role_def: AgentRoleDefinition,
    ) -> AgentConfig:
        try:
            system_prompt = payload["system_prompt"]
        except KeyError as exc:
            raise KeyError(f"Missing 'system_prompt' for role '{role_id}' in {self.agent_cfg_path}.") from exc
        description = payload.get("description") or role_def.responsibilities
        default_lenses = payload.get("default_lenses", [])
        if not isinstance(default_lenses, list):
            raise TypeError(f"'default_lenses' must be a list for role '{role_id}'.")
        tools = payload.get("tools")
        if tools is not None and not isinstance(tools, Mapping):
            raise TypeError(f"'tools' must be a mapping for role '{role_id}'.")
        return AgentConfig(
            id=str(payload.get("id", role_id)),
            role=str(payload.get("role", role_def.label)),
            description=str(description),
            system_prompt=str(system_prompt),
            default_lenses=[str(lens) for lens in default_lenses],
            tools=tools if tools is None else dict(tools),
        )

    @staticmethod
    def _resolve_task_template(role_def: AgentRoleDefinition, payload: Mapping[str, object]) -> str:
        template = payload.get("task_template")
        if template:
            return str(template)
        return (
            "{goal}\n\n"
            f"Role: {role_def.label}\n"
            "Respond with structured reasoning and actionable next steps."
        )

    @staticmethod
    def _resolve_toolchain(role_def: AgentRoleDefinition, payload: Mapping[str, object]) -> Sequence[str]:
        configured = payload.get("toolchain")
        if configured is None:
            return role_def.default_toolchain
        if isinstance(configured, Sequence) and not isinstance(configured, (str, bytes)):
            return tuple(str(item) for item in configured)
        raise TypeError(f"'toolchain' must be a sequence for role '{role_def.id}'.")

    @staticmethod
    def _uses_context(payload: Mapping[str, object]) -> bool:
        if "use_context" in payload:
            return bool(payload["use_context"])
        toolchain = payload.get("toolchain")
        if isinstance(toolchain, Sequence) and not isinstance(toolchain, (str, bytes)):
            lowered = {str(item).lower() for item in toolchain}
            return any(token in lowered for token in {"context", "retrieval"})
        return False

    def _resolve_agent_cfg(self, override: Optional[Path]) -> Path:
        if override:
            return Path(override)
        candidates = [
            self.root.parent / "configs" / "agents.yaml",
            self.root / "configs" / "agents.yaml",
            self.root / "config" / "agents.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError("Unable to locate agents.yaml in configs/ or config/ directories.")

    def _resolve_lens_cfg(self) -> Path:
        candidates = [
            self.root.parent / "configs" / "lenses.yaml",
            self.root / "configs" / "lenses.yaml",
            self.root / "config" / "lenses.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError("Unable to locate lenses.yaml in configs/ or config/ directories.")

    def _load_lens_specs(self, path: Path) -> Dict[str, dict]:
        data = load_yaml_data(path) or {}
        raw_lenses = data.get("lenses", {})
        if not isinstance(raw_lenses, dict):
            raise ValueError(f"Expected 'lenses' mapping in {path}.")
        return raw_lenses

    def _apply_lens_selection(
        self,
        lenses: Optional[Iterable[str]],
        clear_lenses: bool,
    ) -> None:
        if lenses is not None and clear_lenses:
            raise ValueError("Cannot activate and clear lenses simultaneously.")
        if clear_lenses:
            self.clear_lenses()
        elif lenses is not None:
            self.activate_lenses(lenses)


__all__ = ["AgentResult", "OrchestrationRunner"]
