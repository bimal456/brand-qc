#!/usr/bin/env python3
"""
Build the static site: content markdown + design (layouts, blocks, data) -> build/ (clean URLs).

Usage: python3 build.py <project> [--draft]

Reads
  site.json                         brand, geos, pages, play_path
  content/<geo>/<page>.md           Step 3 (content owner): front-matter + markdown
  design/theme.json                 Step 4 (design owner): brand, tokens, labels per geo, toc on/off
  design/layouts.json               Step 4: ordered blocks per page type, or per "<geo>/<page>"
      {"home": ["hero", "games:popular", "games:new", "promos", "content", "providers", "cta"],
       "other": ["hero", "content", "cta"], "mandatory": ["content"]}
  design/templates/base.html        page shell: {{header}} {{sidebar}} {{blocks}} {{footer}} ...
  design/templates/header.html, footer.html, sidebar.html (sidebar optional)
  design/templates/blocks/<block>.html  hero, games, game_card, promos, promo_card, content, providers, cta
  design/data/games.json            {"popular": {"title": {"fi": "Suositut pelit"}, "items": [
                                        {"name": "...", "provider": "...", "img": "/assets/img/g/x.webp", "w": 300, "h": 400}]}}
  design/data/promos.json           [{"title": {"fi": ".."}, "text": {"fi": ".."}, "img": "..", "w": .., "h": ..}]
                                    (promo text = verified facts only)
  design/data/providers.json        [{"name": "NetEnt", "img": "/assets/img/p/netent.webp", "w": 120, "h": 40}]
  design/images.json                optional images per content section {"fi/bonus": {"intro"|"<section-id>": {...}}}
  design/assets/                    css, js, img -> build/assets/
  seo/head/<geo>/<page>.html        Step 5 (SEO owner): extra <head> tags
  seo/files/                        Step 5: robots.txt, sitemap.xml, _redirects, _headers -> build/
Writes
  build/<prefix><slug>.html         /bonus -> bonus.html (served as /bonus), home -> index.html

The hero block shows the page H1 and the content's intro (text owned by the content writer).
The content block shows the rest of the markdown, with a table of contents of the H2s when
theme.json "toc" is true (jump buttons, no "#" links).
Fails (exit 1) when a page still has [VERIFY] placeholders, unless --draft.
Template tokens: {{name}}. Unknown tokens render empty.
"""
import html
import json
import os
import re
import shutil
import sys

import markdown

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_qc_config import RG  # noqa: E402

E = html.escape


def load_md(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"\s*<!--meta\s+(\{.*?\})\s*-->", raw, re.S)
    return (json.loads(m.group(1)) if m else {}), (raw[m.end():] if m else raw)


def jload(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def slugify(t):
    t = re.sub(r"[^\w\s-]", "", t.lower(), flags=re.UNICODE)
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


def loc(v, geo):
    if isinstance(v, dict):
        return v.get(geo) or next(iter(v.values()), "")
    return v or ""


class Img:
    """Gives fetchpriority to the first image of a page and lazy loading to the rest."""
    def __init__(self):
        self.first = True

    def tag(self, src, alt, w, h, cls=""):
        load = 'fetchpriority="high"' if self.first else 'loading="lazy" decoding="async"'
        self.first = False
        c = f' class="{cls}"' if cls else ""
        return f'<img{c} src="{src}" alt="{E(alt, quote=True)}" width="{w}" height="{h}" {load}>'


def md_parts(md_text, play_path, host, images, img):
    """Returns (intro_html, sections_html, toc_list)."""
    h = markdown.markdown(md_text, extensions=["tables", "sane_lists"])

    def fix_link(m):
        href, rest = m.group(1), m.group(2)
        if href.rstrip("/") == play_path.rstrip("/"):
            return f'<a href="{play_path}" rel="nofollow sponsored" class="cta-inline"{rest}>'
        if href.startswith("http") and host not in href:
            return f'<a href="{href}" rel="nofollow noopener" target="_blank"{rest}>'
        return m.group(0)
    h = re.sub(r'<a href="([^"]+)"([^>]*)>', fix_link, h)
    h = re.sub(r"\[VERIFY:([^\]]*)\]", r'<mark class="verify">[VERIFY:\1]</mark>', h)
    h = re.sub(r"<table>", '<div class="tbl"><table>', h)
    h = re.sub(r"</table>", "</table></div>", h)

    def fig(key):
        i = images.get(key)
        if not i:
            return ""
        return f'<figure class="fig">{img.tag(i["src"], i.get("alt", ""), i.get("width", ""), i.get("height", ""))}</figure>'

    parts = re.split(r"(?=<h2>)", h)
    intro, secs, toc = "", [], []
    for i, part in enumerate(parts):
        if i == 0 and not part.startswith("<h2>"):
            intro = part + fig("intro")
            continue
        m = re.match(r"<h2>(.*?)</h2>", part, re.S)
        title = re.sub("<.*?>", "", m.group(1)) if m else ""
        sid = slugify(title) if m else f"s{i}"
        if m:
            toc.append((sid, title))
            part = part[:m.end()] + fig(sid) + part[m.end():]
        secs.append(f'<section class="sec" id="{sid}">{part}</section>')
    return intro, "\n".join(secs), toc


def main():
    proj = sys.argv[1]
    draft = "--draft" in sys.argv
    site = json.load(open(os.path.join(proj, "site.json"), encoding="utf-8"))
    dz = os.path.join(proj, "design")
    theme = jload(os.path.join(dz, "theme.json"), {})
    layouts = jload(os.path.join(dz, "layouts.json"),
                    {"home": ["hero", "content"], "other": ["hero", "content"], "mandatory": ["content"]})
    games = jload(os.path.join(dz, "data", "games.json"), {})
    promos = jload(os.path.join(dz, "data", "promos.json"), [])
    providers = jload(os.path.join(dz, "data", "providers.json"), [])
    images_all = jload(os.path.join(dz, "images.json"), {})
    tdir = os.path.join(dz, "templates")

    def tpl(name):
        p = os.path.join(tdir, name + ".html")
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

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

    problems, built, skipped = [], [], set()
    for g in site["geos"]:
        geo = g["code"]
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
            s = m.get("slug", "/").strip("/")
            return labels.get("home", "Home") if not s else s.replace("-", " ").capitalize()

        def links(pred):
            return "".join(f'<li><a href="{url_for(g["prefix"], m.get("slug", "/"))}">{E(nav(m))}</a></li>'
                           for _, m, _ in pages if pred(m))
        common = dict(theme.get("tokens", {}))
        common.update({k: E(v) for k, v in labels.items()})
        common.update({
            "lang": g.get("html_lang", geo), "brand": theme.get("brand", site["brand"]), "play": play,
            "home": url_for(g["prefix"], "/"), "year": "2026",
            "main_links": links(lambda m: m.get("type") != "mandatory"),
            "footer_links": links(lambda m: m.get("type") == "mandatory"),
            "rg_links": "".join(f'<li><a href="https://{d}/" rel="nofollow noopener" target="_blank">{d}</a></li>'
                                for d in RG.get(geo, [])),
        })

        for name, meta, md in pages:
            ph = re.findall(r"\[VERIFY:[^\]]*\]", md)
            if ph:
                problems.append(f"{geo}/{name}: {len(ph)} [VERIFY] placeholders")
            img = Img()
            intro, sections, toc = md_parts(md, play, host, images_all.get(f"{geo}/{name}", {}), img)
            ptype = meta.get("type", "other")
            order = layouts.get(f"{geo}/{name}") or layouts.get(ptype) or layouts.get("other", ["hero", "content"])
            ctx = dict(common)
            ctx.update({"h1": E(meta.get("h1", "")), "intro": intro, "page_type": ptype})
            blocks = []
            for b in order:
                kind, _, key = b.partition(":")
                t = tpl("blocks/" + kind)
                if not t:
                    skipped.add(f"block template '{kind}'")
                    continue
                c = dict(ctx)
                if kind == "games":
                    row = games.get(key)
                    if not row:
                        skipped.add(f"games data '{key}'")
                        continue
                    card = tpl("blocks/game_card")
                    c["row_id"] = key
                    c["row_title"] = E(loc(row.get("title", ""), geo))
                    c["cards"] = "".join(
                        fill(card, dict(c, name=E(it["name"]), provider=E(it.get("provider", "")),
                                        img=img.tag(it["img"], it["name"], it.get("w", ""), it.get("h", ""), "g-img")))
                        for it in row.get("items", []))
                elif kind == "promos":
                    if not promos:
                        skipped.add("promos data")
                        continue
                    card = tpl("blocks/promo_card")
                    c["cards"] = "".join(
                        fill(card, dict(c, title=E(loc(p.get("title", ""), geo)), text=E(loc(p.get("text", ""), geo)),
                                        img=img.tag(p["img"], loc(p.get("title", ""), geo), p.get("w", ""), p.get("h", ""))
                                        if p.get("img") else ""))
                        for p in promos)
                elif kind == "providers":
                    if not providers:
                        skipped.add("providers data")
                        continue
                    c["items"] = "".join(
                        f'<li>{img.tag(p["img"], p["name"], p.get("w", ""), p.get("h", "")) if p.get("img") else E(p["name"])}</li>'
                        for p in providers)
                elif kind == "content":
                    c["sections"] = sections
                    c["intro_if_no_hero"] = "" if "hero" in order else intro
                    c["toc"] = ("".join(f'<li><button type="button" data-jump="{sid}">{E(t2)}</button></li>'
                                        for sid, t2 in toc) if theme.get("toc") and toc else "")
                blocks.append(fill(t, c))
            ctx["blocks"] = "\n".join(blocks)
            ctx["header"] = fill(tpl("header"), ctx)
            ctx["sidebar"] = fill(tpl("sidebar"), ctx)
            ctx["footer"] = fill(tpl("footer"), ctx)
            head_extra_p = os.path.join(proj, "seo", "head", geo, f"{name}.html")
            ctx.update({
                "title": E(meta.get("title", "")), "description": E(meta.get("description", ""), quote=True),
                "canonical": f"https://{host}{url_for(g['prefix'], meta.get('slug', '/'))}",
                "head_extra": open(head_extra_p, encoding="utf-8").read() if os.path.exists(head_extra_p) else "",
            })
            out = os.path.join(build, out_path(g["prefix"], meta.get("slug", "/")))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, "w", encoding="utf-8").write(fill(tpl("base"), ctx))
            built.append(out_path(g["prefix"], meta.get("slug", "/")))

    print("Built:", ", ".join(built))
    if skipped:
        print("Skipped (no template or data):", ", ".join(sorted(skipped)))
    if problems:
        print("Open placeholders:", "; ".join(problems))
        if not draft:
            print("Build blocked: resolve [VERIFY] placeholders or use --draft for a preview.")
            sys.exit(1)


if __name__ == "__main__":
    main()
