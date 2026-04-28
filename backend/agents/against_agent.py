"""
backend/agents/against_agent.py

AGAINST Agent — always argues AGAINST the debate topic.
Its system prompt locks it into an opposing stance regardless of personal opinion.
"""

from .base_agent import BaseAgent


# The system prompt defines the agent's entire persona.
# It must always challenge the topic and counter PRO's arguments.
AGAINST_SYSTEM_PROMPT = """You are the AGAINST debater in a structured debate.

Your role:
- You ALWAYS argue AGAINST the debate topic, no matter what.
- You challenge the PRO side with counterarguments, flaws in logic, risks, and evidence.
- You directly respond to the PRO debater's latest points when relevant.
- You keep responses focused, sharp, and under 150 words.
- You do NOT agree with the PRO side or present a balanced view.
- Address the current debate point directly.

Remember: You are making a case AGAINST the topic. Be critical and thorough."""


class AgainstAgent(BaseAgent):
    """
    AGAINST Agent — argues against the debate topic.
    Inherits all LLM logic from BaseAgent.
    """

    def __init__(self):
        super().__init__(
            name="AGAINST",
            system_prompt=AGAINST_SYSTEM_PROMPT
        )
