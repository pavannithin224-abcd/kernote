"""Domain models. Pure: no I/O, no SQL, no network (ARCHITECTURE.md §1).

These types encode the rules from docs/MEMORY_MODEL.md §4 that the schema
alone cannot: a score is meaningless without its reason, and a memory without
provenance is only legal when a human asserted it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class MemoryType(StrEnum):
    PROJECT_FACT = "project_fact"
    ARCHITECTURE = "architecture"
    DECISION = "decision"
    PROCEDURE = "procedure"
    CONVENTION = "convention"
    GOTCHA = "gotcha"
    CURRENT_STATE = "current_state"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_REVIEW = "needs_review"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ClaimKind(StrEnum):
    SOURCE_FACT = "source_fact"
    INTERPRETATION = "interpretation"


class SkipReason(StrEnum):
    GITIGNORED = "gitignored"
    EXCLUDED = "excluded"
    BINARY = "binary"
    TOO_LARGE = "too_large"
    SECRET_SUSPECTED = "secret_suspected"  # noqa: S105 -- a skip reason, not a credential
    UNREADABLE = "unreadable"
    NOT_ALLOWLISTED = "not_allowlisted"


class SourceRef(BaseModel):
    """Where a claim came from. content_hash is always present; the git fields
    only inside a repo (ADR-0005)."""

    rel_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    content_hash: str | None = None
    git_blob_hash: str | None = None
    git_commit: str | None = None
    url: str | None = None
    user_note: str | None = None

    @property
    def citation(self) -> str:
        if self.rel_path and self.line_start:
            return f"{self.rel_path}:{self.line_start}-{self.line_end or self.line_start}"
        return self.rel_path or self.url or self.user_note or "unknown"


class Memory(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    type: MemoryType
    title: str
    content: str
    summary: str | None = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    claim_kind: ClaimKind
    importance: float
    importance_reason: str
    confidence: float
    confidence_reason: str
    extraction_method: str
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    last_verified_at: str | None = None
    # Temporal validity: when this claim was true of the project, which is not
    # the same as when the row was written. A `current_state` memory about work
    # in progress stops being true long before anyone edits it.
    valid_from: str | None = None
    valid_until: str | None = None
    # Supersession. `superseded_by` is the authoritative edge (ADR-0017);
    # `supersedes` is derived by inverse lookup and never stored twice.
    superseded_by: str | None = None
    supersedes: str | None = None
    # Decision-only payload: chosen option, alternatives, status, decided_on.
    decision: dict | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_memory_model_rules(self) -> Memory:
        # MEMORY_MODEL.md §4: a score the UI cannot explain is a bug.
        if not self.importance_reason.strip():
            raise ValueError("importance_reason is required: an unexplained score is a bug")
        if not self.confidence_reason.strip():
            raise ValueError("confidence_reason is required: an unexplained score is a bug")
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be in [0,1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        # MEMORY_MODEL.md §4: provenance is mandatory unless a human asserted it.
        if not self.source_refs and self.extraction_method != "manual":
            raise ValueError(
                f"memory extracted by {self.extraction_method!r} has no source_refs; "
                "only extraction_method='manual' may omit provenance"
            )
        if not self.title.strip():
            raise ValueError("title is required")
        # A validity window that ends before it starts is not a window.
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError(
                f"valid_until ({self.valid_until}) precedes valid_from ({self.valid_from})"
            )
        # A record cannot replace itself.
        if self.superseded_by == self.id:
            raise ValueError("a memory cannot supersede itself")
        # Supersession and active status are contradictory: if something has
        # replaced this record it must not still be served as current.
        if self.superseded_by and self.status is MemoryStatus.ACTIVE:
            raise ValueError(
                "memory has superseded_by set but status is 'active'; "
                "a replaced record must be marked 'superseded'"
            )
        # Only decisions carry a decision payload.
        if self.decision is not None and self.type is not MemoryType.DECISION:
            raise ValueError(
                f"decision payload is only valid on type='decision', not {self.type.value!r}"
            )
        return self

    @property
    def is_current(self) -> bool:
        """Active, not replaced, and inside its validity window if it has one."""
        if self.status is not MemoryStatus.ACTIVE or self.superseded_by:
            return False
        return not (self.valid_until and self.valid_until < utc_now())


class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    root_path: str
    is_git_repo: bool = False
    created_at: str = Field(default_factory=utc_now)


class SkippedFile(BaseModel):
    rel_path: str
    reason: SkipReason


class ScanResult(BaseModel):
    scan_run_id: str
    project_id: str
    status: str
    git_commit: str | None = None
    files_seen: int = 0
    files_new: int = 0
    files_skipped: int = 0
    captures_created: int = 0
    memories_created: int = 0
    skipped: list[SkippedFile] = Field(default_factory=list)
