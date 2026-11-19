#!/usr/bin/env python3
"""Vẽ ứng viên để review bằng mắt (Pha 2). Công cụ xem ảnh, KHÔNG phải validator: được dùng Pillow.

  py tools/view_candidates.py --delivery runs/r10007/delivery --candidates runs/r10007/candidates.json --out review_png
  py tools/view_candidates.py ... --range 146-180          # chỉ ảnh thứ 146..180 (xếp theo tên) - batch của TV5
  py tools/view_candidates.py ... --images 000000015254 000000015335

Mỗi ứng viên ra một file PNG gồm 3 khung:
  [ảnh gốc] | [box DETECTION (xanh lá, tên lớp YOLO)] | [viền mask PANOPTIC (màu theo segment, tên category)]
Ảnh nhỏ được phóng to để dễ nhìn. Chỉ đọc thư mục delivery được truyền vào.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

PALETTE = [(255, 64, 64), (64, 160, 255), (255, 200, 0), (200, 80, 255), (0, 220, 220),
           (255, 128, 0), (255, 105, 180), (160, 255, 80), (255, 255, 255), (120, 120, 255)]


def font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def label(draw: ImageDraw.ImageDraw, xy, text: str, color, f) -> None:
    x, y = xy
    l, t, r, b = draw.textbbox((x, y), text, font=f)
    draw.rectangle((l - 2, t - 2, r + 2, b + 2), fill=(0, 0, 0))
    draw.text((x, y), text, fill=color, font=f)


def main() -> int:
    ap = argparse.ArgumentParser(description="Vẽ ứng viên để review bằng mắt")
    ap.add_argument("--delivery", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--range", help="vd 146-180: chỉ ảnh thứ 146..180 trong lô (xếp theo tên)")
    ap.add_argument("--images", nargs="*", help="chỉ các ảnh này")
    ap.add_argument("--min-width", type=int, default=700, help="phóng ảnh nhỏ lên tối thiểu chiều rộng này")
    args = ap.parse_args()

    d = Path(args.delivery)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    names80 = [ln.split(" ", 1)[1].strip() for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    cats = {c["id"]: c["name"] for c in pan["categories"]}
    thing = {c["id"] for c in pan["categories"] if c.get("isthing", 1)}
    ann_by_file = {Path(a["file_name"]).stem: a for a in pan["annotations"]}

    cands = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    if isinstance(cands, dict):
        cands = cands.get("candidates", cands.get("errors", []))
    stems = sorted(p.stem for p in (d / "labels").glob("*.txt"))
    keep = None
    if args.range:
        a, b = (int(x) for x in args.range.split("-"))
        keep = set(stems[a - 1:b])
    if args.images:
        keep = (keep or set(stems)) & set(args.images)
    todo = [c for c in cands if keep is None or c.get("image", c.get("target")) in keep]

    f = font(16)
    lines = []
    for i, c in enumerate(todo, 1):
        stem = c.get("image", c.get("target"))
        img_path = d / "images" / f"{stem}.jpg"
        if not img_path.is_file():
            print(f"bỏ qua {stem}: không có file ảnh")
            continue
        img = Image.open(img_path).convert("RGB")
        W, H = img.size
        k = max(1.0, args.min_width / W)
        big = img.resize((round(W * k), round(H * k)), Image.LANCZOS)

        # Detection
        det = big.copy()
        dd = ImageDraw.Draw(det)
        for ln in (d / "labels" / f"{stem}.txt").read_text(encoding="utf-8").splitlines():
            p = ln.split()
            if len(p) < 5:
                continue
            cid = int(float(p[0]))
            x, y, w, h = (float(v) for v in p[1:5])
            x0, y0, x1, y1 = ((x - w / 2) * W * k, (y - h / 2) * H * k, (x + w / 2) * W * k, (y + h / 2) * H * k)
            dd.rectangle((x0, y0, x1, y1), outline=(0, 255, 0), width=3)
            name = names80[cid] if 0 <= cid < len(names80) else f"?{cid}"
            label(dd, (x0 + 2, max(0, y0 - 20)), name, (0, 255, 0), f)

        # Panoptic: viền từng segment thing
        pv = big.copy()
        ann = ann_by_file.get(stem)
        if ann:
            mask = Image.open(d / "masks" / f"{stem}.png").convert("RGB").resize(big.size, Image.NEAREST)
            r, g, bb = mask.split()
            pd = ImageDraw.Draw(pv)
            for j, seg in enumerate(s for s in ann["segments_info"] if s["category_id"] in thing):
                sid = seg["id"]
                rgb = (sid % 256, (sid // 256) % 256, sid // 65536)
                m = ImageChops.multiply(ImageChops.multiply(
                    r.point(lambda v, t=rgb[0]: 255 if v == t else 0),
                    g.point(lambda v, t=rgb[1]: 255 if v == t else 0)),
                    bb.point(lambda v, t=rgb[2]: 255 if v == t else 0))
                if not m.getbbox():
                    continue
                edge = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(5)), m)
                col = PALETTE[j % len(PALETTE)]
                pv.paste(Image.new("RGB", big.size, col), (0, 0), edge)
                l, t, _, _ = m.getbbox()
                name = cats.get(seg["category_id"], f"?{seg['category_id']}") + (" (crowd)" if seg.get("iscrowd") else "")
                label(pd, (l + 2, t + 2), name, col, f)

        gap = 8
        sheet = Image.new("RGB", (big.width * 3 + gap * 2, big.height + 34), (30, 30, 30))
        for n, part in enumerate((big, det, pv)):
            sheet.paste(part, (n * (big.width + gap), 34))
        sd = ImageDraw.Draw(sheet)
        sd.text((6, 6), f"{stem} | {c.get('type')} | gốc  /  DETECTION (xanh lá)  /  PANOPTIC (viền màu)   "
                        f"| {c.get('note', '')}"[:200], fill=(255, 255, 255), font=f)
        dst = out / f"{i:02d}_{stem}_{c.get('type')}.png"
        sheet.save(dst)
        lines.append(f"{dst.name}\t{c.get('note', '')}")
        print("ghi", dst)
    (out / "_list.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Xong {len(lines)} ảnh -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
