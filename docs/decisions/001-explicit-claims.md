# Decision 001: explicit claims, read-only working-tree scans

Status: accepted for the first local implementation, 2026-10-13.

The original plan included SQLite dependencies, historical Git snapshots, and
review/apply workflows. The first release establishes source-backed correctness
before adding persistence or mutation. It implements roadmap phases 1–2 and a
stateless subset of phase 3.

Alternatives considered:

1. Free-form prose extraction: easier initial authoring, but would require model
   dependencies and evaluation before claims can be trusted.
2. Explicit claims plus deterministic validation: chosen; narrow semantics and
   evidence are inspectable without external services.
3. Persistent SQLite evidence graph: useful after measured repository size or
   integrations justify incremental indexing; currently adds migration and stale
   state risks without a demonstrated need.

Working-tree scans read bounded source files and hash each read. This does not
promise an atomic repository snapshot: files can change between reads. We do not
apply changes, so no optimistic write protocol is needed. Returned hashes provide
provenance, not a guarantee that a file still has the same contents later.

`--changed-since` filters explicit dependency paths from Git changes but does not
read old revisions or persist state. A full scan is the correctness baseline.
No automatic `propose`/`apply` commands, CI-source parser, arbitrary runtime
comparison, MCP integration, SQLite index, or LLM extraction is claimed complete.

SOLID consequences: parsing, I/O, and validation have different reasons to change;
the CLI depends on the SDK. Simple functions and immutable data suffice. There are
no inheritance hierarchies to justify substitution contracts. A future pluggable
evidence resolver must preserve scope, hashes, error, and completeness semantics.
