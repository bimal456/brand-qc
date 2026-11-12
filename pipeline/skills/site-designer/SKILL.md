---
name: site-designer
description: Step 4 of the brand-site pipeline. Create the brand's look (theme, templates, CSS, images) from the real brand site, build the pages from the content files, and check them at mobile and desktop widths.
---

# Site designer (Step 4)

Goal: a site that looks like the **original brand's own site**, not an AI template and not a blog article. Every brand gets its own design. You own layout, CSS, templates and images. You never edit `content/` or `seo/`; wording changes go to the content writer as a request.

## 0. Get the files
Scripts and the design starter are in the private repo `bimal456/brand-qc` (folder `pipeline/`). Attach it with add_repo (owner `bimal456`, repo `brand-qc`) and clone it.

## 1. Research the look (Claude in Chrome)
1. Open the brand's original site. Record:
   - look: colours (computed backgrounds, button gradients), font families, logo, button shape, radius, background pattern
   - layout: header and menu style (top nav, left sidebar, bottom bar), the home page block order (hero, game rows and their names, promotions, providers, content, FAQ), the game card style
   - screenshots of the lobby and each game row (computer tool `screenshot` with `save_to_disk`), to crop game thumbnails and section images with Pillow
2. **If the brand site is geo-blocked or unreachable** (casino sites often block visitors outside their market): use `site.json` `brand_assets` (colours, logo, screenshots collected in Step 1). If those are missing, stop and ask the user for the logo, 2-3 brand colours and lobby/promotion screenshots (they can attach them). Never invent a "brand" palette and present it as the real one; if the user says to go ahead without assets, say clearly in the hand-off that the look is a placeholder.
3. Practical notes: Chrome screenshots are downscaled (a 1920px viewport comes back about 1568px wide), so use the zoom action for crisp thumbnail and logo crops. Brand display fonts that are not on Google Fonts need a fallback: use a heavy weight (800) with `font-synthesis:none` so headings keep the brand's weight.
4. Open the reference site from site.json (or the top competitor for the main keyword). Note layout only: header height, content width, how sections and tables are shown. Take ideas, never copy markup, text or images.

## 2. Build the design
1. If `<project>/design/` does not exist yet, copy `pipeline/design-starter/` there. Then change it to the brand:
   - `theme.json`: brand name, logo token, labels per geo (login, register, footer titles, legal line with 18+).
   - `assets/css/site.css`: brand colours and fonts, spacing, tables, footer. Keep it one file, mobile first.
   - `templates/`: base, header and footer. Header carries only the logo plus Login and Register buttons to the play path (both `rel="nofollow sponsored"`). Footer carries the pages list, the geo's responsible-gambling links, the 18+ badge and the legal line.
2. Images: screenshots turned into WebP with Pillow (`quality=82`) and stored in `design/assets/img/`. Place them per page section in `design/images.json` (format in the `build.py` docstring: key `<geo>/<page>`, then `intro` or the section id, with src, alt, width, height). The build inserts them after the section's H2 and sets `fetchpriority`/`lazy` itself. Alt text is localized. No images of real people.
3. Rules from the user:
   - Look of the original brand, unique per brand; never the same template with a new colour. No badge, pill or checkmark overload, no identical repeated card blocks, no letter-badge placeholder logos.
   - No accordion FAQ unless site.json allows it. No age-gate popup.
   - No `#` in any href: same-page jumps use `<button data-jump="id">` (handled by `assets/js/site.js`).
   - Opening of each page stays plain text (no boxes before the first H2).
4. Build a preview: `python3 pipeline/scripts/build.py <project> --draft` (without `--draft` the build stops while `[VERIFY]` placeholders remain).

## 3. Self-check
1. `python3 pipeline/scripts/design_check.py <project> --shots` must PASS (no overflow at 375 or 1366, no console errors, WebP images with alt, no `#` links, nofollow play links, one H1, no heading skips).
2. Open the screenshots in `design/shots/` (top part of each page at both widths) next to the original brand's screenshots and compare: colours, buttons, header and menu, game rows, spacing. Fix what does not match or looks broken, cramped or templated, then rebuild and recheck.

## 4. Hand off
Report: the design choices in 3-5 lines (colours, fonts, layout idea), the check result, and the screenshot files. Step 5 (SEO) adds head tags and site files through `seo/`, and the build picks them up.
