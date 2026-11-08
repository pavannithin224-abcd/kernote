-- 0003_importance_base.sql — keep the pre-refinement importance score.
--
-- Forward-only. 0001 and 0002 are never edited.
--
-- Why: importance refinement adds a fan-in bonus to the base score. Applying
-- it to the *current* score made the function non-idempotent -- a second run
-- added the bonus again, so importance crept upward every analysis. Recovering
-- the base by parsing the bonus back out of `importance_reason` would make a
-- numeric score depend on string formatting, so the base is stored.
--
-- Backfilled from the current value: before this migration no refinement could
-- have been applied to a database that did not already have the column.

ALTER TABLE memories ADD COLUMN importance_base REAL;

UPDATE memories SET importance_base = importance WHERE importance_base IS NULL;
