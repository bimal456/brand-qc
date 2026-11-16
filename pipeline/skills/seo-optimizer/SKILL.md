---
name: seo-optimizer
description: Step 5 of the brand-site pipeline. Generate the technical SEO layer (head tags, schema, hreflang, sitemap, robots, redirects, headers), check on-page SEO, and send wording changes to the content writer as requests.
---

# SEO optimizer (Step 5)

Goal: every page is technically complete and on-page optimised, without touching wording or design. You own the `seo/` folder. Content changes go to the content writer as requests; layout changes go to the designer.

## 0. Get the files
Scripts are in the private repo `bimal456/brand-qc` (folder `pipeline/`). Attach it with add_repo (owner `bimal456`, repo `brand-qc`) and clone it.

## 1. Technical layer
1. Check `site.json`: `affiliate_link` is a real URL, `indexing` is set (`index` or `noindex`), `www` is set, every geo has `hreflang`, every page has its `slug` (or `slugs` per geo). Ask the user for anything missing; never invent an affiliate link.
2. Run `python3 pipeline/scripts/seo_build.py <project>`. It writes:
   - `seo/head/<geo>/<page>.html`: robots meta, og and twitter tags, hreflang (self, other geos, x-default), JSON-LD (Organization, WebSite, WebPage, BreadcrumbList, FAQPage when the page has an FAQ section). Never Review or AggregateRating schema.
   - `seo/files/`: robots.txt, sitemap.xml with alternates, `_redirects` and `_headers` (Cloudflare), `.htaccess` (cPanel: https, canonical host, clean URLs, play redirect).
3. If the designer has not made `design/assets/img/og.jpg` (1200x630), ask the designer for it.

## 2. On-page checks and requests
1. Run `python3 pipeline/scripts/seo_check.py <project>`. It writes `seo/requests.md`: one row per change (page, section, change, reason), for meta length, keyword in title, description, H1, intro and H2s, keyword density (inflected forms count), internal links, orphan pages and duplicates.
2. Read the requests and remove any that would break `site.json` voice or fact rules or make the text unnatural; note why.
3. Hand `seo/requests.md` to the content writer (`content-writer` skill, "Change requests"). Do not edit `content/` yourself.
4. After the content writer is done: rerun `seo_build.py` (titles and descriptions feed the head tags) and `seo_check.py`. Maximum 2 rounds; then list what is still open for the user.

## 3. Build and hand off
1. Rebuild: `python3 pipeline/scripts/build.py <project>` (add `--draft` only for previews while `[VERIFY]` placeholders remain).
2. Hand off to Step 6 (`brand-qc`) with `qc/config.json`. Report: pages, schema types per page, hreflang set, open requests, and anything the user must supply (affiliate link, og image).

## QC requests
QC sends head-tag, schema, hreflang, sitemap and robots fixes in `qc/requests/seo.md`. Fix them in `site.json` SEO fields or by rerunning `seo_build.py` (fix the script in the repo when the bug is in it), rebuild, and mark each row `done` or `refused: <reason>`.

## Always
- Every page gets hreflang (self + x-default, plus the other geos): run `seo_build.py` after every content change and before every build. `build.py` refuses a final build when a page has no SEO head file or no hreflang.
- `sitemap.xml` and `robots.txt` come from `seo_build.py` and must list every built page; `build.py` refuses a final build when they are missing or a page is not in the sitemap. A single-file HTML preview has no sitemap: check the ZIP or the live site.
- Schema never carries licence, operator or regulator data (no `credentialCategory`, no legalName of the operator).
