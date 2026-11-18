# Desktop product audit — 2026-11-14

Written against the code as it stands, not against the plan. Every claim
below was checked in the repository or measured on the running app; where I
could not verify something, it says so.

**The headline: your section 2 (Memory Intelligence) is substantially built
and is the strongest part of the product. Sections 1 and 4 have real holes.
Section 3 is done well on new screens and not applied to old ones.**

---

## 1. What already works

Not "scaffolded" — working, tested, and in most cases argued for in an ADR.

### Memory intelligence (your section 2) — mostly done
| Requirement | State |
|---|---|
| Source provenance | **Done.** `memory_source_refs` pins `rel_path`, line range, `content_hash`, `git_blob_hash`, `git_commit`. Manual captures carry a `user_note` instead, and are deliberately distinguishable. |
| Timestamps | **Done.** `created_at`, `updated_at`, `last_verified_at`, plus `valid_from`/`valid_until` for temporal validity. |
| Outdated detection | **Done.** `maintain/drift.py` compares pinned `content_hash` against disk, then diffs and tests hunk overlap against the cited lines. Cosmetic reflows are classified as such rather than flagged. |
| Contradictions | **Done.** `maintain/conflicts.py`; one real conflict is live in your vault. |
| Duplicates | **Done.** `maintain/duplicates.py` with consolidation proposals carrying before/after previews. |
| Historical versions | **Done.** `memory_revisions` stores a *full snapshot* per revision with `parent_id` lineage. This is why undo was possible at all. |
| Superseded knowledge | **Done.** `superseded_by`, status `superseded`, never deleted. |
| Approval required | **Done**, and now reversible both ways (ADR-0040, ADR-0041). |
| Suggested updates with evidence | **Partial.** Consolidation proposes concrete merged text; drift explains *why* a claim may be stale but proposes no new wording. |

### Local-first (your section 4) — strong, with one hole
SQLite + FTS5, embeddings opt-in behind a flag and a 90 MB download, no
outbound calls by default, CORS limited to localhost, `.gitignore` respected
plus a configurable include/exclude list, and secrets actively refused during
scanning via `detect-secrets` (`ingest/secrets.py`).

### Visual identity (your section 3)
Palette, glow tokens, Memory Pulse, the React Flow knowledge graph, the
startup reveal and the honest boot status lines are all built and signed off.

### The discipline worth keeping
The codebase repeatedly refuses to show a number it cannot justify: freshness
is three states because "100%" would be a lie on an unchecked project
(ADR-0037); the graph reports what it omitted (ADR-0039); the boot screen
prints three status lines instead of five because only three are checkable
(ADR-0038). **That is the product's actual differentiator and it is already
real.** 475 tests, 59 ADRs.

---

## 2. Gaps, by your six areas

### 1 · Desktop experience — the weakest area
- ~~**No command palette.**~~ **Closed 2026-11-14** — ⌘K, every entry real
  (ADR-0044).
- ~~**No keyboard shortcuts**, and a decorative `⌘1` hint nothing handled.~~
  **Closed 2026-11-14.** The hint is gone, ⌘K works, and
  `test_shortcuts_are_real.py` fails if a hint is ever drawn without a
  handler — verified by replanting the original bug.
- **No tray, no background indexing.** Scanning and analysis are manual
  `POST`s that block until done. There is no job runner.
- **Quick capture is in-app only.** A global OS hotkey is not reachable from
  pywebview and needs platform-specific work.
- **No window state persistence** — size and position are not remembered.

### 2 · Memory intelligence — two real gaps
- ~~**`memory_links` is empty in practice.**~~ **Closed 2026-11-14**
  (ADR-0045): suggestions can be confirmed into durable rows or dismissed so
  they stop recurring.
- **No project dependency concept at all.** Entities include `dependency`,
  but nothing models relationships *between projects*.

### 3 · Visual identity — consistency, not design
~~The neon pass never reached the six older screens.~~ **Closed
2026-11-14**, and almost entirely in shared components: `Panel` adopted the
terminal register and a new `ScreenHeader` replaced six hand-rolled
`text-lg font-semibold` headings. The 1,677 lines of screen code were
**not restructured** — which was the point, and the brief's instruction.

### 4 · Local-first — one significant hole
- ~~**There is no backup, restore or export.**~~ **Closed 2026-11-14**
  (ADR-0043): snapshot via the online backup API, validated restore with an
  automatic pre-restore snapshot, and a JSON export. Verified on the real
  6.3 MB vault.
- ~~**No privacy or data controls in the UI.**~~ **Closed 2026-11-14.**
  Settings now shows the database path and size, offline status, the
  embedding state, and backup / download / export / restore. **Still no
  purge** — deleting a vault deserves its own design, and inventing a button
  for it would be the mistake this audit is about.

### 5 · Product quality
- ~~**Accessibility is thin.**~~ **Largely closed 2026-11-14**: 18 → 38
  aria/role attributes, eight unlabelled controls named, a visible
  `:focus-visible` ring (there was none), a skip link past the ~20-stop
  sidebar, headings on the two screens that lacked them, and errors
  announced via `role="alert"` in the shared component. Guarded by
  `test_accessibility_basics.py`. **Not done:** the neon/palette pass on
  those same screens, and no audit with a real screen reader.
- Loading/empty/error states are good on the new screens and unaudited on the
  old ones.
- Startup measured: `import kernote.main` **0.85 s, 77 MB peak**. Fine.

---

## 3. Risks

### Security
1. **The API has no authentication.** It binds to `127.0.0.1`, so it is not
   exposed to the network — but *any local process or any page in your
   browser* can read and modify the vault. For a tool whose selling point is
   that your knowledge never leaves the machine, "any local process" is a
   meaningful boundary. A loopback token would close it.
2. ~~**CORS still allows `http://localhost:5173`** even when serving the
   built UI.~~ **Closed 2026-11-14**: the middleware is registered only when
   an origin is configured, and the single-process launchers set
   `KERNOTE_CORS_ORIGINS=[]`. Keyed on configuration, not on "is there a
   build?" — `just dev` runs with a `dist/` on disk, so guessing from that
   would have broken the dev loop.
3. The SPA catch-all was checked for traversal and is contained — verified
   live against three encodings.

### Performance
1. **`/analyze` recomputes every drift ref on every call** (587 refs here).
   Linear in vault size, with no incremental mode.
2. **`/graph` rebuilds from SQL per request** — 611 candidate edges computed
   each time, no cache.
3. **`LedgerSummary` issues 2 queries per project** via `useQueries`.
4. ~~**No `Cache-Control` on hashed assets.**~~ **Closed 2026-11-14**:
   `assets/*` is `immutable, max-age=31536000`; the shell is `no-cache`, so
   it can never name assets that no longer exist.

### Project hygiene
**48 uncommitted files and three live migrations.** This is the largest risk
on the list: the working tree and your database now depend on each other, and
none of today's work is recoverable from git.

---

## 4. Recommendation: what is MVP, what is later

### Essential (in order)
| # | Work | Why now | Touches |
|---|---|---|---|
| 1 | **Commit, then tag** | Nothing else is safe until today's work exists in history | — |
| 2 | ~~**Backup / restore / export**~~ **done 2026-11-14** (ADR-0043) | The local-first promise is incomplete without it; cheap because the vault is one file | `api/routers/admin.py`, `db/backup.py`, `test_backup_restore.py` — 15 tests |
| 3 | ~~**Remove the fake `⌘1`, add a real command palette**~~ **done 2026-11-14** (ADR-0044) | Deletes shipped decoration and is the biggest native-feel win | `components/CommandPalette.tsx`, `lib/useCommandPalette.ts`, `App.tsx`, `test_shortcuts_are_real.py` |
| 4 | ~~**Data & privacy panel**~~ **done 2026-11-14** | Surfaces what is already true: path, size, offline status, embedding state, backup/restore/export | `screens/Settings.tsx`, `lib/api.ts` |
| 5 | ~~**Accessibility + neon pass over the six old screens**~~ **both done 2026-11-14** | Consistency is your section 3 and 5; the gap is measurable | a11y: eight controls labelled, focus ring, skip link, headings, `test_accessibility_basics.py`. Neon: `Panel` and a new `ScreenHeader` in `ui.tsx` — the six screens inherited the register without being restructured. |
| 6 | ~~**`Cache-Control` + drop dev CORS when serving built UI**~~ **done 2026-11-14** | Two-line fixes already identified | `main.py`, the three launchers, 5 tests |

### Later (genuinely larger)
- ~~**Background indexing**~~ **done 2026-11-14** (ADR-0046): a one-worker
  queue, `POST /scan/background` and `/analyze/background`, `GET /jobs`.
  **No cancellation and no progress percentage**, both stated. The **tray**
  is still outstanding and needs the desktop shell.
- ~~**Durable relationships**~~ **done 2026-11-14** (ADR-0045, migration
  0010): confirm, dismiss and withdraw, with `origin` distinguishing a
  judgement from a merge's consequence. ~~No bulk flow.~~ **Ranked triage
  added 2026-11-15** (ADR-0047): suggestions ordered by summed specificity,
  with batch confirm/dismiss on an explicit selection — and deliberately no
  "confirm all".
- **Project dependencies**: new concept, new schema.
- **Global OS hotkey**: platform-specific, outside pywebview.
- **Packaging and signing**: the 314 MB virtualenv is the obstacle.
- **Incremental analyze**: only when a vault is large enough to hurt.

### Explicitly do not do
Rewrite the working screens for style alone. `MemoryExplorer`,
`ProjectIntelligence` and `ChangeImpact` work; they need an accessibility and
palette pass, not a redesign.

---

## 5. Note on the brief

Two items you listed are **already done** and should be struck rather than
re-planned: provenance/timestamps, and approval-gated changes with history.
One item — "no fake metrics or decorative functionality pretending to be
real" — is already violated by exactly one thing I can find, the `⌘1` hint,
which is why it is item 3 above rather than a footnote.
