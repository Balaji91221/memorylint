# MemoryLint

Keep an assistant's repository memory aligned with the code.

MemoryLint checks explicit claims in Markdown against repository evidence: the package manager, declared Node version and package.json scripts. Findings include source paths, hashes and selectors. Corrections are separate, reviewable operations.

[Source](https://github.com/Balaji91221/memorylint) · [Usage guide](https://github.com/Balaji91221/memorylint/blob/main/docs/usage.md) · [Architecture](https://github.com/Balaji91221/memorylint/blob/main/docs/architecture.md) · [Issues](https://github.com/Balaji91221/memorylint/issues)

## Install

Requires Python 3.10+. The base runtime has no third-party dependencies or model-account requirement.

```bash
python -m pip install memorylint
memorylint --help
```

For ordinary GitHub Actions YAML parsing:

```bash
python -m pip install 'memorylint[ci]'
```

The extra installs PyYAML 6.x. JSON-compatible workflows work without it. Git is needed only for revision/filter operations.

## A small SDK example

This creates a disposable repository with a saved npm claim and current pnpm evidence. It does not execute package scripts or modify an existing repository.

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from memorylint import scan_memory

with TemporaryDirectory() as directory:
    repo = Path(directory)
    (repo / "package.json").write_text('{"packageManager":"pnpm@10.0.0"}')
    claim = {"id": "manager", "kind": "package_manager", "value": "npm",
             "sources": ["package.json"]}
    memory = {"version": 1, "claims": [claim]}
    (repo / "AGENTS.md").write_text("```memorylint\n" + json.dumps(memory) + "\n```\n")
    result = scan_memory(repo)
    print(result.findings[0].status)          # stale_candidate
    print(result.findings[0].proposed_value)  # pnpm
```

For your own explicit claims:

```bash
memorylint scan --repo /path/to/repository --memory AGENTS.md
```

Exit 0 means evaluated claims are valid; exit 1 means stale/conflicting claims need review; exit 2 means an unsupported or incomplete check. A scan is read-only unless an optional history index is requested.

## Integrations and evidence

- Python SDK for scans, proposals and explicitly applied corrections.
- CLI for snapshot scans, SQLite history, review and extraction workflows.
- Read-only MCP stdio tools: `memorylint_scan` and `memorylint_explain`.
- Optional extraction-provider protocol for review-required candidates; an LLM never authorizes a memory edit.

![MemoryLint local fixture output](https://raw.githubusercontent.com/Balaji91221/memorylint/main/docs/assets/demo.png)

This image shows an authored local fixture, not a live-model benchmark. Examples, tests and documentation are available in the source distribution and GitHub repository; the wheel installs the library and CLI.

## Boundaries

Only explicit supported claims and their declared sources are checked. Runtime declarations are compared as text, not semver satisfaction or installed-interpreter checks. Missing evidence cannot establish validity. Apply operations use optimistic hash checks and a review audit; arbitrary prose is not automatically verified memory.

See [full usage](https://github.com/Balaji91221/memorylint/blob/main/docs/usage.md), [recorded verification](https://github.com/Balaji91221/memorylint/blob/main/IMPLEMENTATION_STATUS.md), [security reporting](https://github.com/Balaji91221/memorylint/blob/main/SECURITY.md), and [release notes](https://github.com/Balaji91221/memorylint/blob/main/CHANGELOG.md).

Version 0.2.0 is a development release. Original code is [MIT licensed](https://github.com/Balaji91221/memorylint/blob/main/LICENSE). Independent pilots and live-model quality evaluation are separate from package availability.
