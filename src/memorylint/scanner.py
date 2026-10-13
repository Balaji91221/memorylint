"""SDK orchestration; reports problems without modifying memory or repository files."""

from pathlib import Path
from typing import Iterable
from dataclasses import replace
import hashlib
import json
import sqlite3
import uuid

from .evidence import Repository, evidence_items
from .git import changed_paths
from .models import Evidence, Finding, ScanResult
from .parser import parse_claims
from .validators import SUPPORTED, validate
from .index import DependencyIndex


def scan_memory(
    repo: str | Path,
    memory_paths: Iterable[str] = ("AGENTS.md",),
    *,
    changed_since: str | None = None,
    revision: str | None = None,
    index_path: str | Path | None = None,
) -> ScanResult:
    """Scan explicit claims in current working-tree files; never apply corrections.

    Paths, including evidence references, are relative to repo. changed_since
    filters claims by changed memory/evidence paths; it does not read old files.
    """
    if index_path is not None:
        try:
            with DependencyIndex(index_path) as index:
                return _scan(repo, memory_paths, changed_since=changed_since, revision=revision, index=index)
        except (OSError, ValueError, sqlite3.Error) as exc:
            return ScanResult((), (f"Index unavailable: {exc}",))
    return _scan(repo, memory_paths, changed_since=changed_since, revision=revision)


def _scan(repo, memory_paths, *, changed_since=None, revision=None, index=None):
    findings: list[Finding] = []
    errors: list[str] = []
    claims = []
    skipped = 0
    cached = 0
    try:
        if changed_since is not None and revision is not None:
            raise ValueError("changed_since and revision are mutually exclusive")
        repository = Repository(repo, revision)
        paths = list(memory_paths)
        if not paths or isinstance(memory_paths, (str, bytes)):
            raise ValueError("memory_paths must be a nonempty iterable of relative paths")
        if any(not isinstance(path, str) for path in paths):
            raise ValueError("memory paths must be strings")
        paths = [str(Path(path)) for path in paths]
        changed = changed_paths(repository.root, changed_since) if changed_since is not None else None
        namespace = DependencyIndex.namespace(repository.root, paths, repository.revision)
    except (OSError, ValueError) as exc:
        return ScanResult((), (str(exc),), changed_since=changed_since)
    for path in paths:
        try:
            if not isinstance(path, str):
                raise ValueError("memory paths must be strings")
            text = repository.read(path).decode("utf-8")
            parsed, problems = parse_claims(text, path)
            claims.extend(parsed)
            errors.extend(problems)
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    seen: set[str] = set()
    for claim in claims:
        if claim.id in seen:
            errors.append(f"Duplicate claim id: {claim.id}")
            continue
        seen.add(claim.id)
        evidence: list[Evidence] = []
        try:
            # Validate boundaries even when the incremental filter would skip a claim.
            dependencies = {str(repository.path(ref, claim.scope).relative_to(repository.root)) for ref in claim.sources}
            dependencies.add(str(repository.path(claim.memory_path).relative_to(repository.root)))
            # Track lexical paths too, so changing a symlink itself triggers evaluation.
            dependencies.update(str(Path(ref)) for ref in claim.sources)
            dependencies.add(str(Path(claim.memory_path)))
            if changed is not None and not dependencies.intersection(changed):
                skipped += 1
                continue
            if claim.kind not in SUPPORTED:
                findings.append(validate(claim, ()))
                continue
            for ref in claim.sources:
                try:
                    evidence.extend(evidence_items(repository, claim, ref))
                except (OSError, ValueError) as exc:
                    evidence.append(Evidence(ref, None, "unavailable", None, str(exc)))
                    raise
            prior = index.lookup(namespace, Finding(claim, "unsupported", "", tuple(evidence))) if index else None
            if prior:
                cached += 1
                findings.append(prior)
            else:
                findings.append(validate(claim, tuple(evidence)))
        except (OSError, ValueError) as exc:
            errors.append(f"{claim.id}: {exc}")
            findings.append(Finding(claim, "unsupported", str(exc), tuple(evidence)))
    try:
        repository.verify_unchanged()
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    hashes = repository.hashes()
    snapshot = hashlib.sha256(json.dumps([repository.revision, hashes], sort_keys=True).encode()).hexdigest()
    result = ScanResult(tuple(findings), tuple(errors), skipped, changed_since,
                        revision=repository.revision, source_hashes=hashes,
                        snapshot_id=snapshot, run_id=str(uuid.uuid4()), cached_claims=cached)
    if index:
        index.record(repository.root, namespace, result)
    return result
