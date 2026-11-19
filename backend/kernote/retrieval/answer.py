"""Evidence composition — the honest half of ADR-0015's F3.

There is no LLM in the core loop (ADR-0006), so this module does **not** write
an answer. It returns the evidence that bears on a question, each item labelled
and cited, and it says so plainly rather than dressing retrieval up as
comprehension.

Three outcomes, and the third matters as much as the first:

* `evidence_found`   — retrieved records that genuinely overlap the question.
* `weak_evidence`    — something was retrieved, but nothing overlaps the terms
                       asked about. Reported as weak rather than presented as
                       an answer.
* `not_found`        — nothing retrieved. "Evidence was not found" is a correct
                       outcome, not a failure (the project contract, memory quality rules).

Every item is labelled `evidence` (quoted from a source) or `inference` (a
model-generated or derived interpretation), because the contract requires
answers to distinguish evidence, inference and unknowns.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field

import structlog

from ..db.connection import transaction
from ..domain.models import new_id, utc_now
from . import fts, hybrid

log = structlog.get_logger(__name__)

# How many content terms an item must mention to count as support. One is too
# few: "what is the airspeed velocity of an unladen swallow" was reported as
# `evidence_found` because the project contract contains "Do not **swallow** errors" -- a
# single coincidental word out of four. Capped at the number of terms actually
# asked, so a one-word question still works.
_MIN_OVERLAP = 2

# Support also requires matching a meaningful share of what makes the question
# *specific*, measured as inverse document frequency over this project's own
# records. Two common words are not evidence: in a repository about orders,
# matching "delivery" and "orders" says nothing.
#
# Measured, not guessed. With an absolute bar of two terms, the Stage 8
# labelled set abstained on 0 of 6 unanswerable questions -- "what is the
# contractual delivery SLA for next-day orders" matched "delivery" and
# "orders" in the architecture document and came back `evidence_found`, while
# "SLA" and "contractual", the whole point of the question, appear nowhere in
# the corpus.
#
# 0.30 is a deliberate trade-off, not a separating line. On that set the two
# classes overlap: the weakest answerable question scores 0.26 and the
# strongest unanswerable one 0.54, so no threshold gets both right. 0.30 buys
# 4 of 6 correct abstentions for 1 false abstention in 20. It is one parameter
# fitted on 26 questions with no held-out split, so treat the measured
# abstention gain as optimistic -- see docs/DEV_HANDOFF.md.
_MIN_INFORMATION_SHARE = 0.30

# If this share or more of what was asked about appears **nowhere** in the
# project, no record can answer it and nothing is asserted. Stated to the user
# in those words, because it is a sentence a reader can act on: "a third of
# your question does not occur in this project".
#
# This replaced a share threshold that could be cleared by *breadth*. Ask "what
# is the monetary cost in dollars of one SPICE simulation run" and `monetary`
# and `dollars` -- the two words that make it unanswerable -- carry half the
# question's weight, while a document matching the five ordinary words scored
# 0.467 against a 0.30 bar and answered confidently. The more everyday words a
# question contains, the easier it became to answer it without addressing it.
#
# Invisible on the synthetic fixture; it appeared the first time the labelled
# set was run against a real repository, where useful abstention measured
# **0 of 4** (ADR-0033).
#
# A per-item "match the heaviest term" rule was tried first and rejected on
# measurement: it refused correct answers whenever the question's subject words
# were common enough in the corpus to weigh zero, so an incidental absent word
# became the peak. The absent-term share beat it on both corpora -- on the real
# repository it reaches 4 of 4 correct abstentions with **no** increase in
# false abstention, where the peak rule reached 3 of 4 and cost two answers.
_MAX_ABSENT_TERM_SHARE = 0.30

# A term matched in a record's own *title* counts for more than one mentioned
# in passing. Inverse document frequency says how *rare* a term is, not how
# *central* it is to the question, and in a small corpus an incidental rare
# word outranks the subject: for "why was MongoDB removed from the stack" the
# document that answers it matched `mongodb` and scored 0.283, while a
# distractor matched `stack` alone and scored 0.385 (open question Q6).
#
# Title agreement was chosen by measurement over the three other candidates.
# Across both corpora it favoured the answering record 5 times and a
# distractor 0 times; entity membership scored 2-0, question capitalisation
# 2-0, and *position in the question* -- which the open question suggested --
# was actively harmful at 1 for and 2 against.
#
# It applies to both tests a record must pass -- the overlap count and the
# information share -- because the flat two-term overlap bar is what actually
# refused the Q6 case. The share is capped at 1.0, so a boost can rescue a
# record that was below the bar but never manufacture support for a question
# whose terms are absent; the ADR-0033 veto still stands in front of both.
#
# 2.0 is structural rather than fitted: `_MIN_OVERLAP` is 2, so this is exactly
# "a term in the record's own title is worth the overlap bar by itself". 1.6
# changed no verdict because it could not clear that bar; 3.0 changed none
# either, so the value is not balanced on a knife edge.
_TITLE_MATCH_BOOST = 2.0

# Stopwords are kept for *retrieval* (bm25 handles them, and dropping them
# would hurt recall on short questions) but must not count as support.
# Without this, "what is the airspeed velocity of an unladen swallow" matched
# "an", "is", "of" and "the" in a spec document and was reported as
# `evidence_found` -- precisely the false confidence ADR-0015 forbids.
_STOPWORDS = frozenset(
    """
    a an and are as at be been but by can could did do does for from had has
    have how i if in into is it its may might must not of on or should so such
    than that the their then there these they this those to was we were what
    when where which who why will with would you your about above after again
    all also any because before being below between both during each few more
    most no nor only other our out over own same some same too under until up
    very via while one them us
    """.split()
)


def _content_terms(terms: list[str]) -> set[str]:
    """Query terms that can actually support an answer.

    Two characters is the floor, not three: `CI`, `DB`, `UI` and `ML` are real
    technical terms, and excluding them left "what does the CI do" with no
    content terms at all, so it could only ever abstain. Stopwords already
    remove the two-letter noise words.
    """
    return {t for t in terms if t not in _STOPWORDS and len(t) >= 2}


# Suffixes stripped for the overlap check, longest first. Chopping a fixed two
# characters was the first attempt and over-matched badly: "import" became
# "impo", which is a prefix of "important", so a question about imports was
# "supported" by a sentence about importance.
_SUFFIXES = ("ingly", "edly", "ing", "ies", "ied", "ers", "est", "ed", "es", "er", "ly", "s")
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_.]*")


def _stem(term: str) -> str:
    """Strip a known inflection, never a fixed number of characters."""
    for suffix in _SUFFIXES:
        if len(term) > len(suffix) + 3 and term.endswith(suffix):
            base = term[: -len(suffix)]
            # "ies" -> "y" keeps "dependencies" and "dependency" together.
            if suffix == "ies":
                return base + "y"
            return base
    return term


def _variants(word: str) -> set[str]:
    """A word and its stem, plus the stem with a restored silent `e`.

    Stripping "ed" from "deleted" gives "delet", which does not equal
    "delete"; the same happens for "caches" and "cache". Adding the `e` form
    reunites them without reintroducing substring matching -- "import" becomes
    "importe", which still does not match "important".
    """
    stem = _stem(word)
    return {word, stem, stem + "e"}


def _mentions(haystack_stems: set[str], term: str) -> bool:
    """Whole-token comparison, not substring.

    A substring test is what let "import" match "important". Comparing stemmed
    *tokens* means a term matches only when the source actually uses that word
    or an inflection of it, which is what "this record mentions what you asked
    about" has to mean.
    """
    return bool(_variants(term) & haystack_stems)


def _document_frequency(
    conn: sqlite3.Connection, project_id: str, terms: set[str]
) -> tuple[dict[str, int], int]:
    """How many of the project's records mention each term, and how many exist.

    Counted through the FTS index, one indexed query per term. The first
    implementation scanned every memory and chunk and stemmed the text in
    Python, which measured **75ms per question on a 754-row corpus and 88-92%
    of the total cost of answering** -- a linear-time full scan added to the
    interactive path for a handful of counts.

    The FTS tables are tokenised `porter unicode61`, so these counts are
    already stem-aware; the term's own variants are OR'd in as well so a
    question's wording matches the same records `_mentions` would. Porter and
    our suffix stemmer still disagree at the margins, which can leave a count
    slightly *lower* than the exact one. That makes a term look rarer and the
    support gate stricter, never looser, so the error cannot produce false
    confidence -- only, at worst, an unnecessary abstention.
    """
    total = conn.execute(
        "SELECT (SELECT COUNT(*) FROM memories WHERE project_id=? "
        "        AND status NOT IN ('superseded','archived')) + "
        "       (SELECT COUNT(*) FROM chunks c JOIN source_files sf "
        "        ON sf.id=c.source_file_id WHERE c.project_id=? "
        "        AND sf.is_current=1) AS c",
        (project_id, project_id),
    ).fetchone()["c"]
    if not total:
        return dict.fromkeys(terms, 0), 0

    counts: dict[str, int] = {}
    for term in terms:
        match = " OR ".join(f'"{v}"' for v in sorted(_variants(term)) if v)
        if not match:
            counts[term] = 0
            continue
        row = conn.execute(
            "SELECT (SELECT COUNT(*) FROM memories_fts "
            "        JOIN memories m ON m.rowid = memories_fts.rowid "
            "        WHERE memories_fts MATCH ? AND m.project_id = ? "
            "          AND m.status NOT IN ('superseded','archived')) + "
            "       (SELECT COUNT(*) FROM chunks_fts "
            "        JOIN chunks c ON c.rowid = chunks_fts.rowid "
            "        JOIN source_files sf ON sf.id = c.source_file_id "
            "        WHERE chunks_fts MATCH ? AND c.project_id = ? "
            "          AND sf.is_current = 1) AS c",
            (match, project_id, match, project_id),
        ).fetchone()
        counts[term] = int(row["c"])
    return counts, total


def _term_weights(frequencies: dict[str, int], total: int) -> dict[str, float]:
    """How much each term would tell us, as inverse document frequency.

    A term absent from the corpus carries the *most* weight, deliberately: if a
    question turns on a word no record contains, that word is precisely what
    makes the question unanswerable, and nothing should be able to support the
    question without it.
    """
    if not total:
        return dict.fromkeys(frequencies, 1.0)
    # Clamped at zero. Unclamped, a term present in *every* record scored
    # log(N/(N+1)) -- a small negative weight, which made the total weight of
    # an all-common question negative and flipped the sign of the share. A
    # term that tells us nothing must be worth nothing, not less than nothing.
    return {
        term: max(0.0, math.log(total / (1 + count))) for term, count in frequencies.items()
    }


def _stems_of(text: str) -> set[str]:
    stems: set[str] = set()
    for token in _TOKEN.findall(text.lower()):
        stems |= _variants(token)
    return stems


@dataclass
class EvidenceItem:
    kind: str  # "evidence" | "inference"
    source: str  # "memory" | "chunk"
    target_id: str
    title: str
    excerpt: str
    citation: str
    confidence: float | None
    matched_terms: list[str]
    why_ranked: str


@dataclass
class AnswerBundle:
    question: str
    outcome: str  # evidence_found | weak_evidence | not_found
    statement: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    related: list[EvidenceItem] = field(default_factory=list)
    """Retrieved, but not verifiable against the question's own words.

    These used to be **discarded in silence** whenever anything else passed the
    support gate, and the record that actually answered the question was
    repeatedly among them: asked "which database does this project use and why
    was it chosen", the deciding ADR came back at rank 2 of 10 and was dropped,
    while four records that do not answer it were returned as evidence.

    They are returned now, labelled and never asserted, because "here is what I
    can verify, and here is what else I found but cannot" is the honest shape
    of the answer. `evidence` still means verified.
    """
    unknowns: list[str] = field(default_factory=list)
    semantic_available: bool = False
    note: str | None = None
    session_id: str | None = None
    turn_id: str | None = None


def _query_terms(question: str) -> list[str]:
    match = fts.build_match(question)
    if not match:
        return []
    return [part.strip('"') for part in match.split(" OR ")]


def _citation(conn: sqlite3.Connection, kind: str, target_id: str) -> tuple[str, str, str]:
    """(title, excerpt, citation) for a retrieved item."""
    if kind == "memory":
        row = conn.execute(
            "SELECT m.title, m.summary, m.content, m.claim_kind, "
            "       r.rel_path, r.line_start, r.line_end, r.user_note "
            "FROM memories m LEFT JOIN memory_source_refs r ON r.memory_id = m.id "
            "WHERE m.id = ? LIMIT 1",
            (target_id,),
        ).fetchone()
        if row is None:
            return "(missing)", "", "unknown"
        excerpt = (row["summary"] or row["content"] or "")[:500]
        if row["rel_path"] and row["line_start"]:
            citation = f"{row['rel_path']}:{row['line_start']}-{row['line_end']}"
        else:
            citation = row["rel_path"] or row["user_note"] or "user note"
        return row["title"], excerpt, citation
    row = conn.execute(
        "SELECT c.heading_path, c.text, c.line_start, c.line_end, sf.rel_path "
        "FROM chunks c JOIN source_files sf ON sf.id = c.source_file_id "
        "WHERE c.id = ?",
        (target_id,),
    ).fetchone()
    if row is None:
        return "(missing)", "", "unknown"
    return (
        row["heading_path"] or row["rel_path"],
        (row["text"] or "")[:500],
        f"{row['rel_path']}:{row['line_start']}-{row['line_end']}",
    )


def _full_text(conn: sqlite3.Connection, kind: str, target_id: str) -> str:
    """Everything an item says, for deciding support."""
    if kind == "memory":
        row = conn.execute(
            "SELECT COALESCE(summary,'') || ' ' || content AS t FROM memories WHERE id=?",
            (target_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(heading_path,'') || ' ' || text AS t FROM chunks WHERE id=?",
            (target_id,),
        ).fetchone()
    return row["t"] if row else ""


def _claim_kind(
    conn: sqlite3.Connection, kind: str, target_id: str
) -> tuple[str, float | None]:
    """Whether an item is a quoted source fact or an interpretation."""
    if kind != "memory":
        # A chunk is verbatim source text by construction.
        return "evidence", None
    row = conn.execute(
        "SELECT claim_kind, confidence FROM memories WHERE id = ?", (target_id,)
    ).fetchone()
    if row is None:
        return "evidence", None
    label = "evidence" if row["claim_kind"] == "source_fact" else "inference"
    return label, float(row["confidence"])


def ask(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    question: str,
    limit: int = 6,
    allow_download: bool = False,
    session_id: str | None = None,
) -> AnswerBundle:
    terms = _query_terms(question)
    if not terms:
        return AnswerBundle(
            question=question,
            outcome="not_found",
            statement=("That question has no searchable terms, so nothing was looked up."),
            unknowns=["the question contained no indexable words"],
        )

    outcome = hybrid.search(
        conn,
        project_id=project_id,
        query=question,
        limit=limit,
        allow_download=allow_download,
    )

    items: list[EvidenceItem] = []
    lowered = [t.lower() for t in terms]
    content_terms = _content_terms(lowered)
    if not content_terms:
        # Only stopwords were asked. Matching them would manufacture support.
        content_terms = set()
    seen_citations: set[str] = set()
    for result in outcome.results:
        title, excerpt, citation = _citation(conn, result.target_kind, result.target_id)
        label, confidence = _claim_kind(conn, result.target_kind, result.target_id)
        # Support is decided against the item's *full* text, not the excerpt
        # shown to the reader: a 500-character preview can omit the very term
        # that makes the record relevant.
        # Support is decided against the item's *full* text, not the excerpt
        # shown to the reader: a 500-character preview can omit the very term
        # that makes the record relevant.
        haystack_stems = _stems_of(
            f"{title}\n{_full_text(conn, result.target_kind, result.target_id)}"
        )
        matched = sorted(t for t in content_terms if _mentions(haystack_stems, t))
        # A memory and the chunk it came from cite the same lines; showing both
        # pads the evidence list without adding a source.
        if citation in seen_citations:
            continue
        seen_citations.add(citation)
        items.append(
            EvidenceItem(
                kind=label,
                source=result.target_kind,
                target_id=result.target_id,
                title=title,
                excerpt=excerpt,
                citation=citation,
                confidence=confidence,
                matched_terms=matched,
                why_ranked=result.why,
            )
        )

    required = min(_MIN_OVERLAP, len(content_terms)) if content_terms else 1
    frequencies, corpus_size = _document_frequency(conn, project_id, content_terms)
    weights = _term_weights(frequencies, corpus_size)
    whole = sum(weights.values())

    def information_share(item: EvidenceItem) -> float:
        # Every term is in every record, so there is nothing to discriminate
        # with and the overlap bar stands alone. Stated, rather than arrived at
        # by dividing by a negative number.
        if whole <= 0:
            return 1.0
        title_stems = _stems_of(item.title or "")
        total = 0.0
        for term in item.matched_terms:
            weight = weights.get(term, 0.0)
            if _mentions(title_stems, term):
                weight *= _TITLE_MATCH_BOOST
            total += weight
        # Capped, so a boost can only ever rescue a record, never invent a
        # share above the whole question.
        return min(1.0, total / whole)

    def effective_overlap(item: EvidenceItem) -> float:
        """Matched terms, counting a title match for more.

        A flat two-term bar is what actually refused the Q6 case: for "why was
        MongoDB removed from the stack" the record that answers it matches one
        term -- `mongodb` -- and was rejected for matching "only one word",
        never reaching the share test at all. But that word is the question's
        subject and the record's title is "Event archive in MongoDB", which is
        evidence a reader can see.
        """
        title_stems = _stems_of(item.title or "")
        return sum(
            _TITLE_MATCH_BOOST if _mentions(title_stems, term) else 1.0
            for term in item.matched_terms
        )

    def supports(item: EvidenceItem) -> bool:
        if effective_overlap(item) < required:
            return False
        return information_share(item) >= _MIN_INFORMATION_SHARE

    absent_share = (
        sum(1 for t in content_terms if frequencies.get(t, 0) == 0) / len(content_terms)
        if content_terms
        else 0.0
    )
    too_much_unknown = absent_share >= _MAX_ABSENT_TERM_SHARE

    supported = [] if too_much_unknown else [i for i in items if supports(i)]

    # When nothing is lexically supported, the answer is a set of *leads*, and
    # the fusion ordering is the wrong one for that job: it is dominated by
    # keyword hits, which are precisely what has already failed. Measured on
    # the Stage 8 labelled set, the document that actually answers a
    # paraphrased question sits at rank 1 for 4 of 6 such questions under
    # semantic ordering against 2 of 6 under the fusion -- on q29 it is first
    # by meaning, fourth by fusion and eleventh by keyword. So leads are
    # ordered by meaning when a semantic signal exists (ADR-0032).
    semantic_rank = {
        (r.target_kind, r.target_id): r.semantic_rank
        for r in outcome.results
        if r.semantic_rank is not None
    }
    leads_reordered = False
    if not supported and semantic_rank:
        items.sort(key=lambda i: semantic_rank.get((i.source, i.target_id), 10**6))
        leads_reordered = True
    unmatched = sorted(content_terms - {t for i in items for t in i.matched_terms})
    # What the question turned on and no record mentioned, heaviest first.
    matched_anywhere = {t for i in items for t in i.matched_terms}
    missing_distinctive = sorted(
        (t for t in content_terms - matched_anywhere),
        key=lambda t: -weights.get(t, 0.0),
    )
    if not items:
        bundle = AnswerBundle(
            question=question,
            outcome="not_found",
            statement=(
                "Evidence was not found. Nothing in this project's memory or "
                "indexed sources matches that question."
            ),
            unknowns=[f"no source mentions: {', '.join(terms[:8])}"],
            semantic_available=outcome.semantic_available,
            note=outcome.note,
        )
    elif not supported:
        bundle = AnswerBundle(
            question=question,
            outcome="weak_evidence",
            statement=(
                (
                    f"{round(absent_share * 100)}% of what you asked about does "
                    "not occur anywhere in this project, so no record here can "
                    "answer it. The closest records are listed as leads."
                    if too_much_unknown
                    else "No source directly addresses that question. The closest "
                    "records are listed, but none of them mentions what makes the "
                    "question specific, so treat them as leads rather than as an "
                    "answer."
                )
                + (
                    " They are ordered by meaning rather than by keyword, "
                    "because the keywords are what failed."
                    if leads_reordered
                    else ""
                )
            ),
            evidence=items,
            unknowns=(
                [f"not mentioned in any source: {', '.join(missing_distinctive[:8])}"]
                if missing_distinctive
                else [f"not mentioned in any source: {', '.join(unmatched[:8])}"]
                if unmatched
                else []
            ),
            semantic_available=outcome.semantic_available,
            note=outcome.note,
        )
    else:
        facts = sum(1 for i in supported if i.kind == "evidence")
        inferences = len(supported) - facts
        asserted = {id(i) for i in supported}
        related = [i for i in items if id(i) not in asserted]
        bundle = AnswerBundle(
            question=question,
            outcome="evidence_found",
            statement=(
                f"{len(supported)} supporting record(s) found: {facts} quoted from "
                f"source, {inferences} interpretation(s). Kernote returns the "
                "evidence rather than composing an answer, so read the citations."
                + (
                    f" {len(related)} further record(s) were retrieved but do not "
                    "mention what you asked about; they are listed as related, "
                    "not as evidence."
                    if related
                    else ""
                )
            ),
            evidence=supported,
            related=related,
            unknowns=[f"no source mentions: {', '.join(unmatched[:8])}"] if unmatched else [],
            semantic_available=outcome.semantic_available,
            note=outcome.note,
        )

    _persist(conn, project_id, session_id, bundle, outcome)
    return bundle


def _persist(
    conn: sqlite3.Connection,
    project_id: str,
    session_id: str | None,
    bundle: AnswerBundle,
    outcome: hybrid.SearchOutcome,
) -> None:
    """Record the turn with its full retrieval trace.

    Session state is kept separate from durable memory (MEMORY_MODEL.md §8):
    these tables are purgeable and nothing here is promoted into the vault.
    The trace exists so a bad answer is debuggable after the fact.
    """
    with transaction(conn):
        if session_id is None:
            session_id = new_id()
            conn.execute(
                "INSERT INTO ask_sessions(id,project_id,created_at) VALUES(?,?,?)",
                (session_id, project_id, utc_now()),
            )
        elif (
            conn.execute(
                "SELECT 1 FROM ask_sessions WHERE id=? AND project_id=?",
                (session_id, project_id),
            ).fetchone()
            is None
        ):
            conn.execute(
                "INSERT INTO ask_sessions(id,project_id,created_at) VALUES(?,?,?)",
                (session_id, project_id, utc_now()),
            )
        turn_id = new_id()
        conn.execute(
            "INSERT INTO ask_turns(id,session_id,question,answer,citations_json,"
            "trace_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (
                turn_id,
                session_id,
                bundle.question,
                bundle.statement,
                json.dumps([i.citation for i in bundle.evidence]),
                json.dumps(
                    {
                        "outcome": bundle.outcome,
                        "keyword_hits": outcome.keyword_hits,
                        "semantic_hits": outcome.semantic_hits,
                        "semantic_available": outcome.semantic_available,
                        "ranked": [
                            {
                                "kind": i.source,
                                "id": i.target_id,
                                "matched_terms": i.matched_terms,
                                "why": i.why_ranked,
                            }
                            for i in bundle.evidence
                        ],
                        "unknowns": bundle.unknowns,
                    }
                ),
                utc_now(),
            ),
        )
    bundle.session_id = session_id
    bundle.turn_id = turn_id
