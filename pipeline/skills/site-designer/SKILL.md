---
name: site-designer
description: Step 4 of the brand-site pipeline. Create the brand's look (theme, templates, CSS, images) from the real brand site, build the pages from the content files, and check them at mobile and desktop widths.
---

# Site designer (Step 4)

Goal: a site that looks like a real brand, not an AI template. You own layout, CSS, templates and images. You never edit `content/` or `seo/`; wording changes go to the content writer as a request.

## 0. Get the files
Scripts and the design starter are in the private repo `bimal456/brand-qc` (folder `pipeline/`). Attach it with add_repo (owner `bimal456`, repo `brand-qc`) and clone it.

## 1. Research the look (Claude in Chrome)
1. Open the brand's real site. Read with the javascript tool: main colours (computed background and button colours), font families, logo (SVG or image URL), button shape and radius. Take screenshots of the lobby, promotions and cashier for section images.
2. Open the reference site from site.json (or the top competitor for the main keyword). Note layout only: header height, content width, how sections and tables are shown. Take ideas, never copy markup, text or images.

## 2. Build the design
1. Copy `pipeline/design-starter/` to `<project>/design/` and change it to the brand:
   - `theme.json`: brand name, logo token, labels per geo (login, register, footer titles, legal line with 18+).
   - `assets/css/site.css`: brand colours and fonts, spacing, tables, footer. Keep it one file, mobile first.
   - `templates/`: base, header and footer. Header carries only the logo plus Login and Register buttons to the play path (both `rel="nofollow sponsored"`). Footer carries the pages list, the geo's responsible-gambling links, the 18+ badge and the legal line.
2. Images: screenshots turned into WebP with Pillow (`quality=82`), stored in `design/assets/img/`, always with width, height and a localized alt. First image `fetchpriority="high"`, the rest `loading="lazy"`.
3. Rules from the user:
   - Editorial look, unique per brand. No badge, pill or checkmark overload, no identical repeated card blocks, no letter-badge placeholder logos.
   - No accordion FAQ unless site.json allows it. No age-gate popup.
   - No `#` in any href: same-page jumps use `<button data-jump="id">` (handled by `assets/js/site.js`).
   - Opening of each page stays plain text (no boxes before the first H2).
4. Build a preview: `python3 pipeline/scripts/build.py <project> --draft` (without `--draft` the build stops while `[VERIFY]` placeholders remain).

## 3. Self-check
1. `python3 pipeline/scripts/design_check.py <project> --shots` must PASS (no overflow at 375 or 1366, no console errors, WebP images with alt, no `#` links, nofollow play links, one H1, no heading skips).
2. Open the screenshots in `design/shots/` (top part of each page at both widths) and look at them. Fix anything that looks broken, cramped or templated, then rebuild and recheck.

## 4. Hand off
Report: the design choices in 3-5 lines (colours, fonts, layout idea), the check result, and the screenshot files. Step 5 (SEO) adds head tags and site files through `seo/`, and the build picks them up.
