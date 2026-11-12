#!/usr/bin/env python3
"""
Build the static site: content markdown + design templates -> build/ (clean URLs).

Usage: python3 build.py <project> [--draft]

Reads
  site.json                         brand, geos, pages, play_path
  content/<geo>/<page>.md           Step 3 (content owner)
  design/theme.json                 Step 4 (design owner): brand name, template tokens, labels per geo
                                    (colours and fonts live in design/assets/css/site.css)
  design/images.json                Step 4 (optional): images per page section, inserted after the H2
                                    {"fi/bonus": {"intro": {...}, "<section-id>": {"src": "/assets/img/x.webp",
                                     "alt": "...", "width": 1200, "height": 750}}}
  design/templates/*.html           Step 4: base.html, header.html, footer.html
  design/assets/                    Step 4: css, js, images (copied to build/assets/)
  seo/head/<geo>/<page>.html        Step 5 (SEO owner): extra <head> tags (og, schema, hreflang)
  seo/files/                        Step 5: robots.txt, sitemap.xml, _redirects, _headers (copied to build/)
Writes
  build/<prefix><slug>.html         /bonus -> bonus.html, served as /bonus (no trailing slash)
  build/<prefix>index.html          home

Fails (exit 1) when a page still has [VERIFY] placeholders, unless --draft.
Template tokens: {{name}}. Unknown tokens are left empty.
"""
import html
import json
import os
import re
import shutil
import sys

import markdown

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_qc_config import RG  # noqa: E402  responsible-gambling domains per geo


def load_md(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"\s*<!--meta\s+(\{.*?\})\s*-->", raw, re.S)
    return (json.loads(m.group(1)) if m else {}), (raw[m.end():] if m else raw)


def slugify(t):
    t = t.lower()
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", t).strip("-")[:60]


def fill(tpl, ctx):
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(ctx.get(m.group(1), "")), tpl)


def out_path(prefix, slug):
    rel = prefix.strip("/")
    name = "index.html" if slug in ("", "/") else slug.strip("/") + ".html"
    return os.path.join(rel, name) if rel else name


def url_for(prefix, slug):
    p = "/" + prefix.strip("/") if prefix.strip("/") else ""
    s = "" if slug in ("", "/") else "/" + slug.strip("/")
    return (p + s) or "/"


def figure(img, first):
    load = 'fetchpriority="high"' if first else 'loading="lazy" decoding="async"'
    return (f'<figure class="fig"><img src="{img["src"]}" alt="{html.escape(img.get("alt", ""), quote=True)}" '
            f'width="{img.get("width", "")}" height="{img.get("height", "")}" {load}></figure>')


def body_html(md_text, play_path, internal_host, images=None):
    images = images or {}
    first = [True]

    def fig(key):
        if key in images:
            f = figure(images[key], first[0])
            first[0] = False
            return f
        return ""
    h = markdown.markdown(md_text, extensions=["tables", "sane_lists"])
    # sections: wrap each H2 block
    parts = re.split(r"(?=<h2>)", h)
    out = []
    for i, part in enumerate(parts):
        if i == 0 and not part.startswith("<h2>"):
            out.append(f'<div class="intro">{part}{fig("intro")}</div>' if part.strip() else "")
            continue
        m = re.match(r"<h2>(.*?)</h2>", part, re.S)
        sid = slugify(re.sub("<.*?>", "", m.group(1))) if m else f"s{i}"
        if m and sid in images:
            part = part[:m.end()] + fig(sid) + part[m.end():]
        out.append(f'<section class="sec" id="{sid}">{part}</section>')
    h = "\n".join(out)
    h = re.sub(r"<table>", '<div class="tbl"><table>', h)
    h = re.sub(r"</table>", "</table></div>", h)

    def fix_link(m):
        href, rest = m.group(1), m.group(2)
        if href.rstrip("/") == play_path.rstrip("/"):
            return f'<a href="{play_path}" rel="nofollow sponsored" class="cta-inline"{rest}>'
        if href.startswith("http") and internal_host not in href:
            return f'<a href="{href}" rel="nofollow noopener" target="_blank"{rest}>'
        return m.group(0)
    h = re.sub(r'<a href="([^"]+)"([^>]*)>', fix_link, h)
    # verify placeholders stay visible in drafts
    h = re.sub(r"\[VERIFY:([^\]]*)\]", r'<mark class="verify">[VERIFY:\1]</mark>', h)
    return h


def main():
    proj = sys.argv[1]
    draft = "--draft" in sys.argv
    site = json.load(open(os.path.join(proj, "site.json"), encoding="utf-8"))
    dz = os.path.join(proj, "design")
    theme = json.load(open(os.path.join(dz, "theme.json"), encoding="utf-8"))
    images_all = {}
    if os.path.exists(os.path.join(dz, "images.json")):
        images_all = json.load(open(os.path.join(dz, "images.json"), encoding="utf-8"))
    tpl = {n: open(os.path.join(dz, "templates", f"{n}.html"), encoding="utf-8").read()
           for n in ("base", "header", "footer")}
    play = site.get("play_path", "/play")
    host = site["domain"]
    build = os.path.join(proj, "build")
    if os.path.exists(build):
        shutil.rmtree(build)
    os.makedirs(build)
    if os.path.isdir(os.path.join(dz, "assets")):
        shutil.copytree(os.path.join(dz, "assets"), os.path.join(build, "assets"))
    seo_files = os.path.join(proj, "seo", "files")
    if os.path.isdir(seo_files):
        for f in os.listdir(seo_files):
            shutil.copy(os.path.join(seo_files, f), build)

    geos = {g["code"]: g for g in site["geos"]}
    problems = []
    built = []
    for geo, g in geos.items():
        cdir = os.path.join(proj, "content", geo)
        if not os.path.isdir(cdir):
            continue
        pages = []
        for fn in sorted(os.listdir(cdir)):
            if fn.endswith(".md") and "before-" not in fn:
                meta, md = load_md(os.path.join(cdir, fn))
                pages.append((fn[:-3], meta, md))
        labels = theme.get("labels", {}).get(geo, {})

        def nav(m):
            if m.get("nav_label"):
                return m["nav_label"]
            slug = m.get("slug", "/").strip("/")
            return labels.get("home", "Home") if not slug else slug.replace("-", " ").capitalize()
        footer_links = "".join(
            f'<li><a href="{url_for(g["prefix"], m.get("slug", "/"))}">{html.escape(nav(m))}</a></li>'
            for _, m, _ in pages if m.get("type") == "mandatory")
        main_links = "".join(
            f'<li><a href="{url_for(g["prefix"], m.get("slug", "/"))}">{html.escape(nav(m))}</a></li>'
            for _, m, _ in pages if m.get("type") != "mandatory")
        rg_links = "".join(
            f'<li><a href="https://{d}/" rel="nofollow noopener" target="_blank">{d}</a></li>' for d in RG.get(geo, []))
        for name, meta, md in pages:
            ph = re.findall(r"\[VERIFY:[^\]]*\]", md)
            if ph:
                problems.append(f"{geo}/{name}: {len(ph)} [VERIFY] placeholders")
            slug = meta.get("slug", "/")
            ctx = dict(theme.get("tokens", {}))
            ctx.update({
                "lang": g.get("html_lang", geo), "brand": theme.get("brand", site["brand"]),
                "play": play, "home": url_for(g["prefix"], "/"),
                "login_label": labels.get("login", "Login"), "register_label": labels.get("register", "Register"),
                "footer_links": footer_links, "main_links": main_links, "rg_links": rg_links,
                "rg_title": labels.get("rg_title", ""), "pages_title": labels.get("pages_title", ""),
                "legal": html.escape(labels.get("legal", "")), "year": "2026",
            })
            ctx["header"] = fill(tpl["header"], ctx)
            ctx["footer"] = fill(tpl["footer"], ctx)
            head_extra_p = os.path.join(proj, "seo", "head", geo, f"{name}.html")
            ctx.update({
                "title": html.escape(meta.get("title", "")), "description": html.escape(meta.get("description", ""), quote=True),
                "canonical": f"https://{host}{url_for(g['prefix'], slug)}",
                "head_extra": open(head_extra_p, encoding="utf-8").read() if os.path.exists(head_extra_p) else "",
                "h1": html.escape(meta.get("h1", "")), "page_type": meta.get("type", "other"),
                "body": body_html(md, play, host, images_all.get(f"{geo}/{name}", {})),
            })
            out = os.path.join(build, out_path(g["prefix"], slug))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, "w", encoding="utf-8").write(fill(tpl["base"], ctx))
            built.append(out_path(g["prefix"], slug))

    print("Built:", ", ".join(built))
    if problems:
        print("Open placeholders:", "; ".join(problems))
        if not draft:
            print("Build blocked: resolve [VERIFY] placeholders or use --draft for a preview.")
            sys.exit(1)


if __name__ == "__main__":
    main()
