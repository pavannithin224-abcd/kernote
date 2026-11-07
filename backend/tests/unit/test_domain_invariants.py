"""MEMORY_MODEL.md §9 invariants that live in the domain layer."""

import pytest
from pydantic import ValidationError

from kernote.domain.models import ClaimKind, Memory, MemoryType, SourceRef
from kernote.domain.scoring import score_confidence, score_importance


def _memory(**over):
    base = {
        "project_id": "p",
        "type": MemoryType.PROJECT_FACT,
        "title": "t",
        "content": "c",
        "claim_kind": ClaimKind.SOURCE_FACT,
        "importance": 0.5,
        "importance_reason": "because",
        "confidence": 0.5,
        "confidence_reason": "because",
        "extraction_method": "manual",
    }
    base.update(over)
    return Memory(**base)


def test_invariant_3_rule_extraction_requires_provenance():
    with pytest.raises(ValidationError, match="no source_refs"):
        _memory(extraction_method="rule:markdown_sections", source_refs=[])


def test_invariant_3_manual_may_omit_provenance():
    assert _memory(extraction_method="manual", source_refs=[]).id


def test_model_extraction_also_requires_provenance():
    with pytest.raises(ValidationError, match="no source_refs"):
        _memory(extraction_method="model:qwen3-1.7b@q4", source_refs=[])


@pytest.mark.parametrize("field", ["importance_reason", "confidence_reason"])
def test_scores_require_a_reason(field):
    with pytest.raises(ValidationError, match="required"):
        _memory(**{field: "   "})


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_scores_bounded(value):
    with pytest.raises(ValidationError):
        _memory(importance=value)


def test_title_required():
    with pytest.raises(ValidationError, match="title is required"):
        _memory(title="  ")


def test_scoring_always_explains_itself():
    score, reason = score_importance(memory_type=MemoryType.DECISION, rel_path="README.md")
    assert 0 <= score <= 1
    assert "decision" in reason and "README" in reason

    score, reason = score_confidence(
        claim_kind=ClaimKind.INTERPRETATION,
        extraction_method="model:x@1",
        has_line_range=False,
    )
    assert 0 <= score <= 1
    assert "interpretation" in reason


def test_interpretation_scores_below_source_fact():
    fact, _ = score_confidence(
        claim_kind=ClaimKind.SOURCE_FACT, extraction_method="rule:x", has_line_range=True
    )
    interp, _ = score_confidence(
        claim_kind=ClaimKind.INTERPRETATION, extraction_method="rule:x", has_line_range=True
    )
    assert fact > interp


def test_citation_format():
    assert SourceRef(rel_path="a/b.md", line_start=3, line_end=9).citation == "a/b.md:3-9"
    assert SourceRef(user_note="asserted by user").citation == "asserted by user"
