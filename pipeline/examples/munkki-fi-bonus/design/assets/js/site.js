// Same-page jumps without "#" in href, carousel arrows, mobile menu.
document.addEventListener("click", function (e) {
  var j = e.target.closest("[data-jump]");
  if (j) { var t = document.getElementById(j.getAttribute("data-jump")); if (t) { e.preventDefault(); t.scrollIntoView({behavior: "smooth", block: "start"}); } return; }
  var s = e.target.closest("[data-scroll]");
  if (s) { var tr = s.closest(".row").querySelector(".track"); tr.scrollBy({left: tr.clientWidth * 0.8 * (+s.getAttribute("data-scroll")), behavior: "smooth"}); return; }
  if (e.target.closest("[data-menu]")) { document.body.classList.toggle("menu-open"); }
});
