---
name: content-writer
description: Step 3 of the brand-site pipeline. Write page content section by section from an approved outline into content/<geo>/<page>.md, then self-check it.
---

# Content writer (Step 3)

Goal: content that follows the approved outline and the site's voice, with no invented facts. You own all wording on the site; SEO and QC send change requests to you.
Input: `<project>/site.json` and `brief/<geo>/<page>/outline.md` with status `approved` in `brief/APPROVAL.md`. Do not start on an unapproved outline.

**Fact gate:** list the facts the outline's Entities need. If the page's core facts (for a bonus page: bonus amount, wagering, minimum deposit) are not verified in site.json, stop and send the page back to Step 1 with that list. Do not write a page that would be mostly placeholders.

## 0. Get the files
Scripts are in the private repo `bimal456/brand-qc` (folder `pipeline/`). Attach it with add_repo (owner `bimal456`, repo `brand-qc`) and clone it.

## 1. One sub-agent per page and geo
Each page is written by its own sub-agent with only: site.json, that page's outline and consensus.md, and this skill. It returns a 3-line summary.

## 2. Write
- File: `content/<geo>/<page>.md`, starting with the front-matter shown in `pipeline/scripts/content_check.py` (slug, geo, lang, type, title, description, h1, target_words). Body is markdown: intro, then `##` H2 and `###` H3 exactly as in the outline. No H1 in the body.
- Write **one section at a time**, in outline order. Before each section reread its intent, points and word target from the outline. Do not write the whole page in one go.
- Write natively in the geo's language. Never translate from English.
- **Facts:** only claims from site.json `facts` that have a source. When the outline and site.json disagree on whether a fact is verified, site.json wins. A number, licence, operator name or bonus term that is not verified is left out or written as a placeholder `[VERIFY: ...]`, never guessed. The placeholder replaces only the value inside a normal sentence. Never write sentences about the site's own process ("figures are confirmed before publishing", "search results show"): they read as dev notes on a live page.
- **Voice (site.json `voice`):** brand speaks as "we / our / [Brand]" for brand sites. If `address_reader_as_you` is false, never address the reader: no "you", and in Finnish no 2nd-person verbs (voit, saat, haluat, talletat) or imperatives; use passive or impersonal forms. Never "official site", "we are not the operator", "information only". This also applies to CTA and meta examples copied from the outline: rewrite imperatives (katso, tutustu, lue) into impersonal forms.
- **Brand name:** use site.json `brand` as the main spelling. Aliases (for example "Munkki Kasino") only where the page keyword needs them.
- **No em dashes.** Hyphens are fine.
- **Intro:** follows the outline's intro brief. Plain text, no boxes or lists in the opening.
- **Style:** answer the section's question in the first one or two sentences, then detail. Vary sentence length. Concrete numbers and examples over adjectives. Lists and tables only where the content is comparable. No filler sections, no "In conclusion".
- **Links:** internal links to other site pages where natural. External links only to the geo's responsible-gambling resources. CTAs point to the play path; vary the anchor text, keep it soft.
- **FAQ:** flat questions and answers unless site.json allows an accordion.

## 3. Self-check (before handing off)
Run `python3 pipeline/scripts/content_check.py content/<geo>/<page>.md --outline brief/<geo>/<page>/outline.md`. Fix every FAIL and rerun until it passes. `[VERIFY]` placeholders do not count toward the word target, so write the real words around them. Leave REVIEW items you cannot fix (for example numbers waiting for verification) and list them in your summary.

## 4. Hand off
Summary per page: words, H2 count, check result, open `[VERIFY]` placeholders. The humanize pass (`humanize-pass` skill) runs next on the same file.

## Change requests
When SEO or QC sends a request (page, section, change, reason), apply it if it keeps the voice and fact rules; otherwise refuse and say why. Mark each row `done` or `refused: <reason>` in the requests file. When a request changes a heading, change the same heading in the outline so outline and page stay in step. Rerun the self-check after every change.
