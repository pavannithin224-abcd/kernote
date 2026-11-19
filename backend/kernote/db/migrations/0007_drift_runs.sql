-- 0007_drift_runs.sql — record that a freshness check actually happened.
--
-- Forward-only. Earlier migrations are never edited.
--
-- The dashboard wants a freshness figure. Computing one from findings alone
-- gives the wrong answer in the most common case: a project that has never
-- been analyzed has no stale_risk findings, so "memories without a stale
-- finding" reads 100% fresh. That is an invented statistic -- it reports an
-- absence of evidence as evidence of freshness, which the project contract forbids
-- ("Freshness checks should use deterministic file hashes/diffs as triggers",
-- "say evidence was not found when it was not found").
--
-- Drift detection was until now a pure function of the database and the disk:
-- it wrote findings but left no trace that it ran. This table is that trace,
-- so freshness has three honest states -- verified, flagged, and never
-- checked -- instead of two and a lie.

CREATE TABLE drift_runs (
  id           TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  ran_at       TEXT NOT NULL,
  refs_checked INTEGER NOT NULL DEFAULT 0,
  -- HEAD at check time, when the project is a git repo. Two runs at the same
  -- commit over an unchanged tree must agree; this makes that checkable.
  git_commit   TEXT
);

CREATE INDEX ix_drift_runs_latest ON drift_runs(project_id, ran_at DESC);
