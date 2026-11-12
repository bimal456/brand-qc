// Brand QC - browser fallback
// Use when the workspace cannot reach the site (outbound requests blocked).
// Open the site's homepage in Chrome, then run this whole file with the
// javascript tool. It reads sitemap.xml, fetches every page, runs the core
// checks and returns a compact plain-text report (no URLs with query strings).
// Edit CFG below for the site before running.

const CFG = {
  playPaths: ["/play"],                // add "/pelaa" etc. if the site uses it
  allowedExternal: [],                 // geo RG domains, e.g. ["peluuri.fi","tiltti.fi"]
  words: { home: 5000, mandatory: 1000, other: 3000 },
  mandatorySlugs: {
    rg: ["responsible", "vastuullinen", "verantwoord", "jeu-responsable", "gioco-responsabile", "ansvarsfullt", "safer-gambling", "verantwortung"],
    terms: ["terms", "kayttoehdot", "ehdot", "voorwaarden", "agb", "cgu", "conditions", "termini", "villkor"],
    privacy: ["privacy", "tietosuoja", "datenschutz", "confidentialite", "integritet"],
    about: ["about", "tietoa", "over-ons", "uber-uns", "ueber-uns", "a-propos", "chi-siamo", "om-oss"],
    contact: ["contact", "yhteytta", "kontakt", "contatti"]
  },
  secondPerson: {
    en: ["you", "your", "you're", "yourself"],
    fi: ["sinä", "sinun", "sinulle", "sinua", "sinulla", "voit", "saat", "haluat", "tarvitset", "pelaat", "löydät"],
    nl: ["je", "jij", "jouw", "u", "uw"], de: ["du", "dich", "dein", "deine"],
    fr: ["vous", "votre", "vos", "tu"], it: ["tu", "tuo", "tua", "voi"], sv: ["du", "dig", "din", "ditt"],
    pl: ["ty", "twój", "twoja"], el: ["εσύ", "σας", "σου"], pt: ["você", "tu", "seu", "sua"]
  },
  banned: ["in conclusion", "it's important to note", "navigating the", "dive into", "the ultimate guide", "look no further", "yhteenvetona", "on tärkeää huomata"],
  placeholders: ["lorem ipsum", "todo", "placeholder", "[brand]", "kap digital"],
  voice: ["we are not the operator", "information only", "official site", "emme ole operaattori", "virallinen sivusto"]
};

const origin = location.origin;
const sm = await (await fetch("/sitemap.xml")).text().catch(() => "");
let pages = [...sm.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/g)].map(m => new URL(m[1]).pathname);
if (!pages.length) pages = ["/"];
const robots = await fetch("/robots.txt").then(r => r.ok ? r.text() : "").catch(() => "");
const lines = [], titles = {}, descs = {};
const wc = t => (t.match(/[\p{L}\p{N}]+(?:[-'][\p{L}\p{N}]+)*/gu) || []).length;
const norm = p => p.replace(/\/+$/, "") || "/";
const typeOf = p => p === "/" || /^\/[a-z]{2}(-[a-z]{2})?\/?$/.test(p) ? "home"
  : Object.values(CFG.mandatorySlugs).flat().some(k => p.toLowerCase().includes(k)) ? "mandatory" : "other";
let fails = 0, reviews = 0;
const inbound = {};

for (const p of pages) {
  const r = await fetch(p, { redirect: "manual" });
  if (r.status !== 200) { lines.push(`${p} | FAIL HTTP ${r.status || r.type}`); fails++; continue; }
  const raw = await r.text();
  const d = new DOMParser().parseFromString(raw, "text/html");
  const F = [], R = [];
  const meta = n => (d.querySelector(`meta[name="${n}"],meta[property="${n}"]`) || {}).content || "";
  const title = d.title || "", desc = meta("description");
  (titles[title] = titles[title] || []).push(p); (descs[desc] = descs[desc] || []).push(p);
  const lang = (d.documentElement.lang || "en").slice(0, 2).toLowerCase();
  const h1 = d.querySelectorAll("h1").length; if (h1 !== 1) F.push(`H1x${h1}`);
  let prev = 0; d.querySelectorAll("h1,h2,h3,h4,h5,h6").forEach(h => { const l = +h.tagName[1]; if (prev && l > prev + 1) F.push(`skip H${prev}>H${l}`); prev = l; });
  if (title.length < 50 || title.length > 65) F.push(`title ${title.length}`); else if (title.length < 55 || title.length > 60) R.push(`title ${title.length}`);
  if (desc.length < 145 || desc.length > 165) F.push(`desc ${desc.length}`); else if (desc.length < 150 || desc.length > 160) R.push(`desc ${desc.length}`);
  if (!desc.includes("18+")) F.push("no 18+ in desc");
  const can = d.querySelector("link[rel=canonical]")?.getAttribute("href") || "";
  if (!can) F.push("no canonical");
  else { const cp = new URL(can, origin).pathname; if (cp !== "/" && cp.endsWith("/")) R.push("canonical trailing slash"); if (norm(cp) !== norm(p)) R.push("canonical path differs"); }
  ["og:title", "og:description", "og:url", "twitter:card", "twitter:title"].forEach(t => { if (!meta(t)) F.push("no " + t); });
  if (can && meta("og:url") && meta("og:url") !== can) F.push("og:url != canonical");
  const hl = [...d.querySelectorAll("link[rel=alternate][hreflang]")];
  if (!hl.length) F.push("no hreflang"); else if (!hl.some(l => l.getAttribute("hreflang") === "x-default")) R.push("no x-default");
  if (/noindex/i.test(meta("robots"))) R.push("noindex");
  let hash = 0; const extNF = new Set(), extOther = new Set(); let playNF = 0; const cta = [];
  d.querySelectorAll("a").forEach(a => {
    const h = a.getAttribute("href") || ""; const rel = (a.getAttribute("rel") || "").toLowerCase(); const t = a.textContent.trim();
    if (h.includes("#")) { hash++; return; }
    let u; try { u = new URL(h, origin); } catch (e) { return; }
    if (!/^https?:/.test(u.protocol)) return;
    if (u.origin !== origin) {
      if (!rel.includes("nofollow")) extNF.add(u.hostname);
      if (CFG.allowedExternal.length && !CFG.allowedExternal.some(x => u.hostname.endsWith(x))) extOther.add(u.hostname);
      return;
    }
    const np = norm(u.pathname);
    (inbound[np] = inbound[np] || new Set()).add(norm(p));
    if (/\.html$/.test(u.pathname)) F.push("html link " + u.pathname);
    const isPlay = CFG.playPaths.includes(np);
    if (isPlay && !rel.includes("nofollow")) playNF++;
    if (/login|log in|register|sign up|kirjaudu|rekisteröidy|pelaa nyt|anmelden|registrieren|connexion|inscription|inloggen|registreren|accedi|registrati/i.test(t) && !isPlay) cta.push(`${t.slice(0, 20)}>${np}`);
  });
  if (hash) F.push(`${hash} # hrefs`);
  if (extNF.size) F.push("ext not nofollow: " + [...extNF].join(","));
  if (extOther.size) F.push("ext not allowed: " + [...extOther].join(","));
  if (playNF) F.push(`${playNF} play CTA not nofollow`);
  if (cta.length) F.push("CTA not to play: " + cta.slice(0, 3).join("; "));
  const body = d.body.cloneNode(true); body.querySelectorAll("script,style,noscript,svg").forEach(e => e.remove());
  const vis = body.textContent.replace(/\s+/g, " "); const low = vis.toLowerCase();
  const mainEl = body.cloneNode(true); mainEl.querySelectorAll("header,nav,footer").forEach(e => e.remove());
  const words = wc(mainEl.textContent); const tp = typeOf(p); const target = CFG.words[tp];
  if (words < target * 0.9) F.push(`words ${words}/${target}`); else if (words < target) R.push(`words ${words}/${target}`);
  { // text wall: longest run of words in main with no visual
    const m = d.querySelector("main") || d.body; let run = 0, longest = 0;
    const tw = d.createTreeWalker(m, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      if (n.nodeType === 1) { if (/^(IMG|SVG|VIDEO|PICTURE|CANVAS)$/i.test(n.tagName) || n.hasAttribute("data-visual")) run = 0; }
      else if (!/^(SCRIPT|STYLE)$/.test(n.parentNode.tagName)) { run += wc(n.textContent); longest = Math.max(longest, run); }
    }
    if (longest > 1200 && typeOf(p) !== "mandatory") F.push(`text wall ${longest} words`); else if (longest > 700) R.push(`text wall ${longest} words`);
  }
  const em = (vis + title + desc).split("—").length - 1; if (em) F.push(`${em} em dash`);
  const sp = (CFG.secondPerson[lang] || CFG.secondPerson.en).map(w => [w, (low.match(new RegExp("(?<![\\p{L}])" + w + "(?![\\p{L}])", "gu")) || []).length]).filter(x => x[1]);
  const spT = sp.reduce((a, x) => a + x[1], 0); if (spT) (spT > 3 ? F : R).push(`2nd person ${spT} (${sp.sort((a, b) => b[1] - a[1]).slice(0, 4).map(x => x.join("=")).join(",")})`);
  CFG.banned.forEach(b => { if (low.includes(b)) R.push("AI phrase: " + b); });
  CFG.placeholders.forEach(b => { if (low.includes(b)) F.push("placeholder/forbidden: " + b); });
  CFG.voice.forEach(b => { if (low.includes(b)) F.push("voice: " + b); });
  const ld = [...d.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent).join(" ");
  if (!ld) R.push("no schema");
  if (/"(Review|AggregateRating)"|aggregateRating/.test(ld)) F.push("review schema");
  if (/"credentialCategory"\s*:\s*"licen[cs]e"|lisenssi|licence number|license number/i.test(ld)) R.push("licence claim in schema - verify");
  const imgs = [...d.querySelectorAll("img")];
  const nw = imgs.filter(i => { const s = (i.getAttribute("src") || "").split("?")[0]; return s && !/\.webp$/i.test(s) && !s.startsWith("data:") && !/\.svg$/i.test(s); }).length;
  if (nw) F.push(`${nw} non-WebP img`);
  const na = imgs.filter(i => !i.getAttribute("alt")).length; if (na) R.push(`${na} img no alt`);
  const ft = d.querySelector("footer"); if (!ft || !ft.textContent.includes("18+")) F.push("no 18+ footer");
  if (/age[-_ ]?gate|age[-_ ]?verif/i.test(raw)) R.push("age gate markup?");
  fails += F.length; reviews += R.length;
  lines.push(`${p} [${tp}, ${words}w, t${title.length}, d${desc.length}]\n  FAIL: ${F.join(" | ") || "-"}\n  REVIEW: ${R.join(" | ") || "-"}`);
}

const site = [];
Object.entries(titles).forEach(([t, ps]) => { if (t && ps.length > 1) site.push("FAIL dup title: " + ps.join(",")); });
Object.entries(descs).forEach(([t, ps]) => { if (t && ps.length > 1) site.push("FAIL dup desc: " + ps.join(",")); });
pages.forEach(p => { const n = norm(p); if (n !== "/" && !([...(inbound[n] || [])].filter(x => x !== n).length)) site.push("FAIL orphan: " + p); });
Object.entries(CFG.mandatorySlugs).forEach(([k, slugs]) => { if (!pages.some(p => slugs.some(s => p.toLowerCase().includes(s)))) site.push(`FAIL mandatory page missing: ${k}`); });
if (!sm) site.push("FAIL no sitemap.xml");
if (!robots) site.push("FAIL no robots.txt"); else if (!/sitemap/i.test(robots)) site.push("REVIEW robots.txt has no Sitemap line");
fails += site.filter(s => s.startsWith("FAIL")).length; reviews += site.filter(s => s.startsWith("REVIEW")).length;

window.__brandqc = `BRAND QC (browser) ${location.hostname} | pages ${pages.length} | FAIL ${fails} | REVIEW ${reviews} | OVERALL ${fails ? "FAIL" : reviews ? "CONDITIONAL PASS" : "PASS"}\nSITE: ${site.join(" ; ") || "ok"}\n` + lines.join("\n");
// Output can be long. If the tool truncates it, read the rest in slices:
//   window.__brandqc.slice(0, 1000), window.__brandqc.slice(1000, 2000), ...
window.__brandqc.slice(0, 1000);
