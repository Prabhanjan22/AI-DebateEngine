"""
backend/agents/base_agent.py

Base class for all AI agents in the debate system.
Every agent (PRO, AGAINST, Fact Checker, Arbiter) inherits from this.

Uses the Groq API (OpenAI-compatible interface).
State lives in the DebateEngine, not here — agents are stateless.
"""

import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

# Explicitly load .env from the project root (2 levels up from this file)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# Shared Groq client — created once, reused by all agents
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # fallback model


class BaseAgent:
    """
    Abstract base class for all debate agents.

    Attributes:
        name          (str): Display name (e.g., "PRO", "AGAINST")
        system_prompt (str): Persona/stance locked in via system message
    """

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt

    def generate(self, conversation_history: list[dict], extra_context: str = "", mcp_manager=None) -> str:
        """
        Call the Groq LLM with the full conversation history.
        Does NOT use tools — fast, single-shot generation for debate turns.

        Args:
            conversation_history: List of {"role": ..., "content": ...} dicts.
            extra_context: Optional extra instructions injected before generation.
            mcp_manager: Accepted for API compatibility but NOT used here.
                         Tool-using agents call generate_with_tools() instead.

        Returns:
            The agent's generated response as a plain string.
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        for msg in conversation_history:
            clean_msg = {k: v for k, v in msg.items() if k in ["role", "content"]}
            messages.append(clean_msg)

        if extra_context:
            messages.append({
                "role": "system",
                "content": f"[Additional context for this turn]: {extra_context}"
            })

        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.7,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[{self.name} encountered an error: {str(e)}]"

    def generate_with_tools(self, conversation_history: list[dict], mcp_manager, extra_context: str = "",
                             temperature: float = 0.1, max_tokens: int = 300,
                             response_format: dict = None) -> str:
        """
        Call the Groq LLM with tool support (MCP). Used by FactChecker, Scorer, Arbiter.
        Runs a multi-step tool-call loop (max 3 iterations).

        Returns:
            The final model response as a plain string.
        """
        import json

        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in conversation_history:
            clean_msg = {k: v for k, v in msg.items() if k in ["role", "content", "name", "tool_calls", "tool_call_id"]}
            messages.append(clean_msg)

        if extra_context:
            messages.append({"role": "system", "content": f"[Context]: {extra_context}"})

        kwargs = {
            "model": MODEL,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": mcp_manager.get_tools_schema(),
            "tool_choice": "auto",
        }
        if response_format:
            kwargs["response_format"] = response_format

        MAX_ITERATIONS = 3
        for _ in range(MAX_ITERATIONS):
            try:
                response = _client.chat.completions.create(messages=messages, **kwargs)
                response_message = response.choices[0].message

                if response_message.tool_calls:
                    messages.append(response_message.model_dump(exclude_none=True))
                    for tool_call in response_message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            args = json.loads(tool_call.function.arguments)
                        except Exception:
                            args = {}
                        result = mcp_manager.execute_tool(tool_name, args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": str(result)
                        })
                    continue
                else:
                    return response_message.content.strip()
            except Exception as e:
                return f"[{self.name} error: {str(e)}]"

        return f"[{self.name} error: Tool iteration limit reached]"
