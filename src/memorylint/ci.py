"""Strict, non-executing parsers for literal CI declarations.

JSON needs only the standard library. Optional YAML keeps scalar spelling intact
(notably ``on`` and versions such as ``20.10``), with no object constructors.
"""

import importlib
import json


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate workflow mapping key")
        result[key] = value
    return result


def load_workflow(content: bytes, ref: str):
    text = content.decode("utf-8")
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError:
        pass
    except RecursionError as exc:
        raise ValueError(f"{ref}: workflow nesting exceeds parser limits") from exc
    try:
        yaml = importlib.import_module("yaml")
    except ImportError as exc:
        raise ValueError(
            f"{ref}: regular CI YAML is unsupported without optional PyYAML; "
            "install MemoryLint with 'python -m pip install .[ci]' from its source "
            "directory, or use JSON-compatible YAML"
        ) from exc

    class StrictWorkflowLoader(yaml.BaseLoader):
        def __init__(self, stream):
            super().__init__(stream)
            self.workflow_depth = 0
            self.workflow_nodes = 0

        def compose_node(self, parent, index):
            event = self.peek_event()
            if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None) is not None:
                raise ValueError("Workflow YAML anchors and aliases are unsupported")
            if getattr(event, "tag", None) is not None:
                raise ValueError("Explicit workflow YAML tags are unsupported")
            self.workflow_depth += 1
            self.workflow_nodes += 1
            try:
                if self.workflow_depth > 64 or self.workflow_nodes > 20000:
                    raise ValueError("Workflow YAML exceeds nesting/node limits")
                return super().compose_node(parent, index)
            finally:
                self.workflow_depth -= 1

        def construct_mapping(self, node, deep=False):
            if not isinstance(node, yaml.MappingNode):
                raise ValueError("Workflow YAML requires mapping nodes")
            pairs = []
            for key_node, value_node in node.value:
                if not isinstance(key_node, yaml.ScalarNode):
                    raise ValueError("Workflow YAML mapping keys must be scalars")
                key = self.construct_object(key_node, deep=deep)
                if key == "<<":
                    raise ValueError("Workflow YAML merge keys are unsupported")
                pairs.append((key, self.construct_object(value_node, deep=deep)))
            return _unique_object(pairs)

    try:
        return yaml.load(text, Loader=StrictWorkflowLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        # Parser exception text can include unrelated source lines; keep it out
        # of reports, which only need a reason this declaration was not checked.
        raise ValueError(f"{ref}: invalid or unsupported workflow YAML") from exc
    except ValueError as exc:
        raise ValueError(f"{ref}: {exc}") from exc
