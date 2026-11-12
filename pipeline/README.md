# Brand site pipeline

Six steps, each run by its own agent with its own short skill. No agent does everything.
The `brand-site-pipeline` skill is the coordinator: give it brand, geo and domain and it runs the steps in order with the gates. `scripts/pipeline_status.py <project>` shows how far a project is and what comes next.
Agents never rely on each other's memory: every step reads files from the project folder and writes files back. The files are the handoff.

| Step | Skill | Reads | Writes | Owns |
|---|---|---|---|---|
| 1 Intake | `brand-intake` | user input, brand's real site | `site.json`, `qc/config.json` | brand facts, site criteria |
| 2 SERP architect | `serp-architect` | `site.json` | `brief/<geo>/<page>/serp.json`, `consensus.md`, `outline.md`, `brief/APPROVAL.md` | page structure |
| 3 Content | `content-writer`, then `humanize-pass` | `site.json`, approved outlines | `content/<geo>/<page>.md` | all wording |
| 4 Design | `site-designer` (`make_images.py`, `build.py`, `design_check.py`) | `site.json`, `content/` | `design/` (theme, templates, css, img), `build/` via `build.py` | layout, visuals |
| 5 SEO | `seo-optimizer` (`seo_build.py`, `seo_check.py`) | `site.json`, `content/` | `seo/head/`, `seo/files/`, `seo/requests.md` | head tags, schema, hreflang, sitemap, robots, redirects, headers |
| 6 QC | `brand-qc` (`qc_route.py`) | `build/`, `qc/config.json` | `qc/qc-*.md`, `qc/route.md`, `qc/requests/<owner>.md` | nothing (reports and routes only) |

## Ownership rule
Only the owner of a thing changes it. When SEO or QC needs a wording change, it writes a request to `seo/requests.md` (or the QC report) and the content agent makes it:

    | page | section | change | reason |
    |---|---|---|---|
    | /bonus | H2 #3 | add "125% bonus" to heading | keyword missing from all H2s |

The content agent may refuse a request that breaks `site.json` voice rules and must say why. Max 2 request rounds per site, then the user decides.

## Gates
- After Step 2: the user approves the outlines (`brief/APPROVAL.md`). Steps 3+ do not start without it.
- After every step: the step runs its own self-check before handing off.
- Step 6 (`qc_route.py`) sends each failed item to its owner in `qc/requests/<owner>.md`, then QC runs again. Max 2 fix rounds, then the user decides.

## Project folder

    <project>/
      site.json            # Step 1 - single source of truth for brand facts and criteria
      qc/config.json       # Step 1 - generated from site.json for brand_qc.py
      brief/<geo>/<page>/  # Step 2 - serp.json, consensus.md, outline.md
      brief/APPROVAL.md    # Step 2 - user approval checkpoint
      content/<geo>/<page>.md
      design/              # Step 4 - theme, templates, css, data, image_plan.json, raw/ (ChatGPT downloads, screenshots), visuals/
      build/  seo/requests.md
      qc/route.md  qc/requests/<owner>.md  qc/round.txt

`<page>` is the slug without slashes, `home` for `/`.
