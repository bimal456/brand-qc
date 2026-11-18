#!/usr/bin/env python3
"""
Brand QC
--------
Runs the deterministic QC checks on a built static casino brand site folder
and writes a PASS / REVIEW / FAIL report (Markdown + JSON).

Usage:
    python3 brand_qc.py /path/to/site-folder
    python3 brand_qc.py https://brand-site.casino --config configs/fi.json
    python3 brand_qc.py /path/to/site-folder --config qc_config.json --out reports/

The folder should contain the built HTML pages (clean URLs: /bonus -> bonus.html
or bonus/index.html), plus sitemap.xml and robots.txt.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment

# --------------------------------------------------------------------------
# Default config (override any key with --config file.json)
# --------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "word_count": {"home": 5000, "mandatory": 1000, "other": 3000},
    "meta_title": [55, 60],
    "meta_description": [150, 160],
    "length_tolerance": 5,          # outside range by <= this many chars = REVIEW, more = FAIL
    "play_paths": ["/play"],          # affiliate redirect path(s); add "/pelaa" etc. per site
    # Register / sign-up links always go to the play path. Login words go to the play path only on
    # CTA buttons (class btn/button/cta, role=button, or inside a <button>); a plain menu, side-menu
    # or footer text link "Login" may open the site's own login page.
    "cta_words": ["register", "sign up", "registreren", "registrieren", "inscription", "registrati",
                  "rekisteröidy", "zarejestruj", "εγγραφή", "registrera", "inscríbete", "registe"],
    "login_cta_words": ["login", "log in", "sign in", "inloggen", "anmelden", "connexion", "accedi",
                        "logga in", "kirjaudu", "zaloguj", "σύνδεση", "entrar", "iniciar sesión"],
    "button_class_re": r"(^|[\s_-])(btn|button|cta)([\s_-]|$)",
    "allowed_external_domains": [],  # geo responsible-gambling resources, e.g. ["joueurs-info-service.fr"]
    "forbidden_names": ["KAP Digital", "KAP "],
    "forbidden_voice": ["we are not the operator", "information only", "informational site only",
                         "official site", "not affiliated with", "this site is not"],
    # Words that must never appear on a brand site (FAIL). Matched case-insensitively from the start
    # of a word, so a stem also catches its inflections (licen -> license, licence, licenza, licentie).
    "forbidden_terms": {
        "operator": ["operator", "operated by", "operatore", "operatori", "gestito da", "operaattori",
                     "ylläpitäjä", "exploitant", "beheerd door", "betreiber", "betrieben von",
                     "opérateur", "exploité par", "operatör", "drivs av", "operador", "operado por"],
        "licence": ["licen", "lisens", "lizenz", "vergunning", "concessione"],
        "independent": ["independent", "onafhankelijk", "unabhängig", "indépendant", "indipendent", "riippumat",
                        "oberoende", "niezależn", "independente", "ανεξάρτητ"],
        "glance": ["glance", "colpo d'occhio", "silmäyksellä", "oogopslag", "auf einen blick",
                   "coup d'œil", "coup d'oeil", "ögonkast", "rzut oka"],
    },
    # Licence / company registration numbers (FAIL)
    "licence_number_patterns": [
        r"\bMGA/[A-Z0-9]+/\d+/\d{4}\b", r"\bB2C/\d+/\d{4}\b", r"\bOGL/\d{4}-\d+",
        r"\b\d{3,5}/JAZ\b", r"\bGLH-[A-Z0-9-]{4,}", r"\bALSI-\d{5,}", r"\bC\d{5}\b",
        r"\b(?:no|nr|n|number|numero|nummer|numéro|numer)\.?\s*:?\s*[A-Z]{1,5}[/-]\d[\dA-Z/-]{3,}",
    ],
    # Regulator names: fine on a responsible-gambling page as a help resource, otherwise a licence claim (REVIEW)
    "regulator_names": ["malta gaming authority", "mga", "curaçao", "curacao", "gaming curacao",
                        "gaming control board", "kahnawake", "anjouan", "agenzia delle dogane", "adm",
                        "gambling commission", "ukgc", "kansspelautoriteit", "ksa", "spelinspektionen",
                        "gemeinsame glücksspielbehörde", "ggl", "autorité nationale des jeux", "anj",
                        "poliisihallitus", "lotteriinspektionen"],
    # Login page: H1 and title use the geo's normal login word; these phrases are wrong (FAIL)
    "login_words": {
        "en": ["login", "log in", "sign in"], "it": ["accedi", "accesso", "login"],
        "fi": ["kirjaudu", "kirjautuminen", "kirjautumi"], "nl": ["inloggen", "login"],
        "de": ["anmelden", "anmeldung", "login"], "fr": ["connexion", "se connecter"],
        "sv": ["logga in", "inloggning"], "pl": ["zaloguj", "logowanie"], "pt": ["login", "entrar"],
        "el": ["σύνδεση"], "es": ["iniciar sesión", "acceder", "login"],
    },
    "login_slug_words": ["login", "log-in", "sign-in", "kirjau", "accedi", "accesso", "inloggen",
                         "anmelden", "connexion", "logga-in", "inloggning", "zaloguj", "logowanie", "entrar"],
    "login_bad_phrases": ["access account", "access your account", "account access", "access the account",
                          "accedi al conto", "accesso al conto", "accedi all'account", "accesso all'account",
                          "accesso account", "pääsy tilille", "toegang tot account", "kontozugang",
                          "accès au compte", "åtkomst till konto"],
    "banned_phrases": [
        "in conclusion", "it's important to note", "it is important to note",
        "navigating the", "in today's digital", "in the ever-evolving", "ever-changing landscape",
        "delve into", "dive into", "deep dive", "the ultimate guide", "look no further",
        "whether you're a seasoned", "unlock the", "elevate your", "game-changer",
        "seamless experience", "a testament to", "in the realm of", "embark on",
        "buckle up", "without further ado", "rest assured", "plethora", "tapestry",
    ],
    "placeholders": ["lorem ipsum", "todo", "tbd", "{{", "}}", "[brand]", "xxx",
                      "placeholder", "your-domain", "example.com"],
    # second-person words per <html lang>. Matching is whole-word, case-insensitive.
    "second_person": {
        "en": ["you", "your", "you're", "yours", "yourself"],
        "nl": ["je", "jij", "jouw", "u", "uw"],
        "de": ["du", "dich", "dein", "deine", "ihr"],
        "fr": ["vous", "votre", "vos", "tu", "ton", "ta"],
        "it": ["tu", "tuo", "tua", "voi", "vostro"],
        "sv": ["du", "dig", "din", "ditt"],
        "fi": ["sinä", "sinun", "sinulle", "sinua", "sinulla", "sinusta", "teidän", "teille",
               "voit", "saat", "haluat", "tarvitset", "pelaat", "löydät", "kannattaa sinun"],
        "pl": ["ty", "twój", "twoja", "wy"],
        "el": ["εσύ", "σας", "σου"],
        "pt": ["você", "tu", "seu", "sua"],
    },
    "mandatory_pages": {
        "responsible gambling": ["responsible", "verantwoord", "verantwortung", "jeu-responsable",
                                  "gioco-responsabile", "ansvarsfullt", "vastuullinen", "odpowiedzialn", "jeu-responsable", "spelansvar",
                                  "responsavel", "ypefthyno", "safer-gambling", "rg"],
        "terms": ["terms", "voorwaarden", "agb", "conditions", "termini", "villkor", "ehdot",
                   "regulamin", "termos", "oroi", "tos", "kayttoehdot", "ehdot", "cgu",
                   "algemene-voorwaarden", "allmanna-villkor", "nutzungsbedingungen"],
        "privacy": ["privacy", "datenschutz", "confidentialite", "integritet", "tietosuoja",
                     "prywatn", "privacidade", "aporrito", "tietosuoja", "integritetspolicy", "privacybeleid"],
        "about": ["about", "over-ons", "ueber-uns", "uber-uns", "a-propos", "chi-siamo", "om-oss",
                   "meista", "tietoa", "o-nas", "sobre", "sxetika", "qui-sommes-nous"],
        "contact": ["contact", "kontakt", "contatti", "yhteys", "yhteytta", "contato", "epikoinonia"],
    },
}

SEV_ORDER = {"FAIL": 0, "REVIEW": 1, "PASS": 2}
EM_DASH = "—"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def deep_merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def file_to_url_path(rel):
    """bonus.html -> /bonus, bonus/index.html -> /bonus, index.html -> /"""
    rel = rel.replace(os.sep, "/")
    if rel.endswith("index.html"):
        p = "/" + rel[: -len("index.html")].rstrip("/")
    else:
        p = "/" + rel[: -len(".html")]
    return p if p != "" else "/"


def visible_text(soup):
    s = BeautifulSoup(str(soup), "lxml")
    for t in s(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    for c in s.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    return re.sub(r"\s+", " ", s.get_text(" ")).strip()


def main_text(soup):
    """Body text without header/nav/footer, used for word counts."""
    s = BeautifulSoup(str(soup), "lxml")
    for t in s(["script", "style", "noscript", "template", "svg", "header", "nav", "footer"]):
        t.decompose()
    body = s.body or s
    return re.sub(r"\s+", " ", body.get_text(" ")).strip()


def word_count(text):
    return len(re.findall(r"\w+(?:[-']\w+)*", text, flags=re.UNICODE))


def line_of(raw, needle):
    idx = raw.lower().find(needle.lower())
    return raw.count("\n", 0, idx) + 1 if idx >= 0 else None


# sequence words: 3+ in one paragraph means the paragraph is really a list of steps
SEQ_WORDS = {
    "en": ["first", "firstly", "then", "next", "after that", "afterwards", "finally", "step", "second", "third"],
    "nl": ["eerst", "daarna", "vervolgens", "tot slot", "ten slotte", "stap", "als eerste", "dan"],
    "it": ["prima", "poi", "quindi", "successivamente", "infine", "passo", "per prima cosa", "dopodiché"],
    "fi": ["ensin", "sitten", "seuraavaksi", "lopuksi", "vaihe", "tämän jälkeen", "aluksi"],
    "de": ["zuerst", "dann", "danach", "anschließend", "schließlich", "schritt", "zunächst"],
    "fr": ["d'abord", "ensuite", "puis", "enfin", "étape", "premièrement", "après cela"],
    "sv": ["först", "sedan", "därefter", "slutligen", "steg", "till sist"],
    "pl": ["najpierw", "następnie", "potem", "na koniec", "krok"],
    "pt": ["primeiro", "depois", "em seguida", "por fim", "passo"],
    "el": ["πρώτα", "μετά", "στη συνέχεια", "τέλος", "βήμα"],
}
# headings that sell a slogan instead of answering a search ("What Fast Means at X", "Our approach")
FLUFF_HEADINGS = [r"^what .{1,30} means", r"\bour (approach|philosophy|promise|mission|story|dna)\b", r"^the .{1,20} way$",
                  r"^wat .{1,30} betekent", r"^cosa significa", r"^mitä .{1,30} tarkoittaa", r"^was .{1,30} bedeutet",
                  r"^ce que .{1,30} signifie", r"^vad .{1,30} betyder", r"\bonze (aanpak|filosofie|belofte)\b",
                  r"\bla nostra (filosofia|promessa)\b", r"\bunsere (philosophie|mission)\b"]
# generic headings that rank for nothing (exact heading, any language)
GENERIC_HEADINGS = [r"^(overview|introduction|intro|conclusion|summary|final thoughts|final words|our verdict|verdict|"
                    r"key takeaways|takeaways|in brief|in short|wrap-up|bottom line|the bottom line|"
                    r"yhteenveto|johdanto|lopuksi|conclusione|riepilogo|panoramica|in sintesi|introduzione|"
                    r"conclusie|samenvatting|overzicht|inleiding|tot slot|fazit|zusammenfassung|überblick|einleitung|"
                    r"résumé|aperçu|en bref|sammanfattning|slutsats|översikt|podsumowanie|wnioski|resumo|conclusão|"
                    r"συμπέρασμα|σύνοψη)\W*$"]
# pros and cons sections are not wanted on brand sites (heading or bold label, any language)
PROS_CONS_RE = (r"(?<!\w)(pros|cons|pros and cons|advantages and disadvantages|plussat|miinukset|hyvät ja huonot puolet|"
                r"voordelen|nadelen|voor- en nadelen|pro e contro|vantaggi|svantaggi|vorteile|nachteile|vor- und nachteile|"
                r"avantages|inconvénients|fördelar|nackdelar|zalety|wady|prós|contras|πλεονεκτήματα|μειονεκτήματα)(?!\w)")
FAQ_HEAD_RE = (r"faq|usein kysyt|frequently asked|vanliga fr[aå]gor|veelgestelde|h[aä]ufig gestellte|questions fr[eé]quentes|"
               r"domande frequenti|preguntas frecuentes|cz[eę]sto zadawane|ofte stilte|συχν[εέ]ς ερωτ")
FAQ_ANSWER_MAX = 60      # words per FAQ answer (FAIL above)
TABLE_LIMIT = {"home": 3, "mandatory": 1, "default": 2}   # tables per page (FAIL above)
H2_KEYWORD_SHARE = 0.4   # at least this share of H2s (FAQ excluded) carry the page keyword, brand or a keyword stem


STOP_FIRST = {"how", "what", "why", "which", "when", "the", "hoe", "wat", "come", "cosa", "miten", "mitä", "wie", "was",
              "comment", "quel", "quels", "quelle", "hur", "vad", "jak", "como"}


def is_button(a, cfg):
    """A CTA button: the link or its parent has a btn/button/cta class, role=button, or sits in a <button>."""
    pat = re.compile(cfg.get("button_class_re", r"(^|[\s_-])(btn|button|cta)([\s_-]|$)"), re.I)
    for el in (a, a.parent):
        if el is None or not hasattr(el, "get"):
            continue
        if el.name == "button" or (el.get("role") or "") == "button" or pat.search(" ".join(el.get("class", []))):
            return True
    return bool(a.find("button"))


def forbidden_term_hits(text, cfg):
    """{group: [matched words]} for cfg['forbidden_terms'], matched from the start of a word."""
    low, out = text.lower(), {}
    for group, terms in cfg.get("forbidden_terms", {}).items():
        hits = []
        for t in terms:
            for m in re.finditer(r"(?<![\w])" + re.escape(t.lower()) + r"[\w']*", low):
                hits.append(text[m.start():m.end()])
        if hits:
            out[group] = sorted(set(hits), key=hits.index)
    return out


def snippet(text, needle, width=60):
    i = text.lower().find(needle.lower())
    if i < 0:
        return ""
    a, b = max(0, i - width // 2), min(len(text), i + len(needle) + width // 2)
    return ("..." if a else "") + text[a:b].strip() + ("..." if b < len(text) else "")


class Report:
    def __init__(self):
        self.items = []  # dicts: check, severity, page, detail

    def add(self, check, severity, page, detail):
        self.items.append({"check": check, "severity": severity, "page": page, "detail": detail})


# --------------------------------------------------------------------------
# Page-level checks
# --------------------------------------------------------------------------
def check_page(path_url, raw, soup, cfg, rep, site_files, page_type, internal_hosts):
    tol = cfg["length_tolerance"]
    vis = visible_text(soup)
    vis_low = vis.lower()
    lang = ((soup.html.get("lang") if soup.html else "") or "en").split("-")[0].lower()

    # 1. Single H1
    h1s = soup.find_all("h1")
    if len(h1s) != 1:
        rep.add("Single H1", "FAIL", path_url, f"found {len(h1s)} H1 tags")

    # 2. Heading hierarchy (no level skips going down)
    prev = 0
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        lvl = int(h.name[1])
        if prev and lvl > prev + 1:
            rep.add("Heading hierarchy", "FAIL", path_url,
                    f"H{prev} -> H{lvl} skip at \"{h.get_text(strip=True)[:60]}\"")
        prev = lvl

    # 3. Meta title / description
    title = (soup.title.get_text(strip=True) if soup.title else "")
    lo, hi = cfg["meta_title"]
    if not title:
        rep.add("Meta title", "FAIL", path_url, "missing <title>")
    elif not (lo <= len(title) <= hi):
        sev = "REVIEW" if (lo - tol) <= len(title) <= (hi + tol) else "FAIL"
        rep.add("Meta title", sev, path_url, f"{len(title)} chars (target {lo}-{hi}): \"{title}\"")

    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    desc = md.get("content", "").strip() if md else ""
    lo, hi = cfg["meta_description"]
    if not desc:
        rep.add("Meta description", "FAIL", path_url, "missing meta description")
    else:
        if not (lo <= len(desc) <= hi):
            sev = "REVIEW" if (lo - tol) <= len(desc) <= (hi + tol) else "FAIL"
            rep.add("Meta description", sev, path_url, f"{len(desc)} chars (target {lo}-{hi})")
        if "18+" not in desc:
            rep.add("Meta description 18+", "FAIL", path_url, "\"18+\" missing in meta description")

    # 4. Canonical / OG / Twitter consistency
    can = soup.find("link", rel=lambda r: r and "canonical" in (r.split() if isinstance(r, str) else r))
    can_href = can.get("href", "").strip() if can else ""
    if not can_href:
        rep.add("Canonical", "FAIL", path_url, "missing canonical")
    else:
        cp = urlparse(can_href).path.rstrip("/") or "/"
        if cp != path_url:
            rep.add("Canonical", "REVIEW", path_url, f"canonical path {cp} != page path {path_url}")
        if can_href.endswith("/") and cp != "/":
            rep.add("Clean URLs", "FAIL", path_url, f"canonical has trailing slash: {can_href}")
        if "index.html" in can_href:
            rep.add("Clean URLs", "FAIL", path_url, f"canonical contains index.html: {can_href}")

    def meta_prop(name):
        t = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        return t.get("content", "").strip() if t else ""

    for tag in ["og:title", "og:description", "og:url", "twitter:card", "twitter:title"]:
        if not meta_prop(tag):
            rep.add("OG / Twitter tags", "FAIL", path_url, f"missing {tag}")
    if can_href and meta_prop("og:url") and meta_prop("og:url").rstrip("/") != can_href.rstrip("/"):
        rep.add("OG / Twitter tags", "FAIL", path_url, "og:url does not match canonical")

    # 5. hreflang
    alts = soup.find_all("link", rel=lambda r: r and "alternate" in (r.split() if isinstance(r, str) else r), hreflang=True)
    if not alts:
        rep.add("Hreflang", "FAIL", path_url, "no hreflang tags")
    else:
        langs = [a.get("hreflang", "").lower() for a in alts]
        if "x-default" not in langs:
            rep.add("Hreflang", "REVIEW", path_url, "no x-default")
        if can_href and not any(a.get("href", "").rstrip("/") == can_href.rstrip("/") for a in alts):
            rep.add("Hreflang", "FAIL", path_url, "no self-referencing hreflang")
        if len(langs) != len(set(langs)):
            rep.add("Hreflang", "FAIL", path_url, "duplicate hreflang values")

    # 6. Robots meta (info only - many brand sites are intentionally noindex)
    rb = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    if rb and "noindex" in rb.get("content", "").lower():
        rep.add("Robots meta", "REVIEW", path_url, "page is noindex (fine if intended)")

    # 7. Links
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        text = a.get_text(" ", strip=True)
        rel = [r.lower() for r in (a.get("rel") or [])]
        if not href:
            rep.add("Links", "FAIL", path_url, f"<a> without href: \"{text[:40]}\"")
            continue
        if "#" in href:
            rep.add("No # in href", "FAIL", path_url, f"href=\"{href}\" (\"{text[:40]}\")")
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        u = urlparse(href)
        is_external = bool(u.netloc) and u.netloc.lower().replace("www.", "") not in internal_hosts
        if is_external:
            if "nofollow" not in rel:
                rep.add("Nofollow external", "FAIL", path_url, f"external link not nofollow: {href}")
            dom = u.netloc.lower().replace("www.", "")
            if cfg["allowed_external_domains"] and not any(dom.endswith(d) for d in cfg["allowed_external_domains"]):
                rep.add("External link allowlist", "FAIL", path_url, f"external domain not in RG allowlist: {dom}")
            elif not cfg["allowed_external_domains"]:
                rep.add("External link allowlist", "REVIEW", path_url, f"external link to {dom} (confirm it is a geo RG resource)")
        else:
            p = u.path or "/"
            if p.endswith("index.html") or p.endswith(".html"):
                rep.add("Clean URLs", "FAIL", path_url, f"internal link uses .html: {href}")
            elif p != "/" and p.endswith("/"):
                rep.add("Clean URLs", "REVIEW", path_url, f"internal link has trailing slash: {href}")
            norm = p.rstrip("/") or "/"
            if norm not in cfg["play_paths"] and norm not in site_files and not re.search(r"\.(webp|png|jpg|jpeg|svg|xml|txt|pdf|css|js|ico)$", norm):
                rep.add("Broken internal link", "FAIL", path_url, f"{href} has no matching page")
            if norm in cfg["play_paths"] and "nofollow" not in rel:
                rep.add("Nofollow CTA", "FAIL", path_url, f"play CTA not nofollow (\"{text[:40]}\")")
        # CTA destinations: register links always, login only when it is a button
        tl = text.lower()
        dest = urlparse(href).path.rstrip("/") or "/"
        is_reg = any(re.search(r"(?<!\w)" + re.escape(w), tl) for w in cfg["cta_words"])
        is_login = any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", tl) for w in cfg["login_cta_words"])
        if (is_reg or (is_login and is_button(a, cfg))) and dest not in cfg["play_paths"]:
            rep.add("Login/Register CTA -> /play", "FAIL", path_url,
                    f"{'button' if is_button(a, cfg) else 'link'} \"{text[:40]}\" points to {href}")

    # 8. Em dashes
    n_em = vis.count(EM_DASH) + (title.count(EM_DASH) + desc.count(EM_DASH))
    if n_em:
        rep.add("No em dashes", "FAIL", path_url, f"{n_em} em dash(es), e.g. {snippet(vis, EM_DASH)}")

    # 9. Second person (reader addressed as "you")
    words = cfg["second_person"].get(lang, cfg["second_person"]["en"])
    hits = defaultdict(int)
    for w in words:
        hits[w] = len(re.findall(r"(?<!\w)" + re.escape(w) + r"(?!\w)", vis_low))
    total = sum(hits.values())
    if total:
        top = ", ".join(f"{k}={v}" for k, v in sorted(hits.items(), key=lambda x: -x[1]) if v)[:120]
        rep.add("No 2nd person (\"you\")", "FAIL" if total > 3 else "REVIEW", path_url,
                f"{total} hits [{lang}]: {top}")

    # 10. Banned AI phrases
    for ph in cfg["banned_phrases"]:
        if ph in vis_low:
            rep.add("AI phrase", "REVIEW", path_url, f"\"{ph}\" -> {snippet(vis, ph)}")

    # 11. Placeholders / dev notes
    for ph in cfg["placeholders"]:
        if re.search(r"(?<!\w)" + re.escape(ph.strip()) + r"(?!\w)", vis_low) if ph.strip().isalnum() else ph in vis_low:
            rep.add("Placeholders / dev notes", "FAIL", path_url, f"\"{ph.strip()}\" -> {snippet(vis, ph.strip())}")
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        if re.search(r"todo|fixme|placeholder|replace|claude|ai generated", c, re.I):
            rep.add("Placeholders / dev notes", "FAIL", path_url, f"HTML comment: {c.strip()[:80]}")

    # 12. Forbidden names / voice
    for nm in cfg["forbidden_names"]:
        if nm.lower().strip() and re.search(r"(?<!\w)" + re.escape(nm.strip().lower()) + r"(?!\w)", raw.lower()):
            rep.add("Forbidden name", "FAIL", path_url, f"\"{nm.strip()}\" found (line {line_of(raw, nm.strip())})")
    for ph in cfg["forbidden_voice"]:
        if ph in vis_low:
            rep.add("Brand voice", "FAIL", path_url, f"\"{ph}\" -> {snippet(vis, ph)}")

    # 12b. Forbidden terms (operator, licence, glance ...), licence numbers, regulator names
    desc_tag = soup.find("meta", attrs={"name": "description"})
    alts = " ".join(i.get("alt", "") for i in soup.find_all("img"))
    scan = " ".join([vis, title, desc_tag.get("content", "") if desc_tag else "", alts])
    for group, hits in forbidden_term_hits(scan, cfg).items():
        rep.add("Forbidden terms", "FAIL", path_url,
                f"{group}: " + "; ".join(f"\"{w}\" -> {snippet(scan, w)}" for w in hits[:3])
                + (f" (+{len(hits) - 3} more)" if len(hits) > 3 else ""))
    nums = []
    for pat in cfg["licence_number_patterns"]:
        for m in re.finditer(pat, scan, re.I if "no|nr" in pat else 0):
            if not any(m.group(0) in n or n in m.group(0) for n in nums):
                nums.append(m.group(0))
    if nums:
        rep.add("Licence number", "FAIL", path_url, "licence/registration number(s): " + ", ".join(nums[:6])
                + f" -> {snippet(scan, nums[0])}")
    regs = [r for r in cfg["regulator_names"] if re.search(r"(?<!\w)" + re.escape(r) + r"(?!\w)", scan.lower())]
    if regs:
        rep.add("Licence number", "REVIEW" if page_type == "mandatory" else "FAIL", path_url,
                "regulator named (licence claim unless it is a help resource on the responsible-gambling page): "
                + ", ".join(regs[:5]))

    # 12c. Login page wording: H1 and title carry the geo's login word, never "access account"
    path_low = urlparse(path_url).path.lower() if "://" in path_url else path_url.lower()
    for ph in cfg["login_bad_phrases"]:
        if ph in scan.lower():
            rep.add("Login wording", "FAIL", path_url, f"\"{ph}\" -> {snippet(scan, ph)}; use the normal login word")
    if any(w in path_low for w in cfg["login_slug_words"]):
        words_ok = cfg["login_words"].get(lang, []) + cfg["login_words"]["en"]
        h1t = soup.find("h1").get_text(" ", strip=True).lower() if soup.find("h1") else ""
        for label, txt in (("H1", h1t), ("title", title.lower())):
            if not any(w in txt for w in words_ok):
                rep.add("Login wording", "FAIL", path_url,
                        f"login page {label} has no login word ({', '.join(cfg['login_words'].get(lang, ['login'])[:2])}): \"{txt[:70]}\"")

    # 12e. Content structure: steps written as paragraphs, too few lists/tables, slogan headings
    main_el = soup.find("main") or soup.body
    if main_el:
        seq = sorted(set(SEQ_WORDS.get(lang, []) + SEQ_WORDS["en"]))
        para_steps = 0
        for p_el in main_el.find_all("p"):
            pl = p_el.get_text(" ", strip=True).lower()
            if sum(len(re.findall(r"(?<!\w)" + re.escape(w) + r"(?!\w)", pl)) for w in seq) >= 3:
                para_steps += 1
        if para_steps:
            rep.add("Content structure", "FAIL", path_url, f"{para_steps} paragraph(s) read as steps (3+ sequence words); write them as numbered lists")
        n_blocks = len(main_el.find_all(["ul", "ol", "table"]))
        mwc = word_count(main_text(soup))
        per = 1000 if page_type == "mandatory" else 600
        if mwc > per and n_blocks < mwc // per:
            rep.add("Content structure", "FAIL", path_url,
                    f"{n_blocks} list/table block(s) for {mwc} words; need at least {mwc // per}: steps, criteria and comparisons belong in lists or tables")
        groups, parent = {}, ""
        for h in main_el.find_all(["h2", "h3"]):
            t = h.get_text(" ", strip=True)
            if h.name == "h2":
                parent = t
            fw = re.sub(r"[^\w]", "", t.split()[0].lower()) if t.split() else ""
            if fw and len(fw) > 2 and fw not in STOP_FIRST:
                groups.setdefault((h.name, parent if h.name == "h3" else "", fw), []).append(t)
            if any(re.search(f_, t, re.I) for f_ in FLUFF_HEADINGS):
                rep.add("Content structure", "FAIL", path_url, f"brand-slogan heading, not a search topic: \"{t[:60]}\"")
        for (lvl, _, fw), hs in groups.items():
            if len(hs) >= 3:
                rep.add("Content structure", "FAIL", path_url,
                        f"templated slogan headings ({len(hs)} {lvl.upper()} start with '{fw}'): " + "; ".join(hs[:4]))

    # 12f. Pros/cons, generic headings, FAQ answer length, table count
    if main_el:
        for h in main_el.find_all(["h2", "h3", "h4"]):
            t = h.get_text(" ", strip=True)
            if re.search(PROS_CONS_RE, t, re.I):
                rep.add("Content structure", "FAIL", path_url, f"pros/cons section not wanted: \"{t[:60]}\"")
            if any(re.search(g, t.strip(), re.I) for g in GENERIC_HEADINGS):
                rep.add("Content structure", "FAIL", path_url, f"generic heading, not a search topic: \"{t[:60]}\"")
        for lab in main_el.find_all(["strong", "b", "dt", "th"]):
            lt = lab.get_text(" ", strip=True)
            if len(lt) < 30 and re.fullmatch(r"\W*" + PROS_CONS_RE + r"\W*", lt, re.I):
                rep.add("Content structure", "FAIL", path_url, f"pros/cons block (label \"{lt}\")")
                break
        n_tab = len(main_el.find_all("table"))
        lim = TABLE_LIMIT.get(page_type, TABLE_LIMIT["default"])
        if n_tab > lim:
            rep.add("Content structure", "FAIL", path_url, f"{n_tab} tables (max {lim} on a {page_type} page); turn the rest into lists or prose")
        faq_h2 = next((h for h in main_el.find_all("h2") if re.search(FAQ_HEAD_RE, h.get_text(" ", strip=True), re.I)), None)
        if faq_h2:
            long_ans = []
            q = None
            words = 0
            for el in faq_h2.find_all_next():
                if el.name == "h2":
                    break
                if el.name in ("h3", "h4", "summary", "dt"):
                    if q and words > FAQ_ANSWER_MAX:
                        long_ans.append((q, words))
                    q, words = el.get_text(" ", strip=True), 0
                elif el.name in ("p", "li", "dd") and q:
                    words += word_count(el.get_text(" ", strip=True))
            if q and words > FAQ_ANSWER_MAX:
                long_ans.append((q, words))
            if long_ans:
                rep.add("Content structure", "FAIL", path_url,
                        f"{len(long_ans)} FAQ answer(s) over {FAQ_ANSWER_MAX} words: "
                        + "; ".join(f"\"{qq[:35]}\" {w}w" for qq, w in long_ans[:3]))

    # 12d. Favicon
    if not soup.find("link", rel=lambda r: r and any(x in ("icon", "shortcut") for x in (r.split() if isinstance(r, str) else r))):
        rep.add("Favicon", "FAIL", path_url, "no <link rel=\"icon\"> in <head>")

    # 13. Schema: present, but no Review / AggregateRating
    blocks = soup.find_all("script", type="application/ld+json")
    if not blocks:
        rep.add("Schema", "REVIEW", path_url, "no JSON-LD schema")
    for b in blocks:
        txt = b.string or b.get_text() or ""
        try:
            json.loads(txt)
        except Exception:
            rep.add("Schema", "FAIL", path_url, "invalid JSON-LD")
        if re.search(r'"@type"\s*:\s*"(Review|AggregateRating)"', txt) or '"aggregateRating"' in txt or '"review"' in txt:
            rep.add("Schema", "FAIL", path_url, "review / rating schema present")

    # 14. Images WebP + alt
    for img in soup.find_all("img"):
        src = (img.get("src") or "").split("?")[0].lower()
        if src and not src.endswith(".webp") and not src.startswith("data:") and not src.endswith(".svg"):
            rep.add("Images WebP", "FAIL", path_url, f"non-WebP image: {src}")
        if not img.get("alt"):
            rep.add("Image alt", "REVIEW", path_url, f"missing alt: {src}")

    # 15. 18+ visible (footer)
    footer = soup.find("footer")
    if not footer or "18+" not in footer.get_text():
        rep.add("18+ badge in footer", "FAIL", path_url, "no 18+ in footer")
    if page_type == "home" and "18+" not in main_text(soup):
        rep.add("18+ disclosure on home", "REVIEW", path_url, "no 18+ line in homepage body")

    # 16. Word count
    wc = word_count(main_text(soup))
    target = cfg["word_count"][page_type]
    if wc < target:
        sev = "REVIEW" if wc >= target * 0.9 else "FAIL"
        rep.add("Word count", sev, path_url, f"{wc} words ({page_type} target {target}+)")

    # Text walls: longest run of words in <main> with no visual (img, svg, video, picture, [data-visual])
    main = soup.find("main") or soup.body
    if main:
        from bs4 import NavigableString, Tag
        run = longest = 0
        for node in main.descendants:
            if isinstance(node, Tag):
                if node.name in ("img", "svg", "video", "picture", "canvas") or node.has_attr("data-visual"):
                    run = 0
            elif isinstance(node, NavigableString) and node.parent and node.parent.name not in ("script", "style"):
                run += len(node.split())
                longest = max(longest, run)
        wall = cfg.get("text_wall_words", [700, 1200])
        if longest > wall[0]:
            rep.add("Visual breaks", "FAIL" if longest > wall[1] and page_type != "mandatory" else "REVIEW", path_url,
                    f"{longest} words in a row without any image or visual block (add one every ~500-700 words)")

    # 17. Age-gate popup (not wanted)
    if re.search(r"age[-_ ]?gate|age[-_ ]?verif|are you (over )?18", raw, re.I):
        rep.add("No age gate popup", "REVIEW", path_url, "possible age-gate markup found")

    return wc


# --------------------------------------------------------------------------
# Site-level
# --------------------------------------------------------------------------
def classify(url_path, cfg):
    if url_path == "/" or re.fullmatch(r"/[a-z]{2}(-[a-z]{2})?", url_path):
        return "home"
    slug = url_path.lower()
    for kws in cfg["mandatory_pages"].values():
        if any(re.search(r"(^|[/-])" + re.escape(k), slug) for k in kws):
            return "mandatory"
    return "other"


def run(site_dir, cfg):
    rep = Report()
    pages = {}
    for root, dirs, files in os.walk(site_dir):
        dirs[:] = [d for d in dirs if not d.startswith((".", "node_modules"))]
        for f in files:
            if f.endswith(".html"):
                rel = os.path.relpath(os.path.join(root, f), site_dir)
                if rel.lower() in ("404.html",):
                    continue
                pages[file_to_url_path(rel)] = os.path.join(root, f)

    if not pages:
        print("No .html files found in", site_dir)
        sys.exit(1)

    # internal host detection from canonicals
    internal_hosts = set()
    parsed = {}
    for up, fp in pages.items():
        raw = open(fp, encoding="utf-8", errors="ignore").read()
        soup = BeautifulSoup(raw, "lxml")
        parsed[up] = (raw, soup)
        can = soup.find("link", rel=lambda r: r and "canonical" in (r.split() if isinstance(r, str) else r))
        if can and can.get("href"):
            h = urlparse(can["href"]).netloc.lower().replace("www.", "")
            if h:
                internal_hosts.add(h)

    site_files = set(pages.keys())
    inbound = defaultdict(set)
    word_counts = {}
    for up, (raw, soup) in parsed.items():
        ptype = classify(up, cfg)
        word_counts[up] = (ptype, check_page(up, raw, soup, cfg, rep, site_files, ptype, internal_hosts))
        for a in soup.find_all("a", href=True):
            u = urlparse(a["href"])
            if not u.netloc or u.netloc.lower().replace("www.", "") in internal_hosts:
                inbound[(u.path.rstrip("/") or "/")].add(up)

    # Orphans
    for up in pages:
        if up != "/" and not (inbound.get(up, set()) - {up}):
            rep.add("Interlinking", "FAIL", up, "orphan page (no internal links point to it)")

    # Mandatory pages per language root
    roots = {""}
    for up in pages:
        seg = up.split("/")[1] if up.count("/") >= 1 else ""
        if re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", seg) and ("/" + seg) in pages:
            roots.add(seg)
    lang_roots = roots - {""}
    for r in sorted(roots):
        if r:
            scope = [p for p in pages if p == "/" + r or p.startswith("/" + r + "/")]
        else:
            scope = [p for p in pages if p.split("/")[1] not in lang_roots]
            if not scope:
                continue
        for name, kws in cfg["mandatory_pages"].items():
            if not any(any(re.search(r"(^|[/-])" + re.escape(k), p.lower()) for k in kws) for p in scope):
                rep.add("Mandatory pages", "FAIL", "/" + r if r else "/", f"{name} page not found")

    # Duplicate titles / descriptions
    seen_t, seen_d = defaultdict(list), defaultdict(list)
    for up, (raw, soup) in parsed.items():
        if soup.title:
            seen_t[soup.title.get_text(strip=True)].append(up)
        md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        if md:
            seen_d[md.get("content", "").strip()].append(up)
    for t, ups in seen_t.items():
        if t and len(ups) > 1:
            rep.add("Duplicate meta title", "FAIL", ", ".join(ups), t)
    for d, ups in seen_d.items():
        if d and len(ups) > 1:
            rep.add("Duplicate meta description", "FAIL", ", ".join(ups), d[:80])

    # sitemap / robots
    sm = os.path.join(site_dir, "sitemap.xml")
    if not os.path.exists(sm):
        rep.add("Sitemap", "FAIL", "site", "sitemap.xml missing")
    else:
        locs = re.findall(r"<loc>\s*([^<]+)\s*</loc>", open(sm, encoding="utf-8", errors="ignore").read())
        sm_paths = {(urlparse(l).path.rstrip("/") or "/") for l in locs}
        for up in pages:
            if up not in sm_paths:
                rep.add("Sitemap", "REVIEW", up, "page not in sitemap.xml")
        for p in sm_paths - set(pages):
            rep.add("Sitemap", "FAIL", p, "sitemap URL has no matching page")
        if any(l.strip().endswith(".html") for l in locs):
            rep.add("Sitemap", "FAIL", "site", "sitemap contains .html URLs")
    rb = os.path.join(site_dir, "robots.txt")
    if not os.path.exists(rb):
        rep.add("Robots.txt", "FAIL", "site", "robots.txt missing")
    elif "sitemap" not in open(rb, encoding="utf-8", errors="ignore").read().lower():
        rep.add("Robots.txt", "REVIEW", "site", "robots.txt has no Sitemap line")

    # Worker / functions that could override meta
    for cand in ["_worker.js", "functions", "worker.js", "src/index.js"]:
        if os.path.exists(os.path.join(site_dir, cand)):
            rep.add("Worker meta override", "REVIEW", "site",
                    f"{cand} exists - confirm it does not rewrite title/meta/canonical")

    return rep, word_counts, pages



# --------------------------------------------------------------------------
# Live URL mode: download pages listed in sitemap.xml into a temp folder
# --------------------------------------------------------------------------
UA = "Mozilla/5.0 (compatible; BrandQC/1.0)"


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="ignore"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception as e:
        return f"ERR {e.__class__.__name__}: {e}", "", url


def mirror_site(base_url, max_pages=200, extra_paths=None):
    base_url = base_url.rstrip("/")
    host = urlparse(base_url).netloc
    out = tempfile.mkdtemp(prefix="brandqc-")
    st, sm, _ = _get(base_url + "/sitemap.xml")
    if not isinstance(st, int):
        print(f"Cannot reach {base_url}: {st}")
        print("If this workspace blocks outbound requests, use browser_qc.js in the browser instead (see SKILL.md).")
        sys.exit(3)
    locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sm) if st == 200 else []
    # sitemap index -> child sitemaps
    if "<sitemapindex" in sm:
        child = list(locs)
        locs = []
        for c in child:
            _, t, _ = _get(c)
            locs += re.findall(r"<loc>\s*([^<]+?)\s*</loc>", t)
    if st == 200:
        open(os.path.join(out, "sitemap.xml"), "w", encoding="utf-8").write(sm)
    stR, rb, _ = _get(base_url + "/robots.txt")
    if stR == 200:
        open(os.path.join(out, "robots.txt"), "w", encoding="utf-8").write(rb)
    urls = [u for u in locs if urlparse(u).netloc == host] or [base_url + "/"]
    # also follow internal links from the home page (finds pages missing from sitemap)
    _, home, _ = _get(base_url + "/")
    for h in re.findall(r'href=["\']([^"\'#?]+)', home):
        full = h if h.startswith("http") else (base_url + h if h.startswith("/") else None)
        if full and urlparse(full).netloc == host and not re.search(r"\.(css|js|webp|png|jpe?g|svg|ico|xml|txt|pdf)$", full):
            if full not in urls:
                urls.append(full)
    for p in extra_paths or []:
        urls.append(base_url + p)
    status = {}
    seen = set()
    for u in urls[:max_pages]:
        path = urlparse(u).path or "/"
        norm = path.rstrip("/") or "/"
        if norm in seen:
            continue
        seen.add(norm)
        code, html, final = _get(u)
        status[norm] = code
        if code != 200 or "<html" not in html.lower():
            continue
        if urlparse(final).path.rstrip("/") != norm.rstrip("/") and norm != "/":
            continue  # redirected away (e.g. affiliate /play), skip
        rel = "index.html" if norm == "/" else norm.strip("/") + "/index.html"
        fp = os.path.join(out, rel)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, "w", encoding="utf-8").write(html)
    return out, status

# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
CHECK_GROUPS = [
    ("Structure", ["Single H1", "Heading hierarchy", "Word count", "Content structure", "Interlinking", "Mandatory pages"]),
    ("Meta & Indexing", ["Meta title", "Meta description", "Meta description 18+", "Canonical",
                          "OG / Twitter tags", "Hreflang", "Robots meta", "Duplicate meta title",
                          "Duplicate meta description", "Sitemap", "Robots.txt", "Worker meta override"]),
    ("Links & CTAs", ["No # in href", "Links", "Nofollow external", "Nofollow CTA", "External link allowlist",
                       "Clean URLs", "Broken internal link", "Login/Register CTA -> /play"]),
    ("Voice & AI signals", ["No em dashes", "No 2nd person (\"you\")", "AI phrase", "Brand voice", "Forbidden terms", "Licence number", "Login wording",
                             "Forbidden name", "Placeholders / dev notes"]),
    ("Compliance & Assets", ["Schema", "Images WebP", "Image alt", "Visual breaks", "18+ badge in footer",
                              "18+ disclosure on home", "No age gate popup", "Favicon"]),
]


def build_markdown(site_dir, rep, word_counts):
    by_check = defaultdict(list)
    for it in rep.items:
        by_check[it["check"]].append(it)
    fails = sum(1 for i in rep.items if i["severity"] == "FAIL")
    reviews = sum(1 for i in rep.items if i["severity"] == "REVIEW")
    overall = "PASS" if not fails and not reviews else ("CONDITIONAL PASS" if not fails else "FAIL")

    L = []
    L.append(f"## Brand QC Report: {site_dir}")
    L.append(f"_Run: {datetime.now():%Y-%m-%d %H:%M} | Pages checked: {len(word_counts)}_\n")
    L.append(f"**Overall: {overall}**  |  FAIL items: {fails}  |  REVIEW items: {reviews}\n")
    L.append("### Scorecard\n")
    L.append("| Group | Check | Status | Items |")
    L.append("|---|---|---|---|")
    known = set()
    for g, checks in CHECK_GROUPS:
        for c in checks:
            known.add(c)
            items = by_check.get(c, [])
            st = min((i["severity"] for i in items), key=lambda s: SEV_ORDER[s]) if items else "PASS"
            L.append(f"| {g} | {c} | {st} | {len(items)} |")
    for c in by_check:
        if c not in known:
            st = min((i["severity"] for i in by_check[c]), key=lambda s: SEV_ORDER[s])
            L.append(f"| Other | {c} | {st} | {len(by_check[c])} |")

    L.append("\n### Word counts\n")
    L.append("| Page | Type | Words |")
    L.append("|---|---|---|")
    for up, (pt, wc) in sorted(word_counts.items()):
        L.append(f"| {up} | {pt} | {wc} |")

    n = 0
    for sev in ["FAIL", "REVIEW"]:
        its = [i for i in rep.items if i["severity"] == sev]
        if not its:
            continue
        L.append(f"\n### {sev} items ({len(its)})\n")
        for i in sorted(its, key=lambda x: (x["check"], x["page"])):
            n += 1
            L.append(f"{n}. **{i['check']}** `{i['page']}`: {i['detail']}")

    L.append("\n### Action")
    if overall == "PASS":
        L.append("Ready to deliver.")
    else:
        L.append(f"Fix {fails} FAIL item(s), check {reviews} REVIEW item(s), then re-run QC.")
    L.append("\n_Not covered by this script (needs the AI QC pass): entity density, topical coverage vs brief, "
             "vague claims without numbers, unbacked licence claims, factual accuracy of bonus/T&C data, "
             "templated/repetitive section patterns._")
    return "\n".join(L), overall, fails, reviews


def main():
    ap = argparse.ArgumentParser(description="Brand site QC gate")
    ap.add_argument("site", help="local built site folder OR live URL (https://domain.com)")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--config", help="JSON file overriding default config")
    ap.add_argument("--out", default=None, help="output folder (default: <site_dir>/../qc-reports)")
    a = ap.parse_args()

    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if a.config:
        deep_merge(cfg, json.load(open(a.config, encoding="utf-8")))

    live = a.site.startswith(("http://", "https://"))
    status = {}
    if live:
        # probe common mandatory slugs too, so missing pages show as 404 in the report
        site_dir, status = mirror_site(a.site, a.max_pages)
        name = urlparse(a.site).netloc.replace(":", "_")
    else:
        site_dir = a.site
        name = os.path.basename(os.path.abspath(site_dir))

    rep, wcs, pages = run(site_dir, cfg)
    for pth, code in status.items():
        if pth in cfg["play_paths"]:
            continue  # affiliate redirect, not a page
        if code != 200:
            rep.add("HTTP status", "FAIL" if code == 404 or not isinstance(code, int) else "REVIEW", pth, f"returned {code}")
    md, overall, fails, reviews = build_markdown(name, rep, wcs)

    out = a.out or (os.path.join(os.getcwd(), "qc-reports") if live else os.path.join(os.path.dirname(os.path.abspath(site_dir)), "qc-reports"))
    os.makedirs(out, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    mdp = os.path.join(out, f"qc-{name}-{stamp}.md")
    jp = os.path.join(out, f"qc-{name}-{stamp}.json")
    open(mdp, "w", encoding="utf-8").write(md)
    json.dump({"site": name, "overall": overall, "fails": fails, "reviews": reviews,
               "word_counts": {k: {"type": v[0], "words": v[1]} for k, v in wcs.items()},
               "items": rep.items}, open(jp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Overall: {overall} | FAIL {fails} | REVIEW {reviews}")
    print("Report:", mdp)
    print("JSON:  ", jp)
    sys.exit(0 if overall != "FAIL" else 2)


if __name__ == "__main__":
    main()
