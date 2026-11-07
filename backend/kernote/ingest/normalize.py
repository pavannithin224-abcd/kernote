"""Markdown normalisation into line-anchored chunks (L2).

Line ranges come from markdown-it-py's token.map, not from counting newlines
ourselves. That map is the reason provenance can point at exact lines, and
getting it from the parser means it stays right when the markdown is odd.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from markdown_it import MarkdownIt


@dataclass
class Section:
    heading: str | None
    heading_path: str
    level: int
    line_start: int  # 1-based, inclusive
    line_end: int  # 1-based, inclusive
    text: str
    code_blocks: list[tuple[str, str, int, int]] = field(default_factory=list)
    # (language, code, line_start, line_end)


def _inline_text(tokens: list, idx: int) -> str:
    if idx + 1 < len(tokens) and tokens[idx + 1].type == "inline":
        return tokens[idx + 1].content.strip()
    return ""


def split_markdown(text: str) -> list[Section]:
    """Split a Markdown document into heading-delimited sections.

    token.map is [start, end) and 0-based; we store 1-based inclusive lines
    because that is what a developer sees in an editor and in a citation.
    """
    md = MarkdownIt("commonmark")
    tokens = md.parse(text)
    lines = text.splitlines()
    total = len(lines)

    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (level, heading)
    current: Section | None = None

    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            heading = _inline_text(tokens, i)
            start = (tok.map[0] + 1) if tok.map else 1
            if current is not None:
                current.line_end = max(current.line_start, start - 1)
                sections.append(current)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            current = Section(
                heading=heading,
                heading_path=" > ".join(h for _, h in stack),
                level=level,
                line_start=start,
                line_end=total,
                text="",
            )
        elif tok.type == "fence" and tok.map:
            lang = (tok.info or "").strip().split()[0] if tok.info.strip() else ""
            fs, fe = tok.map[0] + 1, tok.map[1]
            if current is None:
                current = Section(None, "(preamble)", 0, 1, total, "")
            current.code_blocks.append((lang, tok.content, fs, fe))

    if current is not None:
        sections.append(current)

    if not sections and text.strip():
        sections = [Section(None, "(document)", 0, 1, total, text)]

    for s in sections:
        s.line_end = min(s.line_end, total)
        s.text = "\n".join(lines[s.line_start - 1 : s.line_end]).strip()

    return [s for s in sections if s.text]
