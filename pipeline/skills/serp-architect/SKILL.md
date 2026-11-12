---
name: serp-architect
description: Step 2 of the brand-site pipeline. Run SERP analysis per page keyword and geo, build consensus data, and write SERP-validated outlines for user approval.
---

# SERP architect (Step 2)

Goal: an approved outline per page and geo, built from what ranks, not from what AI thinks is good.
Input: `<project>/site.json` from Step 1. Pipeline overview: `pipeline/README.md` in repo `bimal456/brand-qc`.

## 0. Get the files
Scripts and templates are in the private repo `bimal456/brand-qc` (folder `pipeline/`). In a cloud session attach it with add_repo (owner `bimal456`, repo `brand-qc`) and clone it; paths below are relative to the repo root.

## 1. One sub-agent per keyword
Each keyword costs about 20-30k tokens (SERP call about 3k, each competitor page about 2.5k). Run every page keyword per geo in its own sub-agent so no single context fills up. Give each sub-agent: the keyword, the geo's `location_name` and `language_code`, the brand tokens, the output folder `brief/<geo>/<page>/`, and steps 2-3 below. It returns only a 3-line summary.

## 2. Collect (inside the sub-agent)
1. SERP: DataForSEO `POST /v3/serp/google/organic/live/advanced` with keyword, location_name, language_code, depth 10. Keep the organic results, "people also ask" and related searches. Record the call's datetime as `serp_call`. Results change between calls, so the ranking always comes from this first call.
2. Result URLs are `google.com/goto` redirects that **expire within seconds**. For every result, in rank order, build the direct URL from its `breadcrumb` (`https://site.com › a › b` -> `https://site.com/a/b/`). Use the redirect link only when the breadcrumb is cut off (`...`), and only straight after the SERP call.
3. Pages: skip `official` and `review-platform` results; they are not used for the shape. For the rest call DataForSEO `POST /v3/on_page/instant_pages`, **one URL per call** (a batch only processes the first), with `accept_language`. Keep only: final url, title, description, htags h1/h2/h3, `content.plain_text_word_count`. Do not retry a failed page more than once.
   - Backup only, when instant_pages fails on a page (error, geo block, under 200 words of real text) and Claude in Chrome is available: open the URL in one new tab, run the code of `pipeline/scripts/page_headings.js` with the javascript tool (returns URL, word count, title, description, H1/H2/H3), then close the tab. Never use the browser for the Google search itself.
4. Classify each result: `official` (operator site), `own-site` (our domain), `affiliate`, `jump-link` (affiliate redirect that lands on the operator), `review-platform` (Trustpilot etc.), `forum` or `other`. Set `"exclude": true` with a reason when the URL resolved to a different or generic page (for example a general casino hub for a brand keyword).
5. If fewer than 5 usable competitor pages remain, run the same steps for one close keyword variant (or depth 20) and add those results.
6. Write `serp.json` in the schema at the top of `pipeline/scripts/serp_consensus.py` (put related searches in `related` when there is no people-also-ask), then run `python3 pipeline/scripts/serp_consensus.py brief/<geo>/<page>/serp.json`.

## 3. Outline (inside the sub-agent)
Read `consensus.md` and write `brief/<geo>/<page>/outline.md`:
- **Intent and format**: what type of page ranks (review, listicle, guide) and what our page must be.
- **Meta**: title pattern and description angle, based on the ranking titles.
- **H1** and **intro brief**: how the top 3 open (length, first claim, numbers up front).
- **Sections**: H2/H3 tree in order. Each section has its intent in one line, 2-5 points to cover, and a target word count. Consensus topics (used by half the competitors or more) are mandatory. Add 1-3 single-competitor topics as information gain when they fit.
- **Entities**: terms, products and facts the page must mention (only facts that are verified in site.json).
- **FAQ**: questions from "people also ask"; if there are none, from related searches and competitor FAQ headings. In the geo's language.
- **Total words**: the top-5 competitor median, but never below the site.json criteria for that page type.
Headings, meta examples and CTA examples follow site.json voice rules (no "you" or imperatives unless allowed). Never copy a competitor heading word for word.

## 4. Approval gate
When all sub-agents finish, write `brief/APPROVAL.md`: one line per page and geo with H1, H2 count and target words, and a status of `pending`. Show it to the user. Steps 3+ start only after the user approves; record changes they ask for in the outline and set the status to `approved`.
