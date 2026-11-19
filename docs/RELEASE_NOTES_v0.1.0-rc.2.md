# Kernote v0.1.0-rc.2

First release with a **Windows installer**. Pre-release: it is a release candidate, not a stable 1.0.

## Download

**`Kernote-Setup-0.1.0.exe`** (65.5 MB, Windows). Per-user install, no admin rights.

```
SHA-256  06ccc814c5149550c49854c8594a0538034a6a2c8881582d01d1ba014d4a6ed9
```

```powershell
Get-FileHash Kernote-Setup-0.1.0.exe -Algorithm SHA256
```

> **The installer is not code-signed.** Windows SmartScreen will say *"Unknown publisher"*. Check the hash above,
> then choose **More info → Run anyway**. Signing needs a purchased certificate; until then, the hash is your assurance.

Built from commit `40dbf6b`, which passed CI on Windows and Linux.

## What is new since rc.1

**A real app, not a localhost site**
- Windows installer with Start Menu entry and uninstaller. Uninstalling removes the program and **keeps your data**.
- Native window, sized to fit your screen; no console window.
- **Add project** from the UI: folder picker, background scan with live status. Previously there was no way to do this from the UI.
- **Remove project**: confirmed, snapshot taken first, never touches your folder.
- `kernote-mcp.exe` ships beside the app so coding agents can use the installed copy over MCP.

**Security**
- All 93 known advisories in the pinned dependencies cleared (`pip-audit` and `npm audit`: 0).
- Web pages can no longer talk to the local API: non-loopback `Host` headers (DNS rebinding) and cross-origin writes are refused. See `SECURITY.md`.

**Fixes found by running it on Windows**
- The port-in-use check reported busy ports as free.
- A windowed build died silently on its first log line (no stderr). Logs now go to `<data dir>\logs\kernote.log`.
- A weak search result was labelled "quoted from source". It is now "lead, not an answer".
- The review queue sat below 25 optional suggestions; it now comes first.
- Routine backups grew without limit; the 20 newest are kept (safety snapshots are never pruned).

**Smaller**
- Main UI bundle 522 kB → 329 kB (the graph loads on demand).
- CI on Windows and Linux; weekly dependency audit.

## Verified

559 tests pass, 13 skip (they need the optional 90 MB embedding model). This installer was installed, launched, and uninstalled
on Windows 11; the installed `kernote-mcp.exe` was driven by a real MCP client over stdio.

## Known limitations

- Unsigned installer (above).
- Tested on Windows 11 only. Windows 10 needs the WebView2 runtime.
- Semantic search (opt-in, ~90 MB download) was not re-measured after the embedding library upgrade.
- The Browse… folder dialog has not been clicked in a real session; only that its bridge exists.
- The MCP helper prints a harmless traceback to stderr at shutdown (exit code 0, protocol clean).
- No screen-reader audit. Only Claude Code has been used as an MCP client.
- `Kernote` is a provisional name pending trademark clearance.

Full detail: [`docs/DEV_HANDOFF.md`](https://github.com/pavannithin224-abcd/kernote/blob/main/docs/DEV_HANDOFF.md).
