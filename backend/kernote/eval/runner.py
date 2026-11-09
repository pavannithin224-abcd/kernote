"""Run the labelled question set and report measured retrieval quality.

What the Day-25 criteria ask for is **citation correctness** and
**useful-abstention rate**, not answer fluency, so those two are reported
first-class alongside the ranking metrics.

Three definitions, stated here because an evaluation whose definitions are
implicit cannot be argued with:

* **Citation correctness** — of every citation returned for an answerable
  question, the share pointing at a document the label set grades as relevant
  at all (grade >= 1). `strict` counts only documents graded as *answering* it.
  A citation to an unlabelled document is counted wrong, which is harsh but is
  the honest reading: it is a source offered in support of an answer it does
  not support.
* **Useful abstention** — of the unanswerable questions, the share where the
  system **declined to assert an answer**. This is the metric that makes the
  others trustworthy: a system that always answers has no abstention rate and
  cannot be believed when it does answer.

  "Declined" covers both `not_found` (nothing was retrieved) and
  `weak_evidence` (records were retrieved, and the system said none of them
  addresses the question and they should be read as leads). Counting only
  `not_found` was this module's first definition and it was wrong: it scored
  0% while the product was in fact declining correctly on four of six
  questions. Only `evidence_found` is an assertion.
* **False abstention** — of the answerable questions, the share where it
  declined although the corpus contained the answer. Abstention is only a
  virtue when there is nothing to find, so both numbers are reported together
  and neither is meaningful alone.

**Retrieving and asserting are scored separately**, because the first Stage 8
run conflated them and produced a misleading failure count. On the paraphrased
questions the right document is retrieved at rank 2 to 5 and the system then
declines to assert, because none of the question's words appear in it — ask
"what the taxman takes" and the invoice module never says "taxman". Scoring
that as a flat failure hides what actually happened, and would invite
"fixing" it by loosening the very gate that stops the system inventing
support. Each question therefore gets a `verdict`:

* `answered` — a document that answers it was retrieved *and* asserted.
* `lead_only` — retrieved, but offered as a lead rather than an answer. The
  honest outcome when nothing lexical can verify a semantic match.
* `missed` — never retrieved at all. The only unambiguous retrieval failure.
* `correctly_declined` / `wrongly_asserted` — for the unanswerable questions.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import structlog

from ..db.repositories import projects as project_repo
from ..domain.models import Project
from ..ingest.pipeline import scan_project
from ..retrieval import answer as answer_mod
from . import metrics
from .questions import Question, QuestionSet, corpus_path, load

log = structlog.get_logger(__name__)

RECALL_KS = (1, 3, 5, 10)
NDCG_K = 10


def _reportable_ks(depth: int) -> tuple[int, ...]:
    """The cut-offs a run at this retrieval depth can honestly report.

    Recall@10 from a run that only ever retrieved three documents is Recall@3
    wearing a different label. The first version printed all four cut-offs
    whatever the depth, so a `limit=3` run reported four identical numbers and
    called one of them Recall@10.
    """
    return tuple(k for k in RECALL_KS if k <= depth) or (depth,)


DECLINED_OUTCOMES = frozenset({"not_found", "weak_evidence"})


@dataclass
class QuestionResult:
    id: str
    question: str
    kind: str
    outcome: str
    abstained: bool
    """The system declined to assert an answer -- see the module docstring."""
    correct: bool
    """Retrieval succeeded for an answerable question, or abstention was right."""
    verdict: str = "missed"
    retrieved_answer: bool = False
    """A document graded as answering the question was in the top k."""
    answer_rank: int | None = None
    """Where the first answering document sits in what was returned.

    Reported for leads especially: when the system cannot assert an answer, the
    thing that decides whether it is still useful is whether the right document
    is the first one the reader sees.
    """
    retrieved: list[str] = field(default_factory=list)
    recall: dict[int, float] = field(default_factory=dict)
    reciprocal_rank: float = float("nan")
    ndcg: float = float("nan")
    precision_at_5: float = float("nan")
    citations_total: int = 0
    citations_relevant: int = 0
    citations_answering: int = 0
    note: str | None = None


@dataclass
class EvalReport:
    corpus: str
    questions: int
    answerable: int
    unanswerable: int
    memories_scanned: int
    semantic: bool
    elapsed_seconds: float
    retrieval_depth: int = 0
    """How many results were asked for. Cut-offs above this are not reported."""
    recall_at_k: dict[int, float] = field(default_factory=dict)
    mrr: float = float("nan")
    ndcg_at_10: float = float("nan")
    precision_at_5: float = float("nan")
    outcomes: dict[str, int] = field(default_factory=dict)
    verdicts: dict[str, int] = field(default_factory=dict)
    retrieval_success_rate: float = float("nan")
    answer_rate: float = float("nan")
    lead_first_rate: float = float("nan")
    """Of the questions that ended as leads, how often the right document was
    first. A lead is only useful if the reader does not have to hunt."""
    citation_correctness: float = float("nan")
    citation_correctness_strict: float = float("nan")
    useful_abstention_rate: float = float("nan")
    false_abstention_rate: float = float("nan")
    results: list[QuestionResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        # JSON object keys must be strings, and `nan` is not valid JSON.
        data["recall_at_k"] = {str(k): _jsonable(v) for k, v in self.recall_at_k.items()}
        for key in (
            "mrr",
            "ndcg_at_10",
            "precision_at_5",
            "citation_correctness",
            "citation_correctness_strict",
            "useful_abstention_rate",
            "false_abstention_rate",
        ):
            data[key] = _jsonable(data[key])
        for row in data["results"]:
            row["recall"] = {str(k): _jsonable(v) for k, v in row["recall"].items()}
            for key in ("reciprocal_rank", "ndcg", "precision_at_5"):
                row[key] = _jsonable(row[key])
        return data


def _jsonable(value: float) -> float | None:
    return None if value != value else round(value, 4)


def _source_path(conn: sqlite3.Connection, kind: str, target_id: str) -> str | None:
    """The repository-relative file an evidence item came from."""
    if kind == "memory":
        row = conn.execute(
            "SELECT rel_path FROM memory_source_refs WHERE memory_id=? "
            "AND rel_path IS NOT NULL LIMIT 1",
            (target_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT sf.rel_path FROM chunks c JOIN source_files sf "
            "ON sf.id = c.source_file_id WHERE c.id=?",
            (target_id,),
        ).fetchone()
    return row["rel_path"] if row else None


def _ranked_paths(conn: sqlite3.Connection, bundle) -> list[str]:
    """Evidence collapsed to a ranked list of distinct source files.

    Labels are per file, so several memories from one file are one retrieved
    document — otherwise a file that produced five memories would score five
    recall hits for one correct retrieval.
    """
    ordered: list[str] = []
    for item in bundle.evidence:
        path = _source_path(conn, item.source, item.target_id)
        if path and path not in ordered:
            ordered.append(path)
    return ordered


def _score(conn: sqlite3.Connection, question: Question, bundle, limit: int) -> QuestionResult:
    ranked = _ranked_paths(conn, bundle)
    grades = dict(question.relevant)
    abstained = bundle.outcome in DECLINED_OUTCOMES

    cited = [
        p
        for p in (_source_path(conn, item.source, item.target_id) for item in bundle.evidence)
        if p
    ]
    relevant_cites = sum(1 for p in cited if grades.get(p, 0) >= 1)
    answering_cites = sum(1 for p in cited if grades.get(p, 0) >= metrics.RELEVANT)

    retrieved_answer = bool(set(ranked[:limit]) & question.answering)
    answer_rank = next(
        (i for i, path in enumerate(ranked[:limit], start=1) if path in question.answering),
        None,
    )
    if question.kind == "unanswerable":
        correct = abstained
        verdict = "correctly_declined" if abstained else "wrongly_asserted"
    else:
        # Retrieving the right document is necessary but not sufficient: a
        # system that finds it and then declines to call it an answer has not
        # answered the question -- but it has not missed it either.
        correct = retrieved_answer and not abstained
        if not retrieved_answer:
            verdict = "missed"
        elif abstained:
            verdict = "lead_only"
        else:
            verdict = "answered"

    return QuestionResult(
        id=question.id,
        question=question.question,
        kind=question.kind,
        outcome=bundle.outcome,
        abstained=abstained,
        correct=correct,
        verdict=verdict,
        retrieved_answer=retrieved_answer,
        answer_rank=answer_rank,
        retrieved=ranked[:limit],
        recall={k: metrics.recall_at_k(ranked, grades, k) for k in _reportable_ks(limit)},
        reciprocal_rank=metrics.reciprocal_rank(ranked, grades),
        ndcg=metrics.ndcg_at_k(ranked, grades, min(NDCG_K, limit)),
        precision_at_5=metrics.precision_at_k(ranked, grades, 5)
        if question.kind == "answerable"
        else float("nan"),
        citations_total=len(cited),
        citations_relevant=relevant_cites,
        citations_answering=answering_cites,
        note=question.note,
    )


def prepare_corpus(
    conn: sqlite3.Connection, question_set: QuestionSet, *, name: str = "Evaluation corpus"
) -> tuple[str, int]:
    """Register and scan the corpus. Returns (project_id, memories_created)."""
    root = corpus_path(question_set)
    project = project_repo.create(
        conn, Project(name=name, root_path=str(root), is_git_repo=False)
    )
    result = scan_project(
        conn,
        project_id=project.id,
        root=root,
        max_file_bytes=1_000_000,
        max_files=5_000,
    )
    return project.id, result.memories_created


def run(
    conn: sqlite3.Connection,
    *,
    question_set: QuestionSet | None = None,
    project_id: str | None = None,
    limit: int = 10,
    allow_download: bool = False,
) -> EvalReport:
    """Ask every labelled question and score the answers.

    `allow_download` is off by default: an evaluation must not silently reach
    the network to fetch an embedding model. With it off and no model cached,
    the run measures the keyword-only path and the report says so.
    """
    question_set = question_set or load()
    started = time.perf_counter()
    memories = 0
    if project_id is None:
        project_id, memories = prepare_corpus(conn, question_set)
    else:
        memories = conn.execute(
            "SELECT COUNT(*) AS c FROM memories WHERE project_id=?", (project_id,)
        ).fetchone()["c"]

    results: list[QuestionResult] = []
    semantic = False
    for question in question_set.questions:
        bundle = answer_mod.ask(
            conn,
            project_id=project_id,
            question=question.question,
            limit=limit,
            allow_download=allow_download,
        )
        semantic = semantic or bundle.semantic_available
        results.append(_score(conn, question, bundle, limit))

    answerable = [r for r in results if r.kind == "answerable"]
    unanswerable = [r for r in results if r.kind == "unanswerable"]
    cites_total = sum(r.citations_total for r in answerable)
    cites_relevant = sum(r.citations_relevant for r in answerable)
    cites_answering = sum(r.citations_answering for r in answerable)

    report = EvalReport(
        corpus=question_set.corpus,
        questions=len(results),
        answerable=len(answerable),
        unanswerable=len(unanswerable),
        memories_scanned=memories,
        semantic=semantic,
        elapsed_seconds=round(time.perf_counter() - started, 3),
        retrieval_depth=limit,
        outcomes={
            outcome: sum(1 for r in results if r.outcome == outcome)
            for outcome in sorted({r.outcome for r in results})
        },
        verdicts={
            verdict: sum(1 for r in results if r.verdict == verdict)
            for verdict in sorted({r.verdict for r in results})
        },
        retrieval_success_rate=(
            sum(1 for r in answerable if r.retrieved_answer) / len(answerable)
            if answerable
            else float("nan")
        ),
        answer_rate=(
            sum(1 for r in answerable if r.verdict == "answered") / len(answerable)
            if answerable
            else float("nan")
        ),
        lead_first_rate=(
            sum(1 for r in leads if r.answer_rank == 1) / len(leads)
            if (leads := [r for r in answerable if r.verdict == "lead_only"])
            else float("nan")
        ),
        recall_at_k={
            k: metrics.mean([r.recall[k] for r in results]) for k in _reportable_ks(limit)
        },
        mrr=metrics.mean([r.reciprocal_rank for r in results]),
        ndcg_at_10=metrics.mean([r.ndcg for r in results]),
        precision_at_5=metrics.mean([r.precision_at_5 for r in results]),
        citation_correctness=(cites_relevant / cites_total) if cites_total else float("nan"),
        citation_correctness_strict=(
            (cites_answering / cites_total) if cites_total else float("nan")
        ),
        useful_abstention_rate=(
            sum(1 for r in unanswerable if r.abstained) / len(unanswerable)
            if unanswerable
            else float("nan")
        ),
        false_abstention_rate=(
            sum(1 for r in answerable if r.abstained) / len(answerable)
            if answerable
            else float("nan")
        ),
        results=results,
    )
    log.info(
        "eval.completed",
        questions=report.questions,
        recall_at_5=report.recall_at_k.get(5),
        citation_correctness=report.citation_correctness,
        useful_abstention=report.useful_abstention_rate,
        semantic=report.semantic,
    )
    return report


def to_markdown(report: EvalReport) -> str:
    """A report someone can paste into a document and argue with."""

    def pct(value: float) -> str:
        return "n/a" if value != value else f"{value * 100:.1f}%"

    def num(value: float) -> str:
        return "n/a" if value != value else f"{value:.3f}"

    path_label = "hybrid keyword + semantic" if report.semantic else "keyword only"
    lines = [
        "# Retrieval evaluation",
        "",
        f"Corpus `{report.corpus}` — {report.memories_scanned} memories, "
        f"{report.questions} labelled questions "
        f"({report.answerable} answerable, {report.unanswerable} unanswerable). "
        f"Retrieval path: {path_label}. Ran in {report.elapsed_seconds}s.",
        "",
        "## What the acceptance criteria ask for",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Citation correctness (cited a related document) | "
        f"{pct(report.citation_correctness)} |",
        f"| Citation correctness (cited a document that answers it) | "
        f"{pct(report.citation_correctness_strict)} |",
        f"| Useful abstention rate (declined when nothing supported it) | "
        f"{pct(report.useful_abstention_rate)} |",
        f"| False abstention rate (declined when the answer was there) | "
        f"{pct(report.false_abstention_rate)} |",
        "",
        "Declining means `weak_evidence` or `not_found`; only `evidence_found` "
        "asserts an answer. Outcomes across the set: "
        + ", ".join(f"`{k}` {v}" for k, v in report.outcomes.items())
        + ".",
        "",
        "## Retrieving versus asserting",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Retrieved an answering document (top {report.retrieval_depth}) | "
        f"{pct(report.retrieval_success_rate)} |",
        f"| ...and asserted it as evidence | {pct(report.answer_rate)} |",
        f"| Of the leads, the right document was first | " f"{pct(report.lead_first_rate)} |",
        "",
        "The gap between those two rows is the system finding the right "
        "document and declining to call it an answer, because none of the "
        "question's words appear in it. Verdicts: "
        + ", ".join(f"`{k}` {v}" for k, v in report.verdicts.items())
        + ".",
        "",
        "## Ranking",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k in sorted(report.recall_at_k):
        lines.append(f"| Recall@{k} | {num(report.recall_at_k[k])} |")
    lines += [
        f"| MRR | {num(report.mrr)} |",
        f"| nDCG@{min(NDCG_K, report.retrieval_depth or NDCG_K)} | "
        f"{num(report.ndcg_at_10)} |",
        f"| Precision@5 | {num(report.precision_at_5)} |",
        "",
        f"Retrieval depth was {report.retrieval_depth}, so no cut-off above "
        "that is reported. Recall and MRR are averaged over the answerable "
        "questions only; an unanswerable question has no recall, and scoring it "
        "zero would make honest abstention look like failed retrieval.",
        "",
        "## Per question",
        "",
        "| # | Question | Outcome | Hit | Top source |",
        "|---|---|---|---|---|",
    ]
    for r in report.results:
        mark = "yes" if r.correct else "**no**"
        top = f"`{r.retrieved[0]}`" if r.retrieved else "—"
        lines.append(f"| {r.id} | {r.question} | {r.outcome} | {mark} | {top} |")
    failures = [r for r in report.results if not r.correct]
    if failures:
        lines += ["", "## Failures (missed or wrongly asserted)", ""]
        for r in failures:
            lines.append(
                f"- **{r.id}** ({r.kind}, {r.outcome}) — {r.question}"
                + (f" Retrieved `{r.retrieved[0]}` instead." if r.retrieved else "")
                + (f" Label note: {r.note}" if r.note else "")
            )
    return "\n".join(lines) + "\n"


def write_report(report: EvalReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(report), encoding="utf-8")
    return path
