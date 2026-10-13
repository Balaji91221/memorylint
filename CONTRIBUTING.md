# Contributing

Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` and the held-out replay
evaluation before proposing a change. Add a regression fixture for changes to
claim semantics, path boundaries, Git snapshots, MCP protocol behavior, or review
concurrency. Verify an installed wheel as well as source imports.

Install `python3 -m pip install '.[ci]'` to include the optional ordinary-YAML tests.
A base install skips those seven tests while exercising missing-dependency handling
and JSON workflows; the CI workflow runs both installation variants.

Keep deterministic validation independent of extraction. New claim/source adapters
must retain evidence, scope checks, incomplete-result semantics, and conservative
conflict handling. Do not add network access to scans or MCP tools. Do not let model
output execute code or authorize an edit. Never commit real user memory or secrets.

Changes to report, patch, or index schemas require a version decision, documented
compatibility, and a copy-first migration test where an older stored format exists.
Leave held-out fixtures separate from examples; add new real sanitized evaluation
cases before tuning a model integration to them. Replay metrics are not model scores.

Use this repository's issues and pull requests for contributions. A public source
repository does not imply that `memorylint-local` is published on PyPI. The original
implementation is MIT licensed; reused dependencies must retain their own notices.
