#!/usr/bin/env python3
"""Submit a static site's sitemap to IndexNow (fan-out: Bing / Yandex / Seznam / Naver)
and optionally save the homepage to the Internet Archive Wayback Machine.

Fully free, no accounts, no UI: IndexNow proves domain control via a public key
file named <KEY>.txt hosted on the site (content == file name).

Usage:
  python3 notify_search_engines.py --site https://user.github.io/repo
  python3 notify_search_engines.py --site ... --key-file /path/KEY.txt --no-wayback

Exit code 0 only if the key file is live and at least the primary endpoint accepted.
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

INDEXNOW_ENDPOINTS = (
    "https://api.indexnow.org/indexnow",
    "https://www.bing.com/indexnow",
    "https://yandex.com/indexnow",
)


def fetch(url, timeout=40, data=None, headers=None):
    req = urllib.request.Request(
        url, data=data, headers=headers or {}, method="POST" if data else "GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(1000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - report any transport/HTTP error
        return getattr(e, "code", None), str(e)[:200]


def find_key(repo_dir, key_file):
    if key_file:
        p = Path(repo_dir) / key_file
        if not p.exists():
            sys.exit(f"key file not found: {p}")
        return p.read_text().strip()
    pat = re.compile(r"^[0-9a-fA-F-]{8,128}\.txt$")
    for p in sorted(Path(repo_dir).iterdir()):
        if p.is_file() and pat.match(p.name):
            k = p.read_text().strip()
            if k == p.stem:  # content must equal the key itself
                return k
    sys.exit(f"no IndexNow key file found under {repo_dir} (expected <KEY>.txt whose content equals its name)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="https://ahsen198911-debug.github.io/china-roadtrip-atlas")
    ap.add_argument("--sitemap", default=None)
    ap.add_argument("--key-file", default=None)
    ap.add_argument("--repo-dir", default=".")
    ap.add_argument("--no-wayback", action="store_true")
    args = ap.parse_args()

    site = args.site.rstrip("/")
    sitemap = args.sitemap or site + "/sitemap.xml"
    host = urllib.parse.urlparse(site).netloc
    key = find_key(args.repo_dir, args.key_file)
    keyloc = f"{site}/{key}.txt"

    st, _ = fetch(keyloc, timeout=30)
    print(f"keyLocation {keyloc} -> HTTP {st}")
    if st != 200:
        sys.exit("key file not live; aborting (IndexNow would return 403)")

    xml = urllib.request.urlopen(sitemap, timeout=40).read().decode("utf-8", "replace")
    urls = [urllib.parse.quote(e.text.strip(), safe=":/%")
            for e in ET.fromstring(xml).iter() if e.tag.endswith("}loc")]
    print(f"sitemap {sitemap}: {len(urls)} URLs")

    payload = json.dumps(
        {"host": host, "key": key, "keyLocation": keyloc, "urlList": urls}
    ).encode("utf-8")
    ok = 0
    for ep in INDEXNOW_ENDPOINTS:
        st, body = fetch(ep, data=payload, headers={"Content-Type": "application/json; charset=utf-8"})
        print(f"{ep} -> HTTP {st} {body[:120]!r}")
        ok += st in (200, 202)

    if not args.no_wayback:
        st, body = fetch(f"https://web.archive.org/save/{site}", timeout=90)
        print(f"wayback save {site} -> HTTP {st}")
        ok += st in (200, 301, 302)

    sys.exit(0 if ok >= 1 else 1)


if __name__ == "__main__":
    main()
