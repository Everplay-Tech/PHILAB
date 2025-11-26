"""Compression / DSL agent stub."""
from __future__ import annotations

from typing import Callable, Optional

from .base_agent import AgentConfig, BaseAgent, ChatMessage


class CompressionAgent(BaseAgent):
    def __init__(
        self,
        *args,
        register_semantic_code: Optional[Callable[[str], str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.register_semantic_code = register_semantic_code
        if register_semantic_code:
            self.register_tool("register_semantic_code", register_semantic_code)

    def refine_code(self, current_summary: str) -> str:
        prompt = f"Refine the semantic codes for: {current_summary}"
        messages = [ChatMessage(role="user", content=prompt)]
        return self.chat(messages, use_context=True, task_spec={"summary": current_summary})

    def persist_semantic_code(self, code_blob: str) -> str:
        if not self.register_semantic_code:
            raise RuntimeError(
                "Semantic code registration callback is not configured for this agent."
            )
        return self.register_semantic_code(code_blob)
