#!/usr/bin/env python3
"""Script hỗ trợ Review trực quan: Phân chia lô ảnh & Vẽ Bounding Box Detection (YOLO) + Panoptic lên ảnh.
Công cụ phục vụ vai trò QC / Review Manager của nhóm.

Sử dụng:
  # 1. Xem phân chia lô 250 ảnh cho các thành viên trong nhóm:
  python scripts/preview_boxes.py --split-info

  # 2. Vẽ dải ảnh được phân công (0106 -> 0145, 40 ảnh):
  python scripts/preview_boxes.py --delivery runs/r1007/delivery --range 106 145 --out previews/

  # 3. Chỉ vẽ các ảnh nằm trong danh sách nghi vấn candidates.json (để duyệt siêu tốc):
  python scripts/preview_boxes.py --delivery runs/r1007/delivery --candidates runs/r1007/candidates.json --candidates-only --out previews/

  # 4. Vẽ một ảnh cụ thể:
  python scripts/preview_boxes.py --delivery runs/r1007/delivery --image img_0112 --out previews/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw


def print_split_info():
    """In phân bổ chia dải 250 ảnh cho nhóm 5-6 người."""
    print("=" * 65)
    print(" BẢNG PHÂN CHIA LÔ 250 ẢNH CHO CÁC THÀNH VIÊN TRONG NHÓM")
    print("=" * 65)
    splits = [
        ("Thành viên 1", "0001 → 0035", 35),
        ("Thành viên 2", "0036 → 0070", 35),
        ("Thành viên 3", "0071 → 0105", 35),
        ("BẠN (QC Lead)", "0106 → 0145", 40),
        ("Thành viên 5", "0146 → 0195", 50),
        ("Thành viên 6", "0196 → 0250", 55),
    ]
    print(f"{'Thành viên':<18} | {'Dải ảnh':<15} | {'Số lượng':<8}")
    print("-" * 65)
    for member, r, count in splits:
        prefix = "-> " if "BẠN" in member else "   "
        print(f"{prefix}{member:<15} | {r:<15} | {count:<8} ảnh")
    print("=" * 65)
    print("Lưu ý: Mọi thành viên phải tuân thủ ghi chú >= 20 ký tự, mô tả rõ vật thể.")


def parse_yolo(label_path: Path, img_w: int, img_h: int) -> list[tuple[int, int, int, int, int]]:
    boxes = []
    if not label_path.is_file():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) >= 5:
            cid = int(float(parts[0]))
            xc, yc, w, h = map(float, parts[1:5])
            x1 = max(0, int((xc - w / 2) * img_w))
            y1 = max(0, int((yc - h / 2) * img_h))
            x2 = min(img_w - 1, int((xc + w / 2) * img_w))
            y2 = min(img_h - 1, int((yc + h / 2) * img_h))
            boxes.append((cid, x1, y1, x2, y2))
    return boxes


def main() -> int:
    parser = argparse.ArgumentParser(description="Chia lô & Vẽ preview Detection (YOLO) + Panoptic lên ảnh")
    parser.add_argument("--delivery", help="Thư mục delivery/ của lô (ví dụ runs/r1007/delivery)")
    parser.add_argument("--candidates", help="Đường dẫn file candidates.json (nếu có)")
    parser.add_argument("--candidates-only", action="store_true", help="Chỉ render các ảnh nằm trong candidates.json")
    parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Dải số ảnh cần vẽ, ví dụ: --range 106 145")
    parser.add_argument("--image", help="Tên một ảnh cụ thể (không cần đuôi .jpg)")
    parser.add_argument("--out", default="previews", help="Thư mục lưu ảnh đã vẽ preview (mặc định: previews/)")
    parser.add_argument("--split-info", action="store_true", help="Xem bảng phân chia dải ảnh cho nhóm")
    args = parser.parse_args()

    if args.split_info:
        print_split_info()
        if not args.delivery:
            return 0

    if not args.delivery:
        parser.error("Cần truyền --delivery <thư_mục_delivery> hoặc --split-info")

    delivery = Path(args.delivery).resolve()
    if not (delivery / "images").is_dir():
        print(f"Lỗi: Không tìm thấy thư mục ảnh tại {delivery / 'images'}", file=sys.stderr)
        return 1

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Đọc classes.txt
    classes: dict[int, str] = {}
    if (delivery / "classes.txt").is_file():
        for line in (delivery / "classes.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                parts = line.strip().split(" ", 1)
                classes[int(parts[0])] = parts[1].strip()

    # Đọc panoptic.json
    pan_doc = {}
    if (delivery / "panoptic.json").is_file():
        pan_doc = json.loads((delivery / "panoptic.json").read_text(encoding="utf-8"))
    cat_names = {c["id"]: c["name"] for c in pan_doc.get("categories", [])}
    pan_anns = {}
    for ann in pan_doc.get("annotations", []):
        file_name = ann.get("file_name", "")
        stem = Path(file_name).stem
        pan_anns[stem] = ann.get("segments_info", [])

    # Đọc candidates.json
    cand_map: dict[str, list[str]] = {}
    if args.candidates and Path(args.candidates).is_file():
        cands_data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
        items = cands_data.get("candidates") or cands_data.get("errors") or []
        for c in items:
            t = c.get("target") or c.get("image")
            k = c.get("type", "unknown")
            if t:
                cand_map.setdefault(t, []).append(k)

    all_images = sorted((delivery / "images").glob("*.jpg"))
    if not all_images:
        print(f"Không có ảnh .jpg nào trong {delivery / 'images'}")
        return 0

    # Lọc danh sách ảnh cần xử lý
    selected_images = []
    for idx, img_p in enumerate(all_images, 1):
        stem = img_p.stem
        # Xác định số thứ tự của ảnh (nếu tên dạng img_0106 hoặc lấy 1-based index)
        num = idx
        if stem.startswith("img_"):
            try:
                num = int(stem.split("_")[1])
            except ValueError:
                num = idx

        if args.image and stem != args.image:
            continue
        if args.range and not (args.range[0] <= num <= args.range[1]):
            continue
        if args.candidates_only and stem not in cand_map:
            continue
        selected_images.append(img_p)

    print(f"==> Đang render preview cho {len(selected_images)} ảnh vào thư mục: {out_dir}")

    for img_p in selected_images:
        stem = img_p.stem
        img = Image.open(img_p).convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # 1. Vẽ Detection Box (YOLO) - Viền ĐỎ (RED)
        yolo_p = delivery / "labels" / f"{stem}.txt"
        det_boxes = parse_yolo(yolo_p, w, h)
        for cid, x1, y1, x2, y2 in det_boxes:
            cname = classes.get(cid, str(cid))
            draw.rectangle([x1, y1, x2, y2], outline=(255, 30, 30), width=3)
            # Label
            draw.rectangle([x1, max(0, y1 - 16), x1 + len(cname) * 8 + 45, max(16, y1)], fill=(255, 30, 30))
            draw.text((x1 + 3, max(0, y1 - 15)), f"DET: {cname}", fill=(255, 255, 255))

        # 2. Vẽ Panoptic Thing Bbox - Viền XANH LÁ (LIME)
        for seg in pan_anns.get(stem, []):
            if seg.get("iscrowd"):
                continue
            bx, by, bw, bh = seg.get("bbox", [0, 0, 0, 0])
            cname = cat_names.get(seg.get("category_id"), str(seg.get("category_id")))
            draw.rectangle([bx, by, bx + bw, by + bh], outline=(0, 255, 60), width=2)
            draw.rectangle([bx, min(h - 16, by + bh), bx + len(cname) * 8 + 45, min(h, by + bh + 16)], fill=(0, 160, 40))
            draw.text((bx + 3, min(h - 15, by + bh)), f"PAN: {cname}", fill=(255, 255, 255))

        # 3. Banner cảnh báo ứng viên nghi vấn
        if stem in cand_map:
            warn_text = f"[CANDIDATE ALERT] Loai nghi van: {', '.join(cand_map[stem])}"
            draw.rectangle([0, 0, w, 24], fill=(220, 20, 20))
            draw.text((8, 5), warn_text, fill=(255, 255, 255))

        # Chú thích góc dưới
        draw.rectangle([0, h - 20, w, h], fill=(0, 0, 0))
        draw.text((6, h - 17), f"{stem} | DO: Detection (YOLO) | XANH LA: Panoptic", fill=(220, 220, 220))

        img.save(out_dir / f"{stem}_preview.jpg", quality=92)

    print(f"-> Hoàn tất! Đã xuất {len(selected_images)} ảnh preview.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
