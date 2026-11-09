"""The question set is validated, because labels rot silently."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from kernote.eval import questions as qs


def _write(tmp_path, questions, corpus="corpus"):
    (tmp_path / corpus).mkdir(exist_ok=True)
    path = tmp_path / "questions.json"
    path.write_text(json.dumps({"version": 1, "corpus": corpus, "questions": questions}))
    return path


def test_the_real_question_set_loads_and_its_labels_all_exist():
    """Guards the thing that silently lowers every score: a label pointing at
    a file that has been renamed or deleted."""
    question_set = qs.load()
    assert question_set.questions
    assert question_set.answerable and question_set.unanswerable
    ids = [q.id for q in question_set.questions]
    assert len(ids) == len(set(ids))


def test_a_label_pointing_outside_the_corpus_is_refused(tmp_path):
    path = _write(
        tmp_path,
        [{"id": "q1", "question": "?", "kind": "answerable", "relevant": {"gone.md": 2}}],
    )
    with pytest.raises(ValueError, match="not in the corpus"):
        qs.load(path)


def test_an_answerable_question_needs_a_document_that_answers_it(tmp_path):
    """Graded 1 only means nothing answers it, so recall could never score."""
    path = _write(
        tmp_path,
        [{"id": "q1", "question": "?", "kind": "answerable", "relevant": {"a.md": 1}}],
    )
    (tmp_path / "corpus" / "a.md").write_text("x")
    with pytest.raises(ValidationError, match="no document is graded"):
        qs.load(path)


def test_an_unanswerable_question_may_not_have_an_answer(tmp_path):
    path = _write(
        tmp_path,
        [{"id": "q1", "question": "?", "kind": "unanswerable", "relevant": {"a.md": 2}}],
    )
    (tmp_path / "corpus" / "a.md").write_text("x")
    with pytest.raises(ValidationError, match="graded as answering it"):
        qs.load(path)


def test_duplicate_ids_are_refused(tmp_path):
    path = _write(
        tmp_path,
        [
            {"id": "q1", "question": "a?", "kind": "unanswerable"},
            {"id": "q1", "question": "b?", "kind": "unanswerable"},
        ],
    )
    with pytest.raises(ValueError, match="duplicate question ids"):
        qs.load(path)


def test_a_grade_outside_the_documented_scale_is_refused(tmp_path):
    path = _write(
        tmp_path,
        [{"id": "q1", "question": "?", "kind": "answerable", "relevant": {"a.md": 7}}],
    )
    with pytest.raises(ValidationError, match="outside the documented"):
        qs.load(path)
