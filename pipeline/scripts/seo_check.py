#!/usr/bin/env python3
"""
Step 5: on-page SEO checks on the content files. Content belongs to the content writer, so
this script never edits it: it writes change requests to <project>/seo/requests.md.

Usage: python3 seo_check.py <project>

Per page (keyword from site.json pages[].keywords[geo]):
  - title: 55-60 chars, keyword near the start, "18+" not required; description 150-160 with keyword and "18+"
  - H1 contains the keyword (or all its words)
  - keyword (or all its words) in the first 100 words of the intro
  - keyword words appear in at least one H2
  - keyword density between 0.3% and 2.5% (inflected forms count: all keyword stems within a short window)
  - at least 2 internal links to other pages, and every built page receives a content link
  - no duplicate titles, descriptions or H1s across pages
Exit code 1 when there are requests.
"""
import json
import os
import re
import sys
from collections import defaultdict


def load_md(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"\s*<!--meta\s+(\{.*?\})\s*-->", raw, re.S)
    return (json.loads(m.group(1)) if m else {}), (raw[m.end():] if m else raw)


def words(t):
    return re.findall(r"[\w]+(?:[-'][\w]+)*", t.lower(), re.UNICODE)


def has_kw(text, kw):
    t = text.lower()
    if kw in t:
        return True
    # all keyword words present (allows Finnish/German inflection by 4-letter stem)
    tw = words(t)
    return all(any(w.startswith(k[:max(4, len(k) - 2)]) for w in tw) for k in words(kw))


def kw_hits(text, kw):
    """Occurrences of the keyword allowing inflection: all keyword stems inside a short window."""
    tw = words(text)
    ks = [k[:max(4, len(k) - 2)] for k in words(kw)]
    n, i, span = 0, 0, len(ks) + 2
    while i < len(tw):
        win = tw[i:i + span]
        if all(any(w.startswith(k) for w in win) for k in ks) and tw[i].startswith(tuple(ks)):
            n += 1
            i += span
        else:
            i += 1
    return n


def main():
    proj = sys.argv[1]
    site = json.load(open(os.path.join(proj, "site.json"), encoding="utf-8"))
    play = site.get("play_path", "/play").rstrip("/")
    req = []  # page, section, change, reason
    seen = defaultdict(lambda: defaultdict(list))
    inbound = defaultdict(set)
    pages = {}
    for g in site["geos"]:
        cdir = os.path.join(proj, "content", g["code"])
        if not os.path.isdir(cdir):
            continue
        for fn in sorted(os.listdir(cdir)):
            if not fn.endswith(".md") or "before-" in fn:
                continue
            meta, md = load_md(os.path.join(cdir, fn))
            slug = meta.get("slug", "/")
            pid = f"{g['code']}:{slug}"
            pages[pid] = (g, meta, md)
            for k in ("title", "description", "h1"):
                if meta.get(k):
                    seen[k][meta[k].strip().lower()].append(pid)
            for href in re.findall(r"\]\((/[^)\s]*)\)", md):
                h = href.rstrip("/") or "/"
                if h != play:
                    inbound[f"{g['code']}:{h}"].add(pid)

    kwmap = {}
    for p in site.get("pages", []):
        for geo, kw in (p.get("keywords") or {}).items():
            kwmap[f"{geo}:{(p.get('slugs') or {}).get(geo, p.get('slug', '/'))}"] = (kw or "").lower().strip()

    for pid, (g, meta, md) in pages.items():
        page = f"{meta.get('slug', '/')} [{g['code']}]"
        kw = kwmap.get(pid, "")
        title, desc, h1 = meta.get("title", ""), meta.get("description", ""), meta.get("h1", "")
        if not 55 <= len(title) <= 60:
            req.append((page, "meta title", f"rewrite to 55-60 chars (now {len(title)})", "title length rule"))
        if not 150 <= len(desc) <= 160:
            req.append((page, "meta description", f"rewrite to 150-160 chars (now {len(desc)})", "description length rule"))
        if "18+" not in desc:
            req.append((page, "meta description", "add 18+", "required on every page"))
        text = re.sub(r"\[VERIFY:[^\]]*\]", " ", md)
        links = [h.rstrip("/") or "/" for h in re.findall(r"\]\((/[^)\s]*)\)", text)]
        internal = {h for h in links if h != play and h != (meta.get("slug", "/").rstrip("/") or "/")}
        if meta.get("type") != "mandatory" and len(internal) < 2:
            req.append((page, "body", f"add internal links to other pages (now {len(internal)})", "every page links at least 2 others"))
        if not kw:
            continue
        if not has_kw(title, kw):
            req.append((page, "meta title", f'include "{kw}" near the start', "primary keyword missing"))
        elif title.lower().find(kw.split()[0]) > 25:
            req.append((page, "meta title", f'move "{kw}" toward the start', "keyword starts late in title"))
        if not has_kw(desc, kw):
            req.append((page, "meta description", f'include "{kw}"', "primary keyword missing"))
        if not has_kw(h1, kw):
            req.append((page, "H1", f'include "{kw}"', "primary keyword missing in H1"))
        intro = re.split(r"^##\s", text, maxsplit=1, flags=re.M)[0]
        if not has_kw(" ".join(words(intro)[:100]), kw):
            req.append((page, "intro", f'use "{kw}" in the first 100 words', "keyword missing early"))
        h2s = re.findall(r"^##\s+(.*)$", text, flags=re.M)
        if h2s and not any(has_kw(h, kw) for h in h2s):
            req.append((page, "H2s", f'use "{kw}" (or a close variant) in at least one H2; update the same heading in outline.md', "keyword missing from all H2s"))
        body_w = words(text)
        n = kw_hits(text, kw)
        dens = 100 * n * len(kw.split()) / max(len(body_w), 1)
        if dens > 2.5:
            req.append((page, "body", f'reduce "{kw}" uses ({n}x, density {dens:.1f}%)', "over-optimised"))
        elif n == 0 or dens < 0.3:
            kl = len(kw.split())
            lo = max(n + 1, int(0.4 * len(body_w) / (100 * kl)) + 1)
            hi = max(lo + 1, int(1.0 * len(body_w) / (100 * kl)))
            req.append((page, "body", f'use "{kw}" (inflected forms count) {lo}-{hi} times in total, spread over the page (now {n}x, {dens:.2f}%)', "under-optimised"))

    for k, vals in seen.items():
        for v, pids in vals.items():
            if len(pids) > 1:
                req.append((", ".join(pids), k, "make unique per page", f"duplicate {k}"))
    for pid, (g, meta, _) in pages.items():
        slug = meta.get("slug", "/").rstrip("/") or "/"
        if slug != "/" and len(pages) > 1 and not (inbound.get(f"{g['code']}:{slug}", set()) - {pid}):
            req.append((f"{slug} [{g['code']}]", "site", "link to this page from at least one other page", "orphan page"))

    out = os.path.join(proj, "seo", "requests.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):  # keep the previous round (with done/refused notes) for the record
        n = 1
        while os.path.exists(os.path.join(proj, "seo", f"requests.round-{n}.md")):
            n += 1
        os.rename(out, os.path.join(proj, "seo", f"requests.round-{n}.md"))
    lines = ["# SEO change requests for the content writer", "",
             "Apply in content/<geo>/<page>.md, keep voice and fact rules, then rerun content_check.py.", "",
             "| page | section | change | reason | status |", "|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} | open |" for a, b, c, d in req]
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{'REQUESTS' if req else 'PASS'} | {len(pages)} page(s) | {len(req)} request(s) -> {out}")
    for r in req[:20]:
        print("  -", " | ".join(r))
    sys.exit(1 if req else 0)


if __name__ == "__main__":
    main()
