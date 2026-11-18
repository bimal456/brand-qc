---
name: humanize-pass
description: Step 3b of the brand-site pipeline. Run three separate passes on a written content file (strip AI patterns, add human signals, tune for search and AI extraction) without changing facts or structure.
---

# Humanize pass (Step 3b, the "MSO")

Goal: the same page, reading like an experienced person wrote it. Runs on `content/<geo>/<page>.md` after the content writer's self-check passes.

## 0. Get the files
The check script is in the private repo `bimal456/brand-qc` (folder `pipeline/`). Attach it with add_repo (owner `bimal456`, repo `brand-qc`) and clone it.

## Hard limits (all passes)
- Do not change headings, their order or their level, lists, numbered steps or tables (their wording may be tightened), the front-matter, facts, numbers, links or `[VERIFY]` placeholders.
- Do not add new claims. Every concrete detail added must already be supported by site.json facts or the existing text.
- Keep the site.json voice rules (no "you" unless allowed, brand first person, no em dashes).
- Word count stays within 5% of the original.

Read the file **once**, note what to change for all three passes below, then apply the changes as targeted edits (Edit tool, a few lines at a time). Never rewrite the whole file and never re-read it in full between passes. Usually the content writer's own agent runs this pass at the end of its page.

## Pass 1: strip AI patterns
Remove or rewrite:
- stock phrases ("in today's", "it's important to note", "whether you're", "navigating", "seamless", "in conclusion" and their equivalents in the page's language)
- sentences that restate the heading, empty openers and empty closers of a section
- triplets of adjectives, every paragraph ending in a summary line, the same sentence shape repeated
- hedging stacks ("can often typically")
- Never turn a list, numbered steps or a table into paragraphs, and never add or rename headings. A 2-item list may become one sentence; anything with 3 or more items, steps or comparable values stays a list or table.

## Pass 2: human signals
- Vary rhythm: mix short sentences with longer ones; break any run of similar sentences.
- Replace a generic statement with the concrete detail that exists in the facts (an amount, a time, a step, a game name).
- Add a plain opinion or practical note where it helps a decision, in the brand's voice (for example which option suits a small deposit). No fake personal stories, no invented testimonials.
- Use the words people in that market use (check competitor headings in `brief/<geo>/<page>/consensus.md`).
- Sentences that describe the site's own process ("figures are confirmed before publishing") are dev notes: rewrite them into a normal sentence around the placeholder, keeping the placeholder, and list them in the report.

## Pass 3: search and extraction
- Each section starts with a one or two sentence direct answer to its heading.
- Keyword and close variants appear naturally in the intro and in some H2 sections; never forced, never stuffed.
- Comparable data (amounts, limits, times) sits in a short list, or a table when real numbers sit side by side, so search engines and AI answers can extract it. Never add a table beyond the page limit (2, home 3, mandatory 1) and never add a pros/cons block. A paragraph that walks through steps (first, then, next, finally) becomes a numbered list.
- FAQ answers start with the answer, then one line of detail: 30-50 words, never over 60.
- Skip a table when its values would be `[VERIFY]` placeholders.

## Check and hand off
Run `python3 pipeline/scripts/content_check.py content/<geo>/<page>.md --outline brief/<geo>/<page>/outline.md` before and after. The pass must add no new FAIL or REVIEW item; flags that come from the original content (word shortfall, open placeholders) go back to the content writer, not to this pass. Report what changed per pass in 3-6 lines.
