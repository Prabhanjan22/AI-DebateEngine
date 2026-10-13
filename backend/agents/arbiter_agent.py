"""
backend/agents/arbiter_agent.py

Arbiter Agent — acts as the final judge of the debate.
Reviews the entire debate transcript and declares a winner.
"""

import json
from .base_agent import BaseAgent, _client, MODEL

ARBITER_SYSTEM_PROMPT = """You are the impartial Arbiter of a debate.

Your role is to read the entire transcript of the debate (including the arguments from PRO, AGAINST, and the USER, as well as any fact-checker annotations or scores) and determine the overall winner.

You MUST respond with ONLY a valid JSON object in the following format:
{
  "winner": "PRO" | "AGAINST" | "TIE",
  "reasoning": "<A 2-3 sentence explanation of why this side won, citing their strongest arguments or the opponent's weaknesses>"
}

Do NOT include any markdown formatting like ```json in your response, just the raw JSON object.
"""

class ArbiterAgent(BaseAgent):
    """
    Arbiter Agent — decides the winner of the debate.
    Overrides generate() to enforce JSON output.
    """

    def __init__(self):
        super().__init__(
            name="ARBITER",
            system_prompt=ARBITER_SYSTEM_PROMPT
        )

    def generate(self, conversation_history: list[dict], extra_context: str = "", mcp_manager=None) -> str:
        """
        Call the Groq LLM to evaluate the entire debate history and declare a winner.
        Uses a two-layer approach for model compatibility.
        """
        sys_prompt = self.system_prompt
        if extra_context:
            sys_prompt += f"\n\n{extra_context}"

        messages = [{"role": "system", "content": sys_prompt}]

        for msg in conversation_history:
            clean_msg = {k: v for k, v in msg.items() if k in ["role", "content", "name"]}
            messages.append(clean_msg)

        # Attempt 1: json_object mode
        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.2,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            json.loads(content)  # validate
            return content
        except Exception:
            pass

        # Attempt 2: plain text with JSON extraction
        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.2,
                max_tokens=400,
            )
            content = response.choices[0].message.content.strip()
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                parsed = json.loads(json_str)
                result = {
                    "winner": str(parsed.get("winner", "TIE")),
                    "reasoning": str(parsed.get("reasoning", "No reasoning provided.")),
                }
                return json.dumps(result)
        except Exception:
            pass

        fallback = {
            "winner": "TIE",
            "reasoning": "Arbiter could not produce a verdict — model did not return parseable JSON."
        }
        return json.dumps(fallback)
