"""Request/response DTOs. Validation and serialization only."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..domain.models import Memory, Project


class RegisterProject(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    root_path: str = Field(min_length=1)


class ProjectDetail(BaseModel):
    project: Project
    counts: dict[str, int]


class MemoryDetail(BaseModel):
    memory: Memory
    citations: list[str]
    revisions: list[dict]


class UpdateMemory(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    change_reason: str = Field(min_length=1, max_length=500)


class CreateMemory(BaseModel):
    type: str
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    summary: str | None = None
    user_note: str = Field(default="asserted by user in the UI", max_length=500)
    # Temporal validity is optional but first-class: when this was true of the
    # project, not when the row was written.
    valid_from: str | None = None
    valid_until: str | None = None
    # Decision payload: chosen option, alternatives, status. Only for decisions.
    decision: dict | None = None


class SupersedeMemory(BaseModel):
    """Replace a memory with a newer claim, keeping the old one intact."""

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    summary: str | None = None
    reason: str = Field(min_length=1, max_length=500)
    valid_from: str | None = None
    decision: dict | None = None


class SupersedeResult(BaseModel):
    superseded: Memory
    replacement: Memory
    note: str = "the superseded record is retained and stays fetchable by id"
