# Implementation status

Development release **0.2.0**, implemented and locally verified 2026-10-13.
The distribution is `memorylint-ai`; import and CLI remain `memorylint`. Public distribution
artifacts use SPDX MIT metadata and include a PyPI-specific description.
No hosted deployment, live-model quality result or outside pilot is claimed.

## Plan feature matrix

| Plan area | Implemented local behavior | Evidence / remaining boundary |
|---|---|---|
| Supported claim schemas | Explicit Markdown JSON claims for package manager, Node declaration, scripts | Schema/path/conflict tests; arbitrary prose is unsupported |
| Manifest/CI evidence | package.json, lockfile presence, .nvmrc/.node-version, literal setup-node fields | JSON uses stdlib; optional strict PyYAML adapter supports ordinary YAML. Duplicate keys/tags/aliases/matrices/expressions rejected |
| Source snapshots | Cached working-tree reads with final hash verification; immutable Git commit blobs | Concurrent-edit and real Git integration tests |
| Claim/evidence index | SQLite schema 1, source hashes, dependencies, complete-scan finding cache | Indexed/full equivalence, deletion, affected-claim tests |
| History | Append-only scan, claim-definition, evidence, review rows | Revision history and backup tests |
| Reviewable corrections | JSON proposal with unified diff, original/source hashes | Prose-preserving patch tests |
| Explicit application | Hash/diff revalidation, writer lock, replacement, prepared/applied audit | Concurrent memory/source conflicts and tampering tests |
| Optional extraction | Versioned provider protocol, fixture replay, bounded command bridge, budgets | Contract, quote/path, deadline, output/token/cost validation |
| Held-out evaluation | Eight labeled replay cases; precision/recall and false-stale scorer | Offline score verified; real-model accuracy still unmeasured |
| CLI + SDK | Scan/check, history, backup, propose/apply/reject, extract/evaluate, serve | Source and installed-wheel tests plus CLI workflow smoke |
| MCP checker | Root-bound read-only stdio scan/explain; lifecycle and tool schemas | Actual stdio subprocess integration test; no write tool |
| Operations/release files | CI config, contribution/security guide, changelog, MIT license, copy-first backups | Public distribution packaging prepared; hosted results linked below; external pilots remain separate |

## Verification

- **44 tests passed** from source on Python 3.10.10/macOS with optional PyYAML 6.0.3.
- A real `python -S` process verifies base-package imports and JSON workflow parsing
  without site packages; regular YAML produces the optional-dependency install hint.
- Clean-installed 0.2.0 base wheel: 37 tests passed, with 7 optional-YAML tests
  explicitly skipped because the extra was not installed. The full source run above
  exercised those optional checks. Installed SDK/CLI and held-out replay checks passed.
- Eight held-out fixture replays: 6 expected candidates, no invalid runs,
  precision 1.0, recall 1.0, false-stale rate 0.0. These are deterministic replay
  results, **not live-model quality measurements**.
- Installed CLI smoke: scan/index → propose → apply → review history, plus the
  command-provider extraction bridge, passed in a disposable repository.
- Demo retains two intentional stale claims and one valid claim before applying.
- The earlier local package used setuptools 65.5.0 / wheel 0.47.0. Public
  distribution metadata now requires setuptools 77+ for SPDX license support;
  releases must pass a fresh wheel/sdist build and isolated installation.
- CI defines Python 3.10/3.13 on Linux/macOS, testing both the base install and the
  optional CI adapter. See [current hosted results](https://github.com/Balaji91221/memorylint/actions/workflows/ci.yml).

Run these commands from this repository's root to repeat the source checks:

```bash
python3 -m pip install '.[ci]'
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m memorylint evaluate --dataset evals/heldout.json
python3 -m pip wheel --no-deps --wheel-dir dist .
```

## Boundaries

Only explicitly referenced sources participate. Package-manager evidence is a
presence/declaration check; semver compatibility and installed-runtime checks are
out of scope. Working-tree verification detects observed edits but cannot make
arbitrary concurrent filesystem operations atomic; use a Git revision when needed.
Optimistic apply cannot defeat a malicious writer racing the final rename. Read
SECURITY.md before inspecting hostile repositories or running provider commands.

Command providers own their credentials, networking, pricing/admission, and remote
billing. MemoryLint enforces process deadlines/byte bounds and validates reported
usage but cannot independently audit or reverse charges. Candidate extraction never
writes instructions. In-process custom providers must honor their deadline contract.

No hosted dashboard, vector database, personal-memory hosting, universal natural-
language truth checker, or automatic background rewriting is implemented or in
scope. User interviews, independent pilots, model-backed evals, hosted CI,
release artifact verification and independent pilots require separate evidence.
Publishing a package does not complete those validation gates.
