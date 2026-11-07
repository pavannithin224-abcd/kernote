-- 0001_init.sql — Kernote initial schema
--
-- GENERATED from the schema block in docs/ARCHITECTURE.md §4, then extended
-- with the FTS5 synchronisation triggers and the schema_meta seed row that a
-- design document does not need but a running database does.
--
-- tests/unit/test_schema_matches_doc.py asserts the generated portion still
-- matches the document, so the two cannot drift silently.
-- Forward-only: never edit an applied migration; add 0002_*.sql instead.

-- ===== BEGIN GENERATED FROM docs/ARCHITECTURE.md =====
-- ─── L1 RAW ────────────────────────────────────────────────────────────────
CREATE TABLE projects (
  id            TEXT PRIMARY KEY,          -- uuid4
  name          TEXT NOT NULL,
  root_path     TEXT NOT NULL UNIQUE,
  is_git_repo   INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL,
  settings_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE scan_runs (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  status        TEXT NOT NULL CHECK (status IN
                  ('running','completed','failed','cancelled')),
  git_commit    TEXT,                      -- HEAD at scan time, if any
  files_seen    INTEGER NOT NULL DEFAULT 0,
  files_new     INTEGER NOT NULL DEFAULT 0,
  files_skipped INTEGER NOT NULL DEFAULT 0,
  error         TEXT
);

-- Content-addressed. The same bytes are stored once per project, forever.
CREATE TABLE source_captures (
  content_hash  TEXT NOT NULL,             -- sha256 of raw bytes
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  text          TEXT,                      -- NULL for non-decodable
  byte_size     INTEGER NOT NULL,
  encoding      TEXT,
  captured_at   TEXT NOT NULL,
  PRIMARY KEY (project_id, content_hash)
);

-- Path ↔ capture over time. A path seen again unchanged updates last_seen only.
CREATE TABLE source_files (
  id             TEXT PRIMARY KEY,
  project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  rel_path       TEXT NOT NULL,
  content_hash   TEXT NOT NULL,
  git_blob_hash  TEXT,
  git_commit     TEXT,
  language       TEXT,
  first_seen_run TEXT NOT NULL REFERENCES scan_runs(id),
  last_seen_run  TEXT NOT NULL REFERENCES scan_runs(id),
  is_current     INTEGER NOT NULL DEFAULT 1,
  FOREIGN KEY (project_id, content_hash)
    REFERENCES source_captures(project_id, content_hash)
);
CREATE UNIQUE INDEX ix_source_files_path_hash
  ON source_files(project_id, rel_path, content_hash);
CREATE INDEX ix_source_files_current
  ON source_files(project_id, rel_path) WHERE is_current = 1;

CREATE TABLE skipped_files (          -- transparency: why nothing was imported
  id          TEXT PRIMARY KEY,
  scan_run_id TEXT NOT NULL REFERENCES scan_runs(id) ON DELETE CASCADE,
  rel_path    TEXT NOT NULL,
  reason      TEXT NOT NULL CHECK (reason IN
                ('gitignored','excluded','binary','too_large',
                 'secret_suspected','unreadable','not_allowlisted'))
);

-- ─── L2 NORMALIZED ─────────────────────────────────────────────────────────
CREATE TABLE chunks (
  id             TEXT PRIMARY KEY,
  project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_file_id TEXT NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
  ordinal        INTEGER NOT NULL,
  line_start     INTEGER NOT NULL,
  line_end       INTEGER NOT NULL,
  heading_path   TEXT,                     -- "Setup > Local development"
  text           TEXT NOT NULL,
  token_estimate INTEGER NOT NULL
);
CREATE INDEX ix_chunks_file ON chunks(source_file_id, ordinal);

-- ─── L3 CANONICAL (source of truth) ────────────────────────────────────────
CREATE TABLE memories (
  id                 TEXT PRIMARY KEY,
  project_id         TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  type               TEXT NOT NULL CHECK (type IN
                       ('project_fact','architecture','decision','procedure',
                        'convention','gotcha','current_state')),
  title              TEXT NOT NULL,
  content            TEXT NOT NULL,
  summary            TEXT,
  status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN
                       ('active','needs_review','superseded','archived')),
  claim_kind         TEXT NOT NULL CHECK (claim_kind IN
                       ('source_fact','interpretation')),
  importance         REAL NOT NULL,
  importance_reason  TEXT NOT NULL,        -- a score with no reason is a bug
  confidence         REAL NOT NULL,
  confidence_reason  TEXT NOT NULL,
  extraction_method  TEXT NOT NULL,        -- manual | rule:<n> | model:<id>@<v>
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  last_verified_at   TEXT,
  valid_from         TEXT,
  valid_until        TEXT,
  superseded_by      TEXT REFERENCES memories(id),
  current_revision   TEXT NOT NULL,
  decision_json      TEXT                  -- alternatives/status for `decision`
);
CREATE INDEX ix_memories_project_status ON memories(project_id, status, type);
CREATE INDEX ix_memories_importance ON memories(project_id, importance DESC);

CREATE TABLE memory_revisions (
  id            TEXT PRIMARY KEY,
  memory_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  parent_id     TEXT REFERENCES memory_revisions(id),
  title         TEXT NOT NULL,
  content       TEXT NOT NULL,
  summary       TEXT,
  snapshot_json TEXT NOT NULL,             -- full record at this revision
  change_reason TEXT NOT NULL,
  actor         TEXT NOT NULL CHECK (actor IN ('user','rule','model')),
  created_at    TEXT NOT NULL
);
CREATE INDEX ix_revisions_memory ON memory_revisions(memory_id, created_at);

CREATE TABLE memory_source_refs (
  id             TEXT PRIMARY KEY,
  memory_id      TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  source_file_id TEXT REFERENCES source_files(id),
  rel_path       TEXT,
  line_start     INTEGER,
  line_end       INTEGER,
  content_hash   TEXT,                     -- pinned fingerprint for drift
  git_blob_hash  TEXT,
  git_commit     TEXT,
  url            TEXT,
  user_note      TEXT
);
CREATE INDEX ix_refs_memory ON memory_source_refs(memory_id);
CREATE INDEX ix_refs_hash ON memory_source_refs(content_hash);

CREATE TABLE entities (
  id         TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN
               ('file','module','component','dependency','command','decision')),
  name       TEXT NOT NULL,
  UNIQUE (project_id, kind, name)
);

CREATE TABLE memory_entities (
  memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  role      TEXT,
  PRIMARY KEY (memory_id, entity_id)
);

CREATE TABLE memory_links (
  src_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  dst_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN
               ('relates_to','duplicate_of','contradicts','refines',
                'supersedes','depends_on')),
  reason     TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (src_id, dst_id, kind)
);

-- One review queue for every kind of maintenance signal.
CREATE TABLE findings (
  id           TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind         TEXT NOT NULL CHECK (kind IN
                 ('stale_risk','conflict','duplicate','broken_link',
                  'missing_doc')),
  severity     TEXT NOT NULL CHECK (severity IN ('low','medium','high')),
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN
                 ('open','accepted','rejected','resolved')),
  memory_id    TEXT REFERENCES memories(id) ON DELETE CASCADE,
  other_id     TEXT REFERENCES memories(id) ON DELETE CASCADE,
  detector     TEXT NOT NULL,              -- rule:<n> | model:<id>@<v>
  evidence_json TEXT NOT NULL,             -- hashes, diff hunks, scores
  explanation  TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  resolved_at  TEXT,
  resolution_note TEXT
);
CREATE INDEX ix_findings_queue
  ON findings(project_id, status, severity, created_at);

CREATE TABLE consolidation_proposals (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  finding_id    TEXT REFERENCES findings(id) ON DELETE SET NULL,
  input_ids_json TEXT NOT NULL,            -- memories being merged
  preview_json  TEXT NOT NULL,             -- before/after for the UI
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
                  ('pending','approved','rejected','superseded')),
  created_at    TEXT NOT NULL,
  decided_at    TEXT,
  result_memory_id TEXT REFERENCES memories(id)
);

CREATE TABLE feedback (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  target_kind TEXT NOT NULL CHECK (target_kind IN
                ('memory','finding','proposal','answer','retrieval')),
  target_id   TEXT NOT NULL,
  verdict     TEXT NOT NULL CHECK (verdict IN
                ('useful','not_useful','accepted','rejected','edited')),
  note        TEXT,
  created_at  TEXT NOT NULL
);

-- Session state: purgeable, never promoted without an explicit user action.
CREATE TABLE ask_sessions (
  id         TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
);
CREATE TABLE ask_turns (
  id             TEXT PRIMARY KEY,
  session_id     TEXT NOT NULL REFERENCES ask_sessions(id) ON DELETE CASCADE,
  question       TEXT NOT NULL,
  answer         TEXT NOT NULL,
  citations_json TEXT NOT NULL,
  trace_json     TEXT NOT NULL,            -- exact evidence + scores shown
  created_at     TEXT NOT NULL
);

-- ─── L4 DERIVED (disposable, rebuildable) ──────────────────────────────────
CREATE VIRTUAL TABLE memories_fts USING fts5(
  title, content, summary,
  content='memories', content_rowid='rowid', tokenize='porter unicode61'
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  text, heading_path,
  content='chunks', content_rowid='rowid', tokenize='porter unicode61'
);

CREATE TABLE embeddings (
  target_kind TEXT NOT NULL CHECK (target_kind IN ('memory','chunk')),
  target_id   TEXT NOT NULL,
  model_id    TEXT NOT NULL,
  dim         INTEGER NOT NULL,
  vector      BLOB NOT NULL,               -- float32, L2-normalized
  built_at    TEXT NOT NULL,
  PRIMARY KEY (target_kind, target_id, model_id)
);

CREATE TABLE schema_meta (
  key TEXT PRIMARY KEY, value TEXT NOT NULL
);
-- ===== END GENERATED FROM docs/ARCHITECTURE.md =====

-- FTS5 external-content tables do not populate themselves. Without these
-- triggers memories_fts stays empty and keyword search silently returns
-- nothing, which is the kind of quiet failure that looks like bad retrieval.
CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, title, content, summary)
  VALUES (new.rowid, new.title, new.content, new.summary);
END;
CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, summary)
  VALUES ('delete', old.rowid, old.title, old.content, old.summary);
END;
CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, summary)
  VALUES ('delete', old.rowid, old.title, old.content, old.summary);
  INSERT INTO memories_fts(rowid, title, content, summary)
  VALUES (new.rowid, new.title, new.content, new.summary);
END;

CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text, heading_path)
  VALUES (new.rowid, new.text, new.heading_path);
END;
CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text, heading_path)
  VALUES ('delete', old.rowid, old.text, old.heading_path);
END;
CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text, heading_path)
  VALUES ('delete', old.rowid, old.text, old.heading_path);
  INSERT INTO chunks_fts(rowid, text, heading_path)
  VALUES (new.rowid, new.text, new.heading_path);
END;

INSERT INTO schema_meta(key, value) VALUES ('schema_version', '1');
