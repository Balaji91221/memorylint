"""Parse only explicit, schema-checked memorylint fences, never execute Markdown."""

import json
import re

from .models import Claim

FENCE = re.compile(r"^```memorylint[ \t]*\r?\n(.*?)^```[ \t]*$", re.M | re.S)


def parse_claims(text: str, path: str) -> tuple[list[Claim], list[str]]:
    claims: list[Claim] = []
    errors: list[str] = []
    blocks = list(FENCE.finditer(text))
    openings = len(re.findall(r"^```memorylint[ \t]*$", text, re.M))
    if not blocks:
        return [], [f"{path}: no complete memorylint JSON fence found; prose is unsupported"]
    if len(blocks) != openings:
        errors.append(f"{path}: unmatched memorylint fence")
    for block in blocks:
        line = text.count("\n", 0, block.start()) + 1
        prefix = f"{path}:{line}"
        try:
            data = json.loads(block.group(1))
            if not isinstance(data, dict) or set(data) != {"version", "claims"}:
                raise ValueError("expected only version and claims fields")
            if type(data["version"]) is not int or data["version"] != 1:
                raise ValueError("unsupported schema version (expected 1)")
            if not isinstance(data["claims"], list) or not data["claims"]:
                raise ValueError("claims must be a nonempty array")
            if len(data["claims"]) > 1000:
                raise ValueError("a memory fence supports at most 1000 claims")
            for raw in data["claims"]:
                if not isinstance(raw, dict):
                    raise ValueError("each claim must be an object")
                allowed = {"id", "kind", "value", "sources", "scope", "name"}
                if set(raw) - allowed:
                    raise ValueError(f"unknown claim fields: {sorted(set(raw) - allowed)}")
                for key in ("id", "kind", "value"):
                    if not isinstance(raw.get(key), str) or not raw[key].strip():
                        raise ValueError(f"claim {key} must be a nonempty string")
                sources = raw.get("sources")
                if not isinstance(sources, list) or not sources or any(
                    not isinstance(s, str) or not s.strip() for s in sources
                ):
                    raise ValueError("sources must be a nonempty array of paths")
                if len(sources) > 100:
                    raise ValueError("a claim supports at most 100 evidence paths")
                scope = raw.get("scope", ".")
                if not isinstance(scope, str) or not scope:
                    raise ValueError("scope must be a nonempty relative directory")
                name = raw.get("name")
                if name is not None and (not isinstance(name, str) or not name.strip()):
                    raise ValueError("name must be a nonempty string")
                if raw["kind"] == "script" and name is None:
                    raise ValueError("script claims require name")
                claims.append(Claim(
                    id=raw["id"], kind=raw["kind"], value=raw["value"],
                    sources=tuple(sources), memory_path=path, memory_line=line,
                    scope=scope, name=name,
                ))
        except (ValueError, TypeError) as exc:
            errors.append(f"{prefix}: {exc}")
    return claims, errors
