# Security

This is a local development release. Scans are read-only. Index writes, provider
commands, and patch application require explicit caller configuration. The MCP
surface is read-only and bound to one repository and configured memory paths.

Repository and model text are untrusted data. Paths are checked against repository
and claim scope; files and protocol frames are bounded. These checks are not an OS
sandbox against a hostile process concurrently replacing directories. Use an
immutable Git revision for reproducible inspection, and isolate untrusted provider
commands with your platform's process/container controls. Do not expose the stdio
server as an unauthenticated network endpoint.

The optional YAML CI parser uses PyYAML's BaseLoader with no object constructors.
Explicit tags, aliases/anchors, merge keys, duplicate mappings, and multi-document
streams are rejected. Parsing is bounded by the repository's 2 MiB file limit plus
64 nested nodes and 20,000 total nodes. It reads declarations only; workflow steps
are never executed. The base installation needs no YAML dependency.

Memory, patch files, and the SQLite index can contain source excerpts. Keep them
private, apply repository access controls, and delete the index plus its SQLite
sidecar files when removing local history. Provider bridges may transmit selected
source text externally; inspect/configure them before use. Credentials should be
provided through the chosen provider's environment, not source files or reports.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/Balaji91221/memorylint/security/advisories/new) to contact the maintainers. Include the affected version, a sanitized
reproduction, and the expected and observed behavior. Do not post secrets,
credentials, or sensitive exploit details in public issues.

Security fixes target the latest development release (currently 0.2.0).
Older releases have no maintenance guarantee. No independent security
audit or response-time guarantee is claimed.
