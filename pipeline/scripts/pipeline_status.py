#!/usr/bin/env python3
"""Where is this project? Reads the project folder (no network) and prints, per page and geo,
which pipeline steps are done, plus the next action. The orchestrator runs this first in every chat.

Usage: python3 pipeline_status.py <project> [--json]
"""
import json, os, re, sys

STEPS = ["1 intake", "2 serp", "2 approved", "3 content", "3 humanized", "4 built", "5 seo", "6 qc"]


def exists(*p):
    return os.path.exists(os.path.join(*p))


def read(*p):
    f = os.path.join(*p)
    return open(f, encoding="utf-8").read() if os.path.exists(f) else ""


def open_rows(text):
    return sum(1 for l in text.splitlines() if l.startswith("|") and re.search(r"\|\s*open\s*\|\s*$", l))


def main():
    proj = sys.argv[1]
    as_json = "--json" in sys.argv
    if not exists(proj, "site.json"):
        print("Step 1 not started: no site.json. Next: brand-intake.")
        return
    site = json.load(open(os.path.join(proj, "site.json"), encoding="utf-8"))
    approval = read(proj, "brief", "APPROVAL.md")
    seo_open = open_rows(read(proj, "seo", "requests.md"))
    route = read(proj, "qc", "route.md")
    qc_clean = "Ready to deliver" in route
    missing_intake = [k for k in ("brand", "domain", "geos", "pages", "intake_confirmed") if not site.get(k)]
    if not exists(proj, "qc", "config.json"):
        missing_intake.append("qc/config.json")

    rows = []
    for g in site["geos"]:
        code = g["code"]
        for p in site["pages"]:
            slug = (p.get("slugs") or {}).get(code, p.get("slug", "/"))
            name = "home" if slug.strip("/") == "" else slug.strip("/").replace("/", "-")
            pre = g.get("prefix", "/").strip("/")
            built_rel = (pre + "/" if pre else "") + ("index" if name == "home" else slug.strip("/")) + ".html"
            appr = re.search(r"^\|\s*" + re.escape(slug) + r"\s*\|\s*" + code + r"\s*\|.*\|\s*approved\s*\|\s*$",
                             approval, re.M)
            st = {
                "1 intake": not missing_intake,
                "2 serp": exists(proj, "brief", code, name, "outline.md"),
                "2 approved": bool(appr),
                "3 content": exists(proj, "content", code, f"{name}.md"),
                "3 humanized": exists(proj, "content", code, f"{name}.before-humanize.md"),
                "4 built": exists(proj, "build", built_rel),
                "5 seo": exists(proj, "seo", "head", code, f"{name}.html"),
                "6 qc": qc_clean,
            }
            nxt = next((s for s in STEPS if not st[s]), None)
            rows.append({"geo": code, "page": slug, "type": p.get("type"), "steps": st, "next": nxt})

    if as_json:
        print(json.dumps({"rows": rows, "seo_open_requests": seo_open, "intake_missing": missing_intake},
                         indent=2))
        return
    print(f"# {site['brand']} ({site['domain']})\n")
    print("| geo | page | " + " | ".join(STEPS) + " | next |")
    print("|---|---|" + "---|" * len(STEPS) + "---|")
    for r in rows:
        cells = ["x" if r["steps"][s] else "." for s in STEPS]
        print(f"| {r['geo']} | {r['page']} | " + " | ".join(cells) + f" | {r['next'] or 'done'} |")
    print()
    if missing_intake:
        print("Intake incomplete:", ", ".join(missing_intake))
    if seo_open:
        print(f"SEO requests still open: {seo_open} (seo/requests.md)")
    qreq = os.path.join(proj, "qc", "requests")
    if os.path.isdir(qreq):
        for f in sorted(os.listdir(qreq)):
            if re.fullmatch(r"[a-z]+\.md", f):
                n = open_rows(read(qreq, f))
                if n:
                    print(f"QC requests open for {f[:-3]}: {n} (qc/requests/{f})")
    first = next((r for r in rows if r["next"]), None)
    order = {s: i for i, s in enumerate(STEPS)}
    lowest = min((order[r["next"]] for r in rows if r["next"]), default=None)
    if lowest is None:
        print("Next: deliver.")
    else:
        step = STEPS[lowest]
        pages = [f"{r['geo']}{r['page']}" for r in rows if r["next"] == step]
        print(f"Next: step {step} for {len(pages)} page(s): {', '.join(pages[:12])}{' ...' if len(pages) > 12 else ''}")


if __name__ == "__main__":
    main()
