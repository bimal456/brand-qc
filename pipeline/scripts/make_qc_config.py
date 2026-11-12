#!/usr/bin/env python3
"""Generate qc/config.json for brand_qc.py from a project's site.json.

Usage: python3 make_qc_config.py <project>/site.json
Writes <project>/qc/config.json and prints it.
"""
import json, os, sys

# Starting list of responsible-gambling domains per geo. Verify before relying on it.
RG = {
    "fi": ["peluuri.fi", "pelirajaton.fi", "tiltti.fi", "gamblingtherapy.org"],
    "se": ["stodlinjen.se", "spelberoende.se", "spelinspektionen.se"],
    "nl": ["loketkansspel.nl", "agog.nl", "kansspelautoriteit.nl"],
    "fr": ["joueurs-info-service.fr", "evalujeu.fr", "sosjoueurs.org", "anj.fr"],
    "de": ["check-dein-spiel.de", "anonyme-spieler.org", "spielen-mit-verantwortung.de"],
    "it": ["giocaresponsabile.it", "adm.gov.it"],
    "pl": ["kcpu.gov.pl", "hazardzisci.pl"],
    "uk": ["begambleaware.org", "gamcare.org.uk", "gamstop.co.uk", "gamblersanonymous.org.uk"],
    "us": ["ncpgambling.org", "gamblersanonymous.org", "1800gambler.net"],
    "au": ["gamblinghelponline.org.au", "gamblershelp.com.au", "gaaustralia.org.au"],
    "ca": ["responsiblegambling.org", "connexontario.ca", "ccsa.ca"],
    "nz": ["gamblinghelpline.co.nz", "pgf.nz"],
    "gr": ["kethea.gr", "gamblingtherapy.org"],
}

def main():
    path = sys.argv[1]
    site = json.load(open(path, encoding="utf-8"))
    crit = site.get("criteria", {})
    allowed = sorted({d for g in site.get("geos", []) for d in RG.get(g["code"], [])})
    cfg = {
        "_generated_from": os.path.abspath(path),
        "_site_type": site.get("site_type"),
        "word_count": crit.get("word_count", {"home": 5000, "other": 3000, "mandatory": 1000}),
        "play_paths": sorted({site.get("play_path", "/play").rstrip("/") or "/play", "/play"}),
        "allowed_external_domains": allowed + crit.get("extra_allowed_domains", []),
        "forbidden_names": ["KAP Digital", "KAP "] + site.get("avoid_names", []),
    }
    if site.get("voice", {}).get("address_reader_as_you"):
        # reader may be addressed as "you" on this site: switch the check off for every language
        cfg["second_person"] = {k: [] for k in ["en", "nl", "de", "fr", "it", "sv", "fi", "pl", "el", "pt"]}
    if crit.get("other_brands_named"):
        cfg["allowed_external_domains"] = []  # comparison sites link out to many brands; REVIEW instead of FAIL
    out = os.path.join(os.path.dirname(os.path.abspath(path)), "qc", "config.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(cfg, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(cfg, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
