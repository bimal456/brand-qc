#!/usr/bin/env python3
"""
Step 4 self-check: render every built page at 375px and 1366px with Playwright.

Usage: python3 design_check.py <project> [--shots]

Checks per page and width:
  - horizontal overflow (page wider than the viewport; .tbl scroll boxes are allowed)
  - JS console errors and failed asset requests
  - images: non-WebP, missing alt, missing width/height
  - header carries no page links (only the play-path buttons and the logo)
  - every href with "#", every play link without rel=nofollow
  - h1 count and heading levels (no h4 before h1, no skips)
With --shots, saves full-page screenshots to <project>/design/shots/<page>-<width>.png.
Exit 1 on any FAIL.
"""
import http.server
import json
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright


def serve(root):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def log_message(self, *a):
            pass

        def send_head(self):
            # clean URLs: /bonus -> /bonus.html
            p = self.path.split("?")[0]
            if p != "/" and not os.path.splitext(p)[1] and os.path.exists(os.path.join(root, p.lstrip("/") + ".html")):
                self.path = p + ".html"
            return super().send_head()
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


JS = r"""
() => {
  const r = {};
  const de = document.documentElement;
  r.overflow = Math.max(de.scrollWidth, document.body.scrollWidth) - window.innerWidth;
  r.wide = [...document.querySelectorAll('body *')].filter(e => {
     if (e.closest('.tbl')) return false;
     const b = e.getBoundingClientRect(); return b.right > window.innerWidth + 1 && b.width > 0;
  }).slice(0,5).map(e => e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : ''));
  r.h1 = document.querySelectorAll('h1').length;
  let prev = 0; r.skips = [];
  document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(h => { const l = +h.tagName[1]; if (prev && l > prev + 1) r.skips.push('H'+prev+'>H'+l); if (!prev && l > 1) r.skips.push('first heading H'+l); prev = l; });
  r.hash = [...document.querySelectorAll('a[href*="#"]')].map(a => a.getAttribute('href')).slice(0,5);
  r.headerLinks = [...document.querySelectorAll('header a')].map(a => (a.getAttribute('href')||'')).filter(h => h.replace(/\/$/,'') !== PLAY && !/^\/([a-z]{2}(-[a-z]{2})?\/?)?$/.test(h));
  const foot = document.querySelector('footer');
  r.foot18 = !!foot && foot.textContent.includes('18+');
  r.footExt = foot ? [...foot.querySelectorAll('a[href^="http"]')].length : 0;
  r.internal = [...new Set([...document.querySelectorAll('a[href^="/"]')].map(a => a.getAttribute('href').split('?')[0].replace(/\/$/,'') || '/'))];
  r.imgs = [...document.querySelectorAll('img')].map(i => ({src: i.getAttribute('src')||'', alt: i.getAttribute('alt'), w: i.getAttribute('width'), h: i.getAttribute('height')}));
  r.playNoNofollow = [...document.querySelectorAll('a')].filter(a => (a.getAttribute('href')||'').replace(/\/$/,'') === PLAY && !(a.getAttribute('rel')||'').includes('nofollow')).length;
  return r;
}
"""


def main():
    proj = sys.argv[1]
    shots = "--shots" in sys.argv
    site = json.load(open(os.path.join(proj, "site.json"), encoding="utf-8"))
    play = site.get("play_path", "/play").rstrip("/")
    build = os.path.join(proj, "build")
    pages = []
    for root, _, files in os.walk(build):
        for f in files:
            if f.endswith(".html") and f != "404.html":
                rel = os.path.relpath(os.path.join(root, f), build).replace(os.sep, "/")
                url = "/" + (rel[:-len("index.html")] if rel.endswith("index.html") else rel[:-5])
                pages.append(url.rstrip("/") or "/")
    srv = serve(build)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    if shots:
        sd = os.path.join(proj, "design", "shots")
        os.makedirs(sd, exist_ok=True)
        for f in os.listdir(sd):  # stale shots of removed pages
            if f.endswith(".png"):
                os.remove(os.path.join(sd, f))
    fails, reviews = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for width in (375, 1366):
            ctx = b.new_context(viewport={"width": width, "height": 900})
            for url in sorted(pages):
                pg = ctx.new_page()
                errs = []
                pg.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" else None)
                pg.on("requestfailed", lambda r, errs=errs: errs.append("failed " + r.url))
                pg.on("response", lambda r, errs=errs: errs.append(f"{r.status} {r.url}") if r.status >= 400 else None)
                pg.goto(base + url, wait_until="networkidle")
                r = pg.evaluate(JS.replace("PLAY", json.dumps(play)))
                tag = f"{url} @{width}"
                if r["overflow"] > 1:
                    fails.append(f"{tag}: horizontal overflow {r['overflow']}px ({', '.join(r['wide'])})")
                if errs:
                    fails.append(f"{tag}: console/network errors: {'; '.join(errs[:3])}")
                if width == 1366:
                    if r["h1"] != 1:
                        fails.append(f"{url}: {r['h1']} h1 tags")
                    if r["skips"]:
                        fails.append(f"{url}: heading order {', '.join(r['skips'][:3])}")
                    if r["hash"]:
                        fails.append(f"{url}: href with #: {', '.join(r['hash'])}")
                    if r["headerLinks"]:
                        reviews.append(f"{url}: header has page links {r['headerLinks'][:4]} (header should carry only logo + Login/Register)")
                    if not r["foot18"]:
                        fails.append(f"{url}: no 18+ in footer")
                    if not r["footExt"]:
                        fails.append(f"{url}: no responsible-gambling links in footer")
                    missing = [u for u in r["internal"] if u != play and not u.startswith("/assets") and u not in pages]
                    if missing:
                        reviews.append(f"{url}: links to pages not built yet: {', '.join(missing[:6])}")
                    if r["playNoNofollow"]:
                        fails.append(f"{url}: {r['playNoNofollow']} play links without nofollow")
                    for i in r["imgs"]:
                        if i["src"] and not i["src"].split("?")[0].lower().endswith((".webp", ".svg")):
                            fails.append(f"{url}: non-WebP image {i['src']}")
                        if not i["alt"]:
                            fails.append(f"{url}: image without alt {i['src']}")
                        if not (i["w"] and i["h"]):
                            reviews.append(f"{url}: image without width/height {i['src']}")
                if shots:
                    name = (url.strip("/").replace("/", "_") or "home") + f"-{width}.png"
                    pg.screenshot(path=os.path.join(proj, "design", "shots", name), full_page=True)
                pg.close()
            ctx.close()
        b.close()
    srv.shutdown()
    verdict = "FAIL" if fails else ("REVIEW" if reviews else "PASS")
    print(f"{verdict} | {len(pages)} pages x 2 widths")
    for x in fails:
        print("  FAIL:", x)
    for x in reviews:
        print("  REVIEW:", x)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
