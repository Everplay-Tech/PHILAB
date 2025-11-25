"""AI Provider Service: Factory for creating and managing Phi-2 agents.

This service centralizes agent instantiation and dependency injection,
eliminating duplicated initialization code across scripts and providing
a clean, configuration-driven API for agent creation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..phi2_atlas.storage import AtlasStorage
from ..phi2_atlas.writer import AtlasWriter
from ..phi2_context.context_builder import ContextBuilder
from ..phi2_core.adapter_manager import AdapterManager
from ..phi2_core.config import AppConfig
from ..phi2_core.model_manager import Phi2ModelManager
from ..phi2_experiments.runner import ExperimentRunner
from ..utils import load_yaml_data
from .adapter_agent import AdapterAgent
from .architect_agent import ArchitectAgent
from .atlas_agent import AtlasAgent
from .base_agent import AgentConfig, BaseAgent
from .compression_agent import CompressionAgent
from .experiment_agent import ExperimentAgent


class AIProviderService:
    """Factory service for creating and managing Phi-2 AI agents.

    This service provides a centralized way to:
    - Load agent configurations from YAML
    - Create agents with proper dependency injection
    - Manage shared resources (model manager, atlas writer, etc.)
    - Provide a clean API for scripts to request agents by role/ID

    Example usage:
        >>> app_config = load_app_config("config/app.yaml")
        >>> provider = AIProviderService(app_config, "config/agents.yaml")
        >>>
        >>> # Get specific agents
        >>> architect = provider.get_agent("architect")
        >>> experimenter = provider.get_agent_by_role("experiment_runner")
        >>>
        >>> # Or build all at once
        >>> all_agents = provider.build_all_agents()
    """

    def __init__(
        self,
        app_config: AppConfig,
        agents_config_path: str | Path,
        repo_root: Optional[Path] = None,
        context_builder: Optional[ContextBuilder] = None,
        adapter_manager: Optional[AdapterManager] = None,
    ) -> None:
        """Initialize the AI Provider Service.

        Args:
            app_config: Application configuration (model, atlas, etc.)
            agents_config_path: Path to agents.yaml configuration file
            repo_root: Repository root directory (for resolving paths)
            context_builder: Optional shared context builder for all agents
            adapter_manager: Optional shared adapter manager for all agents
        """
        self.app_config = app_config
        self.agents_config_path = Path(agents_config_path)
        self.repo_root = repo_root or Path.cwd()

        # Load agent configurations
        self.agent_configs = self._load_agent_configs()

        # Initialize shared resources
        self.model_manager = Phi2ModelManager.get_instance(app_config.model)

        # Initialize Atlas storage and writer
        atlas_path = app_config.atlas.resolve_path(self.repo_root)
        self.atlas_storage = AtlasStorage(atlas_path)
        self.atlas_writer = AtlasWriter(self.atlas_storage)

        # Optional shared dependencies
        self.context_builder = context_builder
        self.adapter_manager = adapter_manager

        # Cache for agent instances
        self._agent_cache: Dict[str, BaseAgent] = {}

        # Role to agent ID mapping (for get_agent_by_role)
        self._role_to_id: Dict[str, str] = {
            cfg.role: agent_id for agent_id, cfg in self.agent_configs.items()
        }

    def _load_agent_configs(self) -> Dict[str, AgentConfig]:
        """Load agent configurations from YAML file.

        Returns:
            Dictionary mapping agent IDs to AgentConfig instances
        """
        data = load_yaml_data(self.agents_config_path) or {}
        raw_agents = data.get("agents", {}) if isinstance(data, dict) else {}

        configs: Dict[str, AgentConfig] = {}
        for agent_id, payload in raw_agents.items():
            if not isinstance(payload, dict):
                continue

            merged = {
                "id": payload.get("id", agent_id),
                "role": payload.get("role", agent_id),
                "description": payload.get("description", ""),
                "system_prompt": payload.get(
                    "system_prompt",
                    "You are a Phi-2 agent providing concise, actionable outputs.",
                ),
                "default_lenses": payload.get("default_lenses", []) or [],
                "tools": payload.get("tools"),
            }
            configs[agent_id] = AgentConfig(**merged)

        return configs

    def get_agent(self, agent_id: str, use_cache: bool = True) -> BaseAgent:
        """Get or create an agent by its ID.

        Args:
            agent_id: The unique identifier for the agent (e.g., "architect", "atlas")
            use_cache: Whether to return cached instance if available

        Returns:
            Fully initialized agent instance

        Raises:
            KeyError: If agent_id is not found in configuration
        """
        if use_cache and agent_id in self._agent_cache:
            return self._agent_cache[agent_id]

        if agent_id not in self.agent_configs:
            available = ", ".join(self.agent_configs.keys())
            raise KeyError(
                f"Agent '{agent_id}' not found in configuration. "
                f"Available agents: {available}"
            )

        agent = self._create_agent(agent_id)

        if use_cache:
            self._agent_cache[agent_id] = agent

        return agent

    def get_agent_by_role(self, role: str, use_cache: bool = True) -> BaseAgent:
        """Get or create an agent by its role.

        Args:
            role: The agent's role (e.g., "experiment_runner", "atlas_writer")
            use_cache: Whether to return cached instance if available

        Returns:
            Fully initialized agent instance

        Raises:
            KeyError: If role is not found in configuration
        """
        if role not in self._role_to_id:
            available = ", ".join(self._role_to_id.keys())
            raise KeyError(
                f"No agent found with role '{role}'. "
                f"Available roles: {available}"
            )

        agent_id = self._role_to_id[role]
        return self.get_agent(agent_id, use_cache=use_cache)

    def build_all_agents(self) -> Dict[str, BaseAgent]:
        """Build all configured agents at once.

        Returns:
            Dictionary mapping agent IDs to fully initialized agent instances
        """
        return {
            agent_id: self.get_agent(agent_id, use_cache=True)
            for agent_id in self.agent_configs.keys()
        }

    def _create_agent(self, agent_id: str) -> BaseAgent:
        """Create an agent instance with proper dependencies.

        This method implements the factory logic, mapping agent IDs to
        their specific implementations and injecting the required dependencies.

        Args:
            agent_id: The agent ID to create

        Returns:
            Fully initialized agent instance
        """
        config = self.agent_configs[agent_id]

        # Map agent IDs to their specialized implementations
        # Each agent type may require different dependencies

        if agent_id == "architect":
            return ArchitectAgent(
                config=config,
                model_manager=self.model_manager,
                context_builder=self.context_builder,
                adapter_manager=self.adapter_manager,
            )

        elif agent_id == "experiment":
            return ExperimentAgent(
                config=config,
                model_manager=self.model_manager,
                context_builder=self.context_builder,
                adapter_manager=self.adapter_manager,
            )

        elif agent_id == "atlas":
            # Atlas agent requires special atlas_writer dependency
            agent = AtlasAgent(
                config=config,
                model_manager=self.model_manager,
                atlas_writer=self.atlas_writer,
                context_builder=self.context_builder,
                adapter_manager=self.adapter_manager,
            )
            return agent

        elif agent_id == "compression":
            # Compression agent requires a semantic code registration callback
            def register_semantic_code(code_blob: str) -> str:
                """Register a semantic code in the Atlas."""
                result = self.atlas_writer.register_semantic_code(
                    code="§AUTO",
                    title="Auto semantic code",
                    summary=code_blob[:120],
                    payload=code_blob,
                )
                return result.code

            agent = CompressionAgent(
                config=config,
                model_manager=self.model_manager,
                register_semantic_code=register_semantic_code,
                context_builder=self.context_builder,
                adapter_manager=self.adapter_manager,
            )
            return agent

        elif agent_id == "adapter":
            return AdapterAgent(
                config=config,
                model_manager=self.model_manager,
                context_builder=self.context_builder,
                adapter_manager=self.adapter_manager,
            )

        else:
            # For any other agents, use the base agent implementation
            return BaseAgent(
                config=config,
                model_manager=self.model_manager,
                context_builder=self.context_builder,
                adapter_manager=self.adapter_manager,
            )

    def get_experiment_runner(self) -> ExperimentRunner:
        """Get an ExperimentRunner instance with atlas writer integration.

        Returns:
            Configured ExperimentRunner instance
        """
        return ExperimentRunner(
            model_manager=self.model_manager,
            atlas_writer=self.atlas_writer,
        )

    def clear_cache(self) -> None:
        """Clear the agent instance cache.

        Use this if you need to force recreation of agents with updated configurations.
        """
        self._agent_cache.clear()

    def list_available_agents(self) -> Dict[str, str]:
        """List all available agents with their descriptions.

        Returns:
            Dictionary mapping agent IDs to their descriptions
        """
        return {
            agent_id: config.description
            for agent_id, config in self.agent_configs.items()
        }

    def list_available_roles(self) -> Dict[str, str]:
        """List all available roles with their agent IDs.

        Returns:
            Dictionary mapping roles to agent IDs
        """
        return dict(self._role_to_id)
