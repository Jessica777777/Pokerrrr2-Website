#!/usr/bin/env python3
"""
Build the News (blog) pages from content/news/*.md.

Imported by tools/build_i18n.py; not meant to be run standalone.

Source of truth:
  * content/news/<slug>.md          -> one post: front matter + body
  * tools/templates/news-article.html -> article page template
  * public/news.html                -> list page; the part between
                                       <!-- news:list --> and <!-- /news:list -->
                                       is generated here, the rest is a normal
                                       source page translated by build_i18n.py

Writes:
  * public/news.html (list block only; build_i18n then makes zh/ja copies)
  * public/news/<slug>.html          (English only; post bodies are not translated)
  * public/_redirects                (old Wix /single-post/... URLs -> new URLs)

Post file format:
    ---
    title: Poker Legends: Phil Ivey
    date: 2021-01-30
    author: Pokerrrr
    category: legends            # strategy | guides | stories | legends | pokerrrr2
    cover: assets/images/news/<slug>/01.jpg
    excerpt: One or two sentences for the list card and meta description.
    read_time: 2
    featured: true               # optional, newest featured post tops the list
    old_url: https://www.pokerrrrapp.com/single-post/...   # optional
    ---

    Body: HTML, or Markdown (needs the `markdown` package) for new posts.
Paths in the body/cover are relative to public/ (assets/..., news/<slug>.html);
the build adjusts them for each page's folder.
"""
import datetime
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "public")
CONTENT = os.path.join(ROOT, "content", "news")
TEMPLATE = os.path.join(ROOT, "tools", "templates", "news-article.html")

CATEGORIES = ["strategy", "guides", "mindset", "stories", "legends", "pokerrrr2"]
CAT_EN = {"strategy": "Strategy", "guides": "Guides", "mindset": "Mindset", "stories": "Poker Stories",
          "legends": "Legends", "pokerrrr2": "Pokerrrr 2"}
PAGE_SIZE = 12  # cards shown before "Load more" (main.js reads data-page-size)
LIST_BLOCK = re.compile(r"(<!-- news:list -->).*?(<!-- /news:list -->)", re.S)


# ---------------------------------------------------------------- loading
def parse(path):
    src = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n(.*)", src, re.S)
    if not m:
        raise SystemExit("%s: missing front matter" % path)
    meta = {}
    for line in m.group(1).split("\n"):
        if line.strip() and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.split("  #")[0].strip()
    body = m.group(2).strip()
    if body and not body.startswith("<"):
        import markdown  # only needed for posts written in Markdown
        body = markdown.markdown(body, extensions=["tables"])
    slug = os.path.basename(path)[:-3]
    for k in ("title", "date"):
        if not meta.get(k):
            raise SystemExit("%s: '%s' is required" % (path, k))
    if meta.get("category") not in CATEGORIES:
        meta["category"] = "strategy"
    meta.update(slug=slug, body=body,
                read_time=int(meta.get("read_time") or max(1, round(len(re.sub(r"<[^>]+>", " ", body).split()) / 230))),
                featured=meta.get("featured", "").lower() in ("true", "yes", "1"))
    return meta


def load_posts():
    if not os.path.isdir(CONTENT):
        return []
    posts = [parse(os.path.join(CONTENT, f)) for f in sorted(os.listdir(CONTENT)) if f.endswith(".md")]
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def esc(s):
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- list page
def asset(path, up):
    """public/-relative path -> path from a page `up` levels deep; URLs pass through."""
    return path if re.match(r"https?://", path) else up + path


def card(p, up="", extra=""):
    img = ('<div class="news-card-img"><img src="%s" alt="" loading="lazy" decoding="async"></div>' % esc(asset(p["cover"], up))
           if p.get("cover") else '<div class="news-card-img news-card-img--empty"></div>')
    return (
        '<a href="news/%(slug)s.html" class="card news-card" data-cat="%(cat)s"%(extra)s>\n'
        '  %(img)s\n'
        '  <h2>%(title)s</h2>\n'
        '  <p>%(excerpt)s</p>\n'
        '  <span class="news-card-meta"><time datetime="%(date)s">%(nice)s</time> &middot; %(rt)d <span data-i18n="news.minRead">min read</span></span>\n'
        '</a>' % dict(slug=p["slug"], cat=p["category"], catname=CAT_EN[p["category"]], img=img, extra=extra,
                      title=esc(p["title"]), excerpt=esc(p.get("excerpt", "")), date=p["date"],
                      nice=nice_date(p["date"]), rt=p["read_time"]))


def list_block(posts):
    if not posts:
        return '<p class="news-empty">No posts yet.</p>'
    feat = next((p for p in posts if p["featured"]), posts[0])
    counts = {c: sum(1 for p in posts if p["category"] == c) for c in CATEGORIES}
    chips = ['<button type="button" class="news-chip is-active" data-cat="all" aria-pressed="true">'
             '<span data-i18n="news.cat.all">All</span> <span class="news-chip-n">%d</span></button>' % len(posts)]
    for c in CATEGORIES:
        if counts[c]:
            chips.append('<button type="button" class="news-chip" data-cat="%s" aria-pressed="false">'
                         '<span data-i18n="news.cat.%s">%s</span> <span class="news-chip-n">%d</span></button>'
                         % (c, c, CAT_EN[c], counts[c]))
    featured = (
        '<a href="news/%(slug)s.html" class="card news-featured">\n'
        '  <div class="news-featured-img">%(img)s</div>\n'
        '  <div class="news-featured-body">\n'
        '    <h2>%(title)s</h2>\n'
        '    <p>%(excerpt)s</p>\n'
        '    <span class="news-card-meta"><time datetime="%(date)s">%(nice)s</time> &middot; %(rt)d <span data-i18n="news.minRead">min read</span></span>\n'
        '    <span class="news-card-more" data-i18n="news.readMore">Read full report &rarr;</span>\n'
        '  </div>\n'
        '</a>' % dict(slug=feat["slug"], cat=feat["category"], catname=CAT_EN[feat["category"]],
                      img='<img src="%s" alt="" decoding="async">' % esc(feat["cover"]) if feat.get("cover") else "",
                      title=esc(feat["title"]), excerpt=esc(feat.get("excerpt", "")), date=feat["date"],
                      nice=nice_date(feat["date"]), rt=feat["read_time"]))
    return "\n".join([
        "<!-- news:list -->",
        "<!-- GENERATED by tools/build_news.py from content/news/*.md — edit the posts, not this block. -->",
        featured,
        '<div class="news-search-wrap">',
        '<input type="search" id="news-search" class="news-search" placeholder="Search articles" '
        'data-i18n-placeholder="news.search" autocomplete="off">',  # placeholder doubles as the accessible name
        "</div>",
        '<div class="news-filters" role="group" aria-label="Categories" data-i18n-aria-label="news.filterLabel">',
        "\n".join(chips),
        "</div>",
        '<div class="news-grid" id="news-grid" data-page-size="%d">' % PAGE_SIZE,
        # the featured post is also in the grid (hidden until a search or a
        # category filter is active) so every post can be found
        "\n".join(card(p, extra=' data-featured="1" hidden' if p is feat else "") for p in posts),
        "</div>",
        '<p class="news-empty" id="news-empty" hidden data-i18n="news.noResults">No articles found.</p>',
        '<div class="news-more" hidden><button type="button" class="btn btn-outline" id="news-more" data-i18n="news.loadMore">Load more</button></div>',
        "<!-- /news:list -->",
    ])


def write_list(posts):
    path = os.path.join(SITE, "news.html")
    src = open(path, encoding="utf-8").read()
    if not LIST_BLOCK.search(src):
        raise SystemExit("public/news.html: <!-- news:list --> ... <!-- /news:list --> markers not found")
    new = LIST_BLOCK.sub(lambda m: list_block(posts), src, count=1)
    if new != src:
        open(path, "w", encoding="utf-8", newline="\n").write(new)
    print("wrote news.html list (%d posts)" % len(posts))


# ---------------------------------------------------------------- articles
def related(p, posts, n=3):
    same = [q for q in posts if q is not p and q["category"] == p["category"]]
    other = [q for q in posts if q is not p and q["category"] != p["category"]]
    picks = (same + other)[:n]
    return "\n".join(card(q, "../").replace('href="news/', 'href="') for q in picks)


def seo_title(t):
    if "pokerrrr" in t.lower() or len(t) > 46:
        return t
    return t + " — Pokerrrr 2"


def description(p):
    d = p.get("excerpt") or re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p["body"]))).strip()
    d = d.rstrip("…")
    return d if len(d) <= 155 else d[:154].rsplit(" ", 1)[0] + "…"


def body_paths(body):
    """Paths in posts are relative to public/; articles live in public/news/."""
    # every relative src/href except news/... (assets/..., game-rules.html, ...) goes up one level
    body = re.sub(r'((?:src|href)=")(?!https?:|mailto:|#|/|\.\./|news/)', r"\1../", body)
    return re.sub(r'(href=")news/', r"\1", body)


def post_nav(posts, i):
    """Previous = the older post, Next = the newer one (posts are newest first)."""
    def link(q, cls, key, label):
        if not q:
            return '<span class="%s post-nav-empty"></span>' % cls
        img = ('<span class="post-nav-img"><img src="%s" alt="" loading="lazy" decoding="async"></span>'
               % esc(asset(q["cover"], "../")) if q.get("cover") else '<span class="post-nav-img post-nav-img--empty"></span>')
        return ('<a class="%s" href="%s.html">%s<span class="post-nav-text"><span class="post-nav-label" data-i18n="%s">%s</span>'
                '<span class="post-nav-title">%s</span></span></a>' % (cls, q["slug"], img, key, label, esc(q["title"])))
    older = posts[i + 1] if i + 1 < len(posts) else None
    newer = posts[i - 1] if i > 0 else None
    return ('<nav class="post-nav" aria-label="More posts">\n%s\n%s\n</nav>'
            % (link(older, "post-nav-prev", "news.prev", "&larr; Previous"),
               link(newer, "post-nav-next", "news.next", "Next &rarr;")))


def write_articles(posts, d_en, translate, base_url):
    tpl = open(TEMPLATE, encoding="utf-8").read()
    os.makedirs(os.path.join(SITE, "news"), exist_ok=True)
    keep = set()
    for i, p in enumerate(posts):
        url = "%snews/%s" % (base_url, p["slug"])  # extension-less, see tools/clean_urls.py
        og = asset(p["cover"], base_url) if p.get("cover") else base_url + "assets/images/p2-app-icon-512.png"
        ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"],
              "datePublished": p["date"], "author": {"@type": "Organization", "name": p.get("author") or "Pokerrrr"},
              "publisher": {"@type": "Organization", "name": "Mondraw Limited"},
              "mainEntityOfPage": url, "image": og, "description": description(p)}
        out = tpl
        for k, v in {
            "SEO_TITLE": esc(seo_title(p["title"])), "TITLE": esc(p["title"]), "DESCRIPTION": esc(description(p)),
            "CANONICAL": url, "OG_IMAGE": esc(og), "SLUG": p["slug"],
            "JSONLD": json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"),
            "CAT": p["category"], "CAT_NAME": CAT_EN[p["category"]],
            "DATE_ISO": p["date"], "DATE": nice_date(p["date"]), "AUTHOR": esc(p.get("author") or "Pokerrrr"),
            "READ_TIME": str(p["read_time"]), "RELATED": related(p, posts), "POST_NAV": post_nav(posts, i),
            "BODY": body_paths(p["body"]),
        }.items():
            out = out.replace("{{%s}}" % k, v)
        out = translate(out, d_en, set())
        dest = os.path.join(SITE, "news", p["slug"] + ".html")
        open(dest, "w", encoding="utf-8", newline="\n").write(out)
        keep.add(p["slug"] + ".html")
    # remove pages of posts that were deleted from content/news
    for f in os.listdir(os.path.join(SITE, "news")):
        if f.endswith(".html") and f not in keep:
            os.remove(os.path.join(SITE, "news", f))
    print("wrote news/*.html (%d articles)" % len(posts))


def write_redirects(posts):
    lines = ["# GENERATED by tools/build_news.py — old Wix blog URLs -> new News pages."]
    for p in posts:
        m = re.match(r"https?://[^/]+(/single-post/.+)", p.get("old_url", ""))
        if m:
            lines.append("%s /news/%s 301" % (m.group(1), p["slug"]))
    # targets are the final extension-less URLs, so there is no second hop
    lines.append("/news/page/* /news 301")
    # NLH has no game-rules/ page any more: How to Play is the NLH rules page
    for pre in ("", "/zh", "/ja"):
        for ext in ("", ".html"):
            lines.append("%s/game-rules/nlh%s %s/how-to-play 301" % (pre, ext, pre))
    open(os.path.join(SITE, "_redirects"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")


def sitemap_entries(posts, base_url):
    return [("%snews/%s" % (base_url, p["slug"]), p["date"]) for p in posts]


def build(d_en, translate, base_url):
    posts = load_posts()
    write_list(posts)
    write_articles(posts, d_en, translate, base_url)
    write_redirects(posts)
    return posts
