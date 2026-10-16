#!/usr/bin/env python3
"""Turn downloaded Wix blog posts into content/news/<slug>.md (offline step).

Run tools/fetch_wix_news.py first (it needs network); this script only
reads what that saved:
  _transfer/wix-raw/<slug>.html    raw post pages
  _transfer/wix-media/<id>.<ext>   original-size images
  _transfer/news-migration.json    which posts to migrate (old URL <-> slug)

and writes:
  content/news/<slug>.md                       front matter + cleaned HTML body
  public/assets/images/news/<slug>/<n>.jpg|png  resized images (max 1400px)
  _transfer/wix-import-report.json             per-post notes to review

Usage:  python3 tools/import_wix_news.py [--force] [<slug> ...]
Existing .md files are left alone unless --force is given (so hand edits
made after the import are not overwritten).
Needs: beautifulsoup4, Pillow.
"""
import html
import json
import os
import re
import sys

from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "_transfer")
RAW, MEDIA = os.path.join(T, "wix-raw"), os.path.join(T, "wix-media")
OUT = os.path.join(ROOT, "content", "news")
IMG_URL = "assets/images/news/%s/%s"          # relative to public/
IMG_DIR = os.path.join(ROOT, "public", IMG_URL)
MAX_W = 1400

MIGRATION = json.load(open(os.path.join(T, "news-migration.json"), encoding="utf-8"))
SLUGS = {p["slug"]: p["old_url"] for p in MIGRATION["migrate"]}
OLD_PATH_TO_SLUG = {p["old_url"].split("/single-post/", 1)[1]: p["slug"] for p in MIGRATION["migrate"]}
STORE_LINK = re.compile(r"(apps\.apple\.com|itunes\.apple\.com|play\.google\.com|onelink\.me)", re.I)


# ------------------------------------------------------------------ category
def category(slug, title=""):
    """Rough first guess from the slug only (titles were edited on Wix over the
    years); fix by hand in the front matter if needed."""
    s = slug
    if re.search(r"poker-legends|blackjack-legends|hall-of-fame", s):
        return "legends"
    if re.search(r"^pokerrrr|card-peek|nit-game|seven-deuce|poker-quiz|collect-poker-cards|ai-hand-review|poker-with-friends-online", s):
        return "pokerrrr2"
    if re.search(r"poker-stories|moneymaker|scandal|mrbeast|behind-the-scenes|prince-of-poker|ai-bots|robots|"
                 r"wsop-bluff|tournament-feels|blackjack-players|fun-facts|history|underground|how-did-poker", s):
        return "stories"
    if re.search(r"beginners|how-to-play-|probability|easy-poker|starting-hands|short-deck|rules|count-cards|"
                 r"host-a-poker-night|without-chips|sit-and-go|lessons-for-life|8-ways-poker", s):
        return "guides"
    return "strategy"


# ------------------------------------------------------------------ inline
def inline(node, slug, notes):
    """Clean inline HTML: keep strong/em/a/br/code, drop Wix wrappers and styles."""
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            if c.__class__.__name__ in ("Comment", "Stylesheet", "Script"):
                continue
            out.append(html.escape(str(c), quote=False))
            continue
        if not isinstance(c, Tag) or c.name in ("style", "script", "svg", "button"):
            continue
        inner = inline(c, slug, notes)
        style = c.get("style", "")
        if c.name in ("strong", "b") or (c.name == "span" and re.search(r"font-weight:\s*(bold|[6-9]00)", style)):
            out.append("<strong>%s</strong>" % inner if inner.strip() else inner)
        elif c.name in ("em", "i") or (c.name == "span" and "font-style:italic" in style):
            out.append("<em>%s</em>" % inner if inner.strip() else inner)
        elif c.name == "br":
            out.append("<br>")
        elif c.name == "a" and c.get("href"):
            out.append('<a href="%s"%s>%s</a>' % (link(c["href"], notes), ext(c["href"]), inner))
        else:
            out.append(inner)
    s = "".join(out)
    s = re.sub(r"</strong>(\s*)<strong>", r"\1", s)
    s = re.sub(r"</em>(\s*)<em>", r"\1", s)
    return s


def link(href, notes):
    m = re.match(r"https?://(?:www\.)?pokerrrrapp\.com/single-post/(.+?)/?$", href)
    if m:
        target = OLD_PATH_TO_SLUG.get(m.group(1))
        if target:
            return "news/%s.html" % target
        notes.append("link to a post that is not migrated: " + href)
    return html.escape(href, quote=True)


def ext(href):
    return ' target="_blank" rel="noopener"' if re.match(r"https?://", href) and "pokerrrrapp.com/single-post/" not in href else ""


# ------------------------------------------------------------------ images
class Images:
    def __init__(self, slug):
        self.slug, self.map, self.n = slug, {}, 0
        os.makedirs(IMG_DIR % (slug, ""), exist_ok=True)

    def get(self, media_name):
        """Copy+resize one Wix media file; returns (relative url, w, h) or None."""
        if media_name in self.map:
            return self.map[media_name]
        src = os.path.join(MEDIA, media_name)
        if not os.path.exists(src):
            self.map[media_name] = None
            return None
        self.n += 1
        im = Image.open(src)
        im.load()
        alpha = im.mode in ("RGBA", "LA", "P") and im.convert("RGBA").getextrema()[3][0] < 255
        if im.width > MAX_W:
            im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
        name = "%02d.%s" % (self.n, "png" if alpha else "jpg")
        dest = IMG_DIR % (self.slug, name)
        if alpha:
            im.convert("RGBA").save(dest, optimize=True)
        else:
            im.convert("RGB").save(dest, quality=82, optimize=True, progressive=True)
        self.map[media_name] = (IMG_URL % (self.slug, name), im.width, im.height)
        return self.map[media_name]


def media_name(wow):
    i = wow.get("id", "") if wow else ""
    return i if re.match(r"[0-9a-f]{6}_[0-9a-f]{32}", i) else None


# ------------------------------------------------------------------ blocks
def figure(fig, imgs, notes):
    name = media_name(fig.find("wow-image"))
    got = imgs.get(name) if name else None
    if not got:
        notes.append("image missing: %s" % name)
        return "", None
    url, w, h = got
    cap = fig.find("figcaption")
    cap = cap.get_text(" ", strip=True) if cap else ""
    a = fig.find_parent("a") or fig.find("a", href=True)
    href = a.get("href") if a else None
    img = '<img src="%s" alt="%s" width="%d" height="%d" loading="lazy">' % (url, html.escape(cap, quote=True), w, h)
    if href:
        img = '<a href="%s"%s>%s</a>' % (link(href, notes), ext(href), img)
    out = "<figure>%s%s</figure>" % (img, "<figcaption>%s</figcaption>" % html.escape(cap) if cap else "")
    return out, href


def table(tb, slug, notes):
    rows = []
    for i, tr in enumerate(tb.find_all("tr")):
        tag = "th" if i == 0 else "td"
        cells = []
        for td in tr.find_all("td"):
            ps = [inline(p, slug, notes).strip() for p in td.find_all("p")] or [inline(td, slug, notes).strip()]
            cells.append("<%s>%s</%s>" % (tag, "<br>".join(x for x in ps if x), tag))
        rows.append("<tr>%s</tr>" % "".join(cells))
    return '<div class="table-scroll"><table>\n%s\n</table></div>' % "\n".join(rows)


def blocks(el, slug, imgs, notes, out):
    for c in el.children:
        if not isinstance(c, Tag) or c.name in ("style", "script", "svg", "button"):
            continue
        n = c.name
        if n == "p":
            s = re.sub(r"^(\s*<br>)+|(<br>\s*)+$", "", inline(c, slug, notes).strip()).strip()
            if s:
                out.append("<p>%s</p>" % s)
        elif n in ("h1", "h2", "h3", "h4", "h5", "h6"):
            s = inline(c, slug, notes).strip()
            s = re.sub(r"</?strong>|<br>", "", s).strip()
            if s:
                lvl = "h2" if n in ("h1", "h2") else "h3"
                out.append("<%s>%s</%s>" % (lvl, s, lvl))
        elif n in ("ul", "ol"):
            items = []
            for li in c.find_all("li", recursive=False):
                ps = [inline(p, slug, notes).strip() for p in li.find_all("p")] or [inline(li, slug, notes).strip()]
                items.append("<li>%s</li>" % "<br>".join(x for x in ps if x))
            out.append("<%s>\n%s\n</%s>" % (n, "\n".join(items), n))
        elif n == "blockquote":
            ps = [inline(p, slug, notes).strip() for p in c.find_all("p")] or [inline(c, slug, notes).strip()]
            out.append("<blockquote>%s</blockquote>" % "".join("<p>%s</p>" % x for x in ps if x))
        elif n == "figure":
            f, href = figure(c, imgs, notes)
            if f:
                out.append(("STORE:" if href and STORE_LINK.search(href) else "") + f)
        elif n == "table":
            out.append(table(c, slug, notes))
        elif c.get("data-hook", "").startswith("divider"):
            out.append("<hr>")
        elif n == "iframe" or c.get("data-hook") in ("video-player", "embed"):
            notes.append("embedded media skipped (check manually)")
        else:
            blocks(c, slug, imgs, notes, out)


# ------------------------------------------------------------------ post
def excerpt(body_html, n=180):
    for p in re.findall(r"<p>(.*?)</p>", body_html, re.S):
        t = html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        if len(t) >= 60 and not re.match(r"photo (taken )?from", t, re.I):
            t = re.sub(r"\s+", " ", t)
            return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return ""


def fm_value(v):
    return str(v).replace("\n", " ").strip()


def convert(slug):
    notes = []
    src = open(os.path.join(RAW, slug + ".html"), encoding="utf-8").read()
    soup = BeautifulSoup(src, "html.parser")
    ld = {}
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            j = json.loads(s.string)
        except Exception:
            continue
        if isinstance(j, dict) and j.get("@type") == "BlogPosting":
            ld = j
    h1 = soup.find("h1")
    title = ld.get("headline") or (h1.get_text() if h1 else slug)
    title = re.sub(r"\s+", " ", html.unescape(html.unescape(title))).strip()  # Wix double-escapes
    date = (ld.get("datePublished") or "")[:10]
    if not date:
        m = soup.find("meta", property="article:published_time")
        date = m["content"][:10] if m else ""
    author = (ld.get("author") or {}).get("name", "Pokerrrr")
    if author.lower().startswith(("sammy", "admin")) or re.search(r"\d$", author):
        author = "Pokerrrr"  # Wix account handles, not real bylines

    cv = soup.find(attrs={"data-id": "content-viewer"})
    if not cv:
        return None, ["no content-viewer found"]
    imgs = Images(slug)
    out = []
    blocks(cv, slug, imgs, notes, out)
    # The old posts end with a row of app-store badge images; the new article
    # template has its own download CTA, so drop them.
    # (a trailing run of images: logo, App Store / Google Play badges, QR code)
    i = len(out)
    while i and out[i - 1].removeprefix("STORE:").startswith("<figure"):
        i -= 1
    if any(b.startswith("STORE:") for b in out[i:]):
        out = out[:i]
    out = [b[len("STORE:"):] if b.startswith("STORE:") else b for b in out]
    body = "\n\n".join(out)

    og = soup.find("meta", property="og:image")
    cover = None
    if og:
        m = re.search(r"/media/([0-9a-f]{6}_[0-9a-f]{32}[^/]*?\.(?:jpe?g|png|gif|webp))", og["content"], re.I)
        if m:
            got = imgs.get(m.group(1))
            cover = got[0] if got else None
    if not cover:
        m = re.search(r'<img src="([^"]+)"', body)
        cover = m.group(1) if m else ""
        if not cover:
            notes.append("no cover image")

    # remove image files that ended up unused (e.g. the dropped badges)
    used = set(re.findall(r'assets/images/news/%s/([^"]+)' % re.escape(slug), body + " " + (cover or "")))
    d = IMG_DIR % (slug, "")
    for f in os.listdir(d):
        if f not in used:
            os.remove(os.path.join(d, f))

    words = len(re.sub(r"<[^>]+>", " ", body).split())
    fm = {
        "title": title,
        "date": date,
        "author": author,
        "category": category(slug, title),
        "cover": cover,
        "excerpt": excerpt(body),
        "read_time": max(1, round(words / 230)),
        "old_url": SLUGS[slug],
    }
    if not date:
        notes.append("no publish date")
    text = "---\n%s\n---\n\n%s\n" % ("\n".join("%s: %s" % (k, fm_value(v)) for k, v in fm.items()), body)
    return text, notes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    todo = args or sorted(f[:-5] for f in os.listdir(RAW) if f.endswith(".html"))
    os.makedirs(OUT, exist_ok=True)
    rp = os.path.join(T, "wix-import-report.json")
    report = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
    for slug in todo:
        if slug not in SLUGS:
            print("skip (not in migration list):", slug)
            continue
        dest = os.path.join(OUT, slug + ".md")
        if os.path.exists(dest) and not force:
            print("exists, skip:", slug)
            continue
        text, notes = convert(slug)
        if text:
            open(dest, "w", encoding="utf-8", newline="\n").write(text)
        report[slug] = notes
        print("%s %s%s" % ("ok " if text else "ERR", slug, ("  (%d note(s))" % len(notes)) if notes else ""))
    json.dump(report, open(rp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
