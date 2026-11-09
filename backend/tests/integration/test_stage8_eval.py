"""Stage 8: the evaluation harness, run against the real corpus.

These are regression guards on *measured* behaviour. The numbers are floors,
not targets: they are set below what was measured so an honest improvement
never fails the suite, but the specific defects Stage 8 found cannot come back.
"""

from __future__ import annotations

import math

import pytest

from kernote.eval import questions as qmod
from kernote.eval import runner
from kernote.retrieval import answer as answer_mod


@pytest.fixture(scope="module")
def question_set():
    return qmod.load()


@pytest.fixture
def scanned(conn, question_set):
    project_id, memories = runner.prepare_corpus(conn, question_set)
    assert memories > 20, "the corpus produced too little to measure"
    return project_id


@pytest.fixture
def report(conn, question_set, scanned):
    return runner.run(conn, question_set=question_set, project_id=scanned)


def test_every_question_is_accounted_for(report, question_set):
    assert report.questions == len(question_set.questions)
    assert len(report.results) == report.questions
    assert report.answerable + report.unanswerable == report.questions
    # Every answerable question lands in exactly one verdict bucket.
    buckets = {"answered", "lead_only", "missed"}
    answerable = [r for r in report.results if r.kind == "answerable"]
    assert all(r.verdict in buckets for r in answerable)
    assert sum(report.verdicts.values()) == report.questions


def test_it_declines_on_most_unanswerable_questions(report):
    """The defect Stage 8 was built to find.

    An absolute two-term support bar let "what is the contractual delivery SLA"
    match "delivery" and "orders" and come back `evidence_found`: 0 of 6
    unanswerable questions were declined. Support now needs a share of the
    question's inverse-document-frequency weight.
    """
    assert report.useful_abstention_rate >= 0.5


def test_it_does_not_invent_an_answer_about_an_sla(conn, scanned, question_set):
    """Named regression for the specific case above."""
    question = next(q for q in question_set.questions if q.id == "q21")
    bundle = answer_mod.ask(conn, project_id=scanned, question=question.question, limit=10)
    assert bundle.outcome != "evidence_found", bundle.statement
    assert bundle.unknowns, "it must say which term it could not find"
    assert any("sla" in u.lower() for u in bundle.unknowns)


def test_a_common_word_alone_is_not_support(conn, scanned):
    """Two words that appear everywhere in the corpus are not evidence."""
    bundle = answer_mod.ask(
        conn,
        project_id=scanned,
        question="What is the warehouse forklift certification for orders?",
        limit=10,
    )
    assert bundle.outcome != "evidence_found", bundle.statement


def test_retrieving_and_asserting_are_reported_separately(report):
    """Conflating them hid that the system finds the right document and then
    declines to call it an answer, which is a different problem with a
    different fix."""
    assert report.retrieval_success_rate >= report.answer_rate
    assert not math.isnan(report.retrieval_success_rate)
    gap = report.retrieval_success_rate - report.answer_rate
    lead_only = report.verdicts.get("lead_only", 0)
    assert (gap > 0) == (lead_only > 0)


def test_it_answers_a_reasonable_share_of_answerable_questions(report):
    """A floor, so a retrieval regression is caught. Measured well above this."""
    assert report.retrieval_success_rate >= 0.4
    assert report.answer_rate >= 0.3
    assert report.citation_correctness >= 0.3


def test_recall_is_not_scored_on_unanswerable_questions(report):
    """Scoring them 0.0 would make honest abstention look like failed
    retrieval, and would quietly drag every average down."""
    for result in report.results:
        if result.kind == "unanswerable":
            assert math.isnan(result.recall[5])
            assert math.isnan(result.reciprocal_rank)


def test_the_report_is_json_safe_and_readable(report):
    data = report.to_dict()
    import json

    text = json.dumps(data)  # nan would raise or produce invalid JSON
    assert "NaN" not in text
    assert data["recall_at_k"]["5"] is None or 0.0 <= data["recall_at_k"]["5"] <= 1.0

    markdown = runner.to_markdown(report)
    for heading in ("# Retrieval evaluation", "Citation correctness", "Verdicts:"):
        assert heading in markdown
    # The report must state its own limits rather than implying precision.
    assert "keyword only" in markdown or "semantic" in markdown


# ─── the Settings & Evaluation endpoints ───────────────────────────────────


def test_question_set_endpoint_describes_what_it_measures(client):
    response = client.get("/api/v1/evaluation/question-set")
    assert response.status_code == 200
    body = response.json()
    assert body["questions"] == body["answerable"] + body["unanswerable"]
    assert body["unanswerable"] > 0, "a set with no unanswerable questions proves nothing"
    assert any("abstention" in m for m in body["measures"])


def test_run_endpoint_scores_the_set_without_touching_the_user_vault(client, conn):
    """The fixture corpus must never land in the user's own project list."""
    before = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
    response = client.post("/api/v1/evaluation/run", json={"limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["questions"] > 0
    assert body["useful_abstention_rate"] >= 0.5
    assert "# Retrieval evaluation" in body["markdown"]
    after = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
    assert after == before, "the evaluation leaked its fixture corpus into the vault"


def test_run_endpoint_rejects_an_absurd_limit(client):
    assert client.post("/api/v1/evaluation/run", json={"limit": 0}).status_code == 422
    assert client.post("/api/v1/evaluation/run", json={"limit": 999}).status_code == 422
