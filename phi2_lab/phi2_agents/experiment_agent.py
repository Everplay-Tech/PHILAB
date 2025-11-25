"""Experiment agent implementation."""
from __future__ import annotations

from typing import Callable, Optional

from .base_agent import AgentConfig, BaseAgent, ChatMessage


class ExperimentAgent(BaseAgent):
    def __init__(
        self,
        *args,
        run_experiment: Optional[Callable[[str], str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.run_experiment = run_experiment
        if run_experiment:
            self.register_tool("run_experiment", run_experiment)

    def propose_spec(self, plan_summary: str) -> str:
        prompt = (
            "Convert the following plan into a YAML head_ablation ExperimentSpec.\n" + plan_summary
        )
        messages = [ChatMessage(role="user", content=prompt)]
        task_spec = {"plan": plan_summary, "tags": ["experiments", "head_ablation"]}
        return self.chat(messages, use_context=True, task_spec=task_spec)

    def execute_experiment(self, spec_yaml: str) -> str:
        if not self.run_experiment:
            raise RuntimeError("Run experiment callback is not configured for this agent.")
        return self.run_experiment(spec_yaml)


def build(config: AgentConfig, **kwargs) -> ExperimentAgent:
    return ExperimentAgent(config=config, **kwargs)
