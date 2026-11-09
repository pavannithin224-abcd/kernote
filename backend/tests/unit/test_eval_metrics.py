"""Ranking metrics, checked against hand-worked cases and against `ranx`."""

from __future__ import annotations

import math
import random

import pytest

from kernote.eval import metrics


def test_recall_counts_only_answering_documents():
    grades = {"a": 2, "b": 1}
    # "b" is related but does not answer, so finding it is not a recall point.
    assert metrics.recall_at_k(["b"], grades, 5) == 0.0
    assert metrics.recall_at_k(["a"], grades, 5) == 1.0


def test_recall_is_undefined_without_an_answer():
    """An unanswerable question has no recall; 0.0 would libel the system."""
    assert math.isnan(metrics.recall_at_k(["a", "b"], {}, 5))
    assert math.isnan(metrics.recall_at_k(["a"], {"a": 1}, 5))


def test_reciprocal_rank_is_zero_when_the_answer_never_surfaces():
    """Distinct from nan: the answer existed and ranking failed to find it."""
    assert metrics.reciprocal_rank(["x", "y"], {"a": 2}) == 0.0
    assert metrics.reciprocal_rank(["x", "a"], {"a": 2}) == 0.5


def test_precision_divides_by_k_not_by_results_returned():
    """Two results, both right, is not precision 1.0 at 5."""
    assert metrics.precision_at_k(["a", "b"], {"a": 2, "b": 2}, 5) == pytest.approx(0.4)


def test_ndcg_is_one_for_the_ideal_order():
    grades = {"a": 3, "b": 2, "c": 1}
    assert metrics.ndcg_at_k(["a", "b", "c"], grades, 3) == pytest.approx(1.0)
    assert metrics.ndcg_at_k(["c", "b", "a"], grades, 3) < 1.0


def test_ndcg_default_is_the_linear_gain():
    """The two conventions differ, and ours must be the one ranx checks.

    Worked by hand: grades 2 then 1, in order. Linear DCG = 2/1 + 1/1.585.
    """
    ideal = 2 / math.log2(2) + 1 / math.log2(3)
    assert metrics.dcg([2, 1]) == pytest.approx(ideal)
    assert metrics.dcg([2, 1], exponential_gain=True) == pytest.approx(
        3 / math.log2(2) + 1 / math.log2(3)
    )


def test_mean_ignores_undefined_values():
    assert metrics.mean([1.0, float("nan"), 0.0]) == 0.5
    assert math.isnan(metrics.mean([float("nan")]))
    assert math.isnan(metrics.mean([]))


# ─── the cross-check against ranx ──────────────────────────────────────────


def _random_cases(seed: int = 7, n: int = 40):
    rng = random.Random(seed)  # noqa: S311 -- test fixtures, not cryptography
    qrels, run, mine = {}, {}, {}
    for q in range(n):
        docs = [f"d{i}" for i in range(12)]
        grades = {d: rng.choice([1, 2, 2, 3]) for d in rng.sample(docs, rng.randint(1, 5))}
        if not any(g >= 2 for g in grades.values()):
            grades[rng.choice(list(grades))] = 2
        ranked = rng.sample(docs, 10)
        qid = f"q{q}"
        qrels[qid] = {d: int(g) for d, g in grades.items()}
        run[qid] = {d: float(10 - i) for i, d in enumerate(ranked)}
        mine[qid] = (ranked, grades)
    return qrels, run, mine


@pytest.mark.parametrize(
    ("name", "ours", "binarise"),
    [
        ("ndcg@5", lambda r, g: metrics.ndcg_at_k(r, g, 5), False),
        ("ndcg@10", lambda r, g: metrics.ndcg_at_k(r, g, 10), False),
        ("mrr", metrics.reciprocal_rank, True),
        ("recall@5", lambda r, g: metrics.recall_at_k(r, g, 5), True),
        ("precision@5", lambda r, g: metrics.precision_at_k(r, g, 5), True),
    ],
)
def test_agrees_with_ranx(name, ours, binarise):
    """`ranx` is the authority; we only avoid depending on it at runtime.

    Skipped unless `requirements-eval.txt` is installed, so the 22-package
    numba/pandas stack is never a prerequisite for running the suite.
    """
    ranx_mod = pytest.importorskip(
        "ranx", reason="pip install -r backend/requirements-eval.txt"
    )
    qrels_d, run_d, mine = _random_cases()
    if binarise:
        qrels_d = {q: dict.fromkeys(g, 1) for q, g in qrels_d.items()}
        mine = {q: (r, dict.fromkeys(g, 2)) for q, (r, g) in mine.items()}
    theirs = float(ranx_mod.evaluate(ranx_mod.Qrels(qrels_d), ranx_mod.Run(run_d), name))
    computed = metrics.mean([ours(r, g) for r, g in mine.values()])
    assert computed == pytest.approx(theirs, abs=1e-9)


# ─── defects found in the Stage 8 sweep ────────────────────────────────────


def test_a_repeated_key_cannot_score_twice():
    """Recall read 1.0 when one of two answering documents had been found.

    `_ranked_paths` does collapse duplicates, but a metric that silently
    reports a half-success as a perfect score cannot depend on its caller
    being careful.
    """
    grades = {"a": 2, "b": 2}
    assert metrics.recall_at_k(["a", "a"], grades, 5) == 0.5
    assert metrics.precision_at_k(["a", "a"], grades, 5) == pytest.approx(0.2)
    # Rank is counted over distinct documents too.
    assert metrics.reciprocal_rank(["x", "x", "a"], {"a": 2}) == 0.5


@pytest.mark.parametrize("k", [0, -1, -10])
def test_a_cut_off_of_zero_or_less_measures_nothing(k):
    """It returned 0.0, which `mean` averaged in as a real score."""
    assert math.isnan(metrics.recall_at_k(["a"], {"a": 2}, k))
    assert math.isnan(metrics.precision_at_k(["a"], {"a": 2}, k))
    assert math.isnan(metrics.ndcg_at_k(["a"], {"a": 2}, k))
