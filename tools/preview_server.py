#!/usr/bin/env python3
"""
Local preview that serves URLs the way Cloudflare does in production:
/about -> about.html, /zh/ -> zh/index.html (page links are extension-less,
see tools/clean_urls.py, so plain `python3 -m http.server` would 404 them).

    python3 tools/preview_server.py        # http://localhost:8000
    python3 tools/preview_server.py 8080
"""
import http.server
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def translate_path(self, path):
        p = super().translate_path(path)
        if not os.path.exists(p) or (os.path.isdir(p) and not os.path.exists(os.path.join(p, "index.html"))):
            if os.path.exists(p.rstrip("/") + ".html"):
                return p.rstrip("/") + ".html"
        return p


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("http://localhost:%d" % port)
    http.server.ThreadingHTTPServer(("", port), Handler).serve_forever()
