"""
backend/memory/memory_manager.py

Persistent memory for each debate session.

Responsibilities:
- Track each agent's own arguments (for self-awareness / no repetition)
- Track opponent's arguments (for counter-argument generation)
- Maintain a rolling summary of the debate so far (sent to agents as context)
- Expose a get_context() method that returns a formatted reminder string
  which is injected into the agent's `extra_context` param each turn.

Memory is stored per debate_id, per speaker.
"""

from dataclasses import dataclass, field
from typing import Optional


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class AgentMemory:
    """Memory store for a single agent (PRO or AGAINST) in one debate session."""
    name: str
    own_arguments: list[str] = field(default_factory=list)
    opponent_arguments: list[str] = field(default_factory=list)

    def record_own(self, argument: str):
        """Record an argument this agent just made."""
        self.own_arguments.append(argument)

    def record_opponent(self, argument: str):
        """Record an argument the opposing agent just made."""
        self.opponent_arguments.append(argument)

    def get_summary(self, max_items: int = 3) -> str:
        """
        Build a short memory summary to inject before generation.
        Limits to the last `max_items` entries to avoid bloating the prompt.
        """
        lines = []

        if self.own_arguments:
            recent_own = self.own_arguments[-max_items:]
            lines.append(f"Your previous arguments ({len(self.own_arguments)} total, showing last {len(recent_own)}):")
            for i, arg in enumerate(recent_own, 1):
                lines.append(f"  {i}. {arg[:200]}{'...' if len(arg) > 200 else ''}")

        if self.opponent_arguments:
            recent_opp = self.opponent_arguments[-max_items:]
            lines.append(f"\nOpponent's recent arguments (last {len(recent_opp)}):")
            for i, arg in enumerate(recent_opp, 1):
                lines.append(f"  {i}. {arg[:200]}{'...' if len(arg) > 200 else ''}")

        return "\n".join(lines) if lines else ""


@dataclass
class DebateMemory:
    """
    Full memory context for one debate session.
    Contains per-agent memory plus a rolling debate summary.
    """
    debate_id: str
    topic: str
    # Per-agent memory keyed by agent name ("PRO", "AGAINST")
    agents: dict[str, AgentMemory] = field(default_factory=dict)
    # Running list of (round, speaker, short_summary) for the moderator view
    turn_log: list[dict] = field(default_factory=list)
    # Auto-incremented turn counter
    turn_count: int = 0

    def _ensure_agent(self, name: str):
        """Lazily create an AgentMemory for a new agent name."""
        if name not in self.agents:
            self.agents[name] = AgentMemory(name=name)

    def record_turn(self, speaker: str, content: str, round_num: int):
        """
        Record a completed turn into memory.
        Updates both the speaker's own_arguments and the opponent's opponent_arguments.
        """
        self.turn_count += 1
        self._ensure_agent(speaker)

        # Store in speaker's own memory
        self.agents[speaker].record_own(content)

        # Store as opponent memory for all OTHER AI agents
        for name, mem in self.agents.items():
            if name != speaker and name != "USER":
                mem.record_opponent(content)

        # USER turns go to both AI agents as "opponent" context
        if speaker == "USER":
            for name in ["PRO", "AGAINST"]:
                self._ensure_agent(name)
                self.agents[name].record_opponent(f"[USER]: {content}")

        # Log for the moderator/memory endpoint
        self.turn_log.append({
            "turn": self.turn_count,
            "round": round_num,
            "speaker": speaker,
            "summary": content[:150] + ("..." if len(content) > 150 else ""),
        })

    def get_context_for(self, speaker: str) -> str:
        """
        Build a context string to inject before an agent generates their response.
        Returns empty string for the USER (they don't need injected memory).
        """
        if speaker == "USER":
            return ""

        self._ensure_agent(speaker)
        mem = self.agents[speaker]

        summary = mem.get_summary(max_items=3)
        if not summary:
            return ""

        return (
            f"=== YOUR MEMORY ===\n"
            f"Use this to avoid repeating yourself and to address opponent's points:\n\n"
            f"{summary}\n"
            f"==================\n"
            f"IMPORTANT: Do NOT repeat arguments you've already made. Build on them or introduce new angles."
        )

    def get_full_log(self) -> list[dict]:
        """Return the full turn log (for the /memory endpoint)."""
        return self.turn_log


# ── Manager Singleton ────────────────────────────────────────────────────────

class MemoryManager:
    """
    Manages DebateMemory objects for all active debate sessions.
    One MemoryManager instance lives inside the DebateEngine.
    """

    def __init__(self):
        self._sessions: dict[str, DebateMemory] = {}

    def create_session(self, debate_id: str, topic: str) -> DebateMemory:
        """Initialize memory for a new debate session."""
        memory = DebateMemory(debate_id=debate_id, topic=topic)
        self._sessions[debate_id] = memory
        return memory

    def get(self, debate_id: str) -> Optional[DebateMemory]:
        """Retrieve memory for an existing debate session."""
        return self._sessions.get(debate_id)

    def record_turn(self, debate_id: str, speaker: str, content: str, round_num: int):
        """Record a turn into the debate's memory (no-op if session not found)."""
        memory = self.get(debate_id)
        if memory:
            memory.record_turn(speaker, content, round_num)

    def get_context_for(self, debate_id: str, speaker: str) -> str:
        """Get the memory context string for a specific agent (for prompt injection)."""
        memory = self.get(debate_id)
        if memory is None:
            return ""
        return memory.get_context_for(speaker)

    def get_full_log(self, debate_id: str) -> list[dict]:
        """Return the full turn log for the memory endpoint."""
        memory = self.get(debate_id)
        if memory is None:
            return []
        return memory.get_full_log()

    def get_agent_memory(self, debate_id: str, agent_name: str) -> dict:
        """Return structured memory stats for a specific agent (for the /memory endpoint)."""
        memory = self.get(debate_id)
        if memory is None:
            return {}
        if agent_name not in memory.agents:
            return {"name": agent_name, "own_arguments_count": 0, "opponent_arguments_count": 0}
        mem = memory.agents[agent_name]
        return {
            "name": agent_name,
            "own_arguments_count": len(mem.own_arguments),
            "opponent_arguments_count": len(mem.opponent_arguments),
            "own_arguments": mem.own_arguments,
            "opponent_arguments": mem.opponent_arguments,
        }
