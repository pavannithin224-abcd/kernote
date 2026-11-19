<div align="center">

<img src="docs/assets/banner.png" alt="kernote_ : reviewable project memory. Every fact carries its evidence." width="100%">

### Your project's memory, with receipts.

Kernote reads a codebase and builds a **cited, evidence-backed model of it**. When the code moves, it tells you
exactly which facts to re-check. It answers questions with sources, or says *"evidence not found."*
It runs on your machine, offline, as a Windows app or from source.

<p>
<a href="https://github.com/pavannithin224-abcd/kernote/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/pavannithin224-abcd/kernote/actions/workflows/ci.yml/badge.svg"></a>
<img alt="status" src="https://img.shields.io/badge/status-release%20candidate-e8a317?style=flat-square">
<img alt="python" src="https://img.shields.io/badge/python-3.12-3776ab?style=flat-square&logo=python&logoColor=white">
<img alt="platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-0b6e86?style=flat-square">
<img alt="license" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square">
</p>
<p>
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
<img alt="React" src="https://img.shields.io/badge/React-20232a?style=flat-square&logo=react&logoColor=61dafb">
<img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178c6?style=flat-square&logo=typescript&logoColor=white">
<img alt="SQLite" src="https://img.shields.io/badge/SQLite%20%2B%20FTS5-003b57?style=flat-square&logo=sqlite&logoColor=white">
<img alt="local-first" src="https://img.shields.io/badge/local--first-no%20telemetry-0b6e4f?style=flat-square">
<img alt="MCP" src="https://img.shields.io/badge/MCP-read--only-8a5cf5?style=flat-square">
</p>

<img src="docs/screens/dashboard.png" alt="The Kernote dashboard. The intelligence queue shows a decision that changed inside the lines a memory cites, and two decisions that contradict each other, both kept open. Freshness reads 98%." width="92%">
<br>
<sub>A real scan of a sample service, after its docs and code were edited. Kernote noticed both changes. <b>Nothing</b> was merged or marked wrong for you.</sub>

</div>

---

## Two ways in

|  | |
|---|---|
| **[Download the app](../../releases)** | Windows installer, **65 MB**. Per-user, so no admin rights. Double-click, add a folder, done. No Python, no Node, no setup. |
| **Run from source** | `git clone`, one `pip install`, one `npm install`. Same code, scriptable, hackable. [Jump to it.](#run-from-source) |

The installed app and the source checkout run the **same code**. The desktop build is a window around the same
FastAPI service, and the same test suite covers both.

---

## Why it exists

Every team has a document that says one thing and code that does another. Project notes rot silently, and
the fix is never "write more notes", because nobody knows *which* notes just became wrong.

Kernote keeps a **reviewable** model of a project and keeps it honest as the code changes:

- **Every fact carries its evidence**: file, line range, content hash, and full revision history.
- **Every change to the code says which facts to re-check**, pinned to the diff hunk that overlaps the claim, not just "the repo changed."
- **Nothing enters or leaves the vault without you seeing why.** Conflicts are held open, merges need approval, and approvals can be undone.

It is an **audit and review workspace**, not another agent-memory server. See
[how it differs](docs/COMPETITIVE_LANDSCAPE.md).

---

## See it work

<div align="center">
<img src="docs/demo.webp" alt="A 46-second walkthrough of the real app: add a project, scan it, ask a question and get cited evidence, get an honest refusal when nothing answers, then watch drift and a contradiction appear after the docs change." width="92%">
<br>
<sub>A real capture: <b>46 seconds</b>, from an empty install to drift and a held-open contradiction. Not a mock-up. Smaller file: <a href="docs/demo.mp4"><code>docs/demo.mp4</code></a>.</sub>
</div>

<details>
<summary><b>The original 19-second pitch</b></summary>
<br>
<div align="center">
<img src="docs/brag.webp" alt="Kernote: a cited answer, drift down to the hunk, and a conflict held open. 19 seconds." width="92%">
<br>
<sub><b>Illustrative.</b> The question and citations in this teaser are made up for the video, not output from a real vault. The walkthrough above is the real thing. <a href="docs/brag.mp4"><code>brag.mp4</code></a> has sound (music: <i>Wisps of Whorls</i> by <a href="https://incompetech.com">Kevin MacLeod</a>, <a href="http://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>).</sub>
</div>
</details>

---

## What it does

### 1. Add a project in one step

Pick a folder. Kernote registers it, reads it **read-only** in the background (the window never freezes), then checks the result for drift, conflicts and duplicates.

<div align="center">
<img src="docs/screens/add-project.png" alt="The Add project dialog: a folder path, an auto-filled name, and a live status line reading 'Reading the project. Files are only read, never changed.'" width="92%">
<br>
<sub>The scanner honours <code>.gitignore</code>, refuses secrets and binaries, never writes into your repository, and explains every file it skipped.</sub>
</div>

### 2. Ask a question. Get evidence, or an honest "I don't know"

Kernote does not write an answer. **There is no language model in the loop.** It returns the records that bear on your question, each quoted from its source with a citation.

<div align="center">
<img src="docs/screens/query-answer.png" alt="Asked which database the project uses and why: one record quoted from ARCHITECTURE.md lines 7 to 12, with four weaker matches listed separately as 'also retrieved, not verified'." width="92%">
<br>
<sub>The reason, quoted from <code>ARCHITECTURE.md:7-12</code>. Four weaker matches are shown, but labelled <i>not verified</i> rather than offered as proof.</sub>
</div>

<br>

When nothing in the project answers the question, it says so. Candidates are shown as **leads, not answers**:

<div align="center">
<img src="docs/screens/query-refusal.png" alt="Asked how many nodes the Kubernetes cluster has: the outcome reads 'no direct evidence', 75% of the question's terms occur nowhere in the project, and every candidate row is badged 'lead, not an answer' with no confidence figure." width="92%">
<br>
<sub>"75% of what you asked about does not occur anywhere in this project." Declining is a feature, so it is designed and measured, not an error state.</sub>
</div>

### 3. Know exactly what went stale, and why

When a cited file changes, Kernote shows the **overlapping diff hunk** that triggered the concern. When two sources disagree, **both claims stay visible** with their origins until you resolve it. It never silently picks a winner.

<div align="center">
<img src="docs/screens/review-queue.png" alt="The review queue: a high-severity 'may be stale' finding on docs/adr/0002-redis-queue.md lines 1 to 25 with changed lines 12 to 12, and a high-severity contradiction between ADR-0002 (Redis streams) and ADR-0007 (Celery with RabbitMQ), each with Needs attention and False positive actions." width="92%">
<br>
<sub>A decision reversed in one document and contradicted in another. Findings are requests for review, <b>never verdicts</b>.</sub>
</div>

### 4. See what a commit puts at risk

<div align="center">
<img src="docs/screens/change-impact.png" alt="Change Impact for HEAD~1 to HEAD: 1 file changed, 1 memory directly affected because the changed lines overlap the lines it cites, 0 same-file-only, and the affected decision listed for review." width="92%">
<br>
<sub>A memory is <b>directly affected</b> only when the changed lines overlap the lines it cites, not merely because its file appears in the diff. That is the difference between a useful signal and noise.</sub>
</div>

### 5. See how it all connects

<div align="center">
<img src="docs/screens/knowledge-graph.png" alt="The knowledge graph: 52 memory nodes and 93 edges, clustered by shared files and entities, with one node selected and its record, citation and connections shown below." width="92%">
<br>
<sub>Every dot is a memory. Every line is a row in the database, either a link you confirmed or a shared entity. Nothing is drawn that cannot be explained.</sub>
</div>

### 6. Hand reviewed memory to your coding agent

Kernote serves approved memory over a **read-only MCP server**. There is no write tool in any form, so an agent can use your project's decisions but cannot change them.

<div align="center">
<img src="docs/screens/agent-integrations.png" alt="Agent Integrations: four read-only MCP tools (build_context, get_decision, project_summary, search_memory) and a ready-to-copy 'claude mcp add' command for this project." width="92%">
<br>
<sub>The screen generates the exact registration command for <i>your</i> install and project, with a <b>Copy</b> button.</sub>
</div>

---

## How it works

```mermaid
flowchart LR
    R[("Your repository<br/><i>read-only</i>")] -->|"allowlist · secrets refused"| S["Scan"]
    S --> M["<b>Typed memories</b><br/>file · lines · hash<br/>full revision history"]
    M --> A["Analyse<br/>drift · conflicts · duplicates"]
    A --> Q{{"Review queue<br/><b>you decide</b>"}}
    Q -->|"approve · undo"| M
    M --> Ask["Ask<br/>cited answer or refusal"]
    M --> G["Graph · Change impact"]
    M --> MCP["Read-only MCP<br/>for coding agents"]
```

Seven memory types (fact, architecture, decision, procedure, convention, gotcha, current state), each with
**provenance down to the line** and a lifecycle. Extraction is deterministic and rule-based. Code symbols come
from tree-sitter for Python, TypeScript, TSX and JavaScript. Markdown and `pyproject.toml` / `package.json` /
`requirements.txt` manifests are parsed everywhere. Retrieval is SQLite FTS5 (BM25), optionally fused with local
MiniLM embeddings by reciprocal rank. Full design: [ARCHITECTURE](docs/ARCHITECTURE.md), [MEMORY_MODEL](docs/MEMORY_MODEL.md).

---

## Install

### The app (Windows)

Tested on **Windows 11**. (Windows 10 needs the Microsoft WebView2 runtime, which up-to-date systems already have.)

Download `Kernote-Setup-0.1.0.exe` from [Releases](../../releases) and run it. It installs **per-user**
(`%LOCALAPPDATA%\Programs\Kernote`), so Windows never asks for admin rights, and it adds a Start Menu entry.
Verify the download first if you like:

```powershell
Get-FileHash Kernote-Setup-0.1.0.exe -Algorithm SHA256
```

> **Heads-up: the installer is not code-signed yet.** Signing needs a purchased certificate, and Windows
> SmartScreen will show *"Unknown publisher"* until there is one. Check the SHA-256 against the release notes, then
> choose **More info → Run anyway**. This is stated up front because a security tool should not hide it.

**Uninstalling removes the program but never your data.** The vault lives in `%LOCALAPPDATA%\kernote\kernote`, and the
uninstaller tells you where it is so you can delete it yourself if you want it gone.

### Run from source

<details open>
<summary><b>Windows, macOS or Linux</b>: Python 3.12+, Node 20+, Git 2.40+</summary>

```bash
git clone https://github.com/pavannithin224-abcd/kernote.git
cd kernote

python -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt     # Windows: backend\.venv\Scripts\pip

npm --prefix frontend install
npm --prefix frontend run build
```

Run it as one process on one port, then open <http://127.0.0.1:8787>:

```bash
KERNOTE_CORS_ORIGINS='[]' backend/.venv/bin/python -m uvicorn kernote.main:app --app-dir backend --port 8787
```

On Windows PowerShell, set the variable first: `$env:KERNOTE_CORS_ORIGINS='[]'`.

Or in its own window (needs `pip install -r backend/requirements-desktop.txt`):

```bash
cd backend && .venv/bin/python -m kernote.desktop
```

With [`just`](https://github.com/casey/just): `just app` serves it, `just desktop` opens the window, `just dev` runs hot-reload
(API on :8787, UI on :5173), and `just ci` runs lint, tests and the build.

</details>

Build the Windows installer yourself: `npm --prefix frontend run build`, then `pyinstaller kernote.spec`, then compile
[`packaging/kernote.iss`](packaging/kernote.iss) with [Inno Setup 6](https://jrsoftware.org/isinfo.php). The spec builds both
`kernote.exe` (windowed) and `kernote-mcp.exe` (console, because MCP over stdio needs stdin and stdout).

---

## Use it with a coding agent

The Agent Integrations screen prints the exact command. From the installed app it looks like this:

```powershell
claude mcp add kernote --env KERNOTE_PROJECT=<project-id> --env KERNOTE_DATA_DIR=<vault-dir> -- "C:\Users\<you>\AppData\Local\Programs\Kernote\kernote-mcp.exe"
```

Four tools, all read-only: `kernote_search_memory`, `kernote_get_decision`, `kernote_project_summary`, `kernote_build_context`
(a Markdown bundle of approved memory inside a **token budget**, which states what it dropped). The server is verified against a
real MCP client over stdio, **including the installed `kernote-mcp.exe`**. Claude Code is the only agent it has been
driven from so far.

---

## Choosing what gets scanned

Kernote reads documentation, source and configuration under a built-in allowlist, honours `.gitignore`, and explains every
file it skipped. To adjust it, commit a `.kernote.toml` to the repository root:

```toml
[scan]
include = ["data/schemas/**/*.json", "deploy/*.yaml"]
exclude = ["vendor/**", "docs/generated/**"]
```

The asymmetry is deliberate: **exclude always beats include**, include widens only the allowlist, and **nothing in a repo can
talk Kernote into reading a private key**. A config file inside a repository is untrusted input. `.gitignore` is always
respected, with no switch to disable it. Settings shows the effective configuration with its provenance.

---

## Measured, not claimed

| | |
|---|---|
| Tests | **572** backend tests: **559 pass**, 13 skip (they need the optional 90 MB embedding model or the eval extras, which CI deliberately does not install). CI runs them on **Windows and Linux** |
| Quality gates | `ruff` · `tsc -b` · `eslint` · `npm audit` (0) · `pip-audit` (0) |
| Shipped dependency advisories | **0**. (The previous pins carried 93; see [SECURITY.md](SECURITY.md).) |
| Installer | **65 MB**, per-user, no admin |
| UI bundle | 329 kB (100 kB gzip); the graph loads on demand |
| Retrieval, labelled set | Recall@5 **0.80** keyword-only, **0.98** with semantic search on · useful abstention **83%** · citation correctness **43%** / **55%** (keyword / semantic) ([EVALUATION](docs/EVALUATION.md)) |
| On a real repository | declines **4 of 4** unanswerable questions |

Retrieval is **extractive**: it competes on whether the citations are correct and the abstentions honest, not on fluency.
Those numbers come from a 31-question labelled set and are reproduced by the **Run evaluation** button in Settings. They are
not a marketing figure.

---

## Privacy and safety

- **Local-first.** No telemetry, no accounts, no outbound calls by default. The one optional download (the ~90 MB embedding model for
  semantic search) is opt-in, says what leaves the machine, and sends model weights only.
- **Web pages cannot talk to it.** Requests with a non-loopback `Host` (DNS rebinding) or a cross-origin write are refused.
  Tested. See [SECURITY.md](SECURITY.md) for the full threat model *and what it does not cover*.
- **Destructive actions are guarded.** Restore and project removal require explicit confirmation and take a safety snapshot first.
  Routine backup pruning never touches those snapshots. Removing a project **never touches your folder**.
- **Read-only agent surface.** The MCP server registers no write tool.

---

## Honest limitations

- **Unsigned installer.** SmartScreen will warn (see above).
- **Extraction is rule-based**, so recall is lower than an LLM pipeline would give. A model adapter is optional and additive ([ADR-0006](docs/DECISIONS.md)).
- **Symbol extraction** covers Python, TypeScript, TSX and JavaScript. Other languages are stored as text.
- **Paraphrased questions** can miss: on 24% of answerable questions it finds the right document but declines to call it an answer
  ([ADR-0032](docs/DECISIONS.md)). When it declines, it shows leads rather than hiding them.
- **No batch approval** for consolidations yet (relationship links have it), so clearing a big duplicate backlog is one request each.
- **Never checked with a real screen reader.** Structure, labels, focus and contrast are covered by automated guards; that is not the same thing.
- **One agent tested** over MCP (Claude Code).
- **Semantic search is opt-in** (a one-time ~90 MB download). Its end-to-end path was last exercised on the previous embedding library version; the unit-level API is verified compatible with the current one.
- **The packaged MCP helper prints a harmless traceback to stderr at shutdown.** Exit code 0, protocol clean, no orphan processes.

---

## Documentation

| Document | What is in it |
|---|---|
| [PRODUCT_SPEC](docs/PRODUCT_SPEC.md) | Problem, users, features with priorities, acceptance criteria |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Process shape, modules, API surface, full SQLite schema, security boundaries |
| [MEMORY_MODEL](docs/MEMORY_MODEL.md) | The four data layers, nine lifecycle stages, record design, invariants |
| [DECISIONS](docs/DECISIONS.md) | ADRs with alternatives and consequences |
| [EVALUATION](docs/EVALUATION.md) | Measured retrieval quality |
| [COMPETITIVE_LANDSCAPE](docs/COMPETITIVE_LANDSCAPE.md) | Who else ships this, and where the real gap is |
| [SECURITY](SECURITY.md) | Threat model, what is and is not defended |
| [DEV_HANDOFF](docs/DEV_HANDOFF.md) | Current state, what is verified and what is not |
| [CLAUDE.md](CLAUDE.md) | The project contract for Claude Code |

`Kernote` is a **provisional working name** pending trademark, domain and registry clearance ([spec §9](docs/PRODUCT_SPEC.md)).
The mark in [`design/logo/`](design/logo/) needs the same clearance before public use.

## License

MIT. See [LICENSE](LICENSE).
