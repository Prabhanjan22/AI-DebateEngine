"""
backend/persistence/debate_store.py

Writes completed debate records to:
  1. Local JSONL file:  data/debates/debates.jsonl  (one JSON object per line)
  2. (Phase 3) S3 bucket: configured via AWS_S3_BUCKET env var

The local file is the primary store for Phase 1 and 2.
S3 upload is gated behind an environment variable so it is never
accidentally triggered without explicit configuration.

Usage:
    from backend.persistence.debate_store import DebateStore
    store = DebateStore()
    store.save(record)
"""

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.persistence.debate_schema import (
    DebateRecord, FactCheckSummary, ScoreSummary
)

logger = logging.getLogger(__name__)

# Local storage path — relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data" / "debates"
_JSONL_FILE = _DATA_DIR / "debates.jsonl"


class DebateStore:
    """
    Persist and retrieve completed debate records.
    Thread-safe for single-process use (file append is atomic on most OS).
    """

    def __init__(self):
        _DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── Write ────────────────────────────────────────────────────────────

    def save(self, record: DebateRecord) -> bool:
        """
        Append a DebateRecord to the local JSONL file.
        Returns True on success, False on failure (never raises).
        """
        try:
            line = record.model_dump_json() + "\n"
            with open(_JSONL_FILE, "a", encoding="utf-8") as f:
                f.write(line)
            logger.info(f"Debate record saved: {record.debate_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save debate record {record.debate_id}: {e}")
            return False

    # ── Read ─────────────────────────────────────────────────────────────

    def load_all(self) -> list[DebateRecord]:
        """Load all records from the local JSONL file."""
        if not _JSONL_FILE.exists():
            return []
        records = []
        with open(_JSONL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(DebateRecord.model_validate_json(line))
                    except Exception as e:
                        logger.warning(f"Skipping malformed record: {e}")
        return records

    def load_recent(self, n: int = 20) -> list[DebateRecord]:
        """Return the N most recently saved records."""
        return self.load_all()[-n:]

    def count(self) -> int:
        """Return total number of saved records."""
        return len(self.load_all())

    def get_stats(self) -> dict:
        """
        Return quick aggregate statistics for the analytics endpoint.
        Computed in-memory — fine for small datasets (Phase 2).
        The Glue/Athena pipeline handles large-scale aggregation.
        """
        records = self.load_all()
        if not records:
            return {"total_debates": 0}

        winners = [r.winner for r in records if r.winner]
        pro_wins = winners.count("PRO")
        against_wins = winners.count("AGAINST")
        ties = winners.count("TIE")

        all_pro_scores = [
            r.pro_score_summary.avg_overall
            for r in records
            if r.pro_score_summary and r.pro_score_summary.avg_overall > 0
        ]
        all_against_scores = [
            r.against_score_summary.avg_overall
            for r in records
            if r.against_score_summary and r.against_score_summary.avg_overall > 0
        ]

        durations = [r.duration_seconds for r in records if r.duration_seconds]

        return {
            "total_debates": len(records),
            "verdict_distribution": {
                "PRO": pro_wins,
                "AGAINST": against_wins,
                "TIE": ties,
                "pending": len(records) - len(winners),
            },
            "avg_pro_score": round(sum(all_pro_scores) / len(all_pro_scores), 2) if all_pro_scores else None,
            "avg_against_score": round(sum(all_against_scores) / len(all_against_scores), 2) if all_against_scores else None,
            "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else None,
            "topics_debated": [r.topic for r in records[-10:]],   # last 10 topics
        }


# ── Builder helper ────────────────────────────────────────────────────────────

def build_record_from_session(session, score_history: list[dict], fact_check_history: list[dict],
                               started_at: str, verdict: Optional[dict] = None,
                               rag_retrievals: int = 0) -> DebateRecord:
    """
    Construct a DebateRecord from a finished DebateSession.

    Args:
        session:             The DebateSession object from debate_engine.py
        score_history:       List of {"speaker": ..., "score": {...}} dicts accumulated during the debate
        fact_check_history:  List of {"speaker": ..., "fact_check": {...}} dicts
        started_at:          ISO timestamp when the debate was created
        verdict:             Arbiter output dict {"winner": ..., "reasoning": ...}
        rag_retrievals:      Total number of RAG context lookups performed

    Returns:
        A fully-populated DebateRecord ready to be saved.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Parse duration
    try:
        started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        ended_dt = datetime.now(timezone.utc)
        duration = (ended_dt - started_dt).total_seconds()
    except Exception:
        duration = None

    # Count turns per speaker
    pro_turns = sum(1 for h in session.history if "[PRO]" in h.get("content", ""))
    against_turns = sum(1 for h in session.history if "[AGAINST]" in h.get("content", ""))
    user_turns = sum(1 for h in session.history if "[USER]" in h.get("content", ""))

    # Aggregate fact-check outcomes
    fc_summary = FactCheckSummary()
    confidences = []
    for fc in fact_check_history:
        fc_data = fc.get("fact_check", {})
        assessment = fc_data.get("assessment", "UNVERIFIED")
        conf = fc_data.get("confidence", 0)
        if conf:
            confidences.append(conf)
        if assessment == "TRUE":
            fc_summary.true_count += 1
        elif assessment == "FALSE":
            fc_summary.false_count += 1
        elif assessment == "MIXED":
            fc_summary.mixed_count += 1
        elif assessment == "OPINION":
            fc_summary.opinion_count += 1
        else:
            fc_summary.unverified_count += 1
    if confidences:
        fc_summary.average_confidence = round(sum(confidences) / len(confidences), 1)

    # Aggregate scores per speaker
    def _agg_score(speaker_name: str) -> Optional[ScoreSummary]:
        turns = [s["score"] for s in score_history if s.get("speaker") == speaker_name and s.get("score")]
        if not turns:
            return None
        n = len(turns)
        return ScoreSummary(
            speaker=speaker_name,
            turn_count=n,
            avg_logic=round(sum(t.get("logic", 0) for t in turns) / n, 2),
            avg_relevance=round(sum(t.get("relevance", 0) for t in turns) / n, 2),
            avg_persuasiveness=round(sum(t.get("persuasiveness", 0) for t in turns) / n, 2),
            avg_overall=round(sum(t.get("overall", 0) for t in turns) / n, 2),
        )

    # Build transcript summary (truncated content for storage efficiency)
    transcript_summary = [
        {
            "role": h.get("role"),
            "content_preview": h.get("content", "")[:120],
        }
        for h in session.history
        if h.get("role") in ("assistant", "user")
    ]

    return DebateRecord(
        debate_id=session.debate_id,
        timestamp=now,
        topic=session.topic,
        total_rounds=session.total_rounds,
        actual_rounds_completed=session.current_round - 1 if session.status == "finished" else session.current_round,
        total_turns=len(session.history),
        pro_turns=pro_turns,
        against_turns=against_turns,
        user_turns=user_turns,
        started_at=started_at,
        ended_at=now,
        duration_seconds=duration,
        fact_check_summary=fc_summary,
        pro_score_summary=_agg_score("PRO"),
        against_score_summary=_agg_score("AGAINST"),
        user_score_summary=_agg_score("USER"),
        winner=verdict.get("winner") if verdict else None,
        arbiter_reasoning=verdict.get("reasoning") if verdict else None,
        rag_retrievals=rag_retrievals,
        transcript_summary=transcript_summary,
    )
