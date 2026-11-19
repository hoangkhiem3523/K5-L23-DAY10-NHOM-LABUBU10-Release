#!/usr/bin/env python3
"""Validator cho Day 10 Lab - Bắt lỗi luật và đối chiếu sinh ứng viên.

Phân công nhóm:
  - TV1: Rule bắt lỗi file, hash SHA-256, và định dạng Detection (YOLO).
  - TV2: Rule bắt lỗi Metadata (scene_leak, guideline_mismatch) và Panoptic (invalid_category_id, thing_overlap).
  - TV3: Trích xuất ứng viên nghi vấn lỗi gán nhãn qua đối chiếu chéo Detection <-> Panoptic.

Giao diện cố định:
    python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]
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


def compute_sha256(path: Path) -> str:
    """Tính mã băm sha256 của file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_file(path: Path) -> str:
    """Tính mã băm sha256 của file (alias tương thích)."""
    return compute_sha256(path)


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


# ==============================================================================
# TV1: KIỂM TRA LỖI FILE, HASH VÀ DETECTION
# ==============================================================================

def check_file_and_hash_rules(delivery_dir: Path, manifest: dict) -> list[dict]:
    """Kiểm tra missing_image và wrong_hash dựa trên manifest.json."""
    errors = []
    items = manifest.get("items", {})

    for stem, it in items.items():
        img_path = delivery_dir / it["image"]
        lbl_path = delivery_dir / it["label"]
        msk_path = delivery_dir / it["mask"]

        # 1. missing_image: manifest có khai báo nhưng không có file ảnh trên đĩa
        if not img_path.is_file():
            errors.append({"type": "missing_image", "target": stem})
            continue

        # 2. wrong_hash: mã băm SHA-256 trong manifest không khớp với byte thực tế
        if compute_sha256(img_path) != it.get("image_sha256"):
            errors.append({"type": "wrong_hash", "target": stem})
            continue

        if lbl_path.is_file() and compute_sha256(lbl_path) != it.get("label_sha256"):
            errors.append({"type": "wrong_hash", "target": stem})
            continue

        if msk_path.is_file() and compute_sha256(msk_path) != it.get("mask_sha256"):
            errors.append({"type": "wrong_hash", "target": stem})
            continue

    return errors


def check_detection_rules(delivery_dir: Path, manifest: dict) -> list[dict]:
    """Kiểm tra invalid_class, bbox_out_of_bounds, duplicate_box."""
    errors = []
    items = manifest.get("items", {})

    for stem, it in items.items():
        lbl_path = delivery_dir / it["label"]
        if not lbl_path.is_file():
            continue

        boxes = []
        has_invalid_class = False
        has_oob = False

        for line in lbl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            cls_id = int(float(parts[0]))
            xc, yc, w, h = map(float, parts[1:5])

            # 3. invalid_class: class_id nằm ngoài [0..79]
            if not (0 <= cls_id < 80):
                if not has_invalid_class:
                    errors.append({"type": "invalid_class", "target": stem})
                    has_invalid_class = True

            # 4. bbox_out_of_bounds: tọa độ vượt [0, 1] với dung sai 0.01 (tức < -0.01 hoặc > 1.01)
            left = xc - w / 2
            right = xc + w / 2
            top = yc - h / 2
            bottom = yc + h / 2
            if left < -0.01 or top < -0.01 or right > 1.01 or bottom > 1.01:
                if not has_oob:
                    errors.append({"type": "bbox_out_of_bounds", "target": stem})
                    has_oob = True

            boxes.append((cls_id, xc, yc, w, h))

        # 5. duplicate_box: cùng class, tâm và kích thước lệch <= 1-2 pixel (< 0.005)
        has_dup = False
        for i in range(len(boxes)):
            if has_dup:
                break
            for j in range(i + 1, len(boxes)):
                c1, x1, y1, w1, h1 = boxes[i]
                c2, x2, y2, w2, h2 = boxes[j]
                if c1 == c2:
                    if abs(w1 - w2) < 0.002 and abs(h1 - h2) < 0.002:
                        if abs(x1 - x2) < 0.01 and abs(y1 - y2) < 0.01:
                            errors.append({"type": "duplicate_box", "target": stem})
                            has_dup = True
                            break

    return errors


# ==============================================================================
# TV2: KIỂM TRA LỖI METADATA VÀ PANOPTIC
# ==============================================================================

def check_metadata_rules(delivery_dir: Path, metadata: dict) -> list[dict]:
    """Kiểm tra scene_leak và guideline_mismatch."""
    errors = []

    # Đọc quy định guideline chuẩn của từng Job trong jobs.csv
    jobs_csv_path = delivery_dir / "jobs.csv"
    job_guidelines = {}
    if jobs_csv_path.is_file():
        with open(jobs_csv_path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                job_guidelines[row["job_id"].strip()] = row["guideline"].strip()

    items = metadata.get("items", [])

    # 6. scene_leak: một cảnh (scene_id) có ảnh nằm ở cả train và val (target là scene_id)
    scene_splits: dict[str, set[str]] = {}
    for it in items:
        sid = it.get("scene_id")
        split = it.get("split")
        if sid and split:
            scene_splits.setdefault(sid, set()).add(split)

    for sid, splits in scene_splits.items():
        if len(splits) > 1:
            errors.append({"type": "scene_leak", "target": sid})

    # 7. guideline_mismatch: guideline của ảnh khác guideline được quy định tại Job của nó
    for it in items:
        job_id = it.get("job_id")
        img_guideline = it.get("guideline_version")
        expected_guideline = job_guidelines.get(job_id)
        if expected_guideline and img_guideline != expected_guideline:
            errors.append({"type": "guideline_mismatch", "target": it.get("image")})

    return errors


def check_panoptic_rules(delivery_dir: Path, panoptic: dict) -> list[dict]:
    """Kiểm tra invalid_category_id và thing_overlap."""
    errors = []
    valid_cat_ids = {c["id"] for c in panoptic.get("categories", [])}
    thing_cat_ids = {c["id"] for c in panoptic.get("categories", []) if c.get("isthing")}

    for ann in panoptic.get("annotations", []):
        stem = Path(ann.get("file_name", "")).stem
        has_invalid_cat = False

        # 8. invalid_category_id: category_id trong segments_info không nằm trong categories
        for s in ann.get("segments_info", []):
            if s.get("category_id") not in valid_cat_ids:
                has_invalid_cat = True
                break

        if has_invalid_cat:
            errors.append({"type": "invalid_category_id", "target": stem})

        # 9. thing_overlap: diện tích khai báo area lớn hơn số pixel thực tế của segment trong mask PNG
        mask_path = delivery_dir / "masks" / ann.get("file_name", "")
        if not mask_path.is_file():
            continue

        try:
            w, h, pixels = pngutil.read_rgb(mask_path)
            counts: dict[int, int] = {}
            for i in range(0, len(pixels), 3):
                sid = pixels[i] + pixels[i + 1] * 256 + pixels[i + 2] * 65536
                if sid != 0:
                    counts[sid] = counts.get(sid, 0) + 1

            for s in ann.get("segments_info", []):
                if s.get("category_id") in thing_cat_ids and not s.get("iscrowd"):
                    actual_pixels = counts.get(s["id"], 0)
                    if actual_pixels < s.get("area", 0):
                        errors.append({"type": "thing_overlap", "target": stem})
                        break
        except (ValueError, OSError, RuntimeError) as exc:
            raise ValueError(
                f"Cannot read panoptic mask '{mask_path}': {exc}"
            ) from exc

    return errors


def validate_rules(delivery_dir: Path) -> tuple[list[dict], dict]:
    """Tổng hợp kiểm tra toàn bộ 9 lỗi luật và trả về context dữ liệu."""
    manifest_path = delivery_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy manifest.json tại {manifest_path}")
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

    metadata_path = delivery_dir / "metadata.json"
    metadata_data = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}

    panoptic_path = delivery_dir / "panoptic.json"
    panoptic_data = json.loads(panoptic_path.read_text(encoding="utf-8")) if panoptic_path.is_file() else {}

    classes_path = delivery_dir / "classes.txt"
    yolo_classes = {}
    if classes_path.is_file():
        for line in classes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    yolo_classes[int(parts[0])] = parts[1]

    errors: list[dict] = []
    errors.extend(check_file_and_hash_rules(delivery_dir, manifest_data))
    errors.extend(check_detection_rules(delivery_dir, manifest_data))
    errors.extend(check_metadata_rules(delivery_dir, metadata_data))
    errors.extend(check_panoptic_rules(delivery_dir, panoptic_data))

    valid_categories = {c["id"]: c["name"] for c in panoptic_data.get("categories", [])}
    thing_categories = {c["id"] for c in panoptic_data.get("categories", []) if c.get("isthing", 0) == 1}

    context = {
        "manifest": manifest_data.get("items", {}),
        "metadata": {m["image"]: m for m in metadata_data.get("items", [])},
        "yolo_classes": yolo_classes,
        "panoptic_data": panoptic_data,
        "valid_categories": valid_categories,
        "thing_categories": thing_categories,
    }
    return errors, context


# ==============================================================================
# TV3: ĐỐI CHIẾU CHÉO DETECTION <-> PANOPTIC TRÍCH XUẤT ỨNG VIÊN LỖI GÁN NHÃN
# ==============================================================================

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


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

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

    unique_rule_errors = sorted(
        { (e["type"], e["target"]): e for e in rule_errors }.values(),
        key=lambda x: (x["type"], x["target"])
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_content = {"errors": unique_rule_errors}
    args.out.write_text(json.dumps(out_content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[+] Đã phát hiện {len(unique_rule_errors)} lỗi luật -> Ghi tại: {args.out}")

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
