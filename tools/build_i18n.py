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
  3b. News: list block in news.html + news/<slug>.html from content/news/*.md
      via tools/build_news.py (articles are English only).
  4. Writes sitemap.xml (every page above, in all 3 languages, with hreflang
     alternates) and robots.txt pointing at it.
  5. Rewrites every internal page link to its extension-less URL
     (about.html -> about, index.html -> ./) via tools/clean_urls.py, so
     canonical / hreflang / sitemap / links all match the URL Cloudflare
     actually serves.

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
import build_news
import clean_urls

# Production domain (Cloudflare Workers). Every deployment, including previews,
# points canonical/hreflang/sitemap here so only one copy gets indexed.
BASE_URL = "https://www.pokerrrrapp.com/"

PAGES = ["index.html", "how-to-play.html", "about.html", "faq.html",
         "news.html", "store.html"]
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
        for a in ("aria-label", "alt", "content", "title", "placeholder"):
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
    # extension-less, e.g. .../about, .../zh/ (see tools/clean_urls.py)
    return BASE_URL + DIR[lang] + ("" if page == "index.html" else page[:-len(".html")])


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
        # (news/<slug>.html articles exist in English only, at the site root)
        src = re.sub(r'((?:src|href|poster|srcset)=")((?:assets|css|js|news)/)', r"\1../\2", src)
        src = re.sub(r"url\((['\"]?)((?:assets|css)/)", r"url(\1../\2", src)
        src = src.replace("<!DOCTYPE html>\n", "<!DOCTYPE html>\n" + GEN_NOTE % page, 1)
    return src


# NLH gesture tutorial (public/tutorial/nlh-gestures.html) shown in the right
# column of How to Play: an iframe on desktop, a button that opens the
# tutorial full-screen on phones (an iframe there would fight page scrolling).
NLH_TUTORIAL_TEXT = {
    "en": {"title": "Try the in-app gestures", "cta": "Try the gestures", "frame": "Interactive NLH gesture tutorial"},
    "zh": {"title": "體驗 App 內的手勢操作", "cta": "開始體驗", "frame": "NLH 手勢互動教學"},
    "ja": {"title": "アプリのジェスチャーを体験", "cta": "体験する", "frame": "NLH ジェスチャー体験チュートリアル"},
}

# Scoped styles for the tutorial slot, kept in the generated block so
# style.css (and its ?v= on every page) does not change.
NLH_TUTORIAL_STYLE = (
    '<style>'
    '.htp-nlh-tutorial{position:sticky;top:100px;display:flex;flex-direction:column;align-items:center;gap:14px}'
    '.htp-nlh-tutorial-title{font-family:var(--font-label);font-size:var(--fs-xs);letter-spacing:.1em;text-transform:uppercase;color:var(--color-text-faint);margin:0;text-align:center}'
    '.htp-nlh-tutorial-frame{display:block;width:100%;max-width:380px;aspect-ratio:9/17.5;border:0;border-radius:28px;background:#062631;'
    'box-shadow:0 0 0 1px rgba(212,175,55,.35),0 24px 48px -20px rgba(0,0,0,.7)}'
    '.htp-nlh-tutorial-cta{display:none}'
    '@media (max-width:900px){.htp-nlh-tutorial{position:static}.htp-nlh-tutorial-frame{display:none}'
    '.htp-nlh-tutorial-cta{display:inline-flex}}'
    '</style>'
)

NLH_RULES = re.compile(r"(<!-- nlh:rules -->)(.*?)(<!-- /nlh:rules -->)", re.S)


def fill_nlh_rules(src, lang):
    """how-to-play.html: NLH rules (from data/game-rules.json; How to Play is
    the only NLH rules page) as a two-column split -- rules text with the
    hand-ranking table below it on the left; on the right, a reserved slot
    for the NLH tutorial mini-game (where the OFC demo used to sit; to be
    built later). The leading h2 is dropped (the section's own h1 already
    names the game). Card image paths are root-relative here; localize()
    adds ../ for zh/ja."""
    if "<!-- nlh:rules -->" not in src:
        return src
    gr = build_game_rules.load_game_rules()
    nlh = next(g for g in gr["games"] if g["id"] == "nlh")
    hl = HTML_LANG[lang]
    blocks = [b for b in nlh["blocks"] if b["t"] != "ranking"]
    if blocks and blocks[0]["t"] == "h2":
        blocks = blocks[1:]
    ranking = [b for b in nlh["blocks"] if b["t"] == "ranking"]
    render = build_game_rules.render
    text = render.render_blocks(blocks, hl, gr, "assets/images/cards/")
    rank = render.render_blocks(ranking, hl, gr, "assets/images/cards/")
    tx = NLH_TUTORIAL_TEXT[lang]
    # Page-relative: localize() does not rewrite tutorial/, so zh/ja need ../ here.
    src_url = ("" if lang == "en" else "../") + "tutorial/nlh-gestures.html"
    tutorial = (
        '        <!-- NLH gesture tutorial: iframe on desktop, full-screen page on phones -->\n'
        '        <div class="feature-split-media htp-nlh-tutorial">%s'
        '<p class="htp-nlh-tutorial-title">%s</p>'
        '<iframe class="htp-nlh-tutorial-frame" src="%s" title="%s" loading="lazy"></iframe>'
        '<a class="btn btn-primary htp-nlh-tutorial-cta" href="%s">%s</a></div>\n'
    ) % (NLH_TUTORIAL_STYLE, tx["title"], src_url, tx["frame"], src_url, tx["cta"])
    html = ('\n      <div class="feature-split">\n'
            '        <div class="feature-split-text gr-panel">%s\n'
            '          <div class="htp-nlh-ranking">%s</div>\n'
            '        </div>\n'
            '%s'
            '      </div>\n      ') % (text, rank, tutorial)
    return NLH_RULES.sub(lambda m: m.group(1) + html + m.group(3), src, count=1)


def write_sitemap(posts=()):
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
    # News articles (English only, so no hreflang alternates).
    for loc, date in build_news.sitemap_entries(posts, BASE_URL):
        out.append("  <url>")
        out.append("    <loc>%s</loc>" % _html.escape(loc))
        out.append("    <lastmod>%s</lastmod>" % date)
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
    missing = set()
    build_game_rules.build(d, BASE_URL, translate, missing)
    # News: fills the list block in news.html (before it is translated below)
    # and writes news/<slug>.html + _redirects.
    posts = build_news.build(d["en"], translate, BASE_URL)
    for page in PAGES:
        path = os.path.join(ROOT, page)
        base = open(path, encoding="utf-8").read()
        for lang in LANGS:
            out = localize(fill_nlh_rules(translate(base, d[lang], missing), lang), page, lang)
            dest = os.path.join(ROOT, DIR[lang], page)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w", encoding="utf-8").write(out)
            print("wrote", os.path.relpath(dest, ROOT))
    write_sitemap(posts)
    # Last step: every internal link -> extension-less URL (see tools/clean_urls.py)
    clean_urls.clean_site(ROOT, BASE_URL)
    if missing:
        print("WARNING: keys used in HTML but missing from js/i18n.js:", ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
