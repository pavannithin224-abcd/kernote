-- 0004_embedding_freshness.sql — keep derived vectors consistent with L3.
--
-- Forward-only. Earlier migrations are never edited.
--
-- Two defects this fixes, both reproduced before the change:
--
-- 1. Editing a memory's content left its vector untouched, so semantic search
--    kept matching the OLD text indefinitely. `source_hash` records what was
--    actually embedded, so a changed body is re-embedded. `updated_at` was the
--    obvious alternative and is wrong: importance refinement touches
--    `updated_at` without changing a single word, which would re-embed the
--    whole project after every analysis.
--
-- 2. `embeddings` has a polymorphic target, so it cannot carry a foreign key,
--    and deleting a project left its vectors behind forever. Triggers do the
--    cleanup a foreign key cannot.

ALTER TABLE embeddings ADD COLUMN source_hash TEXT;

-- Existing vectors have no recorded source, so they are treated as stale and
-- re-embedded once. Cheaper than guessing they are current.
UPDATE embeddings SET source_hash = NULL WHERE source_hash IS NOT NULL;

CREATE TRIGGER embeddings_cleanup_memory AFTER DELETE ON memories BEGIN
  DELETE FROM embeddings
   WHERE target_kind = 'memory' AND target_id = old.id;
END;

CREATE TRIGGER embeddings_cleanup_chunk AFTER DELETE ON chunks BEGIN
  DELETE FROM embeddings
   WHERE target_kind = 'chunk' AND target_id = old.id;
END;

CREATE INDEX IF NOT EXISTS ix_embeddings_target
  ON embeddings(target_kind, target_id);
