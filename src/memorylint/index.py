"""Versioned SQLite dependency cache and append-only scan/review history."""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from .models import Finding, ScanResult, finding_from_dict

SCHEMA_VERSION = 1
APPLICATION_ID = 0x4D4C494E
VALIDATOR_VERSION = "2"


def signature(finding: Finding) -> str:
    data = {"validator": VALIDATOR_VERSION, "claim": asdict(finding.claim),
            "evidence": [asdict(item) for item in finding.evidence]}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class DependencyIndex:
    def __init__(self, path: str | Path):
        self.path = Path(path).absolute()
        if self.path.is_symlink():
            raise ValueError("Index file must not be a symlink")
        self.connection = sqlite3.connect(self.path, timeout=5)
        try:
            self.connection.execute("PRAGMA foreign_keys=ON")
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            app = self.connection.execute("PRAGMA application_id").fetchone()[0]
            tables = self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if version not in {0, SCHEMA_VERSION} or app not in {0, APPLICATION_ID} or (version == 0 and tables):
                raise ValueError("Unsupported index schema; preserve the original and migrate a backup")
            if version == SCHEMA_VERSION and app != APPLICATION_ID:
                raise ValueError("This is not a MemoryLint index")
            if version == 0:
                self.connection.executescript("""
                    CREATE TABLE scans (
                        id TEXT PRIMARY KEY, repo TEXT NOT NULL, namespace TEXT NOT NULL,
                        created_at TEXT NOT NULL, revision TEXT NOT NULL, complete INTEGER NOT NULL,
                        report TEXT NOT NULL);
                    CREATE TABLE claims (
                        scan_id TEXT NOT NULL REFERENCES scans(id), claim_id TEXT NOT NULL,
                        definition TEXT NOT NULL, finding TEXT NOT NULL,
                        PRIMARY KEY(scan_id, claim_id));
                    CREATE TABLE evidence (
                        scan_id TEXT NOT NULL, claim_id TEXT NOT NULL, path TEXT NOT NULL,
                        sha256 TEXT, details TEXT NOT NULL,
                        FOREIGN KEY(scan_id, claim_id) REFERENCES claims(scan_id, claim_id));
                    CREATE TABLE current_claims (
                        namespace TEXT NOT NULL, claim_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                        finding TEXT NOT NULL, PRIMARY KEY(namespace, claim_id));
                    CREATE TABLE dependencies (
                        namespace TEXT NOT NULL, claim_id TEXT NOT NULL, path TEXT NOT NULL,
                        PRIMARY KEY(namespace, claim_id, path));
                    CREATE INDEX dependency_path ON dependencies(namespace, path);
                    CREATE TABLE reviews (
                        id TEXT PRIMARY KEY, patch_id TEXT NOT NULL, decision TEXT NOT NULL,
                        created_at TEXT NOT NULL, details TEXT NOT NULL);
                """)
                self.connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                self.connection.commit()
            self.path.chmod(0o600)
        except Exception:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    @staticmethod
    def namespace(repo: Path, memories: list[str], revision: str) -> str:
        return json.dumps([str(repo), sorted(memories), revision], separators=(",", ":"))

    def lookup(self, namespace: str, candidate: Finding) -> Finding | None:
        row = self.connection.execute(
            "SELECT finding FROM current_claims WHERE namespace=? AND claim_id=? AND fingerprint=?",
            (namespace, candidate.claim.id, signature(candidate)),
        ).fetchone()
        return finding_from_dict(json.loads(row[0])) if row else None

    def affected(self, namespace: str, changed_refs: set[str]) -> set[str]:
        result: set[str] = set()
        for ref in changed_refs:
            result.update(row[0] for row in self.connection.execute(
                "SELECT claim_id FROM dependencies WHERE namespace=? AND path=?", (namespace, ref)))
        return result

    def record(self, repo: Path, namespace: str, result: ScanResult) -> str:
        scan_id = result.run_id or str(uuid.uuid4())
        with self.connection:
            self.connection.execute("INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?, ?)", (
                scan_id, str(repo), namespace, datetime.now(timezone.utc).isoformat(),
                result.revision, int(result.complete), json.dumps(result.to_dict())))
            for finding in result.findings:
                serialized = json.dumps(asdict(finding))
                self.connection.execute("INSERT INTO claims VALUES (?, ?, ?, ?)", (
                    scan_id, finding.claim.id, json.dumps(asdict(finding.claim)), serialized))
                for item in finding.evidence:
                    self.connection.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?)", (
                        scan_id, finding.claim.id, item.path, item.sha256, json.dumps(asdict(item))))
            # Failed/filtered scans remain audit evidence but cannot poison a full-scan cache.
            if result.complete and result.changed_since is None:
                self.connection.execute("DELETE FROM current_claims WHERE namespace=?", (namespace,))
                self.connection.execute("DELETE FROM dependencies WHERE namespace=?", (namespace,))
                for finding in result.findings:
                    self.connection.execute("INSERT INTO current_claims VALUES (?, ?, ?, ?)", (
                        namespace, finding.claim.id, signature(finding), json.dumps(asdict(finding))))
                    for ref in set(finding.claim.sources) | {finding.claim.memory_path}:
                        self.connection.execute("INSERT INTO dependencies VALUES (?, ?, ?)", (
                            namespace, finding.claim.id, str(Path(ref))))
        return scan_id

    def history(self, *, claim_id: str | None = None, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("History limit must be between 1 and 1000")
        if claim_id is not None:
            rows = self.connection.execute("""SELECT s.id,s.created_at,c.finding FROM claims c
                JOIN scans s ON s.id=c.scan_id WHERE c.claim_id=? ORDER BY s.rowid DESC LIMIT ?""",
                                           (claim_id, limit)).fetchall()
            return [{"run_id": r[0], "created_at": r[1], "finding": json.loads(r[2])} for r in rows]
        rows = self.connection.execute("SELECT report FROM scans ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def record_review(self, patch_id: str, decision: str, details: dict) -> str:
        if decision not in {"prepared", "applied", "rejected", "conflict"}:
            raise ValueError("Unknown review decision")
        review_id = str(uuid.uuid4())
        with self.connection:
            self.connection.execute("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", (
                review_id, patch_id, decision, datetime.now(timezone.utc).isoformat(), json.dumps(details)))
        return review_id

    def reviews(self) -> list[dict]:
        return [{"id": r[0], "patch_id": r[1], "decision": r[2], "created_at": r[3], "details": json.loads(r[4])}
                for r in self.connection.execute("SELECT * FROM reviews ORDER BY rowid")]

    def backup(self, destination: str | Path) -> None:
        target = Path(destination)
        with target.open("xb"):
            pass
        target.chmod(0o600)
        with sqlite3.connect(target) as copy:
            self.connection.backup(copy)
