#!/usr/bin/env python3
"""
Step 3 self-check for one content file.

Usage: python3 content_check.py <project>/content/<geo>/<page>.md [--outline <project>/brief/<geo>/<page>/outline.md]

Content file format (markdown with JSON front-matter):
    <!--meta {"slug": "/bonus", "geo": "fi", "lang": "fi", "type": "other",
              "title": "...", "description": "...", "h1": "...", "target_words": 3000} -->
    Intro paragraph(s)...
    ## H2 heading
    text...
    ### H3 heading
    text...

Checks: word count vs target and site.json criteria, meta lengths and 18+, em dashes,
reader addressed as "you" (per site.json voice), banned AI phrases, forbidden names,
heading levels (no H1 in body, no skips), H2 count vs outline, numbers/claims that do
not appear in a verified site.json fact, repeated sentence openers, paragraph length.
Exit code 1 when any FAIL.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

EM = "—"
SECOND_PERSON = {
    "en": ["you", "your", "you're", "yourself"],
    "fi": ["sinä", "sinun", "sinulle", "sinua", "sinulla", "sinusta", "voit", "saat", "haluat",
           "tarvitset", "pelaat", "löydät", "talletat", "kotiutat", "lunasta", "valitse", "aloita",
           "katso", "tutustu", "lue", "tarkista", "kokeile", "hyödynnä", "nappaa", "rekisteröidy"],
    "nl": ["je", "jij", "jouw", "u", "uw"], "de": ["du", "dich", "dein", "deine"],
    "fr": ["vous", "votre", "vos", "tu"], "it": ["tu", "tuo", "tua", "voi"], "sv": ["du", "dig", "din", "ditt"],
    "pl": ["ty", "twój", "twoja"], "el": ["εσύ", "σας", "σου"], "pt": ["você", "tu", "seu", "sua"],
}
BANNED = [
    "in conclusion", "it's important to note", "it is important to note", "navigating the", "in today's",
    "ever-evolving", "delve", "dive into", "deep dive", "the ultimate guide", "look no further",
    "whether you're a seasoned", "unlock the", "elevate your", "game-changer", "seamless", "a testament to",
    "in the realm of", "embark on", "buckle up", "without further ado", "rest assured", "plethora", "tapestry",
    # Finnish
    "yhteenvetona", "on tärkeää huomata", "kaiken kaikkiaan", "tässä artikkelissa", "sukella",
    "ei ole mikään salaisuus", "lopuksi voidaan todeta",
]


def load(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"\s*<!--meta\s+(\{.*?\})\s*-->", raw, re.S)
    meta = json.loads(m.group(1)) if m else {}
    body = raw[m.end():] if m else raw
    return meta, body


def words(t):
    return re.findall(r"[\w]+(?:[-'][\w]+)*", t, re.UNICODE)


def find_site_json(path):
    d = os.path.dirname(os.path.abspath(path))
    for _ in range(4):
        cand = os.path.join(d, "site.json")
        if os.path.exists(cand):
            return json.load(open(cand, encoding="utf-8"))
        d = os.path.dirname(d)
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content")
    ap.add_argument("--outline")
    a = ap.parse_args()
    meta, body = load(a.content)
    site = find_site_json(a.content)
    lang = meta.get("lang", "en")
    F, R = [], []

    placeholders = re.findall(r"\[VERIFY:[^\]]*\]", body)
    body_np = re.sub(r"\[VERIFY:[^\]]*\]", " ", body)
    # strip markdown for text checks (placeholders excluded)
    text = re.sub(r"^#+\s.*$", " ", body_np, flags=re.M)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    low = (text + " " + " ".join(re.findall(r"^#+\s(.*)$", body, flags=re.M))).lower()
    wc = len(words(text))

    # 1 word count
    crit = site.get("criteria", {}).get("word_count", {})
    target = max(meta.get("target_words", 0), crit.get(meta.get("type", "other"), 0))
    if target and wc < target:
        (F if wc < target * 0.9 else R).append(f"words {wc} < target {target}")

    # 2 meta
    t, d = meta.get("title", ""), meta.get("description", "")
    if not (55 <= len(t) <= 60):
        (R if 50 <= len(t) <= 65 else F).append(f"title {len(t)} chars (55-60)")
    if not (150 <= len(d) <= 160):
        (R if 145 <= len(d) <= 165 else F).append(f"description {len(d)} chars (150-160)")
    if "18+" not in d:
        F.append("description has no 18+")
    if not meta.get("h1"):
        F.append("no h1 in front-matter")

    # 3 em dash
    n_em = (body + t + d + meta.get("h1", "")).count(EM)
    if n_em:
        F.append(f"{n_em} em dash")

    # 4 second person
    if not site.get("voice", {}).get("address_reader_as_you", False):
        hits = Counter()
        for w in SECOND_PERSON.get(lang, SECOND_PERSON["en"]):
            hits[w] = len(re.findall(r"(?<!\w)" + re.escape(w) + r"(?!\w)", low))
        tot = sum(hits.values())
        if tot:
            F.append("reader addressed as 'you': " + ", ".join(f"{k}={v}" for k, v in hits.most_common() if v))

    # 5 banned phrases / forbidden names
    for b in BANNED:
        if re.search(r"(?<!\w)" + re.escape(b) + r"(?!\w)", low):
            F.append(f"AI phrase: '{b}'")
    for nm in ["kap digital"] + [n.lower() for n in site.get("avoid_names", [])]:
        if nm and nm in low:
            F.append(f"forbidden name: '{nm}'")

    # 6 headings
    heads = re.findall(r"^(#{1,6})\s+(.*)$", body, flags=re.M)
    if any(len(h) == 1 for h, _ in heads):
        F.append("H1 inside body (H1 belongs in front-matter only)")
    prev = 1
    for h, txt in heads:
        lvl = len(h)
        if lvl > prev + 1:
            F.append(f"heading skip H{prev}>H{lvl}: {txt[:50]}")
        prev = lvl
    h2 = [txt for h, txt in heads if len(h) == 2]
    if a.outline and os.path.exists(a.outline):
        o = open(a.outline, encoding="utf-8").read()
        o_h2 = re.findall(r"\*\*H2:\s*(.+?)\*\*", o)
        if o_h2 and len(h2) < len(o_h2):
            F.append(f"H2 count {len(h2)} < outline {len(o_h2)}")

    # 7 numbers vs verified facts
    verified = " ".join(f["claim"] for f in site.get("facts", []) if f.get("source"))
    nums = set(re.findall(r"\d[\d\s.,]*\s?(?:%|€|eur|x\b|kr|\$|£)", text, flags=re.I))
    unbacked = []
    for n in nums:
        core = re.sub(r"\s", "", n).lower()
        if core.rstrip("%€$£xkreu") and core.rstrip("%€$£xkreu") not in re.sub(r"\s", "", verified).lower():
            unbacked.append(n.strip())
    if unbacked:
        R.append("numbers not in a verified fact: " + ", ".join(sorted(set(unbacked))[:15]))

    if placeholders:
        R.append(f"{len(placeholders)} open [VERIFY] placeholders (excluded from word count; must be resolved before design)")

    # 9 links
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", body_np)
    internal = [u for _, u in links if u.startswith("/") and not u.rstrip("/").endswith(site.get("play_path", "/play").rstrip("/"))]
    play = [u for _, u in links if u.rstrip("/") == site.get("play_path", "/play").rstrip("/")]
    external = [u for _, u in links if u.startswith("http")]
    qc_cfg = {}
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.content))))
    if os.path.exists(os.path.join(root, "qc", "config.json")):
        qc_cfg = json.load(open(os.path.join(root, "qc", "config.json"), encoding="utf-8"))
    allowed = qc_cfg.get("allowed_external_domains", [])
    for u in external:
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        if allowed and not any(host.endswith(x) for x in allowed):
            F.append(f"external link not allowed: {host}")
    if not internal and meta.get("type") != "mandatory":
        R.append("no internal links")
    if not play and meta.get("type") != "mandatory":
        R.append("no CTA link to the play path")
    anchors = Counter(t.lower() for t, u in links if u in play)
    if anchors and anchors.most_common(1)[0][1] > 2:
        R.append(f"CTA anchor repeated: '{anchors.most_common(1)[0][0]}' x{anchors.most_common(1)[0][1]}")

    # 10 intro must be plain text
    intro = re.split(r"^##\s", body_np, maxsplit=1, flags=re.M)[0]
    if re.search(r"^\s*([-*|>]|\d+\.)\s", intro, flags=re.M):
        R.append("intro contains a list/table/quote (keep the opening plain)")

    # 8 rhythm
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    long_p = [p for p in paras if len(words(p)) > 120]
    if long_p:
        R.append(f"{len(long_p)} paragraphs over 120 words")
    sents = re.split(r"(?<=[.!?])\s+", text)
    openers = Counter(" ".join(words(s)[:2]).lower() for s in sents if len(words(s)) > 3)
    rep = [(o, c) for o, c in openers.most_common(5) if c >= 6]
    if rep:
        R.append("repeated sentence openers: " + ", ".join(f"'{o}' x{c}" for o, c in rep))
    lens = [len(words(s)) for s in sents if words(s)]
    info = ""
    if lens:
        avg = sum(lens) / len(lens)
        var = sum((x - avg) ** 2 for x in lens) / len(lens)
        info = f"sentences: avg {avg:.0f} words, sd {var ** 0.5:.1f}"
        if var ** 0.5 < 5:
            R.append(f"sentence length too uniform ({info})")

    verdict = "FAIL" if F else ("REVIEW" if R else "PASS")
    print(f"{verdict} | {meta.get('slug','?')} [{meta.get('geo','?')}] | {wc} words | {len(h2)} H2" + (f" | {info}" if lens else ""))
    for x in F:
        print("  FAIL:", x)
    for x in R:
        print("  REVIEW:", x)
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
