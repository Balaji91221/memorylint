# MemoryLint usage guide

[Back to README](../README.md) · [Architecture](architecture.md)

Run commands from the repository root unless a command says otherwise.

Evidence-backed repository-memory validation, dependency history, and reviewable
corrections. Local release **0.2.0**; Python 3.10+, standard-library-only base runtime.
Distribution name: `memorylint-ai`; Python import and CLI: `memorylint`. Install with
`python -m pip install memorylint-ai`; add `memorylint-ai[ci]` for ordinary YAML support.
The examples below use the source checkout or extracted source distribution.

MemoryLint checks three explicit claim types: package manager, declared Node
runtime, and package.json script command. It never treats arbitrary prose as true,
never executes repository scripts, and never silently changes memory. Optional
LLM extraction produces labelled candidates that require review.

## Install and first scan

```bash
git clone https://github.com/Balaji91221/memorylint.git
cd memorylint
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/memorylint scan --repo examples/demo
```

The fixture deliberately reports two stale claims and one valid claim, returning
**exit 1**. Build dependencies are setuptools 61+ and wheel; the base runtime has
no third-party dependencies. Ordinary YAML workflows use the optional CI extra
described below. For an offline environment with build tools already present:

```bash
python3 -m pip wheel --no-build-isolation --no-deps --wheel-dir dist .
python3 -m pip install --no-index --no-deps dist/memorylint_ai-0.2.0-py3-none-any.whl
```

Source checkout execution: `PYTHONPATH=src python3 -m memorylint ...`. Windows uses
`.venv\Scripts\memorylint.exe`; set `PYTHONPATH` using the local shell's syntax.

## Explicit Markdown claims

````markdown
# Repository memory

```memorylint
{
  "version": 1,
  "claims": [
    {
      "id": "manager",
      "kind": "package_manager",
      "value": "npm",
      "scope": ".",
      "sources": ["package.json", "pnpm-lock.yaml"]
    },
    {
      "id": "test-command",
      "kind": "script",
      "name": "test",
      "value": "jest",
      "sources": ["package.json"]
    }
  ]
}
```
````

All paths are relative to `--repo`, including when a claim sets `scope`.
`scope: "apps/site"` requires paths such as `apps/site/package.json`. Claim IDs
are unique across the scan. List every authoritative source explicitly; omitted
sources cannot generate a conflict. Unrelated monorepo apps need separate claims.

| Kind | Supported evidence | Comparison |
|---|---|---|
| `package_manager` | package.json `packageManager`; npm/pnpm/yarn/bun lockfile presence | Manager name; lockfile contents are not validated |
| `runtime` | package.json `engines.node`; `.nvmrc`; `.node-version`; literal setup-node steps in GitHub workflow JSON or optional YAML | Declared text, whitespace and numeric `v` prefix normalized |
| `script` | package.json `scripts[name]` | Declared command; never executed |

Different declarations remain a `conflict`, even when semver ranges could be
compatible. Runtime checking does not check the installed interpreter or semver
satisfaction. The dependency-free installation reads **JSON-compatible YAML**.
To read ordinary GitHub Actions `.yml/.yaml` workflows, install the optional CI
extra from this source directory:

```bash
python3 -m pip install 'memorylint-ai[ci]'
```

This adds PyYAML 6.x. The strict parser accepts literal `actions/setup-node`
`with.node-version` declarations, including quoted `'22'` and unquoted `20.10`,
and preserves their exact spelling. It rejects duplicate mapping keys, explicit
tags, anchors, aliases, merge keys, multiple documents, and excessive nesting.
Expressions, matrix jobs, and `node-version-file` indirection remain unsupported.
Without the extra, regular YAML yields an explicit unsupported result and install
hint; JSON workflows still work. Every supported setup-node step is retained as
evidence, so differing CI and manifest declarations remain visible.

Reports include source hashes, selectors, short excerpts, source revision,
memory fence location, a snapshot identifier, and a run identifier. Exit codes:

- **0:** all evaluated claims are valid. Filtered scans may evaluate none; inspect skipped counts.
- **1:** a stale candidate or conflicting declaration needs review.
- **2:** unsupported claims, invalid input, missing evidence, incomplete reads, or infrastructure errors.

`complete` means the scan encountered no input/I/O errors; it is not a replacement
for the exit code. Unknown claims never pass.

## Snapshot consistency and Git

```bash
memorylint scan --repo /path/to/repo --memory AGENTS.md --memory docs/MEMORY.md
memorylint scan --repo /path/to/repo --revision HEAD --format json
memorylint check --repo /path/to/repo --changed-since HEAD~1
```

Working-tree reads are cached for the duration of a scan, bounded to 2 MiB/file,
and re-read at completion; observed concurrent changes make the report incomplete.
For an immutable, coherent snapshot use `--revision`: Git resolves the commit once
and reads regular blobs directly. Snapshot symlinks and submodules are rejected.
The root must be the Git top level for revision/filter modes. Git is optional for
ordinary full scans.

`--changed-since` reads the current working tree and filters by changed memory or
evidence paths, including untracked and deleted files. It is not a historic scan,
and cannot be combined with `--revision`.

## SQLite history and dependency cache

```bash
memorylint scan --repo /path/to/repo --index /path/to/history.sqlite --format json
memorylint history --index /path/to/history.sqlite --claim manager
memorylint history --index /path/to/history.sqlite --reviews
memorylint backup-index --index /path/to/history.sqlite --output /path/to/backup.sqlite
```

The index is created only when explicitly requested. It stores append-only scan,
claim, evidence, and review records, plus a replaceable current dependency cache.
An unchanged claim/evidence signature reuses its finding. Changed, deleted, or
moved sources are checked again; failed scans do not replace a complete cache.
A full indexed scan still reads/hashes dependencies and returns every finding, so
its semantic output matches an unindexed full scan. `cached_claims` reports reuse.
History is scoped by repository/memory set/revision internally; use separate index
files if repository histories must be segregated.

The current SQLite schema is 1. Unknown schemas are rejected without replacement.
Backups use SQLite's backup API, refuse overwrite, and preserve the original.
Future migrations must operate on a backup; no unneeded in-place migration is
performed. Index files have restrictive permissions and may contain source excerpts.

## Propose, review, explicitly apply

Use a disposable copy of the demo to try mutation:

```bash
cp -R examples/demo /tmp/memorylint-review-demo
memorylint propose --repo /tmp/memorylint-review-demo --claim package-manager --output /tmp/manager.patch.json
# Read the JSON's unified diff and expected source hashes.
memorylint apply --repo /tmp/memorylint-review-demo --patch /tmp/manager.patch.json --index /tmp/memorylint-history.sqlite
```

`propose` never changes memory and refuses ambiguous conflicts or claims without a
replacement. An existing patch file is never overwritten. `apply` requires an
explicit audit index, checks the memory hash and evidence hashes, revalidates the
replacement, verifies the displayed diff, and changes only the selected JSON
claim value. Other prose is preserved; that fence is pretty-printed.

Concurrent changes cause a conflict. Cooperating MemoryLint writers are serialized
by an exclusive repository lock; observed external changes are rejected immediately
before replacement. A hostile writer racing the final OS rename is outside this
optimistic protocol. Apply refuses symlinked or multiply linked memory targets.

An audit entry is recorded as `prepared` before replacement and `applied` afterward.
A crash between those records requires comparing the recorded new hash to the
current file before deciding whether to re-propose. Never blindly replay a patch.
A leftover `.memorylint-apply.lock` can be removed only after confirming that its
writer is no longer running. `memorylint reject --patch ... --index ...` records a
rejected review without touching memory. `--expected-hash` can additionally bind
an apply request to the hash your interface displayed.

## Optional extraction and evaluation

```bash
memorylint extract --repo examples/extraction --memory MEMORY.md --source package.json --response examples/extraction/response.json
memorylint extract --repo examples/extraction --memory MEMORY.md --source package.json --provider-command python3 examples/extraction/provider.py
memorylint evaluate --dataset evals/heldout.json
```

The first command replays a saved provider response. The second runs an explicitly
configured provider bridge (the bundled example is also a fixture). Its stdin
contains a versioned instruction, Markdown, allowed source contents, and limits;
stdout must contain one JSON response. No shell interpolation is used. Replace
its `complete()` function with your chosen model client; keep credentials in its
environment, not in memory files. See [the provider contract](../docs/api/provider.md).

Input/output bytes, output-token reports, elapsed time, and cost reports are
bounded and validated. The command process is terminated on timeout or oversized
output; on POSIX its process group is cleaned up. The configured provider must
reserve/enforce its cost budget before billing. MemoryLint cannot reverse remote
charges or independently verify a provider's billing report.

Candidates must quote actual memory text and reference only approved paths.
They are labelled `review_required`; deterministic validators produce candidate
findings. Nothing is accepted or patched automatically. Using an external provider
sends exactly the selected Markdown and source contents to that configured process;
any subsequent remote transfer is controlled by that provider.

The held-out fixture set tests parsing, attribution, ambiguity, stale flags, scope,
and scoring. Its replay precision/recall **is not a claim of live-model accuracy**.
The SDK evaluator accepts `provider_factory` to run the same held-out labels against
an actual model. External model validation is still required before that release claim.

## Read-only MCP integration

Configure your MCP client to launch:

```bash
memorylint serve --repo /absolute/repository --memory AGENTS.md
```

The process exposes `memorylint_scan` and `memorylint_explain({"claim_id":"manager"})`.
Root and memory files are bound at startup; tool arguments cannot change them.
There are no write, extraction, shell, or apply tools. Scans do not open an index
or create files. stdio is newline-delimited JSON-RPC, with MCP initialization,
tools/list, tools/call, notifications/initialized, and ping. Supported protocol
versions: 2024-11-05, 2025-03-26, 2025-06-18, and 2025-11-25. This is a synchronous
local server without HTTP transport or task/cancellation extensions. References:
[MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
and [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

## Python SDK

```python
from memorylint import scan_memory, propose_patch, apply_patch

result = scan_memory('/path/to/repo', ['AGENTS.md'], index_path='/tmp/history.sqlite')
report = result.to_dict()  # report schema 2; Markdown claim schema remains 1

patch = propose_patch('/path/to/repo', 'manager')
print(patch.diff)          # present to the user first
# Only after the caller explicitly chooses to apply:
# apply_patch('/path/to/repo', patch, index_path='/tmp/history.sqlite')
```

## Verification and maintenance

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m memorylint evaluate --dataset evals/heldout.json
```

See [feature status](../IMPLEMENTATION_STATUS.md),
[contribution guidance](../CONTRIBUTING.md), [security guidance](../SECURITY.md), and
[release notes](../CHANGELOG.md). CI builds a wheel, installs it in a fresh environment,
and runs tests and evaluation. See the [workflow history](https://github.com/Balaji91221/memorylint/actions/workflows/ci.yml)
for current hosted results. Independent pilots have not been claimed. No hosted service, general truth checker, vector database, or
automatic memory rewrite is part of this local release.
