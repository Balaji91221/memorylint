"""Bounded repository reads and narrowly supported source adapters."""

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

from .models import Claim, Evidence
from .ci import load_workflow

MAX_FILE_BYTES = 2 * 1024 * 1024
LOCKFILES = {"package-lock.json": "npm", "npm-shrinkwrap.json": "npm",
             "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "bun.lock": "bun",
             "bun.lockb": "bun"}


class Repository:
    def __init__(self, root: str | Path, revision: str | None = None):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("repository root must be a directory")
        self.cache: dict[str, bytes] = {}
        self.revision = "working-tree"
        if revision is not None:
            if not revision or revision.startswith("-"):
                raise ValueError("revision must be a Git commit reference")
            top = Path(self.git("rev-parse", "--show-toplevel").decode().strip()).resolve()
            if top != self.root:
                raise ValueError("revision scans require the Git repository root")
            self.revision = self.git("rev-parse", "--verify", revision + "^{commit}").decode().strip()

    def git(self, *args: str) -> bytes:
        try:
            result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"Git snapshot failed: {exc}") from exc
        if result.returncode:
            raise ValueError("Git snapshot failed: " + result.stderr.decode("utf-8", "replace").strip())
        return result.stdout

    def path(self, ref: str, scope: str = ".") -> Path:
        relative = Path(ref)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe repository path: {ref}")
        scoped = Path(scope)
        if scoped.is_absolute() or ".." in scoped.parts:
            raise ValueError(f"unsafe scope: {scope}")
        if self.revision != "working-tree":
            # Git paths are lexical and cannot depend on current working-tree symlinks.
            boundary = self.root / scoped
            candidate = self.root / relative
        else:
            boundary = (self.root / scoped).resolve()
            candidate = (self.root / relative).resolve()
        if not boundary.is_relative_to(self.root) or not candidate.is_relative_to(boundary):
            raise ValueError(f"path escapes repository or claim scope: {ref}")
        return candidate

    def read(self, ref: str, scope: str = ".") -> bytes:
        path = self.path(ref, scope)
        normalized = Path(ref).as_posix()
        if normalized not in self.cache:
            self.cache[normalized] = self._read_current(normalized, path)
        return self.cache[normalized]

    def _read_current(self, ref: str, path: Path) -> bytes:
        if self.revision != "working-tree":
            entries = self.git("ls-tree", "-z", self.revision, "--", ref).split(b"\0")
            exact = [item for item in entries if item and item.split(b"\t", 1)[1].decode("utf-8") == ref]
            if len(exact) != 1 or exact[0].split(b" ", 1)[0] not in {b"100644", b"100755"}:
                raise ValueError(f"snapshot evidence missing or not a regular blob: {ref}")
            object_id = exact[0].split(b"\t", 1)[0].split()[-1].decode("ascii")
            size = int(self.git("cat-file", "-s", object_id))
            if size > MAX_FILE_BYTES:
                raise ValueError(f"file exceeds {MAX_FILE_BYTES} byte limit: {ref}")
            return self.git("cat-file", "blob", object_id)
        if not path.is_file():
            raise ValueError(f"evidence is missing or is not a regular file: {ref}")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"file exceeds {MAX_FILE_BYTES} byte limit: {ref}")
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError(f"not a regular file: {ref}")
            content = handle.read(MAX_FILE_BYTES + 1)
            after = os.fstat(handle.fileno())
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError(f"file changed while being read: {ref}")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError(f"file exceeds {MAX_FILE_BYTES} byte limit: {ref}")
        return content

    def verify_unchanged(self) -> None:
        if self.revision == "working-tree":
            for ref, original in self.cache.items():
                if self._read_current(ref, self.path(ref)) != original:
                    raise ValueError(f"source changed during scan: {ref}; retry or use --revision")

    def hashes(self) -> dict[str, str]:
        return {ref: hashlib.sha256(content).hexdigest() for ref, content in sorted(self.cache.items())}


def extract_evidence(repo: Repository, claim: Claim, ref: str) -> Evidence:
    content = repo.read(ref, claim.scope)
    digest = hashlib.sha256(content).hexdigest()
    basename = Path(ref).name
    value = None
    selector = "unsupported_source"
    excerpt = "No supported field in this source for this claim type."
    if claim.kind == "package_manager" and basename in LOCKFILES:
        value = LOCKFILES[basename]
        selector = "lockfile_presence"
        excerpt = f"{basename} exists ({len(content)} bytes); contents are not executed."
    elif basename == "package.json":
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{ref}: package.json root must be an object")
        if claim.kind == "package_manager":
            selector = "packageManager"
            raw = data.get(selector)
            if raw is not None:
                if not isinstance(raw, str) or raw.split("@", 1)[0] not in {"npm", "pnpm", "yarn", "bun"}:
                    raise ValueError(f"{ref}: unsupported packageManager declaration")
                value = raw.split("@", 1)[0]
            excerpt = f"packageManager = {json.dumps(raw)}"
        elif claim.kind == "runtime":
            selector = "engines.node"
            engines = data.get("engines", {})
            if not isinstance(engines, dict):
                raise ValueError(f"{ref}: engines must be an object")
            value = engines.get("node")
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{ref}: engines.node must be a string")
            excerpt = f"engines.node = {json.dumps(value)}"
        elif claim.kind == "script":
            selector = f"scripts.{claim.name}"
            scripts = data.get("scripts", {})
            if not isinstance(scripts, dict):
                raise ValueError(f"{ref}: scripts must be an object")
            value = scripts.get(claim.name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{ref}: {selector} must be a string")
            excerpt = f"{selector} = {json.dumps(value)}"
    elif claim.kind == "runtime" and basename in {".nvmrc", ".node-version"}:
        selector = "declared_node_runtime"
        value = content.decode("utf-8").strip()
        if not value or "\n" in value:
            raise ValueError(f"{ref}: expected one nonempty runtime declaration")
        excerpt = value
    return Evidence(ref, digest, selector, value, excerpt, repo.revision)


def evidence_items(repo: Repository, claim: Claim, ref: str) -> tuple[Evidence, ...]:
    """Extract literal GitHub Actions Node declarations using a strict parser."""
    path = Path(ref)
    if claim.kind != "runtime" or path.suffix not in {".yml", ".yaml"} or ".github/workflows/" not in path.as_posix():
        return (extract_evidence(repo, claim, ref),)
    content = repo.read(ref, claim.scope)
    digest = hashlib.sha256(content).hexdigest()
    workflow = load_workflow(content, ref)
    jobs = workflow.get("jobs") if isinstance(workflow, dict) else None
    if not isinstance(jobs, dict):
        raise ValueError(f"{ref}: workflow jobs must be an object")
    items = []
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            raise ValueError(f"{ref}: invalid workflow job")
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError(f"{ref}: steps must be an array")
        for position, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"{ref}: invalid workflow step")
            uses = step.get("uses", "")
            if not isinstance(uses, str) or not uses.startswith("actions/setup-node@"):
                continue
            strategy = job.get("strategy", {})
            if not isinstance(strategy, dict) or "matrix" in strategy:
                raise ValueError(f"{ref}: setup-node matrix jobs are unsupported")
            options = step.get("with", {})
            value = options.get("node-version") if isinstance(options, dict) else None
            if (not isinstance(value, str) or not value.strip() or "${{" in value or
                    "\n" in value or "node-version-file" in options):
                raise ValueError(f"{ref}: setup-node needs a literal node-version string; matrices/file indirection are unsupported")
            selector = f"jobs.{job_name}.steps[{position}].with.node-version"
            items.append(Evidence(ref, digest, selector, value, f"{selector} = {json.dumps(value)}", repo.revision))
    if not items:
        raise ValueError(f"{ref}: no supported setup-node declaration found")
    return tuple(items)
