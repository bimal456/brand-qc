#!/usr/bin/env python3
"""Image plan -> WebP files + design/images.json.

Usage:
  python3 make_images.py <project> --prompts   # print the ChatGPT prompts still to generate
  python3 make_images.py <project> --slots     # list the slot ids per built page (section ids)
  python3 make_images.py <project>             # convert raw files, write images.json, list what is missing

design/image_plan.json:
{
  "style": "3D cartoon casino art, dark navy background (#0d1b2a), bright green accents (#1ed760), soft studio light,
            glossy, centered subject, plenty of empty space on the left, no text, no letters, no logos, no people",
  "items": [
    {"id": "bonus-hero", "source": "chatgpt", "page": "it/bonus", "slot": "hero",
     "display": [560, 360], "subject": "an open gift box spilling gold crypto coins", "alt": "Bonus di benvenuto"},
    {"id": "lobby-slots", "source": "screenshot", "page": "it/home", "slot": "<section-id>",
     "display": [720, 300], "file": "raw/lobby.png", "crop": [120, 300, 1560, 900], "alt": "..."},
    {"id": "bonus-steps", "source": "css", "page": "it/bonus", "slot": "<section-id>", "html": "visuals/bonus-steps.html"},
    {"id": "bonus-games", "source": "games", "page": "it/bonus", "slot": "<section-id>@end", "games": "popular", "limit": 6}
  ]
}
- chatgpt: the raw download goes to design/raw/<id>.png (or "file"). Prompt = style + subject.
- screenshot: "file" is a screenshot in design/raw/, "crop" = x0,y0,x1,y1 in that file's pixels.
- Every image is cover-cropped to the display ratio and saved at 2x display size as
  design/assets/img/v/<id>.webp (quality 82). One 2x file with width/height = display size is sharp
  on phones and retina screens and stays small as WebP.
- slot: "hero", "intro", a section id (H2 slug), or "<section id>@end". Several items may share a slot.
"""
import json, os, sys

from PIL import Image

PLAN = "design/image_plan.json"


def cover(im, w, h):
    sw, sh = im.size
    r = max(w / sw, h / sh)
    im = im.resize((max(w, round(sw * r)), max(h, round(sh * r))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def main():
    proj = sys.argv[1]
    plan = json.load(open(os.path.join(proj, PLAN), encoding="utf-8"))
    style = plan.get("style", "").strip()
    items = plan["items"]
    dz = os.path.join(proj, "design")

    if "--slots" in sys.argv:
        import glob, re
        site = json.load(open(os.path.join(proj, "site.json"), encoding="utf-8"))
        for g in site["geos"]:
            pre = g.get("prefix", "/").strip("/")
            for p in site["pages"]:
                slug = (p.get("slugs") or {}).get(g["code"], p.get("slug", "/")).strip("/")
                name = slug.replace("/", "-") or "home"
                f = os.path.join(proj, "build", pre, (slug or "index") + ".html")
                if not os.path.exists(f):
                    continue
                ids = re.findall(r'class="sec" id="([^"]+)"', open(f, encoding="utf-8").read())
                print(f"{g['code']}/{name}: hero, intro, " + ", ".join(ids) + "  (append @end for the end of a section)")
        return

    if "--prompts" in sys.argv:
        todo = [i for i in items if i["source"] == "chatgpt"
                and not os.path.exists(os.path.join(dz, i.get("file", f"raw/{i['id']}.png")))]
        for i in todo:
            w, h = i["display"]
            shape = "wide landscape" if w / h > 1.3 else ("tall portrait" if h / w > 1.3 else "square")
            print(f"## {i['id']}  ->  save as design/{i.get('file', 'raw/' + i['id'] + '.png')}")
            print(f"{i['subject']}. {style}. Format: {shape} image.\n")
        print(f"{len(todo)} prompt(s) to generate")
        return

    images = {}
    imgjson = os.path.join(dz, "images.json")
    if os.path.exists(imgjson):
        images = json.load(open(imgjson, encoding="utf-8"))
    planned_pages = {i["page"] for i in items}
    for p in planned_pages:  # the plan owns these pages' entries
        images.pop(p, None)

    missing, done = [], 0
    outdir = os.path.join(dz, "assets", "img", "v")
    os.makedirs(outdir, exist_ok=True)
    for i in items:
        src = i["source"]
        if src == "css":
            if not os.path.exists(os.path.join(dz, i["html"])):
                missing.append(f"{i['id']}: CSS visual design/{i['html']} not written yet")
                continue
            entry = {"html": i["html"]}
        elif src == "games":
            entry = {"games": i["games"], "limit": i.get("limit", 8)}
        else:
            raw = os.path.join(dz, i.get("file", f"raw/{i['id']}.png"))
            if not os.path.exists(raw):
                missing.append(f"{i['id']}: {src} file {os.path.relpath(raw, proj)} missing")
                continue
            w, h = i["display"]
            im = Image.open(raw).convert("RGB")
            if i.get("crop"):
                im = im.crop(tuple(i["crop"]))
            if im.width < w * 2 or im.height < h * 2:
                print(f"WARNING {i['id']}: source {im.width}x{im.height} is below 2x display ({w*2}x{h*2}); "
                      "it will look soft. Use a bigger source or a zoom screenshot.")
            cover(im, w * 2, h * 2).save(os.path.join(outdir, f"{i['id']}.webp"), "WEBP", quality=82, method=6)
            entry = {"src": f"/assets/img/v/{i['id']}.webp", "alt": i.get("alt", ""), "width": w, "height": h}
            done += 1
        slot = images.setdefault(i["page"], {}).get(i["slot"])
        if slot is None:
            images[i["page"]][i["slot"]] = entry
        else:
            images[i["page"]][i["slot"]] = (slot if isinstance(slot, list) else [slot]) + [entry]
    json.dump(images, open(imgjson, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    heroes = [i for i in items if i["slot"] == "hero"]
    pages_with_hero = {i["page"] for i in heroes}
    print(f"{done} image(s) written to design/assets/img/v/, images.json updated for {len(planned_pages)} page(s)")
    print(f"pages with their own hero: {len(pages_with_hero)}")
    for m in missing:
        print("MISSING", m)
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
