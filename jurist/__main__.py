"""Command-line interface for the five jurist runtime tools."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .engine import JuristEngine


LEGACY_COMMANDS = {
    "resolve_act": "resolve",
    "legal_search": "search",
    "get_provision": "provision",
    "find_related": "related",
    "find_related_law": "related",
    "corpus_status": "corpus-status",
}


def _normalise_argv(argv: list[str]) -> list[str]:
    # Keep compatibility with the first private MVP without exposing extra
    # subcommands in --help. The public contract remains exactly five commands.
    for index, value in enumerate(argv):
        if value in LEGACY_COMMANDS:
            return argv[:index] + [LEGACY_COMMANDS[value]] + argv[index + 1 :]
    return argv


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jurist", description="Deterministic local Romanian/EU legal retrieval")
    parser.add_argument("--db", default=None, help="SQLite database path (default: data/legal.db)")
    parser.add_argument("--seed", action="store_true", default=False, help="Seed empty database with fixtures")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="resolve an act alias, acronym or number")
    resolve.add_argument("reference_pos", nargs="?")
    resolve.add_argument("--reference")
    resolve.add_argument("--jurisdiction", choices=["RO", "EU"])
    resolve.add_argument("--as-of", "--as_of", dest="as_of")
    resolve.add_argument("--json", action="store_true")

    search = sub.add_parser("search", help="search the selected legal corpus")
    search.add_argument("query_pos", nargs="?")
    search.add_argument("--query")
    search.add_argument("--corpus", choices=["legislation", "case_law", "guidance"], default="legislation")
    search.add_argument("--jurisdiction", action="append")
    search.add_argument("--domains", action="append", help="repeat or use comma-separated domain tags")
    search.add_argument("--authority-class", "--authority-classes", dest="authority_classes", action="append")
    search.add_argument("--as-of", "--as_of", dest="as_of")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--json", action="store_true")

    provision = sub.add_parser("provision", help="retrieve exact legal text")
    provision.add_argument("citation", nargs="?")
    provision.add_argument("--act")
    provision.add_argument("--article")
    provision.add_argument("--paragraph")
    provision.add_argument("--point")
    provision.add_argument("--letter")
    provision.add_argument("--context", choices=["article", "section"])
    provision.add_argument("--as-of", "--as_of", dest="as_of")
    provision.add_argument("--json", action="store_true")

    related = sub.add_parser("related", help="retrieve relations between legal acts")
    related.add_argument("identifier", nargs="?")
    related.add_argument("--act-id")
    related.add_argument("--relations", action="append", help="repeat or use comma-separated relation types")
    related.add_argument("--json", action="store_true")

    status = sub.add_parser("corpus-status", help="show corpus contents and freshness")
    status.add_argument("--json", action="store_true")
    return parser


def _split(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    return [item.strip() for value in values for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(_normalise_argv(list(sys.argv[1:] if argv is None else argv)))
    engine = JuristEngine(args.db, seed=args.seed)
    try:
        if args.command == "resolve":
            reference = args.reference or args.reference_pos
            if not reference:
                return _print_error("jurist resolve", "BAD_ARGS", "reference is required")
            output = engine.resolve_act(reference, args.jurisdiction, args.as_of)
        elif args.command == "search":
            query = args.query or args.query_pos
            if not query:
                return _print_error("jurist search", "BAD_ARGS", "query is required")
            output = engine.legal_search(query, args.corpus, args.limit, args.as_of,
                                         _split(args.jurisdiction), _split(args.domains), _split(args.authority_classes))
        elif args.command == "provision":
            if not args.citation and not args.act:
                return _print_error("jurist provision", "BAD_ARGS", "citation or --act is required")
            try:
                output = engine.get_provision(args.citation, args.context, args.as_of, args.act, args.article,
                                              args.paragraph, args.point, args.letter)
            except ValueError as exc:
                return _print_error("jurist provision", "BAD_ARGS", str(exc))
        elif args.command == "related":
            identifier = args.act_id or args.identifier
            if not identifier:
                return _print_error("jurist related", "BAD_ARGS", "act-id is required")
            output = engine.find_related(identifier, _split(args.relations))
        else:
            output = engine.corpus_status()
    finally:
        engine.close()
    print(json.dumps(output, ensure_ascii=False, sort_keys=False, default=str))
    return 0


def _print_error(tool: str, code: str, message: str) -> int:
    print(json.dumps({"tool": tool, "ok": False, "error": {"code": code, "message": message},
                      "warnings": [], "next_action": None}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
