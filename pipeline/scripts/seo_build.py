#!/usr/bin/env python3
"""
Step 5: generate the SEO layer. Writes only into <project>/seo/ (the SEO owner's folder);
build.py injects it.

Usage: python3 seo_build.py <project>

Reads site.json and content/<geo>/<page>.md front-matter. Writes:
  seo/head/<geo>/<page>.html  og + twitter tags, hreflang alternates (self + other geos + x-default),
                              robots meta, JSON-LD (Organization, WebSite, WebPage, BreadcrumbList,
                              FAQPage when the page has an FAQ section). Never Review/AggregateRating.
  seo/files/robots.txt        Disallow play path, Sitemap line
  seo/files/sitemap.xml       clean URLs with xhtml:link alternates
  seo/files/_redirects        Cloudflare: play path -> affiliate link (302), .html and trailing slash -> clean URL (301)
  seo/files/_headers          Cloudflare: HSTS, nosniff, referrer, frame; noindex on play path; asset caching
  seo/files/.htaccess         cPanel/Apache: https + non-www, clean URLs, play redirect, noindex play path

site.json keys used: domain, brand, geos[], pages[] (slug or slugs{geo}, type), play_path,
affiliate_link, indexing ("index" default | "noindex"), www (false default).
The og image is /assets/img/og.jpg when design/assets/img/og.jpg exists (1200x630, made by the designer).
"""
import html
import json
import os
import re
import sys

import markdown

E = html.escape
FAQ_RE = re.compile(r"faq|usein kysyt|frequently asked|vanliga fr[aå]gor|veelgestelde|h[aä]ufig gestellte|questions fr[eé]quentes|"
                    r"domande frequenti|preguntas frecuentes|cz[eę]sto zadawane|ofte stilte|συχν[εέ]ς ερωτ", re.I)


def load_md(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"\s*<!--meta\s+(\{.*?\})\s*-->", raw, re.S)
    return (json.loads(m.group(1)) if m else {}), (raw[m.end():] if m else raw)


def url_for(prefix, slug):
    p = "/" + prefix.strip("/") if prefix.strip("/") else ""
    s = "" if slug in ("", "/") else "/" + slug.strip("/")
    return (p + s) or "/"


def page_slug(page, geo):
    return (page.get("slugs") or {}).get(geo, page.get("slug", "/"))


def faq_items(md_text):
    h = markdown.markdown(md_text, extensions=["tables"])
    secs = re.split(r"(?=<h2>)", h)
    for s in secs:
        m = re.match(r"<h2>(.*?)</h2>", s, re.S)
        if not m or not FAQ_RE.search(re.sub("<.*?>", "", m.group(1))):
            continue
        items = []
        for qa in re.split(r"(?=<h3>)", s[m.end():]):
            q = re.match(r"<h3>(.*?)</h3>", qa, re.S)
            if not q:
                continue
            a = re.sub(r"<.*?>", "", qa[q.end():]).strip()
            a = re.sub(r"\s+", " ", re.sub(r"\[VERIFY:[^\]]*\]", "", a))
            if a:
                items.append((re.sub("<.*?>", "", q.group(1)).strip(), a[:1000]))
        return items
    return []


def main():
    proj = sys.argv[1]
    site = json.load(open(os.path.join(proj, "site.json"), encoding="utf-8"))
    host = site["domain"]
    base = f"https://{'www.' if site.get('www') else ''}{host}"
    play = site.get("play_path", "/play").rstrip("/") or "/play"
    noindex = site.get("indexing", "index") == "noindex"
    geos = site["geos"]
    default_geo = geos[0]["code"]
    og_img = os.path.exists(os.path.join(proj, "design", "assets", "img", "og.jpg"))
    logo = site.get("brand_assets", {}).get("logo_path") or ""

    # map content files per geo by slug
    content = {}
    for g in geos:
        cdir = os.path.join(proj, "content", g["code"])
        if not os.path.isdir(cdir):
            continue
        for fn in os.listdir(cdir):
            if fn.endswith(".md") and "before-" not in fn:
                meta, md = load_md(os.path.join(cdir, fn))
                content[(g["code"], meta.get("slug", "/"))] = (fn[:-3], meta, md)

    sitemap_urls = []
    for page in site.get("pages", []):
        variants = []
        for g in geos:
            slug = page_slug(page, g["code"])
            if (g["code"], slug) in content:
                variants.append((g, slug))
        if not variants:
            continue
        alts = [(g["hreflang"], base + url_for(g["prefix"], slug)) for g, slug in variants]
        xdef = next((u for (g, _), (_, u) in zip(variants, alts) if g["code"] == default_geo), alts[0][1])
        for g, slug in variants:
            name, meta, md = content[(g["code"], slug)]
            url = base + url_for(g["prefix"], slug)
            home = base + url_for(g["prefix"], "/")
            locale = g["hreflang"].replace("-", "_")
            tags = [
                f'<meta name="robots" content="{"noindex, nofollow" if noindex else "index, follow, max-image-preview:large"}">',
                f'<meta property="og:type" content="{"website" if slug in ("", "/") else "article"}">',
                f'<meta property="og:site_name" content="{E(site["brand"], quote=True)}">',
                f'<meta property="og:locale" content="{locale}">',
                f'<meta property="og:title" content="{E(meta.get("title", ""), quote=True)}">',
                f'<meta property="og:description" content="{E(meta.get("description", ""), quote=True)}">',
                f'<meta property="og:url" content="{url}">',
                '<meta name="twitter:card" content="summary_large_image">',
                f'<meta name="twitter:title" content="{E(meta.get("title", ""), quote=True)}">',
                f'<meta name="twitter:description" content="{E(meta.get("description", ""), quote=True)}">',
            ]
            if og_img:
                tags += [f'<meta property="og:image" content="{base}/assets/img/og.jpg">',
                         '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
                         f'<meta name="twitter:image" content="{base}/assets/img/og.jpg">']
            for hl, u in alts:
                tags.append(f'<link rel="alternate" hreflang="{hl}" href="{u}">')
            tags.append(f'<link rel="alternate" hreflang="x-default" href="{xdef}">')
            org = {"@type": "Organization", "@id": base + "/#org", "name": site["brand"], "url": base + "/"}
            if logo:
                org["logo"] = base + logo
            graph = [
                org,
                {"@type": "WebSite", "@id": base + "/#website", "url": base + "/", "name": site["brand"],
                 "inLanguage": g["hreflang"], "publisher": {"@id": base + "/#org"}},
                {"@type": "WebPage", "@id": url + "#webpage", "url": url, "name": meta.get("title", ""),
                 "description": meta.get("description", ""), "inLanguage": g["hreflang"],
                 "isPartOf": {"@id": base + "/#website"}},
            ]
            crumbs = [{"@type": "ListItem", "position": 1, "name": site["brand"], "item": home}]
            if slug not in ("", "/"):
                crumbs.append({"@type": "ListItem", "position": 2, "name": meta.get("nav_label") or meta.get("h1", ""), "item": url})
            graph.append({"@type": "BreadcrumbList", "itemListElement": crumbs})
            faqs = faq_items(md)
            if faqs:
                graph.append({"@type": "FAQPage", "mainEntity": [
                    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]})
            ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
            tags.append(f'<script type="application/ld+json">{ld}</script>')
            out = os.path.join(proj, "seo", "head", g["code"], f"{name}.html")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, "w", encoding="utf-8").write("\n".join(tags) + "\n")
            sitemap_urls.append((url, alts, xdef))

    files = os.path.join(proj, "seo", "files")
    os.makedirs(files, exist_ok=True)
    open(os.path.join(files, "robots.txt"), "w").write(
        f"User-agent: *\n{'Disallow: /' if noindex else 'Allow: /'}\nDisallow: {play}\n\nSitemap: {base}/sitemap.xml\n")
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for url, alts, xdef in sitemap_urls:
        sm.append(f"  <url><loc>{url}</loc>")
        for hl, u in alts:
            sm.append(f'    <xhtml:link rel="alternate" hreflang="{hl}" href="{u}"/>')
        sm.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{xdef}"/>')
        sm.append("  </url>")
    sm.append("</urlset>")
    open(os.path.join(files, "sitemap.xml"), "w").write("\n".join(sm) + "\n")
    aff = site.get("affiliate_link", "")
    if not aff.startswith("http"):
        aff = "https://example.invalid/set-affiliate-link"
    open(os.path.join(files, "_redirects"), "w").write(
        f"{play}  {aff}  302\n{play}/  {aff}  302\n/index.html  /  301\n/:page.html  /:page  301\n")
    open(os.path.join(files, "_headers"), "w").write(
        "/*\n  Strict-Transport-Security: max-age=31536000; includeSubDomains\n  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n  X-Frame-Options: SAMEORIGIN\n"
        f"{play}\n  X-Robots-Tag: noindex, nofollow\n"
        "/assets/*\n  Cache-Control: public, max-age=2592000\n")
    canon_host = ("www." if site.get("www") else "") + host
    open(os.path.join(files, ".htaccess"), "w").write(f"""Options -Indexes
RewriteEngine On
# https and canonical host
RewriteCond %{{HTTPS}} off [OR]
RewriteCond %{{HTTP_HOST}} !^{re.escape(canon_host)}$ [NC]
RewriteRule ^(.*)$ https://{canon_host}/$1 [R=301,L]
# affiliate redirect
RewriteRule ^{play.strip('/')}/?$ {aff} [R=302,L]
# /page.html and /page/ -> /page
RewriteCond %{{THE_REQUEST}} \\s/([^.?\\s]+)\\.html[\\s?] [NC]
RewriteRule ^ /%1 [R=301,L]
RewriteCond %{{REQUEST_FILENAME}} !-d
RewriteRule ^(.+)/$ /$1 [R=301,L]
# serve clean URLs
RewriteCond %{{REQUEST_FILENAME}} !-f
RewriteCond %{{REQUEST_FILENAME}}.html -f
RewriteRule ^(.+)$ $1.html [L]
ErrorDocument 404 /404.html
<IfModule mod_headers.c>
  Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
  Header always set X-Content-Type-Options "nosniff"
  <If "%{{REQUEST_URI}} =~ m#^{play}#">
    Header set X-Robots-Tag "noindex, nofollow"
  </If>
</IfModule>
""")
    print(f"SEO layer: {len(sitemap_urls)} page(s), files: robots.txt, sitemap.xml, _redirects, _headers, .htaccess"
          + ("" if site.get("affiliate_link", "").startswith("http") else " | WARNING: site.json affiliate_link not set"))


if __name__ == "__main__":
    main()
