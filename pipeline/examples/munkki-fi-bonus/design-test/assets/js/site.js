// Same-page jumps without "#" in href: <button data-jump="section-id">
document.addEventListener("click",function(e){var b=e.target.closest("[data-jump]");if(!b)return;var t=document.getElementById(b.getAttribute("data-jump"));if(t){e.preventDefault();t.scrollIntoView({behavior:"smooth"});}});
