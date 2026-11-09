"""Evaluation (Settings & Evaluation screen).

This measures **Kernote's retrieval against its own labelled question set**,
over the fixture corpus in `samples/eval-repo` — not against the user's
project, which has no relevance labels and so cannot be scored. The screen says
so, because a metrics panel that looks like it describes your repository when
it does not is worse than no panel.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...db.connection import open_db
from ...eval import questions as qmod
from ...eval import runner

router = APIRouter(prefix="/api/v1", tags=["evaluation"])


class EvalRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    allow_download: bool = Field(
        default=False,
        description=(
            "Permit fetching the embedding model if it is not cached. Off by "
            "default: an evaluation must not silently reach the network."
        ),
    )


@router.get("/evaluation/question-set")
def question_set() -> dict:
    """What the evaluation measures, without running it."""
    try:
        loaded = qmod.load()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(503, f"question set unavailable: {exc}") from exc
    return {
        "version": loaded.version,
        "corpus": loaded.corpus,
        "about": loaded.about,
        "questions": len(loaded.questions),
        "answerable": len(loaded.answerable),
        "unanswerable": len(loaded.unanswerable),
        "measures": [
            "citation correctness",
            "useful abstention rate",
            "Recall@k, MRR, nDCG",
        ],
    }


@router.post("/evaluation/run")
def run_evaluation(body: EvalRequest) -> dict:
    """Scan the fixture corpus into a throwaway database and score every
    labelled question.

    A separate database on purpose: the evaluation must never add 50 fixture
    memories to the user's own vault, and it must not be affected by what is
    already in it.
    """
    try:
        loaded = qmod.load()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(503, f"question set unavailable: {exc}") from exc

    with tempfile.TemporaryDirectory(prefix="kernote-eval-") as directory:
        conn = open_db(Path(directory) / "eval.db")
        try:
            report = runner.run(
                conn,
                question_set=loaded,
                limit=body.limit,
                allow_download=body.allow_download,
            )
            payload = report.to_dict()
            payload["markdown"] = runner.to_markdown(report)
            return payload
        finally:
            conn.close()
