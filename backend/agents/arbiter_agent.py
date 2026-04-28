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
        """
        sys_prompt = self.system_prompt
        if extra_context:
            sys_prompt += f"\n\n{extra_context}"

        messages = [{"role": "system", "content": sys_prompt}]
        
        # Include the entire history for the arbiter
        for msg in conversation_history:
            clean_msg = {k: v for k, v in msg.items() if k in ["role", "content", "name"]}
            messages.append(clean_msg)

        try:
            response = _client.chat.completions.create(
                messages=messages,
                model=MODEL,
                temperature=0.2,    # Low temperature for consistency, slight leeway for reasoning
                max_tokens=250,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content.strip()
            
            # Verify the LLM returned valid JSON format
            json.loads(content)
            return content

        except Exception as e:
            # Fallback to tie if LLM output fails validation
            fallback = {
                "winner": "TIE",
                "reasoning": f"Arbiter error: {str(e)}"
            }
            return json.dumps(fallback)
