import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from memorylint import scan_memory


class MemoryLintTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, path, value):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value, encoding="utf-8")

    def manifest(self, value, path="package.json"):
        self.write(path, json.dumps(value))

    def memory(self, *claims):
        self.write("AGENTS.md", "# Memory\n\n```memorylint\n" + json.dumps({"version": 1, "claims": claims}) + "\n```\n")

    def claim(self, kind="package_manager", value="npm", sources=None, **extra):
        return {"id": "build", "kind": kind, "value": value,
                "sources": sources or ["package.json"], **extra}

    def scan(self, **options):
        return scan_memory(self.root, ["AGENTS.md"], **options)

    def test_matching_manager_has_source_hash_and_is_read_only(self):
        self.manifest({"packageManager": "pnpm@9.0.0"})
        self.memory(self.claim(value="pnpm"))
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.scan()
        self.assertEqual(result.exit_code, 0)
        finding = result.findings[0]
        self.assertEqual(finding.status, "valid")
        self.assertEqual(finding.evidence[0].sha256, hashlib.sha256(before["package.json"]).hexdigest())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_stale_manager_gets_proposed_correction(self):
        self.manifest({"packageManager": "pnpm@9.0.0"})
        self.write("pnpm-lock.yaml", "lockfileVersion: '9.0'")
        self.memory(self.claim(sources=["package.json", "pnpm-lock.yaml"]))
        result = self.scan()
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.findings[0].proposed_value, "pnpm")

    def test_conflicting_package_managers_never_choose_winner(self):
        self.manifest({"packageManager": "pnpm@9"})
        self.write("package-lock.json", "{}")
        self.memory(self.claim(sources=["package.json", "package-lock.json"]))
        finding = self.scan().findings[0]
        self.assertEqual(finding.status, "conflict")
        self.assertIsNone(finding.proposed_value)

    def test_exact_runtime_declarations_and_v_prefix(self):
        self.manifest({"engines": {"node": "22.0.0"}})
        self.write(".nvmrc", "v22.0.0\n")
        self.memory(self.claim("runtime", "22.0.0", ["package.json", ".nvmrc"]))
        self.assertEqual(self.scan().exit_code, 0)

    def test_runtime_range_and_pin_are_different_not_semver_evaluated(self):
        self.manifest({"engines": {"node": ">=20"}})
        self.write(".nvmrc", "22\n")
        self.memory(self.claim("runtime", ">=20", ["package.json", ".nvmrc"]))
        self.assertEqual(self.scan().findings[0].status, "conflict")

    def test_changed_script_command_and_missing_script(self):
        self.manifest({"scripts": {"test": "node --test"}})
        self.memory(self.claim("script", "jest", name="test"))
        self.assertEqual(self.scan().findings[0].proposed_value, "node --test")
        self.manifest({"scripts": {}})
        finding = self.scan().findings[0]
        self.assertEqual(finding.status, "stale_candidate")
        self.assertIsNone(finding.proposed_value)
        self.assertEqual(finding.evidence[0].selector, "scripts.test")

    def test_independent_monorepo_scopes_do_not_conflict(self):
        self.manifest({"packageManager": "npm@10"}, "apps/a/package.json")
        self.manifest({"packageManager": "pnpm@9"}, "apps/b/package.json")
        self.memory(self.claim(sources=["apps/a/package.json"], scope="apps/a"),
                    self.claim(value="pnpm", sources=["apps/b/package.json"], scope="apps/b", id="b"))
        self.assertEqual(self.scan().exit_code, 0)

    def test_missing_evidence_is_incomplete_and_never_valid(self):
        self.memory(self.claim())
        result = self.scan()
        self.assertFalse(result.complete)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.findings[0].evidence[0].selector, "unavailable")

    def test_unknown_claim_and_unknown_source_are_unsupported(self):
        self.manifest({})
        self.memory(self.claim("framework", "django"))
        self.assertEqual(self.scan().findings[0].status, "unsupported")
        self.write("README.md", "uses npm")
        self.memory(self.claim(sources=["README.md"]))
        self.assertEqual(self.scan().exit_code, 2)

    def test_plain_prose_and_malformed_json_are_reported(self):
        self.write("AGENTS.md", "Uses pnpm.")
        self.assertFalse(self.scan().complete)
        self.write("AGENTS.md", "```memorylint\n{\n```\n")
        self.assertEqual(self.scan().exit_code, 2)

    def test_duplicate_ids_and_script_without_name_rejected(self):
        self.manifest({"packageManager": "npm@10"})
        self.memory(self.claim(), self.claim())
        self.assertFalse(self.scan().complete)
        self.memory(self.claim("script", "node --test"))
        self.assertFalse(self.scan().complete)

    def test_bad_manifest_shape_reported(self):
        self.manifest({"scripts": ["test"]})
        self.memory(self.claim("script", "test", name="test"))
        self.assertEqual(self.scan().exit_code, 2)

    def test_traversal_absolute_and_scope_escape_rejected(self):
        for ref, scope in [("../package.json", "."), ("/etc/passwd", "."), ("package.json", "apps/a")]:
            with self.subTest(ref=ref):
                self.memory(self.claim(sources=[ref], scope=scope))
                result = self.scan()
                self.assertEqual(result.exit_code, 2)
                self.assertFalse(result.complete)

    def test_symlink_outside_repo_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / "package.json"
            target.write_text('{"packageManager": "npm@10"}')
            (self.root / "package.json").symlink_to(target)
            self.memory(self.claim())
            self.assertFalse(self.scan().complete)

    def test_size_limit_rejected(self):
        self.write("package.json", " " * (2 * 1024 * 1024 + 1))
        self.memory(self.claim())
        self.assertFalse(self.scan().complete)

    def test_cli_json_exit_and_source_evidence(self):
        self.manifest({"packageManager": "pnpm@9"})
        self.memory(self.claim())
        process = subprocess.run([sys.executable, "-m", "memorylint", "scan", "--repo", str(self.root), "--format", "json"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 1, process.stderr)
        data = json.loads(process.stdout)
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["findings"][0]["evidence"][0]["value"], "pnpm")

    @unittest.skipUnless(shutil.which("git"), "Git not installed")
    def test_incremental_scan_matches_affected_full_scan_and_untracked_sources(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        self.manifest({"packageManager": "npm@10", "scripts": {"test": "node --test"}})
        self.memory(self.claim(), self.claim("script", "node --test", name="test", id="script"))
        git("init")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "baseline")
        unchanged = self.scan(changed_since="HEAD")
        self.assertEqual(unchanged.skipped_claims, 2)
        self.assertEqual(unchanged.findings, ())
        self.manifest({"packageManager": "pnpm@9", "scripts": {"test": "node --test"}})
        incremental = self.scan(changed_since="HEAD")
        self.assertEqual(incremental.findings, self.scan().findings)
        self.memory(self.claim(sources=["pnpm-lock.yaml"]))
        git("add", "AGENTS.md")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "new claim")
        self.write("pnpm-lock.yaml", "lockfileVersion: '9.0'")
        self.assertEqual(self.scan(changed_since="HEAD").findings[0].status, "stale_candidate")
        self.assertEqual(self.scan(changed_since="--help").exit_code, 2)


if __name__ == "__main__":
    unittest.main()
