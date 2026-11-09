"""Ranking metrics, from the standard definitions.

These are implemented here rather than taken from `ranx` because `ranx` pulls
numba, llvmlite, pandas, scipy, matplotlib and seaborn — 22 packages for three
formulas, in a product whose selling point is that it installs and runs on a
modest laptop with no heavy stack. `ranx` stays the *authority*: it is pinned
in `requirements-eval.txt` and `tests/unit/test_eval_metrics.py` asserts these
functions agree with it, skipping when it is not installed. A library we trust
checks our arithmetic without becoming a prerequisite for `pytest`.

Conventions, so the reported numbers can be compared with anything else:

* `ranked` is a list of document keys, best first. Duplicates are **collapsed
  here** rather than trusted to the caller: counting a repeated key twice
  reported Recall 1.0 when one of two answering documents had been found, and
  a metric that reads 1.0 on a half-success is worse than no metric.
* `grades` maps a document key to a positive integer relevance grade. A key
  absent from `grades` has grade 0.
* **Recall@k** counts only *fully* relevant documents — grade >= `RELEVANT`.
  A merely related document should not be able to score a recall point.
* **nDCG@k** uses the **linear (Järvelin) gain** — gain is the grade itself —
  with the `log2(rank + 1)` discount, normalised by the best ordering actually
  achievable from `grades`.

  There are two nDCG conventions in circulation and they give different
  numbers: the linear gain above, and the exponential `2**grade - 1` gain used
  by `trec_eval` and much of the learning-to-rank literature. This module was
  first written with the exponential one and a docstring asserting `ranx` used
  it too. `ranx` disagreed on the first cross-check — 0.3192 against our 0.3053
  — and `ranx` was right. The default is now the linear form, so the headline
  figure is comparable with the tool that checks it; `exponential_gain=True`
  gives the other convention for anyone comparing against `trec_eval`.

  The lesson is the one the cross-check exists for: a metric that is 4% off is
  far more dangerous than one that crashes.
"""

from __future__ import annotations

import math

# The grade at which a document is treated as answering the question, not
# merely relating to it. The question set documents the scale it labels with.
RELEVANT = 2


def _fully_relevant(grades: dict[str, int]) -> set[str]:
    return {key for key, grade in grades.items() if grade >= RELEVANT}


def _distinct(ranked: list[str], k: int) -> list[str]:
    """The first `k` positions, with repeats dropped and order kept."""
    seen: set[str] = set()
    out: list[str] = []
    for key in ranked[:k]:
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def recall_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float:
    """Share of the answering documents that appear in the top `k`.

    Undefined with no answering document, which is a *labelling* question, not
    a retrieval result: an unanswerable question has no recall and the caller
    must not average one in. Returns `float("nan")` so a silent 0.0 cannot
    drag an average down.
    """
    relevant = _fully_relevant(grades)
    if not relevant or k <= 0:
        # k <= 0 measures nothing. Returning 0.0 -- as this did -- would be a
        # score, and `mean` would average it in and drag the result down.
        return float("nan")
    hits = sum(1 for key in _distinct(ranked, k) if key in relevant)
    return hits / len(relevant)


def precision_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float:
    """Share of the top `k` that answer the question.

    Divided by `k`, not by the number returned: a system that returns two
    results and gets both right has not achieved precision 1.0 at 5.
    """
    if k <= 0:
        return float("nan")
    hits = sum(1 for key in _distinct(ranked, k) if key in _fully_relevant(grades))
    return hits / k


def reciprocal_rank(ranked: list[str], grades: dict[str, int]) -> float:
    """1 / the rank of the first answering document, or 0.0 if none appears.

    0.0 is correct here rather than nan: the question *had* an answer and the
    ranking never surfaced it, which is a real score of zero.
    """
    relevant = _fully_relevant(grades)
    if not relevant:
        return float("nan")
    for index, key in enumerate(_distinct(ranked, len(ranked)), start=1):
        if key in relevant:
            return 1.0 / index
    return 0.0


def dcg(gains: list[int], *, exponential_gain: bool = False) -> float:
    """Discounted cumulative gain. See the module docstring on the two gains."""

    def gain_of(grade: int) -> float:
        return float(2**grade - 1) if exponential_gain else float(grade)

    return sum(gain_of(gain) / math.log2(rank + 1) for rank, gain in enumerate(gains, start=1))


def ndcg_at_k(
    ranked: list[str],
    grades: dict[str, int],
    k: int,
    *,
    exponential_gain: bool = False,
) -> float:
    """Graded gain, discounted by rank, normalised by the best possible order."""
    if not grades:
        return float("nan")
    actual = dcg([grades.get(key, 0) for key in ranked[:k]], exponential_gain=exponential_gain)
    ideal = dcg(sorted(grades.values(), reverse=True)[:k], exponential_gain=exponential_gain)
    if ideal == 0:
        return float("nan")
    return actual / ideal


def mean(values: list[float]) -> float:
    """Mean over the values that are defined.

    Averaging `nan` away rather than treating it as zero is the whole reason
    these functions return it: an unanswerable question has no Recall@k, and
    counting it as 0.0 would make honest abstention look like failed retrieval.
    """
    defined = [v for v in values if not math.isnan(v)]
    if not defined:
        return float("nan")
    return sum(defined) / len(defined)
