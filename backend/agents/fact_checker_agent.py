"""
backend/agents/fact_checker_agent.py

Fact Checker Agent — evaluates the factual accuracy of the latest argument.
Returns a JSON object with assessment, confidence, and reasoning.
"""

import json
from .base_agent import BaseAgent, _client, MODEL

FACT_CHECKER_SYSTEM_PROMPT = """You are an impartial Fact Checker in a structured debate.

Your role is to analyze the user's or agent's latest argument for factual accuracy.
You do NOT take sides. You only evaluate the objective claims made.

You MUST respond with ONLY a valid JSON object in the following format:
{
  "assessment": "TRUE" | "FALSE" | "MIXED" | "OPINION",
  "confidence": <integer from 0 to 100>,
  "reasoning": "<short explanation of your assessment, citing known facts if applicable, max 50 words>"
}

If the argument is purely an opinion or subjective, classify it as "OPINION".
If the argument contains multiple factual claims and some are true while others are false, classify as "MIXED".
Do NOT include any markdown formatting like ```json in your response, just the raw JSON object.
"""

class FactCheckerAgent(BaseAgent):
    """
    Fact Checker Agent — evaluates arguments for accuracy.
    Overrides generate() to enforce JSON output and low temperature.
    """

    def __init__(self):
        super().__init__(
            name="FACT_CHECKER",
            system_prompt=FACT_CHECKER_SYSTEM_PROMPT
        )

    def generate(self, conversation_history: list[dict], extra_context: str = "", mcp_manager=None) -> str:
        """
        Fast, single-shot fact check on the latest argument.
        Uses LLM knowledge only (no live tool calls) for speed.
        """
        sys_prompt = self.system_prompt
        if extra_context:
            sys_prompt += f"\n\n{extra_context}"
            
        messages = [{"role": "system", "content": sys_prompt}]

        # Only need the last 3 messages for context
        recent_history = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
        for msg in recent_history:
            clean_msg = {k: v for k, v in msg.items() if k in ["role", "content"]}
            messages.append(clean_msg)

        # Attempt 1: json_object mode
        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            json.loads(content)
            return content
        except Exception:
            pass

        # Attempt 2: plain text response with JSON extraction
        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.1,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                parsed = json.loads(json_str)
                result = {
                    "assessment": str(parsed.get("assessment", "OPINION")),
                    "confidence": int(parsed.get("confidence", 50)),
                    "reasoning": str(parsed.get("reasoning", "Fact check completed.")),
                }
                return json.dumps(result)
        except Exception:
            pass

        return json.dumps({
            "assessment": "UNVERIFIED",
            "confidence": 0,
            "reasoning": "Fact check unavailable."
        })
