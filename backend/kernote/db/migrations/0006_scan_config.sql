-- 0006_scan_config.sql — per-project scan configuration.
--
-- Forward-only. Earlier migrations are never edited.
--
-- This is the local adjustment layer that sits next to a repository's own
-- `.kernote.toml`, the way `.git/info/exclude` sits beside a shared
-- `.gitignore`. It lives here rather than being written into the user's
-- repository, because `CLAUDE.md` forbids rewriting their files and scanning
-- stays read-only.
--
-- No BEGIN/COMMIT: the migration runner wraps every script in one, because
-- `executescript()` implicitly commits an outer transaction.

CREATE TABLE project_scan_config (
  project_id    TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  include_json  TEXT NOT NULL DEFAULT '[]',
  exclude_json  TEXT NOT NULL DEFAULT '[]',
  updated_at    TEXT NOT NULL
);
