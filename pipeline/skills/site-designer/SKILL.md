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
1. If `<project>/design/` does not exist yet, copy `pipeline/design-starter/` there (a casino-lobby starter: sidebar, header, hero, game carousels, promos, content with sticky table of contents, providers, CTA band). Then rebuild it into the original brand's look and layout:
   - `layouts.json`: block order per page type, matching the original (for example home `["hero", "games:popular", "games:new", "promos", "content", "providers", "cta"]`). Inner pages get a shorter set; mandatory pages usually just `content`. A single page can be overridden with a `"<geo>/<page>"` key.
   - `data/games.json`: game rows named like the original (localized), each item a real game with name, provider and a cropped WebP thumbnail. `data/promos.json` only from verified facts. `data/providers.json`.
   - `assets/css/site.css`: change the variables at the top (colours, gradients, fonts, radius, shadows) and the component styles until the screenshots look like the original. One file, mobile first.
   - `templates/`: base, header, sidebar (empty it if the original has none), footer and `blocks/`. Play-path links are always `rel="nofollow sponsored"`. Footer carries the pages list, the geo's responsible-gambling links, the 18+ badge and the legal line.
   - Header nav: follow the original brand's header unless `site.json` `criteria.header_page_links` is false; then the header carries only the logo plus Login/Register and page links move to the sidebar or footer. The current page's link carries `aria-current="page"`; style it.
   - Labels and the footer legal line never mention an operator, licence or regulator. The login label is the geo's normal login word (Login, Accedi, Kirjaudu), never "Access Account".
   - `theme.json`: brand name, logo token (inline SVG or `<img>` with width and height), labels per geo (any extra label key becomes a template token), `toc` on or off.
2. Images: follow section 2b. No images of real people.
3. Rules from the user:
   - Look of the original brand, unique per brand; never the same template with a new colour. No badge, pill or checkmark overload, no identical repeated card blocks, no letter-badge placeholder logos.
   - No accordion FAQ unless site.json allows it. No age-gate popup.
   - No `#` in any href: same-page jumps use `<button data-jump="id">` (handled by `assets/js/site.js`).
   - The intro text inside the hero stays plain prose (no lists, tables or cards inside it).
4. Build a preview: `python3 pipeline/scripts/build.py <project> --draft` (without `--draft` the build stops while `[VERIFY]` placeholders remain).

## 2b. Image plan (every page, before the build)
A page must never turn into a wall of text: the lobby blocks at the top are not enough. Plan the visuals of every page in `design/image_plan.json` (format at the top of `pipeline/scripts/make_images.py`) and let the script write `design/images.json`.

1. **Slots:** build once with `--draft`, then `python3 pipeline/scripts/make_images.py <project> --slots` lists each page's slots: `hero`, `intro`, every section id, and `<id>@end`. Copy the ids exactly; they keep the page's own letters (ä, à).
2. **How many:** one visual at least every 800-1000px of text at desktop width (roughly every 1-2 H2 sections), and every page gets its **own hero art**. Never the same hero on two pages.
3. **Pick the source per visual:**
   | Need | Source | How |
   |---|---|---|
   | Hero art per page, promo card art, section illustrations (gift and coins for bonus, wallet for withdrawal, coins for payments, phone for login, trophy for VIP) | `chatgpt` | generated in ChatGPT in the user's Chrome (below) |
   | Game tiles, provider logos, real lobby, cashier or app views of the brand | `screenshot` | from the original brand site in Chrome: `zoom` action on the area (sharper than a full screenshot), saved to `design/raw/` |
   | Steps (signup, deposit, withdrawal), one big verified number, tier ladders, comparisons | `css` | copy a component from `design-starter/visuals/` to `design/visuals/<page>-<name>.html` |
   | A row of real games inside a long section | `games` | tiles from `data/games.json`, no extra heading |
4. **ChatGPT images** (Claude in Chrome, user's own ChatGPT account):
   - Write one `style` line for the whole site from the original brand: background colour, accent colour, render style (3D cartoon, flat, photo-like). The same style goes in front of every prompt, so all images look like one set. Always end it with "no text, no letters, no logos, no people".
   - `make_images.py <project> --prompts` prints the prompts still to make. Open chatgpt.com in a new tab, one prompt per message, wait for the image, download it. Ask the user once before the first download (filename, source chatgpt.com) and say how many files will follow.
   - Never ask for real game characters, other brands' mascots or the brand's own logo or mascot; generic objects only. Never put words in the image: headings stay in HTML.
   - Downloaded files land in the user's Downloads folder. Get access to that folder (device folder access tools) and stage the files into `design/raw/<id>.png`. If that is not possible, ask the user to attach them.
   - Check each image before use: no garbled letters, matches the style, subject clear at small size. Regenerate a bad one once, then pick the best.
5. **Sharpness:** every image file must be 2x its display size. `make_images.py` cover-crops and saves at 2x and warns when the source is too small. Game tiles from the original site: take the biggest version available (zoom screenshot), never upscale.
6. **Words inside CSS visuals** (step titles, labels, numbers) come from the page's content file or `site.json` facts, word for word. No new claims. If the right words are missing, ask the content writer through a request.
7. Run `python3 pipeline/scripts/make_images.py <project>` (it lists anything still missing), then build. The build warns about slots that match no section.

## 3. Self-check
1. `python3 pipeline/scripts/design_check.py <project> --shots` must PASS (no FAIL: no overflow at 375 or 1366, no console errors, WebP images with alt, no `#` links, nofollow play links, 18+ and responsible-gambling links in the footer, one H1, no heading skips, no stretch of main content over 1800px without a visual, no upscaled image). Fix REVIEW notes about soft images (under 2x) and stretches over 1200px too. Other REVIEW notes about web fonts not loading in the sandbox or links to pages not built yet are fine.
2. Open the screenshots in `design/shots/` (top part of each page at both widths) next to the original brand's screenshots and compare: colours, buttons, header and menu, game rows, spacing. Fix what does not match or looks broken, cramped or templated, then rebuild and recheck.

## 4. Hand off
Report: the design choices in 3-5 lines (colours, fonts, layout), the image plan per page (how many visuals from each source, any still missing), whether they come from the original brand or are a placeholder, what still differs from the original, the check result, and the screenshot files. Step 5 (SEO) adds head tags and site files through `seo/`, and the build picks them up.

## Change requests
QC sends template, CSS, image and link fixes in `qc/requests/design.md` (page | section | change | reason | status). Fix them in `design/` only, never in `content/` or `seo/`. A wording problem goes back to the content writer as a request. Rebuild, rerun `design_check.py`, and mark each row `done` or `refused: <reason>`.
