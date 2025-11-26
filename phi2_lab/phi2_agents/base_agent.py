"""Base agent implementation wrapping Phi-2 generation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from ..phi2_context.context_builder import ContextBuilder
from ..phi2_core.adapter_manager import AdapterManager
from ..phi2_core.model_manager import Phi2ModelManager


@dataclass
class AgentConfig:
    id: str
    role: str
    description: str
    system_prompt: str
    default_lenses: List[str] = field(default_factory=list)
    tools: Mapping[str, Callable[..., Any]] | None = None


@dataclass
class ChatMessage:
    role: str
    content: str


class BaseAgent:
    """Thin agent wrapper around the shared Phi-2 model."""

    def __init__(
        self,
        config: AgentConfig,
        model_manager: Phi2ModelManager,
        context_builder: Optional[ContextBuilder] = None,
        adapter_manager: Optional[AdapterManager] = None,
    ) -> None:
        self.config = config
        self.model_manager = model_manager
        self.context_builder = context_builder
        self.adapter_manager = adapter_manager
        self.tools: Dict[str, Callable[..., Any]] = dict(config.tools or {})

    def chat(
        self,
        messages: Sequence[ChatMessage],
        use_context: bool = False,
        task_spec: Optional[Dict[str, str]] = None,
    ) -> str:
        if use_context and self.context_builder:
            context_block = self.context_builder.build_context(task_spec)
        else:
            context_block = None
        prompt = self._format_chat_prompt(messages, context_block)
        if self.adapter_manager and self.config.default_lenses:
            with self.adapter_manager.activation_scope(self.config.default_lenses):
                return self.model_manager.generate(prompt)
        return self.model_manager.generate(prompt)

    def _format_chat_prompt(self, messages: Sequence[ChatMessage], context_block: Optional[str]) -> str:
        lines: List[str] = [f"Role: {self.config.role}", f"Agent ID: {self.config.id}", "", self.config.system_prompt.strip(), ""]
        if context_block:
            lines.extend([context_block.strip(), ""])
        for message in messages:
            role = message.role.capitalize()
            lines.append(f"{role}: {message.content.strip()}")
        lines.append("Assistant:")
        return "\n".join(lines)

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        """Register a callable *func* under *name* for tool dispatch."""

        self.tools[name] = func

    def call_tool(self, name: str, *args: object, **kwargs: object) -> Any:
        """Invoke a registered tool by *name* with the provided arguments."""

        try:
            tool = self.tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool '{name}' is not registered for agent '{self.config.id}'.") from exc
        return tool(*args, **kwargs)

    def describe(self) -> str:
        return f"{self.config.id}: {self.config.description}"
