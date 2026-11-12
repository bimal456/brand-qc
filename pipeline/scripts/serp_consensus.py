#!/usr/bin/env python3
"""
SERP consensus for one keyword.

Input:  brief/<geo>/<page>/serp.json  (written by the SERP agent, schema below)
Output: brief/<geo>/<page>/consensus.md  (numbers only - the outline is written by the agent)

serp.json schema:
{
  "keyword": "munkki kasino bonus", "geo": "fi", "brand_tokens": ["munkki"],
  "checked": "2026-11-12",
  "results": [
    {"rank": 1, "url": "...", "kind": "affiliate",   # official | own-site | affiliate | jump-link | review-platform | forum | other
     "title": "...", "description": "...", "h1": ["..."], "h2": ["..."], "h3": ["..."], "words": 1456,
     "exclude": false, "exclude_reason": ""}          # exclude=true when the URL resolved to a different/generic page
  ],
  "serp_call": {"endpoint": "...", "datetime": "..."}, # which SERP call the ranking came from
  "paa": ["question 1"],
  "related": ["related search 1"]                     # fallback when there is no people-also-ask
}

Usage: python3 serp_consensus.py brief/fi/bonus/serp.json
"""
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

# Results that are not competitors for the content shape (excluded from medians)
NON_COMPETITOR = {"official", "own-site", "jump-link", "review-platform", "forum"}
THIN_WORDS = 200  # pages below this are offer cards / failed fetches: listed, not used for medians or topics

STOP = set("""
a an and the of to in on for with at by from is are be or as it its this that how what why when which who your you
ja tai on ei se ne kun jos kuin mitä miten mikä missä onko voiko kanssa sekä myös
en het de een van voor met op in is zijn hoe wat waarom bij
der die das und mit für von im ist wie was zu den dem ein eine
le la les des du un une et pour avec sur est en au aux comment quoi
il lo gli le di da con per su che come cosa un una
och att det som för med på av är hur vad en ett
i w z na do jak co czy dla
""".split())


def norm_tokens(text, brand_tokens):
    text = text.lower()
    text = re.sub(r"[^\w\s%€$-]", " ", text, flags=re.UNICODE)
    toks = [t.strip("-") for t in text.split()]
    out = []
    for t in toks:
        if not t or t in STOP or len(t) <= 2 and not t.isdigit():
            continue
        if any(t.startswith(b) for b in brand_tokens):
            continue
        out.append(t)
    return out


def main():
    path = sys.argv[1]
    d = json.load(open(path, encoding="utf-8"))
    brand = [b.lower() for b in d.get("brand_tokens", [])]
    res = d["results"]
    kw_tokens = set(norm_tokens(d["keyword"], []))
    comp = [r for r in res if r.get("kind") not in NON_COMPETITOR and not r.get("exclude")
            and (r.get("words") or 0) >= THIN_WORDS]
    words = [r["words"] for r in comp if r.get("words")]
    top5 = [r["words"] for r in sorted(comp, key=lambda r: r["rank"])[:5] if r.get("words")]

    L = [f"# SERP consensus: \"{d['keyword']}\" ({d['geo'].upper()})", ""]
    L.append(f"Checked: {d.get('checked', '?')} | results: {len(res)} | competitor pages used: {len(comp)}")
    kinds = Counter(r.get("kind", "?") for r in res)
    L.append("Result mix: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    sc = d.get("serp_call") or {}
    if sc:
        L.append(f"SERP call: {sc.get('endpoint','')} at {sc.get('datetime','')}")
    dropped = [r for r in res if r not in comp]
    if dropped:
        L.append("Not used for medians/topics: " + "; ".join(
            f"#{r['rank']} {r.get('kind','')}" + (f" ({r.get('exclude_reason')})" if r.get('exclude') else
            (f" ({r.get('words',0)} words)" if r.get('kind') not in NON_COMPETITOR else "")) for r in dropped))
    if len(comp) < 5:
        L.append(f"**Warning: only {len(comp)} usable competitor pages. Treat medians as weak; consider a close keyword variant or depth 20.**")
    L.append("")

    # Word count
    L.append("## Length")
    if words:
        L.append(f"- Median words (all competitors): **{int(statistics.median(words))}**")
        if top5:
            L.append(f"- Median words (top 5 competitors): **{int(statistics.median(top5))}**")
        L.append(f"- Range: {min(words)} - {max(words)}")
    else:
        L.append("- No word counts available")
    L.append("")

    # Titles / H1
    L.append("## Titles and H1s (rank order)")
    L.append("| # | kind | words | H2s | title | H1 |")
    L.append("|---|---|---|---|---|---|")
    for r in sorted(res, key=lambda r: r["rank"]):
        h1 = " / ".join(r.get("h1", []))[:70]
        L.append(f"| {r['rank']} | {r.get('kind','')}{' (excluded)' if r.get('exclude') else ''} | {r.get('words','')} | {len(r.get('h2', []))} | {r.get('title','')[:70]} | {h1} |")
    tl = [len(r.get("title", "")) for r in comp if r.get("title")]
    if tl:
        L.append(f"\nTitle length median: {int(statistics.median(tl))} chars")
    h2n = [len(r.get("h2", [])) for r in comp if r.get("h2")]
    if h2n:
        L.append(f"H2 count median: {int(statistics.median(h2n))} (range {min(h2n)}-{max(h2n)})")
    L.append("")

    # Topic consensus from headings (document frequency across competitors)
    df = Counter()
    examples = defaultdict(list)
    bigram_df = Counter()
    for r in comp:
        heads = r.get("h2", []) + r.get("h3", [])
        seen, seen_bi = set(), set()
        for h in heads:
            toks = [t for t in norm_tokens(h, brand) if t not in kw_tokens]
            for t in toks:
                if t not in seen:
                    seen.add(t)
                    if len(examples[t]) < 3:
                        examples[t].append(h.strip()[:60])
            for a, b in zip(toks, toks[1:]):
                seen_bi.add(f"{a} {b}")
        df.update(seen)
        bigram_df.update(seen_bi)
    n = max(len(comp), 1)
    bis = [(b, c) for b, c in bigram_df.most_common(25) if c >= 2]
    L.append(f"## Repeated phrases in headings (of {n} competitors)")
    L.append(", ".join(f"{b} ({c})" for b, c in bis) if bis else "none")
    L.append("")
    L.append(f"## Heading terms by how many competitors use them (of {n})")
    L.append("Keyword and brand words are removed. Read phrases above first; single words are a rough signal.")
    L.append("Topics used by half or more of the competitors are the consensus sections. Topics used by 1-2 are gap or differentiation candidates.")
    L.append("")
    L.append("| competitors | term | example headings |")
    L.append("|---|---|---|")
    for t, c in df.most_common(40):
        if c < 2:
            break
        L.append(f"| {c} | {t} | {' ; '.join(examples[t])} |")
    L.append("")

    # Rare topics (gap ideas)
    rare = [t for t, c in df.items() if c == 1]
    if rare:
        L.append("## Single-competitor terms (possible information gain)")
        L.append(", ".join(sorted(rare)[:60]))
        L.append("")

    if d.get("paa"):
        L.append("## People also ask")
        for q in d["paa"]:
            L.append(f"- {q}")
        L.append("")
    if d.get("related"):
        L.append("## Related searches")
        for q in d["related"]:
            L.append(f"- {q}")
        L.append("")

    # Full heading lists of the top 3 competitors for structure reference
    L.append("## Heading lists of the top 3 competitors")
    for r in sorted(comp, key=lambda r: r["rank"])[:3]:
        L.append(f"\n**#{r['rank']} {r['url']}** ({r.get('words','?')} words)")
        for h in r.get("h2", []):
            L.append(f"- H2: {h}")
        for h in r.get("h3", [])[:15]:
            L.append(f"  - H3: {h}")

    out = os.path.join(os.path.dirname(os.path.abspath(path)), "consensus.md")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
