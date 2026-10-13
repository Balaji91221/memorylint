"""Read-only Git change detection for repository-root working tree scans."""

import subprocess
from pathlib import Path


def changed_paths(root: Path, revision: str) -> set[str]:
    def git(*args: str) -> bytes:
        try:
            result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"Git change detection failed: {exc}") from exc
        if result.returncode:
            raise ValueError("Git change detection failed: " + result.stderr.decode("utf-8", "replace").strip())
        return result.stdout
    if not revision or revision.startswith("-"):
        raise ValueError("changed-since must be a Git commit reference, not an option")
    top = Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve()
    if top != root:
        raise ValueError("changed-since requires --repo to be the Git repository root")
    commit = git("rev-parse", "--verify", revision + "^{commit}").decode().strip()
    paths = git("diff", "--no-ext-diff", "--no-textconv", "--name-only", "--no-renames", "-z", commit, "--")
    paths += git("ls-files", "--others", "--exclude-standard", "-z")
    return {p.decode("utf-8", "surrogateescape") for p in paths.split(b"\0") if p}
