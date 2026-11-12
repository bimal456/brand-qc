#!/usr/bin/env python3
"""Step 6 router: run Brand QC on <project>/build and send every failed item to its owner.

Usage:
  python3 qc_route.py <project>                 # run brand_qc.py, then route
  python3 qc_route.py <project> --report x.json # route an existing QC json

Writes:
  qc/requests/content.md, design.md, seo.md, intake.md   (page | section | change | reason | status)
  qc/route.md        summary: per owner counts, pending pages, round number
  qc/round.txt       QC round counter (max 2 fix rounds, then the user decides)

Exit codes: 0 = nothing for owners to fix (PASS, or only pages not built yet)
            1 = owner fixes needed
            3 = round limit reached, user decides
"""
import argparse, glob, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND_QC = os.path.normpath(os.path.join(HERE, "..", "..", "brand_qc.py"))
MAX_ROUNDS = 2

# check name (as written by brand_qc.py) -> owner
OWNER = {
    # wording lives in content/<geo>/<page>.md (incl. front-matter meta)
    "Word count": "content", "AI phrase": "content", "Brand voice": "content",
    "No em dashes": "content", "Forbidden name": "content", "Placeholders / dev notes": "content",
    "Meta title": "content", "Meta description": "content", "Meta description 18+": "content",
    "Duplicate meta title": "content", "Duplicate meta description": "content",
    "External link allowlist": "content", "18+ disclosure on home": "content", "Links": "content",
    # templates, css, images, build.py output
    "Single H1": "design", "Heading hierarchy": "design", "No # in href": "design",
    "Login/Register CTA -> /play": "design", "Nofollow CTA": "design", "Nofollow external": "design",
    "Images WebP": "design", "Image alt": "design", "Visual breaks": "design", "18+ badge in footer": "design",
    "No age gate popup": "design",
    # head tags, schema, files
    "Canonical": "seo", "Hreflang": "seo", "Sitemap": "seo", "Robots.txt": "seo",
    "Robots meta": "seo", "Schema": "seo", "OG / Twitter tags": "seo", "Clean URLs": "seo",
    "Worker meta override": "seo", "HTTP status": "seo", "Interlinking": "seo",
}
FIX = {
    "content": "content-writer (Change requests), then rerun content_check.py",
    "design": "site-designer, then rerun build.py and design_check.py",
    "seo": "seo-optimizer, then rerun seo_build.py and build.py",
    "intake": "brand-intake: update site.json, rerun make_qc_config.py",
}


def mandatory_words(proj):
    """slug words per mandatory page kind: brand_qc.py defaults + qc/config.json overrides"""
    sys.path.insert(0, os.path.dirname(BRAND_QC))
    from brand_qc import DEFAULT_CONFIG, deep_merge
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cp = os.path.join(proj, "qc", "config.json")
    if os.path.exists(cp):
        deep_merge(cfg, json.load(open(cp, encoding="utf-8")))
    return cfg["mandatory_pages"]


def load(p):
    return json.load(open(p, encoding="utf-8"))


def geo_pages(site):
    """url path -> (geo, page name, content file, planned page dict)"""
    out = {}
    for g in site["geos"]:
        pre = g.get("prefix", "/")
        for p in site["pages"]:
            slug = (p.get("slugs") or {}).get(g["code"], p.get("slug", "/"))
            name = "home" if slug.strip("/") == "" else slug.strip("/").replace("/", "-")
            url = (pre.rstrip("/") + "/" + slug.strip("/")).rstrip("/") or "/"
            out[url] = (g["code"], name, f"content/{g['code']}/{name}.md", p)
    return out


def built_paths(build):
    paths = set()
    for f in glob.glob(os.path.join(build, "**", "*.html"), recursive=True):
        rel = os.path.relpath(f, build).replace(os.sep, "/")
        if rel == "index.html":
            paths.add("/")
        elif rel.endswith("/index.html"):
            paths.add("/" + rel[:-11])
        else:
            paths.add("/" + rel[:-5])
    return paths


def norm(path):
    path = re.sub(r"[?#].*$", "", path or "/")
    return path.rstrip("/") or "/"


def run_qc(proj):
    out = os.path.join(proj, "qc")
    cmd = [sys.executable, BRAND_QC, os.path.join(proj, "build"), "--out", out]
    cfg = os.path.join(proj, "qc", "config.json")
    if os.path.exists(cfg):
        cmd += ["--config", cfg]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip())
    m = re.search(r"JSON:\s+(\S+)", r.stdout)
    if not m:
        sys.exit("brand_qc.py did not produce a report:\n" + r.stderr[-1500:])
    return m.group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--report", help="existing brand_qc JSON (skip running QC)")
    a = ap.parse_args()
    proj = a.project
    site = load(os.path.join(proj, "site.json"))
    planned = geo_pages(site)
    built = built_paths(os.path.join(proj, "build"))
    report = load(a.report or run_qc(proj))

    reqs = {k: [] for k in FIX}
    kinds = mandatory_words(proj)
    pending = {}   # planned page not built yet -> reasons
    seen = set()

    def add(owner, page, section, change, reason):
        key = (owner, page, section, change)
        if key not in seen:
            seen.add(key)
            reqs[owner].append((page, section, change, reason))

    def content_file(page):
        return planned.get(norm(page), (None, None, "?", None))[2]

    for it in report["items"]:
        chk, sev, page, det = it["check"], it["severity"], norm(it["page"]), it["detail"]
        if chk == "Broken internal link":
            target = norm(det.split(" has no")[0])
            if target in planned and target not in built:
                pending.setdefault(target, set()).add(f"linked from {page}")
                continue
            # a link to a page nobody planned: in the body text -> content, else templates -> design
            cf = os.path.join(proj, content_file(page))
            in_body = os.path.exists(cf) and re.search(r"\]\(" + re.escape(target) + r"[)#?\s]",
                                                       open(cf, encoding="utf-8").read())
            add("content" if in_body else "design", page, "link",
                f"fix or remove link to {target}", f"{target} is not a planned page in site.json")
            continue
        if chk == "Mandatory pages":
            kind = det.replace(" page not found", "").strip()
            words = kinds.get(kind, [kind])
            hit = [u for u in planned if any(re.search(r"(^|[/-])" + re.escape(w), u.lower()) for w in words)]
            if hit:
                for u in hit:
                    if u not in built:
                        pending.setdefault(u, set()).add(f"mandatory {kind} page")
            else:
                add("intake", "site.json", "pages", f"add a {kind} page (type mandatory) for every geo",
                    "mandatory page missing from the plan")
            continue
        if chk == "Interlinking" and len(built) < 2:
            pending.setdefault("(site)", set()).add("orphan check needs more than one built page")
            continue
        owner = OWNER.get(chk, "content")
        section = content_file(page) if owner == "content" else ""
        if sev == "REVIEW":
            det = "REVIEW: " + det
        add(owner, page, section or chk, det, chk)

    # round counter: a round is one QC run that sent work to owners
    rf = os.path.join(proj, "qc", "round.txt")
    rnd = int(open(rf).read().strip()) if os.path.exists(rf) else 0
    owner_items = sum(len(v) for v in reqs.values())
    if owner_items:
        rnd += 1
        open(rf, "w").write(str(rnd))

    rq = os.path.join(proj, "qc", "requests")
    os.makedirs(rq, exist_ok=True)
    for owner, rows in reqs.items():
        f = os.path.join(rq, f"{owner}.md")
        if os.path.exists(f):
            shutil.move(f, os.path.join(rq, f"{owner}.round-{max(rnd - 1, 0)}.md"))
        if not rows:
            continue
        L = [f"# QC requests for {owner} (round {rnd})", "", f"Owner: {FIX[owner]}",
             "Mark each row `done` or `refused: <reason>`.", "",
             "| page | section | change | reason | status |", "|---|---|---|---|---|"]
        for page, sec, ch, why in rows:
            L.append(f"| {page} | {sec} | {ch.replace('|', '/')} | {why} | open |")
        open(f, "w", encoding="utf-8").write("\n".join(L) + "\n")

    S = [f"# QC routing (round {rnd} of max {MAX_ROUNDS})", "",
         f"Brand QC overall: **{report['overall']}** (FAIL {report['fails']}, REVIEW {report['reviews']})", "",
         "| owner | items | file |", "|---|---|---|"]
    for owner, rows in reqs.items():
        S.append(f"| {owner} | {len(rows)} | {'qc/requests/' + owner + '.md' if rows else '-'} |")
    if pending:
        S += ["", "## Pages not built yet (not a defect; run Steps 2-5 for them)", ""]
        for u, why in sorted(pending.items()):
            S.append(f"- `{u}`: {', '.join(sorted(why))}")
    S.append("")
    if not owner_items:
        S.append("Nothing for owners to fix." + (" Build the pending pages, then rerun." if pending else " Ready to deliver."))
        code = 0
    elif rnd > MAX_ROUNDS:
        S.append(f"Round limit reached. Show the user the open items and let them decide.")
        code = 3
    else:
        S.append("Send each requests file to its owner. After the fixes: rebuild, then rerun qc_route.py.")
        code = 1
    open(os.path.join(proj, "qc", "route.md"), "w", encoding="utf-8").write("\n".join(S) + "\n")
    print("\n".join(S))
    sys.exit(code)


if __name__ == "__main__":
    main()
