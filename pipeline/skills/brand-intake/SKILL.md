---
name: brand-intake
description: Step 1 of the brand-site pipeline. Collect brand, geo and domain, verify brand facts from real sources, and write the project's site.json and QC config.
---

# Brand intake (Step 1)

Goal: one `site.json` that every later step trusts. Nothing in it may be invented.
Pipeline overview and folder layout: `pipeline/README.md` in repo `bimal456/brand-qc`.

## 0. Get the files
Scripts and templates are in the private repo `bimal456/brand-qc` (folder `pipeline/`). In a cloud session attach it with add_repo (owner `bimal456`, repo `brand-qc`) and clone it; paths below are relative to the repo root.

## 1. Ask the user (one round)
Required: **brand**, **geo(s)**, **domain**. Ask in one question round only for what is missing:
- Site type: `brand` (first-party voice), `affiliate-listicle` (ranks several casinos) or `expired-onepage`.
- Affiliate path if not `/play`.
- Names to avoid (sister or parent brands).
- Any rule that differs for this site (reader as "you", accordion FAQ, author byline, noindex, word counts).

## 2. Verify brand facts
Open the brand's real site in the user's browser (Chrome). Read the footer, bonus terms and cashier pages. Record each fact with its source URL and today's date:
- licence: regulator and licence number, with a source (the brand's footer or terms page, or the regulator's register). This fact may appear on the site, so store it with a source and without `"publish": false`; without a source it stays unverified and the site does not mention a licence
- operator company and registration number: only to confirm the brand is real. Store them with `"publish": false`; they never appear on the site
- welcome bonus, wagering, min deposit, max withdrawal, payment methods, game count, providers, support hours and email
Also collect `brand_assets` for the designer, because every brand site copies the look of its original brand:
- logo, brand colours (hex, including button gradients), font names, button shape
- the original site's layout: header and menu (top nav, left sidebar, bottom bar), the home page block order (hero, game rows and their names, promotions, providers, content, FAQ), and how game cards look
- screenshots of the lobby, each game row, promotions and cashier, saved in `<project>/assets-in/`, plus the names and providers of the games shown in each row Casino sites often block visitors outside their market; if the brand site does not open, ask the user for these files instead of guessing.
A fact without a source goes in with an empty `source` and is marked unverified. Later steps must not use unverified facts, so every fact the pages depend on (bonus terms, payments, limits) must be verified here, or the content step fills the page with `[VERIFY]` placeholders.

## 3. Pick pages and keywords
Start from the site type's default pages (brand: home + bonus + login + mandatory pages; listicle: hub + mandatory pages). For each page and geo, check brand-intent keywords with DataForSEO (`dataforseo_labs/google/keyword_suggestions/live` for the brand name, location and language of the geo). Add a page only if its keyword has search demand. Mandatory pages need no keyword.

## 4. Write the files
1. Copy `pipeline/templates/site.example.json` to `<project>/site.json` and fill every field.
2. Run `python3 pipeline/scripts/make_qc_config.py <project>/site.json` to create `qc/config.json`.
3. Self-check before handing off: every geo has location_name and language_code, every non-mandatory page has a keyword per geo, every fact has a source or is marked unverified.

## 5. Hand off
Show the user a short summary: pages and keywords per geo, verified facts, unverified facts, and the criteria that differ from defaults. Step 2 starts after the user confirms; then set `"intake_confirmed": "<date>"` in `site.json`.
