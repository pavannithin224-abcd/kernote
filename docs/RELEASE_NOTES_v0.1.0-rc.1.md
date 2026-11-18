# Kernote v0.1.0-rc.1

**Release candidate.** Local-first, evidence-backed project memory for
developers and coding agents. MIT licensed.

`Kernote` is a provisional working name pending trademark, domain and registry
clearance (`docs/PRODUCT_SPEC.md` §9). The mark in `design/logo/` needs the
same clearance before public use.

---

## What works, end to end

Register a local project, scan it read-only, and you get a typed memory vault
with line-exact provenance. From there:

- **Scanning** runs under a built-in allowlist that refuses secrets, binaries
  and build output, honours `.gitignore`, and explains every file it skipped.
  `.kernote.toml` widens or narrows it; exclude always beats include, and
  include can never override a secret refusal.
- **Memory records** are typed — facts, architecture, decisions, procedures,
  conventions, gotchas, current state — each carrying repository, path, line
  range, content hash, capture time and extraction method, plus full revision
  history.
- **Answers** cite their sources and label every claim as evidence, inference
  or unknown. When there is nothing to cite it says so rather than composing
  prose around a guess.
- **Drift detection** diffs the stored capture against the working tree and
  shows the overlapping hunk that triggered the concern, not just "the repo
  changed". It needs no Git on `PATH`.
- **Conflicts stay open.** Two disagreeing sources both remain visible with
  their origins and dates until a human resolves it. Nothing picks a winner
  silently.
- **Consolidation** proposes duplicate merges with a before/after preview.
  Approval preserves lineage: the absorbed record keeps its own provenance and
  passes it onto the keeper, so merges add citations rather than lose them.
- **Context export and a read-only MCP surface** serve approved context to
  coding agents, budgeted by token count.

`scripts/demo.py` is the release gate and exercises all of the above against
the real API on a copy of `samples/eval-repo`, in a temporary data directory.
It is verified from a clean clone and exits non-zero on any failed step.

## New since the last tag

The tag previously sat 17 commits back. What landed in between:

- **Approval undo.** Consolidation approvals and finding resolutions can be
  reversed. Proven on production rows, not a fixture: a real merge undone and
  re-applied returned the vault to byte-identical counts.
- **Packaged as a self-contained binary** via PyInstaller (`kernote.spec`),
  with a pywebview desktop shell that degrades gracefully to the browser when
  no webview is present.
- **Backup, restore and export** using SQLite's online backup API rather than
  a file copy, so a snapshot taken during a write is still consistent.
- **An interactive knowledge graph** over real relationship data, plus a
  Memory Pulse view. Neither fabricates nodes or edges; both show explicit
  loading, empty and error states and honour reduced-motion.
- **Curated relationships** — confirm, dismiss and remove links, with ranked
  suggestions weighted by entity specificity, and rejected pairs excluded from
  future suggestions.
- **Background indexing** through a single-worker job runner, so a scan no
  longer blocks the request.
- **Bulk curation** for relationship links.
- **Command palette** and a data & privacy panel.
- **Accessibility pass** and a visual pass across the screens, with a logo and
  startup reveal.
- **A scanner correctness fix (ADR-0049):** a re-scan now supersedes the
  previous reading instead of duplicating it. The duplicate backlog that bug
  produced has been cleared — 85 byte-identical pairs merged, nothing deleted,
  zero dropped citations.
- Cache headers, conditional CORS registration, and the npm advisories cleared.

## Verified

Run on Linux (WSL2), 2026-11-18, at the tagged commit:

| Check | Result |
|---|---|
| `pytest backend/tests` | **533 passed, 7 skipped** |
| ruff | clean |
| `npm run typecheck` (`tsc -b`) | clean |
| eslint | clean |
| frontend build | succeeds (warns that the 522 kB JS chunk is over Vite's 500 kB advisory limit; 163 kB gzipped) |

The 7 skips are honest: 5 need `requirements-eval.txt`, which CI deliberately
does not install, and 2 are corpus-dependent suggestion tests that skip when
the fixture produces no suggestions.

**Native Windows** was verified separately at an earlier commit (ADR-0009a /
0009b): dependencies install from prebuilt wheels, the end-to-end demo passes,
and a Windows scan produced the same 51 memories with the same retrieval
metrics as Linux. The 3 failures there were all Change Impact, which needs Git
on `PATH`. Windows has not been re-run against this commit, and the frontend
build remains untested there — that install has no Node.

## Measured retrieval quality

Numbers, not adjectives — `docs/EVALUATION.md` has the method. On a 31-question
labelled set:

- citation correctness **55%**
- useful abstention **83%**
- Recall@5 **0.98**
- on a real sibling repository it declines on **4 of 4** unanswerable questions

Retrieval surfaces an answering document for every answerable question and
asserts one for 60%, showing the rest as retrieved-but-unverified rather than
hiding them. The known weakness is the opposite error: on 24% of answerable
questions it finds the right document and declines to call it an answer,
because a paraphrased question shares no words with its source. When it cannot
assert, it returns leads ordered by meaning, and the right document is first in
67% of those cases. ADR-0032 explains why assertion stays lexical; ADR-0030 why
the remaining gap is a centrality problem.

## Known limitations

- Answers are **extractive**, not generated prose. Kernote does not compete
  with frontier-LLM codebase chat on fluency; it competes on whether the
  citations are correct and the abstentions honest.
- Extraction is deterministic and rule-based by default, so recall is lower
  than an LLM pipeline would give. A model adapter is optional and additive
  (ADR-0006).
- **Tested languages:** symbols are extracted for Python, TypeScript, TSX and
  JavaScript. Markdown and `pyproject.toml` / `package.json` /
  `requirements.txt` manifests parse everywhere. Anything else is stored as
  text without symbol extraction, and nothing further is claimed.
- **Tested agent:** the MCP surface is verified against a real client over
  stdio, driven only from Claude Code.
- 478 open `stale_risk` findings remain in the maintainer's own vault from
  documentation edits — a backlog, not a defect.
- Consolidations have no batch approval endpoint; only relationship links do.
- The README demo video is **illustrative**: the question and citations in it
  were written for the video, not produced by a real vault.
- Not code-signed, and there is no installer wrapper yet.

## Install

Requires Python 3.12+, Node 20 LTS and Git 2.40+.

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt
npm --prefix frontend install
backend/.venv/bin/honcho start
```

Then open http://localhost:5173. The API serves `127.0.0.1:8787` and the web app
proxies `/api` to it, so the browser only ever talks to one origin.

`requirements-ml.txt` is optional and is never installed by CI or by the
commands above — that is what keeps "works with no ML stack and no paid API"
true rather than aspirational.

## Privacy

No telemetry. No outbound network calls by default. Scanning is read-only and
Kernote never writes into your repository. Any remote provider is opt-in and
must state what leaves the machine.
