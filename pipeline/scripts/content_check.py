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
import difflib
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


# sentences about the site's own process read as dev notes on a live page
DEV_NOTES = [
    "before publishing", "before publication", "once verified", "search results show", "according to search results",
    "will be updated once", "to be confirmed", "placeholder",
    "ennen julkaisua", "hakutuloksissa", "kun ne on tarkistettu", "kun ehdot on vahvistettu", "vahvistetaan ennen",
    "vor der veröffentlichung", "avant publication", "voor publicatie", "innan publicering", "prima della pubblicazione",
]


def norm_h(t):
    return re.sub(r"[^\w ]", "", re.sub(r"\s+", " ", t.lower())).strip()


def site_facts(path):
    """facts[] from <project>/site.json (content/<geo>/<page>.md)"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path))))
    sp = os.path.join(root, "site.json")
    return json.load(open(sp, encoding="utf-8")).get("facts", []) if os.path.exists(sp) else []


def page_keyword(path, meta):
    """keyword of this page and geo from <project>/site.json (content/<geo>/<page>.md)"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path))))
    sp = os.path.join(root, "site.json")
    if not os.path.exists(sp):
        return ""
    site = json.load(open(sp, encoding="utf-8"))
    geo, slug = meta.get("geo", ""), meta.get("slug", "")
    for pg in site.get("pages", []):
        pslug = (pg.get("slugs") or {}).get(geo, pg.get("slug", ""))
        if pslug.strip("/") == slug.strip("/"):
            k = (pg.get("keywords") or {}).get(geo, "")
            return k if isinstance(k, str) else (k[0] if k else "")
    return ""


def section_texts(body):
    """[(heading, text until the next heading of any level)]"""
    parts = re.split(r"^(#{2,6})\s+(.*)$", body, flags=re.M)
    return [(parts[i + 1], parts[i + 2]) for i in range(1, len(parts) - 2, 3)]


sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
from brand_qc import (DEFAULT_CONFIG as QC, forbidden_term_hits, SEQ_WORDS, FLUFF_HEADINGS, STOP_FIRST,  # noqa: E402
                      GENERIC_HEADINGS, PROS_CONS_RE, FAQ_HEAD_RE, FAQ_ANSWER_MAX, TABLE_LIMIT, H2_KEYWORD_SHARE)


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

    # 5b forbidden terms (operator, licence, glance ...), licence numbers, regulators, login wording.
    # Lists live in brand_qc.py DEFAULT_CONFIG so Step 3 and Step 6 check the same words.
    scan = " ".join([body, t, d, meta.get("h1", ""), meta.get("nav_label", "")])
    for group, hits in forbidden_term_hits(scan, QC).items():
        F.append(f"forbidden {group} word(s): " + ", ".join(f"'{h}'" for h in hits[:5])
                 + " (remove the sentence or rewrite it without the word)")
    nums = []
    for pat in QC["licence_number_patterns"]:
        for m in re.finditer(pat, scan, re.I if "no|nr" in pat else 0):
            if not any(m.group(0) in n or n in m.group(0) for n in nums):
                nums.append(m.group(0))
    # licence: allowed, but only as the verified licence fact in site.json (has a source, not publish:false)
    lic_facts = " ".join(f.get("claim", "") for f in site_facts(a.content)
                         if f.get("source") and f.get("publish", True) is not False).lower()
    unverified = [n for n in nums if n.lower() not in lic_facts]
    if unverified:
        F.append("licence number(s) not in a verified site.json fact (with source): " + ", ".join(unverified[:4])
                 + " (use the verified number word for word, or remove it)")
    for pat in QC["company_number_patterns"]:
        m = re.search(pat, scan, re.I)
        if m:
            F.append(f"company registration number (operator detail): '{m.group(0)}'")
            break
    regs = [r for r in QC["regulator_names"] if re.search(r"(?<!\w)" + re.escape(r) + r"(?!\w)", scan.lower())]
    bad_regs = [r for r in regs if not re.search(r"(?<!\w)" + re.escape(r) + r"(?!\w)", lic_facts)]
    if bad_regs:
        (R if meta.get("type") == "mandatory" else F).append(
            "regulator named without a verified licence fact in site.json: " + ", ".join(bad_regs[:5])
            + " (fine as a help resource on the responsible-gambling page)")
    for ph in QC["login_bad_phrases"]:
        if ph in scan.lower():
            F.append(f"'{ph}' used; write the normal login word ({', '.join(QC['login_words'].get(lang, ['login'])[:2])})")
    if any(w in meta.get("slug", "").lower() for w in QC["login_slug_words"]):
        ok = QC["login_words"].get(lang, []) + QC["login_words"]["en"]
        for label, txt in (("h1", meta.get("h1", "")), ("title", t)):
            if not any(w in txt.lower() for w in ok):
                F.append(f"login page {label} has no login word ({', '.join(QC['login_words'].get(lang, ['login'])[:2])}): '{txt[:60]}'")

    for dn in DEV_NOTES:
        if dn in low:
            F.append(f"dev-note sentence: '{dn}' (rewrite as a normal sentence or remove)")

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
        # every H2/H3 must come from the approved outline (no invented headings)
        o_heads = [norm_h(x) for x in re.findall(r"\*\*H2:\s*(.+?)\*\*", o) + re.findall(r"H3:\s*(.+?)(?:\s+-\s|\*|$)", o, flags=re.M)]
        if o_heads:
            extra = [txt for h, txt in heads if len(h) in (2, 3)
                     and not any(difflib.SequenceMatcher(None, norm_h(txt), oh).ratio() >= 0.75 for oh in o_heads)]
            if extra:
                F.append(f"{len(extra)} heading(s) not in the approved outline: " + "; ".join(f"'{x[:45]}'" for x in extra[:4]))
        # section formats from the outline: "format: steps | list | table | paragraphs"
        need = {}
        for line in o.splitlines():
            m = re.search(r"(?:\*\*H2:\s*(.+?)\*\*|H3:\s*(.+?)(?:\s+-\s|$)).*?format:\s*(steps|list|table|paragraphs)", line, re.I)
            if m:
                need[norm_h(m.group(1) or m.group(2))] = m.group(3).lower()
        secs = section_texts(body_np)
        for title, fmt in need.items():
            st = next((txt for hd, txt in secs if difflib.SequenceMatcher(None, norm_h(hd), title).ratio() >= 0.75), None)
            if st is None or fmt == "paragraphs":
                continue
            ok = {"steps": r"^\s*\d+[.)]\s", "list": r"^\s*(?:[-*]|\d+[.)])\s", "table": r"^\s*\|"}[fmt]
            if not re.search(ok, st, flags=re.M):
                F.append(f"section '{title[:40]}' must be {fmt} (outline) but has none")

    # 6b structure: steps written as paragraphs, too few lists/tables, slogan headings
    seq = sorted(set(SEQ_WORDS.get(lang, []) + SEQ_WORDS["en"]))
    for para in re.split(r"\n\s*\n", re.sub(r"^#{1,6}\s.*$", "\n", body_np, flags=re.M)):
        if not para.strip() or para.lstrip().startswith(("|", "-", "*")) or re.match(r"\s*\d+[.)]\s", para):
            continue
        pl = para.lower()
        hits = sum(len(re.findall(r"(?<!\w)" + re.escape(w) + r"(?!\w)", pl)) for w in seq)
        if hits >= 3:
            F.append(f"steps written as a paragraph ({hits} sequence words), make it a numbered list: '{para.strip()[:60]}...'")
    blocks = len(re.findall(r"(?:^\s*(?:[-*]|\d+[.)])\s.*\n?)+", body_np, flags=re.M)) + len(re.findall(r"(?:^\s*\|.*\n?)+", body_np, flags=re.M))
    per = 1000 if meta.get("type") == "mandatory" else 600
    if wc > per and blocks < wc // per:
        F.append(f"only {blocks} list/table block(s) for {wc} words; need at least {wc // per} (one per {per} words): steps, criteria and comparisons go in lists or tables")
    sib = {}
    parent = ""
    for h, txt in heads:
        if len(h) == 2:
            parent = txt
        if len(h) in (2, 3):
            first = re.sub(r"[^\w]", "", txt.split()[0].lower()) if txt.split() else ""
            if first and len(first) > 2 and first not in STOP_FIRST:
                sib.setdefault((len(h), parent if len(h) == 3 else "", first), []).append(txt)
    for (lvl, _, first), hs in sib.items():
        if len(hs) >= 3:
            F.append(f"templated slogan headings ({len(hs)} H{lvl} start with '{first}'): " + "; ".join(f"'{x[:30]}'" for x in hs[:4]))
    for h, txt in heads:
        if any(re.search(p_, txt, re.I) for p_ in FLUFF_HEADINGS):
            F.append(f"brand-slogan heading, not a search topic: '{txt[:60]}'")
        if any(re.search(g, txt.strip(), re.I) for g in GENERIC_HEADINGS):
            F.append(f"generic heading, not a search topic: '{txt[:60]}' (use a heading people search for)")
        if re.search(PROS_CONS_RE, txt, re.I):
            F.append(f"pros/cons section not wanted: '{txt[:60]}'")
    if re.search(r"^\s*(?:\*\*|__)?\s*" + PROS_CONS_RE + r"\s*:?\s*(?:\*\*|__)?\s*:?\s*$", body_np, re.I | re.M):
        F.append("pros/cons block (a 'Pros' / 'Cons' label line); write the trade-off into normal sections instead")

    # 6c tables: lists first, tables only for real numeric comparisons
    n_tab = len(re.findall(r"(?:^\s*\|.*\n?)+", body_np, flags=re.M))
    lim = TABLE_LIMIT.get(meta.get("type", ""), TABLE_LIMIT["default"])
    if n_tab > lim:
        F.append(f"{n_tab} tables (max {lim} on a {meta.get('type', 'default')} page); turn the rest into lists or prose")

    # 6d FAQ answers stay short
    if re.search(r"^##\s.*(?:" + FAQ_HEAD_RE + ")", body_np, re.I | re.M):
        # questions are the H3s after the FAQ H2 (until the next H2), or bold question lines inside it
        parts = re.split(r"^##\s", body_np, flags=re.M)
        faq_body = next((x for x in parts if re.search(FAQ_HEAD_RE, x.split("\n", 1)[0], re.I)), "")
        qa = re.split(r"^(?:###\s+(.+)|\*\*(.+\?)\*\*)\s*$", faq_body, flags=re.M)
        long_ans = []
        for i in range(1, len(qa) - 2, 3):
            q = qa[i] or qa[i + 1]
            n = len(re.findall(r"\w+", qa[i + 2] or ""))
            if n > FAQ_ANSWER_MAX:
                long_ans.append(f"'{q[:35]}' {n}w")
        if long_ans:
            F.append(f"{len(long_ans)} FAQ answer(s) over {FAQ_ANSWER_MAX} words (answer first, 30-50 words): " + "; ".join(long_ans[:3]))

    # 6e SEO subheadings: H2s carry the page keyword, a keyword stem or the brand
    kw = meta.get("keyword") or page_keyword(a.content, meta)
    if kw:
        stems = {w[:5] for w in re.findall(r"\w+", kw.lower()) if len(w) > 2}
        h2s = [txt for h, txt in heads if len(h) == 2 and not re.search(FAQ_HEAD_RE, txt, re.I)]
        with_kw = [t for t in h2s if any(st in t.lower() for st in stems)]
        if h2s and len(with_kw) / len(h2s) < H2_KEYWORD_SHARE:
            F.append(f"only {len(with_kw)}/{len(h2s)} H2s carry the keyword '{kw}' or a variant (need {int(H2_KEYWORD_SHARE * 100)}%+); "
                     "make subheadings the searched phrases (PAA, related searches, competitor headings)")

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
