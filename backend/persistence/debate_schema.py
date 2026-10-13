"""
backend/persistence/debate_schema.py

Versioned Pydantic schema for a completed debate record.

This schema is the contract between:
  - The debate engine (writes records)
  - The data pipeline (reads and transforms records)
  - The analytics API (queries aggregated records)

Version: 1.0
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FactCheckSummary(BaseModel):
    """Aggregated fact-check result across all turns."""
    true_count: int = 0
    false_count: int = 0
    mixed_count: int = 0
    opinion_count: int = 0
    unverified_count: int = 0
    average_confidence: float = 0.0


class ScoreSummary(BaseModel):
    """Per-speaker aggregate scores from the scoring engine."""
    speaker: str
    turn_count: int = 0
    avg_logic: float = 0.0
    avg_relevance: float = 0.0
    avg_persuasiveness: float = 0.0
    avg_overall: float = 0.0


class DebateRecord(BaseModel):
    """
    A complete record of a finished debate session.
    Stored as a JSON line in data/debates/debates.jsonl
    and uploaded to S3 for pipeline processing.

    Fields intentionally exclude:
    - API keys or tokens
    - Full raw transcript (stored separately in transcript field, optional)
    - Any personal user information
    """
    # Identity
    debate_id: str
    schema_version: str = "1.0"
    timestamp: str  # ISO 8601 UTC

    # Topic metadata
    topic: str
    topic_category: Optional[str] = None   # Filled by ML classifier later

    # Debate structure
    total_rounds: int
    actual_rounds_completed: int
    total_turns: int                        # Total history entries
    pro_turns: int = 0
    against_turns: int = 0
    user_turns: int = 0

    # Timing and performance
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    avg_response_latency_ms: Optional[float] = None  # Populated when available

    # Fact-check outcomes
    fact_check_summary: Optional[FactCheckSummary] = None
    wikipedia_tool_calls: int = 0           # MCP tool invocations

    # Scoring outcomes
    pro_score_summary: Optional[ScoreSummary] = None
    against_score_summary: Optional[ScoreSummary] = None
    user_score_summary: Optional[ScoreSummary] = None

    # Arbiter verdict
    winner: Optional[str] = None            # "PRO" | "AGAINST" | "TIE" | None
    arbiter_reasoning: Optional[str] = None

    # Evidence and retrieval
    rag_retrievals: int = 0                 # Total RAG lookups performed
    evidence_sources: list[str] = Field(default_factory=list)  # Wikipedia articles cited

    # Error tracking
    had_error: bool = False
    error_messages: list[str] = Field(default_factory=list)

    # Optional: Condensed transcript for offline analysis
    # Kept short (first 100 chars per turn) to control file size
    transcript_summary: list[dict] = Field(default_factory=list)
