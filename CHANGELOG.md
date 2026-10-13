# Changelog

## 0.2.0 — 2026-10-13

- Added SQLite dependency cache, append-only source/claim history, review audit, and backups.
- Added immutable Git revision reads and working-tree consistency verification.
- Added reviewable JSON/unified-diff proposals and explicit hash-guarded apply/reject.
- Added optional structured extraction providers, budgets, and held-out replay scoring.
- Added read-only MCP stdio scan/explain tools with startup-bound paths.
- Added literal setup-node evidence from JSON-compatible GitHub workflows and an
  optional strict PyYAML adapter for ordinary YAML (`pip install 'memorylint[ci]'`).
- Report schema is now 2; Markdown claims, patch schema, and SQLite schema are 1.
- Added installed-wheel checks and CI configuration.
- Prepared public `memorylint` distributions with SPDX license metadata, a PyPI description and complete authored source-distribution fixtures/docs.

## 0.1.0 — local build

- Introduced deterministic explicit claim scanning, evidence, Git changed-path
  filtering, Python SDK, CLI, fixtures, and focused tests.
