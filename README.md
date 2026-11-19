# Brand QC

QC gate for casino brand sites. Built folder ya live URL pe chalao, PASS / CONDITIONAL PASS / FAIL report milegi (Markdown + JSON).

## Install

    pip install beautifulsoup4 lxml

## Run

    # built site folder (clean URLs: /bonus -> bonus.html or bonus/index.html)
    python3 brand_qc.py ./aphroditeuk-site --config configs/uk.json

    # live site (reads sitemap.xml + homepage links)
    python3 brand_qc.py https://munkkicasinoo.com --config configs/fi.json

Reports go to `./qc-reports/`. Exit code 2 = FAIL, so it can block a deploy step.

## Browser fallback
Agar machine se site reach na ho (proxy / firewall), site ka homepage Chrome mein kholo, `browser_qc.js` ke top pe `CFG` set karo, aur poori file DevTools console mein run karo. Report `window.__brandqc` mein milegi.

## Configs
`configs/<geo>.json` sirf wahi keys override karti hai jo usme hain. Useful keys:
- `play_paths`: affiliate redirect paths (default `["/play"]`)
- `allowed_external_domains`: us geo ke responsible-gambling sites (inke alawa koi external link FAIL)
- `word_count`: home / mandatory / other targets
- `forbidden_names`, `banned_phrases`, `second_person`
- `second_person_ignore`: per-language phrases skipped before the "you" count (e.g. French "rendez-vous", "donne le ton")

Saari keys `configs/example-all-keys.json` aur script ke `DEFAULT_CONFIG` mein hain. Geo configs ke RG domains starting list hain, use karne se pehle ek baar check kar lena.

## Checks
- Structure: single H1, heading skips, word counts (home 5k / mandatory 1k / other 3k), orphan pages, mandatory pages (RG, terms, privacy, about, contact) per language root
- Meta & indexing: title 55-60, description 150-160 + "18+", canonical, og/twitter match, hreflang (self + x-default), duplicate titles/descriptions, sitemap vs pages, robots.txt, HTTP status (live mode), worker files that may rewrite meta
- Links & CTAs: no "#" in href, external nofollow, play CTA nofollow, Register links and Login buttons -> play path (plain Login menu/footer links may open the login page), clean URLs, broken internal links, RG allowlist
- Voice & AI signals: em dashes, reader addressed as "you" (per `<html lang>`, incl. Finnish verb forms), AI phrases, forbidden brand-voice lines, forbidden names, placeholders and dev comments
- Compliance & assets: no review/rating schema, WebP images, alt text, 18+ in footer, 18+ on home, age-gate markup

## Not covered (manual / AI check)
Entity density, topical coverage vs brief, vague claims, licence-claim verification, bonus/T&C accuracy, templated section patterns.
