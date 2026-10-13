"""
backend/agents/scoring_agent.py

Scoring Agent — evaluates the quality of the latest argument.
Returns a JSON object with scores for logic, relevance, and persuasiveness.
"""

import json
from .base_agent import BaseAgent, _client, MODEL

SCORING_SYSTEM_PROMPT = """You are an impartial Debate Scoring Engine.

Your role is to evaluate the latest argument made in the debate by scoring it on three dimensions:
- Logic: How well-reasoned and logically sound is the argument? (1-10)
- Relevance: How relevant is the argument to the debate topic and the opponent's points? (1-10)
- Persuasiveness: How compelling and rhetorically effective is the argument? (1-10)

You MUST respond with ONLY a valid JSON object in the following format:
{
  "logic": <integer 1-10>,
  "relevance": <integer 1-10>,
  "persuasiveness": <integer 1-10>,
  "overall": <integer 1-10, calculated as average of the three>,
  "reasoning": "<short explanation of your scores, max 40 words>"
}

Do NOT include any markdown formatting like ```json in your response, just the raw JSON object.
"""

class ScoringAgent(BaseAgent):
    """
    Scoring Agent — evaluates arguments for quality.
    Overrides generate() to enforce JSON output and low temperature.
    """

    def __init__(self):
        super().__init__(
            name="SCORING_ENGINE",
            system_prompt=SCORING_SYSTEM_PROMPT
        )

    def generate(self, conversation_history: list[dict], extra_context: str = "", mcp_manager=None) -> str:
        """
        Call the Groq LLM to score the latest message in the history.
        Uses a two-layer approach: tries json_object mode first, then falls
        back to plain text with manual JSON extraction for compatibility with
        models that do not support the response_format parameter.
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        recent_history = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
        for msg in recent_history:
            clean_msg = {k: v for k, v in msg.items() if k in ["role", "content", "name"]}
            messages.append(clean_msg)

        # Attempt 1: use json_object response format (works on models that support it)
        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.1,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            json.loads(content)  # validate
            return content
        except Exception:
            pass  # fall through to plain-text attempt

        # Attempt 2: plain text response with manual JSON extraction
        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.1,
                max_tokens=300,
            )
            content = response.choices[0].message.content.strip()
            # Try to find the JSON block inside the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                parsed = json.loads(json_str)
                # Normalise: ensure all required keys exist
                result = {
                    "logic": int(parsed.get("logic", 5)),
                    "relevance": int(parsed.get("relevance", 5)),
                    "persuasiveness": int(parsed.get("persuasiveness", 5)),
                    "overall": int(parsed.get("overall", 5)),
                    "reasoning": str(parsed.get("reasoning", "Scored via text extraction.")),
                }
                return json.dumps(result)
        except Exception as e:
            pass

        # Final fallback: return a safe default so the debate never crashes
        fallback = {
            "logic": 5,
            "relevance": 5,
            "persuasiveness": 5,
            "overall": 5,
            "reasoning": "Score unavailable — model did not return parseable JSON."
        }
        return json.dumps(fallback)
