#!/usr/bin/env python3
"""Make a built site ready for the Cloudflare Worker upload (same rules as the cleanup skill,
github.com/bimal456/cleanup), so no separate cleanup run is needed.

A separate link-router worker answers /play, /go, /visit and /out. The site must therefore:
  - have index.html at its root
  - not answer those paths itself: no play.html / play.htm / play/ (same for go, visit, out)
    and no /play, /go, /visit, /out lines in _redirects
  - carry no worker or build files (_worker.js, _routes.json, functions/, wrangler.*, package.json ...)
  - carry no affiliate URL on a CTA: an <a>/<button> that leaves the site and has a btn/button/cta class,
    rel="sponsored", an onclick redirect on a <button>, or a tracking parameter (ref, aff, btag, clickid ...)
    points at /play instead. Social links and plain external links (help sites, sources) stay.

Usage:
  python3 worker_ready.py <build_dir> [--domain example.com] [--target /play]   # fix in place, print report
  python3 worker_ready.py <build_dir> --check                                   # report only, exit 1 if not ready
Used by build.py (fix) and brand_qc.py (check).
"""
import html, json, os, re, shutil, sys
from urllib.parse import urlsplit, parse_qsl

ROUTES = ("play", "go", "visit", "out")
_R = "|".join(ROUTES)
ROUTE_LINE = re.compile(rf"^/({_R})(/|\s|$)", re.I)
ROUTE_NAMES = {r + e for r in ROUTES for e in (".html", ".htm", "")}
NON_STATIC = {"_worker.js", "_routes.json", "functions", "worker.js", "wrangler.toml", "wrangler.json",
              "wrangler.jsonc", "package.json", "package-lock.json", "node_modules", ".git", ".wrangler"}
JUNK = {"__MACOSX", ".DS_Store", "Thumbs.db"}

# affiliate CTA detection (identical to the cleanup skill)
TAG = re.compile(r"""(?is)<(a|button)\b(?:[^>"']|"[^"]*"|'[^']*')*>""")
ATTR = re.compile(r"""(?is)([a-z_:][-a-z0-9_:.]*)\s*=\s*("[^"]*"|'[^']*'|[^\s>"']+)""")
URL_IN_JS = re.compile(r"""(?i)(?:https?:)?//[a-z0-9][^\s'"\\)<>]*""")
CTA_CLASS = re.compile(r"(?i)btn|button|(?<![a-z])cta(?![a-z])")
TRACK = {"ref", "refid", "ref_id", "refcode", "aff", "affid", "aff_id", "affiliate", "affiliate_id", "a_aid",
         "btag", "stag", "clickid", "click_id", "subid", "sub_id", "sub1", "tracker", "partner", "partnerid",
         "partner_id", "offer_id", "campaign_id"}
URL_ATTRS = ("href", "data-href", "data-url", "data-link")
SOCIAL = ("facebook.com", "fb.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "youtu.be",
          "t.me", "telegram.me", "telegram.org", "wa.me", "whatsapp.com", "linkedin.com", "pinterest.com",
          "tiktok.com", "reddit.com", "discord.gg", "discord.com")


def host_of(url):
    u = html.unescape(url).strip()
    if not re.match(r"(?i)^(https?:)?//", u):
        return ""
    try:
        h = (urlsplit(u if not u.startswith("//") else "https:" + u).hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def tracked(url):
    try:
        q = urlsplit(html.unescape(url).strip()).query
    except ValueError:
        return False
    return any(k.lower() in TRACK for k, _ in parse_qsl(q, keep_blank_values=True))


def own_hosts(root, domain=""):
    """Domains the site calls its own (site.json domain, canonical, og:url, sitemap, CNAME)."""
    own = {host_of("https://" + domain.strip("/"))} if domain else set()
    idx = os.path.join(root, "index.html")
    if os.path.exists(idx):
        t = open(idx, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"(?is)<(?:link|meta)\b[^>]*>", t):
            tag = m.group(0)
            if re.search(r"""(?i)rel\s*=\s*["']?canonical|property\s*=\s*["']?og:url""", tag):
                v = re.search(r"""(?i)(?:href|content)\s*=\s*["']([^"']+)""", tag)
                if v:
                    own.add(host_of(v.group(1)))
    sm = os.path.join(root, "sitemap.xml")
    if os.path.exists(sm):
        t = open(sm, encoding="utf-8", errors="ignore").read()
        own.update(host_of(u) for u in re.findall(r"(?is)<loc>\s*([^<\s]+)", t)[:50])
    cn = os.path.join(root, "CNAME")
    if os.path.exists(cn):
        h = open(cn, encoding="utf-8", errors="ignore").read().strip().lower()
        own.add(h[4:] if h.startswith("www.") else h)
    own.discard("")
    return own


def scan_cta(text, own, target="/play"):
    """(new_text, [affiliate urls replaced], {kept external host: count})"""
    hits, kept, out, pos = [], {}, [], 0
    ext = lambda u: (lambda h: h and h not in own and not any(h == s or h.endswith("." + s) for s in SOCIAL) and h)(host_of(u))
    for m in TAG.finditer(text):
        tag, el = m.group(0), m.group(1).lower()
        attrs = [(a.group(1).lower(), a.group(2), a.start(2), a.end(2)) for a in ATTR.finditer(tag)]
        val = lambda raw: raw[1:-1] if raw[:1] in "\"'" else raw
        get = lambda n: next((val(r) for k, r, _, _ in attrs if k == n), "")
        spans = []
        for k, raw, s, e in attrs:
            off = 1 if raw[:1] in "\"'" else 0
            v = val(raw)
            if k in URL_ATTRS and ext(v):
                spans.append((s + off, s + off + len(v), v))
            elif k == "onclick":
                for u in URL_IN_JS.finditer(v):
                    if ext(u.group(0)):
                        spans.append((s + off + u.start(), s + off + u.end(), u.group(0)))
        if not spans:
            continue
        is_cta = (el == "button" or CTA_CLASS.search(get("class")) or "sponsored" in get("rel").lower()
                  or any(tracked(u) for _, _, u in spans))
        if not is_cta:
            for _, _, u in spans:
                kept[host_of(u)] = kept.get(host_of(u), 0) + 1
            continue
        new, p = [], 0
        for s, e, u in sorted(spans):
            new += [tag[p:s], target]
            p = e
            hits.append(html.unescape(u))
        new.append(tag[p:])
        out += [text[pos:m.start()], "".join(new)]
        pos = m.end()
    out.append(text[pos:])
    return "".join(out), hits, kept


def run(root, domain="", target="/play", fix=True):
    """Returns a report dict; with fix=False nothing is changed."""
    rep = {"removed": [], "redirect_lines_removed": [], "cta_links_rewritten": [], "cta_pages": {},
           "external_hosts_kept": {}, "problems": []}
    if not os.path.exists(os.path.join(root, "index.html")):
        rep["problems"].append("no index.html at the site root")
    for n in sorted(os.listdir(root)):
        p = os.path.join(root, n)
        if n.lower() in ROUTE_NAMES or n in NON_STATIC or n in JUNK:
            rep["removed"].append(n + ("/" if os.path.isdir(p) else ""))
            if fix:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    rd = os.path.join(root, "_redirects")
    if os.path.exists(rd):
        lines = open(rd, encoding="utf-8").read().splitlines(True)
        keep = [l for l in lines if not ROUTE_LINE.match(l.strip())]
        rep["redirect_lines_removed"] = [l.strip() for l in lines if ROUTE_LINE.match(l.strip())]
        if fix and len(keep) != len(lines):
            open(rd, "w", encoding="utf-8").writelines(keep)
    own = own_hosts(root, domain)
    for d, ds, fs in os.walk(root):
        for f in fs:
            if not f.lower().endswith((".html", ".htm")):
                continue
            fp = os.path.join(d, f)
            t = open(fp, encoding="utf-8", errors="ignore").read()
            new, hits, kept = scan_cta(t, own, target)
            for h, c in kept.items():
                rep["external_hosts_kept"][h] = rep["external_hosts_kept"].get(h, 0) + c
            if hits:
                rel = "/" + os.path.relpath(fp, root).replace(os.sep, "/")
                rep["cta_pages"][rel] = len(hits)
                rep["cta_links_rewritten"] += hits
                if fix:
                    open(fp, "w", encoding="utf-8").write(new)
    if not fix:
        if rep["removed"]:
            rep["problems"].append("files the worker must answer or must not see: " + ", ".join(rep["removed"]))
        if rep["redirect_lines_removed"]:
            rep["problems"].append("_redirects answers worker paths: " + "; ".join(rep["redirect_lines_removed"][:4]))
        if rep["cta_links_rewritten"]:
            rep["problems"].append(f"{len(rep['cta_links_rewritten'])} CTA link(s) carry an affiliate URL instead of /play: "
                                   + ", ".join(sorted(set(rep["cta_links_rewritten"]))[:3]))
    return rep


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    root, domain, target, check = a[0], "", "/play", "--check" in a
    if "--domain" in a:
        domain = a[a.index("--domain") + 1]
    if "--target" in a:
        target = "/" + a[a.index("--target") + 1].strip("/").lower()
        if target.strip("/") not in ROUTES:
            sys.exit("--target must be /play, /go, /visit or /out")
    rep = run(root, domain, target, fix=not check)
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    sys.exit(1 if check and rep["problems"] else 0)


if __name__ == "__main__":
    main()
