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
  - image sharpness for 2x screens: file narrower than its display size = FAIL (upscaled),
    narrower than 2x display size = REVIEW (soft on retina/phones)
  - text walls: longest stretch of <main> at 1366px with no visual (image, svg, video or
    [data-visual] block at least 80px tall): over 1200px = REVIEW, over 1800px = FAIL
  - the same hero image on more than one page = REVIEW
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
  r.internal = [...new Set([...document.querySelectorAll('main a[href^="/"]')].map(a => a.getAttribute('href').split('?')[0].replace(/\/$/,'') || '/'))];
  r.imgs = [...document.querySelectorAll('img')].map(i => ({src: i.getAttribute('src')||'', alt: i.getAttribute('alt'), w: i.getAttribute('width'), h: i.getAttribute('height')}));
  r.res = [...document.querySelectorAll('main img, .hero img')].filter(i => i.naturalWidth && i.getBoundingClientRect().width >= 60)
     .map(i => ({src: i.getAttribute('src'), n: i.naturalWidth, d: Math.round(i.getBoundingClientRect().width)}));
  const main = document.querySelector('main');
  if (main) {
    const mb = main.getBoundingClientRect(), top0 = mb.top + scrollY, bot0 = mb.bottom + scrollY;
    const vis = [...main.querySelectorAll('img, svg, video, canvas, picture, [data-visual]')]
      .map(e => e.getBoundingClientRect()).filter(b => b.height >= 80 && b.width >= 80)
      .map(b => [b.top + scrollY, b.bottom + scrollY]).sort((a, b) => a[0] - b[0]);
    let cur = top0, gap = 0, at = 0;
    for (const [t, bt] of vis) { if (t - cur > gap) { gap = t - cur; at = cur - top0; } cur = Math.max(cur, bt); }
    if (bot0 - cur > gap) { gap = bot0 - cur; at = cur - top0; }
    r.gap = Math.round(gap); r.gapAt = Math.round(at); r.mainH = Math.round(bot0 - top0);
  }
  const hi = document.querySelector('.hero img');
  r.hero = hi ? hi.getAttribute('src') : '';
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
    heroes = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for width in (375, 1366):
            ctx = b.new_context(viewport={"width": width, "height": 900})
            for url in sorted(pages):
                pg = ctx.new_page()
                errs = []
                pg.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" else None)
                ext = []
                pg.on("requestfailed", lambda r, errs=errs, ext=ext: (ext if not r.url.startswith(base) else errs).append("failed " + r.url))
                pg.on("response", lambda r, errs=errs: errs.append(f"{r.status} {r.url}") if r.status >= 400 else None)
                pg.goto(base + url, wait_until="networkidle")
                pg.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
                pg.wait_for_load_state("networkidle")
                r = pg.evaluate(JS.replace("PLAY", json.dumps(play)))
                tag = f"{url} @{width}"
                if r["overflow"] > 1:
                    fails.append(f"{tag}: horizontal overflow {r['overflow']}px ({', '.join(r['wide'])})")
                errs = [e for e in errs if base in e or not e.startswith(("failed", "4", "5"))]
                if errs:
                    fails.append(f"{tag}: console/network errors: {'; '.join(errs[:3])}")
                if ext and width == 1366:
                    reviews.append(f"{url}: external assets not loaded here (fine if they load live, e.g. web fonts): {', '.join(sorted(set(e.split('/')[2] for e in ext if '//' in e)))}")
                if width == 1366:
                    if r["h1"] != 1:
                        fails.append(f"{url}: {r['h1']} h1 tags")
                    if r["skips"]:
                        fails.append(f"{url}: heading order {', '.join(r['skips'][:3])}")
                    if r["hash"]:
                        fails.append(f"{url}: href with #: {', '.join(r['hash'])}")
                    if r["headerLinks"]:
                        reviews.append(f"{url}: header has page links {r['headerLinks'][:4]} (fine when the original brand site has this nav; otherwise header carries only logo + Login/Register)")
                    if not r["foot18"]:
                        fails.append(f"{url}: no 18+ in footer")
                    if not r["footExt"]:
                        fails.append(f"{url}: no responsible-gambling links in footer")
                    missing = [u for u in r["internal"] if u != play and not u.startswith("/assets") and u not in pages]
                    if missing:
                        reviews.append(f"{url}: links to pages not built yet: {', '.join(missing[:6])}")
                    if r["playNoNofollow"]:
                        fails.append(f"{url}: {r['playNoNofollow']} play links without nofollow")
                    up = [i for i in r.get("res", []) if i["n"] < i["d"]]
                    soft = [i for i in r.get("res", []) if i["d"] <= i["n"] < 2 * i["d"]]
                    if up:
                        fails.append(f"{url}: {len(up)} image(s) upscaled (file narrower than shown), e.g. "
                                     + ", ".join(f"{i['src']} {i['n']}px shown at {i['d']}px" for i in up[:3]))
                    if soft:
                        reviews.append(f"{url}: {len(soft)} image(s) soft on 2x screens (file under 2x display width), e.g. "
                                       + ", ".join(f"{i['src']} {i['n']}px for {i['d']}px (needs {2 * i['d']}px)" for i in soft[:3]))
                    if r.get("gap", 0) > 1200:
                        (fails if r["gap"] > 1800 else reviews).append(
                            f"{url}: {r['gap']}px of main content without any visual (starts {r['gapAt']}px into main, main is {r['mainH']}px); "
                            "add an image or a CSS visual block (design/images.json)")
                    if r.get("hero"):
                        heroes.setdefault(r["hero"], []).append(url)
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
    for src, urls in heroes.items():
        if len(urls) > 1:
            reviews.append(f"same hero image on {len(urls)} pages ({', '.join(urls[:5])}): {src}; give each page its own hero art")
    verdict = "FAIL" if fails else ("REVIEW" if reviews else "PASS")
    print(f"{verdict} | {len(pages)} pages x 2 widths")
    for x in fails:
        print("  FAIL:", x)
    for x in reviews:
        print("  REVIEW:", x)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
