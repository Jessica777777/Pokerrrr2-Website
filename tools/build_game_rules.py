#!/usr/bin/env python3
"""
Build the 18 per-game static pages (<lang>/game-rules/<id>.html) and 3
static overview pages (<lang>/game-rules.html), replacing the old single
dynamic game-rules.html?game=<id>&lang=xx page.

Imported by tools/build_i18n.py; not meant to be run standalone (it needs
the i18n dict `d` that build_i18n.py's load_dict() already parses).

Source of truth:
  * data/game-rules.json              -> per-game rules content (blocks)
  * js/i18n.js                        -> gameRules.* / howToPlay.more.* /
                                          common.* strings, all 3 languages
  * tools/templates/game-rule.html    -> per-game page template
  * tools/templates/game-rules-overview.html -> overview page template
  * tools/game_rules_render.py        -> renders `blocks` -> HTML (ported
                                          from the old page's JS renderer)

See claude/game-rules-static-plan.md for the full background/plan.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_rules_render as render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Generated pages go to the site root (public/, the deploy output directory);
# sources (data/, tools/templates/) stay at the repo root.
SITE = os.path.join(ROOT, "public")

GAMES = ["nlh", "plo", "stud", "blackjack", "rummy", "ginrummy"]
LANGS = ["en", "zh", "ja"]
HTML_LANG = {"en": "en", "zh": "zh-Hant", "ja": "ja"}
DIR = {"en": "", "zh": "zh/", "ja": "ja/"}
LANG_SWITCH_LABEL = {"en": "EN", "zh": "中", "ja": "日"}

# Per-game pages live one level deeper (game-rules/<id>.html, or
# <lang>/game-rules/<id>.html) than the already-built root/zh/ja pages, so
# shared assets (css/js/assets) need one more "../" than those pages do.
UP_ASSET = {"en": "../", "zh": "../../", "ja": "../../"}
# But links back to index/about/faq/how-to-play only need to escape the
# game-rules/ subfolder to land back in the right language folder -- that's
# "../" for every language (confirmed against the already-built
# zh/how-to-play.html, which uses bare same-directory filenames for its own
# page-to-page nav: the lang folder itself needs no further prefixing).
UP_PAGE = "../"

# Hardcoded to match the small kicker tag inside each per-game hero banner
# image, ported verbatim from game-rules.html's JS (UI.tabsGroupLabel) --
# this is NOT the per-game `group` field in game-rules.json (that field
# exists in the data but was never actually used by the old renderer).
TABS_GROUP_LABEL = {"en": "Game Rules", "zh": "遊戲規則", "ja": "ゲームルール"}


def esc_attr(v):
    return v.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def esc_text(v):
    return v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def t(d, lang, key):
    """Look up an i18n key for `lang` ('en'/'zh'/'ja'), used by build_i18n's dict."""
    val = d[lang].get(key)
    if val is None:
        raise KeyError("missing i18n key %r for lang %r" % (key, lang))
    return val


# Absolute URLs (canonical / hreflang / sitemap) are extension-less, see
# tools/clean_urls.py. Relative links in the pages are cleaned afterwards by
# clean_urls.clean_site(), so they can keep their .html file names here.
def game_url(gid, lang, base_url):
    return base_url + DIR[lang] + "game-rules/" + gid


def overview_url(lang, base_url):
    return base_url + DIR[lang] + "game-rules"


def hreflang_block(urls, current_lang):
    lines = ['<link rel="canonical" href="%s">' % urls[current_lang]]
    for l in LANGS:
        lines.append('<link rel="alternate" hreflang="%s" href="%s">' % (HTML_LANG[l], urls[l]))
    lines.append('<link rel="alternate" hreflang="x-default" href="%s">' % urls["en"])
    return lines


def lang_menu_html(make_href, current_lang):
    links = []
    for l in LANGS:
        links.append(
            '          <a href="%s" data-lang="%s" hreflang="%s" lang="%s"%s>%s</a>' % (
                esc_attr(make_href(l)), l, HTML_LANG[l], HTML_LANG[l],
                ' class="active" aria-current="true"' if l == current_lang else "",
                LANG_SWITCH_LABEL[l])
        )
    return "\n".join(links)


def hero_banner_html(game, lang, up_asset, h1):
    # The banner now carries the page's single <h1> as live ivory text, so the
    # background photo is the only image here.
    bg = up_asset + game["bg"]
    return (
        '<div class="gr-hero-banner" style="background-image:url(\'%s\')">'
        '<div class="gr-hero-banner-inner">'
        '<h1 class="gr-hero-banner-title">%s</h1>'
        '</div></div>'
    ) % (esc_attr(bg), esc_text(h1))


def tabs_html(games, current_id, lang):
    # Sibling pages in the SAME game-rules/ folder -- bare filename, no
    # prefix needed (same reasoning as other same-folder page links).
    out = []
    for g in games:
        selected = g["id"] == current_id
        href = g["id"] + ".html"
        out.append(
            '<a href="%s" class="gr-tab" role="tab" data-game="%s" aria-selected="%s"%s>%s</a>' % (
                esc_attr(href), g["id"], "true" if selected else "false",
                ' aria-current="page"' if selected else "",
                esc_text(render.txt(g["tab"], HTML_LANG[lang])))
        )
    return "\n      ".join(out)


def feature_card_html(gid, lang, up_asset, d):
    title = t(d, lang, "howToPlay.more.card.%s.title" % gid)
    img_alt = t(d, lang, "howToPlay.more.card.%s.imgAlt" % gid)
    view_rules = t(d, lang, "howToPlay.more.viewRules")
    logo_cls = "feature-card-logo" + (" feature-card-logo--stud" if gid == "stud" else "")
    # game-rules/ sits beside this overview page in the same lang folder --
    # bare relative path, no prefix (same reasoning as how-to-play.html's
    # own 6 card links, rewritten the same way in build_i18n.py).
    href = "game-rules/" + gid + ".html"
    return """        <a href="%s" class="feature-card" aria-label="%s">
          <div class="feature-card-media">
            <img class="feature-card-img is-wide" src="%sassets/images/game-rules/table-%s.jpg" alt="%s">
            <h2 class="feature-card-logo-heading"><img class="%s" src="%sassets/images/game-rules/title-%s.png" alt="%s"></h2>
          </div>
          <div class="feature-card-body feature-card-body--cta">
            <span class="btn btn-outline btn-sm">%s</span>
          </div>
        </a>""" % (esc_attr(href), esc_attr(title), up_asset, gid, esc_attr(img_alt),
                   logo_cls, up_asset, gid, esc_attr(title), esc_text(view_rules))


def fill(template, values):
    out = template
    for k, v in values.items():
        out = out.replace("{{%s}}" % k, v)
    return out


def common_values(lang, up_asset, d):
    return {
        "BRAND_NAME": esc_text(t(d, lang, "common.nav.brandName")),
        "BRAND_SHORT": esc_text(t(d, lang, "common.nav.brandShort")),
        "BRAND_ALT": esc_attr(t(d, lang, "common.nav.brandAlt")),
        "NAV_HOME": esc_text(t(d, lang, "common.nav.home")),
        "NAV_HOWTOPLAY": esc_text(t(d, lang, "common.nav.howToPlay")),
        "NAV_ABOUT": esc_text(t(d, lang, "common.nav.about")),
        "NAV_FAQ": esc_text(t(d, lang, "common.nav.faq")),
        "NAV_NEWS": esc_text(t(d, lang, "common.nav.news")),
        "NAV_STORE": esc_text(t(d, lang, "common.nav.store")),
        "NAV_DOWNLOAD": esc_text(t(d, lang, "common.nav.downloadBtn")),
        "LANG_LABEL": LANG_SWITCH_LABEL[lang],
        "STORE_APPLE_ARIA": esc_attr(t(d, lang, "common.store.appleAria")),
        "STORE_GOOGLE_ARIA": esc_attr(t(d, lang, "common.store.googleAria")),
        "STORE_APPLE_SMALL": {"en": "Download on the", "zh": "Download on the", "ja": "Download on the"}[lang],
        "STORE_GOOGLE_SMALL": {"en": "GET IT ON", "zh": "GET IT ON", "ja": "GET IT ON"}[lang],
        "CTA_TITLE": esc_text(t(d, lang, "index.cta.title")),
        "CTA_DESC": esc_text(t(d, lang, "howToPlay.cta.desc")),
        "AGE_BADGE": esc_text(t(d, lang, "howToPlay.cta.ageBadge")),
        "CTA_IMG_ALT": esc_attr(t(d, lang, "gameRules.cta.imgAlt")),
        "CTA_TAG": esc_text(t(d, lang, "gameRules.cta.tag")),
        "CTA_CLOSING": esc_text(t(d, lang, "index.cta.closing")),
        "FOOTER_DISCLAIMER": esc_text(t(d, lang, "common.footer.disclaimer")),
        "FOOTER_NAV_HEADING": esc_text(t(d, lang, "common.footer.navHeading")),
        "FOOTER_FOLLOW_HEADING": esc_text(t(d, lang, "common.footer.followHeading")),
        "FOOTER_CONTACT_LINE": t(d, lang, "common.footer.contactLine"),
        "FOOTER_RIGHTS": esc_text(t(d, lang, "common.footer.rights")),
    }


def load_game_rules():
    with open(os.path.join(ROOT, "data", "game-rules.json"), encoding="utf-8") as f:
        return json.load(f)


def build_game_pages(d, base_url):
    """Writes the 18 <lang>/game-rules/<id>.html pages. Returns a list of
    (lang, gid, loc_path) tuples for sitemap use."""
    gr = load_game_rules()
    games = gr["games"]
    template = open(os.path.join(ROOT, "tools/templates/game-rule.html"), encoding="utf-8").read()
    written = []
    for game in games:
        gid = game["id"]
        for lang in LANGS:
            up_asset = UP_ASSET[lang]
            common = common_values(lang, up_asset, d)
            urls = {l: game_url(gid, l, base_url) for l in LANGS}
            head = hreflang_block(urls, lang)
            # Relative cross-language link: escape this per-game page's own
            # lang folder entirely (UP_ASSET[lang], same depth as shared
            # assets), then back down into the target language's own
            # game-rules/<id>.html.
            lang_menu = lang_menu_html(
                lambda l, gid=gid: UP_ASSET[lang] + DIR[l] + "game-rules/" + gid + ".html", lang)
            panel_html = render.render_blocks(game["blocks"], HTML_LANG[lang], gr, up_asset + "assets/images/cards/")
            values = dict(common)
            values.update({
                "HTML_LANG": HTML_LANG[lang],
                "STATIC_LANG": lang,
                "UP": up_asset,
                "UP_PAGE": UP_PAGE,
                "TITLE": esc_text(t(d, lang, "gameRules.%s.head.title" % gid)),
                "DESCRIPTION": esc_attr(t(d, lang, "gameRules.%s.head.description" % gid)),
                "CANONICAL": esc_attr(urls[lang]),
                "HREFLANG_EN": esc_attr(urls["en"]),
                "HREFLANG_ZH": esc_attr(urls["zh"]),
                "HREFLANG_JA": esc_attr(urls["ja"]),
                "LANG_MENU": lang_menu,
                "BACK_HREF": UP_PAGE + "how-to-play.html#more-games",
                "BACK_LABEL": esc_text(t(d, lang, "gameRules.hero.back")),
                "SWITCH_ARIA": esc_attr(t(d, lang, "gameRules.switchAria")),
                "TABS_HTML": tabs_html(games, gid, lang),
                "HERO_BANNER_HTML": hero_banner_html(game, lang, up_asset, t(d, lang, "gameRules.%s.h1" % gid)),
                "PANEL_HTML": panel_html,
            })
            out = fill(template, values)
            dest = os.path.join(SITE, DIR[lang], "game-rules", gid + ".html")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w", encoding="utf-8").write(out)
            written.append((lang, gid, os.path.relpath(dest, SITE)))
    return written


def build_overview_pages(d, base_url):
    """Writes the 3 <lang>/game-rules.html overview pages. Returns a list of
    (lang, loc_path) tuples for sitemap use."""
    gr = load_game_rules()
    games = gr["games"]
    template = open(os.path.join(ROOT, "tools/templates/game-rules-overview.html"), encoding="utf-8").read()
    written = []
    for lang in LANGS:
        up = "" if lang == "en" else "../"  # same depth as how-to-play.html etc.
        common = common_values(lang, up, d)
        urls = {l: overview_url(l, base_url) for l in LANGS}
        lang_menu = lang_menu_html(
            lambda l: ("" if lang == "en" else "../") + DIR[l] + "game-rules.html", lang)
        cards = "\n".join(feature_card_html(gid, lang, up, d) for gid in GAMES)
        values = dict(common)
        values.update({
            "HTML_LANG": HTML_LANG[lang],
            "STATIC_LANG": lang,
            "UP": up,
            # overview pages sit next to index.html etc. in their language folder
            "UP_PAGE": "",
            "TITLE": esc_text(t(d, lang, "gameRules.head.title")),
            "DESCRIPTION": esc_attr(t(d, lang, "gameRules.head.description")),
            "CANONICAL": esc_attr(urls[lang]),
            "HREFLANG_EN": esc_attr(urls["en"]),
            "HREFLANG_ZH": esc_attr(urls["zh"]),
            "HREFLANG_JA": esc_attr(urls["ja"]),
            "LANG_MENU": lang_menu,
            "BACK_LABEL": esc_text(t(d, lang, "gameRules.hero.back")),
            "EYEBROW": esc_text(t(d, lang, "gameRules.hero.eyebrow")),
            "H1": esc_text(t(d, lang, "gameRules.hero.title")),
            "HERO_DESC": esc_text(t(d, lang, "gameRules.hero.desc")),
            "CARDS_HTML": cards,
        })
        out = fill(template, values)
        dest = os.path.join(SITE, DIR[lang], "game-rules.html")
        open(dest, "w", encoding="utf-8").write(out)
        written.append((lang, os.path.relpath(dest, SITE)))
    return written


def sitemap_entries(base_url):
    """(loc, {lang: alt_url}) pairs for all 18 game pages + 3 overviews, for
    write_sitemap() in build_i18n.py to fold into sitemap.xml."""
    entries = []
    for gid in GAMES:
        for lang in LANGS:
            entries.append((game_url(gid, lang, base_url), {l: game_url(gid, l, base_url) for l in LANGS}))
    for lang in LANGS:
        entries.append((overview_url(lang, base_url), {l: overview_url(l, base_url) for l in LANGS}))
    return entries


def build(d, base_url):
    pages = build_game_pages(d, base_url)
    overviews = build_overview_pages(d, base_url)
    for lang, gid, path in pages:
        print("wrote", path)
    for lang, path in overviews:
        print("wrote", path)
    return pages, overviews
