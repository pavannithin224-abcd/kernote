# Kernote — Developer Handoff

Updated at the end of every task, per the project contract §"Git and task workflow" step 7.
Newest entry first.

---

## 2026-11-19 — From localhost site to installable Windows app

Audit, fixes, packaging and a README rewrite, on native Windows (Python 3.12, Node 26).
Pushed to `main`; CI green (c116dad).

### Found by actually running it
| | |
|---|---|
| **Port probe lied on Windows** | `SO_REUSEADDR` lets a bind succeed on a *listening* port, so the launcher could not tell "already running" from "free". `SO_EXCLUSIVEADDRUSE` on win32. |
| **Windowed build died silently** | `sys.stderr is None` with no console; the first log line raised. Logs now fall back to `<data_dir>/logs/kernote.log`; startup failures reach a native dialog. |
| **93 known advisories in the pins** | starlette, mcp, pillow. Upgraded; `pip-audit` and `npm audit` both report 0. `mcp` stays on 1.x (2.x renames FastMCP). |
| **DNS rebinding / cross-site writes** | A login-less API on loopback was reachable from any page. Non-loopback `Host` and cross-origin writes now get 403 (`security.py`). |
| **No way to add a project in the UI** | `api.registerProject` was never called. Add-project dialog with folder picker and live progress. |
| **No way to remove one** | Confirmed, snapshot first, clears the FK-less `embeddings` table, never touches the user's folder. |
| **A lead was labelled "quoted from source"** | On a weak answer, irrelevant records read as evidence. They now read "lead, not an answer". |
| **Backups grew forever** | Routine snapshots pruned to 20; pre-restore / pre-remove snapshots are never pruned. |
| **MCP could not work when installed** | A windowed process has no stdio. Ships `kernote-mcp.exe` (console, same libraries via `MERGE`); the screen emits its path. |

### Verified
- `pytest`: **559 passed, 13 skipped** (572 collected), exit 0, on Windows. The 3 Git-dependent failures documented earlier no longer occur here because Git is installed.
- `ruff`, `tsc -b`, `eslint`, `npm audit`, `pip-audit`, `pip check`: clean.
- The **real installed** `kernote.exe`: window opens, fits a 1920x1080 work area, serves, logs.
- The **real installed** `kernote-mcp.exe` driven by a real MCP client over stdio: 4 tools, a cited search, a project summary.
- Install and uninstall both run: per-user, no admin; uninstall removes the program, shortcut and registry entry and **keeps the vault**.
- UI walked in a browser: all 8 routes, add project, ask, refuse, remove (on a throwaway), graph.
- Sizes: main bundle 522 kB -> 329 kB (lazy graph); bundle 177 -> 160 MB; installer 65 MB.

### Not verified, stated plainly
- ~~CI has never run.~~ **Ran on first push (c116dad): all three jobs green** (frontend, backend on Windows, backend on Linux) after two fixes the first run exposed: the runner's own `pipx` made `pip check` fail on its pin of `platformdirs`, and a new test hard-coded a Windows path that POSIX `Path` cannot parse. Both were mistakes in the CI setup and the test, not in the app. The dependency-audit workflow passed first time.
- **Semantic search end to end** on the upgraded fastembed (0.5.1 -> 0.9.1). Needs the 90 MB model; the API is checked compatible, the retrieval numbers were not re-measured.
- **The installer is unsigned.** Needs a purchased certificate in Pavan's name.
- The native **Browse...** dialog was never clicked; only that the bridge exists in a real window.
- The packaged MCP helper prints a harmless traceback to stderr at shutdown (exit 0, protocol clean). Not diagnosed.
- Never opened on Windows 10 or on a machine without WebView2.
- Accessibility: no screen reader, as before.

### Released
`v0.1.0-rc.2` (pre-release) at `40dbf6b`, with `Kernote-Setup-0.1.0.exe` (65,510,099 bytes) and `SHA256SUMS.txt`.
SHA-256 `06ccc814c5149550c49854c8594a0538034a6a2c8881582d01d1ba014d4a6ed9`; the asset was re-downloaded from GitHub and
the hash matched. The installer was rebuilt from that exact commit and smoke-tested (install, launch, foreign-Host 403,
log written, uninstall keeps data). `CLAUDE.md` was removed in `40dbf6b`; its references now say "the project contract"
and the file remains in history (last touched at `214b771`).

### Next safe task
Buy a code-signing certificate in Pavan's name and sign the installer; clear the name before promoting it publicly.

## 2026-11-18 — Published, and the README made true again

Pushed to `github.com/pavannithin224-abcd/kernote` over SSH (the key on this
machine was already registered; no token or password was handled). Local branch
renamed `stage-2-app-foundation` -> `main`, so `main` is the default branch.

### README drift corrected
Six claims understated the product on what is now a public page: approval undo,
the visual and accessibility passes, the packaged binary, the test count
(411 -> 533), "planned MVP"/"Planned stack", and "Day 4" (day 13). Each was
replaced with the limitation that is *actually* still true -- no screen-reader
audit, unsigned binary with no installer, no batch approval for consolidations,
Windows not re-run against this commit.

### The demo plays inline
GitHub's sanitizer strips `<video>` in every form -- tested against the
`/markdown` API with repo `/raw/`, `raw.githubusercontent.com`, external and
`user-attachments` URLs; all four returned `<p></p>`. An `<img>` survives, so
the demo is a 293-frame animated WebP, **863 KB** at 1100px versus **8.9 MB**
for the equivalent GIF. Verified rather than assumed: `raw.githubusercontent`
serves it as `image/webp`, byte-identical to the local file, with all 293
`ANMF` frames intact, and GitHub's rendered-README API returns the `<img>`
with its `src` unchanged. `docs/brag.mp4` stays for audio, and the CC BY credit
now names which file the music is in.

### Attribution removed
All 41 commits carried a `Co-Authored-By: Claude` trailer, which is what put
Claude in the contributors list. Stripped with `git filter-branch --msg-filter`
across every ref, backup refs deleted, reflog expired, repo gc'd, then
force-pushed. Verified: 0 trailers in live history; the contributors API now
lists one login with 42 contributions. Pre-rewrite bundle:
`~/kernote-pre-attribution-20261118-173149.bundle` (3.3 MB, verified complete).

### Verified at 72d3c7f (Linux/WSL2)
| check | result |
|---|---|
| pytest | **533 passed, 7 skipped** |
| ruff check / format | clean, 107 files formatted |
| `npm run typecheck` | clean |
| eslint | clean |
| frontend build | succeeds; warns the 522 kB chunk exceeds Vite's 500 kB advisory (163 kB gzipped) |

Release notes drafted at `docs/RELEASE_NOTES_v0.1.0-rc.1.md`. `v0.1.0-rc.1`
now points at `72d3c7f`.

### Known issues
- A stale local `master` branch still points at `214b771`, an ancestor of
  `main`. Never pushed, harmless, not deleted without asking.
- `gh` 2.105.0 installed to `~/.local/bin` (checksum verified against the
  official list; no root, nothing system-wide). Authenticated by the user
  through the browser device flow; token scopes `repo`, `read:org`, `gist`,
  `admin:public_key`.
- The rendered page has still never been looked at in a browser.

### Released
`v0.1.0-rc.1` published at 2026-11-18T17:46:20Z from
`docs/RELEASE_NOTES_v0.1.0-rc.1.md`, **marked pre-release** and not latest --
confirmed by `/releases/latest` returning 404, so no badge or API consumer will
read it as stable. The tag points at `72d3c7f`; this handoff entry is the
commit after it. No binaries attached: the only build available here would be
unsigned and Linux-only.

### Next safe task
Open the repo page and confirm the WebP animation actually plays -- it is the
one claim still resting on bytes-and-headers evidence rather than eyes.

## 2026-11-17 — The duplicate backlog cleared

The damage from the pre-ADR-0049 scanner, cleaned up. A backup was taken
first (11.8 MB, `backups/kernote-20261117-063924.db`).

### What was applied
| | |
|---|---|
| approved | **85** — byte-identical pairs from the double-scan |
| rejected | **1** — `npm scripts` spanning `frontend/package.json` and `samples/eval-repo/web/package.json`: two projects sharing a heading, not one claim |
| left alone | **5** — wording differs; three of those would have made the *stale* version canonical |
| failures | **0** |

### The vault
| | before | after |
|---|---|---|
| memories (total) | 932 | **932** — nothing deleted |
| active | 932 | 847 |
| superseded | 0 | 85 |
| citations | 932 | **974** |
| open findings | 564 | 478 |

Citations *rose*, which is the point: `supersede_into` carries the absorbed
record's provenance onto the keeper, and the absorbed record keeps its own.
42 of the 85 pairs cited different line ranges of the same file.

### Guarantees checked rather than assumed
- superseded records with no content: **0**
- superseded records with no replacement: **0**
- replacements that are not active: **0**
- **merges that dropped a citation: 0**
- revisions recording a merge: 85; feedback rows: 85

### Reversibility proven on the real data
Undid one merge and re-applied it: active 847 → 848 → 847, superseded
85 → 84 → 85, citations 974 → 973 → 974. Exact round trip, on production
rows rather than a fixture.

### What is still pending, and why
Five proposals remain, deliberately:
- `Retrieved records are never silently discarded…` — differs by a `---`.
- `npm scripts` (frontend) — the old reading predates the `typecheck` script.
- `Dashboard redesign — brief`, `Startup animation — brief`,
  `Remaining order` — each is the **old and new text of the same passage**,
  and the merge preview would keep the stale wording. For the dashboard
  brief that means serving *"Received 2026-11-11. Not started."* over
  *"Built 2026-11-14, reviewed and accepted."*

These are not duplicates; they are versions. With ADR-0049 in place a
re-scan now supersedes properly, so the honest fix is to re-scan the
project and let the newer reading win, then let these proposals lapse.

### Known issues
- **478 open findings remain**, almost all `stale_risk` from the
  documentation edits of 14–15 November. Unrelated to this cleanup.
- Approving 85 proposals took 85 individual requests; there is no batch
  endpoint for consolidations, only for relationship links.

### Next safe task
Re-scan the project so the five version-pairs resolve by supersession, then
commit — 72 files.

---

## 2026-11-15 — The scanner now updates instead of copying (ADR-0049)

The upstream bug from the previous entry, fixed.

### What was wrong
`exists_same_claim` keyed on the **file's** content hash, so a file was
either untouched (skip everything) or changed (re-create everything).
One edited paragraph re-created every memory that document had produced —
345 memories from 24 new files, 587 → 932, and 91 duplicate proposals.

### Three outcomes, one of them new
1. File byte-identical → skip. Unchanged cheap path.
2. File changed but we hold this claim — identity `(project, title, file)`:
   - same wording, moved lines → **re-pin** the citation, no revision
     written, because the claim did not change;
   - new wording → **supersede**: the old reading keeps every byte and
     gains `superseded_by`.
3. Genuinely new → create.

Ambiguity is refused: `find_same_claim` returns nothing when two live
memories match, so a duplicate is created and the detector raises it for
review rather than superseding the wrong record.

### Measured on `samples/eval-repo`
| scan | created | superseded | re-pinned |
|---|---|---|---|
| fresh | 51 | 0 | 0 |
| nothing changed | 0 | 0 | 0 |
| one section appended | **1** | 0 | 7 |
| one section edited | 0 | **1** | 7 |

Before: scans 3 and 4 each re-created the file's whole set.

### A behaviour change, stated plainly
Editing a cited file **and re-scanning** no longer leaves a staleness
finding — the claim was refreshed from the same source the finding would
have pointed at. Drift still fires for a file edited **without** a re-scan,
which is the ordinary case and what `test_drift_spike.py` covers. One test
encoded the old expectation; it was updated, not worked around, and now
asserts the supersession explicitly.

### What changed
- **`db/repositories/memories.py`** — `find_same_claim`, `repin`.
- **`ingest/pipeline.py`** — the three-way branch; counters threaded
  through `_ingest_one_file`.
- **`domain/models.py`** — `ScanResult.memories_superseded` / `.memories_repinned`.
- **`tests/integration/test_rescan_is_incremental.py`** (new, 5 tests).
- **`tests/integration/test_stage6_review.py`** — one test updated.

### Verification performed
- `pytest backend/tests` — **540 collected, all pass**.
- `ruff`, `typecheck`, `eslint`, `build` clean.
- Measured on a copy of `samples/eval-repo`, not your vault.

### Known issues
- **Your vault still holds the 91 duplicates** from before the fix, and the
  345 extra memories. The fix stops it recurring; it does not clean up what
  already happened. The 85 exact-duplicate proposals are the way to do that.
- Identity is the heading. Renaming a section is indistinguishable from
  deleting one and adding another — the old memory stays active and the new
  one is created. Nothing detects a rename.
- A claim that moves to a *different file* is likewise a new memory.

### Next safe task
Decide what to do with the existing 91 proposals now that new ones will not
appear, and commit — 72 files.

---

## 2026-11-15 — Reviewing the 91 proposals found a bigger bug upstream

**Nothing was merged.** Auditing the queue turned up a defect in the
scanner that the review queue was quietly cleaning up after.

### The audit
| | |
|---|---|
| proposals | 91 |
| byte-identical bodies | **85** |
| bodies differ (judgement) | 6 |
| previews that would drop a citation | **0** — the merge guarantee holds across all 91 |
| merges spanning two different files | 1 |

### The root cause: a re-scan does not supersede, it re-creates
**All 91 duplicate pairs straddle the two scan runs, and the vault contains
zero superseded memories.** Scanning the project a second time created a
fresh memory for every extracted region rather than recognising that one
already existed:

- 587 memories after the first scan, **932 after the second** — +345, while
  only 24 new files appeared.
- 46 of the 91 pairs cite the *same* file region; the rest cite the same
  content at shifted line numbers, because the files grew.

So the duplicate detector is doing cleanup for the ingest pipeline. That is
the defect to fix, in `ingest/pipeline.py` — a region whose content is
unchanged should leave its memory alone, and a region whose content changed
should **supersede** the old memory, not sit beside it.

### Three proposals would make the *stale* version canonical
The 6 non-identical pairs are not duplicates at all — they are the old and
new text of the same passage, captured either side of an edit. The merge
preview blends them, and for `Dashboard redesign — brief` the result keeps:

> `**Received 2026-11-11. Not started.**`

and discards `Built 2026-11-14, reviewed and accepted`. The absorbed record
keeps its content (nothing is destroyed), but the **served** memory would
assert the outdated claim — precisely what Kernote exists to prevent. Same
for `Startup animation — brief` and `Remaining order`.

### One is a false positive
`npm scripts` from **`frontend/package.json`** and
**`samples/eval-repo/web/package.json`** — two different projects' scripts
sharing a title. Merging them would conflate facts about different files.
It should be rejected, not approved.

### Recommendation
1. **Fix the scanner first.** Merging 91 proposals treats the symptom, and
   the next scan recreates them.
2. The 85 exact duplicates are safe to approve whenever — citations are
   preserved and ADR-0040 makes it reversible.
3. Reject the cross-file `npm scripts` pair.
4. Leave the three stale/fresh pairs alone until the scanner supersedes
   properly; merging them now enshrines the stale text.

### Verification performed
- All 91 previews audited programmatically; 535 tests still pass.
- **No proposal was approved or rejected. Your vault is unchanged** beyond
  the analysis run recorded in the previous entry.

### Next safe task
`ingest/pipeline.py`: make a re-scan supersede rather than re-create.

---

## 2026-11-15 — Analysis run on the real vault

Ran with the new background endpoint: **4 seconds**, and `/health` answered
throughout. A backup was taken first (10.6 MB, in `backups/`).

### What it found
| | |
|---|---|
| open findings | 114 → **564** |
| stale_risk, low | **401** — file changed, but not within the cited lines |
| stale_risk, high | **69** — the cited lines themselves moved |
| duplicate, high | **91**, with 91 pending proposals |
| conflict | 1 |
| freshness | **61%** (573 of 932 verified) — the first real figure this vault has had |

### Most of the drift is my doing
The stale risks point overwhelmingly at files this session rewrote:
**215 at `docs/DECISIONS.md`** (ten ADRs added), 63 at `lib/api.ts`, 30 at
`routers/maintenance.py`, 24 at `VISUAL_PASS.md`. The product correctly
detected that its own documentation moved under its own memories. That is
the feature working, not a fault — but the queue is large because of the
last two days of work, not because the vault was neglected.

### The duplicates are real
**85 of the 91 proposals merge byte-identical memories** — same title, same
body. These are ADRs extracted twice across two scans. Sampled three; all
identical. So the nesting fix (ADR-0048) is pulling its weight: before it,
these were invisible.

### The suggestion exclusion works end to end
Same-title pairs in the relationship feed fell **50 → 7**, because the
duplicate detector now owns those pairs and `suggestions.ranked` excludes
anything the review queue is already asking about (ADR-0047). That exclusion
had only been unit-tested until now.

### Known issues
- **564 open findings is a lot of queue.** The 401 low-severity stale risks
  are "the file changed around the citation", which ADR-0037 counts as
  not-verified; that is why freshness reads 61%.
- No bulk action for stale findings — the consolidation proposals can be
  reviewed in batches, drift findings one at a time.
- Re-running analysis after each doc edit will keep regenerating these.

### Next safe task
Commit, then work the duplicate proposals — 85 of 91 are exact duplicates
and should merge cleanly.

---

## 2026-11-15 — The duplicate "weakness" investigated (ADR-0048)

Yesterday I wrote that the duplicate detector was missing 50 same-title
pairs and called it a product bug. **That was 90% wrong**, and the real bug
was somewhere I had not looked.

### What the 50 actually were
Measured by replaying detection against copies of the real vault:

| | |
|---|---|
| **30** | **Stale findings.** The last analysis ran before the scan that added 345 memories. Flagged the moment analysis ran again. |
| 14 | Excluded by the parent/child nesting guard — **9 of them wrongly**. |
| 5 | Genuinely nested. Correct. |
| 1 | Bodies genuinely differ. Correct. |

### The real bug
`_is_nested` tested containment with `<=` on both bounds, which is **also
true when the ranges are identical**. Two memories citing exactly the same
lines of the same file were read as "a section and the block inside it" —
when they are the same region extracted twice, which is the clearest
duplicate there is. The guard built to stop a false positive was causing a
false negative.

One line. Same-title pairs flagged **30 → 38**; candidates 49 → 93.

### A change I made and then deleted
Before finding the cause I added an "exact duplicate" pass — hash every
memory by `(type, content_fingerprint)` and flag identical groups directly,
so exact duplication would not depend on bucket limits. Defensible, and
**removed**, because with the nesting fix it changed nothing: 93 candidates,
91 proposals, 38 of 50, *identical* with and without it. 68 lines that
duplicated existing work. Same standard as ADR-0036's rejected per-file cap.

### What changed
- **`maintain/duplicates.py`** — three lines in `_is_nested`, and the
  docstring explaining why identical is not nested.
- **`tests/integration/test_stage6_review.py`** — two regression tests:
  identical ranges are not nesting, genuine nesting still is. The first was
  confirmed to fail when the fix is reverted.

### Verification performed
- `pytest backend/tests` — **535 collected, all pass**.
- `ruff` clean.
- Measured on copies of the real vault throughout. **Your data was not
  modified** — every detection run went to a scratch copy.

### Known issues
- `_CLIQUE_LIMIT` still means two non-canonical duplicates are not compared
  *as a pair*; each is compared against the canonical, so both surface. That
  is the trade the limit exists to make, and it is now the only known gap.
- **Your vault's findings are stale.** Running analysis would surface ~93
  duplicate candidates and 91 proposals that currently are not visible.

### Next safe task
Run analysis on your project to clear the stale findings, and commit — 69
files.

---

## 2026-11-15 — Ranked relationship triage (ADR-0047)

967 suggestions were answerable one pair at a time by clicking graph nodes,
which is not a workflow. `GET /projects/{id}/links/suggestions` returns them
ranked, and `POST /projects/{id}/links/batch` applies several answers at
once. A *Suggested relationships* panel sits at the top of the review queue.

### The ranking, which is the actual feature
The graph scores each shared entity separately and keeps the best per pair,
so two memories sharing **three** rare files looked identical to two sharing
one. The score is now the **sum** of `1/(n-1)` across everything a pair
shares. On the real vault the top suggestion scores **9.34** — two
dependency lists sharing four packages — against a floor of 0.17.

Three exclusions: already linked, already dismissed, and **already in the
review queue**. That last one matters — an open duplicate finding has a
better answer waiting than "related", and without the exclusion those pairs
ranked *first*, because near-identical memories share the most entities.

### Two deliberate refusals
- **No "confirm all".** Agreeing to hundreds of relationships in one click
  records a judgement nobody made. Selection is explicit.
- **A batch is not a bulk writer.** Every decision goes through
  `links.confirm` / `links.dismiss`, so no guard is bypassed — a batch
  cannot assert `supersedes` or link across projects. A failed decision is
  reported, not fatal: forty answers where three are stale apply
  thirty-seven and name the three.

### It found a weakness somewhere else
**Four of the five strongest suggestions are same-title pairs that the
duplicate detector never flagged** — 50 such pairs in the vault. They are
listed with `same title — check for duplicate` rather than hidden.

> **Corrected 2026-11-15 (ADR-0048).** The guess in the rest of this
> paragraph was wrong. Investigated: **30 of the 50 were simply stale
> findings** — the last analysis predated a scan that added 345 memories —
> and 6 more were correctly excluded. The real defect was 9 pairs hidden by
> an off-by-one-ish `<=` in the nesting guard. Fixed.

### What changed
- **`maintain/suggestions.py`** (new) — ranking and batch application.
- **`api/routers/maintenance.py`** — the two endpoints.
- **`lib/api.ts`** — `linkSuggestions`, `batchLinks`, `LinkSuggestion`.
- **`screens/MaintenanceCenter.tsx`** — the triage panel.
- **`tests/integration/test_link_suggestions.py`** (new, 11 tests).

### Verification performed
- `pytest backend/tests` — **533 collected, all pass**.
- `ruff`, `typecheck`, `eslint`, `build` clean.
- Live against the real vault: ranked output inspected, exclusions working,
  `same_title` flagged correctly. **No decisions were applied to your data.**

### Known issues
- Still a lot of clicking: ordered clicking, but 967 pairs is 967 pairs.
  No keyboard flow through the list.
- The feed is per project.
- `limit` defaults to 25 in the UI and caps at 200.
- Not seen rendered.

### Next safe task
Commit — 68 files now. Then possibly the duplicate-detector weakness above,
which is a product bug this work happened to expose.

---

## 2026-11-14 — Curated relationships and background indexing

Two of the audit's "later" items, both built.

### Relationships can now be answered (ADR-0045, migration 0010)
`memory_links` was empty in practice, so the graph derived every edge from
entity co-occurrence at read time. A suggestion now has two durable answers:
**confirm** writes a row with `origin='user'`, **dismiss** records the pair
in `link_rejections` so it stops recurring, and **withdraw** returns a
confirmed link to being a suggestion.

`origin` is the useful part: `suggested` | `user` | `merge` | `finding`, so
the inspector offers confirm/dismiss on heuristics, withdraw on judgements,
and nothing on a merge's consequence — that one is undone by undoing the
merge.

**Two bugs, both found by tests rather than by reading.** The first version
stored every pair in sorted id order, which is right for `relates_to` and
`contradicts` and **silently reverses `refines` and `depends_on`**. The same
assumption meant a sorted lookup never matched merge links, which are
written `(keeper, absorbed)`, so `remove` said "no such link" instead of
refusing. Symmetric kinds are sorted, directional ones are not, and lookups
check both orderings.

### Background indexing (ADR-0046)
`POST /projects/{id}/scan/background` and `/analyze/background` queue the
work and return a job; `GET /jobs/{id}` and `GET /jobs` report it. The
blocking endpoints are unchanged — the demo, the tests and anyone scripting
the API depend on them.

**One worker, on purpose**: SQLite takes a single writer, so two scans would
serialise on the lock anyway, with the added chance of one timing out
against the other. Submitting a second scan of the same project returns the
one already running.

**State is in memory, and that is the honest choice.** A job describes this
process; it cannot survive a restart because the work cannot either.
Persisting it would mean reopening the app to a list of jobs that are not
running and cannot be resumed. What the work produced *is* durable —
`scan_runs`, findings, `drift_runs`.

### Verification performed
- `pytest backend/tests` — **522 collected, all pass** (26 new).
- `ruff`, `typecheck`, `eslint`, `build` clean.
- **Live, on the real vault**: a suggested edge confirmed (337 suggested → 336
  + 1 user), withdrawn, dismissed (the suggestion disappeared), then restored
  so the vault was left exactly as found — `memory_links` and
  `link_rejections` both back to 0 rows.
- **Live background scan**: returned immediately, ran 8s across 177 files,
  and `/health` answered throughout. A second request while it ran returned
  the same job id.

### Known issues
- **The background scan I ran added memories** (345) because the docs
  changed since the last scan. Expected, but your vault is larger than it
  was this morning.
- **No cancellation, no progress percentage.** A job is queued, running,
  done or failed — a long scan cannot be called off.
- **No bulk curation.** Confirming relationships is one pair at a time;
  337 suggestions is a lot of clicking. Ranking suggestions by confidence
  is the obvious next step.
- The tray still needs the desktop shell.
- Not seen rendered, as all session.

### Next safe task
Commit. 66 files now.

---

## 2026-11-14 — Cache headers and CORS (audit item 6)

Small, and one of them had a trap worth recording.

### Caching
`assets/*` is `public, max-age=31536000, immutable` — Vite renames the file
whenever the bytes change, so it never needs revalidating. **Everything else,
including the shell, is `no-cache`**: a cached `index.html` names hashed
assets that no longer exist after an upgrade, and the symptom is a blank app
fixed only by a hard refresh the user has no reason to guess at.

Verified live: the 517 KB bundle returns `immutable`, `/graph` returns
`no-cache`.

### CORS, and the trap
The obvious implementation — "drop CORS when a build is present" — **would
have broken `just dev`**. Development runs the API with a `dist/` sitting on
disk from an earlier build while Vite serves the UI on :5173; keyed on the
build, CORS would vanish exactly where it is needed.

So it is keyed on **configuration**: the middleware is registered only when
`cors_origins` is non-empty, and `just app`, `just serve`, `just desktop`
and `scripts/app.sh` all set `KERNOTE_CORS_ORIGINS='[]'`. Single-process
mode has one origin, so the middleware there is attack surface and nothing
else.

Verified live in both modes: with `[]`, a request carrying
`Origin: http://evil.example` gets no `access-control-allow-origin` at all;
with the defaults, `http://localhost:5173` is still allowed and a foreign
origin still is not.

### What changed
- **`main.py`** — `_cache_headers()`, and the CORS registration made
  conditional.
- **`justfile`**, **`scripts/app.sh`** — the three single-process launchers
  set `KERNOTE_CORS_ORIGINS='[]'`.
- **`tests/integration/test_single_process_ui.py`** — 5 more tests.

### Verification performed
- `pytest backend/tests` — **501 collected, all pass**.
- `ruff`, `typecheck`, `build` clean.
- Response headers and CORS behaviour checked against the running server in
  both modes, not only in tests.

### Known issues
- `KERNOTE_CORS_ORIGINS='[]'` is JSON-shaped because pydantic-settings parses
  complex types that way. It works, and it is obscure; a packaged build
  should set it in its own environment rather than rely on a shell quirk.
- The desktop launcher inherits the variable from `just desktop`. Running
  `python -m kernote.desktop` by hand keeps the dev CORS allowance.

### Next safe task
**Commit.** Every essential item on the audit list is now done except the
first one, which was this.

---

## 2026-11-14 — Neon pass on the six older screens

The second half of audit item 5, and it turned out to be a **shared-component
change, not six screen rewrites** — which is what the brief asked for
("do not rewrite working components just for stylistic reasons").

### Two edits reached all six screens
- **`Panel`** now renders its title in the terminal register (mono, 11px,
  upper case, tracked `0.14em`) and uses `rounded` + `px-3.5` to match the
  redesigned panels. Every older screen renders through it, so they all
  moved at once.
- **`ScreenHeader`** (new) replaces six hand-rolled
  `<h1 className="text-lg font-semibold tracking-tight">` blocks. It takes a
  `right` slot, which is what `MaintenanceCenter` needed for its Run
  analysis button.

Screen bodies were left alone. Two names were brought in line with the
sidebar while I was there: *Memory Explorer* → **Memory Ledger**, *Project
Intelligence* → **Query Console**, which is what the nav has called them
since the redesign.

### The guard had to learn the new structure
`test_every_screen_has_a_heading` looked for a literal `<h1`, which no screen
has any more — the heading moved into `ScreenHeader`. Rather than weaken it,
it now accepts either a literal `<h1>` or `<ScreenHeader`, **and a second
test pins that `ScreenHeader` actually renders an `<h1>`**, so the
indirection cannot hollow the rule out.

Writing that second test cost one false failure of its own: slicing the
function body at `"\n}"` matched the `}) {` of the signature and truncated
before the heading. It looks for a line that is exactly `}` now. Both guards
were confirmed to fire by breaking the real thing.

### Verification performed
- `pytest backend/tests` — **496 collected, all pass**.
- `ruff`, `typecheck`, `eslint`, `build` clean.
- Served live: all eight routes return 200.

### Known issues
- **Still not seen rendered.** A shared-component restyle is exactly the
  change most likely to look wrong somewhere specific — a panel header
  crowded by its `right` slot, say — and nobody has looked.
- `Panel`'s padding changed from `p-4` to `p-3.5`. Harmless in principle,
  unverified in practice.
- Colour contrast was not re-checked for the smaller uppercase headings,
  though they use `--text`, which was measured.

### Next safe task
Commit. 63 files now, and the audit's essential list is finished apart from
item 6 (cache headers, dev CORS) and item 1 (commit, which is where this
list started).

---

## 2026-11-14 — Accessibility pass (audit item 5)

Measured first, which changed what the work was. The audit said "six of
eight screens have no aria"; the actual defects were **eight unlabelled form
controls**, **two screens with no heading**, and **no focus style anywhere**
— small, specific, and quick to reintroduce.

**18 → 38 aria/role attributes.** Not a redesign: the brief says not to
rewrite working screens for style, so this named controls and left the
markup alone.

### What changed
- **Eight controls named** across `AgentIntegrations`, `ChangeImpact`,
  `MemoryExplorer` and `ProjectIntelligence` — git refs, filters, the
  question box, the token budget.
- **A visible focus ring.** Nothing defined one, so keyboard users got the
  browser default: a thin dark outline on a near-black panel, effectively
  invisible. `:focus-visible` keeps mouse clicks clean.
- **A skip link.** The sidebar is ~20 tab stops; without one every keyboard
  visit to a screen began by traversing it.
- **`<h1>` on Dashboard and Knowledge Graph** (`sr-only`) — the two *newest*
  screens were the ones missing a heading.
- **`role="alert"` on `ErrorNote`**, which covers every screen at once,
  including `MaintenanceCenter`, whose own file has no aria because it has
  no form controls and its buttons all carry text.
- The React Flow graph is keyboard-reachable already — checked in the
  library rather than assumed. Memory Pulse has no click handlers, so there
  is nothing there to focus.

### The guard, and two mistakes writing it
`tests/unit/test_accessibility_basics.py` pins the three defects. Getting it
right took two corrections, both found by **replanting a real defect and
watching the test not fail**:

1. Scanning to the next `>` to find the end of a tag is wrong — inline arrow
   handlers (`onChange={(e) => ...}`) contain one.
2. A fixed 500-character window is worse: it reaches into the *next*
   control and finds *that* one's `aria-label`, so an unlabelled field
   passes silently.

It now walks the characters tracking brace depth and quotes. Both the
control guard and the heading guard were confirmed to fire.

### Verification performed
- `pytest backend/tests` — **495 collected, all pass** (3 new).
- `ruff`, `typecheck`, `eslint`, `build` clean.
- `sr-only`, `:focus-visible` and `.skip-link` confirmed present in the
  built CSS, not just the source.

### Known issues
- **No real screen-reader audit.** These are structural fixes verified by
  grep and by the built stylesheet; nobody has driven the app with VoiceOver
  or NVDA, and I could not — Chrome was unreachable all session.
- **The neon pass on those six screens is still outstanding.** This was the
  accessibility half of audit item 5 only.
- Colour contrast was computed for the palette earlier but not re-checked
  for the focus ring against every background.

### Next safe task
The neon/palette pass on the six older screens, or commit — now 61 files.

---

## 2026-11-14 — Command palette and the data & privacy panel (audit 3 and 4)

### The fake shortcut is gone (ADR-0044)
The sidebar shipped a `⌘1` badge that **nothing handled**. It survived a
redesign, a review and a visual sign-off, because a plausible affordance is
exactly what nobody thinks to test.

Replaced with **⌘K**, a real palette: fuzzy navigation to all eight screens,
Capture, and typed text becoming a real query on the Query Console. It
**navigates rather than acts** — Scan and Analyze are long and belong on the
screen that owns them with their own progress, not behind a fuzzy match.

**Not ⌘1-⌘9**: those switch browser tabs, and most people run Kernote in a
browser today, so claiming them would fail silently or steal something.

`tests/unit/test_shortcuts_are_real.py` now extracts every key hint drawn in
JSX and asserts a handler exists. **Verified by replanting the original
`⌘1`** and watching it fail. Getting it right cost one false failure: a JSX
comment explaining the removal read as a live hint, so the detector strips
comments.

### Data & privacy panel
Settings now answers "where is my data": database path, size on disk
(including the WAL), `offline · no outbound calls`, and the embedding state
with the one-time download size when it is off. Below that, the ADR-0043
endpoints get a surface — take a backup, download a copy, export JSON, and a
restore flow that **inspects the file first**, shows what it contains, and
only then offers a two-step confirmation in the stale colour.

Every line reports something already checked. There is **no "encrypted"
badge and no "0 trackers" counter**, and **no purge button** — deleting a
vault deserves its own design, and inventing the control would be the exact
mistake the audit is about.

### What changed
- **`components/CommandPalette.tsx`**, **`lib/useCommandPalette.ts`** (new).
- **`app/App.tsx`** — palette wired; the `⌘1` hint and the now-dead `hint`
  prop removed; the search box carries a ⌘K button that opens the palette.
- **`screens/Settings.tsx`** — `DataAndPrivacyPanel`.
- **`lib/api.ts`** — `takeBackup`, `inspectBackup`, `restoreBackup`.
- **`tests/unit/test_shortcuts_are_real.py`** (new, 2 tests).

### Verification performed
- `pytest backend/tests` — **492 collected, all pass**.
- `typecheck`, `eslint`, `build` clean. The hook lives in `lib/` because
  exporting it beside the component broke Fast Refresh.
- Served live: `/settings` 200, and the palette and privacy strings confirmed
  present in the built bundle.
- Download and export links are relative and work in both modes — Vite
  already proxies `/api` and `/health`, which I checked rather than assumed.

### Known issues
- **Not seen rendered.** Chrome unreachable all session; the palette's
  keyboard behaviour is reasoned, not observed.
- The shortcut test only understands `⌘X`, `⌃X`, `Ctrl+X`. A hint written
  another way slips past; the fix is to teach the regex, not drop the rule.
- The five remaining pre-redesign screens still have no aria (audit item 5).

### Next safe task
Audit item 5: the accessibility and palette pass over the six older screens.
Still uncommitted, now 57 files.

---

## 2026-11-14 — Backup, restore and export (ADR-0043)

The biggest hole the audit found: Kernote had **no way to get a copy of your
own data**. Three endpoints now, no new dependencies.

```
POST /api/v1/backup              snapshot to <data_dir>/backups/
GET  /api/v1/backup/download     a fresh snapshot, as a download
POST /api/v1/restore/inspect     what a file claims to be, touching nothing
POST /api/v1/restore             replace the vault (confirm=true required)
GET  /api/v1/projects/{id}/export    portable JSON
```

### The three things that make it safe
1. **Backup uses `sqlite3.Connection.backup()`, not a file copy.** Copying
   the file while running can catch a torn page or miss data still in the
   WAL. A test proves the point: a memory written *after* the snapshot is
   absent from it.
2. **Restore validates before destroying.** The dangerous input is not junk
   but *a real SQLite database that is not ours* — there is a test for
   exactly that. A newer schema is refused rather than downgraded.
3. **Restore always snapshots first**, and returns the path. An undo nobody
   has to ask for.

The copy goes **into the live connection** (`source.backup(conn)`) rather
than swapping files, so open handles stay valid and Windows cannot complain
about replacing an open file.

**Paths, not uploads** — the server is always local, so `python-multipart`
and a multi-megabyte HTTP round trip buy nothing. A native file dialog can
fill the path later.

### What changed
- **`db/backup.py`** (new) — snapshot, inspect, restore, export.
- **`api/routers/admin.py`** (new) — the five endpoints above.
- **`db/connection.py`** — `current_version()` made public, so restore can
  compare against it rather than reach for the private name.
- **`main.py`** — router registered.
- **`tests/integration/test_backup_restore.py`** (new, **15 tests**), most
  of them about what restore *refuses* to do.

### Verification performed
- `pytest backend/tests` — **490 collected, all pass** (15 new).
- `ruff` clean; `requirements.txt` untouched.
- **On the real vault**: 6.3 MB snapshot, `PRAGMA integrity_check` = `ok`,
  587 memories, inspect reporting them without touching anything, restore
  without `confirm` refused with 400, and a 1.3 MB JSON export carrying
  source refs and revision lineage.
- I did **not** run a restore against your live vault. Backup and inspect
  are read-only; restore is destructive and you have not asked for one.

### Known issues
- **Backups accumulate** in `<data_dir>/backups/` with no retention rule.
  Fine at 6.3 MB each, not fine forever.
- **No scheduled or automatic backup.** This is the mechanism, not a policy.
- No UI yet — these are endpoints. The data & privacy panel (audit item 4)
  is where they belong.

### Next safe task
Audit items 3 and 4: remove the fake `⌘1`, add the command palette, and
surface backup/restore plus data location in Settings. Still uncommitted.

---

## 2026-11-14 — Kernote in its own window (ADR-0042)

Step two of the desktop track. `just desktop` builds the UI and opens Kernote
in an OS window; `backend/kernote/desktop.py` starts the existing app on a
daemon thread, waits for `/health`, then opens the webview. Closing the
window ends the process.

**pywebview, and optional.** It runs inside the same Python process — no
sidecar — and drives the platform webview rather than shipping a browser.
Electron would be ~150 MB and Tauri needs a Rust toolchain, and both assume a
JavaScript backend, so Kernote's server would have to be supervised as a
second process. It lives in **`requirements-desktop.txt`**, not
`requirements.txt`: the product is fully usable with `just app` and a
browser, so the window should not weigh on anyone who does not want it.

### It degrades instead of failing — and that is the path actually tested
This machine has **no WebKit** (`gi` is present, `WebKit2` is not), so the
window could not be opened here at all. Rather than leave that as a hole, the
launcher checks first and falls back:

```
no platform webview found. On Debian/Ubuntu:
  sudo apt install gir1.2-webkit2-4.1

Serving in the terminal instead: http://127.0.0.1:8787
Ctrl-C to stop.
```

Confirmed live: it printed exactly that and served `/health` and `/graph` on
8787 throughout. **The fallback is verified end to end; the window itself is
not** — it needs a machine with a webview.

Three smaller decisions, each because the alternative is worse: readiness is
checked before the window opens (an empty webview explains nothing); a busy
port is diagnosed rather than fought (reuse a running Kernote, refuse to
stack on a stranger); and the webview check runs first, so the message
arrives instead of a traceback from inside the GUI layer.

### What changed
- **`backend/kernote/desktop.py`** (new) — the launcher.
- **`backend/requirements-desktop.txt`** (new) — `pywebview==5.3.2` only.
- **`justfile`** — `desktop`.
- **`tests/integration/test_desktop_launcher.py`** (new, **11 tests**).

### A bug found while running it
`main.py` builds an app at module scope *and* `_serve` was calling
`create_app()` again, so two apps were constructed and `web.serving` logged
twice. The launcher now uses the module-level `app` — the same object
`uvicorn kernote.main:app` runs. Confirmed: one line now, not two.

### Verification performed
- `pytest backend/tests` — **475 collected, all pass** (11 new).
- `ruff` clean.
- Real detection path exercised on this machine: `gui_unavailable_reason()`
  returns the apt instruction, and the launcher serves anyway.

### Known issues
- **The window has never been opened.** Needs `sudo apt install
  gir1.2-webkit2-4.1` here, or any Windows/macOS machine.
- The GUI itself is untestable in the suite; the 11 tests cover everything
  around it, which is where a user would actually hit a failure.
- Still no packaging: no installer, no signing, no bundle. `just desktop`
  runs from a checkout. The 314 MB virtualenv is the obstacle.

### Next safe task
Open the window on a machine that can, then decide whether packaging is worth
it. Still unresolved and growing: the uncommitted tree.

---

## 2026-11-14 — One process, one port (Q4 reopened and answered)

Step one of "make this a desktop app": the API now serves the built UI
itself, so Kernote runs as **one command on one port**.

```bash
just app        # build the UI, then serve everything from :8787
just serve      # same, without rebuilding
./scripts/app.sh
```

`just dev` is unchanged and is still the right thing while writing code —
two processes, hot reload. This is the arrangement for *using* Kernote.

### What it buys
- **No Node at runtime.** Only to build. That matters for the Windows box,
  which has no Node: the UI can be built elsewhere and shipped as `dist`.
- **No CORS**, because there is only one origin. The port-5173 allowlist that
  forced the React Flow demo through a Vite proxy stops applying.
- The prerequisite for any packaging later — a single process is what you
  wrap in a window or an installer.

### What changed
- **`config.py`** — `web_dist`, overridable via `KERNOTE_WEB_DIST` so a
  packaged build can point anywhere. `None` means "look beside the repo".
- **`main.py`** — `web_dist()` and `_serve_frontend()`, registered **after**
  the routers so no API path can be shadowed.
- **`justfile`** — `app` and `serve`; **`scripts/app.sh`** for the just-free
  equivalent.
- **`tests/integration/test_single_process_ui.py`** (new, 8 tests).

### The two rules the catch-all has to respect
1. **An unknown API path stays a JSON 404.** Falling through to `index.html`
   would answer 200 with HTML where a client expected a parseable error,
   turning a client-side typo into a silent mystery. Verified live:
   `/api/v1/nope` → 404.
2. **Everything else falls back to the shell**, because `/graph` is a React
   Router path, not a file, and a hard reload there must not 404. Verified:
   `/`, `/dashboard`, `/graph`, `/maintenance` all 200 with the app.

Path traversal is contained by resolving the candidate and checking it is
still inside the build directory. Checked live with `--path-as-is` against
`/../../etc/passwd`, `/assets/../../../../etc/passwd` and a percent-encoded
variant: all three return the app shell, none leaks a byte.

With no build present the app serves no UI and the API runs alone — the
development state, and a test pins it.

### Verification performed
- `pytest backend/tests` — **464 collected, all pass** (8 new).
- `ruff`, `typecheck`, `eslint` clean; UI built and served for real.
- Live on :8787: shell, three client routes, `/health`, `/api/v1/projects`
  and a 507 KB JS asset all served from the one process.

### Known issues
- The UI is served **unbuilt-aware but not cache-aware**: no `Cache-Control`
  on hashed assets, so the browser revalidates every file on every load.
  Harmless locally, worth fixing before anything ships.
- CORS middleware still allows the 5173 dev origin. Correct for `just dev`,
  but it is now configuration a packaged build should drop.
- Still nothing seen rendered by me; Chrome unreachable all session.

### Next safe task
Decide the desktop shell. The honest options and costs are in the message
thread: **pywebview** is the natural fit (same Python process, OS webview,
a few MB) over Tauri or Electron, which both assume a JS backend and would
need the Python server as a sidecar. Packaging and code signing is a
separate, much larger piece of work — the venv is 314 MB, dominated by
`onnxruntime`, `tree-sitter-language-pack` and `numpy`.

---

## 2026-11-14 — Review of the uncommitted diff: one real bug

A low-effort review pass over the 41 uncommitted files. Two findings, both
fixed.

### The bug: a fabricated dashboard statistic
`LedgerSummary` built two arrays — project details and embedding statuses —
then **filtered each independently and indexed one by the other's position**.
The moment any project is missing from either list (semantic search off, or a
failed detail fetch) the pairing slips and a project's embedding status is
compared against a *different* project's memory count.

Reproduced numerically: projects A (120 memories, semantic OFF) and B (40
memories, ON, 10 indexed) made the dashboard print **110 pending index**; the
honest figure is 30.

That is precisely the class of error ADR-0037 exists to prevent — an invented
number on a panel whose rule is never to invent one, and it would have been
almost impossible to notice by looking, because 110 is a plausible number.

Fixed by carrying each project's two queries together in one row keyed off
`ids`, so they cannot drift apart. A project whose detail fails to load is now
reported as "unreadable · totals incomplete" instead of silently shrinking the
totals.

### The cosmetic one
The neon refactor stranded `Dot`'s doc comment above `Neon`, which has its own
docstring — so the orphan described a status dot while sitting on an inline
text helper, and its claim about "one small shadow" was obsolete. Removed, and
`Dot` given an accurate docstring.

### Verification performed
- The scenario in the finding re-run against both the old and new logic: 110
  (wrong) → 30 (correct).
- `typecheck`, `eslint`, `build` — clean.

### Worth knowing about the review itself
This was the **low-effort** pass: one diff read, no verification stage, tests
and docs skipped, capped at four findings. Against ~1,400 lines of new backend
logic — two undo paths with transactional invariants, three migrations, a
graph read model — that is a thin net. `/code-review high` or the cloud
`/code-review ultra` would be a fairer examination, particularly of
`undo_approval`, which deletes source refs and rewrites memory state in one
transaction and whose tests I wrote myself, so they encode my own assumptions.

### Next safe task
Commit. Then a deeper review pass if you want one.

---

## 2026-11-14 — Three things: finding undo, ADR-0014 settled, Windows re-verified

### 1. Resolving a finding can be undone (ADR-0041)
The review flow was asymmetric: consolidation reversible, resolution not.

Reversing a consolidation works because revisions preserve the prior record.
**Resolution's status flips write no revision**, so there was nothing to read
back — and the obvious inference ("re-flag every memory this finding names")
is *wrong*, because a memory already `active` was never touched by the
resolution, and re-flagging it would invent a review requirement.

So the resolution now records its own effect: **migration 0009** adds
`findings.effect_json`, one entry per memory actually flipped with its prior
status and `last_verified_at`. Undo replays exactly that.

Two refusals: a resolution recorded before 0009 has no effect record and
declines rather than guessing; and a finding closed by approving a
consolidation must be reopened through that consolidation, or the merge would
stay applied while its finding reads open.

Files: `migrations/0009_finding_effect.sql`, `maintain/review.py`
(`undo_resolution`), `db/repositories/findings.py` (`findings_by_status`,
`resolved_findings`), `POST /findings/{id}/undo`, a `status` filter on the
findings list, `lib/api.ts`, and a *Recently decided* panel in
`MaintenanceCenter.tsx`.

### 2. ADR-0014 is settled — declined on measurement
The spike finally ran. **`model2vec` is worse than `all-MiniLM-L6-v2` on our
own labelled set**, and worse where it matters most.

| metric | MiniLM-L6-v2 | potion-base-8M | potion-base-32M |
|---|---|---|---|
| Recall@1 | **0.7200** | 0.6200 | 0.5600 |
| nDCG@10 | **0.8609** | 0.7936 | 0.7956 |
| MRR | **0.8270** | 0.7447 | 0.7215 |
| encode 69 chunks | 2.52 s | **0.006 s** | **0.006 s** |

Method: the 25 answerable questions against `samples/eval-repo`, chunked by
the product's own pipeline, scored with the repo's own `eval/metrics.py`.
`model2vec` went into a **throwaway venv** — the product's dependencies were
never touched.

The 420× speed claim is real and irrelevant: embedding is a one-time scan
cost (`EVALUATION.md`: 4.7 s for the whole real corpus). Ten points of
Recall@1 for four seconds once is a bad trade. The 32M model is *worse* than
the 8M at rank 1, so size is not the answer either. **No ADR is left in
`proposed` state.**

### 3. Windows re-verified
Native Windows **Python 3.12.10 AMD64**, fresh venv on an NTFS path, all
dependencies from prebuilt wheels, `pip check` clean. Migrations ran to
**schema v9**.

**455 collected, 3 failed — and the three are the known Git-dependent Change
Impact tests**, unchanged from the last Windows run. Everything added since
then passes natively, including the new undo work and the HTTP round trip.

**Git and Node are still not installed there** (checked, both absent), so
Change Impact and the frontend build remain unverifiable on Windows. That is
the only outstanding Windows item and it needs you, not me.

The NTFS copy was **deleted afterwards** — a stale duplicate of the source is
worse than none, the same call made about the React Flow demo. To recreate:
copy the tree to a Windows path excluding `.venv`/`node_modules`/`.git`,
`python -m venv .venv-win`, install `backend/requirements.txt` and
`requirements-dev.txt`, run pytest.

### Verification performed
- `pytest backend/tests` — **455 collected, all pass** on Linux.
- `ruff`, `typecheck`, `eslint`, `build` — clean.
- Windows: 455 collected, only the 3 Git tests failing.
- Migration 0009 applied to the live database (now schema v9).

### Known issues
- **Still not seen rendered.** Chrome unreachable; the two undo panels are
  verified by tests and compilation only.
- The ADR-0014 benchmark scores semantic retrieval alone, not the product's
  hybrid RRF where BM25 would mask part of the gap, and could not be repeated
  on IVForge (not in this repository). Stated in the ADR; the margin is wide
  enough that neither caveat changes the conclusion.

### Next safe task
Nothing is blocked. The backlog is now: click through the review screen, and
commit — the uncommitted set is large and three migrations are live in the
database.

---

## 2026-11-14 — Approval can be undone (ADR-0040)

The last real product gap is closed. The project contract demands a review flow and no
silent destructive merges; the flow had the review but no way back.

**Everything needed was already there.** `memory_revisions.snapshot_json`
stores the complete record at every revision, source refs included, with
`parent_id` chaining them — so the pre-merge state is just the parent of the
revision the merge wrote. The lineage was preserved all along; nothing reached
for it.

### The shape of it (ADR-0040)
An undo is a **forward operation**. It writes new revisions restoring the
prior state and deletes nothing that records what happened:
- the merge revisions stay — the history reads "merged, then unmerged";
- the original `accepted` feedback stays, with an `undone` row beside it
  (**migration 0008** extends the verdict CHECK). An approval later taken back
  is a stronger signal than one never made, and collapsing them would blind
  any future tuning of the duplicate thresholds;
- the `supersedes` link **is** removed — derived state asserting something no
  longer true, and it would otherwise put a false edge in the graph;
- the proposal returns to `pending`, its finding to `open`.

It **refuses** when the keeper was edited after the merge, when the absorbed
record has since been superseded by something else, or when either is gone —
each would destroy something unrelated to the merge.

### What changed
- **`migrations/0008_feedback_undone.sql`** (new) — schema 7 → 8.
- **`maintain/review.py`** — `undo_approval`, `UndoResult`.
- **`db/repositories/memories.py`** — `write_revision` made public, rather
  than letting `review.py` reach for the private name.
- **`maintain/duplicates.py`** — `proposals_by_status`; `pending_proposals`
  now delegates to it.
- **`api/routers/maintenance.py`** — `POST /proposals/{id}/undo`, and a
  `status` filter on the proposals list (422 on an unknown value).
- **`lib/api.ts`** — `undoProposal`, `proposals(id, status)`.
- **`screens/MaintenanceCenter.tsx`** — an *Applied consolidations* panel with
  Undo. A merge invisible in the UI cannot be undone however reversible it is
  underneath, which is why this panel is part of the feature and not a nicety.

### Verification performed
- **11 new tests**; `pytest backend/tests` — **450 collected, all pass**.
- Two guards **proved to fire** by removing them: the edited-since-merge
  refusal, and the `supersedes` link cleanup.
- An **HTTP round trip** covers the real path: approve → appears as applied →
  undo → back in the pending queue → second undo returns 409.
- `approve → undo → approve` asserted stable, with no duplicated citations.
- `ruff`, `typecheck`, `eslint`, `build` all clean.
- Migration 0008 applied to the live database on restart (now schema v8);
  the status filter and its 422 checked against the running API.

### A mistake worth noting
The anchor `function MaintenanceCenter() {` matched **inside** `export default
function MaintenanceCenter() {`, splitting the declaration and leaving a
dangling `export default` before a comment block. Same substring trap as the
CSS token edits earlier in this project. Caught by `tsc`, which reported it as
a duplicate default export.

### Known issues
- **Not seen rendered.** Chrome unreachable all session; the panel is verified
  by tests and compilation only.
- Undo is available only while the merge is the most recent thing to have
  happened to both records. Deliberate — see ADR-0040.
- There is no undo for `reject`, which needs none: rejecting changes no
  memory. Resolving a *finding* is also not undoable, which is a smaller
  version of the same gap and still open.

### Next safe task
Click through the review screen. Remaining backlog: ADR-0014's unrun spike,
Windows missing Git and Node, and finding-resolution undo.

---

## 2026-11-14 — The comparison demo deleted

`design/reactflow-demo/` is gone. It existed to answer one question — React
Flow or hand-rolled SVG — and that question is answered and recorded in
ADR-0039.

**Why it had to go rather than linger.** It was a duplicate that would drift
in two specific ways: `src/graphLayout.js` was a de-typed copy of
`frontend/src/lib/graphLayout.ts`, and its styling hardcoded the dark palette
while the product's version uses theme tokens. A stale second implementation
of a screen is worse than no second implementation, because it looks
authoritative.

**It was untracked, so this was not recoverable through git.** Before
deleting, its unique reasoning — the itemised list of what React Flow actually
buys, and why the question was narrow — was moved into **ADR-0039**, which
previously carried only the cost table. Nothing of substance was lost; the
code it held is superseded by `screens/KnowledgeGraph.tsx`.

**Also cleaned up:**
- the two now-dead `.gitignore` entries for the folder;
- the demo's dev server on port 5174, stopped;
- every dangling reference. Two of them were "next safe task" items
  instructing a future reader to act on a folder that no longer exists, and
  the source comments in `index.css` and `KnowledgeGraph.tsx` now point at
  ADR-0039 rather than a dead path.

54 MB reclaimed, nearly all of it the demo's own `node_modules`.

### Next safe task
Click through `/graph` in both themes on the new router. Then: approval undo,
ADR-0014.

---

## 2026-11-14 — npm advisories cleared: 10 → 0

All ten `npm audit` findings in `frontend/` are resolved. **No declared
dependency range changed**, so this is a lockfile-level fix.

### The three high-severity ones
`npm audit fix` resolved them inside the existing `^7.1.3` range:

| | before | after |
|---|---|---|
| `react-router` | 7.1.3 | **7.18.5** |
| `react-router-dom` | 7.1.3 | **7.18.5** |
| `turbo-stream` | 2.4.0 | **removed** (the router no longer depends on it) |

### The seven moderate ones needed a judgement call
They were one root cause — a glob-DoS in `minimatch`, reachable only through
`@typescript-eslint/typescript-estree`, a **lint-only** dependency that is
never shipped.

`npm audit fix` kept reporting "fix available" and kept not applying it. The
reason: **`typescript-eslint` 8.72.2 is the latest published version and is
itself inside the flagged range**, so there was nothing to upgrade to. npm's
advice was simply wrong.

`minimatch` *is* fixed, at 11.0.8 — the same major as the flagged range's
upper bound, so API-compatible. Resolved with an `overrides` entry:

```json
"overrides": { "minimatch": "^11.0.8" }
```

**Remove this override once `typescript-eslint` ships a release depending on a
patched `minimatch`.** A note belongs on it, but npm rejects comment keys
inside `overrides` (`Override without name: _comment`), which is why the
explanation lives here instead.

### Verification performed
- `npm audit` — **0 vulnerabilities**, from 10 (3 high, 7 moderate).
- `eslint` clean, and **confirmed still functional** by planting an unused
  variable and watching it fail — worth checking specifically, since the
  linter is the thing consuming the overridden package.
- `npm run typecheck`, `npm run build` — clean.
- Dev server restarted; all eight routes serve 200. The router APIs in use
  (`BrowserRouter`, `Routes`, `Route`, `NavLink`, `Navigate`, `Link`,
  `useLocation`, `useNavigate`, `useSearchParams`) are stable core APIs
  unchanged across 7.x minors.

### Known issues
- **Routing was not exercised in a browser.** Serving 200 proves the SPA
  loads, not that navigation works — every route returns the same `index.html`
  by design. A 7.1.3 → 7.18.5 jump is 17 minor versions, so this deserves a
  click-through even though no declared range moved.
- `design/reactflow-demo/` had its own `node_modules` and was not audited
  here. It has since been **deleted** (see the entry above this one).

### Next safe task
Click through the app on the new router. Then the backlog: the approval undo,
ADR-0014.

---

## 2026-11-14 — React Flow ported into the product

The user chose it after the side-by-side, so `@xyflow/react@12.12.1` is now a
product dependency and `screens/KnowledgeGraph.tsx` renders with it.

### What changed
- **`frontend/package.json`** — `@xyflow/react` added (first new runtime
  dependency since the project began).
- **`screens/KnowledgeGraph.tsx`** — rewritten on React Flow: neon dots, a
  `NodeToolbar` popup on click, the orbit ring on the selection, and the
  bottom inspector with the live record, its citations and its connections.
- **`index.css`** — an `.rf-*` block. The demo hardcoded the dark palette;
  **this is all theme tokens**, including the glow knobs, so it works in
  daylight. React Flow's own chrome (controls, minimap, attribution) is
  restyled to the product's palette rather than left white-on-grey.
- **`lib/graphLayout.ts`** — **unchanged**. React Flow takes positions, it does
  not compute them.
- Everything honest survives: the limits line, the three empty states, the
  loading skeleton, the error notes, and reduced motion.

### I gave you a wrong number, and here is the right one
I estimated **+18 kB gzipped** by subtracting the app's bundle from the demo's.
That was a bad inference — the two contain different things (the demo has no
router or query layer; the app has both plus eight screens), so the difference
measured nothing. **You approved the port against that figure.**

Measured properly, building the app twice with the screen stubbed:

| | without | with | cost |
|---|---|---|---|
| JS | 88.6 kB gz | 153.4 kB gz | **+64.8** |
| CSS | 6.0 kB gz | 8.4 kB gz | **+2.4** |
| **total** | **94.6** | **161.8** | **+67.2 kB gz** |

**3.7× the estimate; the shipped bundle grew 71%.** For a local-first app this
is far less serious than for a public site, but the decision deserved to be
made against the real figure — so it was put to the user again with the
corrected number, and **they confirmed keeping React Flow**. Decided twice,
once wrongly informed and once correctly, with the same outcome.

### Unrelated finding: pre-existing advisories
`npm audit` in `frontend/` reports **react-router ≤7.17.0 (high)** and
`turbo-stream` **(high)**, both fixable within the existing semver range by
`npm audit fix`. These pre-date today and are **not** from React Flow. Not
fixed here, deliberately — changing the router version during a rendering port
would confuse the diagnosis if anything broke.

### Verification performed
- `npm run typecheck`, `eslint`, `npm run build` — all clean.
- `pytest backend/tests` — 439 pass, 5 skipped. Accent guard still passes.
- Dev server restarted so Vite re-optimised the new dependency; `/graph`
  serving 200.

### Known issues
- **Not seen rendered.** Chrome unreachable all session.
- `design/reactflow-demo/` was a superseded duplicate that would have drifted.
  **Deleted** — see the newest entry.
- The light theme for the graph is written but unverified by eye; React Flow
  ships its own stylesheet and the overrides sit on top of it.

### Next safe task
Both loose ends are now closed: the advisories are cleared and the demo folder
is deleted. Look at `/graph` in both themes.

---

## 2026-11-14 — The React Flow demo, reworked to dots

Still outside the product; `frontend/` dependencies unchanged.

Nodes are now **neon dots** rather than labelled boxes — at 160 nodes the
labels were most of the ink. Clicking one opens a small block above it
(`NodeToolbar`, so it tracks the dot through pan and zoom) with type, status,
connections and importance; the **bottom panel** carries the full record,
fetched live from `GET /memories/{id}`, with its citations and its connections
and the reason each exists. A **dashed ring turns around the selected dot**
with a cyan particle riding it the other way — one `rotate` keyframe each, no
path maths and no animation loop.

**A bug fixed in passing.** The custom node had no `Handle`s. React Flow
attaches edges to handles rather than to the node box, so a custom node
without them logs error #008 and the edge is silently dropped — meaning the
first version of this demo may well have been drawing no edges at all. Both
handles now sit invisible at the centre of each dot.

**Verification:** builds clean; dev server serving with no HMR errors; the
fields the panel reads (`memory.content`, `citations`) confirmed against the
live API. The `/memories/{id}` shape was checked rather than assumed.

**Reviewed by the user and accepted (2026-11-14).** Chrome stayed unreachable,
so the sign-off is theirs, not mine — including the edges, which they were
asked to check specifically because of the `Handle` bug above.

**Note:** the three dev servers (8787, 5173, 5174) were killed mid-session and
restarted; the scratchpad was cleared at the same time.

---

## 2026-11-14 — A React Flow comparison, kept outside the product

`design/reactflow-demo/` draws the **same real graph** with `@xyflow/react`, so
the React Flow question from ADR-0039 can be judged by looking rather than
arguing.

**It is deliberately separate.** Own folder, own `package.json`, own
`node_modules`, own port (5174). `frontend/package.json` dependencies are
unchanged — still the same four. Nothing under `frontend/src` imports it.
Deleting the folder changes nothing else.

The API allows CORS only from 5173, so the demo **proxies `/api` through Vite**
rather than widening that setting for a throwaway. The product needed no change
at all to make this work.

**Measured, so the decision is not vibes:**

| | |
|---|---|
| Bundle | 90 → **108 kB gz** (the demo has no router or query layer, so this is close to React Flow's own share) |
| `node_modules` | 4.5 MB |
| New runtime packages | **36**, including the whole `d3-zoom`/`drag`/`selection`/`transition` chain |
| Layout | **still ours** — React Flow does not lay out graphs, it takes positions |

So React Flow replaces ~120 lines of SVG rendering, not the layout, which was
the part that took work. What it adds that the product would feel today is
**node dragging and a minimap**. Full write-up in the demo's `README.md`.

Its `src/graphLayout.js` is a de-typed **copy** of `frontend/src/lib/graphLayout.ts`.
If the layout changes and this demo is still around, the copy will drift.

**Verification:** demo builds and serves; proxy confirmed returning the real
160 nodes / 338 edges including the one conflict. Product re-checked
afterwards: backend suite, typecheck and build all still pass.

**Note:** the demo's own `vite` is pinned to 6.4.6 rather than 6.0.3 to clear a
dev-server advisory in esbuild; `npm audit` reports 0 vulnerabilities there.
The main app resolves `vite` 6.4.5 and is unaffected.

### Next safe task
Compare the two at <http://localhost:5174> and `/graph`, then decide. Nothing
depends on the answer.

---

## 2026-11-14 — Memory Pulse and the Knowledge Graph (ADR-0039)

A living map of the project's actual relationships: a compact preview on the
dashboard, a full interactive graph behind it. Every dot is a memory and every
line is a row in the database.

### What changed
- **`db/repositories/graph.py`** (new) — the read model. Explicit links,
  findings naming two memories, and shared entities below a spread threshold.
- **`api/routers/projects.py`** — `GET /projects/{id}/graph`.
- **`lib/graphLayout.ts`** (new) — deterministic, aspect-aware force layout.
- **`components/MemoryPulse.tsx`** (new) — the dashboard preview.
- **`screens/KnowledgeGraph.tsx`** (new) — the full view, at `/graph`.
- **`index.css`** — a network block; all motion under `no-preference`.
- **`App.tsx`** — route, nav entry, breadcrumb.
- **`tests/integration/test_memory_graph.py`** (new, 7 tests).
- **No new dependencies.**

### React Flow is not installed
The brief said to use the existing `@xyflow/react` installation. There isn't
one — not in `package.json`, not in `node_modules`, not imported anywhere. I
did not add it: the brief also says to avoid unnecessary dependencies, and
what is needed here is positions and hit-testing, which is ~150 lines. **If you
wanted the dependency, this is the decision to revisit** — only
`lib/graphLayout.ts` would be replaced.

### The threshold is the feature (ADR-0039)
`memory_links` is empty (it is written only on supersede/merge), so the only
dense signal is entity co-occurrence — and it is also the easiest way to invent
meaning. The entity `docs` is on 123 memories here; drawn naively that alone is
**7,503 edges** saying documentation mentions documentation. An entity may
therefore only link memories when it appears in **≤ 8** of them, weighted by
specificity. Raising the cap to 20 adds 1,670 edges and no information.

Everything omitted is reported in `limits` and printed by both views.

### A bug the real data found
Ranking nodes by connectivity **evicted the only open conflict**. Two claims
that disagree usually share nothing else, so both memories had degree 1 and
fell outside the 160-node cap, taking the most interesting edge in the graph
with them. Caught by reading the response and noticing the kind histogram said
`shares: 338` and nothing else. Flagged memories now outrank well-connected
ones; `test_an_open_conflict_survives_the_node_cap` was confirmed to fail when
the fix is reverted.

### A layout defect found without a browser
Measured the output geometry directly instead of looking at it. The first
version anchored the scaled graph at the padding corner, so a blob whose
aspect differs from the viewport sat to one side — x spanned 22–508 of 900,
leaving the right 43% empty. Centring fixed that; then the preview showed the
deeper issue, a circular equilibrium in a 320×150 panel collapsing to a 64px
column. The simulation is now run in viewport-normalised space, so the
equilibrium is an ellipse that matches the box. Stretching at the end would
have filled it too, by distorting the only thing position means.

Final geometry: graph screen margins 24/24/22/22, closest pair 19.1px, **36ms**
for 160 nodes — once, in a `useMemo`, never during animation.

### Animation
No animation loop anywhere. Node breathing is one CSS keyframe; the travelling
particles are SVG `<animateMotion>` on five edges; the capture ring fires when
the memory count **actually increases**, not when a button is pressed. Under
`prefers-reduced-motion: reduce` the network is drawn still and no particles
render.

### Verification performed
- `pytest backend/tests` — **439 collected, all pass**, 5 skipped.
- `ruff check backend`, `npm run build`, `eslint` — all clean.
- The graph endpoint checked against the live database: 160 nodes, 338 edges,
  611 considered, 427 memories and 40 too-common entities reported as omitted,
  and the one real conflict present.
- Layout verified numerically: finite, in-bounds, deterministic across runs,
  no node pile-ups.

### Known issues
- **`npx tsc --noEmit` is a no-op in this repo** — the root `tsconfig.json`
  has `files: []` with project references, so it checks nothing. The real
  typecheck is `npm run build` (`tsc -b`). Earlier handoff entries cite
  `tsc --noEmit` as a passing check; that claim was empty, though the builds
  quoted alongside it were real. **Fixed:** `npm run typecheck` (`tsc -b`) now
  exists and was confirmed to catch a planted type error.
- **Never seen rendered.** Chrome remained unreachable. Geometry, timings and
  data are verified numerically; nothing is verified by eye.
- The entity extractor produces some noise (`decision Leave it` is an entity
  here, from a one-word reply in a design doc). It makes weak edges, not wrong
  ones, but it is visible in the graph.
- `/graph` recomputes from SQL on every request; fine at 587 memories.

### Next safe task
Look at both views. Then decide the React Flow question.

---

## 2026-11-14 — Documentation drift swept; the RC tag is blocked, not forgotten

Housekeeping, plus one finding that is not housekeeping.

### Open questions: all six now closed
`PRODUCT_SPEC.md` §10 listed Q1–Q4 as open. None of them was.

- **Q1** (generative model in scope?) — closed by outcome: fully deterministic.
  The stated default held and no model adapter was ever needed.
- **Q2** (which real repos?) — closed 2026-11-09: **neither** of the two the
  guide named. The corpus is **IVForge**, as `EVALUATION.md` has said all along.
- **Q3** (Windows a target?) — closed 2026-11-09 by **ADR-0009a**.
- **Q4** (packaging?) — closed **by default, not by decision**: dev scripts
  only. Recorded that way deliberately, so the distinction stays visible.

Q1 and Q4 are marked closed-*by-default* rather than decided. Writing them up
as decisions would have been tidier and false.

### Two ADR statuses were lying
- **ADR-0009** still read `proposed · needs your confirmation`. ADR-0009a
  resolved it five days ago and says so in its own header. Now marked
  **superseded**, with a note that the Day 18 / Day 23 checkpoint schedule was
  overtaken by the project finishing early.
- **ADR-0014** (the `model2vec` spike) still read `proposed · needs a Day 14–17
  measurement`. That window never arrived — the RC landed on day 4. It is now
  marked **proposed, not run**, stating plainly that `all-MiniLM-L6-v2` is the
  default *by inertia rather than by measurement*, and that the MTEB figures
  quoted in it are someone else's numbers. Either run it or decline it; leaving
  it as-is implied work in flight that was not.

### Both design briefs still said "not started"
`DASHBOARD_BRIEF.md` and `STARTUP_ANIMATION_BRIEF.md` were both marked
`not started` while describing features that shipped and were accepted
yesterday. Same class of drift, one day old. Corrected.

### The RC tag: blocked, and deliberately not moved
`v0.1.0-rc.1` points at `22acb32` (2026-11-09), **12 commits and 24 uncommitted
files behind**. It was not re-tagged, because there is nowhere honest to move
it to. `HEAD` is `1bccdcf` — *"Store the startup animation brief; still no
implementation"* — a commit that by its own message contains neither design
track. Tagging that as `rc.2` would produce a release candidate excluding every
feature of the last two days and advertising the fact in its subject line.

**The tag is blocked on committing the 24 files, not on anything technical.**

### Verification performed (release battery, so the tag can be cut immediately)
- `pytest backend/tests` — **432 collected, all pass**, 5 skipped.
- `ruff check backend` — clean.
- `tsc --noEmit` — clean. `eslint` — clean. `npm run build` — clean.
- No dependency changes; no outbound URLs introduced.

### Known issues
- The 24 uncommitted files span four coherent pieces of work: the dashboard
  redesign, the tiles + ADR-0037 + migration 0007, the neon pass, and the
  reveal + ADR-0038.
- **Migration 0007 is already applied to the live database** at
  `~/.local/share/kernote/kernote.db` (schema 7). The working tree and that
  database now move together; a stash would separate them.
- ADR-0014 is a genuine open decision, now visible as one.
- Unchanged: no undo on approval; Windows has no Git and no Node.

### Next safe task
Commit the four groups, then re-tag the RC at that commit. The battery above is
green, so nothing else gates it.

---

## 2026-11-14 — The startup reveal (ADR-0038)

The second of the two agreed tracks, and the last of them. A knowledge graph
forming, resolving into the `kernote_` wordmark, over status lines that are
actually true.

### What changed
- **`components/Boot.tsx`** (new) — the reveal and the readiness checks.
- **`index.css`** — a `.boot-*` block; all movement inside
  `@media (prefers-reduced-motion: no-preference)`.
- **`main.tsx`** — `<Boot>` mounted **above** `<BrowserRouter>`.
- **`tests/unit/test_boot_claims_are_backed.py`** (new, 4 tests).
- No dependencies added. No Canvas.

### Three lines, not five — ADR-0038
The brief asked for `DATABASE`, `MEMORY ENGINE`, `RETRIEVAL INDEX`,
`LOCAL SERVICES`, `WORKSPACE READY`, and forbade an `[OK]` before the service
is ready. Two of those have **no service behind them** in this architecture
(the memory engine is library code in the API process; "local services" is the
API that already answered), and `RETRIEVAL INDEX` conflates FTS5 with opt-in
semantic search. So the screen prints what it can check, and a line is allowed
to say something other than OK:

```
[ OK ]  DATABASE          schema v7 · fts5
[ OFF ] SEMANTIC INDEX    opt-in, not enabled
[ OK ]  WORKSPACE         1 project
WORKSPACE READY
```

On this machine the middle line really does read `OFF`, because embeddings are
disabled — verified against the live endpoint, which returns
`enabled: false, usable: false`.

### Startup only, solved by position
`Boot` sits above the router, so a route change cannot remount it. No module
flag and no `sessionStorage` — nothing to go stale. A real reload remounts and
replays, which is what the brief asked for. A test asserts the ordering,
because moving it inside the router would silently make it replay on every
internal navigation.

### A failure hands over rather than blocking
First draft left the curtain up forever when `/health` failed. That hides the
dashboard's own error states, which are the useful ones — they name the failing
call and offer a retry. Now a failure is shown for 2.2s and then dismissed.

### Verification performed
- `pytest backend/tests` — 432 collected, all pass, 5 skipped.
- `ruff check backend`, `tsc --noEmit`, **`eslint`**, `npm run build` — clean.
- Each of the four new guards **proved to fire** by planting a violation:
  an unbacked line, `Boot` moved inside the router, and the semantic line
  ungated from `usable`.
- The `.boot-*` rules and both reduced-motion blocks are in the built CSS.

### Known issues
- ~~Never watched.~~ **Reviewed by the user in the running app and confirmed
  (2026-11-14); the timing curve is accepted as-is.** Chrome was unreachable
  throughout, so no screenshot exists and nothing was verified by *my* eye —
  the visual sign-off on both design tracks is the user's.
- `MIN_MS = 1250` is the only invented duration in the feature. Locally
  `/health` answers in milliseconds, so in the normal case the reveal is paced
  by its own animation and the live-status machinery only earns its keep when
  something is slow or broken. Said plainly in ADR-0038.
- Unchanged: `PRODUCT_SPEC.md` §10 drift, ADR-0009 `proposed`, stale RC tag,
  no undo on approval, Windows has no Git.

### Next safe task
Both design tracks are built and signed off. Nothing is committed: 22 files
span four distinct pieces of work (redesign, tiles + ADR-0037, neon pass,
reveal + ADR-0038) and would make four legible commits. After that the backlog
is the older debris above.

---

## 2026-11-14 — The neon treatment

The dashboard had the mock's palette but not its *treatment*: correct colours,
under-lit. Closed against the reference crop. Design notes in
`design/VISUAL_PASS.md`.

### What changed
- **`index.css`** — `--glow-alpha` / `--glow-blur` as theme tokens (45%/9px
  dark, **0%/0px light**), and three consumers: `.neon-outline`, `.neon-bar`,
  `.neon-text`. An element opts in with `style={{ '--neon': 'var(--rel)' }}`.
  In light mode `color-mix` at 0% yields transparent, so the rules become
  no-ops instead of something the light theme has to override.
- **`components/ui.tsx`** — semantic `Badge` tones are now outlined and lit
  rather than filled; new `Bar` and `Neon` primitives; `Dot` uses the shared
  glow.
- **`screens/Dashboard.tsx`** — queue header counts hued per kind, record ids
  lit in the relationship violet, freshness bars on the shared `Bar`, and a new
  `LedgerSummary` row.
- **`tests/unit/test_accent_is_reserved.py`** — rejects `--neon: var(--accent)`.

### The summary row is gated like the tile
`LedgerSummary` averages **only projects that have been checked** and prints
"(n unchecked)" beside the figure rather than folding unchecked projects in at
100% — the same rule as ADR-0037, which would otherwise have been quietly
broken one level up. With nothing checked it reads "freshness not checked".
Pending index only renders where semantic search is actually enabled. It reuses
the rows' query keys, so it adds no requests.

### A guard hole, opened and closed in the same change
`.neon-bar` fills with whatever `--neon` names, so binding `--neon` to the
accent would have filled a surface with the action colour without the word
`background` appearing anywhere near it — walking straight around the fill
guard added earlier today. The test now rejects that binding, proved by
planting one.

### Verification performed
- `pytest backend/tests` — 428 collected, all pass, 5 skipped.
- `ruff check backend`, `tsc --noEmit`, `npm run build` — all clean.
- The neon classes and `color-mix` are present in the built CSS.
- **Contrast computed, not eyeballed** (transparent badges lost the soft
  background that was helping). All five hues clear 4.5:1 against both panel
  and page, in both themes, at the 10px badge size: dark ok 14.83, warn 10.39,
  accent 11.97, rel 6.73, stale 6.55; light 5.42–7.10.

### Known issues
- ~~Still never seen rendered.~~ **Reviewed by the user in the running app and
  confirmed (2026-11-14).** The glow strength (45% / 9px) is accepted as-is.
  The Chrome extension was unreachable throughout, so no screenshot exists and
  nothing here was verified by *my* eye -- the visual sign-off is the user's.
- `color-mix()` is required. Fine on current Chrome/Firefox/Safari and already
  implied by Tailwind v4, but it is a hard dependency of the glow now.
- Not taken from the mock: its invented figures, and the `sort: freshness ↓`
  control, which sorts nothing. Worth adding when it actually sorts.
- Unchanged: `PRODUCT_SPEC.md` §10 drift, ADR-0009 `proposed`, stale RC tag, no
  undo on approval, Windows has no Git.

### Next safe task
Look at it, and tune the glow. Then the logo reveal animation.

---

## 2026-11-14 — The three dashboard tiles, decided (ADR-0037)

The three figures left out of the redesign because they could not be computed
honestly. All three are now in, and the freshness one needed a schema change to
be answerable at all.

### Freshness: three states, not a percentage
Full reasoning in **ADR-0037**. The short version: the naive figure (memories
without a stale finding, over all memories) prints **100% fresh for a project
nobody has ever analyzed**, because an unanalyzed project has no findings. It
reports an absence of evidence as evidence.

- Denominator is **verifiable** memories — those pinning a real file region —
  mirroring `detect_drift`'s own `WHERE` clause so the two cannot diverge. A
  hand-written assertion has no file to drift from and is in neither half.
- `flagged` = open `stale_risk` or `broken_link` on those memories.
- **`checked_at` gates everything.** Migration **0007** adds `drift_runs`;
  `detect_drift` now records that it ran. No run → `checked_at: null` → the UI
  says "never checked".
- Zero verifiable memories → "nothing cited", not 100%.

### What changed
- **`migrations/0007_drift_runs.sql`** (new) — schema version 6 → 7.
- **`maintain/drift.py`** — records a run, with `git_commit`.
- **`db/repositories/projects.py`** — `freshness()`.
- **`api/schemas.py`**, **`api/routers/projects.py`** — `ProjectDetail.freshness`.
- **`main.py`** — `/health` reports `db_bytes`, **summing the `-wal` and `-shm`
  sidecars**; in WAL mode the log holds uncheckpointed megabytes, so the `.db`
  size alone understates what Kernote occupies.
- **`screens/Dashboard.tsx`** — `FreshnessBar` (a fifth ledger column) and the
  database size in Local System. `bytes()` formatter added.
- **`lib/api.ts`** — `Freshness` type, `db_bytes`.
- **`tests/integration/test_freshness_states.py`** (new, 6 tests).

### Verification performed
- `pytest backend/tests` — 428 collected, all pass, 5 skipped.
- `ruff check backend`, `tsc --noEmit`, `npm run build` — all clean.
- Migration 0007 applied to the real database on restart: schema 6 → 7, logged.
- **The trap reproduced live on this repository.** After scanning and before any
  analysis: 587 verifiable, 0 flagged, 587 verified — `verified/verifiable` is
  exactly 1.0, so a naive tile prints "100% fresh" for a repo nothing had
  checked. `checked_at` was `null`, so the UI read *never checked*. After
  `analyze`: `checked_at` set, `refs_checked` 587, 0 flagged, 1 conflict and 2
  duplicate proposals found — and the 100% is now earned.
- **The flagged state too**: appending to `DECISIONS.md` and `DEV_HANDOFF.md`
  during this task moved 53 memories out of `verified` (587 → 534), so the tile
  read 91% with a stale-toned bar. All 53 were severity LOW, the overlap test
  working correctly on appends. ADR-0037 records why LOW still counts as
  not-verified, and what to do instead if that proves noisy.
- 1366px re-checked by arithmetic with the fifth column: 428px of fixed columns
  leaves 310px for the project name inside the 738px track.

### Known issues
- **Still not seen rendered.** The Chrome extension was unreachable again, so the
  freshness bar and the new column have never been looked at. This is now the
  main outstanding item for the dashboard track.
- The live dev database at `~/.local/share/kernote/kernote.db` was **empty** at
  the start of this task — the "546 memories" in the previous entry came from a
  different data dir. It now holds this repository (587 memories), registered
  and scanned during verification.
- `/analyze` recomputes drift for every ref on every call (587 refs here). Fine
  at this size, not obviously fine at ten times it.
- Unchanged from the previous entry: `PRODUCT_SPEC.md` §10 drift, ADR-0009 still
  `proposed`, the stale RC tag, no undo on approval, Windows has no Git.

### Next safe task
Look at the dashboard. Then the logo reveal animation
(`design/STARTUP_ANIMATION_BRIEF.md`).

---

## 2026-11-14 — Dashboard redesign, and the accent rule re-expressed

Implemented `design/DASHBOARD_BRIEF.md` against the supplied mock. Two open
questions were settled by the user first: keep **both** themes (the new palette
becomes dark, a light equivalent is derived) and **map the nav to real screens**
rather than inventing destinations.

### What changed
- **`frontend/src/index.css`** — rewritten. Three theme blocks of 19 identical
  tokens. New: `--grid`, `--rel`/`--rel-soft` (a relationship between records),
  `--stale`/`--stale-soft` (a claim the code has moved out from under). Light
  values are derived by taking each neon to its darkest legible form; contrast
  was computed numerically before shipping, as with `--accent-contrast`.
- **`components/ui.tsx`** — `Badge` gained `rel` and `stale` tones; added `Dot`
  and `PanelTitle`.
- **`screens/Dashboard.tsx`** — rewritten: Intelligence Queue, Project Memory
  Ledger, Local System, Recent Activity.
- **`app/App.tsx`** — rewritten: grouped sidebar with the terminal wordmark,
  breadcrumb, working search, Capture Memory.
- **`components/CaptureMemory.tsx`** (new) + `api.createMemory`.
- **`screens/ProjectIntelligence.tsx`** — honours `?q=` once, then drops it.
- **`tests/unit/test_accent_is_reserved.py`** — the accent rule re-expressed.

### No invented numbers
Per the brief's "never invent system statuses or memory statistics", every
figure is read from the API and each panel has its own loading, empty and error
state. Where a figure does not exist the panel says so: Local System reports
"language model: none · extraction is deterministic" and "network: offline by
default". **The brief's freshness % tile is deliberately absent** — there is no
agreed denominator for it yet. Same for database file size and the per-project
freshness bars.

### The accent rule: re-expressed, not deleted
The brief predicted the collision and it landed. Cyan is now the brand hue as
well as the action colour, so a blanket ban on naming `--accent` outside
`ui.tsx` could not survive alongside the identity. The rule now forbids the
thing that actually did the damage: **filling** a surface with it. Lines and
type are free; only `Button` may fill. Verified by planting a violation and
confirming the test caught it. Reasoning is in the test docstring and
`design/VISUAL_PASS.md`.

### Verification performed
- `pytest backend/tests` — 422 collected, all pass, 5 skipped.
- `ruff check backend` — clean. `tsc --noEmit` — clean. `npm run build` — clean.
- New accent rule proved to fire on a planted `background: 'var(--accent)'`.
- 1366px checked **by arithmetic only** (see below).

### Known issues
- **The redesign has not been seen rendered.** The Chrome extension was not
  reachable this session, so the 1366px check is a width calculation, not a
  screenshot. Content track 1078px, right rail 328px, 738px left — the ledger
  needs ~440px. It should hold, but it is unconfirmed by eye.
- Fixed while doing that sum: the project-name cell used `truncate
  max-w-[180px]`, which is **inert on an auto-layout table cell**, so a long
  name could have pushed the panel past its track at that exact width. The
  table is now `table-fixed` with a `colgroup`.
- Older, unrelated: `PRODUCT_SPEC.md` §10 still marks Q2/Q3 open though both are
  resolved, and ADR-0009 still reads `proposed`. RC tag `v0.1.0-rc.1` sits at
  `22acb32`, now well behind. Approval still has no undo. Git is not installed
  on the Windows machine and the frontend build is untested there.

### Next safe task
Open the app and look at the dashboard at 1366px and at full width, in both
themes, then the logo reveal animation
(`design/STARTUP_ANIMATION_BRIEF.md`) — the user put UI design first and the
animation second.

---

## 2026-11-09 — Recall: the metric was measuring the composer

`missed` was the largest failure bucket after Q6 closed, so retrieval recall
looked like the next task. The diagnosis said otherwise, and found a real
product defect instead.

### What changed
- **`retrieval/answer.py`** — `AnswerBundle.related` carries records that were
  retrieved but cannot be verified against the question's words. They used to
  be **discarded in silence** (ADR-0036).
- **`eval/runner.py`** — `retrieved_answer` now reads what retrieval surfaced,
  not what the composer chose to return. Verdicts split three non-overlapping
  ways.
- **Ask screen** shows "Also retrieved, not verified" with the reason;
  `kernote_search_memory` returns `related_but_unverified`.
- ADR-0036 added (53 ADRs).

### There was no recall problem
For every one of the "missed" questions the answering document **was in the
fused top ten**, at ranks 2 to 5. Two separate faults were hiding behind one
number.

**The product binned its own best candidate.** When anything passed the support
gate, every other retrieved record was dropped — and the answering record was
repeatedly among them. Asked "which database does this project use and why was
it chosen", the deciding ADR came back at rank 2 of 10 and was withheld, while
four records that do not answer it were returned as evidence. The response
implied "these four are what I found" when six had been found.

**The metric measured the composer.** `retrieved_answer` was computed from what
was returned, so a document retrieved at rank 2 and then withheld scored as a
retrieval miss.

### What is real and what is not
| | before | after |
|---|---|---|
| Retrieved an answering doc | 80.0% | **100.0%** |
| ...and asserted it | 60.0% | **60.0%** |
| Recall@5 | 0.780 | **0.980** |
| `missed` | 9 | **0** |
| Useful abstention / false abstention | 83.3% / 20.0% | unchanged |

**The retrieval numbers moved because the metric was wrong, not because
retrieval improved.** "...and asserted it" unchanged at 60.0% is the honest
summary. What changed for a user is that the other retrieved records are now
visible.

### A rejected alternative, measured
Capping records per source file. The premise was true — the real repository's
answer to "what error metric is used" sits at distinct-file rank 6 while the top
ten collapse into four files — but it changed no verdict on either corpus and
**cost citation correctness** (54.7% → 47.7% fixture, 57.9% → 51.2% real). It
cannot work by construction: it filters the ten results the composer already
holds rather than fetching more. Reverted, and recorded in ADR-0036 rather than
deleted.

### Verification performed
- **414 tests pass, 5 skipped** (was 413). One new, pinning the silent discard.
- Both corpora measured after every change; `docs/EVALUATION.md` regenerated.
- `ruff` clean, frontend builds, demo passes.

### Known issues / blockers
1. **One genuine miss remains**, on the real repository, needing a deeper
   candidate pool rather than better ranking — a precision trade, not a free
   win.
2. The 40% gap between retrieving an answering document and asserting one is
   the support gate working as designed: those records do not mention what was
   asked, and ADR-0032 settled that assertion stays lexical.
3. Windows: Git absent, frontend build untested. UI has had no visual pass.
4. The RC tag predates all post-RC work.

### Next safe task
**The UI visual pass**, which needs reference stills. The retrieval side has no
cheap wins left — what remains is a deliberate precision/recall trade.

---

## 2026-11-09 — Q6 closed: a title match is worth the overlap bar

The last open question on retrieval quality, and the measurement redirected it
twice.

### What changed
- **`retrieval/answer.py`** — a term matched in a record's own title counts
  **2.0** toward both the overlap count and the information share (ADR-0035).
- `docs/EVALUATION.md` regenerated; Q6 struck through in the spec.
- ADR-0035 added (52 ADRs).

### Four signals, measured rather than argued
For every answerable question on both corpora, the answering record was
compared against the best-scoring wrong one:

| Signal | Favours the answer | Favours a distractor |
|---|---|---|
| **term is in the record's title** | **5** | **0** |
| term is an extracted entity | 2 | 0 |
| term was capitalised in the question | 2 | 0 |
| *position in the question* | 1 | **2** |

**Position is actively harmful** — and it is the signal Q6 proposed first. That
is the most useful thing the measurement produced.

### The blocker was not the share
Boosting the share changed **no verdict** at any multiplier from 1.3 to 3.0,
which took a second measurement to understand: `_MIN_OVERLAP` is 2, the
MongoDB record matches *one* term, so it was rejected for matching "only one
word" and never reached the share test. The flat two-term bar was doing the
refusing. Once the title weight applied to the overlap count as well, 2.0
cleared it — and 2.0 is structural, not fitted: it is exactly "a term in the
record's own title is worth the overlap bar by itself".

### Verification performed
- **413 tests pass, 5 skipped** (was 411). Two new, one of them asserting the
  boost cannot reach past the ADR-0033 veto.
- Fixture: false abstention **28.0% → 20.0%**, answered **12 → 15**,
  `lead_only` 3 → 1, citation correctness **51.6% → 54.7%**, Recall@5
  **0.740 → 0.780**, MRR 0.678 → 0.718 — with **useful abstention (83.3%) and
  wrongly-asserted (1) unchanged**. Answers bought without spending the
  guarantee.
- Real repository **completely unaffected**: abstention 100%, false abstention
  11.1%, zero wrongly asserted. The right outcome for a fix aimed at a defect
  the fixture had and it did not.
- Windows: **404 passed, 3 failed** (the Git-dependent Change Impact tests).
  `ruff` clean, demo passes on Linux.

### Known issues / blockers
1. **False abstention is 20% / 11% and is now dominated by `missed`** —
   documents retrieval never surfaced — rather than by records found and not
   asserted. That is a retrieval problem, not a support-rule one, which is why
   Q6 closes rather than being renamed.
2. `lead_first_rate` reads lower (57.1% → 40.0%) only because there are fewer
   leads to be first among. The denominator changed, not the behaviour.
3. Git is not installed on the Windows machine, so Change Impact is unverified
   there. The frontend build is untested on Windows.
4. The UI has had no visual pass. The RC tag predates all post-RC work.

### Next safe task
**The UI visual pass**, which needs your reference stills, or **retrieval
recall** — the `missed` bucket is now the largest single source of failure on
both corpora.

---

## 2026-11-09 — Code symbols work on Windows: language-pack 0.4.0 → 1.25.0

ADR-0009a left two Windows caveats. One is now gone.

### What changed
- **`tree-sitter-language-pack` 0.4.0 → 1.25.0** in `backend/requirements.txt`,
  with the reason written beside the pin (ADR-0009b).
- **The ADR-0009a guard test narrowed** to named source roots.

### The result
| | Windows | Linux |
|---|---|---|
| Before | 13 failed, 391 passed | 411 passed |
| After | **3 failed, 402 passed** | **411 passed** |

All four languages load on Windows, all 23 code-symbol tests pass there, and a
Windows scan now produces **51 memories — identical to Linux** — with matching
metrics (citation correctness 37.9%, useful abstention 83.3%, Recall@5 0.6).
The three remaining failures are Change Impact needing Git on `PATH`.

### Checked before pinning, not after
The Stage 7 lesson. A `--dry-run --report` showed **one** package changing and
nothing transitive; `tree-sitter` core stays at 0.23.2, so `Language.query()`
is untouched and no code change was needed; `pip check` is clean on both
platforms; grammar loading is immeasurable.

### Two things that could have misled me
- The first post-bump Linux run showed **4 failures and took 369s** against a
  normal 40s. Both transient — a re-run was clean at 36.7s and the code-symbol
  file passed in isolation. Had I stopped there I would have reverted a good
  bump.
- **My own guard test failed on Windows**, and it was the guard's bug: it
  globbed from the repository root and swept in the Windows virtualenv's
  site-packages, because `.venv-win` does not match a `.venv` exclusion. It
  checks named source roots now, and a planted offender confirms it still
  fires.

### Known issues / blockers
1. **Git is not installed on the Windows machine**, so Change Impact is
   unverified there. It is a documented prerequisite and everything else works
   without it.
2. The frontend build is still untested on Windows (no Node).
3. False abstention (Q6) and the UI visual pass remain.
4. The RC tag `v0.1.0-rc.1` points at `22acb32` and predates Windows work.

### Next safe task
**Q6** — centrality in term weighting, the remaining lever on false abstention.

---

## 2026-11-09 — Native Windows verified (ADR-0009a)

The largest untested claim in the project, carried since day one. Run on native
Windows Python **3.12.10 AMD64** against a checkout on an NTFS path — not WSL,
not a container. It found **three product bugs**, every one of them invisible on
Linux.

### What changed
- **Every text read and write names `encoding="utf-8"`**, with
  `tests/unit/test_text_io_is_explicit.py` to keep it that way.
- **`mcp/server.py`** forces UTF-8 on the stdio streams before anything writes.
- **`scripts/demo.py`** sends server output to a file instead of an unread
  pipe, and degrades its own console decoration when the console is not UTF-8.
- ADR-0009a added, resolving ADR-0009 and Q3 (50 ADRs).

### The install risk was unfounded
Risk R11 — native wheels on Windows, the main reason ADR-0009 stayed
`proposed` — did not materialise. `tree-sitter-language-pack` and
`onnxruntime 1.31.1` both installed from prebuilt `win_amd64` wheels, nothing
built from source, no MSVC toolchain, `pip check` clean.

### Three product bugs
1. **Locale-encoded text I/O.** Reading our own `ARCHITECTURE.md` raised
   `UnicodeDecodeError: 'charmap' codec can't decode byte 0x90` — box-drawing
   characters, under cp1252. The quiet case is worse: a byte cp1252 *can* map
   becomes mojibake, so a migration comment or a memory would be silently
   wrong. 24 failures became 14. The scan path was already safe, because
   `capture.py` reads bytes and decodes UTF-8 explicitly — this broke our own
   files, never a user's content.
2. **The MCP server wrote cp1252 to a UTF-8 transport.** One em-dash in a tool
   response and the client died with `can't decode byte 0x97`. Our content is
   full of em-dashes, so **the agent surface was unusable on Windows**. 27 of
   27 MCP tests pass after forcing UTF-8.
3. **The release gate deadlocked.** `stderr=subprocess.PIPE` with nobody
   reading it: Windows pipe buffers are small enough that the server's own logs
   filled it mid-scan, uvicorn blocked on write, and the next request timed out
   after two minutes with the process still apparently alive.

### Two environmental limits, neither a Kernote bug
- **`tree-sitter-language-pack` grammars will not load** (10 tests). Wheel
  installed, all 155 `.pyd` present, `tree_sitter` core imports, MSVC runtime
  on the machine — and `get_language("python")` still raises
  `ImportError: DLL load failed`. Same shape as the `sqlite-vec` evidence in
  ADR-0003a. Kernote degrades correctly: the scan completes with 40 memories
  instead of 51, without symbols.
- **Git is not installed** (3 tests). `gitmeta` catches `OSError` and logs
  `git.failed`, so everything but Change Impact works. **Drift still names the
  overlapping hunk**, because ADR-0019 diffs the stored capture rather than
  calling `git diff` — a decision taken for untracked files that turned out to
  carry a whole platform.

### Verification performed
- Windows: **391 passed, 13 failed, 11 skipped** (from 24 failed), with **zero
  product-code failures**.
- **`scripts/demo.py` passes on Windows, exit 0** — scan, idempotent rescan,
  cited answer, honest refusal, conflict held open with both claims, drift to
  the overlapping hunk, human resolution, evaluation, context bundle, the MCP
  surface, and a real process restart.
- Linux: **411 passed, 5 skipped**, demo still passes. `ruff` clean.

### Known issues / blockers
1. **Code symbols unavailable on this Windows install.** Worth trying a newer
   `tree-sitter-language-pack` — our pin is from Stage 3 — but that is a
   dependency bump to make deliberately, not during a verification.
2. **The frontend build is untested on Windows** (no Node there). Low risk,
   stated rather than assumed.
3 Windows metrics differ because the corpus is smaller without symbols:
   citation correctness 33.3% against 43.4%, Recall@5 0.52 against 0.60.
   Explainable, and recorded so nobody reads it as a regression.
4. The RC tag `v0.1.0-rc.1` points at `22acb32` and predates all of this.
5. False abstention (Q6) and the UI visual pass remain.

### Next safe task
**Q6** — centrality in term weighting, the remaining lever on false abstention.
Optionally first: try a newer `tree-sitter-language-pack` on Windows to see
whether code symbols can be recovered there.

---

## 2026-11-09 — A configurable include/exclude list

The last outstanding the project contract requirement. Only half of it existed:
`.gitignore` and an undocumented `.kernoteignore` were honoured, but there was
no way to *include* anything and nothing was visible in the application.

### What changed
- **`ingest/scanconfig.py`** — three layers merged with provenance: the
  built-in allowlist, `.kernote.toml` in the repository root, and a per-project
  override in Kernote's own database (ADR-0034).
- **`ingest/walker.py`** — exclude is evaluated early and always wins; include
  widens only the allowlist decision.
- **Migration 0006** — `project_scan_config`.
- **`GET`/`PUT /projects/{id}/scan-config`** — the effective configuration with
  its sources, and the local override. 28 endpoints.
- **Settings & Evaluation** — a Scan configuration panel showing the effective
  patterns, where each came from, and editable local overrides.
- **README** — the configuration is now documented, including
  `.kernoteignore`, which never was.
- ADR-0034 added (49 ADRs).

### The asymmetry is the whole design
A configuration file inside a repository is untrusted input, so include is
deliberately weaker than exclude. Include widens only the allowlist — "is this
a kind of file Kernote reads?" — and **cannot** override a secret refusal,
`.gitignore`, the size limit or the binary check. `.gitignore` has no off
switch, because the project contract requires it be respected and a configurable
exemption would be a way around that rule rather than an implementation of it.

Five of the thirteen tests assert what configuration cannot do, including
`include = [".env", "**/*"]`, which still refuses the credential file.

### Verification performed
- **410 tests pass, 5 skipped** (was 397). Thirteen new.
- `ruff` clean, frontend builds.
- Verified on the real repository, without writing to it:
  `exclude = ["datasets/**", "reports/**"]` skips 68 files with reason
  `excluded`; `include = ["data/manifests/**/*reference.json"]` recovers
  exactly the **12** reference manifests that matter without the 2906
  generated ones. `**/*.rst` is correctly a no-op, since `.rst` is already
  allowlisted.
- Migration 0006 applies to schema version 6 on a fresh database.
- Migration 0007 takes a fresh database to schema version 7.

### A note on my own first attempt
The migration initially carried its own `BEGIN`/`COMMIT` and wrote to a
`schema_migrations` table that does not exist. The runner wraps every script in
a transaction already — because `executescript()` implicitly commits an outer
one — and tracks versions in `schema_meta`. It failed loudly on the first run,
which is what that design is for.

### Known issues / blockers
1. **Kernote cannot write `.kernote.toml` for you.** Editing the repository
   file from the UI is the natural thing to want and needs the review/approval
   flow canonical writes get. Deferred rather than done badly; the local
   override covers the immediate need.
2. **No native-Windows verification.** Still the largest untested claim.
   ADR-0009 remains `proposed`.
3. False abstention 28% on the fixture, 11% on the real repository. Q6
   (centrality in term weighting) is the lever.
4. Approval has no undo. The UI has had no visual pass.
5. The RC tag `v0.1.0-rc.1` points at `22acb32` and does not include this work.

### Next safe task
**Windows verification** — the existing suite and `scripts/demo.py` run on
native Windows, which needs a Windows machine and no new code. Then **Q6**.

---

## 2026-11-09 — Real-repository evaluation (Q2): the central claim failed on first contact

Everything measured so far came from a corpus written for the purpose. Pointing
the harness at a real repository broke the product's central claim within
minutes, and 392 passing tests had nothing to say about it.

### What changed
- **`ingest/secrets.py`** — a low-precision hit now needs the key *name* to
  name a credential, not just a credential-shaped value (ADR-0020c).
- **`ingest/walker.py`** — `.json` allowlisted by filename, not by suffix.
- **`retrieval/answer.py`** — nothing is asserted when 30% or more of a
  question's terms occur nowhere in the project, and the user is told that in
  those words (ADR-0033). `one`, `them` and `us` added to the stopwords.
- **`eval/questions-ivforge.json`** — 13 labels over the real repository, kept
  as the evidence behind the numbers; the corpus is not in this repository.
- `docs/EVALUATION.md` has a real-repository section. ADR-0020c and ADR-0033
  added (48 ADRs).

### Three findings, none of which a synthetic corpus could show

**1. Useful abstention was 0 of 4 on a real repository** — against 66.7% on the
fixture. Retrieval was *better* there (Recall@3 0.889 against 0.600), so this
was never a retrieval problem: ADR-0030's share threshold can be cleared by
**breadth**. Ask "what is the monetary cost in dollars of one SPICE simulation
run" and `monetary` and `dollars` carry half the question's weight and appear
nowhere, while a document matching the five ordinary words scores 0.467 against
a 0.30 bar. The more everyday words a question has, the easier it was to answer
it without addressing it. Now **100.0%** correct abstention on the real
repository, 0 wrongly asserted, with false abstention and the answered count
both unchanged.

**2. The secret scanner refused 2918 of 2938 files** — including three of the
repository's seven Markdown documents and two Python scripts. One detector,
`Hex High Entropy String`, plus a value-shape rule ending in `len(value) >= 20`:
every SHA-256 digest in a JSON manifest is credential-shaped. The heuristic was
tuned on Kernote's own prose repository in Stage 3 and had never seen data.
Refusals **2918 → 0**, warnings 0 → 9, scan **30.6s → 2.0s**, and the
documentation that was being dropped now produces 8 procedure memories that did
not exist before.

**3. `.json` as an allowed suffix swept in 2909 generated manifests.** JSON is
a data format and its meaningful instances are named config files, which the
name list already covered. A project memory tool should read a project's
documentation and configuration, not its data.

### A rule I implemented and then rejected on measurement
The first fix for finding 1 was a per-record rule requiring a match on the
question's heaviest term. A positive-control test caught it refusing *correct*
answers: when a question's subject words are common enough in the corpus to
weigh zero, an incidental absent word becomes the peak. Measured head to head
on both corpora it was strictly worse — 3 of 4 abstentions and two answers lost,
against 4 of 4 and none. It is recorded in ADR-0033 as a rejected alternative
rather than quietly deleted.

### Verification performed
- **397 tests pass, 5 skipped** (was 392). Five new: two pinning the secret
  scanner in both directions, one the JSON allowlist, and two the breadth
  defect and its positive control.
- Measured on both corpora after every change, not just the one being fixed.
- `ruff` clean. `docs/EVALUATION.md` regenerated from real runs.
- One test fixture corrected: a positive control on a 3-document corpus proved
  nothing, because with that few records every content word is ubiquitous and
  inverse document frequency makes them all worth zero. Same class of fixture
  fault as Stage 7's.

### Known issues / blockers
1. **False abstention rose on the fixture, 20.0% → 28.0%.** That is the price
   of finding 1 and it is the right direction for this product, but it is a
   real cost. Q6 (centrality in term weighting) is still the lever on it.
2. **The include/exclude list is still not configurable**, and finding 3 makes
   that gap sharper: a project with meaningful JSON under a non-standard name
   now loses it, visibly but without recourse. The project contract asks for the
   configurable list; this is the strongest case yet for building it.
3. The RC tag `v0.1.0-rc.1` points at `ca0f72c` and does **not** include this
   work. Its message quotes citation correctness 52% and abstention 67%; the
   fixture now measures 51.6% and 83.3%.
4. No native-Windows verification. Approval has no undo. The UI has had no
   visual pass.

### Next safe task
**The configurable include/exclude list**, which is a the project contract requirement,
is now the blocking issue for scanning real repositories well, and is the
natural home for the JSON question. Then **Windows verification**, then **Q6**.

---

## 2026-11-09 — Q5 closed: assertion stays lexical, leads are ordered by meaning

Q5 was the named cause of the product's largest quality weakness. Closing it
properly meant measuring the obvious fix first, and the obvious fix was wrong.

### What changed
- **`retrieval/answer.py`** — when nothing is lexically supported, the returned
  leads are ordered by semantic similarity rather than by the hybrid fusion,
  and the statement says so (ADR-0032).
- **`eval/runner.py`** — reports `answer_rank` per question and
  `lead_first_rate` overall.
- `docs/EVALUATION.md` regenerated. ADR-0032 added (46 ADRs).

### The answer to Q5 is no, and here is the evidence
Before changing anything I measured the two relaxations that would let a
semantic match be asserted. Dropping corpus-absent terms from the
information-share denominator changed **no verdict at all**. Adding the missing
function words to the stopword list changed no verdict and lowered citation
correctness. **Both together: useful abstention collapsed from 66.7% to 33.3%
and wrongly-asserted answers doubled from 2 to 4.**

So the relaxation path buys nothing measurable and costs the one claim the
product is built on. Assertion keeps requiring lexical verification: a cosine
score is not something a reader can check by reading.

### Two findings that reframe the 20-24% false abstention
**It is mostly not a semantic problem.** For "why was MongoDB removed from the
stack", the document that answers it matched the question's *subject*
(`mongodb`, share 0.283) and a distractor matched one incidental rare word
(`stack`, 0.385) and cleared the bar. Inverse document frequency is standing in
for centrality, and in a small corpus an incidental rare word outweighs the
subject of the sentence. That is a limitation of ADR-0030's rule, not of Q5,
and it is now **open question Q6**.

**The lead path was ordered by the signal that had just failed.** Leads came
back in hybrid-fusion order, which keyword hits dominate. On q29 the answering
document is first by meaning, fourth by fusion and eleventh by keyword.

### Verification performed
- **392 tests pass, 5 skipped** (was 390). Two new, one driven by a planted
  corpus so the assertion does not depend on a 31-question measurement.
- Measured under identical conditions with the vector index present: the right
  document is first among leads for **4 of 6 questions against 2 of 6 before**.
  Abstention (66.7%), asserted answers (12) and citation correctness (52.2%)
  all unchanged — a gain on the lead path with no movement in the guarantee.
- Ranking metrics improved as a side effect, since lead ordering is part of
  what they measure: Recall@1 0.560 → 0.620, MRR 0.611 → 0.668, nDCG@10
  0.663 → 0.700.
- `ruff` clean.
- One regression recorded rather than averaged away: on q28 the answering
  document moved from rank 3 to rank 5, because semantic similarity preferred a
  glossary entry on the same subject.

### Known issues / blockers
1. **False abstention is still 20-24%, and Q5 is no longer the explanation.**
   Q6 is: the share rule cannot distinguish a question's subject from an
   incidental rare word. The next attempt should weight by centrality —
   position in the question, or agreement with the document's title — not by
   rarity alone.
2. The lead ordering depends on the opt-in embedding index. With no model
   cached there is no semantic signal and leads keep the fusion order; the
   statement then omits the "ordered by meaning" sentence rather than claiming
   it.
3. No native-Windows verification. ADR-0009 still `proposed`.
4. Approval has no undo; the include/exclude list is not configurable; the UI
   has had no visual pass.

### Next safe task
**Windows verification**, which is the largest untested claim in the project
and needs only the existing suite and `scripts/demo.py` run on native Windows.
Then **Q6**, which is now the real lever on false abstention.

---

## 2026-11-09 — Stage 9: release candidate

The gate for this stage is a demo that runs end to end from a clean clone, and
writing it found two defects that every previous stage had missed — both of
them in the documented happy path rather than in the code.

### What changed
- **`scripts/demo.py`** — the end-to-end release gate. It drives the real HTTP
  API through: scan, idempotent rescan, a cited answer, an honest refusal, a
  planted contradiction held open with both claims, drift detected down to the
  overlapping hunk, a human resolution, a budgeted context bundle, the
  read-only MCP surface, the measured evaluation, and a **real process
  restart**. It exits non-zero if any check fails. `just demo`.
- **`backend/requirements-dev.txt`** — `honcho==2.0.0` added. See below.
- **`db/repositories/findings.py`** — a resolved finding now suppresses its own
  cause (ADR-0031).
- **README** — status, demo instructions, and a known-limitations list that
  now names the tested languages, the tested agent, the untested platform and
  the measured numbers.
- ADR-0031 added (45 ADRs).

### Two defects in the documented happy path

**1. `honcho` was never installed.** The README's primary instruction for
running the product is `backend/.venv/bin/honcho start`. It is not in
`requirements-dev.txt` and never was: it existed only in this machine's
virtualenv because it had been installed by hand during Stage 2. A clean clone
following the README got `command not found`, exit 127.

This is the **exact Stage 2 lesson repeating** — a documented command that had
never been run from a clean install — and it survived six stages and three
defect sweeps because every sweep tested the code rather than the instructions.
Now pinned, and `honcho start` is verified from a fresh clone: API 200, web
200, and the web app's `/api` proxy 200.

**2. The review queue refilled with whatever you had just closed.** The dedupe
query matched only `status='open'`, so resolving a finding stopped it
suppressing itself and the next `analyze` inserted an identical one. Every test
that resolved a finding stopped there, so nothing caught it; the demo caught it
because it resolves a finding and then keeps working. Fixed in ADR-0031, with a
test asserting both that the resolved finding stays closed and that a further
edit still raises a new one.

A third, smaller one was mine: the demo printed "survives a restart" while only
re-querying the API. It now really stops and restarts the process, and 53
memories, the project and the findings all come back.

### Verification performed
- **Clean clone, from scratch**: `git clone`, `python3 -m venv`,
  `pip install -r backend/requirements-dev.txt`, `npm install` — all clean, and
  `pip check` reports no broken requirements.
- **390 tests pass, 5 skipped** on that clean clone (the skips are the ranx
  cross-checks, which pass under `requirements-eval.txt`).
- `npm run build` clean on the clean clone.
- **`scripts/demo.py` passes on the clean clone**, every check green.
- `backend/.venv/bin/honcho start` verified on the clean clone.
- `ruff check` and `ruff format --check` clean.

### Known issues / blockers
1. **No native-Windows verification.** The native wheels
   (`tree-sitter-language-pack`, `fastembed`/onnxruntime) have only run on
   Linux/WSL2. ADR-0009 remains `proposed`. This is the largest untested claim
   in the project and it is stated in the README rather than hidden.
2. **False abstention 20-24%** remains the headline quality weakness, with the
   `lead_only` gap its cause. Open question Q5 (ADR-0014a) is the decision that
   would close it.
3. The support threshold is fitted on the same 31 questions the metrics are
   reported on; a held-out split needs more questions.
4. Approval still has no undo.
5. The include/exclude list is not configurable (`walker.py` has a hardcoded
   `EXCLUDED_DIRS`); the project contract asks for a configurable one.
6. The UI has had no visual pass. It shows real data and real error states, and
   that is a different thing from being designed.
7. Proposal items P3, P6-P10, P12-P13 unapplied. Q1/Q2/Q4 open, Q5 new.

### Next safe task
The RC is tagged **locally** and has not been pushed, so nothing is published
yet. The next moves, in the order I would take them:
1. **Windows verification** — the biggest unknown, and purely a matter of
   running the existing suite and demo on native Windows.
2. **The UI visual pass**, once reference stills are available.
3. **Q5** — whether a semantic match with no lexical overlap can ever be
   asserted as evidence. Closing it would address the 20-24% false abstention.

---

## 2026-11-09 — Stage 8 defect sweep: the measurement apparatus was itself wrong

Seven defects. Three were in the code the evaluation measures, and **four were
in the evaluation itself** — which is the uncomfortable part: a harness that
reports confident numbers about correctness is the last place a wrong number
can be noticed.

### What changed
- **`retrieval/answer.py`** — document frequency now comes from the FTS index
  instead of a full table scan, and term weights are clamped at zero
  (ADR-0029a).
- **`eval/metrics.py`** — duplicate keys collapse inside the metric, and
  `k <= 0` returns `nan` instead of `0.0`.
- **`eval/runner.py`** — a report lists only the cut-offs its retrieval depth
  can support, and states the depth.
- **`eval/questions.py`** — a corpus path that escapes the question set's own
  directory is refused, as is an empty set (ADR-0029b).
- **Settings screen** — shows the retrieval depth and no longer labels nDCG
  with a fixed k.
- `docs/EVALUATION.md` regenerated. ADR-0029a and ADR-0029b added (44 ADRs).

### The seven defects

**1. The support gate was a full table scan on every question.** The worst of
them. It read every memory and chunk and stemmed the text in Python for a
handful of counts: **75ms per question on 754 rows, 88-92% of the whole cost of
answering**, growing linearly with the vault. It now uses the FTS index, which
is already tokenised `porter unicode61` and therefore already stem-aware.
`ask()` went **83ms → 18ms** and **86ms → 30ms**, and the evaluation's verdicts
came out **identical** — answered 12, lead_only 3, missed 10. Citation
correctness even rose slightly, 41.9% → 43.4%, because Porter weights a few
terms differently.

**2. A term in every record carried a negative weight.** `log(N/(1+df))` goes
negative once `df` reaches `N`. A question whose terms were all ubiquitous
summed to a negative total weight, which flipped the sign of the share;
matching a common term gave -0.005. The gate behaved correctly **by luck**, since
a negative share is below any positive threshold — which is the kind of
correctness that stops being correct the moment anything nearby changes.

**3. A metric reported cut-offs it never measured.** `Recall@10` was printed
for a run that only ever retrieved three documents: Recall@3 under a different
name, and a `limit=3` run printed four identical numbers under four labels.
This is the Stage 7 lesson — a stated number must describe what was delivered —
reappearing in the tool built to check honesty.

**4. A repeated document scored twice.** Recall read **1.0** when one of two
answering documents had been found. `_ranked_paths` does dedupe, so nothing was
mismeasured in practice, but a metric cannot depend on its caller being careful.

**5. `recall_at_k(k=0)` returned 0.0**, which `mean` averaged in as a real
score. `precision_at_k` already returned `nan`; the two disagreed.

**6. A question set could aim a scan at any directory.** `"corpus":
"../../../../etc"` loaded and resolved to `/etc`; so did `"/etc"`. The project contract
forbids reading credentials during scanning, and relying on the walker's
deny-list to save us is not a security property. A corpus must now resolve
inside the set's own directory or one level above (ADR-0029b).

**7. An empty question set loaded happily** and produced a report of `n/a`
everywhere that still looked like a measurement.

### Verification performed
- **389 tests pass, 5 skipped** (was 379). 10 new, one per defect plus the
  allowed-layout cases.
- The ranx cross-check still agrees to 1e-9 after the distinct-key change:
  **16 passed** under `requirements-eval.txt`.
- `ruff` clean, `tsc -b` and `npm run build` clean.
- Before/after timings measured on this repository at 754 rows, not a fixture.
- `docs/EVALUATION.md` regenerated; the ADR-0014a conclusion is unchanged.

### Known issues / blockers
1. **False abstention remains the headline weakness at 20-24%** and the
   `lead_only` gap is its cause. Open question Q5 (ADR-0014a) is the decision
   that would close it.
2. The support threshold is still fitted on the same 31 questions the metrics
   are reported on. A held-out split needs more questions.
3. **The include/exclude list is not configurable.** `walker.py` has a
   hardcoded `EXCLUDED_DIRS`, and the project contract asks for a configurable list.
   Pre-existing, not Stage 8, and now more visible because `samples/eval-repo`
   means a self-scan of Kernote ingests the fixture service's documents --
   including its deliberate contradiction, which our own conflict detection
   will flag against our own project. Harmless but noisy for dogfooding.
4. Approval still has no undo (Stage 6).
5. Proposal items P3, P6-P10, P12-P13 unapplied. ADR-0009 open; Q1/Q2/Q4 open,
   Q5 new. No Windows verification of the native wheels.

### Next safe task
**Stage 9 (Day 25): the release candidate.** Tag, demo script that runs end to
end from a clean clone, and a known-limitations list with measured numbers
behind it. The honest headline: citation correctness 52%, useful abstention
67%, Recall@5 0.70, with the `lead_only` gap named as the known weakness.

---

## 2026-11-09 — Stage 8: evaluation, and what it found

The first honest measurement of retrieval quality, and it immediately failed
the product's central claim. That is what an evaluation is for.

### What changed
- **`samples/eval-repo/`** — a 22-file fixture corpus with deliberate
  distractors and a stale document that contradicts the README. The old
  `samples/demo-repo` is 67 lines; on a corpus that small every metric is 1.0.
- **`eval/questions.json`** — 31 labelled questions, graded 2/1, of which 6 are
  unanswerable and 5 are deliberate paraphrases (ADR-0029). Labels are
  validated against the corpus on load, because a rotted label silently lowers
  every score.
- **`kernote/eval/`** — `metrics.py` (Recall@k, MRR, nDCG, precision),
  `questions.py` (typed, validated loader), `runner.py` (scores a run and
  renders a report).
- **`requirements-eval.txt`** — `ranx` as the *authority* we check against,
  never a runtime dependency.
- **`api/routers/evaluation.py`** + a real **Settings & Evaluation screen** —
  the last placeholder screen is now live. 26 endpoints.
- **`docs/EVALUATION.md`** — the measured results, both configurations.
- ADR-0029, ADR-0030, ADR-0014a (42 ADRs).

### Three findings, in order of how much they matter

**1. Useful abstention was 0 out of 6.** The claim that Kernote says "evidence
was not found" when that is the truth failed every unanswerable question. A
fixed bar of two matched terms let "what is the contractual delivery SLA for
next-day orders" match "delivery" and "orders" — words in half the corpus — and
answer confidently, while "SLA" appears nowhere. Support now also requires 30%
of the question's inverse-document-frequency weight (ADR-0030). **0% → 66.7%**,
citation correctness **53.8% → 60.3%**, all 355 existing tests still passing.

The threshold is one parameter fitted on 31 questions with no held-out split,
and the classes overlap (weakest answerable 0.26, strongest unanswerable 0.54),
so no threshold gets both right. The gain is real but optimistic.

**2. Embeddings buy retrieval that the support gate throws away.** This
resolves ADR-0014 and cancels its four-way benchmark. Adding MiniLM moves
retrieval success **60% → 72%** and `missed` from 10 to 7 — and `answered`
stays at **12**, because every newly found document becomes a `lead_only`. The
support gate is lexical and a paraphrase has no lexical overlap: ask about
"what the taxman takes" and the invoice module is retrieved at rank 2 and never
says "taxman". All five paraphrase questions fail under both configurations.
Benchmarking potion-8M against MiniLM would optimise a stage whose output is
discarded. Recorded as ADR-0014a with open question Q5.

**3. Our nDCG was 4% wrong, and `ranx` caught it.** We used the exponential
`2**grade - 1` gain where `ranx` uses the linear Järvelin gain: 0.305 against
0.319. A metric that is quietly 4% off is far more dangerous than one that
crashes, and nothing but the cross-check would have found it. This is the
clearest argument for the library-as-authority pattern in ADR-0029.

### Two mistakes of my own worth recording
- **The abstention metric was wrong before the product was.** It counted only
  `not_found` as declining, scoring 0% while the system was correctly declining
  on four of six questions via `weak_evidence`. I nearly "fixed" a product that
  was already behaving correctly. Only `evidence_found` asserts an answer.
- **The first embedding comparison was measuring my own labelling bias.** It
  showed semantic retrieval adding nothing, because every question had been
  written while looking at the document that answers it. Adding five paraphrase
  questions reversed the conclusion. A question set written from the corpus
  flatters keyword search.

### Verification performed
- **376 tests pass, 5 skipped** (was 355). The 5 skips are the ranx
  cross-checks; run under `requirements-eval.txt` they pass, verified
  separately: **12 passed**.
- `ruff check` and `ruff format --check` clean; `tsc -b` and `npm run build`
  clean.
- Measured numbers in `docs/EVALUATION.md` come from a real run over the
  fixture corpus, both configurations, not from a fixture.
- A test asserts the evaluation does not leak its fixture corpus into the
  user's vault.

### Known issues / blockers
1. **False abstention is now the headline weakness at 20-24%**, and the
   `lead_only` gap is its cause: the system finds the right document and
   declines to call it an answer. Open question Q5 (ADR-0014a) is the decision
   that would close it, and it deliberately has no answer yet.
2. `answer_rate` is 48%. On a corpus this small that is a bound for regression
   detection, not a quality claim.
3. The support threshold is fitted on the same 31 questions the metrics are
   reported on. A held-out split needs more questions.
4. Approval still has no undo (Stage 6).
5. Proposal items P3, P6-P10, P12-P13 unapplied. ADR-0009 open; Q1/Q2/Q4 open,
   Q5 new. No Windows verification of the native wheels.

### Next safe task
**Stage 9 (Day 25): the release candidate.** Tag, README, demo script that runs
end to end from a clean clone, and a known-limitations list that now has
measured numbers behind it rather than estimates. The honest headline for the
RC is citation correctness 51% and useful abstention 67% on our own labelled
set, with the `lead_only` gap named as the known weakness.

---

## 2026-11-09 — Stage 7 defect sweep: a stated number must describe what was delivered

Every defect here is the same shape: **a confident number or claim that was
wrong**, in the one place a caller has no way to check it. None of them crashed
anything, which is why a sweep was needed rather than a bug report.

### What changed
- **`apply/context_bundle.py`** — the token count is now **measured from the
  finished document** instead of summed from its parts, fitting is a search
  over rendered sizes, memories past the candidate cut-off are counted and
  reported, and `over_budget` is stated when the budget cannot be met
  (ADR-0027a).
- **`mcp/server.py`** — whole-word subject matching, refusal of an empty or
  stopword subject, rejection of an unknown `memory_type`, an honest outcome
  when a filter empties the result, and `tool_manifest()` so the UI's tool list
  comes from the live registry (ADR-0028a).
- **`api/routers/agents.py`** — the tool list is derived, not hand-written; the
  bundle response carries `not_considered`, `excluded_total` and `over_budget`.
- **Agent Integrations screen** — "Dropped" became **"Left out"** and shows the
  true total, split into over-budget and unranked.
- **README** — the status block said "Stage 2 of 9 complete", five stages
  behind. Stale docs are this product's subject matter; ours should not be an
  example.
- ADR-0027a and ADR-0028a added (37 ADRs).

### The six defects, measured before and after
1. **The bundle lied about its own size.** Asked for 200 tokens it returned
   **792** and reported **187**; at 500 it reported 482 and was 1118. The
   per-entry sum never saw the "did not fit" list, which *grows as the budget
   shrinks*. Now stated equals measured at every budget from 200 to 32000,
   asserted by a parametrised test.
2. **It under-reported what it left out by 260 records.** The note said "113
   did not fit" while 260 more had never been weighed against the budget at
   all. Now `included + dropped + not_considered` equals the project's current
   total, and a test asserts that identity.
3. **`get_decision` matched substrings.** `"it"` matched "SQLite" and returned
   six decisions; `"a"` returned ten; an **empty** subject returned ten
   arbitrary decisions as though they matched. This is the Stage 3
   `"adr"`-matches-"Quadratic" defect in a new module — the fix had not
   travelled with the lesson.
4. **`search_memory` claimed records it had filtered away.** An unknown
   `memory_type` was accepted silently, then returned `evidence_found` and
   *"19 supporting record(s) found"* beside an empty list.
5. **The Agent Integrations tool list was a hand-written copy** of the real
   registry. Rename a tool and the screen lies. Now derived, with a test
   asserting the two match.
6. **"No memory available" when 380 memories existed.** None fitted a tight
   budget, and the bundle blamed the vault for a budget problem — sending the
   reader off to rescan for nothing.

### Verification performed
- **355 tests pass** (was 342). 13 new, each pinning one defect above.
- `ruff check` and `ruff format --check` clean, `tsc --noEmit` clean,
  `npm run build` succeeds.
- Dogfooded on this repository at **380 memories**: the before/after numbers
  quoted above are measured from that corpus, not from a fixture.
- Re-verified against a **real MCP client over stdio**: four tools, none
  mutating; `get_decision("it")` and `get_decision("")` now both decline;
  `search_memory(memory_type="bogus")` returns `invalid_request`; and
  `build_context` reported 200/200, 933/1000 and 3144/4000 tokens with the
  stated figure equal to the measured one in every case.

### One regression, caught by an existing test
Making content win the budget made a 400-token bundle list **no** dropped
titles at all — trading the size lie for a silence. The listing now has a
floor of four titles. The test that caught it was the Stage 7 test asserting a
dropped entry is *named* in the markdown, which is a good argument for
asserting on behaviour rather than on wording.

### Two probe faults worth recording
The live MCP run hung with no output and looked exactly like the Stage 7 stdout
bug returning. It was my harness: `KERNOTE_DATA_DIR` pointed at a directory
whose database was not named `kernote.db`, so the server found no project,
raised and exited — and **the client waits silently when the server dies during
startup**. Worth knowing before blaming the protocol. Separately, a truncation
test driven through a scanned file asserted nothing, because extraction fills
`summary` and the bundle prefers it; a summary never reaches the 1200-character
cap, so the test had to drive a stored memory directly.

### Known issues / blockers
1. **ADR-0014's four-way embedding benchmark remains the oldest open item**,
   blocked on the labelled question set (P11).
2. Approval still has no undo (Stage 6).
3. `search_memory` silently rewrites a `limit` of 0 or a negative to 1. It is
   clamping rather than lying, so it was left alone.
4. The MCP server holds one SQLite connection for its lifetime; untested under
   simultaneous use with the UI.
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

### Next safe task
**Stage 8 (Days 23-24): polish and evaluation.** The labelled question set,
`ranx` metrics (Recall@k, MRR, nDCG), citation-correctness and abstention-rate
measurement, and ADR-0014's four-way embedding comparison.

---

## 2026-11-09 — Stage 7: agent delivery

### What changed
- **`apply/context_bundle.py`** — the budgeted Markdown bundle. States its
  token estimate, **lists what it dropped**, cites every claim, excludes
  superseded records and marks interpretations.
- **`mcp/server.py`** — four read-only tools over stdio (ADR-0028).
- **`kernote/logging.py`** — shared logging to **stderr** with a late-bound
  sink (ADR-0027).
- **`api/routers/agents.py`** — `POST /context`, `GET /mcp`. 24 endpoints.
- **Agent Integrations screen** — the MCP registration command with a copy
  button, the tool list with "read-only" stated, and a bundle builder with a
  budget control and a .md download.
- ADR-0027 and ADR-0028 added (35 ADRs).

### Verification performed
- **342 tests pass** (was 328). 14 new, including three that drive a **real MCP
  server as a subprocess over stdio**.
- `ruff` clean, frontend builds, and **`pip check` reports no broken
  requirements** — which matters because of the conflict below.
- Live MCP client session: 4 tools advertised, none mutating;
  `project_summary` returned 365 memories with cited decisions;
  `get_decision("sqlite-vec")` returned ADR-0003 with its source;
  `get_decision("quantum teleportation")` returned an explicit
  "evidence was not found"; `build_context` came back at ~988 of 1000 tokens.

### Three bugs, and why only one was findable by unit tests
1. **`pip install mcp` broke the whole application.** It pulled
   `starlette 1.10.0` against FastAPI's `<0.42`, and all 328 tests stopped
   collecting. Risk R12 from ADR-0010, realised. Resolved by pinning
   `starlette==0.41.3` and `sse-starlette==2.1.3` **with the reason beside
   them**, since an unexplained pin invites a future tidy-up.
2. **Logging to stdout corrupted the MCP protocol.** stdout *is* the JSON-RPC
   transport; the first log line hung the client with no error. Calling the
   tool functions directly works perfectly — only running a real server over
   stdio shows it. Then the first fix bound `sys.stderr` at configure time,
   so pytest's `capsys` closed it and one test poisoned every later log call
   in the suite. The sink is now resolved at write time.
3. **A parameter that silently did nothing.** `kernote_search_memory`'s
   `memory_type` filter contained an `or True`, so it never filtered. It now
   looks the type up on the memory, and a test asserts the result set is
   actually narrowed.

### Three test faults worth remembering
The bundle tests failed for reasons that were mine, not the product's: a
two-document fixture is ~277 tokens so **no budget would ever drop anything**;
asserting `"Architecture" not in markdown` collides with the rendered section
heading; and ranking a task of "which database and why" correctly prefers the
README (which says "free of **database** imports") over an ADR that says
"PostgreSQL" and "persistence" — the same Stage 5 limitation, now hit from a
different direction.

### Known issues / blockers
1. **ADR-0014's four-way embedding benchmark is now the oldest open item**, and
   it needs the labelled question set (P11). That plus `ranx` metrics is the
   whole of what the Day-25 acceptance criteria measure.
2. Approval still has no undo (Stage 6).
3. The MCP server holds one SQLite connection for its lifetime and sees
   whatever the UI writes, since both point at the same file — fine for a local
   single-user tool, but untested under simultaneous use.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

### Next safe task
**Stage 8 (Days 23-24): polish and evaluation.** The labelled question set,
`ranx` metrics (Recall@k, MRR, nDCG), citation-correctness and
abstention-rate measurement, and ADR-0014's four-way embedding comparison.
This is the oldest deferred work in the project and what the Day-25 criteria
actually require.

---

## 2026-11-09 — Stage 6 defect sweep

### Probed and found sound
- **Change Impact at width.** A 1,200-file commit range works: SQLite's
  parameter limit here is **250,000**, not the 999 often assumed. Now pinned by
  a test rather than assumed.
- Merge chains cannot form by accident — an already-superseded record is
  refused as a merge input.

### Bugs found and fixed (ADR-0025a)
1. **Approval silently reverted a human's edit.** The merged content is
   computed when the duplicate is *detected*; editing the keeper and then
   approving applied the stale preview over the newer wording. This is the
   worst defect found in the project so far — everything else produces a bad
   *suggestion*, this destroyed deliberate work under a button that promises
   nothing is lost. The preview now carries a fingerprint of each input and
   approval refuses when either has changed, leaving the proposal pending so a
   fresh analysis replaces it.
2. **Merging into an archived record succeeded.** `supersede_into` checked the
   absorbed record's status but never the keeper's, so merged wording could
   land somewhere hidden from every listing. Both sides must now be live.

### Verification performed
- **328 tests pass** (was 321). 7 new sweep regressions.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- Re-probed: an edit before approval is refused with the edit intact; an
  archived keeper is refused; an untouched proposal still merges cleanly
  (citations 1 → 2, 2 revisions).

### Known issues / blockers
1. **Approval is still not reversible.** The data supports an undo — the
   absorbed record is byte-intact and the supersession is recorded — but there
   is no endpoint. Worth adding before anyone relies on the merge button.
2. Resolved findings are closed, not re-openable.
3. **ADR-0014's four-way embedding benchmark remains the biggest gap**, and it
   needs the labelled question set (P11). That plus `ranx` metrics is the
   Stage 8 story and the oldest outstanding item in the project.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

No known Stage 6 defects remain open.

### Next safe task
**Stage 8's evaluation work is the higher-value target** even though Stage 7
comes first in the roadmap: F9 (MCP) is first on the scope-cut list, while the
labelled question set, `ranx` metrics and the embedding benchmark have been
deferred since Day 1 and are what the Day-25 acceptance criteria actually
measure.

---

## 2026-11-09 — Stage 6: the review flow

The differentiating milestone. Detection was proven by the P4/P5 spikes; this
is the half where a human decides and the decision is recorded.

### What changed
- **`memories.supersede_into()`** — merge into an *existing* record, in one
  transaction: carries the absorbed record's citations onto the keeper, writes
  revisions on both, closes the absorbed one with `superseded_by` and a
  `valid_until`, records a typed edge. Nothing deleted (ADR-0025).
- **`maintain/review.py`** — `approve_proposal`, `reject_proposal`,
  `resolve_finding`. Approval **verifies its own promise**: it compares the
  citations the preview advertised against the keeper's actual citations and
  rolls back if any is missing.
- **`maintain/impact.py`** — Change Impact over a commit range, with `direct`
  vs `same_file` classification (ADR-0026).
- **`ingest/gitmeta.py`** — `resolve`, `changed_files`, `file_diff`,
  `recent_commits`.
- **Migration 0005** — `feedback.verdict` now allows `'resolved'`.
- **API** — approve, reject, resolve, impact, commits. 22 endpoints.
- **UI** — the Memory Intelligence Center's buttons now do something:
  *Approve merge* / *Not a duplicate* on proposals, *Needs attention* /
  *False positive* on findings, with the citation delta reported back. New
  **Change Impact** screen with a commit picker.
- ADR-0025 and ADR-0026 added (33 ADRs).

### Verification performed
- **321 tests pass** (was 301). 20 new.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- **Live over HTTP on this repository:** scan 105 files / 348 memories →
  analyze → approve a real proposal → **citations 1 → 2, 2 revisions, promise
  held**, absorbed record still fetchable with its wording intact, second
  approval returns **409**. Resolve a conflict finding → 200. Change Impact
  `HEAD~1..HEAD` → 6 files, 41 memories in them, **5 directly affected**.

### Two bugs found while building
1. **A CHECK constraint disagreed with the code.** `findings.status` has always
   allowed `'resolved'`, but `feedback.verdict` did not, so resolving a finding
   as resolved passed every application check and then failed on the last
   statement — the review flow's own happy path. Migration 0005 rebuilds the
   table; SQLite cannot alter a CHECK.
2. **A fixture produced no memories** because its section body was under the
   40-character floor, which surfaced as an `IndexError` rather than a clear
   failure. Lengthened; worth remembering that the extractor's minimum body
   length is a silent filter in tests.

### Known issues / blockers
1. **Approval is not reversible.** Superseding is recorded and the absorbed
   record is intact, so an undo is *possible* — but there is no endpoint for
   it. Worth adding before anyone relies on the merge button.
2. Resolved findings are closed, not re-openable.
3. **ADR-0014's four-way benchmark is still the biggest gap**, and it needs the
   labelled question set (P11). That plus `ranx` metrics is the Stage 8 story.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

### Next safe task
Either the **Stage 6 defect sweep**, or **Stage 7 (Days 21-22): agent
delivery** — the context-bundle export and the four read-only MCP tools. Note
that F9 is the first thing on the scope-cut list, so Stage 8's evaluation work
(the labelled question set, `ranx` metrics, the embedding benchmark) is the
higher-value target if time is short.

---

## 2026-11-09 — Stage 5 defect sweep

### Probed and found sound
- **Latency.** 450 vectors: search p50 **5 ms**, a full ask **7 ms**. Loading
  the whole matrix per query is not a problem at this scale.
- **Index build.** 322 memories + 316 chunks in ~41 s, then fully incremental.

### Bugs found and fixed (ADR-0024a, migration 0004)
1. **An edited memory kept its old vector**, so semantic search matched text
   the project no longer contained — the derived index diverging from the
   source of truth. `embeddings.source_hash` now records exactly what was
   embedded. `updated_at` was the tempting alternative and is wrong:
   importance refinement touches it without changing a word.
2. **Vectors outlived their targets.** `embeddings` has a polymorphic target so
   it cannot carry a foreign key; deleting a project left its vectors forever.
   `AFTER DELETE` triggers now do what the FK cannot.
3. **The stemmer over-matched**: a fixed two-character chop turned "import"
   into "impo", a prefix of "important". Now strips known suffixes and compares
   whole stemmed tokens, with a `+e` variant for "deleted"/"delete".
4. **`CI`, `DB`, `UI`, `ML` were unsearchable** — the content-term floor
   excluded them, so "what does the CI do" could only abstain.

### Verification performed
- **301 tests pass** (was 287). 14 new sweep regressions.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- Both bugs re-probed after the fix: an edit now re-embeds exactly one record
  and `search("Cassandra")` finds it; a project delete leaves **0** orphans.
- 10 of 10 stemming cases correct in both directions.

### A self-reference worth noting
Asking *"what is the airspeed velocity of an unladen swallow"* against this
repository now returns `evidence_found` — because ADR-0024 documents that exact
sentence as its own worked example, so the corpus genuinely contains it. Not a
regression: the controlled fixtures still assert abstention. The same
self-reference bit the secret scanner in Stage 3, and it is worth remembering
that a project documenting its own behaviour becomes part of its own corpus.

### Known issues / blockers
1. **ADR-0014's four-way benchmark is still outstanding.** `fastembed` does not
   carry the potion models, so they need `model2vec` as a second runtime (an
   ADR-0011 amendment), and the benchmark needs the labelled question set (P11).
2. No `ranx` metrics yet — Recall@k, MRR, nDCG belong with that set.
3. Stage 6 work: proposal approval, finding resolution, Change Impact.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the native wheels.

No known Stage 5 defects remain open.

### Next safe task
**Stage 6 (Days 18-20) — the differentiating milestone.** Approval for
consolidation proposals (writing revisions and `superseded_by` through the
existing `supersede()` path), resolution for findings, and the Change Impact
screen over a commit range. Both detection halves are already proven.

---

## 2026-11-09 — Stage 5: recall and evidence retrieval

### What changed
- **`retrieval/fts.py`** — keyword search with a safe MATCH builder.
- **`retrieval/embed.py`** — `fastembed` (ONNX, no torch), **opt-in** with a
  filesystem-only status check (ADR-0023).
- **`retrieval/vector.py`** — float32 BLOBs, cosine by one numpy matmul,
  incremental index, project-scoped, `clear()` for reindex.
- **`retrieval/hybrid.py`** — Reciprocal Rank Fusion plus small boosts; every
  result explains its rank (ADR-0024).
- **`retrieval/answer.py`** — evidence composition with three outcomes and
  labelled, cited items; turns persisted to `ask_turns` with a full trace.
- **`api/routers/ask.py`** — `POST /ask`, `GET /embeddings`,
  `POST /embeddings/build`. 17 endpoints total.
- **Project Intelligence screen** — asks, renders labelled evidence with
  citations and matched terms, shows unknowns, and offers the opt-in download
  with its size and destination stated.
- ADR-0023 and ADR-0024 added (31 ADRs).

### Verification performed
- **287 tests pass** (was 245). 42 new, with the semantic ones skipped when the
  model is not cached so the suite never reaches the network.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- **Live over HTTP**: 102 files → 319 memories → index 319 memories + 313
  chunks → three questions answered with citations, session reused across turns.
- 8 of 8 probe questions classify correctly on this repository.

### Five defects found by measuring first
1. **FTS5 crashed on 8 of 10 realistic questions** — `"what's the setup?"`,
   `sqlite-vec`, `C++`, `100%`, `""`, `OR`. Measured *before* writing the
   module, which is why the safe MATCH builder exists at all rather than being
   bolted on after a crash report. Now 0 of 13.
2. **Stopwords manufactured support.** "airspeed velocity of an unladen
   swallow" matched "an/is/of/the" and reported `evidence_found`.
3. **Exact substring matching abstained wrongly.** "secrets" missed ADR-0020a's
   "Secret refusal"; fixed with a prefix stem against the item's full text.
4. **One coincidental word passed as support** — the project contract contains "Do not
   **swallow** errors", so the nonsense question passed again. Support now
   needs `min(2, content_terms)` matches.
5. **The model cache sat under `data_dir`**, so relocating the database meant
   another 90 MB download. Found when tests pointed `data_dir` at a temp
   directory and the model silently vanished. Weights now live in the user
   cache.

### Known issues / blockers
1. **The honest cost of ADR-0006 is now visible and pinned by a test:** *"which
   database did we choose"* returns `weak_evidence`, because the ADR says
   "PostgreSQL" and "persistence" and never "database". A human would answer
   it; term overlap cannot. This is the clearest place an optional model
   adapter would earn its keep.
2. **ADR-0014's four-way benchmark is not done.** `fastembed` does not carry
   the potion models, so `potion-code-16M-v2` and `potion-retrieval-32M` need
   `model2vec` as a second runtime — an ADR-0011 amendment, to be decided
   deliberately. The benchmark also needs the labelled question set (P11).
2. No `ranx` metrics yet: Recall@k, MRR and nDCG belong with the labelled set.
3. Proposal approval and finding resolution remain Stage 6.
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
Either **the Stage 5 defect sweep** (the pattern that has found real bugs at
every stage), or **Stage 6 (Days 18-20)** — the differentiating milestone:
approval for consolidation proposals, resolution for findings, and the Change
Impact screen over a commit range. Stage 6's detection halves are already
proven by the P4/P5 spikes.

---

## 2026-11-08 — Stage 4 defect sweep

Probed Stage 4 adversarially before starting Stage 5, as with Stage 3.

### Probed and found sound
- **Scale.** 120 files scanned and analysed in well under a second; the
  detectors are not the bottleneck.
- **Importance refinement** is idempotent (migration 0003 holds).

### Bugs found and fixed (ADR-0021a)
1. **A filler-only title was never compared.** "Overview", "Commands" and
   "This is it" are entirely filler words, so the bucket signature was empty
   and 120 files sharing an `## Overview` heading gave `compared=0`. Fixing
   bucketing alone was insufficient — `title_score` used the same stripped
   tokens, so Jaccard returned 0.0 and correctly-bucketed pairs still scored
   zero. Bucketing and scoring now share one fallback.
2. **Unbounded pairwise work.** A 120-member bucket is 7140 pairs. Buckets
   above 5 members now compare against the highest-importance record instead
   of every pair: 24 actionable statements rather than 300. Buckets above 25
   are truncated and candidates capped at 200, both logged.
3. **Cross-granularity false positives.** A section in one file and a fenced
   block in another share a title and an overlapping body — 4 candidates where
   2 were real. Pairs now require matching `extraction_method`.
4. **Unbounded entity derivation.** A 400-dependency manifest produced 401
   entities and ~800 writes for one memory. Capped at 60, paths first.
5. **Dead code**: `entities.fan_in()`, defined and never called.

### Verification performed
- **245 tests pass** (was 236). 9 new sweep regressions.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- All five probe cases correct: 120 identical sections → 24 bounded
  candidates; cross-file section/commands → 2; planted duplicate → 1;
  same-title-different-body → 0; unrelated → 0.
- Dogfood: comparisons fell from **1851 to 168**, candidates from 2 to **1**,
  and the remaining one is genuine with citations provably preserved.

### Known issues / blockers
1. Proposal approval and finding resolution are still unimplemented, so the
   queue only grows. Stage 6, and the UI says so.
2. Fan-in adjusts nothing on this repository (each command appears once).
3. `SecretWarning` has no findings row (needs a new `findings.kind`).
4. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the tree-sitter wheels.

No known Stage 4 defects remain open.

### Next safe task
**Stage 5 (Days 14-17): recall and evidence retrieval.** FTS5 keyword search,
`fastembed` embeddings (ADR-0011), the four-way model benchmark (ADR-0014),
hybrid fusion, and the extractive composer that labels evidence, inference and
unknowns. `chunks`, both FTS tables and `embeddings` are wired and waiting.

---

## 2026-11-08 — Stage 4: core memory engine

### What changed
- **`ingest/entities.py`** — entity derivation and linking. `entities` and
  `memory_entities` were created in migration 0001 and never written to; they
  are now populated during a scan from data already extracted (source paths,
  manifest package names, the first bare word of a command, decision options).
- **`maintain/duplicates.py`** — duplicate candidates and consolidation
  proposals with a before/after preview (ADR-0021). Detection proposes;
  nothing merges.
- **`maintain/importance.py`** — fan-in refinement that explains itself in
  `importance_reason` (ADR-0022).
- **Migration 0003** — `memories.importance_base`, so refinement is idempotent.
- **`api/routers/maintenance.py`** — `POST /projects/{id}/analyze`,
  `GET /findings`, `GET /proposals`. Analysis is explicit rather than automatic
  on scan: it writes findings, and a scan's meaning ("what is in the
  repository") stays separate from analysis ("what looks wrong").
- **Frontend** — Memory Explorer now renders **validity**, **supersession**
  (with links in both directions) and the **decision payload**, all of which
  the API had been returning and nothing displayed. New Memory Intelligence
  Center with the review queue, severity, diff hunks and side-by-side
  consolidation previews.
- ADR-0021 and ADR-0022 added.

### Verification performed
- **236 tests pass** (was 217). 19 new in `test_stage4_memory_engine.py`.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- **Live over HTTP** on this repository: scan 95 files / 285 memories →
  analyze → 285 refs checked, 1 conflict, 2 duplicate candidates, 2 proposals,
  3 open findings. 29 decision memories, **27 with a parsed payload**. The
  proposal preview was asserted to preserve every citation from both inputs.

### Four measurements that set the thresholds
Each is a defect found by running against our own repository, not a guess.

1. **8 false duplicates out of 8** from title similarity alone: `function
   create` in two repository modules, `function get`, `function extract` —
   same identifier, different function. A candidate now also requires body
   overlap, and symbol memories are excluded entirely since they are keyed by
   (file, qualified name) and unique by construction.
2. **The obvious duplicate was invisible** when bucketing by shared entity
   alone: two root-level files have no shared `module`, so identical "Running
   the tests" sections in `README.md` and `CONTRIBUTING.md` were never
   compared. Title-signature bucketing was added.
3. **Every `## Setup` section duplicated its own fenced block.** Parent and
   child, not two claims — memories whose line ranges nest are now skipped.
4. **Importance adjusted 271 of 271 memories.** Every memory under `docs/`
   shares the `docs` module, so file and module fan-in ranks nothing. Those
   kinds were removed from the weight table.

Plus two bugs in my own Stage 4 code: entity derivation produced commands
literally named ```` ``` ```` and ```` ```bash ```` from section-derived
procedure memories (now only real command lists yield command entities), and
fan-in was applied to the current score rather than a base, so importance crept
upward on every analysis — caught by the idempotency test and fixed with
migration 0003.

### Known issues / blockers
1. **Proposal approval is not implemented.** The preview exists and says so in
   the UI; applying a merge is Stage 6, where it must write revisions and set
   `superseded_by` using the existing `supersede()` path.
2. Fan-in currently adjusts nothing on this repository because each command
   appears in a single memory. Honest, and the signal is exercised by a fixture
   instead. A larger repo will exercise it for real.
3. Findings have no resolve/dismiss endpoint yet, so the queue only grows.
   Stage 6, together with approval.
4. `SecretWarning` still has no findings row (needs a new `findings.kind`).
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open. No Windows
   verification of the tree-sitter wheels.

### Next safe task
**Stage 5 (Days 14-17): recall and evidence retrieval.** FTS5 keyword search,
`fastembed` embeddings (ADR-0011) with the four-way model benchmark (ADR-0014),
hybrid fusion, and the extractive answer composer that labels evidence,
inference and unknowns. The `embeddings` table and both FTS tables are wired
and waiting; `chunks` is populated for both prose and code.

---

## 2026-11-08 — Stage 3 defect sweep, before starting Stage 4

Probed the Stage 3 code adversarially rather than working from the known-issue
list, then fixed everything confirmed.

### Probed and found sound (no change needed)
- **Symlink directory loops** do not hang the walker: `Path.rglob` does not
  follow directory symlinks. A child-to-parent loop returned in 0.00s.
- **The cached tree-sitter parser is safe under threads** in practice: 6
  threads x 12 parses produced one consistent symbol count and no errors.
- **No ReDoS in the ADR regexes**: a 40x200-character alternatives block and a
  5000-word decision line both parsed in under 0.01s.

### Bugs found and fixed
1. **A real credential was stored, only warned about** (ADR-0020b). The
   two-tier policy discriminated on the *detector*, but what distinguishes
   `DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"` from `SECRET_SUSPECTED =
   "secret_suspected"` is the *value*. A keyword hit now refuses the file when
   the value is credential-shaped. Detector co-occurrence was tried first and
   measured insufficient: that password produces no entropy hit.
2. **Superseded and archived memories were served as current.**
   `MEMORY_MODEL.md` says they are excluded unless asked; they were in every
   listing. Now hidden by default, still reachable by id, by explicit status,
   or with `include_inactive`. The Memory Explorer gained "Current" /
   "All, including replaced" / "Superseded" options.
3. **Prose was compared as a command list.** `manual` procedure memories had
   their sentences split into pseudo-commands. Now gated on command shape.
4. **Reindentation inside a code fence was called cosmetic** — the limitation
   ADR-0019a shipped with a test documenting. Inside a fence, indentation is
   compared but trailing whitespace is not, so a Python reindent is semantic
   while saving a file is still cosmetic.

### Three bugs in my own fixes, caught by my own tests
- `password: 'Xk92Lm04Qp77Zr'` was missed because the key was split on `=`
  only, making the whole line the "key" so the value looked self-referential.
- `PASSWORD = "<your-password>"` was flagged: the template pattern required
  `<lowercase>` and the value contained a hyphen.
- `PASSWORD = os.environ["DB_PASSWORD"]` was flagged, because the quoted part
  is a *key name*. An indirection guard now covers `environ`, `getenv`,
  `process.env`, `config.get` and similar.

### One regression I caused and caught by dogfooding
The stricter heuristic refused `docs/DECISIONS.md`, dropping decision memories
from 31 to **8** — our own decision log, lost for containing the example
`password = "hunter2..."` inside a sentence. Fixed with a prose guard: a line
whose text outside the quoted literal runs to 8+ words is read as prose, not an
assignment. Any project that documents its security decisions would have hit
this.

### Verification performed
- **217 tests pass** (was 183). 32 new in `test_stage3_fixes.py`, plus the
  fence tests rewritten to assert the fix rather than the limitation.
- `ruff check` / `format --check` clean; frontend typechecks and builds.
- Dogfood: **91 files, 291 memories, 33 decisions**. Refusals are exactly the
  four files that genuinely contain credential-format literals (three test
  fixtures, the demo `.env`); our own docs and source that merely discuss
  secrets are imported with a warning.
- Drift on a clean tree: 0 high, 0 medium, 0 low across 260 source refs.

### Known issues / blockers
1. The value-shape heuristic is necessarily imperfect in both directions. Both
   are pinned by tests (13 detection, 12 non-detection), and the escape hatch
   is `# pragma: allowlist secret`, which detect-secrets honours in code files
   but not reliably in Markdown.
2. `SecretWarning` still has no review-queue entry; that needs a new
   `findings.kind` and a migration. Stage 6.
3. Task-name matching in conflict detection is still literal (`Setup` vs
   `Set up`). Deferred to Stage 6 against the P11 evaluation set, because
   widening it trades false negatives for false positives.
4. Four languages only, by design. No Windows verification of the tree-sitter
   wheels yet (risk R11); they load cleanly on Linux.
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
**Stage 4 (Days 10-13): core memory engine.** Dedup candidate generation,
importance refinement over the symbol graph, and the Memory Explorer work that
surfaces validity, supersession and the decision payload the API already
returns. No known Stage 3 defects remain open.

---

## 2026-11-08 — Stage 3 part 2: tree-sitter symbols, widened allowlist

Stage 3 is now complete.

### What changed
- **`ingest/extract/code_symbols.py`** + `queries/{python,typescript,tsx,
  javascript}/tags.scm` — tree-sitter symbol extraction (ADR-0012, ADR-0012a).
  One `architecture` memory per top-level definition, names qualified by their
  enclosing class, private helpers skipped, test files excluded.
- **Walker allowlist widened to source files**, derived from the same language
  table as the extractor, so the allowlist cannot drift ahead of what we can
  actually parse.
- Source files are **chunked by symbol**, so each chunk has a real line range
  and a name for Stage 5 retrieval.
- **Two-tier secret policy** (ADR-0020a): format detectors refuse, keyword and
  entropy detectors warn via a new `SecretWarning` on the scan result.
- Path deny-list narrowed to configuration filenames.
- **Refactor:** findings persistence moved to `db/repositories/findings.py`,
  with `Finding`/`FindingKind`/`Severity` as domain types. `ingest/` needs to
  raise findings and `ARCHITECTURE.md` forbids `ingest` depending on
  `maintain`, so the repository is the only correct home.
- ADR-0012a and ADR-0020a added (23 ADRs).

### Verification performed
- **183 tests pass** (was 146). 37 new: 23 code symbols, 14 secret policy.
- `ruff check` / `format --check` clean. Frontend typechecks and builds.
- Every shipped `tags.scm` is asserted to compile against its grammar, and
  `supported_languages()` is asserted to equal exactly the set with query files.
- Dogfood on this repository: **91 files, 285 memories, 320 chunks, 3.1s** —
  133 symbol memories, 24 ADR memories, 117 section memories.

### Four more bugs found by dogfooding
1. **`secrets.py` was refused by the path deny-list.** `secrets.*` matched our
   own module. A file named `secrets.py` is ordinary Python; the pattern is now
   limited to config extensions.
2. **`SECRET_SUSPECTED = "secret_suspected"` refused `domain/models.py`**, and
   "possible secret" refused `Dashboard.tsx`. The keyword detector fires on the
   *name*, not the value. Hence the two-tier policy — refusals on this repo
   went from 6 files to 3, all 3 correct.
3. **19 architecture memories from one test file.** Tests describe behaviour,
   not module shape; test paths are now excluded, with the matcher anchored so
   "latest" and "protest" are not caught.
4. **TypeScript class methods were invisible.** The query captured the class
   but had no `method_definition` pattern, so a class's whole surface was
   missing. Caught by a test asserting `method Renderer.render`.

### Process note
My edit helper printed "ok" before writing to disk, so when a later assertion
aborted the script, earlier edits that had reported success were silently
discarded — and I chased a `NameError` twice as a result. The helper now writes
after each edit, so "ok" means it is on disk.

### Known issues / blockers
1. **A real `password = "..."` with no recognisable format is now imported**
   with a warning rather than refused. That is the deliberate cost of ADR-0020a
   and the reason the warning exists.
2. `SecretWarning` reaches the scan result but has no review-queue entry; that
   needs a new `findings.kind` and therefore a migration. Stage 6.
3. Four languages only. Adding one is a query file plus a test — by design.
4. Symbol `content` is signature plus docstring, while the line range spans the
   whole definition. Intentional (drift should fire on any change inside the
   function) but it means `content` is not the full source.
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.
6. No Windows verification of the tree-sitter wheels yet (risk R11); it loads
   cleanly on Linux.

### Next safe task
**Stage 4 (Days 10-13): core memory engine.** Dedup candidate generation,
importance refinement using the symbol graph, and the Memory Explorer work that
surfaces validity, supersession and the decision payload the API already
returns. The Stage 4 conflict feasibility gate is already met.

---

## 2026-11-08 — Stage 3 part 1: secret scanning and ADR extraction

### What changed
- **`ingest/secrets.py`** — content-level secret refusal via `detect-secrets`
  (ADR-0013), wired into the pipeline before any capture is persisted. A file
  with a credential is refused whole and recorded as `secret_suspected`.
- **`ingest/extract/adr.py`** — `rule:adr`, handling three conventions:
  `adr-tools` / MADR one-decision-per-file, a combined log, and a plain
  `## Decision:` heading. Produces `status`, `chosen`, `alternatives`,
  `decided_on`, and sets `valid_from` from the decision date (ADR-0017).
- `extract/markdown.py` — heading classification now matches on word
  boundaries with optional plurals, not substrings.
- ADR-0020 added (21 ADRs).

### Verification performed
- **146 tests pass** (was 113). 19 new: 10 secret scanning, 9 ADR extraction.
- `ruff check` / `format --check` clean. Frontend typechecks and builds.
- **End-to-end payoff:** two opposing `adr-tools` files scanned from disk now
  produce a decision conflict — `0001-use-sqlite.md` chose SQLite,
  `0004-use-postgresql.md` chose PostgreSQL, both valid, one finding holding
  both claims with citations. Before this the signal could only fire on
  hand-written memories.
- Secret refusal asserted at the database level: after scanning a file with a
  pasted GitHub token, `source_captures.text` and `memories.content` contain
  zero occurrences of it.

### Four bugs found by dogfooding Kernote on its own repository
Scanning our own repo was worth more than any synthetic fixture.

1. **`scan_line` would have refused every file.** The obvious detect-secrets
   entry point bypasses the library's filters and reports high-entropy hits on
   ordinary prose, on `pip install -r requirements.txt` and on
   `fastapi==0.115.6`. `scan_file` applies the filter chain and returned zero
   hits on a benign documentation fixture while catching a GitHub token and an
   AWS key with correct line numbers.
2. **Numbered headings are not ADRs.** `## 1. Shape` and
   `## 2. Repository structure` in `ARCHITECTURE.md` were extracted as
   decisions — **44 false records out of 66**. The bare `N. Title` form is now
   only trusted inside a path that already looks like a decision document.
3. **One decision per file is the document, not a section.** The first
   implementation treated `## Status` / `## Decision` as candidate ADRs and so
   extracted *nothing* from `adr-tools` and MADR files, because no sub-section
   carries both a decision heading and a long enough body.
4. **`"adr"` was matched as a substring**, so "Quadratic scoring" and
   "Squadron layout" classified as decisions. Fixing it with a bare `\b`
   boundary then broke plurals — "Conventions" stopped matching "convention",
   which substring matching had handled by accident. Both are now covered by
   tests.

Also: the ADR extractor now owns its document, suppressing the generic section
extractor for it. Without that, every `## Decision` sub-heading produced a
second payload-less "Decision" memory duplicating the real record.

### Known issues / blockers
1. **`chosen` parses from 2 of 22 of our own ADRs.** Our house style states the
   decision as a paragraph ("Ship a Vite frontend plus…"), which is not
   reliably parseable. The extractor declines rather than guessing, because a
   fabricated option produces a fabricated conflict. `adr-tools` and MADR
   conventions parse correctly. This limits the decision-conflict signal to
   repos using a structured ADR format — worth stating plainly rather than
   claiming broad coverage.
2. A file containing one credential is refused **whole**, so a README with an
   example token loses its real content. `# pragma: allowlist secret` is the
   escape hatch in code files; it is unreliable in Markdown, where
   detect-secrets does not recognise `#` as a comment.
3. If a previously clean file gains a credential, its existing memories stay
   and their pinned hash goes stale, so drift flags them. Coherent, but the
   review UI should eventually say why the source vanished.
4. **Stage 3 is not finished:** tree-sitter symbol extraction (ADR-0012) and
   the widened source-file allowlist are still to do. That is the larger and
   riskier half — a native wheel (risk R11) plus per-language `tags.scm`.
5. Proposal items P3, P6-P13 unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
**Stage 3 part 2:** `tree-sitter` + `tree-sitter-language-pack` with
per-language `tags.scm` seeded from Aider's queries (ADR-0012, attributed),
and the allowlist widened to source files. Gate: slice S2 on a repository with
real code, plus a Windows note for risk R11.

---

## 2026-11-08 — Problem 2 fixed: cosmetic changes are no longer "stale"

### The problem
Drift severity had two bands, so **any** whitespace change inside a citation
was high severity: trailing spaces added on editor save, a rewrapped
paragraph, an inserted blank line, a reindented block. The first run of a docs
formatter over a real repository would have flagged every citation in every
touched line as high — risk R10 arriving by a second route, since the overlap
test exists precisely to stop "the file changed" meaning "everything is stale".

### What changed (ADR-0019a)
A third band. Each hunk is now classified by comparing its removed and added
lines with all whitespace collapsed, which also neutralises reflow. Then per
citation: **high** if an overlapping hunk's text really differs, **medium** if
overlapping but only formatting moved, **low** if the change missed the cited
lines. Evidence gains `cosmetic_only` and `substantive_hunks`.

A cosmetic change still raises a finding rather than silently re-pinning the
hash, because re-pinning is a write to canonical memory and the project contract
requires approval for that. The medium explanation says what accepting it does.

### Verification performed
Measured on the real `samples/demo-repo`:

| Scenario | Before | After |
|---|---|---|
| Whole-file reformat (trailing whitespace everywhere) | 7 high | **0 high / 7 medium** |
| Genuine one-line word change | 1 high / 6 low | **1 high / 6 low** (unchanged) |
| Both together in one file | — | **1 high / 1 medium / 5 low** |

The third row is the important one: each citation is judged on its own lines,
so a reflowed section and a rewritten section in the same file get different
verdicts.

- **113 tests pass** (was 102). 11 new: a 7-case parametrised
  cosmetic/semantic matrix, the formatter scenario, an over-correction guard
  asserting a real edit is still high, the mixed-file case, and one test that
  documents a limitation rather than a desire.
- `ruff check` and `ruff format --check` clean.

### Known issues / blockers
1. **Indentation inside code fences is treated as cosmetic.** It is significant
   in Python, YAML and Makefiles. A test asserts the current behaviour and says
   in its failure message that it documents behaviour, not intent. Fixing it
   needs fence-language awareness — Stage 6, measured against the P11 set.
2. **Problem 3** (prose split into pseudo-commands for `manual` memories) and
   **Problem 4** (literal task-name matching) remain open, both deferred to
   Stage 6 because widening them trades false negatives for false positives and
   needs the labelled evaluation set.
3. Proposal items P3, P6-P13 remain unapplied. ADR-0009 and Q1/Q2/Q4 open.
4. Neither detector is wired to an endpoint or the UI. Stage 6.

### Next safe task
**Stage 3 proper (Days 6-9).** `detect-secrets` content scanning to replace the
path deny-list (ADR-0013); `rule:adr` extraction, which is what will finally
feed the decision-conflict signal with real data instead of only manual
memories; tree-sitter symbols with per-language `tags.scm` (ADR-0012); the
allowlist widened to source files. Gate: slice S2, plus the Stage 3 drift gate
which is already met.

---

## 2026-11-08 — Spike review: fixed a latent wrong-answer bug in validity comparison

Review of the P4/P5 spikes, by probing them adversarially rather than reading
them. Four weaknesses found; the user chose to fix the first.

### The bug
`_windows_overlap` and the ADR-0017 ordering validator compared `valid_from` /
`valid_until` as **raw strings**. `"2026-1-1"` sorts after `"2026-01-01"`
because `"1" > "0"`, so an unpadded date gave the wrong overlap verdict with no
error. `"01/01/2026"` was accepted and compared as nonsense. Nothing validated
the format, and the fields are writable through the public API.

This is the worst failure shape available to this product: not a crash, but a
confident and wrong conflict finding, in the feature ADR-0015 made the wedge.

### What changed (ADR-0017a)
Three layers, in `domain/models.py` and `maintain/conflicts.py`:
1. A field validator parses with `datetime.fromisoformat` and rejects the rest,
   naming the field, showing an example and quoting the bad input.
2. Accepted values are normalised to one canonical form, so four spellings of
   the same instant cannot coexist on disk.
3. Ordering and overlap compare timezone-aware `datetime` objects. An
   unparseable **stored** bound is treated as open-ended and logged, erring
   towards reporting a possible conflict rather than hiding one.

### Verification performed
- **102 tests pass** (was 73). 29 new in `tests/unit/test_temporal.py`:
  rejection matrix (9 bad formats × 2 fields), normalisation table (5 forms),
  ordering across mixed formats, overlap (6 cases incl. touching windows),
  currency.
- Confirmed at the boundary: all of `2026-1-1`, `01/01/2026`, `2026-13-01`,
  `2026-02-30`, `yesterday`, `""` are now rejected before storage.
- `ruff check` and `ruff format --check` clean.
- Drift re-verified on the real demo repo after the change: still HIGH=1,
  LOW=6 on a one-line edit, so the fix did not disturb the overlap test.

### Known issues / blockers
1. **Problem 2 (not fixed, user deferred):** whitespace-only edits and prose
   reflow produce hunks, so a formatter run across the docs would flag every
   citation in the touched lines as high severity. Proposed fix was a `medium`
   band for "changed, but only whitespace within the cited lines", which also
   puts the currently-unused `medium` severity to work.
2. **Problem 3 (deferred to Stage 6):** `manual` is in `_COMMAND_METHODS`, so a
   hand-written procedure memory has its prose split into pseudo-commands.
   Harmless today because no UI creates them.
3. **Problem 4 (deferred to Stage 6, needs the eval set):** task normalisation
   is literal — `Setup`/`Set up`, `Testing`/`Tests`, `Build`/`Building` all
   miss. Widening it trades false negatives for false positives and should be
   tuned against the P11 labelled set, not by guesswork.
4. Stored temporal values changed shape (`"2026-03-11"` →
   `"2026-03-11T00:00:00+00:00"`). One round-trip test updated deliberately.
5. Proposal items P3, P6-P13 remain unapplied. ADR-0009 and Q1/Q2/Q4 open.

### Next safe task
Either Problem 2 (small, prevents a false-positive wave on the first formatter
run) or **Stage 3 proper**: `detect-secrets` content scanning, `rule:adr`
extraction to feed the decision-conflict signal, tree-sitter symbols, widened
allowlist.

---

## 2026-11-08 — Drift and conflict feasibility spikes (proposals P4, P5)

Detection only, test level, no UI. Full implementation stays in Stage 6. The
point was to prove the two mechanisms before the milestone that carries the
product wedge depends on them.

### What changed
- `maintain/findings.py` — the single review queue (ADR-0007), with a
  `dedupe_key` so re-running a detector cannot pile up duplicate findings.
- `maintain/drift.py` — hash change, then diff, then **hunk/line-range overlap**.
  High severity only when changed regions overlap the cited lines.
- `maintain/conflicts.py` — two deterministic signals: *same task, different
  commands* and *same question, different answer with overlapping validity*.
  The second is only possible because ADR-0017 made validity reachable.
- `unidiff` promoted from commented-out to installed in `requirements.txt`.
- ADR-0019 added (20 ADRs). `ROADMAP.md` Stage 3 and Stage 4 now carry the
  feasibility gates; a note records that both are already met.

### Verification performed
- **73 tests pass** (was 53). 20 new: 10 drift, 10 conflict.
- `ruff check` clean, `ruff format --check` clean (44 files).
- Demonstrated on the real `samples/demo-repo`: editing README line 10 produced
  **exactly 1 high finding** (the memory citing lines 6-11) and **6 low** for
  the other memories in that same file. A naive file-changed detector would
  have raised 7 false alarms. This is the single most important number in the
  spike.
- Conflict, on the same repo with a CONTRIBUTING.md added:
  `README.md:26-29 -> ['pytest -q', 'ruff check .']` versus
  `CONTRIBUTING.md:7-9 -> ['tox -e py312']`, one finding holding both claims,
  neither record touched.

### Two findings that changed the design
1. **A file conflicted with itself.** `## Testing` yields both a section memory
   and a commands memory, and "commands" is a filler word, so both normalised
   to the same task. My guard compared full citations, which differ by line
   range. Fixed two ways: only extractors that produce an actual command list
   participate (`rule:markdown_commands`, `manual`), and comparison is now per
   **file**, not per citation. This is exactly what a spike is for.
2. **`git diff` is the wrong source for hunks** (ADR-0019). It yields nothing
   for untracked files, nothing outside a repository, and nothing for
   working-tree edits against a mid-session hash — which is the normal state of
   a project someone is actively editing, precisely when freshness matters.
   Diffs now come from the stored L1 capture via `difflib` + `unidiff`, with
   `n=0` context so neighbouring unchanged lines do not create false overlaps.
   A test asserts drift works in a directory with no Git at all.

### Known issues / blockers
1. Conflict title normalisation is literal: "Setup" and "How to set up" do not
   match. Acceptable for heading-derived titles, but Stage 6 should widen it,
   and that will trade false negatives for false positives — needs the
   evaluation set to tune against, not guesswork.
2. Neither detector is wired to an endpoint or the UI. Deliberate: Stage 6.
3. Severity is binary (overlap or not). Medium is unused for `stale_risk`.
4. `_decisions` only fires when a `decision` payload exists, and no extractor
   produces one yet — only manual memories do. `rule:adr` in Stage 3 will feed it.
5. Proposal items P3, P6-P13 remain unapplied.
6. ADR-0009 (Windows) and open questions Q1, Q2, Q4 still unanswered.

### Next safe task
**Stage 3 proper.** `detect-secrets` content scanning to replace the path
deny-list (ADR-0013), `rule:adr` extraction to feed the decision-conflict
signal, tree-sitter symbols with per-language `tags.scm` (ADR-0012), and the
allowlist widened to source files. Gate: slice S2, plus the Stage 3 drift gate
which is already met.

---

## 2026-11-08 — Backend hardening: write integrity, supersession, temporal validity

Scope chosen by the user: strengthen the backend and eliminate bugs before
adding features. UI work deferred to Stage 8.

### Bugs found by auditing Stage 2's own code, each reproduced before fixing

1. **Orphaned memories.** The connection runs in autocommit
   (`isolation_level=None`) and no application code opened a transaction, so
   `memories.create()` committed the memory row, then its revision, then its
   source refs as three independent writes. Simulating a failure on the second
   left a **committed memory with no lineage and no provenance** — MEMORY_MODEL
   invariant 3 violated at the storage layer, below where validation can help.
2. **Duplicate current source files.** `ix_source_files_current` was a plain
   partial index, so two rows for one path could both be `is_current=1`. The
   rule lived only in Python, and the database accepted the violation when
   tested directly.
3. **Non-atomic scans.** Hundreds of autocommitted writes meant a mid-scan
   failure left captures committed without their chunks and memories — worse
   than failing outright, because the next scan treats the capture as known and
   never retries the extraction.

### What changed
- `db/connection.py`: `transaction()` context manager — `BEGIN IMMEDIATE`,
  **re-entrant** (a nested call joins the outer unit of work and rolls back with
  it), guarded by one process-wide `RLock` (ADR-0018).
- `repositories/memories.py`: `create`, `update`, `archive` are now single units
  of work; new `supersede()`.
- `repositories/sources.py`: `record_file` demote-then-insert is atomic, which
  it must be now that the index is UNIQUE.
- `ingest/pipeline.py`: rewritten so **one file is one transaction**; extraction
  split into `_ingest_one_file`.
- **Migration 0002** (forward-only): makes `ix_source_files_current` UNIQUE,
  repairing any existing violation first by demoting all but the most recently
  seen row per path; adds indexes for `superseded_by` and `(project_id,
  valid_until)`.
- **Proposal P1/P2 implemented** (ADR-0017): `valid_from`, `valid_until`,
  `superseded_by`, derived `supersedes` and the `decision` payload are now
  reachable through the domain model, the repositories and the API. They were
  columns no code touched.
- New endpoint `POST /api/v1/memories/{id}/supersede`, and `Memory.is_current`.
- Domain invariants now enforced, not documented: backwards validity window
  rejected, self-supersession rejected, `superseded_by` + `active` rejected,
  decision payload only on `type='decision'`.
- ADR-0017 and ADR-0018 added (19 ADRs).

### Verification performed
- Both bugs **reproduced first**, then re-tested after the fix: the orphan case
  now leaves 0 rows, and the duplicate-current insert is refused by the database
  with `UNIQUE constraint failed`.
- **53 tests pass** (was 37). 16 new in `tests/integration/test_write_integrity.py`
  covering atomicity, re-entrancy, uniqueness, supersession, temporal validity
  and a 4-thread × 8-write concurrency check asserting every memory ends with
  exactly one revision and one source ref.
- `ruff check` clean, `ruff format --check` clean, `tsc --noEmit` clean, frontend
  builds.
- Live end-to-end on the demo repo at schema v2: scan 4 files / 11 memories,
  re-scan 0/0, supersede closes the old window and the old record stays
  fetchable with 2 revisions and a derived inverse edge.

### Process note
One edit silently no-op'd because I used `replace` without an assertion — the
anchor had changed when ruff removed a then-unused `import json`. It surfaced as
a `NameError` in nine tests. Every edit in this session's scripts now asserts
exactly one match before writing.

### Known issues / blockers
1. **Writes now serialise.** Correct for a local single-user tool, but any
   future long-running write must be chunked rather than hold the lock.
2. `list_for_project` still returns superseded records by default;
   `MEMORY_MODEL.md` says they should be excluded unless asked. Deferred to
   Stage 4 with the richer explorer, since it changes UI behaviour.
3. The frontend does not yet surface validity, supersession or the decision
   payload — the API returns them, nothing renders them. Stage 4.
4. Proposal items **P3–P13 remain unapplied** and unreviewed.
5. ADR-0009 (Windows) and open questions Q1, Q2, Q4 still unanswered.

### Next safe task
Either (a) apply proposal **P4/P5** — the drift and conflict feasibility spikes
in Stages 3 and 4, which are now cheap because provenance and validity are both
reachable; or (b) begin **Stage 3** ingestion proper: `detect-secrets` content
scanning, `unidiff`, tree-sitter symbols, widened allowlist. P4 first is the
better order: it de-risks Stage 6 before more surface area is added.

---

## 2026-11-08 — Stage 2 fix: `honcho start` was broken on a clean PATH

### What changed
- `Procfile` web process now prepends `$HOME/.local/bin` itself, so Node is
  found without the caller exporting PATH.
- `frontend/vite.config.ts`: `strictPort: true`.

### Why
Pre-flighting the exact command the README tells you to run found two faults
that separate-process testing had hidden:

1. **`backend/.venv/bin/honcho start` failed** with `/bin/sh: 1: npm: not
   found`. Stage 2 verification had started uvicorn and npm as separate
   commands with PATH already exported, so the documented single command was
   never actually exercised. Reproduced with a sanitised PATH, then fixed.
2. **Vite was silently sliding to the next free port** (it reported 5175 while
   something else held 5173), which would make the documented URL wrong and
   point the API proxy at the wrong place. `strictPort` now fails loudly.

While checking, two **orphaned Vite processes from earlier test runs** (pids
10953, 12208, up 25 minutes) were found squatting 5173/5174. They made the
first fixed-Procfile check ambiguous, because curl to 5173 was being answered
by a stale server rather than the one just started. Both were terminated and
the check re-run against free ports.

### Verification performed
Re-run with a sanitised PATH, no stale listeners and an empty database:
Vite bound to 5173 (not a fallback port), `/` served HTTP 200 with
`<title>Kernote</title>`, `/health` ok at schema 1, the `/api` proxy returned
`[]` then completed register → scan (4 files, 4 captures, 11 memories) →
detail with citation `README.md:6-11` → re-scan creating 0 and 0. Ports were
released on shutdown.

Also re-run after the change: **37 tests passed**, ruff clean, frontend
typecheck and build clean.

### Lesson worth keeping
Verifying the components separately is not verifying the command in the
README. Pre-flight the documented entry point itself, on a PATH that does not
already have your fixes in it.

---

## 2026-11-08 — Stage 2 complete: application foundation, slice S1 proven

### What changed
- **Node 20.20.2 LTS installed** to `~/.local/opt/node` (tarball,
  checksum-verified against `SHASUMS256.txt`) with symlinks in `~/.local/bin`.
  No root needed: `sudo` requires a password here and apt only offered Node 18.
- **Backend** (`backend/`): venv, staged `requirements*.txt`, `pyproject.toml`
  with ruff + pytest config.
  - `db/migrations/0001_init.sql` — **generated** from the schema block in
    `ARCHITECTURE.md` §4, then extended with the 6 FTS5 synchronisation
    triggers and the `schema_meta` seed the document did not need.
  - `db/connection.py` — WAL, foreign keys ON, busy_timeout, forward-only
    idempotent migration runner.
  - `domain/models.py`, `domain/scoring.py` — pure; the MEMORY_MODEL rules are
    enforced in code, not merely documented.
  - `db/repositories/{projects,sources,memories}.py` — the only SQL writers.
  - `ingest/{walker,capture,gitmeta,normalize,pipeline}.py`,
    `ingest/extract/{markdown,manifests}.py`.
  - `api/` with 10 endpoints + `/health`; `main.py` binds 127.0.0.1 only.
- **Frontend** (`frontend/`): Vite + React + TS, Tailwind v4, react-router,
  TanStack Query, hand-written typed client, 7 routed screens. Dashboard and
  Memory Explorer are functional; the other five are explicit placeholders
  naming their stage and gate.
- **Orchestration**: `justfile`, `Procfile` (honcho), `scripts/dev.sh` fallback.
- **`samples/demo-repo/`** plus `NOTE.md`, and the README setup section.

### Verification performed
All of the following were run, and these are the actual results:

- **`ruff check backend`** → All checks passed. **`ruff format --check`** →
  38 files already formatted.
- **`pytest backend/tests`** → **37 passed**, 1 warning (a starlette/anyio
  deprecation, not our code).
- **`tsc --noEmit`** → clean. **`npm run build`** → built, 235 kB JS / 11.7 kB CSS.
- **Live run with both servers up**, exercised over real HTTP *through the Vite
  proxy*: register → scan (3 files, 3 captures, 10 memories, 1 refused) →
  list → detail → re-scan → counts. `.env` refused as `secret_suspected`.
- **S1 gate proven**: a second app instance against the same database file sees
  the same project, all 10 memories, their provenance and their revisions.

Invariants now covered by named tests: #1 idempotent re-scan (0 new captures,
0 new memories), #3 no provenance unless manual, #4 FTS index rebuildable,
#5 archived records stay fetchable, #7 secrets and gitignored files refused.
Plus: the walker does not modify the project tree, CRLF files stay readable,
and `0001_init.sql` cannot drift from `ARCHITECTURE.md` without a test failing.

**Three real bugs found and fixed during the stage, worth remembering:**
1. `executescript()` implicitly COMMITs, so an outer `BEGIN` was silently
   discarded and a failed migration could have half-applied. The transaction
   now lives *inside* the script.
2. `check_same_thread` was documented but not set, so every request from
   FastAPI's threadpool raised. Set, with the reasoning recorded in the code.
3. Tailwind v4.0.0 build failed because `@tailwindcss/vite@4.0.0` bundles
   `tailwindcss@4.3.5` internally — a version mismatch, not a CSS error as the
   message suggested. Both pinned to 4.3.5.

### Known issues / blockers
1. **Node is not on your shell `PATH`.** Adding it to `~/.bashrc` was blocked
   as unauthorised persistence, which is fair, so I kept it project-scoped: the
   `justfile` and `scripts/dev.sh` prepend `~/.local/bin` themselves. To use
   `node`/`npm` directly in your own terminal, add this yourself:
   `export PATH="$HOME/.local/bin:$PATH"` in `~/.bashrc`.
2. `samples/demo-repo/.env` is **intentionally not committed** (root
   `.gitignore` refuses it). `NOTE.md` explains how to recreate it by hand;
   tests use a generated hostile fixture instead of a committed fake secret.
3. The frontend client is hand-written. It is replaced by
   `openapi-typescript` in Stage 4, once the endpoint surface stops moving.
4. shadcn/ui is **not** installed yet despite the project contract naming it. Stage 2
   needed a shell and a table, not a component library; it lands in Stage 4
   when the Memory Explorer gets rich. Flagging rather than quietly skipping.
5. No Windows verification yet (ADR-0009 still `proposed`).
6. ADR-0009 and open questions Q1, Q2, Q4 remain unanswered.
7. Stage 6 still carries the product wedge and sits second-to-last.

### Next safe task
**Stage 3 (Days 6–9): repository ingestion.** In order: add `detect-secrets`,
`unidiff`, `tree-sitter` + `tree-sitter-language-pack` to
`requirements.txt`; replace the walker's path-based deny-list with
`detect-secrets` content scanning (ADR-0013); add `ingest/extract/adr.py` and
`ingest/extract/code_symbols.py` with per-language `tags.scm` (ADR-0012);
widen the allowlist to source files; record git blob hashes for tracked files
in `memory_source_refs`. Gate: slice S2 — the hostile fixture scans with every
refusal explained, and a repeat scan still creates nothing.

---

## 2026-11-07 — Day 2 (cont.): contract aligned with ADR-0015

### What changed
- The project contract scope item 3: "Ask Your Project" → "Cited evidence retrieval".
- The project contract scope item 6: now marked the differentiating feature, ref ADR-0015.
- Nothing else in the project contract touched. 2 insertions, 2 deletions.

### Verification performed
- Both edits applied by assertion-guarded script (exactly one match required
  each); `git diff` confirms 2 lines changed and no collateral edits.
- Full cross-check of the remaining the project contract clauses against all 17 ADRs.
  Compliant: the MiniLM baseline (ADR-0011 runs the same model via ONNX;
  ADR-0014 keeps MiniLM as the baseline unless our own numbers justify a swap),
  the vector-index clause (ADR-0003a validated and deferred on evidence — the
  clause working as intended), PyTorch confinement (ADR-0004), conditional MCP
  (scope 7 vs the F9 cut order — the kickoff guide itself made MCP conditional),
  and untested-language claims (ADR-0012 is structurally compliant).
- **One phrase left deliberately unedited:** scope item 8's "polished
  desktop-quality application screens" against ADR-0001, which ships a localhost
  app rather than a packaged desktop binary. Read as a claim about UI craft, not
  distribution, and already disclosed in README "Known limitations". Raise it if
  you meant a packaged binary — that would reopen ADR-0001 and cost Stage 8–9 time.

**Not verified:** still no application code, so no tests, lint, type or build
checks were run, and none are claimed.

### Known issues / blockers
1. **Node.js still not installed** — the only remaining Stage 2 blocker.
2. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 unanswered.
3. Stage 6 carries the product wedge and sits second-to-last.

### Next safe task
**Stage 2 (Days 3–5), slice S1**, on a feature branch: install Node 20 LTS →
re-run the toolchain probe → `backend/` skeleton with migration 0001 applied →
`frontend/` Vite shell routing the seven screens → `justfile` + `Procfile` →
then S1 end to end: register a project, scan README and config, save one memory
with provenance, see it in Memory Explorer, restart, prove it persisted.

---

## 2026-11-07 — Day 2 (cont.): planning set committed

### What changed
- `git config user.name` set to "Pavan" at **repository scope only** (it was
  unset globally and a commit needs it). Change it with
  `git config user.name "<your name>"`; there is no remote, so history can still
  be amended freely.
- Added **ADR-0016**: the roadmap, structure and architecture are ours; prior art
  is reference only. 17 ADRs total.
- First commit of the project: the whole planning foundation, 12 files.

### Verification performed
- Secret scan before staging: no private keys, no `ghp_`/`sk-`/`AKIA`/`xox`/JWT
  patterns, no assigned credentials, and the account email appears in no tracked
  file (git config only). `.gitignore` confirmed to exclude both
  `*:Zone.Identifier` artifacts.
- Schema re-executed against sqlite3 immediately before committing: 29 tables,
  FTS5 present.
- Reviewed the file list: 12 files, all documentation plus the source kickoff PDF.
  No code, no generated artifacts, no database files.

**Not verified:** there is still no application code, so no tests, lint, type or
build checks were run, and none are claimed.

### Known issues / blockers
1. **Node.js still not installed** — the Stage 2 blocker.
2. The project contract scope items 3 and 6 still use pre-ADR-0015 wording. Left for you
   to approve, since the project contract is the contract that overrides these docs.
3. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 unanswered.
4. Committed on `master`, the default branch, because this is a fresh repo with
   no prior commits and no remote. Stage 2 onward should use feature branches.
5. Stage 6 carries the product wedge and sits second-to-last; front-loading a
   conflict-detection spike remains an open option.

### Next safe task
**Stage 2 (Days 3–5), slice S1.** In order: install Node 20 LTS → re-run the
toolchain probe → scaffold `backend/` with `schema.sql` and migration 0001
applied → `frontend/` Vite shell routing the seven screens → `justfile` and
`Procfile` → then S1 end to end: register a project, scan README and config, save
one memory with provenance, see it in Memory Explorer, restart, prove it
persisted.

---

## 2026-11-07 — Day 2 (cont.): ADR-0015 applied

### What changed
- **ADR-0015 accepted** and applied across the planning set.
- `PRODUCT_SPEC.md`: new §2 positioning ("reviewable project memory", explicitly
  not an agent memory server); §4 success criteria reordered with drift and
  conflict first and a conflict criterion added; F3 renamed **Cited Evidence
  Retrieval** and marked `Must (supporting)`; **F8 `Should` → `Must`**; feature
  detail reordered to lead with F5 and F8; §7 gains a **Conflict** acceptance
  row, retrieval now measured as citation correctness + abstention, and the four
  MemoryAgentBench evaluation axes; §9 lists the new names to re-screen.
- `ROADMAP.md`: Days 18–20 relabelled the differentiating milestone with
  conflict as `Must`; Days 14–17 renamed off "Project Brain"; S5 split into
  drift and conflict halves; **F8 removed from the scope-cut list** and added to
  "never cut", with F9 and F3 breadth cut first instead.
- `README.md`: positioning headline, conflict feature, and three honest
  limitations including the extractive-answers caveat.
- `ARCHITECTURE.md` §9: conflict-detection test fixtures and the evaluation axes.
- `COMPETITIVE_LANDSCAPE.md` §6 marked accepted.

### Verification performed
- Every edit applied by an assertion-guarded script: each replacement required
  exactly one match or the run aborted. One assertion did fire (the acceptance
  table wording differed from my draft), was inspected and corrected rather than
  forced.
- Consistency sweep via `grep` for "Ask Your Project", "Project Brain" and
  `F8 ... Should`. All surviving hits are in historical records (ADR-0015, the
  landscape doc, the Day 2 handoff entry) where the old wording is the point.
- No code exists, so no tests were run and none are claimed.

### Known issues / blockers
1. **the project contract line 17 still says "Ask Your Project using hybrid retrieval and
   source citations."** The project contract is the authoritative contract that overrides
   every document I write, so I did **not** edit it. The kickoff guide says to
   update it when scope intentionally changes, which just happened. Recommended
   minimal edit, for you to make or approve:
   - scope item 3 → `Cited evidence retrieval using hybrid retrieval and source citations.`
   - scope item 6 → `Knowledge conflict review (differentiating feature; see ADR-0015).`
   Nothing else in the project contract conflicts with ADR-0015 — conflict review was
   already scope item 6.
2. **Node.js still not installed** — blocks Days 3–5.
3. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 still unanswered.
4. Days 18–20 is now the highest-risk milestone by design, since the wedge lives
   there and it is late in the sprint. Consider pulling a conflict-detection
   spike earlier if Days 10–13 run ahead.
5. The embedding ONNX artifact is still not vendored or hash-pinned.
6. Still nothing committed; the working tree is untracked.

### Next safe task
1. Approve the two the project contract line edits above (or make them yourself).
2. Install Node 20 LTS; re-run the toolchain probe.
3. Commit the whole planning set as one reviewed increment.
4. Read `projectmem`'s event schema and MCP tool surface before finalizing ours
   (ADR-0010).
5. Then the Day 3–5 scaffold and the S1 vertical slice.

---

## 2026-11-07 — Day 2: competitive scan

### What changed
- Created `docs/COMPETITIVE_LANDSCAPE.md` — the first competitive analysis for
  this project. The kickoff guide's §1 only screened the *name*, never asked
  whether the product exists.
- Appended **ADR-0015 (proposed)** to `docs/DECISIONS.md`: reposition on
  reviewable memory, promote F8 to `Must`, demote F3 to supporting, make drift
  granularity the technical claim, adopt MemoryAgentBench evaluation axes.
- Updated the README documentation index.
- **No application code written. No priorities changed in `PRODUCT_SPEC.md`** —
  ADR-0015 is proposed, not accepted, because it alters agreed scope.

### Verification performed
- 7 web searches across four competitor lanes, plus a full read of
  arXiv:2606.12329v1 (PROJECTMEM) including its §2 related-work survey.
- Every claim in the landscape document is attributed in its §8; vendor claims
  are marked as vendor sources.
- No code, so no tests were run and none are claimed.

**Material finding:** the thesis is already occupied. `projectmem` is an
open-source, local-first, typed, provenance-keeping, MCP-served project memory
layer (Jun 2026). `Codified Context` is plain-text, no-vector-DB, MCP-served,
with a drift detector. Neither was known to the kickoff guide.

**Countervailing finding:** `MemoryAgentBench` evaluates retention, update,
retrieval and conflict resolution, and no architecture masters all four. The two
unsolved ones — update and conflict — are our F5 (`Must`) and F8 (`Should`).
That priority ordering is backwards.

### Known issues / blockers
1. **Node.js still not installed** — blocks the Day 3–5 frontend milestone.
2. **ADR-0015 needs a decision.** It changes agreed scope, so Days 3+ should not
   start until it is accepted, rejected or amended.
3. ADR-0009 (Windows target) and open questions Q1, Q2, Q4 still unanswered.
4. Days 18–20 becomes the highest-risk milestone if F8 is promoted to `Must`.
5. The MiniLM/potion ONNX artifact is still not vendored or hash-pinned.
6. Still nothing committed; the working tree is untracked.

### Next safe task
1. Decide on ADR-0015, then apply its edits to `PRODUCT_SPEC.md` §4/§5/§7 and
   `ROADMAP.md` if accepted.
2. Read `projectmem`'s event schema and MCP tool surface (ADR-0010: borrow the
   solved parts) before finalizing our MCP surface.
3. Install Node 20 LTS; re-run the toolchain probe.
4. Commit the planning set as one reviewed increment.
5. Only then the Day 3–5 scaffold and the S1 vertical slice.

---

## 2026-11-06 — Day 1: planning foundation

### What changed
- `git init` run in the project root (the repo did not exist before this task).
- Created `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/MEMORY_MODEL.md`,
  `docs/ROADMAP.md`, `docs/DECISIONS.md`, `docs/DEV_HANDOFF.md`.
- Created `README.md` and `.gitignore`.
- **No application code written.** Per the kickoff guide §10, the blueprint is
  presented for approval before any scaffold or implementation.

### Verification performed
- `git --version` → 2.43.0 · `python3 --version` → 3.12.3 — both fine.
- Toolchain probe for `node`, `npm`, `pnpm` — **all missing** (see blockers).
- `python3 -c "import venv"` → ok. `pip3` present at `/usr/bin/pip3`, but the
  system environment is PEP-668 externally-managed, so a venv is mandatory.
- **The `ARCHITECTURE.md` schema was executed, not just written.** The SQL block
  was extracted and run through `sqlite3` 3.45.1 with `foreign_keys=ON`:
  `executescript` succeeded and produced 29 tables, confirming every constraint,
  composite foreign key, partial index and both FTS5 virtual tables are valid and
  that FTS5 is compiled into the system SQLite. Re-run with:
  `python3 -c "import re,sqlite3,pathlib; sqlite3.connect(':memory:').executescript('\n'.join(re.findall(r'\`\`\`sql\n(.*?)\`\`\`', pathlib.Path('docs/ARCHITECTURE.md').read_text(), re.S)))"`
- `git check-ignore` confirms the two `:Zone.Identifier` files are ignored.
- Documents reviewed against the project contract for contradictions; none found. Where
  this planning set adds a position the project contract did not take (extraction
  strategy, embedding runtime, vector search), it is recorded as an ADR rather
  than assumed silently.

**Not verified:** nothing executable exists yet, so no tests were run. No test
suite, lint or type-check has been claimed as passing because none exists.

### Known issues / blockers
1. **Node.js is not installed** — blocks the Day 3–5 frontend milestone. Need
   Node 20 LTS (`nvm install 20` or the distro package) before Nov 8.
2. **ADR-0009 is `proposed`, not accepted** — needs your call on whether native
   Windows is a Day 25 release target or best-effort (open question Q3). Affects
   whether Days 3–5 absorb a Windows environment spike.
3. **Open questions Q1, Q2, Q4** in `PRODUCT_SPEC.md` §10 have working defaults
   recorded but are unconfirmed.
4. a `:Zone.Identifier` stream file and `Kernote_Project_Kickoff_Guide.pdf:Zone.Identifier`
   are WSL artifacts from the Windows copy. Harmless; now gitignored rather than
   deleted. Remove them whenever you like.
5. The MiniLM ONNX artifact (ADR-0004) is not yet vendored or hash-pinned. Needed
   before the Day 14–17 retrieval milestone.
6. Nothing is committed yet — the working tree is untracked. The project contract step 9
   says not to commit unless asked.

### Next safe task
**Day 2 — close the blueprint, then scaffold.** In order:

1. Get approval on the six documents and a decision on ADR-0009 plus Q1–Q4.
2. Install Node 20 LTS and re-run the toolchain probe.
3. Make the first commit of the planning set.
4. Then, and only then, the Day 3–5 scaffold as its own task: `backend/`
   skeleton with `schema.sql` + migration 0001 applied, `frontend/` Vite shell
   with routing for the seven screens, `scripts/dev.sh`, and the S1 vertical
   slice (register project → scan README/config → one memory with provenance →
   visible in Memory Explorer → survives restart).

Do not start step 4 before steps 1–3. The slice in step 4 is the gate for the
whole ingestion milestone and it is worth having the schema reviewed first.
