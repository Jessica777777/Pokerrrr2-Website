#!/usr/bin/env python3
"""Download old Wix blog posts (raw HTML + images) for the News migration.

Network-only step: it saves each post page as-is and downloads every Wix
media file the page references, at original size. Turning the HTML into
Markdown is done afterwards by a separate script (no network needed).

Standard library only, so it runs with macOS's built-in python3.

Usage (from the repo root):
  python3 tools/fetch_wix_news.py                # sample posts (default)
  python3 tools/fetch_wix_news.py --all          # every post in the list
  python3 tools/fetch_wix_news.py --only <slug> [<slug> ...]

Reads  _transfer/news-migration.json
Writes _transfer/wix-raw/<slug>.html
       _transfer/wix-media/<media-id>.<ext>
       _transfer/wix-fetch-log.json
Already-downloaded files are skipped, so it is safe to re-run.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.path.join(ROOT, "_transfer", "news-migration.json")
RAW = os.path.join(ROOT, "_transfer", "wix-raw")
MEDIA = os.path.join(ROOT, "_transfer", "wix-media")
LOG = os.path.join(ROOT, "_transfer", "wix-fetch-log.json")

# A spread of years and article types, used to check the layout first.
SAMPLE = [
    "pokerrrr2-card-peek-the-mobile-poker-app-that-recreates-the-casino-swipe",
    "double-board-poker-strategy-how-to-win-big-in-hold-em-plo",
    "best-starting-hands-in-poker-guide",
    "poker-legends-phil-ivey",
    "poker-stories-the-moneymaker-effect",
    "gto-vs-exploitative-poker",
    "the-one-thing-all-winning-players-have-in-common",
]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
# static.wixstatic.com/media/<id>~mv2.<ext>  (also old ids without ~mv2)
MEDIA_RE = re.compile(
    r"https?://static\.wixstatic\.com/media/([0-9a-f]{6}_[0-9a-f]{32}(?:~mv2(?:_d_\d+_\d+_s_\d+)?)?\.(?:jpe?g|png|gif|webp))",
    re.I)


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            err = e
        except Exception as e:  # network hiccup: back off and retry
            err = e
        time.sleep(2 * (i + 1))
    raise err


def fetch_media(name):
    path = os.path.join(MEDIA, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return name, "skip"
    try:
        data = get("https://static.wixstatic.com/media/" + name)
    except Exception as e:
        return name, "error: %s" % e
    with open(path, "wb") as f:
        f.write(data)
    return name, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="fetch every post in the list")
    ap.add_argument("--only", nargs="+", metavar="SLUG", help="fetch these slugs only")
    args = ap.parse_args()

    posts = json.load(open(LIST, encoding="utf-8"))["migrate"]
    by_slug = {p["slug"]: p for p in posts}
    if args.all:
        todo = posts
    else:
        wanted = args.only or SAMPLE
        missing = [s for s in wanted if s not in by_slug]
        if missing:
            sys.exit("Not in news-migration.json: " + ", ".join(missing))
        todo = [by_slug[s] for s in wanted]

    os.makedirs(RAW, exist_ok=True)
    os.makedirs(MEDIA, exist_ok=True)
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {}

    media = set()
    for n, p in enumerate(todo, 1):
        slug, path = p["slug"], os.path.join(RAW, p["slug"] + ".html")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            status = "skip"
        else:
            try:
                html = get(p["old_url"])
                with open(path, "wb") as f:
                    f.write(html)
                status = "ok"
                time.sleep(0.5)  # be gentle with the old site
            except Exception as e:
                status = "error: %s" % e
        print("[%d/%d] %s  %s" % (n, len(todo), status, slug))
        log[slug] = {"page": status}
        if os.path.exists(path):
            text = open(path, encoding="utf-8", errors="replace").read()
            names = sorted(set(m.group(1) for m in MEDIA_RE.finditer(text)))
            log[slug]["media"] = names
            media.update(names)

    print("\nDownloading %d image(s)..." % len(media))
    errors = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, status in ex.map(fetch_media, sorted(media)):
            if status.startswith("error"):
                errors += 1
                print("  %s  %s" % (status, name))

    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=1)
    bad_pages = [s for s, v in log.items() if v["page"].startswith("error")]
    print("\nDone. Pages: %d, page errors: %d, images: %d, image errors: %d"
          % (len(todo), len(bad_pages), len(media), errors))
    print("Saved to _transfer/wix-raw/ and _transfer/wix-media/")


if __name__ == "__main__":
    main()
