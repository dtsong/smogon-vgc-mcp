"""Base agent class for VGC teambuilding agents."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from vgc_agent.core.events import EventEmitter
from vgc_agent.core.mcp import MCPConnection
from vgc_agent.core.types import TokenUsage


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    system_prompt: str
    tools: list[str]
    model: str = "claude-opus-4-5-20251101"
    max_tokens: int = 4096
    max_tool_calls: int = 20


class BaseAgent(ABC):
    """Base class for all VGC teambuilding agents."""

    def __init__(
        self,
        config: AgentConfig,
        mcp: MCPConnection,
        events: EventEmitter,
        anthropic: Anthropic | None = None,
        token_usage: TokenUsage | None = None,
        budget: float | None = None,
    ):
        self.config = config
        self.mcp = mcp
        self.events = events
        self.anthropic = anthropic or Anthropic()
        self.token_usage = token_usage or TokenUsage()
        self.budget = budget

    @property
    def name(self) -> str:
        return self.config.name

    def _get_tools(self) -> list[dict]:
        return self.mcp.get_anthropic_tools(self.config.tools)

    async def _call_tool(self, name: str, arguments: dict) -> str:
        self.events.agent_tool_call(self.name, name, arguments)
        try:
            result = await self.mcp.call_tool(name, arguments)
            result_str = str(result) if not isinstance(result, str) else result
            summary = result_str[:100] + "..." if len(result_str) > 100 else result_str
            self.events.agent_tool_result(self.name, name, success=True, summary=summary)
            return result_str
        except Exception as e:
            self.events.agent_tool_result(self.name, name, success=False, summary=str(e))
            return f"Error calling {name}: {e}"

    async def run(self, task: str, context: str = "") -> str:
        self.events.agent_thinking(self.name, f"Starting task: {task[:50]}...")
        tools = self._get_tools()
        full_prompt = f"{context}\n\nTask: {task}" if context else task
        messages: list[dict[str, Any]] = [{"role": "user", "content": full_prompt}]
        tool_call_count = 0

        while tool_call_count < self.config.max_tool_calls:
            response = self.anthropic.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=self.config.system_prompt,
                tools=tools,
                messages=messages,
            )
            if response.usage:
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.token_usage.add(input_tokens, output_tokens)
                self.events.token_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_input=self.token_usage.input_tokens,
                    total_output=self.token_usage.output_tokens,
                    cost_usd=self.token_usage.cost_usd,
                    budget=self.budget,
                )
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_call_count += 1
                        result = await self._call_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                final_text = "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
                self.events.agent_response(self.name, final_text)
                return final_text
        return "Error: Maximum tool calls exceeded"

    @abstractmethod
    async def execute(self, state: Any) -> Any:
        pass

    def _extract_json(self, text: str) -> dict | None:
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            return None
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            json_str = text[json_start:json_end].replace(",]", "]").replace(",}", "}")
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return None
