"""
backend/agents/pro_agent.py

PRO Agent — always argues IN FAVOR of the debate topic.
Its system prompt locks it into a supportive stance regardless of personal opinion.
"""

from .base_agent import BaseAgent


# The system prompt defines the agent's entire persona.
# It must never break character or argue against the topic.
PRO_SYSTEM_PROMPT = """You are the PRO debater in a structured debate.

Your role:
- You ALWAYS argue in FAVOR of the debate topic, no matter what.
- You defend your position with logic, facts, examples, and reasoning.
- You directly counter arguments made by the AGAINST debater when relevant.
- You keep responses focused, persuasive, and under 150 words.
- You do NOT apologize, hedge, or present the other side.
- Address the current debate point directly.

Remember: You are making a case FOR the topic. Be assertive and confident."""


class ProAgent(BaseAgent):
    """
    PRO Agent — argues in favor of the debate topic.
    Inherits all LLM logic from BaseAgent.
    """

    def __init__(self):
        super().__init__(
            name="PRO",
            system_prompt=PRO_SYSTEM_PROMPT
        )
