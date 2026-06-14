"""Command-line interface.

Subcommands:
  doctor    probe each required host and report allowlisted vs egress-blocked
  fetch     scrape metadata from sources into a JSON file
  download  download discovered media files (filter by --kind / --source)
  report    render a Markdown index from a fetched JSON file
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from collections import Counter, defaultdict

from .config import OPTIONAL_HOSTS, REQUIRED_HOSTS, SOURCES
from .http import EgressBlocked, HttpClient
from .models import MediaItem
from .sources import FETCHERS, fetch_source

ALLOWLIST_HELP = (
    "One or more target hosts are blocked by the environment's network egress "
    "allowlist.\nAdd them in your Claude Code on the web environment's network "
    "egress settings,\nthen re-run. Docs: https://code.claude.com/docs/en/claude-code-on-the-web\n"
    "Alternatively, run this tool on a machine with normal internet access."
)


def _client(args) -> HttpClient:
    return HttpClient(
        cache_dir=None if getattr(args, "no_cache", False) else args.cache,
        verbose=getattr(args, "verbose", False),
        delay=getattr(args, "delay", 1.0),
    )


# ---- doctor -----------------------------------------------------------
def cmd_doctor(args) -> int:
    client = _client(args)
    hosts = dict(REQUIRED_HOSTS)
    if args.all:
        hosts.update(OPTIONAL_HOSTS)

    print("Probing target hosts (egress allowlist check)\n" + "-" * 56)
    blocked, reachable = [], []
    for host, note in hosts.items():
        res = client.probe(f"https://{host}/")
        if res["reason"] == "egress_blocked":
            mark, blocked = "BLOCKED ", blocked + [host]
        elif res["ok"]:
            mark, reachable = "OK      ", reachable + [host]
        else:
            mark = "ERROR   "
        print(f"  {mark} {host:<24} {res['reason']}   ({note})")

    print("-" * 56)
    print(f"reachable: {len(reachable)}   blocked: {len(blocked)}")
    if blocked:
        print("\nAdd these hosts to the egress allowlist:")
        for h in blocked:
            print(f"  - {h}")
        print("\n" + ALLOWLIST_HELP)
        return 1
    print("\nAll required hosts are reachable. You can run `fetch`.")
    return 0


# ---- fetch ------------------------------------------------------------
def cmd_fetch(args) -> int:
    client = _client(args)
    names = list(FETCHERS) if args.source == "all" else [args.source]
    all_items: list[MediaItem] = []
    blocked_hosts: set[str] = set()

    for name in names:
        print(f"[fetch] {name}: {SOURCES[name]['label']}")
        try:
            items = fetch_source(client, name)
        except EgressBlocked as e:
            blocked_hosts.add(e.host)
            print(f"  -> egress blocked for {e.host}; skipping {name}")
            continue
        all_items.extend(items)
        kinds = Counter(i.kind for i in items)
        print(f"  -> {len(items)} items {dict(kinds)}")

    # dedupe
    uniq: dict[str, MediaItem] = {}
    for it in all_items:
        uniq.setdefault(it.key(), it)
    items = list(uniq.values())

    payload = {
        "version": 1,
        "sources": names,
        "count": len(items),
        "items": [i.to_dict() for i in items],
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"\nwrote {len(items)} items -> {args.out}")

    if blocked_hosts:
        print("\nEgress-blocked hosts (data incomplete):")
        for h in sorted(blocked_hosts):
            print(f"  - {h}")
        print("\n" + ALLOWLIST_HELP)
        return 1
    return 0


# ---- download ---------------------------------------------------------
def cmd_download(args) -> int:
    with open(args.infile, encoding="utf-8") as fh:
        payload = json.load(fh)
    items = [MediaItem(**i) for i in payload["items"]]

    kinds = set(args.kind.split(",")) if args.kind else {"video", "audio", "image", "document"}
    if args.source != "all":
        items = [i for i in items if i.source == args.source]
    items = [i for i in items if i.kind in kinds and i.url.startswith(("http://", "https://"))]

    if not items:
        print("nothing to download (check --kind / --source / input file)")
        return 0

    client = _client(args)
    print(f"downloading {len(items)} files -> {args.out}/")
    ok = fail = 0
    for it in items:
        path = urllib.parse.urlparse(it.url).path
        name = os.path.basename(path) or (it.kind + ".bin")
        dest = os.path.join(args.out, it.source, it.kind, name)
        if os.path.exists(dest) and not args.force:
            print(f"  skip (exists) {dest}")
            ok += 1
            continue
        try:
            n = client.download(it.url, dest)
            print(f"  ok  {n:>10} B  {dest}")
            ok += 1
        except EgressBlocked as e:
            print(f"  egress blocked: {e.host} -> stopping")
            print("\n" + ALLOWLIST_HELP)
            return 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {it.url} ({e})")
            fail += 1
    print(f"\ndone: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 1


# ---- report -----------------------------------------------------------
def cmd_report(args) -> int:
    with open(args.infile, encoding="utf-8") as fh:
        payload = json.load(fh)
    items = [MediaItem(**i) for i in payload["items"]]
    by_source: dict[str, list[MediaItem]] = defaultdict(list)
    for it in items:
        by_source[it.source].append(it)

    lines = ["# UAP sources — scraped index", "",
             f"Total items: {len(items)}", ""]
    for src in sorted(by_source):
        lines.append(f"## {SOURCES.get(src, {}).get('label', src)}")
        lines.append("")
        by_kind: dict[str, list[MediaItem]] = defaultdict(list)
        for it in by_source[src]:
            by_kind[it.kind].append(it)
        for kind in sorted(by_kind):
            lines.append(f"### {kind} ({len(by_kind[kind])})")
            for it in by_kind[kind]:
                title = it.title or it.url
                lines.append(f"- [{title}]({it.url})"
                             + (f" — {it.assessment}" if it.assessment else ""))
            lines.append("")
    out = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"wrote report -> {args.out}")
    else:
        print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="uap_scraper",
                                description="Fetch official US UAP/UFO disclosures.")
    p.add_argument("--cache", default=".cache", help="response cache dir")
    p.add_argument("--no-cache", action="store_true", help="disable response cache")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="check which target hosts are reachable")
    d.add_argument("--all", action="store_true", help="also probe optional CDN hosts")
    d.set_defaults(func=cmd_doctor)

    f = sub.add_parser("fetch", help="scrape metadata into JSON")
    f.add_argument("--source", default="all", choices=["all", *FETCHERS])
    f.add_argument("--out", default="data/uap_items.json")
    f.set_defaults(func=cmd_fetch)

    dl = sub.add_parser("download", help="download media listed in a JSON file")
    dl.add_argument("infile")
    dl.add_argument("--source", default="all", choices=["all", *FETCHERS])
    dl.add_argument("--kind", default="", help="comma list: video,audio,image,document")
    dl.add_argument("--out", default="media")
    dl.add_argument("--force", action="store_true", help="re-download existing files")
    dl.set_defaults(func=cmd_download)

    r = sub.add_parser("report", help="render Markdown index from JSON")
    r.add_argument("infile")
    r.add_argument("--out", default="")
    r.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except EgressBlocked as e:
        print(f"\n{e}\n\n{ALLOWLIST_HELP}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
