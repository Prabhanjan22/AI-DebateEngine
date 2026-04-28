"""
backend/routes/debate_routes.py

FastAPI router exposing all debate endpoints.

Endpoints:
  POST /start_debate   — Create a new debate session
  POST /next_turn      — Advance the debate by one turn
  GET  /debate_status  — Get current state of a session
  GET  /end_debate     — End debate and return full transcript (Arbiter added Phase 6)

All request/response models are defined as Pydantic models here.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from backend.debate_engine import DebateEngine


# ── Router setup ──────────────────────────────────────────────────────────────
router = APIRouter()

# Single shared engine instance — all routes use this
# Manages global state for all active debate sessions in memory
engine = DebateEngine()


# ── Pydantic Request / Response Models ────────────────────────────────────────

class StartDebateRequest(BaseModel):
    topic: str = Field(..., description="The debate topic or question", min_length=5)
    total_rounds: int = Field(default=3, ge=1, le=10, description="Number of debate rounds (1-10)")


class StartDebateResponse(BaseModel):
    debate_id: str
    topic: str
    total_rounds: int
    status: str
    first_turn: str
    message: str


class NextTurnRequest(BaseModel):
    debate_id: str = Field(..., description="The debate session ID from /start_debate")
    user_input: Optional[str] = Field(default=None, description="User's argument (required on USER's turn)")


class TurnResponse(BaseModel):
    speaker: str
    content: str
    round: int
    turn: str          # Who speaks next
    status: str
    fact_check: Optional[dict] = None
    score: Optional[dict] = None


class DebateStatusResponse(BaseModel):
    debate_id: str
    topic: str
    status: str
    current_round: int
    total_rounds: int
    whose_turn: str
    total_messages: int


class EndDebateResponse(BaseModel):
    debate_id: str
    topic: str
    status: str
    total_rounds: int
    transcript: list[dict]
    verdict: Optional[dict] = None
    message: str


class TraceResponse(BaseModel):
    debate_id: str
    topic: str
    total_turns_recorded: int
    docs: list[dict]
    history: list[dict]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start_debate", response_model=StartDebateResponse, tags=["Debate"])
def start_debate(request: StartDebateRequest):
    """
    Start a new debate session.

    Creates a new session with a unique debate_id.
    Returns the ID you'll use for all subsequent calls.
    """
    # Create the session inside the engine and grab its ID
    session = engine.start_debate(
        topic=request.topic,
        total_rounds=request.total_rounds
    )

    return StartDebateResponse(
        debate_id=session.debate_id,
        topic=session.topic,
        total_rounds=session.total_rounds,
        status=session.status,
        first_turn=session.whose_turn(),
        message=(
            f"Debate started! Topic: '{session.topic}'. "
            f"Running for {session.total_rounds} round(s). "
            f"First speaker: {session.whose_turn()}. "
            f"Call /next_turn with this debate_id to begin."
        )
    )


@router.post("/next_turn", response_model=TurnResponse, tags=["Debate"])
def next_turn(request: NextTurnRequest):
    """
    Advance the debate by one turn.

    - For AI turns (PRO / AGAINST): just send debate_id, no user_input needed.
    - For USER turns: you MUST include user_input, otherwise the turn is paused.
    - Returns what was said, who said it, and who speaks next.
    """
    # Delegate the heavy lifting of agent generation or user recording to the engine
    result = engine.next_turn(
        debate_id=request.debate_id,
        user_input=request.user_input
    )

    # Handle error case (bad debate_id, finished debate, etc.)
    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result["error"])

    return TurnResponse(**result)


@router.get("/debate_status", response_model=DebateStatusResponse, tags=["Debate"])
def debate_status(debate_id: str):
    """
    Get the current state of a debate session.

    Returns: round number, who speaks next, total messages, status.
    """
    session = engine.get_session(debate_id)

    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Debate session not found.")

    return DebateStatusResponse(
        debate_id=session.debate_id,
        topic=session.topic,
        status=session.status,
        current_round=session.current_round,
        total_rounds=session.total_rounds,
        whose_turn=session.whose_turn() if session.status != "finished" else "DONE",
        total_messages=len(session.history)
    )


@router.get("/end_debate", response_model=EndDebateResponse, tags=["Debate"])
def end_debate(debate_id: str):
    """
    End the debate and retrieve the full transcript.
    
    Runs the Arbiter to declare a winner.
    """
    session = engine.get_session(debate_id)

    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Debate session not found.")

    # Mark as finished if not already
    session.status = "finished"

    # Phase 6: Run the Arbiter to judge the final transcript
    verdict = engine.evaluate_debate(debate_id)

    return EndDebateResponse(
        debate_id=session.debate_id,
        topic=session.topic,
        status=session.status,
        total_rounds=session.total_rounds,
        transcript=session.history,
        verdict=verdict,
        message="Debate ended. The Arbiter has declared a winner!"
    )


@router.get("/trace", response_model=TraceResponse, tags=["Trace"])
def get_trace(debate_id: str):
    """
    Phase 7 — Inspect the RAG index and debate memory trace.

    Returns:
    - Chronological doc store (the embeddings data)
    """
    session = engine.get_session(debate_id)

    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Debate session not found.")

    # Gather trace info (RAG documents) from the FAISS manager for frontend observability
    if debate_id in engine._rag._sessions:
        docs = engine._rag._sessions[debate_id]["docs"]
    else:
        docs = []

    return TraceResponse(
        debate_id=debate_id,
        topic=session.topic,
        total_turns_recorded=len(docs),
        docs=docs,
        history=session.history,
    )
