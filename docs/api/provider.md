# Structured extraction provider protocol, version 1

A user-configured command receives one JSON object on stdin:

```json
{
  "prompt_version": "explicit-repository-claims-v1",
  "instruction": "Versioned extraction instructions",
  "markdown": "We use npm.",
  "allowed_sources": {"package.json": "{\"packageManager\":\"pnpm@9\"}"},
  "limits": {"max_input_bytes": 32768, "max_output_bytes": 65536, "max_output_tokens": 2048, "timeout_seconds": 30, "max_cost_usd": 0}
}
```

It writes one JSON object to stdout and exits successfully:

```json
{
  "version": 1,
  "claims": [{"id": "manager", "kind": "package_manager", "value": "npm", "sources": ["package.json"], "quote": "We use npm."}],
  "usage": {"output_tokens": 50, "cost_usd": 0}
}
```

Each candidate has exactly id/kind/value/sources/quote and optional scope/name.
Name is mandatory for script claims. Unsupported, ambiguous, personal, or future
statements should yield an empty claims array. A quote must be an exact substring,
and sources must come from allowed_sources. All output stays review-required.

Model integrations should use their provider's structured-output feature with this
schema, set max_output_tokens, enforce admission against max_cost_usd before
calling the provider, and report actual usage afterward. Keep provider/model/version
metadata in the bridge's own logs without raw documents or credentials. The SDK
ExtractionProvider Protocol also supports in-process integrations; those must honor
provided time limits themselves because Python cannot forcibly cancel arbitrary
in-process user code. CommandProvider supplies a process-level deadline.

No vendor-specific API or model is assumed; bundled fixture replay validates this
contract without credentials. The bridge owns authentication, pricing, and remote
network behavior. Third-party provider costs cannot be guaranteed from self-reports.
