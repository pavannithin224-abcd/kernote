-- 0005_feedback_resolved.sql — let feedback record a 'resolved' verdict.
--
-- Forward-only. Earlier migrations are never edited.
--
-- `findings.status` has always allowed ('open','accepted','rejected',
-- 'resolved'), but `feedback.verdict` allowed only
-- ('useful','not_useful','accepted','rejected','edited'). So resolving a
-- finding as 'resolved' passed every application check and then failed on a
-- CHECK constraint at the last statement -- the review flow's own happy path,
-- caught by a Stage 6 test.
--
-- SQLite cannot alter a CHECK constraint, so the table is rebuilt. It is small
-- (one row per human decision) and the copy is inside the migration's
-- transaction, so this is atomic.

CREATE TABLE feedback_new (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  target_kind TEXT NOT NULL CHECK (target_kind IN
                ('memory','finding','proposal','answer','retrieval')),
  target_id   TEXT NOT NULL,
  verdict     TEXT NOT NULL CHECK (verdict IN
                ('useful','not_useful','accepted','rejected','resolved','edited')),
  note        TEXT,
  created_at  TEXT NOT NULL
);

INSERT INTO feedback_new(id,project_id,target_kind,target_id,verdict,note,created_at)
  SELECT id,project_id,target_kind,target_id,verdict,note,created_at FROM feedback;

DROP TABLE feedback;

ALTER TABLE feedback_new RENAME TO feedback;

CREATE INDEX IF NOT EXISTS ix_feedback_target ON feedback(target_kind, target_id);
