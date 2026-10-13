# Saved repository memory

This demonstration deliberately contains two outdated facts. MemoryLint reads
only the explicit block below; ordinary prose is not asserted as true.

```memorylint
{
  "version": 1,
  "claims": [
    {
      "id": "package-manager",
      "kind": "package_manager",
      "value": "npm",
      "sources": ["package.json", "pnpm-lock.yaml"]
    },
    {
      "id": "node-runtime",
      "kind": "runtime",
      "value": "22.0.0",
      "sources": ["package.json", ".nvmrc"]
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
