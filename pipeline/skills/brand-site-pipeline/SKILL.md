---
name: brand-site-pipeline
description: Orchestrate a full casino brand-site build from brand, geo and domain: run the six pipeline steps as separate agents in order, enforce the gates, route QC fixes to owners, and deliver.
---

# Brand site pipeline (orchestrator)

You are the coordinator. You do not write content, design pages or edit SEO files yourself. Each step runs as its own agent with its own skill; you start the agents, check their output with the scripts, enforce the gates, and keep the user informed.

## 0. Setup
1. Attach the private repo `bimal456/brand-qc` (add_repo owner `bimal456`, repo `brand-qc`) and clone it to `/tmp/brand-qc`. Install: `pip install beautifulsoup4 lxml playwright --break-system-packages` and `python3 -m playwright install chromium`.
2. Inputs from the user: **brand, geo(s), domain**. Optional: reference site, affiliate link, page list, criteria that differ from the defaults. Ask only for brand, geo and domain if missing; everything else Step 1 collects.
3. Project folder: the folder the user names, an existing project folder for this domain, or else `/tmp/projects/<domain>/`. If the user attached a `project-<domain>.zip` from an earlier chat, unzip it there and continue from where it stopped.
4. Run `python3 /tmp/brand-qc/pipeline/scripts/pipeline_status.py <project>` at the start and after every step. It shows per page and geo which steps are done and what is next. Keep a task list with one item per step.

## 1. How to start a step agent
Use the Agent tool, one agent per job. The prompt names:
- the skill (`brand-intake`, `serp-architect`, `content-writer`, `humanize-pass`, `site-designer`, `seo-optimizer`): "read `/tmp/brand-qc/pipeline/skills/<skill>/SKILL.md` and follow it". The repo copy is always the current one, so it wins over an installed skill of the same name;
- the project folder and repo path, and "run every script from the repo root (`cd /tmp/brand-qc`) with the project's absolute path";
- the exact scope (which pages and geos, or which requests file);
- "Do not change files you do not own. End with the self-check output and a list of anything you could not do."

Run independent jobs in parallel (one agent per page for Steps 2 and 3). Never give one agent several steps. Step agents do not start agents of their own: you already split the work.

Shared files have one writer, you: `brief/APPROVAL.md` (page agents return their row and you merge it, keeping existing `approved` rows), `qc/requests/*` (written by `qc_route.py`) and the progress zip.

## 2. The run

| Step | Agents | Done when (you check, do not trust the report) |
|---|---|---|
| 1 Intake | 1 x `brand-intake` | `site.json` and `qc/config.json` exist; status shows intake complete |
| 2 SERP | 1 x `serp-architect` per page and geo | `brief/<geo>/<page>/outline.md` for every page; `brief/APPROVAL.md` written |
| 3 Content | 1 x `content-writer` per page, then 1 x `humanize-pass` per page | `content_check.py` has no FAIL for every page (`[VERIFY]` placeholders allowed until facts arrive) |
| 4 Design | 1 x `site-designer` for the whole site | `build.py` runs; `design_check.py` has no FAIL |
| 5 SEO | 1 x `seo-optimizer` | `seo_check.py` has 0 open requests (or round 2 done); `seo/files/` exists |
| 6 QC | you run `qc_route.py` | `qc/route.md` ends with "Ready to deliver" (exit 0 with pending pages only means no defects in the built pages) |

Step 1 gate state: when you show the intake summary and the user confirms, add `"intake_confirmed": "<date>"` to `site.json`. Gate 2 state is the `approved` status in `APPROVAL.md`. A `[VERIFY]` fact the user supplies goes into `site.json` facts first (brand-intake), then the content agent fills it in.

Mandatory pages (responsible gambling, terms, privacy, about, contact) need no SERP calls: the SERP agent writes their outline from `site.json` facts and the geo's responsible-gambling rules, with the word target from `site.json` criteria.

## 3. Gates (stop and ask the user)
1. **After Step 1:** show brand facts with their sources, unverified facts, page list with keywords, and criteria. Continue when the user confirms.
2. **After Step 2:** show `brief/APPROVAL.md`. Steps 3+ start only for pages marked `approved`. Record the user's changes in the outlines.
3. **Before the final build:** list every `[VERIFY: ...]` placeholder. The user supplies the facts (or approves removing the sentence); a content agent fills them in. `build.py` refuses to build without `--draft` while any remain.
4. **Affiliate link:** never invent it. If it is missing, keep the `/play` redirect target as the placeholder and say so at delivery.

When the user is not there to answer, finish the work up to the gate, send what is ready, and stop. Do not pass a gate on the user's behalf.

## 4. Step 6 loop
1. Rebuild: `python3 /tmp/brand-qc/pipeline/scripts/seo_build.py <project>` (hreflang and head tags for every page, also new ones), then `python3 /tmp/brand-qc/pipeline/scripts/build.py <project>` (plus `--draft` only for previews).
2. Run `python3 /tmp/brand-qc/pipeline/scripts/qc_route.py <project>`. It runs Brand QC on `build/` with `qc/config.json` and writes `qc/requests/content.md`, `design.md`, `seo.md`, `intake.md` and `qc/route.md`.
   - Exit 0: nothing for owners. If `route.md` lists pages not built yet, go back to Step 2 for those pages; otherwise deliver.
   - Exit 1: start one agent per requests file (content to `content-writer`, design to `site-designer`, seo to `seo-optimizer`, intake to `brand-intake`) with "apply qc/requests/<owner>.md, mark each row done or refused: reason". Content changes also go through `content_check.py`; if a heading changed, rerun `seo_check.py`. Then rebuild and rerun `qc_route.py`.
   - A round counts only when rows go to owners; `qc/round.txt` holds it.
   - Exit 3: two fix rounds are used up. Show the user the open rows and refused requests and let them decide.
3. After the script passes, run the brand-qc skill's manual checks (licence claims, TOC links counted as CTAs, entity coverage, templated sections) yourself and route anything found the same way.

## 5. Save progress
Whenever you stop (at a gate, waiting for the user, or at the end), zip the project (`project-<domain>.zip`, without `build/assets` images if over 50 MB) and send it to the user with SendUserFile, so the next chat can continue from it.

## 6. Deliver
1. Before zipping, check the final build (not `--draft`) passed: favicon, `sitemap.xml`, `robots.txt` and hreflang are in `build/`. `build/` as a ZIP ready for Cloudflare (uses `_redirects`, `_headers`) or cPanel (`.htaccess`), plus one self-contained HTML preview of the home page.
2. Final report in the user's language: pages per geo with word counts, Brand QC verdict, refused requests and why, everything the user still has to supply (affiliate link, facts, og image, logo files).

## Rules that apply to every agent
Brand speaks as "we / our / <brand>", the reader is never addressed as "you" unless `site.json` allows it, no em dashes, no other operators or brands named, external links only to the geo's responsible-gambling resources, every CTA and external link nofollow, every Register link and every Login *button* (header buttons, CTA buttons) goes to `/play`, while plain Login text links in the side menu or footer may open the site's own login page, no agency name anywhere on the site, no 18+ popup (18+ badge in the footer only), no operator, licence, licence number or regulator words anywhere (regulators only as help resources on the responsible-gambling page), no "glance" / "at a glance", the login page says Login (or the geo's login word) and never "Access Account", hreflang on every page, favicon and sitemap present, lists/steps/tables instead of walls of paragraphs, only headings from the approved outline (no slogan headings), no "independent", clean URLs without `.html` or a trailing slash.
