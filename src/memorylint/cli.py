"""CLI adapters. Mutations are available only through explicit index/apply commands."""

import argparse
import json
from pathlib import Path
import sqlite3

from .scanner import scan_memory


def display(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)[1:-1]


def dump(data):
    print(json.dumps(data, indent=2, ensure_ascii=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-backed repository memory checking.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("scan", "check"):
        command = commands.add_parser(name)
        command.add_argument("--repo", default=".")
        command.add_argument("--memory", action="append")
        command.add_argument("--changed-since")
        command.add_argument("--revision", help="Immutable Git commit snapshot")
        command.add_argument("--index", help="Explicitly persist SQLite evidence/history and reuse unchanged findings")
        command.add_argument("--format", choices=("text", "json"), default="text")
    propose = commands.add_parser("propose", help="Create a reviewable JSON patch; never apply it")
    propose.add_argument("--repo", default=".")
    propose.add_argument("--memory", action="append")
    propose.add_argument("--claim", "--finding", required=True, dest="claim")
    propose.add_argument("--output", help="Create a new patch file exclusively; default prints JSON")
    apply = commands.add_parser("apply", help="Explicitly apply a reviewed patch if hashes still match")
    apply.add_argument("--repo", default=".")
    apply.add_argument("--patch", required=True)
    apply.add_argument("--index", required=True, help="SQLite audit index")
    apply.add_argument("--expected-hash")
    history = commands.add_parser("history")
    history.add_argument("--index", required=True)
    history.add_argument("--claim")
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--reviews", action="store_true")
    backup = commands.add_parser("backup-index")
    backup.add_argument("--index", required=True)
    backup.add_argument("--output", required=True)
    reject = commands.add_parser("reject")
    reject.add_argument("--index", required=True)
    reject.add_argument("--patch", required=True)
    extraction = commands.add_parser("extract", help="Generate review-required candidates; never modify memory")
    extraction.add_argument("--repo", default=".")
    extraction.add_argument("--memory", default="AGENTS.md")
    extraction.add_argument("--source", required=True, action="append")
    extraction.add_argument("--timeout", type=float, default=30)
    extraction.add_argument("--max-cost-usd", type=float, default=0)
    extraction.add_argument("--max-output-tokens", type=int, default=2048)
    providers = extraction.add_mutually_exclusive_group(required=True)
    providers.add_argument("--response", help="Replay a saved structured provider response")
    providers.add_argument("--provider-command", nargs=argparse.REMAINDER, help="User-selected provider argv; must be last")
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--dataset", required=True)
    server = commands.add_parser("serve", help="Read-only, root-bound MCP stdio server")
    server.add_argument("--repo", default=".")
    server.add_argument("--memory", action="append")
    args = parser.parse_args(argv)
    try:
        if args.command in {"scan", "check"}:
            result = scan_memory(args.repo, args.memory or ["AGENTS.md"], changed_since=args.changed_since,
                                 revision=args.revision, index_path=args.index)
            if args.format == "json":
                dump(result.to_dict())
            else:
                for finding in result.findings:
                    claim = finding.claim
                    print(f"{finding.status.upper()} {display(claim.id)} ({display(claim.memory_path)}:{claim.memory_line})")
                    print(f"  {display(finding.explanation)}")
                    for item in finding.evidence:
                        print(f"  {display(item.path)} [{display(item.selector)}]: {json.dumps(item.excerpt, ensure_ascii=True)}")
                    if finding.proposed_value is not None:
                        print(f"  Proposed value (not applied): {json.dumps(finding.proposed_value)}")
                for error in result.errors:
                    print(f"ERROR {json.dumps(error, ensure_ascii=True)}")
                print(f"{len(result.findings)} checked; {result.cached_claims} cached; {result.skipped_claims} skipped; exit {result.exit_code}")
            return result.exit_code
        if args.command == "serve":
            from .mcp import serve
            return serve(args.repo, args.memory or ["AGENTS.md"])
        if args.command == "propose":
            from .review import propose_patch
            patch = propose_patch(args.repo, args.claim, args.memory or ["AGENTS.md"])
            if args.output:
                with Path(args.output).open("x", encoding="utf-8") as handle:
                    handle.write(json.dumps(patch.to_dict(), indent=2) + "\n")
                dump({"patch_path": args.output, "patch_id": patch.patch_id, "applied": False})
            else:
                dump(patch.to_dict())
            return 0
        if args.command in {"apply", "reject"}:
            from .review import ProposedPatch, apply_patch
            patch = ProposedPatch.from_dict(json.loads(Path(args.patch).read_text()))
            if args.command == "apply":
                dump(apply_patch(args.repo, patch, index_path=args.index, expected_hash=args.expected_hash))
            else:
                from .index import DependencyIndex
                with DependencyIndex(args.index) as index:
                    dump({"review_id": index.record_review(patch.patch_id, "rejected", {"memory_path": patch.memory_path}), "decision": "rejected"})
            return 0
        if args.command in {"history", "backup-index"}:
            from .index import DependencyIndex
            if not Path(args.index).is_file():
                raise ValueError("Index does not exist")
            with DependencyIndex(args.index) as index:
                if args.command == "history":
                    dump(index.reviews() if args.reviews else index.history(claim_id=args.claim, limit=args.limit))
                else:
                    index.backup(args.output)
                    dump({"backup": args.output})
            return 0
        if args.command == "extract":
            from .extraction import CommandProvider, FixtureProvider, ExtractionLimits, extract_claims
            provider = FixtureProvider(json.loads(Path(args.response).read_text())) if args.response else CommandProvider(args.provider_command)
            limits = ExtractionLimits(timeout_seconds=args.timeout, max_cost_usd=args.max_cost_usd,
                                      max_output_tokens=args.max_output_tokens)
            dump(extract_claims(args.repo, args.memory, args.source, provider, limits=limits))
            return 0
        if args.command == "evaluate":
            from .evaluation import evaluate_extraction
            result = evaluate_extraction(args.dataset)
            dump(result)
            return 1 if result["invalid_runs"] or result["counts"]["false_positive"] or result["counts"]["false_negative"] or result["counts"]["false_stale_flags"] else 0
        raise ValueError("Unknown command")
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"ERROR {display(str(exc))}", file=__import__("sys").stderr)
        return 2
