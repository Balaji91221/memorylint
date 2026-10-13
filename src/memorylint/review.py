"""Reviewable patches and explicit, optimistic-concurrency guarded application."""

from dataclasses import dataclass, asdict
import difflib
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .evidence import Repository
from .index import DependencyIndex
from .parser import FENCE
from .scanner import scan_memory


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ProposedPatch:
    schema_version: int
    patch_id: str
    claim_id: str
    memory_path: str
    expected_hash: str
    expected_sources: dict[str, str]
    old_value: str
    new_value: str
    diff: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid patch schema")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported patch version")
        if any(not isinstance(data[key], str) or not data[key] for key in (
            "patch_id", "claim_id", "memory_path", "expected_hash", "old_value", "new_value", "diff")):
            raise ValueError("Invalid patch fields")
        sources = data["expected_sources"]
        if not isinstance(sources, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in sources.items()):
            raise ValueError("Invalid patch source hashes")
        return cls(**data)


def _replacement(text: str, claim_id: str, old_value: str, new_value: str) -> str:
    matches = []
    for block in FENCE.finditer(text):
        data = json.loads(block.group(1))
        for claim in data["claims"]:
            if claim["id"] == claim_id:
                if claim["value"] != old_value:
                    raise ValueError("Claim value changed since proposal")
                claim["value"] = new_value
                matches.append((block.start(1), block.end(1), json.dumps(data, indent=2, ensure_ascii=False) + "\n"))
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching claim")
    start, end, replacement = matches[0]
    return text[:start] + replacement + text[end:]


def propose_patch(repo: str | Path, claim_id: str, memory_paths=("AGENTS.md",)) -> ProposedPatch:
    result = scan_memory(repo, memory_paths)
    if not result.complete:
        raise ValueError("Cannot propose from incomplete evidence: " + "; ".join(result.errors))
    findings = [f for f in result.findings if f.claim.id == claim_id]
    if len(findings) != 1 or findings[0].status != "stale_candidate" or findings[0].proposed_value is None:
        raise ValueError("Claim has no unambiguous replacement; resolve conflicts or missing declarations manually")
    finding = findings[0]
    repository = Repository(repo)
    original = repository.read(finding.claim.memory_path)
    if sha(original) != result.source_hashes[finding.claim.memory_path]:
        raise ValueError("Memory changed during proposal")
    text = original.decode("utf-8")
    updated = _replacement(text, claim_id, finding.claim.value, finding.proposed_value)
    diff = "".join(difflib.unified_diff(text.splitlines(keepends=True), updated.splitlines(keepends=True),
                                     fromfile=finding.claim.memory_path, tofile=finding.claim.memory_path))
    identity = sha(json.dumps([claim_id, result.source_hashes, finding.proposed_value], sort_keys=True).encode())
    return ProposedPatch(1, identity, claim_id, finding.claim.memory_path, sha(original),
                         result.source_hashes, finding.claim.value, finding.proposed_value, diff)


def apply_patch(repo: str | Path, patch: ProposedPatch, *, index_path: str | Path,
                expected_hash: str | None = None) -> dict:
    """Apply only a still-valid deterministic proposal. Requires an explicit audit index.

    A lock serializes MemoryLint writers; rechecks reject observed external edits.
    This is optimistic concurrency, not an OS-level CAS against hostile writers.
    """
    repository = Repository(repo)
    destination = repository.path(patch.memory_path)
    # Memory edits use lexical regular paths, not symlinks or hardlinked aliases.
    lexical = repository.root / patch.memory_path
    if lexical != destination or lexical.is_symlink() or destination.stat().st_nlink != 1:
        raise ValueError("Apply requires a regular, non-symlinked, unaliased memory path")
    lock_path = repository.root / ".memorylint-apply.lock"
    lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    temporary: str | None = None
    try:
        with DependencyIndex(index_path) as index:
            try:
                original = repository.read(patch.memory_path)
                if sha(original) != patch.expected_hash or (expected_hash is not None and expected_hash != patch.expected_hash):
                    raise ValueError("Memory hash conflict; create and review a new proposal")
                for ref, expected in patch.expected_sources.items():
                    if sha(repository.read(ref)) != expected:
                        raise ValueError(f"Evidence hash conflict: {ref}; create and review a new proposal")
                # Never trust a patch file's replacement text or diff as executable authority.
                current = propose_patch(repo, patch.claim_id, [patch.memory_path])
                if current.old_value != patch.old_value or current.new_value != patch.new_value:
                    raise ValueError("Proposal no longer matches current deterministic evidence")
                if any(patch.expected_sources.get(ref) != digest for ref, digest in current.expected_sources.items()):
                    raise ValueError("Patch is missing current source hashes or its evidence changed")
                updated = _replacement(original.decode("utf-8"), patch.claim_id, patch.old_value, patch.new_value).encode("utf-8")
                expected_diff = "".join(difflib.unified_diff(original.decode().splitlines(keepends=True),
                                                           updated.decode().splitlines(keepends=True),
                                                           fromfile=patch.memory_path, tofile=patch.memory_path))
                if expected_diff != patch.diff:
                    raise ValueError("Patch diff was altered; re-propose before applying")
                prepared = {"memory_path": patch.memory_path, "original_hash": patch.expected_hash,
                            "new_hash": sha(updated), "source_hashes": patch.expected_sources}
                index.record_review(patch.patch_id, "prepared", prepared)
                with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".memorylint-", delete=False) as handle:
                    temporary = handle.name
                    os.fchmod(handle.fileno(), destination.stat().st_mode & 0o777)
                    handle.write(updated)
                    handle.flush()
                    os.fsync(handle.fileno())
                repository.verify_unchanged()
                os.replace(temporary, destination)
                temporary = None
                review_id = index.record_review(patch.patch_id, "applied", prepared)
                return {"decision": "applied", "review_id": review_id, **prepared}
            except (OSError, ValueError) as exc:
                index.record_review(patch.patch_id, "conflict", {"message": str(exc), "memory_path": patch.memory_path})
                raise
    finally:
        os.close(lock_fd)
        lock_path.unlink()
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
