#!/usr/bin/env python3
"""
Clean (extension-less) page URLs — run as the last step of tools/build_i18n.py.

Cloudflare serves every page without ".html" and redirects /xxx.html -> /xxx
(and /index.html -> /). Google only indexes the URL the browser ends up on,
so canonical, hreflang, sitemap and every internal link must use that same
clean URL; otherwise the clean URLs get reported as "alternate pages" and
are not indexed.

Rules (pages only — images, CSS, JS etc. keep their paths):
  xxx.html        -> xxx           game-rules/plo.html -> game-rules/plo
  index.html      -> ./            ../index.html -> ../   zh/index.html -> zh/
  https://www.pokerrrrapp.com/zh/index.html -> https://www.pokerrrrapp.com/zh/
Query strings and #fragments are kept. Running it twice changes nothing.
"""
import os
import re

SKIP = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.I)  # mailto:, tel:, other schemes, //cdn, #frag


def clean_path(path):
    """'about.html' -> 'about', 'zh/index.html' -> 'zh/', 'index.html' -> './'."""
    if not path.endswith(".html"):
        return path
    if path == "index.html":
        return "./"
    if path.endswith("/index.html"):
        return path[: -len("index.html")]
    return path[: -len(".html")]


def clean_url(url, base_url):
    """Clean one URL if it points at a page on this site; leave anything else."""
    if url.startswith(base_url):
        rest = url[len(base_url):]
        m = re.match(r"([^?#]*)(.*)$", rest, re.S)
        path = m.group(1)
        if path == "index.html":
            path = ""
        else:
            path = clean_path(path)
        return base_url + path + m.group(2)
    if SKIP.match(url):
        return url
    m = re.match(r"([^?#]*)(.*)$", url, re.S)
    return clean_path(m.group(1)) + m.group(2)


HREF = re.compile(r'(\shref=")([^"]*)(")')


def clean_html(src, base_url):
    # every href (a, link rel=canonical/alternate, ...): only .html pages change
    src = HREF.sub(lambda m: m.group(1) + clean_url(m.group(2), base_url) + m.group(3), src)
    # absolute page URLs anywhere else (og:url, JSON-LD, ...)
    abs_page = re.compile(re.escape(base_url) + r'[^"\'\s<>]*?\.html(?=[?#"\'\s<>]|$)')
    return abs_page.sub(lambda m: clean_url(m.group(0), base_url), src)


def clean_site(root, base_url):
    """Rewrite every .html file under public/ (assets/ excluded) in place."""
    changed = 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "assets"]
        for f in fn:
            if not f.endswith(".html"):
                continue
            p = os.path.join(dp, f)
            src = open(p, encoding="utf-8").read()
            new = clean_html(src, base_url)
            if new != src:
                open(p, "w", encoding="utf-8", newline="\n").write(new)
                changed += 1
    print("clean URLs: rewrote %d html files" % changed)
