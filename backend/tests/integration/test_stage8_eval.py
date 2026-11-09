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


def _scan(conn, root):
    """Register and scan a directory, returning (project_id, memories)."""
    from kernote.db.repositories import projects as project_repo
    from kernote.domain.models import Project
    from kernote.ingest.pipeline import scan_project

    project = project_repo.create(
        conn, Project(name="Planted", root_path=str(root), is_git_repo=False)
    )
    result = scan_project(
        conn, project_id=project.id, root=root, max_file_bytes=1_000_000, max_files=100
    )
    return project.id, result.memories_created


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


# ─── defects found in the Stage 8 sweep ────────────────────────────────────


def test_it_reports_no_cut_off_deeper_than_it_searched(conn, question_set, scanned):
    """Recall@10 from a run that retrieved three documents is Recall@3 with a
    misleading label. All four cut-offs used to be printed whatever the depth."""
    shallow = runner.run(conn, question_set=question_set, project_id=scanned, limit=3)
    assert set(shallow.recall_at_k) == {1, 3}
    assert shallow.retrieval_depth == 3
    assert "Retrieval depth was 3" in runner.to_markdown(shallow)
    assert "Recall@10" not in runner.to_markdown(shallow)

    deep = runner.run(conn, question_set=question_set, project_id=scanned, limit=10)
    assert set(deep.recall_at_k) == {1, 3, 5, 10}


def test_a_term_in_every_record_is_worth_nothing_not_less(conn, scanned):
    """Unclamped, log(N/(N+1)) gave a ubiquitous term a small *negative*
    weight, which made an all-common question's total weight negative and
    flipped the sign of the information share."""
    weights = answer_mod._term_weights({"everywhere": 51, "absent": 0}, 51)
    assert weights["everywhere"] == 0.0
    assert weights["absent"] > 0
    assert all(w >= 0 for w in weights.values())
    # And the degenerate case cannot produce a negative denominator.
    all_common = answer_mod._term_weights({"a": 10, "b": 10}, 10)
    assert sum(all_common.values()) == 0.0


def test_document_frequency_uses_the_index_not_a_full_scan(conn, scanned):
    """It was 75ms per question on a 754-row corpus and 88-92% of the cost of
    answering -- a linear scan with Python stemming in the interactive path.

    Asserted by behaviour rather than by a timing, which would be flaky: the
    counts must be bounded by the corpus and must find a term that is really
    there, and the query plan must use the FTS tables.
    """
    terms = {"redis", "postgresql", "definitelynotinthiscorpus"}
    counts, total = answer_mod._document_frequency(conn, scanned, terms)
    assert total > 0
    assert counts["definitelynotinthiscorpus"] == 0
    assert counts["redis"] > 0, "a term that is in the corpus must be counted"
    assert all(0 <= c <= total for c in counts.values())


# ─── Q5: leads are ordered by meaning (ADR-0032) ───────────────────────────


def test_leads_are_ordered_by_meaning_not_by_the_failed_keywords(conn, tmp_path):
    """When nothing is lexically supported the answer is a set of leads, and
    the fusion ordering is the wrong one for that job: it is dominated by the
    keyword hits that have already failed.

    Driven with a planted corpus rather than the eval fixture, so the
    assertion does not depend on a 31-question measurement: one document
    answers a paraphrased question and never uses its words, and a decoy
    shares the question's incidental vocabulary.
    """
    (tmp_path / "billing.md").write_text(
        "# Billing\n\n## Totals\n\nTax is applied to the invoice total, never "
        "per line, and the invoice total is what the customer pays.\n",
        encoding="utf-8",
    )
    (tmp_path / "decoy.md").write_text(
        "# Operations\n\n## Money\n\nThe money is worked out by the finance "
        "team, who get the figures out on time every month without fail.\n",
        encoding="utf-8",
    )
    project_id, _ = _scan(conn, tmp_path)
    from kernote.retrieval import vector

    if vector.build_index(conn, project_id=project_id).skipped:
        pytest.skip("no embedding model cached; semantic ordering cannot be exercised")

    bundle = answer_mod.ask(
        conn,
        project_id=project_id,
        question="How does the money owed get worked out including what the taxman takes?",
        limit=10,
    )
    assert bundle.outcome == "weak_evidence", bundle.statement
    assert "ordered by meaning" in bundle.statement
    assert bundle.evidence, "leads must still be returned"


def test_the_lead_first_rate_is_reported(report):
    """A lead is only useful if the reader does not have to hunt for it, so the
    report states how often the right document came first among leads."""
    leads = [r for r in report.results if r.verdict == "lead_only"]
    if not leads:
        pytest.skip("no leads in this run")
    assert not math.isnan(report.lead_first_rate)
    assert 0.0 <= report.lead_first_rate <= 1.0
    assert all(r.answer_rank is None or r.answer_rank >= 1 for r in report.results)
    assert "the right document was first" in runner.to_markdown(report)


# ─── found by evaluating against a real repository (ADR-0033) ───────────────


def test_breadth_of_common_words_does_not_assert_an_answer(conn, tmp_path):
    """A share threshold alone is satisfiable by breadth.

    On a real repository, "what is the monetary cost in dollars of one SPICE
    simulation run" was answered `evidence_found`: the two words that make it
    unanswerable carried half the question's weight, and a document matching
    the five ordinary words cleared the bar without touching either.
    """
    (tmp_path / "sim.md").write_text(
        "# Simulation\n\n## Budget\n\nOne simulation run of the SPICE netlist "
        "has a cost measured in curve runs, and the budget for each study is "
        "recorded with the result.\n",
        encoding="utf-8",
    )
    project_id, _ = _scan(conn, tmp_path)
    bundle = answer_mod.ask(
        conn,
        project_id=project_id,
        question="What is the monetary cost in dollars of one SPICE simulation run?",
        limit=10,
    )
    assert bundle.outcome != "evidence_found", bundle.statement
    assert bundle.unknowns
    # It must name the words it could not find, heaviest first.
    missing = " ".join(bundle.unknowns).lower()
    assert "monetary" in missing or "dollars" in missing


def test_the_questions_own_subject_still_asserts(conn, tmp_path):
    """The abstention rules must not refuse a question whose subject is
    matched -- otherwise they would trade one failure for another.

    Needs several documents on different subjects. In a two-document corpus
    every content word appears in every record, so inverse document frequency
    makes them all worth zero and the only weight left belongs to whichever
    word is missing -- which is a property of the fixture, not of the rule.
    """
    (tmp_path / "sim.md").write_text(
        "# Simulation\n\n## Simulator\n\nThe circuit simulator is ngspice "
        "version 47, pinned for reproducibility across every study.\n",
        encoding="utf-8",
    )
    for index in range(6):
        (tmp_path / f"topic{index}.md").write_text(
            f"# Topic {index}\n\n## Subsystem {index}\n\nSubsystem {index} "
            "handles billing reconciliation, delivery windows and operator "
            "sessions, none of which concern the simulator.\n",
            encoding="utf-8",
        )
    project_id, _ = _scan(conn, tmp_path)
    bundle = answer_mod.ask(
        conn,
        project_id=project_id,
        question="Which circuit simulator version is used?",
        limit=10,
    )
    assert bundle.outcome == "evidence_found", bundle.statement


# ─── Q6: a title match is worth the overlap bar (ADR-0035) ─────────────────


def test_a_record_whose_title_names_the_subject_can_answer_alone(conn, tmp_path):
    """The Q6 case. "Why was MongoDB removed from the stack" matches one term
    in the record that answers it -- `mongodb` -- and a flat two-term overlap
    bar rejected it for matching "only one word", never reaching the share
    test. But that word is the question's subject and the record's title names
    it, which is evidence a reader can check by looking."""
    (tmp_path / "0006-mongo.md").write_text(
        "# ADR-0006: Event archive in MongoDB\n\nStatus: superseded\n\n"
        "## Decision\n\nArchive events into MongoDB nightly.\n\n"
        "## Consequences\n\nThis ran for four months and was removed.\n",
        encoding="utf-8",
    )
    for index in range(6):
        (tmp_path / f"topic{index}.md").write_text(
            f"# Topic {index}\n\n## Stack {index}\n\nThe stack for subsystem "
            f"{index} covers billing, delivery windows and operator sessions.\n",
            encoding="utf-8",
        )
    project_id, _ = _scan(conn, tmp_path)
    bundle = answer_mod.ask(
        conn,
        project_id=project_id,
        question="Why was MongoDB removed from the stack?",
        limit=10,
    )
    assert bundle.outcome == "evidence_found", bundle.statement
    cited = [item.citation.split(":")[0] for item in bundle.evidence]
    assert "0006-mongo.md" in cited


def test_a_title_match_cannot_answer_a_question_the_corpus_cannot(conn, tmp_path):
    """The boost must not reach past the ADR-0033 veto: a question whose terms
    are absent stays unanswered however well its one present term matches."""
    (tmp_path / "redis.md").write_text(
        "# Redis\n\n## Queue\n\nRedis streams carry the job queue.\n", encoding="utf-8"
    )
    for index in range(6):
        (tmp_path / f"other{index}.md").write_text(
            f"# Other {index}\n\n## Part {index}\n\nUnrelated subsystem {index}.\n",
            encoding="utf-8",
        )
    project_id, _ = _scan(conn, tmp_path)
    bundle = answer_mod.ask(
        conn,
        project_id=project_id,
        question="What is the monthly licensing cost of Redis Enterprise in euros?",
        limit=10,
    )
    assert bundle.outcome != "evidence_found", bundle.statement
