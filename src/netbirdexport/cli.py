"""Command line entry point."""

import argparse
import datetime
import json
import os
import sys

from . import __version__
from .core import (
    DEFAULT_RESOURCES,
    DEFAULT_URL,
    RESOURCES,
    ExportError,
    auth_header,
    export,
    flatten,
    http_fetch,
    to_csv,
    to_json,
)

TOKEN_ENV = "NETBIRD_TOKEN"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="netbirdexport",
        description=(
            "Export a NetBird account inventory to CSV and JSON in one command. "
            "The token is read from the %s environment variable and is never "
            "accepted as an argument, so it does not appear in the argument list of "
            "the running process. It is still in that process's environment, and "
            "typing it at a prompt puts it in your shell history." % TOKEN_ENV
        ),
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="management API base URL (default: %s)" % DEFAULT_URL,
    )
    parser.add_argument(
        "--out",
        default="netbird-export",
        help="directory to write into, created if missing (default: netbird-export)",
    )
    parser.add_argument(
        "--resources",
        default=",".join(DEFAULT_RESOURCES),
        help=(
            "comma separated list, in output order (default: %s; available: %s)"
            % (",".join(DEFAULT_RESOURCES), ",".join(sorted(RESOURCES)))
        ),
    )
    parser.add_argument(
        "--format",
        default="csv,json",
        help="comma separated, csv and json (default: csv,json)",
    )
    parser.add_argument(
        "--bearer",
        action="store_true",
        help="send the token as Bearer instead of Token, for an OAuth access token",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def parse_list(raw, allowed, label):
    names = [one.strip() for one in raw.split(",") if one.strip()]
    if not names:
        raise ExportError("--%s got an empty list." % label)
    unknown = [one for one in names if one not in allowed]
    if unknown:
        raise ExportError(
            "unknown %s: %s. Available: %s."
            % (label, ", ".join(unknown), ", ".join(sorted(allowed)))
        )
    ordered = []
    for one in names:
        if one not in ordered:
            ordered.append(one)
    return ordered


def render_report(url, out, written, dropped):
    """The exact text the tool prints on success.

    Kept free of anything that changes between two identical runs, so that the
    sample in the README can be checked character by character.
    """
    lines = [
        "netbirdexport " + __version__,
        "source  " + url,
        "output  " + out,
        "",
    ]
    head = ("resource", "rows", "files")
    rows = [(name, str(count), ", ".join(files)) for name, count, files in written]
    first = max([len(head[0])] + [len(row[0]) for row in rows])
    second = max([len(head[1])] + [len(row[1]) for row in rows])
    lines.append("%-*s  %*s  %s" % (first, head[0], second, head[1], head[2]))
    for name, count, files in rows:
        lines.append("%-*s  %*s  %s" % (first, name, second, count, files))
    lines.append("")
    if dropped:
        lines.append("never written, matched by field name: " + ", ".join(dropped))
    else:
        lines.append("never written, matched by field name: none found")
    total = sum(len(files) for _, _, files in written) + 1
    lines.append("wrote %d files including manifest.json" % total)
    return "\n".join(lines) + "\n"


def run(argv, fetch=http_fetch, env=None, stdout=None):
    env = os.environ if env is None else env
    stdout = sys.stdout if stdout is None else stdout
    args = build_parser().parse_args(argv)

    token = env.get(TOKEN_ENV, "").strip()
    if not token:
        raise ExportError(
            "%s is not set. Create a personal access token in the management "
            "dashboard, then export %s=... before running this." % (TOKEN_ENV, TOKEN_ENV)
        )

    resources = parse_list(args.resources, set(RESOURCES), "resources")
    formats = parse_list(args.format, {"csv", "json"}, "format")

    result = export(resources, args.url, auth_header(token, args.bearer), fetch=fetch)

    os.makedirs(args.out, exist_ok=True)
    written = []
    all_dropped = []
    manifest = {
        "tool": "netbirdexport",
        "version": __version__,
        "source": args.url,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "resources": {},
    }

    for name in resources:
        items, dropped = result[name]
        all_dropped.extend(name + "." + one for one in dropped)
        files = []
        if "csv" in formats:
            rows = [flatten(item) for item in items]
            files.append(name + ".csv")
            write_text(os.path.join(args.out, name + ".csv"), to_csv(rows))
        if "json" in formats:
            files.append(name + ".json")
            write_text(os.path.join(args.out, name + ".json"), to_json(items))
        written.append((name, len(items), files))
        manifest["resources"][name] = {
            "path": RESOURCES[name],
            "rows": len(items),
            "files": files,
            "redacted_fields": dropped,
        }

    write_text(
        os.path.join(args.out, "manifest.json"),
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    stdout.write(render_report(args.url, args.out, written, all_dropped))
    return 0


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def main(argv=None):
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except ExportError as err:
        sys.stderr.write("netbirdexport: %s\n" % err)
        return 1


if __name__ == "__main__":
    sys.exit(main())
