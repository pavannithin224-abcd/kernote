-- 0008_feedback_undone.sql — let a reversal be recorded as a decision.
--
-- Forward-only. Earlier migrations are never edited.
--
-- Approving a consolidation can now be undone. The undo is itself a human
-- decision and belongs in `feedback` alongside the approval it reverses --
-- MEMORY_MODEL stage 9 is explicit feedback only, and later tuning of the
-- duplicate thresholds rests on it. An approval that was later undone is a
-- *much* stronger signal than one that was never made, and recording the undo
-- as 'rejected' would erase that distinction by making the two look identical.
--
-- The original 'accepted' row is kept. Deleting it would make the history read
-- as though the approval never happened, which is exactly the silent rewriting
-- The project contract forbids.
--
-- SQLite cannot alter a CHECK constraint, so the table is rebuilt -- the same
-- approach as 0005, and for the same reason. It is small (one row per human
-- decision) and the copy is inside this migration's transaction.

CREATE TABLE feedback_v3 (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  target_kind TEXT NOT NULL CHECK (target_kind IN
                ('memory','finding','proposal','answer','retrieval')),
  target_id   TEXT NOT NULL,
  verdict     TEXT NOT NULL CHECK (verdict IN
                ('useful','not_useful','accepted','rejected','resolved',
                 'edited','undone')),
  note        TEXT,
  created_at  TEXT NOT NULL
);

INSERT INTO feedback_v3(id,project_id,target_kind,target_id,verdict,note,created_at)
  SELECT id,project_id,target_kind,target_id,verdict,note,created_at FROM feedback;

DROP TABLE feedback;

ALTER TABLE feedback_v3 RENAME TO feedback;

CREATE INDEX IF NOT EXISTS ix_feedback_target ON feedback(target_kind, target_id);
