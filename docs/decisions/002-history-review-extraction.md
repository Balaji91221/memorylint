# Decision 002: complete the local workflow without making model output authoritative

Accepted 2026-10-13. Supersedes the phase deferrals in decision 001.

SQLite now persists append-only scans, claim definitions, evidence, and reviews.
The replaceable current cache uses claim/evidence/validator-version fingerprints;
a full indexed result includes cached findings rather than hiding them. Failed and
Git-filtered scans remain audit history without replacing the complete cache.

Working-tree file contents are cached and verified at completion. This detects
observed edits but does not claim an atomic cross-file filesystem snapshot. A Git
commit resolves once and provides an immutable snapshot via regular blobs.

Proposals are deterministic and reviewable. Explicit apply checks both memory and
evidence hashes, recreates the proposal, verifies the diff, records preparation,
and replaces only the selected memory file. The local lock serializes cooperating
writers; immutable hashes and last-moment checks reject observed external edits.
No automatic background editing or write-capable MCP tool exists.

Optional extraction is a narrow provider protocol. Command bridges are bounded
by time/output and receive token/cost budgets; admission and remote billing remain
the provider's responsibility. Candidate quotations and paths are validated, then
the deterministic engine evaluates them. Review remains mandatory. Replay evals
exercise scoring and contracts, not real-model accuracy.

The built-in CI parser accepts JSON-compatible YAML and literal setup-node values
using the standard library. The optional `ci` extra adds PyYAML 6.x for ordinary
workflow YAML. Its BaseLoader-derived parser preserves scalar spelling and has no
object constructors; it rejects duplicate keys, explicit tags, anchors, aliases,
merge keys, multiple documents, and excessive nesting/node counts. Matrices,
expressions, file indirection, and semantic version compatibility remain out of
scope. Missing PyYAML produces an explicit unsupported result without affecting
base-package imports or JSON evidence.
