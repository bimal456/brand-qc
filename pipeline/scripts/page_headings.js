// Compact heading extractor for SERP competitor pages (Step 2).
// Open the competitor page in the browser, then run this file with the javascript tool.
// Returns one short string: final URL, word count, title, description, H1/H2/H3.
// Output is capped so it fits in one tool result; if it ends with "...more", read
// window.__ph.slice(1000, 2000) for the rest.
(() => {
  const clean = s => (s || "").replace(/\s+/g, " ").trim();
  const cut = (s, n) => (s.length > n ? s.slice(0, n - 1) + "~" : s);
  const body = document.body.cloneNode(true);
  body.querySelectorAll("script,style,noscript,svg,header,nav,footer,aside,form,iframe").forEach(e => e.remove());
  const words = (clean(body.textContent).match(/[\p{L}\p{N}]+(?:[-'][\p{L}\p{N}]+)*/gu) || []).length;
  const hs = lvl => [...document.querySelectorAll(lvl)]
    .filter(h => !h.closest("header,nav,footer,aside"))
    .map(h => cut(clean(h.textContent), 70))
    .filter(Boolean);
  const desc = (document.querySelector('meta[name="description"]') || {}).content || "";
  const out = [
    "URL " + location.origin + location.pathname,
    "W " + words,
    "T " + cut(clean(document.title), 90),
    "D " + cut(clean(desc), 160),
    "H1 " + hs("h1").join(" | "),
    "H2 " + hs("h2").join(" | "),
    "H3 " + hs("h3").slice(0, 25).join(" | "),
  ].join("\n");
  window.__ph = out;
  return out.length > 1000 ? out.slice(0, 1000) + " ...more" : out;
})();
