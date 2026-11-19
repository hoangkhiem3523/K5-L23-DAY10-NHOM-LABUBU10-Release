#!/usr/bin/env python3
"""Validator cho Day 10 Lab - Bắt lỗi luật và đối chiếu sinh ứng viên.

Giao diện cố định:
    python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]

Chỉ đọc thư mục delivery; chỉ dùng thư viện chuẩn Python (cho phép import scripts/pngutil.py).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

# Thêm thư mục scripts để import pngutil
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import pngutil  # noqa: E402


def sha256_file(path: Path) -> str:
    """Tính mã băm sha256 của file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_iou(boxA: tuple[float, float, float, float], boxB: tuple[float, float, float, float]) -> float:
    """Tính Intersection over Union (IoU) giữa 2 bounding box dạng (xmin, ymin, xmax, ymax)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h

    if inter_area == 0:
        return 0.0

    areaA = max(0.0, boxA[2] - boxA[0]) * max(0.0, boxA[3] - boxA[1])
    areaB = max(0.0, boxB[2] - boxB[0]) * max(0.0, boxB[3] - boxB[1])
    union_area = areaA + areaB - inter_area

    return inter_area / (union_area + 1e-12)


def validate_rules(delivery_dir: Path) -> tuple[list[dict], dict]:
    """Kiểm tra 9 loại lỗi luật (File, Detection, Metadata, Panoptic)."""
    errors: list[dict] = []
    
    # 1. Đọc manifest.json
    manifest_path = delivery_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy manifest.json tại {manifest_path}")
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest_data.get("items", {})

    # 2. Đọc metadata.json
    metadata_path = delivery_dir / "metadata.json"
    meta_by_image = {}
    if metadata_path.is_file():
        metadata_data = json.loads(metadata_path.read_text(encoding="utf-8"))
        meta_by_image = {m["image"]: m for m in metadata_data.get("items", [])}

    # 3. Đọc jobs.csv
    jobs_path = delivery_dir / "jobs.csv"
    job_guidelines = {}
    if jobs_path.is_file():
        with open(jobs_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                job_guidelines[row["job_id"]] = row.get("guideline")

    # 4. Đọc classes.txt
    classes_path = delivery_dir / "classes.txt"
    yolo_classes = {}
    if classes_path.is_file():
        for line in classes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    yolo_classes[int(parts[0])] = parts[1]

    # 5. Đọc panoptic.json
    panoptic_path = delivery_dir / "panoptic.json"
    panoptic_data = {}
    valid_categories = {}
    thing_categories = set()
    if panoptic_path.is_file():
        panoptic_data = json.loads(panoptic_path.read_text(encoding="utf-8"))
        for cat in panoptic_data.get("categories", []):
            valid_categories[cat["id"]] = cat["name"]
            if cat.get("isthing", 0) == 1:
                thing_categories.add(cat["id"])

    # ------------------ Kiểm tra mức file và detection ------------------
    scenes: dict[str, set[str]] = {}

    for name, item_info in items.items():
        # Kiểm tra scene_leak qua metadata
        meta = meta_by_image.get(name)
        if meta:
            scenes.setdefault(meta["scene_id"], set()).add(meta["split"])
            # Kiểm tra guideline_mismatch
            expected_gl = job_guidelines.get(meta.get("job_id"))
            if expected_gl and meta.get("guideline_version") != expected_gl:
                errors.append({"type": "guideline_mismatch", "target": name})

        # Kiểm tra missing_image & wrong_hash
        img_file = delivery_dir / item_info["image"]
        if not img_file.is_file():
            errors.append({"type": "missing_image", "target": name})
            continue

        if sha256_file(img_file) != item_info.get("image_sha256"):
            errors.append({"type": "wrong_hash", "target": name})

        # Kiểm tra nhãn YOLO
        label_file = delivery_dir / item_info["label"]
        if label_file.is_file():
            boxes = []
            has_invalid_class = False
            has_oob = False
            for line in label_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                c, x, y, w, h = int(float(parts[0])), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                
                # invalid_class
                if not (0 <= c < 80):
                    if not has_invalid_class:
                        errors.append({"type": "invalid_class", "target": name})
                        has_invalid_class = True
                
                # bbox_out_of_bounds (vượt ngưỡng sai số [-0.01, 1.01])
                left = x - w / 2
                right = x + w / 2
                top = y - h / 2
                bottom = y + h / 2
                if left < -0.01 or top < -0.01 or right > 1.01 or bottom > 1.01:
                    if not has_oob:
                        errors.append({"type": "bbox_out_of_bounds", "target": name})
                        has_oob = True

                boxes.append((c, x, y, w, h))

            # Kiểm tra duplicate_box: cùng class, cùng kích thước, chỉ lệch 1-2 pixel
            has_dup = False
            for i in range(len(boxes)):
                if has_dup:
                    break
                for j in range(i + 1, len(boxes)):
                    c1, x1, y1, w1, h1 = boxes[i]
                    c2, x2, y2, w2, h2 = boxes[j]
                    if c1 == c2:
                        # Kích thước gần như đồng nhất và tâm lệch rất nhỏ
                        if abs(w1 - w2) < 0.002 and abs(h1 - h2) < 0.002:
                            if abs(x1 - x2) < 0.01 and abs(y1 - y2) < 0.01:
                                errors.append({"type": "duplicate_box", "target": name})
                                has_dup = True
                                break

    # Kiểm tra scene_leak (target là scene_id)
    for scene_id, splits in scenes.items():
        if len(splits) > 1:
            errors.append({"type": "scene_leak", "target": scene_id})

    # ------------------ Kiểm tra Panoptic ------------------
    if panoptic_data:
        for ann in panoptic_data.get("annotations", []):
            img_stem = Path(ann.get("file_name", "")).stem
            segments = ann.get("segments_info", [])

            # 1. invalid_category_id
            for seg in segments:
                if seg["category_id"] not in valid_categories:
                    errors.append({"type": "invalid_category_id", "target": img_stem})
                    break

            # 2. thing_overlap: đếm số pixel thật sự của từng segment từ mask PNG
            mask_rel = f"masks/{ann['file_name']}"
            mask_file = delivery_dir / mask_rel
            if mask_file.is_file():
                try:
                    w, h, pixels = pngutil.read_rgb(mask_file)
                    pixel_counts: dict[int, int] = {}
                    for p_idx in range(0, len(pixels), 3):
                        sid = pngutil.segment_id(pixels, p_idx)
                        if sid:
                            pixel_counts[sid] = pixel_counts.get(sid, 0) + 1

                    for seg in segments:
                        sid = seg["id"]
                        area = seg.get("area", 0)
                        actual = pixel_counts.get(sid, 0)
                        diff = area - actual
                        # Nếu diện tích khai báo bị lấn chiếm đáng kể (>= 10px và >= 10% diện tích)
                        if diff >= 10 and diff / (area + 1e-6) >= 0.10:
                            errors.append({"type": "thing_overlap", "target": img_stem})
                            break
                except Exception:
                    pass

    context = {
        "manifest": items,
        "metadata": meta_by_image,
        "jobs": job_guidelines,
        "yolo_classes": yolo_classes,
        "panoptic_data": panoptic_data,
        "valid_categories": valid_categories,
        "thing_categories": thing_categories,
    }
    return errors, context


def extract_candidates(delivery_dir: Path, context: dict, rule_targets: set[str]) -> list[dict]:
    """Đối chiếu Detection ↔ Panoptic để tìm ứng viên lỗi gán nhãn cho người review."""
    candidates: list[dict] = []
    items = context["manifest"]
    yolo_classes = context["yolo_classes"]
    panoptic_data = context["panoptic_data"]
    valid_categories = context["valid_categories"]
    thing_categories = context["thing_categories"]

    if not panoptic_data:
        return candidates

    # Lấy thông tin kích thước ảnh
    img_dims = {}
    for img_info in panoptic_data.get("images", []):
        stem = Path(img_info.get("file_name", "")).stem
        img_dims[stem] = (img_info["width"], img_info["height"])

    ann_by_stem = {Path(ann["file_name"]).stem: ann for ann in panoptic_data.get("annotations", [])}

    for stem, item_info in items.items():
        # Mỗi ảnh chỉ có nhiều nhất 1 lỗi: bỏ qua ảnh đã có lỗi luật
        if stem in rule_targets:
            continue

        ann = ann_by_stem.get(stem)
        if not ann:
            continue

        W, H = img_dims.get(stem, (0, 0))
        label_file = delivery_dir / item_info["label"]
        if not label_file.is_file() or W == 0 or H == 0:
            continue

        # 1. Đọc YOLO boxes
        yolo_list = []
        for line in label_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            cid = int(float(parts[0]))
            xc, yc, w, h = map(float, parts[1:5])
            bw, bh = w * W, h * H
            xmin = (xc - w / 2) * W
            ymin = (yc - h / 2) * H
            xmax = xmin + bw
            ymax = ymin + bh
            yolo_list.append({
                "class_id": cid,
                "name": yolo_classes.get(cid, str(cid)),
                "box": (xmin, ymin, xmax, ymax),
                "norm": (xc, yc, w, h),
                "norm_area": w * h,
            })

        # 2. Đọc Panoptic segments (chỉ lấy thing, bỏ iscrowd)
        pan_list = []
        for seg in ann.get("segments_info", []):
            if seg["category_id"] in thing_categories and not seg.get("iscrowd", 0):
                bx, by, bw, bh = seg["bbox"]
                pan_list.append({
                    "id": seg["id"],
                    "cat_id": seg["category_id"],
                    "name": valid_categories.get(seg["category_id"], str(seg["category_id"])),
                    "box": (bx, by, bx + bw, by + bh),
                    "area": seg.get("area", 0),
                })

        # --- Dấu hiệu 1 & 2: class_swap / category_swap & bbox_drift ---
        found_fault_for_image = False
        matched_yolo = set()
        matched_pan = set()

        # Ma trận IoU
        pair_ious = []
        for yi, y_item in enumerate(yolo_list):
            for pi, p_item in enumerate(pan_list):
                iou = compute_iou(y_item["box"], p_item["box"])
                pair_ious.append((iou, yi, pi))

        pair_ious.sort(key=lambda x: x[0], reverse=True)

        # 1a. Kiểm tra class_swap / category_swap: trùng vị trí cao nhưng lệch tên lớp
        for iou, yi, pi in pair_ious:
            if iou >= 0.40 and yi not in matched_yolo and pi not in matched_pan:
                y_name = yolo_list[yi]["name"]
                p_name = pan_list[pi]["name"]
                if y_name != p_name:
                    candidates.append({
                        "image": stem,
                        "type": "class_swap",
                        "note": f"IoU={iou:.2f}: YOLO='{y_name}' vs Panoptic='{p_name}'. Cần mở ảnh xác định nguồn sai."
                    })
                    found_fault_for_image = True
                    break

        if found_fault_for_image:
            continue

        # 1b. Ghép các cặp cùng lớp để kiểm tra bbox_drift
        for iou, yi, pi in pair_ious:
            if yi not in matched_yolo and pi not in matched_pan:
                y_name = yolo_list[yi]["name"]
                p_name = pan_list[pi]["name"]
                if y_name == p_name and iou >= 0.15:
                    matched_yolo.add(yi)
                    matched_pan.add(pi)
                    # Nếu box kích thước đủ lớn mà IoU bị lệch đáng kể
                    if yolo_list[yi]["norm_area"] >= 0.005 and iou <= 0.65:
                        candidates.append({
                            "image": stem,
                            "type": "bbox_drift",
                            "note": f"Cùng lớp '{y_name}' nhưng IoU thấp ({iou:.2f}). Hộp detection có thể bị lệch."
                        })
                        found_fault_for_image = True
                        break

        if found_fault_for_image:
            continue

        # --- Dấu hiệu 3: instance_merge ---
        # Một segment panoptic bao phủ >= 2 box YOLO cùng lớp
        for pi, p_item in enumerate(pan_list):
            overlapping_yolo = []
            for yi, y_item in enumerate(yolo_list):
                if y_item["name"] == p_item["name"]:
                    iou = compute_iou(y_item["box"], p_item["box"])
                    if iou >= 0.20:
                        overlapping_yolo.append(yi)
            if len(overlapping_yolo) >= 2:
                candidates.append({
                    "image": stem,
                    "type": "instance_merge",
                    "note": f"Segment panoptic '{p_item['name']}' phủ đồng thời {len(overlapping_yolo)} box YOLO cùng lớp."
                })
                found_fault_for_image = True
                break

        if found_fault_for_image:
            continue

        # --- Dấu hiệu 4: missing_box ---
        # TH1: Panoptic có vật thể thing nhưng YOLO thiếu số lượng của class đó
        pan_class_counts: dict[str, int] = {}
        for p in pan_list:
            pan_class_counts[p["name"]] = pan_class_counts.get(p["name"], 0) + 1
        yolo_class_counts: dict[str, int] = {}
        for y in yolo_list:
            yolo_class_counts[y["name"]] = yolo_class_counts.get(y["name"], 0) + 1

        for cname, p_cnt in pan_class_counts.items():
            y_cnt = yolo_class_counts.get(cname, 0)
            if y_cnt < p_cnt:
                candidates.append({
                    "image": stem,
                    "type": "missing_box",
                    "note": f"Panoptic có {p_cnt} '{cname}' nhưng YOLO chỉ có {y_cnt}."
                })
                found_fault_for_image = True
                break

        if found_fault_for_image:
            continue

        # TH2: Segment panoptic không ghép được với box YOLO cùng loại nào
        for pi, p_item in enumerate(pan_list):
            if pi not in matched_pan and p_item["area"] >= 50:
                same_cls_ious = [compute_iou(y["box"], p_item["box"]) for y in yolo_list if y["name"] == p_item["name"]]
                max_iou = max(same_cls_ious, default=0.0)
                if max_iou < 0.15:
                    candidates.append({
                        "image": stem,
                        "type": "missing_box",
                        "note": f"Segment panoptic '{p_item['name']}' diện tích {p_item['area']}px không có box YOLO tương ứng."
                    })
                    break

    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Validator bắt lỗi luật & đối chiếu sinh ứng viên")
    parser.add_argument("delivery", type=Path, help="Đường dẫn thư mục delivery cần kiểm tra")
    parser.add_argument("--out", type=Path, required=True, help="Đường dẫn file errors.json đầu ra")
    parser.add_argument("--candidates", type=Path, help="Đường dẫn file candidates.json (nếu muốn sinh ứng viên)")
    args = parser.parse_args()

    delivery_dir = args.delivery
    if not delivery_dir.is_dir():
        print(f"Lỗi: {delivery_dir} không phải là thư mục hợp lệ.", file=sys.stderr)
        return 1

    print(f"[*] Đang kiểm tra lỗi luật trên {delivery_dir}...")
    rule_errors, context = validate_rules(delivery_dir)

    # Loại bỏ trùng lặp và sắp xếp
    unique_rule_errors = sorted(
        { (e["type"], e["target"]): e for e in rule_errors }.values(),
        key=lambda x: (x["type"], x["target"])
    )

    # Ghi lỗi luật ra file --out
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_content = {"errors": unique_rule_errors}
    args.out.write_text(json.dumps(out_content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[+] Đã phát hiện {len(unique_rule_errors)} lỗi luật -> Ghi tại: {args.out}")

    # Sinh ứng viên nếu được yêu cầu
    if args.candidates:
        rule_targets = {e["target"] for e in unique_rule_errors}
        print("[*] Đang đối chiếu Detection ↔ Panoptic để trích xuất ứng viên...")
        candidates = extract_candidates(delivery_dir, context, rule_targets)
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        cand_content = {"candidates": candidates}
        args.candidates.write_text(json.dumps(cand_content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[+] Đã sinh {len(candidates)} ứng viên cần review mắt -> Ghi tại: {args.candidates}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
