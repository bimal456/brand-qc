# Brand site pipeline

Six steps, each run by its own agent with its own short skill. No agent does everything.
Agents never rely on each other's memory: every step reads files from the project folder and writes files back. The files are the handoff.

| Step | Skill | Reads | Writes | Owns |
|---|---|---|---|---|
| 1 Intake | `brand-intake` | user input, brand's real site | `site.json`, `qc/config.json` | brand facts, site criteria |
| 2 SERP architect | `serp-architect` | `site.json` | `brief/<geo>/<page>/serp.json`, `consensus.md`, `outline.md`, `brief/APPROVAL.md` | page structure |
| 3 Content | (next) | `site.json`, approved outlines | `content/<geo>/<page>.md` | all wording |
| 4 Design | (next) | `site.json`, `content/` | `design/` templates, `build/` | layout, visuals |
| 5 SEO | (next) | `build/`, `content/` | technical files, `seo/requests.md` | meta, schema, hreflang, links |
| 6 QC | `brand-qc` | `build/`, `qc/config.json` | `qc/report-*.md` | nothing (reports only) |

## Ownership rule
Only the owner of a thing changes it. When SEO or QC needs a wording change, it writes a request to `seo/requests.md` (or the QC report) and the content agent makes it:

    | page | section | change | reason |
    |---|---|---|---|
    | /bonus | H2 #3 | add "125% bonus" to heading | keyword missing from all H2s |

The content agent may refuse a request that breaks `site.json` voice rules and must say why. Max 2 request rounds per site, then the user decides.

## Gates
- After Step 2: the user approves the outlines (`brief/APPROVAL.md`). Steps 3+ do not start without it.
- After every step: the step runs its own self-check before handing off.
- Step 6 sends each failed item back to its owner, re-runs once more, then reports.

## Project folder

    <project>/
      site.json            # Step 1 - single source of truth for brand facts and criteria
      qc/config.json       # Step 1 - generated from site.json for brand_qc.py
      brief/<geo>/<page>/  # Step 2 - serp.json, consensus.md, outline.md
      brief/APPROVAL.md    # Step 2 - user approval checkpoint
      content/<geo>/<page>.md
      design/  build/  seo/requests.md  qc/report-*.md

`<page>` is the slug without slashes, `home` for `/`.
