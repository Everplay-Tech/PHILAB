"""Adapter agent stub."""
from __future__ import annotations

from typing import Callable, Optional

from .base_agent import AgentConfig, BaseAgent, ChatMessage


class AdapterAgent(BaseAgent):
    def __init__(
        self,
        *args,
        tuning_planner: Optional[Callable[[str], str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tuning_planner = tuning_planner
        if tuning_planner:
            self.register_tool("tuning_planner", tuning_planner)

    def plan_tuning(self, target: str) -> str:
        if self.tuning_planner:
            return self.tuning_planner(target)
        prompt = f"Draft an adapter tuning plan for {target}. Include stop conditions."
        messages = [ChatMessage(role="user", content=prompt)]
        return self.chat(messages, use_context=False)
