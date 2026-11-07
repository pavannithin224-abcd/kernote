"""Deterministic importance and confidence, each with a human-readable reason.

Every score returned here carries the signals that produced it, because
MEMORY_MODEL.md requires the UI to be able to show *why* a record ranks where
it does. No model call: this is rules, so it is reproducible and testable.
"""

from __future__ import annotations

from .models import ClaimKind, MemoryType

# A README outranks an inline comment: source authority is a real signal.
_SOURCE_AUTHORITY: tuple[tuple[str, float, str], ...] = (
    ("readme", 0.30, "README is the project's authoritative entry point"),
    ("contributing", 0.22, "CONTRIBUTING states project conventions"),
    ("claude.md", 0.22, "CLAUDE.md is an agent-facing project contract"),
    ("agents.md", 0.22, "AGENTS.md is an agent-facing project contract"),
    ("docs/", 0.18, "lives under docs/"),
    ("pyproject.toml", 0.20, "declares the Python project and its dependencies"),
    ("package.json", 0.20, "declares the Node project and its dependencies"),
    ("dockerfile", 0.15, "defines the runtime image"),
)

_TYPE_WEIGHT: dict[MemoryType, tuple[float, str]] = {
    MemoryType.DECISION: (0.30, "decisions are durable project knowledge"),
    MemoryType.ARCHITECTURE: (0.25, "architecture changes rarely and is costly to rediscover"),
    MemoryType.PROCEDURE: (0.25, "setup and build steps are consulted repeatedly"),
    MemoryType.PROJECT_FACT: (0.20, "core project facts orient every reader"),
    MemoryType.CONVENTION: (0.18, "conventions govern future changes"),
    MemoryType.GOTCHA: (0.15, "gotchas prevent repeated mistakes"),
    MemoryType.CURRENT_STATE: (0.08, "current state is volatile by nature"),
}


def score_importance(
    *, memory_type: MemoryType, rel_path: str | None, heading_depth: int = 1
) -> tuple[float, str]:
    signals: list[str] = []
    base, why = _TYPE_WEIGHT[memory_type]
    score = base
    signals.append(f"type={memory_type.value} (+{base:.2f}, {why})")

    if rel_path:
        low = rel_path.lower()
        for needle, weight, why in _SOURCE_AUTHORITY:
            if needle in low:
                score += weight
                signals.append(f"source={rel_path} (+{weight:.2f}, {why})")
                break
        else:
            signals.append(f"source={rel_path} (+0.00, no special authority)")

    # A top-level heading says more about the project than a deep subsection.
    if heading_depth > 2:
        penalty = min(0.10, 0.03 * (heading_depth - 2))
        score -= penalty
        signals.append(f"heading depth {heading_depth} (-{penalty:.2f}, deeply nested)")

    score = max(0.0, min(1.0, score))
    return round(score, 3), "; ".join(signals)


def score_confidence(
    *, claim_kind: ClaimKind, extraction_method: str, has_line_range: bool
) -> tuple[float, str]:
    signals: list[str] = []
    if claim_kind is ClaimKind.SOURCE_FACT:
        score = 0.75
        signals.append("claim is a source fact, not an interpretation (+0.75)")
    else:
        score = 0.45
        signals.append("claim is an interpretation, not quoted from source (+0.45)")

    if extraction_method.startswith("rule:"):
        score += 0.15
        signals.append(f"{extraction_method} is deterministic and reproducible (+0.15)")
    elif extraction_method == "manual":
        score += 0.20
        signals.append("asserted directly by a human (+0.20)")
    elif extraction_method.startswith("model:"):
        signals.append(f"{extraction_method} output is model-generated (+0.00)")

    if has_line_range:
        score += 0.05
        signals.append("pinned to an exact line range (+0.05)")
    else:
        signals.append("no line range available (+0.00)")

    score = max(0.0, min(1.0, score))
    return round(score, 3), "; ".join(signals)
