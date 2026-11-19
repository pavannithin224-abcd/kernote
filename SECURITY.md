# Security

Kernote is a single-user, local-first tool. It listens on `127.0.0.1` only and
has no accounts, so the question that matters is what a *web page you happen to
have open* could do to it. That is the threat model, and it is tested.

## What it defends against

| Threat | Defence | Test |
|---|---|---|
| **DNS rebinding.** A site re-points its name at `127.0.0.1` so the browser treats the API as same-origin and a script reads your vault. | Any request whose `Host` is not a loopback name (`127.0.0.1`, `localhost`, `::1`) gets a 403. Lookalikes such as `localhost.evil.example` are refused too. | `test_host_guard.py` |
| **Cross-site writes.** A page POSTs to `http://127.0.0.1:8787` from the background. | A state-changing request carrying a non-loopback `Origin` (including `null`) gets a 403. JSON bodies are also strictly content-typed, so a form POST is rejected. | `test_host_guard.py` |
| **Reading files it should not.** A repository is untrusted input. | The scanner is read-only, honours `.gitignore`, refuses secrets (content-level and by name), binaries and oversized files, and a `.kernote.toml` inside the repo cannot widen those refusals. | `test_secret_scanning.py`, `test_walker_safety.py`, `test_scan_config.py` |
| **Destructive actions by accident.** | Restore and project removal require `confirm=true` and take a snapshot first. Routine backup pruning never touches those safety snapshots. | `test_backup_restore.py`, `test_remove_project.py`, `test_backup_retention.py` |
| **Agents changing your memory.** | The MCP server is read-only by construction: it registers no write tool in any form. | `test_stage7_agents.py` |
| **Known-vulnerable dependencies.** | Pins are audited with `pip-audit` and `npm audit`; a scheduled workflow re-checks them weekly. | `.github/workflows/audit.yml` |

No telemetry. No outbound network calls by default. The one optional download
(the ~90 MB embedding model for semantic search) is opt-in, says what leaves
the machine, and sends model weights only: nothing about your code.

## What it does not defend against

- **Another process running as you.** The API has no authentication, so any
  local program can call it, and any local program can already read your files.
  If that is in your threat model, Kernote is the wrong tool.
- **Other users of a shared machine.** It binds to loopback, which every local
  user can reach. Run it only on a machine you do not share.
- **Changing `KERNOTE_HOST` to a non-loopback address.** Unsupported. The
  Host/Origin guard is a defence for a loopback service, not an access-control
  system.
- **A malicious `kernote-mcp.exe` replacement.** The installer is currently
  **not code-signed**; verify the SHA-256 published with each release.

## Reporting a vulnerability

Please use GitHub's private reporting: **Security → Report a vulnerability** on
this repository. Include the version (`/health` shows the schema version; the
installer shows the app version) and steps to reproduce. Please do not open a
public issue for anything exploitable.
