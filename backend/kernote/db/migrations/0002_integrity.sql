-- 0002_integrity.sql — constraints the initial schema described but did not enforce.
--
-- Forward-only. 0001 is never edited.
--
-- Why: 0001 created ix_source_files_current as a plain partial INDEX, so two
-- rows for the same path could both carry is_current=1. The application tried
-- to maintain that rule in Python, which is not the same as the database
-- refusing to break it. A reproduction is in
-- tests/integration/test_write_integrity.py.

-- Repair any existing violation before adding the constraint: keep the row
-- most recently seen for each path, demote the rest. Nothing is deleted.
UPDATE source_files
SET is_current = 0
WHERE is_current = 1
  AND id NOT IN (
    SELECT id FROM (
      SELECT id,
             ROW_NUMBER() OVER (
               PARTITION BY project_id, rel_path
               ORDER BY last_seen_run DESC, rowid DESC
             ) AS rn
      FROM source_files
      WHERE is_current = 1
    )
    WHERE rn = 1
  );

DROP INDEX IF EXISTS ix_source_files_current;
CREATE UNIQUE INDEX ix_source_files_current
  ON source_files(project_id, rel_path) WHERE is_current = 1;

-- Supersession and temporal validity are queried per project once memory
-- lifecycle management is wired (ADR-0017); without these every such lookup is
-- a full scan of memories.
CREATE INDEX IF NOT EXISTS ix_memories_superseded_by
  ON memories(superseded_by) WHERE superseded_by IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_memories_validity
  ON memories(project_id, valid_until) WHERE valid_until IS NOT NULL;

-- A revision must belong to a memory that exists. 0001 left current_revision
-- undeclared, so this at least indexes the reverse lookup used by history.
CREATE INDEX IF NOT EXISTS ix_memories_current_revision
  ON memories(current_revision);
