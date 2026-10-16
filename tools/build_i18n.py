#!/usr/bin/env python3
"""
Build the per-language static pages (SEO item 3, Debby 2026-10-02).

    python3 tools/build_i18n.py

Source of truth:
  * public/js/i18n.js    -> all three languages' text (zh / en / ja)
  * public/index.html, how-to-play.html, about.html, faq.html (site root)
                         -> page structure; these ARE the English pages

What it does (safe to run any number of times):
  1. Root pages: rewrites every data-i18n / data-i18n-* text with the `en`
     strings, marks <html lang="en" data-static-lang="en">, refreshes the
     canonical + hreflang block, turns the language menu into real links.
  2. Writes zh/<page>.html and ja/<page>.html from the root page with the
     zh / ja strings, ../ asset paths and their own lang/canonical.
  3. Writes the 18 per-game pages (<lang>/game-rules/<id>.html) and 3
     overview pages (<lang>/game-rules.html) via tools/build_game_rules.py.
  4. Writes sitemap.xml (every page above, in all 3 languages, with hreflang
     alternates) and robots.txt pointing at it.

So: edit text in js/i18n.js (and structure in the root .html files, or
data/game-rules.json for per-game content), then run this script and commit
everything, including zh/, ja/, and game-rules/.
Never hand-edit zh/*.html, ja/*.html, or any game-rules/*.html — they are
all overwritten by this script.
"""
import html as _html
import os
import re
import sys
from html.parser import HTMLParser

import build_game_rules

# Production domain (Cloudflare Workers). Every deployment, including previews,
# points canonical/hreflang/sitemap here so only one copy gets indexed.
BASE_URL = "https://www.pokerrrrapp.com/"

PAGES = ["index.html", "how-to-play.html", "about.html", "faq.html",
         "news.html", "store.html", "news-card-peek.html", "news-tight-players.html", "news-ofc-sit-and-go.html"]
LANGS = ["en", "zh", "ja"]
HTML_LANG = {"en": "en", "zh": "zh-Hant", "ja": "ja"}
DIR = {"en": "", "zh": "zh/", "ja": "ja/"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}

# Site root = public/ (the Cloudflare Pages output directory); all paths
# below are relative to it.
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")


def load_dict():
    src = open(os.path.join(ROOT, "js/i18n.js"), encoding="utf-8").read()
    body = src[src.index("const I18N = {"):src.index("const OFC_LANG_KEY")]
    item = re.compile(r"^\s*'([^']+)':\s*'((?:[^'\\]|\\.)*)',?\s*$")
    out, cur = {}, None
    for line in body.split("\n"):
        m = re.match(r"^  (zh|en|ja): \{", line)
        if m:
            cur = m.group(1)
            out[cur] = {}
            continue
        m = item.match(line)
        if m and cur:
            val = re.sub(r"\\(.)", lambda x: {"n": "\n"}.get(x.group(1), x.group(1)), m.group(2))
            out[cur][m.group(1)] = val
    sizes = {k: len(v) for k, v in out.items()}
    if set(out) != set(LANGS) or len(set(sizes.values())) != 1:
        sys.exit("i18n.js parse problem: %r" % sizes)
    return out


def esc_attr(v):
    return v.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


class Scan(HTMLParser):
    """Records source offsets of data-i18n element bodies and attributes."""

    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.lo = [0]
        for l in src.split("\n"):
            self.lo.append(self.lo[-1] + len(l) + 1)
        self.stack, self.inner, self.attrs = [], [], []

    def off(self):
        l, c = self.getpos()
        return self.lo[l - 1] + c

    def handle_starttag(self, tag, attrs):
        st = self.off()
        en = st + len(self.get_starttag_text())
        d = dict(attrs)
        for a in ("aria-label", "alt", "content", "title"):
            if d.get("data-i18n-" + a):
                self.attrs.append((st, en, a, d["data-i18n-" + a]))
        if tag not in VOID:
            self.stack.append((tag, en, d.get("data-i18n")))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        st = self.off()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                _, en, key = self.stack[i]
                del self.stack[i:]
                if key:
                    self.inner.append((en, st, key))
                return


def translate(src, d, missing):
    p = Scan(src)
    p.feed(src)
    p.close()
    inner = sorted(p.inner)
    keep = [r for r in inner
            if not any(o != r and o[0] <= r[0] and r[1] <= o[1] for o in inner)]
    edits = []
    for a, b, key in keep:
        if key in d:
            edits.append((a, b, d[key]))
        else:
            missing.add(key)
    for st, en, attr, key in p.attrs:
        if any(a <= st < b for a, b, _ in keep):
            continue
        if key not in d:
            missing.add(key)
            continue
        tag = src[st:en]
        new, n = re.subn(r'(\s%s=")[^"]*(")' % re.escape(attr),
                         lambda m: m.group(1) + esc_attr(d[key]) + m.group(2), tag, count=1)
        if n == 0:
            close = " />" if tag.endswith("/>") else ">"
            new = tag[:-len(close.strip())].rstrip().rstrip("/").rstrip() + ' %s="%s"%s' % (attr, esc_attr(d[key]), close)
        edits.append((st, en, new))
    for a, b, v in sorted(edits, key=lambda e: e[0], reverse=True):
        src = src[:a] + v + src[b:]
    return src


def page_url(page, lang):
    return BASE_URL + DIR[lang] + ("" if page == "index.html" else page)


def head_block(page, lang):
    lines = ['<link rel="canonical" href="%s">' % page_url(page, lang)]
    for l in LANGS:
        lines.append('<link rel="alternate" hreflang="%s" href="%s">' % (HTML_LANG[l], page_url(page, l)))
    lines.append('<link rel="alternate" hreflang="x-default" href="%s">' % page_url(page, "en"))
    return "<!-- i18n:alternates (generated by tools/build_i18n.py) -->\n" + "\n".join(lines) + "\n<!-- /i18n:alternates -->\n"


ANTI_FLASH = re.compile(r"<script>\s*/\* Hide the page until js/i18n\.js.*?</script>\n", re.S)
ALT_BLOCK = re.compile(r"<!-- i18n:alternates.*?<!-- /i18n:alternates -->\n", re.S)
LANG_MENU = re.compile(r'(<div class="lang-switch-menu">)(.*?)(</div>)', re.S)
GEN_NOTE = "<!-- GENERATED by tools/build_i18n.py from ../%s + js/i18n.js — do not edit by hand. -->\n"


def localize(src, page, lang):
    up = "" if lang == "en" else "../"
    # <html> tag
    src = re.sub(r"<html[^>]*>", '<html lang="%s" data-static-lang="%s">' % (HTML_LANG[lang], lang), src, count=1)
    # no runtime translation on static pages -> no anti-flash snippet needed
    src = ANTI_FLASH.sub("", src)
    # canonical + hreflang
    src = ALT_BLOCK.sub("", src)
    src = src.replace('<link rel="stylesheet" href="', head_block(page, lang) + '<link rel="stylesheet" href="', 1)
    # language menu -> real links to this page in each language
    links = "\n".join(
        '          <a href="%s%s%s" data-lang="%s" hreflang="%s" lang="%s"%s>%s</a>' % (
            up, DIR[l], page, l, HTML_LANG[l], HTML_LANG[l],
            ' class="active" aria-current="true"' if l == lang else "",
            {"en": "EN", "zh": "中", "ja": "日"}[l])
        for l in LANGS)
    src = LANG_MENU.sub(lambda m: m.group(1) + "\n" + links + "\n        " + m.group(3), src, count=1)
    src = re.sub(r'(<span class="lang-switch-label">)[^<]*(</span>)',
                 lambda m: m.group(1) + {"en": "EN", "zh": "中", "ja": "日"}[lang] + m.group(2), src)
    # how-to-play.html's 6 feature-card links used to point at the single
    # dynamic game-rules.html?game=<id>&lang=xx page; it's now 18 static
    # pages, one per game per language, living at game-rules/<id>.html
    # alongside this page in every language's own folder -- so no "../" is
    # needed here regardless of lang (see tools/build_game_rules.py).
    src = re.sub(r'href="(?:\.\./)?game-rules\.html\?game=([a-z]+)(?:&amp;lang=\w+)?"',
                 lambda m: 'href="game-rules/%s.html"' % m.group(1), src)
    if lang != "en":
        # shared assets live one level up
        src = re.sub(r'((?:src|href|poster|srcset)=")((?:assets|css|js)/)', r"\1../\2", src)
        src = re.sub(r"url\((['\"]?)((?:assets|css)/)", r"url(\1../\2", src)
        src = src.replace("<!DOCTYPE html>\n", "<!DOCTYPE html>\n" + GEN_NOTE % page, 1)
    return src


def write_sitemap():
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!-- GENERATED by tools/build_i18n.py — do not edit by hand. -->',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
           '        xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for page in PAGES:
        for lang in LANGS:
            out.append("  <url>")
            out.append("    <loc>%s</loc>" % _html.escape(page_url(page, lang)))
            for l in LANGS:
                out.append('    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (HTML_LANG[l], _html.escape(page_url(page, l))))
            out.append('    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>' % _html.escape(page_url(page, "en")))
            out.append("  </url>")
    # 18 per-game pages + 3 overview pages, each with full hreflang alternates.
    for loc, alts in build_game_rules.sitemap_entries(BASE_URL):
        out.append("  <url>")
        out.append("    <loc>%s</loc>" % _html.escape(loc))
        for l in LANGS:
            out.append('    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (HTML_LANG[l], _html.escape(alts[l])))
        out.append('    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>' % _html.escape(alts["en"]))
        out.append("  </url>")
    out.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    # Note: crawlers only read robots.txt at the host root, so this file only
    # takes effect on www.pokerrrrapp.com, not on sub-path preview hosts.
    open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8").write(
        "User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % BASE_URL)
    print("wrote sitemap.xml, robots.txt")


def main():
    d = load_dict()
    build_game_rules.build(d, BASE_URL)
    missing = set()
    for page in PAGES:
        path = os.path.join(ROOT, page)
        base = open(path, encoding="utf-8").read()
        for lang in LANGS:
            out = localize(translate(base, d[lang], missing), page, lang)
            dest = os.path.join(ROOT, DIR[lang], page)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w", encoding="utf-8").write(out)
            print("wrote", os.path.relpath(dest, ROOT))
    write_sitemap()
    if missing:
        print("WARNING: keys used in HTML but missing from js/i18n.js:", ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
