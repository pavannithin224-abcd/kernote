# Runbook: Deploying

Deploys are from `main` only, through GitHub Actions, triggered by a tag.

```bash
git tag -s v1.4.0 -m "release 1.4.0"
git push origin v1.4.0
```

The pipeline runs migrations before swapping traffic. A migration that cannot
run against the old code must therefore be split into two releases: add the
column in one, start writing to it in the next.

## Rolling back

Re-tag the previous commit. Rollback does **not** reverse migrations; if the
release contained a destructive migration, restore from the pre-deploy
snapshot instead. The snapshot is taken automatically and retained for 7 days.
