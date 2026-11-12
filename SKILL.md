---
name: brand-qc
description: Run the Brand QC gate on a casino brand or affiliate site (live URL or built folder) and report PASS / CONDITIONAL PASS / FAIL with numbered issues and fixes.
---

# Brand QC

Deterministic QC gate for casino brand sites. The rules live in the script, not in this file. Run it, then report.

## 1. Get the tool
The files are in the private GitHub repo `bimal456/brand-qc` (brand_qc.py, browser_qc.js, configs/).
- In a cloud session: attach the repo (add_repo owner `bimal456`, repo `brand-qc`) and clone it to `/tmp/brand-qc`.
- If the repo cannot be reached, ask the user to attach `brand-qc.zip` and unzip it.
- Install: `pip install beautifulsoup4 lxml --break-system-packages`

## 2. Pick a config
`configs/<geo>.json` sets the allowed responsible-gambling domains and play paths for that market (fi, fr, nl, uk exist). If the site uses a different affiliate path (e.g. `/pelaa`), add it to `play_paths` in a copy of the config.

## 3. Run
- Built folder: `python3 brand_qc.py /path/to/site --config configs/fi.json`
- Live site: `python3 brand_qc.py https://domain.com --config configs/fi.json`
- If the workspace cannot reach the site (proxy 403 / connection error): open the homepage in the user's browser, set `CFG` at the top of `browser_qc.js` to match the config, run the whole file with the javascript tool, and read `window.__brandqc` in 1000-character slices.

## 4. Report to the user
One site per report. Write the reply in the user's language (Hinglish if they write Hinglish), with:
1. Overall verdict and FAIL / REVIEW counts.
2. A short "what passed" list.
3. Numbered issues, most severe first. For each: what is wrong (page and count), then **Fix:** written in English.
4. A word-count table when pages are under target.
5. A priority order (quick template fixes first, content rewrites last).

Before reporting, sanity-check findings the script cannot judge:
- Links counted as "CTA not to play" that are really in-page table-of-contents links.
- Licence or operator claims (schema `credentialCategory: license`, licence numbers, operator names): look up the number and say whether it belongs to the named operator. Never confirm a claim you could not verify.
- Second-person counts in languages where the verb form carries "you" (Finnish voit/saat, etc.): treat as real.

The script does not judge entity coverage, vague claims, bonus/T&C accuracy or templated section patterns. Mention these as a separate manual/AI check if the user asks for a full audit.
