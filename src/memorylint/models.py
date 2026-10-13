"""Immutable input and report contracts; JSON output is schema-versioned."""

from dataclasses import asdict, dataclass, field
from typing import Literal

Status = Literal["valid", "stale_candidate", "conflict", "unsupported"]


@dataclass(frozen=True)
class Claim:
    id: str
    kind: str
    value: str
    sources: tuple[str, ...]
    memory_path: str
    memory_line: int
    scope: str = "."
    name: str | None = None


@dataclass(frozen=True)
class Evidence:
    path: str
    sha256: str | None
    selector: str
    value: str | None
    excerpt: str
    revision: str = "working-tree"


@dataclass(frozen=True)
class Finding:
    claim: Claim
    status: Status
    explanation: str
    evidence: tuple[Evidence, ...]
    proposed_value: str | None = None


@dataclass(frozen=True)
class ScanResult:
    findings: tuple[Finding, ...]
    errors: tuple[str, ...]
    skipped_claims: int = 0
    changed_since: str | None = None
    schema_version: int = 2
    revision: str = "working-tree"
    source_hashes: dict[str, str] = field(default_factory=dict)
    snapshot_id: str | None = None
    run_id: str | None = None
    cached_claims: int = 0

    @property
    def complete(self) -> bool:
        return not self.errors

    @property
    def exit_code(self) -> int:
        # Unsupported claims are unresolved checks, never silent passes.
        if self.errors or any(f.status == "unsupported" for f in self.findings):
            return 2
        return 1 if any(f.status != "valid" for f in self.findings) else 0

    def to_dict(self) -> dict:
        result = asdict(self)
        result["complete"] = self.complete
        result["exit_code"] = self.exit_code
        return result


def finding_from_dict(data: dict) -> Finding:
    claim = dict(data["claim"])
    claim["sources"] = tuple(claim["sources"])
    return Finding(Claim(**claim), data["status"], data["explanation"],
                   tuple(Evidence(**item) for item in data["evidence"]), data.get("proposed_value"))
