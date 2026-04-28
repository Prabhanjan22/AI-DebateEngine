"""
backend/debate_engine.py

The core orchestrator of the debate system.

Responsibilities:
- Maintains all active debate sessions (keyed by debate_id)
- Controls turn order: PRO → AGAINST → USER → (repeat)
- Stores full conversation history per session
- Provides next_turn() which advances the debate by one step
- Designed to be extended in later phases (memory, scoring, fact-check)

Turn order logic:
  Each "round" has 3 turns: PRO (index 0), AGAINST (index 1), USER (index 2)
  After USER turn, we loop back to PRO for the next round.
"""

import uuid
from datetime import datetime
from typing import Optional

from backend.agents.pro_agent import ProAgent
from backend.agents.against_agent import AgainstAgent
from backend.agents.fact_checker_agent import FactCheckerAgent
from backend.agents.scoring_agent import ScoringAgent
from backend.agents.arbiter_agent import ArbiterAgent
from backend.memory.rag_manager import RAGManager
from backend.mcp import MCPManager
import json


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

# Turn order within a single round
TURN_ORDER = ["PRO", "AGAINST", "USER"]

# Debate status values
STATUS_ACTIVE = "active"
STATUS_WAITING_USER = "waiting_for_user"
STATUS_FINISHED = "finished"


class DebateSession:
    """
    Represents a single debate session.

    Attributes:
        debate_id       : Unique identifier for this debate
        topic           : The debate topic/question
        total_rounds    : How many rounds to run (default 3)
        current_round   : Which round we are on (1-indexed)
        turn_index      : Position in TURN_ORDER (0=PRO, 1=AGAINST, 2=USER)
        history         : Full conversation log as list of dicts
        status          : "active" | "waiting_for_user" | "finished"
        created_at      : Timestamp of creation
    """

    def __init__(self, topic: str, total_rounds: int = 3):
        self.debate_id: str = str(uuid.uuid4())
        self.topic: str = topic
        self.total_rounds: int = total_rounds
        self.current_round: int = 1
        self.turn_index: int = 0           # Starts at PRO (index 0)
        self.history: list[dict] = []      # Full conversation log
        self.status: str = STATUS_ACTIVE
        self.created_at: str = datetime.utcnow().isoformat()

    def whose_turn(self) -> str:
        """Returns the name of who should speak next."""
        return TURN_ORDER[self.turn_index]

    def add_to_history(self, speaker: str, content: str):
        """
        Append a turn to conversation history.
        Uses 'assistant' role for AI agents, 'user' role for the human.
        This format is compatible with OpenAI's message format.
        """
        role = "user" if speaker == "USER" else "assistant"
        self.history.append({
            "role": role,
            "content": f"[{speaker}]: {content}"
        })

    def advance_turn(self):
        """
        Move to the next speaker.
        If we just completed USER's turn (end of round), increment round counter.
        If we've completed all rounds, mark debate as finished.
        """
        self.turn_index += 1

        # Check if a full round just completed (after USER's turn)
        if self.turn_index >= len(TURN_ORDER):
            self.turn_index = 0           # Reset to PRO for next round
            self.current_round += 1       # Increment round counter

        # Check if all rounds are done
        if self.current_round > self.total_rounds:
            self.status = STATUS_FINISHED
        elif self.whose_turn() == "USER":
            # Pause and wait for human input before continuing
            self.status = STATUS_WAITING_USER
        else:
            self.status = STATUS_ACTIVE


class DebateEngine:
    """
    Manages all active debate sessions.

    This is the single source of truth — routes call into this engine.
    In later phases, the engine will also coordinate with:
      - MemoryManager (Phase 2)
      - FactChecker (Phase 3)
      - MCPManager (Phase 4)
      - ScoringEngine (Phase 5)
      - Arbiter (Phase 6)
    """

    def __init__(self):
        # In-memory store of all sessions: {debate_id: DebateSession}
        self._sessions: dict[str, DebateSession] = {}

        # Instantiate agents once — they are stateless and reusable
        self._pro_agent = ProAgent()
        self._against_agent = AgainstAgent()
        self._fact_checker = FactCheckerAgent()
        self._scoring_agent = ScoringAgent()
        self._arbiter_agent = ArbiterAgent()

        # Phase 2 & 7: RAG system — tracks argument history using FAISS
        self._rag = RAGManager()

        # Phase 4: MCP system for tool-augmented reasoning
        self._mcp_manager = MCPManager()

    # ── Session Management ────────────────────────────────────────────

    def start_debate(self, topic: str, total_rounds: int = 3) -> DebateSession:
        """
        Create a new debate session and return it.
        Also adds an opening system message to history so agents know the topic.
        """
        session = DebateSession(topic=topic, total_rounds=total_rounds)

        # Seed the history with the topic so all agents see it from the start
        session.history.append({
            "role": "system",
            "content": (
                f"The debate topic is: \"{topic}\". "
                f"This debate will run for {total_rounds} round(s). "
                f"Turn order each round: PRO → AGAINST → USER."
            )
        })

        self._sessions[session.debate_id] = session

        # (RAGManager lazily initializes sessions when arguments are added)

        return session

    def get_session(self, debate_id: str) -> Optional[DebateSession]:
        """Retrieve an existing session by ID."""
        return self._sessions.get(debate_id)

    # ── Core Debate Logic ────────────────────────────────────────────

    def _run_fact_check(self, session: DebateSession, speaker: str) -> dict:
        """Run the FactCheckerAgent on the latest argument and append result to history."""
        try:
            # Retrieve relevant historical context via RAG for grounding
            query = session.history[-1]["content"] if session.history else ""
            rag_context = self._rag.get_context_for_agent(session.debate_id, query=query, speaker="SYSTEM")
            
            fact_check_raw = self._fact_checker.generate(
                conversation_history=session.history,
                extra_context=rag_context,
                mcp_manager=self._mcp_manager
            )
            fact_check_data = json.loads(fact_check_raw)
        except Exception as e:
            fact_check_data = {
                "assessment": "UNVERIFIED",
                "confidence": 0,
                "reasoning": f"Fact checker error: {str(e)}"
            }

        # Append to history so other agents see it
        assessment = fact_check_data.get("assessment", "UNVERIFIED")
        reasoning = fact_check_data.get("reasoning", "")
        confidence = fact_check_data.get("confidence", 0)
        
        session.add_to_history(
            "Fact Checker",
            f"[{assessment}] {reasoning} (Confidence: {confidence}%)"
        )
        return fact_check_data

    def _run_scoring(self, session: DebateSession, speaker: str) -> dict:
        """Run the ScoringAgent on the latest argument and append result to history."""
        try:
            score_raw = self._scoring_agent.generate(
                conversation_history=session.history,
                mcp_manager=self._mcp_manager
            )
            score_data = json.loads(score_raw)
        except Exception as e:
            score_data = {
                "logic": 0,
                "relevance": 0,
                "persuasiveness": 0,
                "overall": 0,
                "reasoning": f"Scoring error: {str(e)}"
            }

        overall = score_data.get("overall", 0)
        session.add_to_history(
            "Scoring Engine",
            f"[Score: {overall}/10] {score_data.get('reasoning', '')}"
        )
        return score_data

    def next_turn(self, debate_id: str, user_input: Optional[str] = None) -> dict:
        """
        Advance the debate by one turn and return the result.

        Args:
            debate_id  : The active debate session ID
            user_input : Required when it's the USER's turn; ignored otherwise

        Returns:
            A dict with: speaker, content, round, turn, status
        """
        session = self.get_session(debate_id)

        # ── Guard: session must exist ──
        if session is None:
            return {"error": "Debate session not found. Start a new debate first."}

        # ── Guard: debate must not be over ──
        if session.status == STATUS_FINISHED:
            return {"error": "This debate has already ended. Use /end_debate to see results."}

        speaker = session.whose_turn()

        # ── Handle USER turn ──
        if speaker == "USER":
            # USER input is required — if missing, pause and ask
            if not user_input or not user_input.strip():
                session.status = STATUS_WAITING_USER
                return {
                    "speaker": "SYSTEM",
                    "content": "It's your turn! Please provide your argument.",
                    "round": session.current_round,
                    "turn": speaker,
                    "status": session.status,
                }

            content = user_input.strip()
            session.add_to_history("USER", content)

            # Record human input in FAISS RAG to allow AI agents to recall it later
            self._rag.add_argument(
                debate_id=session.debate_id,
                speaker="USER",
                content=content,
                round_num=session.current_round
            )

            # Phase 3: Run Fact Checker
            fact_check_data = self._run_fact_check(session, "USER")

            # Phase 5: Run Scoring Engine
            score_data = self._run_scoring(session, "USER")

            session.advance_turn()

            return {
                "speaker": "USER",
                "content": content,
                "round": session.current_round - 1 if session.turn_index == 0 else session.current_round,
                "turn": session.whose_turn() if session.status != STATUS_FINISHED else "DONE",
                "status": session.status,
                "fact_check": fact_check_data,
                "score": score_data,
            }

        # ── Handle AI agent turns (PRO / AGAINST) ──
        agent = self._pro_agent if speaker == "PRO" else self._against_agent

        # Phase 2 & 7: Fetch RAG context to inject before generation
        query = session.history[-1]["content"] if session.history else ""
        memory_context = self._rag.get_context_for_agent(
            debate_id=session.debate_id, query=query, speaker=speaker
        )

        # Generate response using full conversation history + memory context + tools
        response_text = agent.generate(
            conversation_history=session.history,
            extra_context=memory_context,
            mcp_manager=self._mcp_manager
        )

        # Store this turn in history
        session.add_to_history(speaker, response_text)

        # Embed AI response into FAISS RAG for future context recall
        self._rag.add_argument(
            debate_id=session.debate_id,
            speaker=speaker,
            content=response_text,
            round_num=session.current_round
        )

        # Phase 3: Run Fact Checker
        fact_check_data = self._run_fact_check(session, speaker)

        # Phase 5: Run Scoring Engine
        score_data = self._run_scoring(session, speaker)

        # Advance to the next turn
        session.advance_turn()

        return {
            "speaker": speaker,
            "content": response_text,
            "round": session.current_round - 1 if session.turn_index == 0 and session.current_round > 1 else session.current_round,
            "turn": session.whose_turn() if session.status != STATUS_FINISHED else "DONE",
            "status": session.status,
            "fact_check": fact_check_data,
            "score": score_data,
        }

    def get_full_history(self, debate_id: str) -> list[dict]:
        """Return the full conversation history for a session."""
        session = self.get_session(debate_id)
        if session is None:
            return []
        return session.history

    def evaluate_debate(self, debate_id: str) -> dict:
        """Run the Arbiter to evaluate the whole debate and declare a winner."""
        session = self.get_session(debate_id)
        if session is None:
            return {"winner": "UNKNOWN", "reasoning": "Session not found."}

        try:
            # Provide Arbiter with topic-grounded context from FAISS
            rag_context = self._rag.get_context_for_agent(debate_id, query=session.topic, speaker="SYSTEM")
            
            arbiter_raw = self._arbiter_agent.generate(
                conversation_history=session.history,
                extra_context=rag_context,
                mcp_manager=self._mcp_manager
            )
            arbiter_data = json.loads(arbiter_raw)
        except Exception as e:
            arbiter_data = {
                "winner": "TIE",
                "reasoning": f"Arbiter evaluation error: {str(e)}"
            }
        
        session.add_to_history("Arbiter", f"[{arbiter_data.get('winner', 'TIE')}] {arbiter_data.get('reasoning', '')}")
        return arbiter_data
