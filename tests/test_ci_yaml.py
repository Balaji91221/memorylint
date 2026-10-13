import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from memorylint import scan_memory
from memorylint.ci import load_workflow


@unittest.skipUnless(importlib.util.find_spec("yaml"), "optional CI extra not installed")
class WorkflowYamlTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workflow = self.root / ".github/workflows/ci.yml"
        self.workflow.parent.mkdir(parents=True)
        claim = {"id": "node", "kind": "runtime", "value": "20.10",
                 "sources": [".github/workflows/ci.yml"]}
        (self.root / "AGENTS.md").write_text(
            "```memorylint\n" + json.dumps({"version": 1, "claims": [claim]}) + "\n```\n")

    def scan(self, workflow):
        self.workflow.write_text(workflow)
        return scan_memory(self.root, ["AGENTS.md"])

    @staticmethod
    def workflow_with(value):
        return ("name: CI\non: [push, pull_request]\njobs:\n  test:\n"
                "    runs-on: ubuntu-latest\n    steps:\n"
                "      - uses: actions/setup-node@v4\n        with:\n"
                f"          node-version: {value}\n")

    def test_literal_workflow_preserves_unquoted_version_and_on_key(self):
        text = self.workflow_with("20.10")
        result = self.scan(text)
        self.assertEqual(result.exit_code, 0, result.errors)
        evidence = result.findings[0].evidence[0]
        self.assertEqual(evidence.value, "20.10")
        self.assertEqual(evidence.selector, "jobs.test.steps[0].with.node-version")
        parsed = load_workflow(text.encode(), "ci.yml")
        self.assertEqual(parsed["on"], ["push", "pull_request"])
        self.assertEqual(parsed["jobs"]["test"]["steps"][0]["with"]["node-version"], "20.10")

    def test_every_literal_setup_node_step_contributes_to_conflicts(self):
        text = self.workflow_with("'20.10'") + (
            "      - uses: actions/setup-node@v4\n        with:\n          node-version: '22'\n")
        finding = self.scan(text).findings[0]
        self.assertEqual(finding.status, "conflict")
        self.assertEqual([item.value for item in finding.evidence], ["20.10", "22"])

    def test_duplicate_yaml_and_json_mapping_keys_are_rejected(self):
        inputs = [self.workflow_with("'20.10'") + "          node-version: '22'\n",
                  'jobs: {}\njobs: {}\n', '{"jobs":{},"jobs":{}}']
        for text in inputs:
            with self.subTest(text=text):
                result = self.scan(text)
                self.assertEqual(result.exit_code, 2)
                self.assertIn("Duplicate workflow mapping key", result.errors[0])

    def test_python_and_custom_tags_are_rejected_without_construction(self):
        for tag in ['!!python/object/apply:os.system ["unexpected command"]', '!custom 20.10']:
            with self.subTest(tag=tag), patch("os.system") as execute:
                result = self.scan(self.workflow_with(tag))
                self.assertEqual(result.exit_code, 2)
                self.assertIn("tags are unsupported", result.errors[0])
                execute.assert_not_called()

    def test_anchors_aliases_and_merge_keys_are_rejected(self):
        for text in ["defaults: &node {node-version: '20.10'}\njobs: {}\n",
                     "jobs: *missing\n", "jobs: {test: {<<: {steps: []}}}\n"]:
            with self.subTest(text=text):
                self.assertEqual(self.scan(text).exit_code, 2)

    def test_expressions_matrices_and_file_indirection_remain_unsupported(self):
        inputs = [self.workflow_with("${{ matrix.node }}"),
                  self.workflow_with("20.10").replace(
                      "    runs-on:", "    strategy:\n      matrix:\n        os: [ubuntu-latest]\n    runs-on:"),
                  self.workflow_with("20.10") + "          node-version-file: .nvmrc\n"]
        for text in inputs:
            with self.subTest(text=text):
                self.assertEqual(self.scan(text).exit_code, 2)

    def test_multiple_documents_and_deep_nesting_fail_closed(self):
        for text in [self.workflow_with("20.10") + "---\njobs: {}\n",
                     "jobs: " + "[" * 70 + "x" + "]" * 70]:
            with self.subTest(text=text):
                self.assertEqual(self.scan(text).exit_code, 2)


class OptionalCiDependencyTests(unittest.TestCase):
    def test_missing_pyyaml_explains_optional_install(self):
        with patch("memorylint.ci.importlib.import_module", side_effect=ImportError("unavailable")):
            with self.assertRaisesRegex(ValueError, r"unsupported.*PyYAML.*install.*\.\[ci\]"):
                load_workflow(b"jobs:\n  test: {}\n", "ci.yml")

    def test_json_workflows_do_not_import_optional_dependency(self):
        with patch("memorylint.ci.importlib.import_module") as dependency:
            self.assertEqual(load_workflow(b'{"jobs":{}}', "ci.yml"), {"jobs": {}})
            dependency.assert_not_called()

    def test_base_package_works_without_site_packages(self):
        # -S removes installed PyYAML and proves imports are lazy in a real process.
        package_parent = str(Path(__import__("memorylint").__file__).resolve().parent.parent)
        code = "\n".join([
            "import sys",
            f"sys.path.insert(0, {package_parent!r})",
            "import memorylint",
            "from memorylint.ci import load_workflow",
            "assert load_workflow(b'{\"jobs\":{}}', 'ci.yml') == {'jobs': {}}",
            "try: load_workflow(b'jobs: {}', 'ci.yml')",
            "except ValueError as error: assert 'optional PyYAML' in str(error)",
            "else: raise AssertionError('unexpected YAML availability')",
        ])
        result = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
