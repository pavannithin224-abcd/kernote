"""The labelled question set (proposal item P11), loaded and validated.

A question set is only as good as its labels, and labels rot silently as the
corpus changes — a relevance judgement pointing at a file that no longer exists
quietly lowers every score. `load()` therefore validates the labels against the
corpus on disk and refuses a set that does not match, rather than measuring
against a fiction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .. import resources

# A document that answers the question, as opposed to merely relating to it.
RELEVANT_GRADE = 2


class Question(BaseModel):
    id: str
    question: str
    kind: Literal["answerable", "unanswerable"]
    # rel_path -> grade. 2 answers the question, 1 is related but does not.
    relevant: dict[str, int] = Field(default_factory=dict)
    note: str | None = None

    @field_validator("relevant")
    @classmethod
    def _grades_in_range(cls, value: dict[str, int]) -> dict[str, int]:
        for path, grade in value.items():
            if grade not in (1, 2, 3):
                raise ValueError(f"{path}: grade {grade} is outside the documented 1-3 scale")
        return value

    def model_post_init(self, _context: object) -> None:
        answering = [p for p, g in self.relevant.items() if g >= RELEVANT_GRADE]
        if self.kind == "answerable" and not answering:
            raise ValueError(
                f"{self.id}: marked answerable but no document is graded "
                f"{RELEVANT_GRADE}, so recall could never be scored"
            )
        if self.kind == "unanswerable" and answering:
            raise ValueError(
                f"{self.id}: marked unanswerable but {answering} is graded as answering it"
            )

    @property
    def answering(self) -> set[str]:
        return {p for p, g in self.relevant.items() if g >= RELEVANT_GRADE}


class QuestionSet(BaseModel):
    version: int
    corpus: str
    """Where the corpus is, **relative to this question set's own file**.

    One rule, so a question set is self-describing and can be dropped anywhere
    -- a temporary directory in a test, or a user's own repository -- and still
    find what it describes. Resolving against the project root instead meant a
    set outside the project could never locate its corpus.
    """
    source_path: Path | None = Field(default=None, exclude=True)
    about: list[str] = Field(default_factory=list)
    questions: list[Question]

    @property
    def answerable(self) -> list[Question]:
        return [q for q in self.questions if q.kind == "answerable"]

    @property
    def unanswerable(self) -> list[Question]:
        return [q for q in self.questions if q.kind == "unanswerable"]


def default_path() -> Path:
    """`eval/questions.json` at the repository root."""
    return resources.project_file("eval/questions.json")


def allowed_root(question_set: QuestionSet) -> Path:
    """The directory a question set's corpus must stay inside.

    One level above the set's own file, which is what a `project/eval/` layout
    needs to reach `project/samples/`. The guard exists because `corpus` is a
    relative path from a data file: `../../../../etc` resolved happily, and the
    harness would then have pointed a scan at it. The project contract forbids reading
    credentials during scanning, and the cheapest way to honour that is to
    refuse the path rather than to trust the walker's deny-list to catch
    whatever is in there.
    """
    base = (
        question_set.source_path.parent if question_set.source_path else default_path().parent
    )
    return base.parent.resolve()


def corpus_path(question_set: QuestionSet, *, root: Path | None = None) -> Path:
    base = root or (
        question_set.source_path.parent if question_set.source_path else default_path().parent
    )
    return (base / question_set.corpus).resolve()


def load(path: Path | None = None, *, validate_corpus: bool = True) -> QuestionSet:
    path = path or default_path()
    if not path.is_file():
        raise FileNotFoundError(f"question set not found: {path}")
    question_set = QuestionSet.model_validate(json.loads(path.read_text(encoding="utf-8")))
    question_set.source_path = path.resolve()

    ids = [q.id for q in question_set.questions]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate question ids: {sorted(duplicates)}")

    if not question_set.questions:
        raise ValueError(
            "the question set is empty; every metric would be undefined and the "
            "report would look like a measurement"
        )

    if validate_corpus:
        corpus = corpus_path(question_set)
        root = allowed_root(question_set)
        if not corpus.is_relative_to(root):
            raise ValueError(
                f"corpus {question_set.corpus!r} resolves to {corpus}, outside "
                f"{root}. A question set may only point at a corpus beside it, "
                "so a data file cannot aim a scan at an arbitrary directory."
            )
        if not corpus.is_dir():
            raise FileNotFoundError(f"corpus not found: {corpus}")
        missing = sorted(
            f"{q.id} -> {rel}"
            for q in question_set.questions
            for rel in q.relevant
            if not (corpus / rel).is_file()
        )
        if missing:
            raise ValueError(
                "relevance labels point at files that are not in the corpus, so "
                "the measurement would be against a fiction: " + ", ".join(missing)
            )
    return question_set
