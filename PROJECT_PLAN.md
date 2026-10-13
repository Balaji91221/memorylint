# MemoryLint project plan

Evidence based validation of repository memory.

**Status:** Local roadmap phases implemented in release 0.2.0; external validation and PyPI publication remain outstanding. See [current implementation status](IMPLEMENTATION_STATUS.md) and [usage instructions](README.md). This plan retains the broader proposed roadmap; deployment and production validation have not started. **Planning date:** 13 October 2026. Package names and interfaces below are illustrative and must be checked before publication.

## Goal and target users

Developers using coding assistants with saved repository instructions and project memory.

Stored notes say a project uses npm while lockfiles and CI now use pnpm. MemoryLint links a claim to source evidence, detects changes, and proposes reviewable corrections rather than silently overwriting memory.

## Product hypothesis and validation

Dependency tracking between memory claims and versioned source evidence. A general memory store is outside the scope; integrate with existing stores after repository-specific validation is useful.

Before expanding the implementation, interview three to five target developers. Ask for a recent concrete failure, current workaround, and a repository or sanitized fixture they can share. A successful pilot means someone other than the author can install the tool, reproduce a useful finding, and explain why it belongs in their workflow. These are validation goals, not established demand.

## First release scope

Markdown memory input, explicit source references, Git change detection, and three supported claim types: package manager, declared runtime version, and documented script command. Return valid, stale_candidate, conflict, or unsupported.

**Out of scope:** No universal natural-language truth checker, automatic rewriting of instructions, personal-memory hosting, or vector database in v1.

## Representative workflow

Developer registers a memory file → parser identifies typed claims and evidence refs → source resolver reads the pinned repository state → rules compare claims with manifests and CI → report proposes corrections → user reviews and applies a patch.

## High level design

```text
Memory files + Git snapshot -> Claim parser -> Claim/evidence graph
Changed source files -> Dependency index -> Affected claims -> Validators
Validator results -> Reviewable report/patch
```

**Implementation stack:** Python, typed data models, Git subprocess adapter, SQLite claim/evidence index, Markdown parser, CLI; optional MCP server after the core checker.

**Architecture choice:** Rescanning every claim is simplest for a prototype. Choose dependency-indexed checks after correctness is established. A semantic vector search can find related evidence but cannot establish truth, so defer it.

Keep the core as a local library with thin interface adapters. Process boundaries shown above are deliberate; do not split every module into a deployed service. A dashboard is a consumer of the core results, not the owner of domain rules.

## Low level design

| Component | Contract | Responsibility and state |
|---|---|---|
| `ClaimParser` | `parse(memory) -> Claim[]` | Identifies supported claim schemas; marks ambiguous text unsupported. |
| `EvidenceResolver` | `resolve(ref, revision) -> Evidence` | Reads exact files and source hashes. |
| `DependencyIndex` | `affected(changedRefs) -> ClaimId[]` | Owns claim-to-evidence edges. |
| `ClaimValidator` | `validate(claim, evidence) -> Finding` | Owns type-specific consistency rules. |
| `PatchProposer` | `propose(finding) -> ProposedPatch` | Produces edits without applying them. |
| `ReviewService` | `apply(patch, expectedHash) -> ApplyResult` | Rejects stale edits and records acceptance. |

### Data and state ownership

Claim(id, kind, value, memoryLocation); Evidence(ref, revision, contentHash, excerpt); Dependency(claimId, evidenceRef); Finding(status, explanation, evidenceRefs); Review(decision, originalHash, newHash). Claim revisions are append-only audit records.

### Invariants

Repository path does not imply truth for every claim. Conflicting sources stay visible; no arbitrary latest-file-wins rule. Every correction points to evidence. Applying a patch requires the original file hash to match. Unsupported claims cannot be reported valid.

### Failure and concurrency behavior

Git-unavailable mode can perform a full snapshot scan. Deleted evidence invalidates its references without deleting history. Resolve symlinks and restrict access to configured roots. Concurrent memory edits cause a review conflict. Incomplete indexing must be reported, not treated as no findings.

## SOLID decisions

- **Single responsibility:** ClaimParser owns input interpretation; ReviewService owns its separate output or integration concern. Domain evaluation does not move into CLI handlers.
- **Open closed:** introduce a new supported adapter behind an existing contract; add new domain behavior explicitly rather than adding hidden project-name switches.
- **Liskov substitution:** adapters must preserve documented result, error, cancellation, and completeness semantics. Run the same contract fixtures against every implementation; unsupported behavior must be explicit.
- **Interface segregation:** separate inspection from mutation and execution from reporting. Consumers receive only the operations they use.
- **Dependency inversion:** domain logic consumes typed contracts; the CLI or composition root wires concrete filesystem, transport, and provider implementations. Pure transformations stay functions instead of gaining unnecessary interfaces.

## LLM system design

Optional claim extraction produces candidates in a constrained schema. Deterministic validators handle supported fields. Label model-proposed interpretations separately; evaluate extraction precision and false stale flags against annotated repositories. Never treat repository text as execution instructions.

When optional model calls are introduced, version prompts and output schemas, validate every response, bound tokens/time/cost, and store source references. Treat retrieved files and tool output as data. Keep model output out of authorization and deterministic pass/fail decisions. Document which content leaves the machine.

## Installation and integration design

The following command names are proposed interfaces for this future project; they are not claims that published packages exist. Reserve a package name, select a license, and publish only after the clean-install gate passes.

```text
memorylint scan --memory AGENTS.md --repo .
memorylint check --changed-since HEAD~1
memorylint propose --finding finding-123
```

**Public SDK contract:**

```text
scan_memory(repo, memory_paths, revision) -> ScanResult
```

Provide one end-to-end example with pinned supported dependencies. Keep the CLI a wrapper over the public SDK. Document configuration discovery, schema version, error categories, supported platforms, and exit codes. For check-oriented commands, distinguish success, failed checks, and incomplete/infrastructure failure. MCP integrations should expose narrow tools and validate configured roots; a plugin packages instructions and connection configuration rather than duplicating the engine.

## Repository structure

```text
src/
  core/             # Domain types, state, and evaluation
  adapters/         # External protocols, analyzers, runners, or storage
  cli/              # User commands and composition
tests/
  unit/
  integration/
  fixtures/
examples/
docs/
  decisions/
  api/
```

Add a report UI or server directory only when that milestone begins. Keep runtime artifacts and any credential files out of version control. Do not create a shared framework spanning these seven independent projects.

## Implementation roadmap

| Phase | Working deliverable | Verification gate |
|---|---|---|
| 1. Define supported claims | Write annotated memory/source fixture pairs. | Each claim has a documented authority and conflict rule. |
| 2. Implement deterministic scanner | Read manifests, scripts, and explicit source references. | Baseline fixtures classify correctly. |
| 3. Add dependency tracking | Persist source hashes and claim edges. | Incremental output matches a full scan. |
| 4. Add reviewable corrections | Generate patches with optimistic concurrency checks. | Concurrent edits are preserved. |
| 5. Add optional extraction | Parse prose into candidate typed claims. | Compare extraction with a held-out labeled set. |
| 6. Package integrations | Ship CLI, Python API, and a read-only MCP checker. | A clean repo can be scanned with one documented command. |

Proceed in order. Each phase should finish with a runnable example and its verification evidence. Size the next phase after measuring the current one; no fixed delivery date is assumed.

## Testing and evaluation

Fixtures for npm→pnpm changes, multiple package managers in a monorepo, conflicting CI and manifest runtime versions, deleted scripts, moved source files, unsupported prose, and edits during patch review.

Release gate: supported fixtures receive correct statuses and all findings include evidence. Measure precision of stale_candidate findings separately from recall. No silent edits; applying a stale patch must fail.

Use unit tests for pure rules and integration tests at external boundaries. Maintain a held-out set for model-dependent behavior. Record run counts, versions, and incomplete cases. Do not call a system production-ready based only on seeded fixtures.

## Operations and release

- Start local-first. Log structured event IDs, durations, completeness, and errors without secrets; make detailed source capture explicit.
- Version configuration and stored artifact schemas. Validate compatibility before loading older artifacts; migrate a copy and retain the original.
- Pin supported integration versions in examples and test the documented minimum/current range before releases.
- Build distributable artifacts in CI and test installation in a clean environment. Publish release notes, a changelog, contribution instructions, and a security-reporting route.
- Roll back by pinning the previous package version. Keep baseline artifacts readable; do not overwrite them during a failed upgrade.
- A future hosted dashboard requires authentication, tenant isolation, retention/deletion controls, job quotas, and tested backups. Those are a separate release, not implicit MVP features.

## Learning outcomes

Build the deterministic core to practice data modeling and LLD. Trace the process and storage boundaries to practice HLD. Package the CLI/SDK to learn API stability and developer experience. Add model evaluation only where the product needs it. Use the optional report UI to learn full-stack integration around meaningful domain results.

## Open decisions and risks

A monorepo may legitimately use multiple tools. Authority must be scoped by project and claim type. Need real user examples to choose additional claim types; avoid broad contradiction claims before evaluation.

Before implementation: confirm the first supported platform and dependency versions, choose a license compatible with reused code, check naming conflicts, and find pilot users. These are implementation inputs rather than reasons to expand the initial scope.

## Delivery checklist

- [ ] Product hypothesis tested with target developers
- [x] First vertical slice implemented
- [x] Domain and local integration verification gates passed (44 source tests; base wheel 37 passed with 7 optional skips)
- [ ] Live-model behavior evaluated (offline held-out replay/scorer implemented and verified)
- [x] Clean-install example verified
- [x] Documentation and local package artifacts reviewed
- [ ] PyPI package release published
- [ ] Independent pilot completed

## Reference projects

These references are starting points for implementation-time review, not proof that the proposed differentiator is novel.

- [Mem0 reference](https://github.com/mem0ai/mem0)

## Implemented feature matrix — 0.2.0

| Phase | Delivery | Verification |
|---|---|---|
| 1. Supported claims | Explicit schemas and source authority semantics | Baseline fixture tests |
| 2. Deterministic scanner | Three claim types, source evidence, JSON-compatible CI YAML, safe reads | Scope, conflict, deletion, incomplete-source tests |
| 3. Dependency tracking | SQLite history/index/cache plus Git snapshots and hash consistency | Indexed/full equivalence, append-only history, changed/deleted evidence |
| 4. Reviewable corrections | Unified-diff proposal; explicit expected-hash apply/reject and audit | Concurrent edits preserved; tampering rejected |
| 5. Optional extraction | Versioned provider bridge, limits, review-required candidates, held-out evaluator | Eight offline replays and provider timeout/output/cost/schema tests |
| 6. Integrations | CLI, SDK, root-bound read-only MCP server, packaged wheel and CI configuration | Real subprocess MCP and installed-wheel workflow tests |

The local implementation uses standard-library-only runtime dependencies. General
YAML/matrix resolution and semver compatibility are outside its declared source
adapter contract; unsupported syntax cannot silently pass. The evaluator supports
real provider integrations, but fixture replay is not evidence of model accuracy.
See IMPLEMENTATION_STATUS.md for current verified counts and external release gates.
