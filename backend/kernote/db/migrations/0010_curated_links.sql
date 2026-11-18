-- 0010_curated_links.sql — let a relationship be confirmed or dismissed.
--
-- Forward-only. Earlier migrations are never edited.
--
-- `memory_links` has existed since 0001 but is written only when a merge
-- supersedes a record, so in practice it is empty: the knowledge graph
-- derives its edges from entity co-occurrence *at read time* (ADR-0039).
-- That makes the graph a view over a heuristic rather than over anything a
-- human has agreed with. There is nowhere to record "yes, these two really
-- are related", and nowhere to record "no, they are not" either -- so a
-- wrong suggestion comes back every single time the page is opened.
--
-- Two additions, one for each answer:
--
--   origin           on memory_links: how the row got there. A link written
--                    by a merge is a mechanical consequence; a link a person
--                    confirmed is a judgement. Collapsing them would lose
--                    which claims a human actually stands behind.
--
--   link_rejections  the negative answer, which has nowhere else to live.
--                    Without it "dismiss" can only mean "hide until reload".

ALTER TABLE memory_links ADD COLUMN origin TEXT;

-- Everything already in the table got there through a consolidation.
UPDATE memory_links SET origin = 'merge' WHERE origin IS NULL;

CREATE TABLE link_rejections (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  -- Stored with the lower id first, so a pair is one row whichever way
  -- round the suggestion happened to be generated.
  src_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  dst_id     TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  note       TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (src_id, dst_id)
);

CREATE INDEX ix_link_rejections_project ON link_rejections(project_id);
