# Per-language symbol queries

One `tags.scm` per language, in the shape `cased/kit` uses (ADR-0012): adding a
language is a new query file plus a test, never a change to core logic.

The capture contract each file must satisfy:

* `@name`   — the symbol's identifier node (required)
* `@definition.<kind>` — the whole definition node, where `<kind>` becomes the
  symbol kind shown to the user (class, function, method, interface, type)

Approach seeded from Aider's `aider/queries/` (Apache-2.0,
https://github.com/Aider-AI/aider) — the idea of per-language tag queries is
theirs; these queries are written for Kernote's narrower needs.

**A language is only supported once it has a query file and a passing test.**
That is how `CLAUDE.md`'s "do not claim support for languages that have not
been tested" becomes structural rather than a promise.
