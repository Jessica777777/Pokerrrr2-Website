#!/usr/bin/env python3
"""FAQ screenshots from the old Wix FAQ page (www.pokerrrrapp.com/faq).

The Wix FAQ widget renders its answers with screenshots; the copy we made
for public/faq.html had text only. FAQ_IMAGES below records which Wix image
belongs to which answer block (collected from the live page, 33 images in
14 answers).

  python3 tools/fetch_faq_images.py --insert   # add <img> tags to public/faq.html (no network)
  python3 tools/fetch_faq_images.py            # download images, then fill width/height
                                               # (needs network: run in the Mac terminal)
  python3 tools/build_i18n.py                  # regenerate zh/ja

Images go to public/assets/images/faq/<faq-id>-<n>.<ext>. Already-downloaded
files are skipped, so it is safe to re-run. Standard library only.
"""
import html
import os
import re
import struct
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "public", "faq.html")
OUT_DIR = os.path.join(ROOT, "public", "assets", "images", "faq")
WEB_DIR = "assets/images/faq"

# faq id -> [(block number, wix media id)]. Blocks are the answer's <p> and
# <li> elements in document order, counted from 1; the image is placed at
# the end of that block.
FAQ_IMAGES = {
    "host-01": [(3, "e4fb81_e105a10ffe484c519d891c921a80e561~mv2.png"),
                (4, "e4fb81_ff7584b7cd9a4f5789dc5dd0e925d742~mv2.png"),
                (5, "e4fb81_b5cce1bc88d7482197f4ee320aec1ab8~mv2.png"),
                (6, "e4fb81_6b2033a4ad134a06a1a2f7b39b003d76~mv2.jpg")],
    "host-02": [(2, "41d3cc_2c56fcc92fcb446ab5625fcc4fff92f6~mv2.png"),
                (3, "41d3cc_9be20911cf554144bdf4ecc51c5990aa~mv2.png")],
    "host-03": [(1, "41d3cc_f76abfeae32e4b24afe55ac7749c63b0~mv2.png"),
                (2, "41d3cc_bc9403e078af4eeda1e7c40fb972c49c~mv2.png")],
    "host-04": [(2, "41d3cc_b482f4aaaec743a998f2e035e5a57b0e~mv2.png"),
                (3, "41d3cc_f8bb7173038642cfaf06e55bd29362f3~mv2.png")],
    "rules-10": [(2, "1b80e4_b37e137d155942bea4c0be582128176f~mv2.png")],  # block 2 = royalties line (added by --insert)
    "join-01": [(1, "41d3cc_84a8d247e4f642e8a41829a3d7f5bcfd~mv2.png")],
    "clubs-01": [(1, "41d3cc_33f7964938ed4b018c4ed67b00cb266b~mv2.png"),
                 (2, "41d3cc_5686b7a5f46b45589448d814bc7e91c7~mv2.png")],
    "clubs-02": [(1, "41d3cc_1a48a9a0c7c64853b852dbb90509e670~mv2.png"),
                 (2, "41d3cc_af6f0e335cb3407496ff97ab1a1834a2~mv2.png")],
    "clubs-03": [(1, "41d3cc_d7c2acef815d441a8ff2225324ddeda0~mv2.png"),
                 (2, "41d3cc_36cde6e524cf48638ad8e910ba1c2bb2~mv2.png"),
                 (3, "41d3cc_047bc5f410424082a2df5b7b38e39fbe~mv2.png")],
    "gold-02": [(2, "1b80e4_e6c722796a9f4cb7b161a339178a5941~mv2.png"),
                (3, "1b80e4_b1349b2b0b964d26bc05bdf03b7910e1~mv2.png"),
                (4, "1b80e4_052b3aa527c5441bbff3c04679c830e2~mv2.png"),
                (5, "1b80e4_869181f5b7e741509735cebbb8e85c04~mv2.png")],
    "gold-03": [(2, "41d3cc_262777b34f274095b13cbf4fa921af20~mv2.png"),
                (3, "41d3cc_4360d6793d824a4ebba0f17c98b718b7~mv2.png")],
    "records-01": [(4, "41d3cc_3cabe8dea33a4680ada6addeb4abae49~mv2.png"),
                   (5, "41d3cc_c756b8dc43554517936cd7cbbc1fe2c5~mv2.png"),
                   (11, "41d3cc_3cabe8dea33a4680ada6addeb4abae49~mv2.png"),
                   (12, "41d3cc_c756b8dc43554517936cd7cbbc1fe2c5~mv2.png")],
    "records-02": [(1, "41d3cc_7c98a5b191154eaba7f5cf7120cb9dbb~mv2.png"),
                   (3, "41d3cc_293f6f3cbf494d2bbc0b25c8c669904b~mv2.png")],
    "account-02": [(1, "90f6f1_322c322cfe8d4ac88dc9ffa3748f4717~mv2.jpg"),
                   (2, "90f6f1_7a1ddee4321749fc9e3a4f104dd729b6~mv2.jpg")],
}

# rules-10 on Wix has a "Royalties" line before the royalties table image.
ROYALTIES_P = "<p>Royalties for the bottom, middle and top hands:</p>"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def file_names():
    """media id -> local file name (a repeated image reuses the first name)."""
    names = {}
    for fid, imgs in FAQ_IMAGES.items():
        n = 0
        for _, mid in imgs:
            if mid not in names:
                n += 1
                names[mid] = "%s-%d.%s" % (fid, n, mid.rsplit(".", 1)[1].lower())
    return names


def rd(p):
    return open(p, encoding="utf-8").read()


def wr(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


ITEM_RE = re.compile(r'(<details class="faq-item" id="([^"]+)">.*?<div class="faq-answer">)(.*?)(</div>\s*</details>)', re.S)
BLOCK_RE = re.compile(r"<(p|li)\b[^>]*>(.*?)</\1>", re.S)


def alt_for(fid, text):
    if fid == "rules-10":
        return "OFC royalties table for the bottom, middle and top hands"
    t = html.unescape(re.sub(r"<[^>]+>", "", text)).strip().rstrip(".:")
    if len(t) > 90:
        t = t[:87].rsplit(" ", 1)[0] + "…"
    return "Pokerrrr 2 screenshot: " + t


def insert():
    names = file_names()
    s = rd(PAGE)
    if 'class="faq-shot"' in s:
        print("faq.html already has FAQ images; nothing to do.")
        return

    def fix(m):
        fid, ans = m.group(2), m.group(3)
        if fid not in FAQ_IMAGES:
            return m.group(0)
        if fid == "rules-10" and ROYALTIES_P not in ans:
            first = ans.index("</p>") + 4
            ans = ans[:first] + ROYALTIES_P + ans[first:]
        want = {}
        for blk, mid in FAQ_IMAGES[fid]:
            want.setdefault(blk, []).append(mid)
        out, pos, k = [], 0, 0
        for b in BLOCK_RE.finditer(ans):
            k += 1
            if k not in want:
                continue
            tags = "".join('<img class="faq-shot" src="%s/%s" alt="%s" loading="lazy" decoding="async">' % (
                WEB_DIR, names[mid], html.escape(alt_for(fid, b.group(2)), quote=True)) for mid in want[k])
            if b.group(1) == "li":  # inside the step
                cut = b.end() - len("</li>")
            else:  # right after the paragraph
                cut = b.end()
            out.append(ans[pos:cut] + tags)
            pos = cut
        missing = [b for b in want if b > k]
        if missing:
            sys.exit("%s: answer has only %d blocks, wanted %s" % (fid, k, missing))
        out.append(ans[pos:])
        return m.group(1) + "".join(out) + m.group(4)

    s2 = ITEM_RE.sub(fix, s)
    wr(PAGE, s2)
    print("inserted %d <img> tags into public/faq.html" % s2.count('class="faq-shot"'))


def image_size(path):
    with open(path, "rb") as f:
        head = f.read(26)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                marker, = struct.unpack(">H", f.read(2))
                length, = struct.unpack(">H", f.read(2))
                if 0xFFC0 <= marker <= 0xFFCF and marker not in (0xFFC4, 0xFFC8, 0xFFCC):
                    f.read(1)
                    h, w = struct.unpack(">HH", f.read(4))
                    return w, h
                f.seek(length - 2, 1)
    return None


def download():
    os.makedirs(OUT_DIR, exist_ok=True)
    names = file_names()
    for mid, name in names.items():
        dest = os.path.join(OUT_DIR, name)
        if os.path.exists(dest):
            continue
        # Wix resize endpoint: phone screenshots capped at 750px wide, same format
        url = "https://static.wixstatic.com/media/%s/v1/fit/w_750,h_1600,q_85,enc_auto/%s" % (mid, mid)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            data = urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:  # fall back to the original file
            print("  resize failed (%s), fetching original: %s" % (e, mid))
            req = urllib.request.Request("https://static.wixstatic.com/media/" + mid, headers={"User-Agent": UA})
            data = urllib.request.urlopen(req, timeout=60).read()
        with open(dest, "wb") as f:
            f.write(data)
        print("  %s  %d KB" % (name, len(data) // 1024))

    # width/height on every <img> (avoids layout shift while lazy images load)
    s = rd(PAGE)

    def wh(m):
        tag = m.group(0)
        if " width=" in tag:
            return tag
        src = re.search(r'src="%s/([^"]+)"' % WEB_DIR, tag).group(1)
        size = image_size(os.path.join(OUT_DIR, src))
        if not size:
            return tag
        return tag.replace(' loading=', ' width="%d" height="%d" loading=' % size, 1)

    wr(PAGE, re.sub(r'<img class="faq-shot"[^>]*>', wh, s))
    print("done: %d files in public/assets/images/faq/ — now run python3 tools/build_i18n.py" % len(names))


if __name__ == "__main__":
    if "--insert" in sys.argv:
        insert()
    else:
        download()
