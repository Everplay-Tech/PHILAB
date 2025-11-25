"""Architect agent implementation."""
from __future__ import annotations

from .base_agent import AgentConfig, BaseAgent, ChatMessage


class ArchitectAgent(BaseAgent):
    def propose_plan(self, goal: str) -> str:
        prompt = f"Design a phased plan for: {goal}"
        messages = [ChatMessage(role="user", content=prompt)]
        task_spec = {"goal": goal, "tags": ["architecture", "planning", "atlas"]}
        return self.chat(messages, use_context=True, task_spec=task_spec)


def build(config: AgentConfig, **kwargs) -> ArchitectAgent:
    return ArchitectAgent(config=config, **kwargs)
