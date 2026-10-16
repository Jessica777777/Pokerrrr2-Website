"""Python port of game-rules.html's renderBlock()/card()/hand()/text() --
must stay class-for-class and tag-for-tag identical to the JS version so
css/style.css styles the static build exactly like the old JS-rendered page.
"""
import html
import re

SUIT = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_FILE = {"s": "spade", "h": "heart", "d": "diamond", "c": "club"}
RED_SUIT = {"h", "d"}
PLACEHOLDER_RE = re.compile(r"%(?:\d+\$)?[sd]")

# v35: real card-set artwork (assets/images/cards/, from the user's
# 素材/POKER/V08 material) in place of the old CSS-text rank/suit and the
# inline jester SVG -- kept identical to game-rules.html's inline script so
# the static pages this renders match the dynamic page exactly.
CARD_IMG_BASE = "assets/images/cards/"


def esc(s):
    return html.escape(s, quote=True)


def esc_text(s):
    # text node content (not an attribute) -- matches JS's textContent
    # behavior, which never turns a literal '/" into an HTML entity.
    return html.escape(s, quote=False)


def card_html(code, img_base=CARD_IMG_BASE):
    # v36 -- "." is a second, distinct placeholder from "_": "_" is consumed
    # by hand_html() itself to split codes into before/after groups and never
    # reaches here, while "." passes straight through as an ordinary code so
    # it renders a blank card-shaped slot *inside* a group (the empty space
    # left behind by a card that moved elsewhere -- see the Rummy "feature
    # instructions" examples in data/game-rules.json).
    if code in ("_", "."):
        return '<span class="gr-card gap"></span>'
    if code == "?":
        return '<span class="gr-card back"></span>'
    # v36 -- a trailing "^" marks a card as the one just added/utilized in a
    # before -> after demo, matching the real app's UI which visually raises
    # those cards instead of leaving every card flush with the rest of the
    # group (game-rules-static-plan.md pending-tasks item 0).
    raised = code.endswith("^")
    if raised:
        code = code[:-1]
    raised_cls = " is-raised" if raised else ""
    rank, suit = code[:-1], code[-1]
    if rank == "X":
        return (
            '<span class="gr-card joker%s" data-suit="%s">'
            '<img src="%sjoker.png" alt="Joker"></span>'
        ) % (raised_cls, esc(suit), img_base)
    is_red = suit in RED_SUIT
    cls = ("gr-card is-red" if is_red else "gr-card") + raised_cls
    label = "10" if rank == "T" else rank
    rank_file = "%s%s_%s.png" % (img_base, label, "r" if is_red else "b")
    suit_file = "%s%s.png" % (img_base, SUIT_FILE.get(suit, ""))
    return (
        '<span class="%s">'
        '<img class="gr-card-rank" src="%s" alt="%s">'
        '<img class="gr-card-suit" src="%s" alt="%s"></span>'
    ) % (cls, esc(rank_file), esc(label), esc(suit_file), esc(SUIT.get(suit, "")))


def _group_inner_html(g, img_base):
    # v36 -- "/" is a row-break *within* one group's own cards (e.g. the
    # Rummy "reform sets" example, which shows each side as a 3-row grid
    # rather than one flowing row): emit a 100%-wide zero-height flex item
    # so .gr-hand-group (flex-wrap: wrap) wraps onto a new line at exactly
    # this point, without adding a visible card slot. Never produced by
    # card_html() itself since it is consumed here, before any code reaches
    # that function.
    parts = []
    for c in g:
        if c == "/":
            parts.append('<span class="gr-hand-break" aria-hidden="true"></span>')
        else:
            parts.append(card_html(c, img_base))
    return "".join(parts)


def hand_html(codes, img_base=CARD_IMG_BASE):
    """Split on the "_" placeholder into groups: 1 group -> plain flat hand
    (unchanged); 2 groups -> a "before -> after" demo, gold arrow between two
    bordered boxes; 3+ groups -> independent example hands side by side, each
    boxed, plain gap (no arrow) between them. Mirrors game-rules.html's JS
    hand() exactly. See card_html() for the "." (blank slot) and "^" (raised
    card) placeholders usable within a group, and _group_inner_html() above
    for the "/" (row-break within a group) placeholder.
    """
    groups = [[]]
    for c in (codes or []):
        if c == "_":
            groups.append([])
        else:
            groups[-1].append(c)
    groups = [g for g in groups if g] or [[]]

    if len(groups) == 1:
        return '<div class="gr-hand">%s</div>' % _group_inner_html(groups[0], img_base)

    # v36 -- a group using "/" row-breaks is laid out as a multi-row grid
    # (e.g. Rummy's "reform sets" example), which is too wide for a
    # before -> after pair to sit side by side within the panel's 900px
    # reading column. Stack them instead, with the arrow rotated to point
    # down at the second grid rather than sideways at empty space.
    is_grid = any("/" in g for g in groups)

    is_pair = len(groups) == 2

    parts = []
    for i, g in enumerate(groups):
        if i > 0:
            if is_pair:
                arrow_cls = "gr-hand-arrow gr-hand-arrow--down" if is_grid else "gr-hand-arrow"
                parts.append('<span class="%s" aria-hidden="true">&#8594;</span>' % arrow_cls)
            else:
                parts.append('<span class="gr-hand-gap" aria-hidden="true"></span>')
        parts.append('<div class="gr-hand-group">%s</div>' % _group_inner_html(g, img_base))
    # v36 -- "is-pair" (only the before -> after 2-group case) is a narrower
    # hook than "is-grouped" (every multi-group hand, including blackjack's
    # independent-hands-side-by-side case) so the new "stack + arrow points
    # down" mobile treatment below only ever applies to a real before/after
    # demo, never to unrelated multi-hand examples that happen to flex-wrap
    # onto their own lines already.
    hand_cls = "gr-hand is-grouped" + (" is-pair" if is_pair else "") + (" is-grid" if is_grid else "")
    return '<div class="%s">%s</div>' % (hand_cls, "".join(parts))


def txt(node, lang):
    if node is None:
        return ""
    return node.get(lang) or node.get("en") or ""


def text_html(node, lang):
    """Escape then wrap %s/%d/%1$s placeholders in <span class="gr-ph">."""
    value = txt(node, lang)
    escaped = esc_text(value)
    out = []
    last = 0
    for m in PLACEHOLDER_RE.finditer(escaped):
        out.append(escaped[last:m.start()])
        out.append('<span class="gr-ph">%s</span>' % m.group(0))
        last = m.end()
    out.append(escaped[last:])
    return "".join(out)


def render_block(b, lang, game_rules, img_base=CARD_IMG_BASE):
    t = b["t"]
    if t == "h2":
        return '<div class="gr-sec-head"><h2>%s</h2></div>' % text_html(b["v"], lang)
    if t == "h3":
        return "<h3>%s</h3>" % text_html(b["v"], lang)
    if t == "sub":
        return '<p class="gr-sub">%s</p>' % text_html(b["v"], lang)
    if t == "p":
        return "<p>%s</p>" % text_html(b["v"], lang)
    if t == "hand":
        return hand_html(b["v"], img_base)
    if t == "steps":
        rows = []
        for s in b["v"]:
            bodies = "".join(
                '<p class="gr-step-body">%s</p>' % text_html(line, lang)
                for line in s["body"]
            )
            rows.append(
                '<div class="gr-step"><span class="gr-step-name">%s</span><div>%s</div></div>'
                % (text_html(s["name"], lang), bodies)
            )
        return '<div class="gr-steps">%s</div>' % "".join(rows)
    if t == "vrows":
        rows = []
        for r in b["v"]:
            rows.append(
                '<div class="gr-vrow">%s<span class="gr-amount">%s</span></div>'
                % (hand_html(r["cards"], img_base), text_html(r["amount"], lang))
            )
        return '<div class="gr-vrows">%s</div>' % "".join(rows)
    if t == "paytable":
        rows = []
        for r in b["v"]:
            cards_html = hand_html(r["cards"], img_base) if r.get("cards") else "<span></span>"
            rows.append(
                '<div class="gr-prow"><span class="gr-kind">%s</span>%s<span class="gr-amount">%s</span></div>'
                % (text_html(r["kind"], lang), cards_html, text_html(r["amount"], lang))
            )
        return '<div class="gr-vrows">%s</div>' % "".join(rows)
    if t == "ranking":
        cap = '<p class="gr-rank-cap">%s</p>' % text_html(game_rules["rankingCaption"], lang)
        trs = []
        for r in game_rules["ranking"]:
            trs.append(
                '<tr><th scope="row">%s</th><td>%s</td></tr>'
                % (text_html(r["name"], lang), hand_html(r["cards"], img_base))
            )
        table = (
            '<div class="gr-table-scroll"><table class="gr-rank-table"><tbody>%s</tbody></table></div>'
            % "".join(trs)
        )
        return "<div>%s%s</div>" % (cap, table)
    return ""


def render_blocks(blocks, lang, game_rules, img_base=CARD_IMG_BASE):
    return "".join(render_block(b, lang, game_rules, img_base) for b in blocks)
