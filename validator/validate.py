#!/usr/bin/env python3
"""Validator cho gói bàn giao dataset Day 10 Lab (VinUniversity AI20K).

Sử dụng thư viện chuẩn của Python (3.10+). Không đọc _private, không dùng mạng.
Giao diện:
  python validator/validate.py <delivery_dir> --out <errors.json> [--candidates <candidates.json>]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

# Cho phép import pngutil từ thư mục scripts/ theo quy định của đề bài
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
import pngutil  # noqa: E402


def compute_sha256(file_path: Path) -> str:
    """Tính mã băm SHA-256 từ byte nhị phân của tệp."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


# ==============================================================================
# NHÓM 1: LUẬT DETECTION & TỆP (THÀNH VIÊN 1 PHỤ TRÁCH)
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
            parts = line.strip().split()
            if not parts:
                continue

            try:
                cls_id = int(parts[0])
            except ValueError:
                has_invalid_class = True
                continue

            # 3. invalid_class: class_id nằm ngoài khoảng hợp lệ [0, 79] của COCO 80 lớp
            if cls_id < 0 or cls_id >= 80:
                has_invalid_class = True

            x, y, w, h = map(float, parts[1:5])

            # 4. bbox_out_of_bounds: box vượt ra ngoài khung ảnh (với dung sai nhỏ)
            x1, y1 = x - w / 2.0, y - h / 2.0
            x2, y2 = x + w / 2.0, y + h / 2.0
            if x1 < -1e-3 or y1 < -1e-3 or x2 > 1.001 or y2 > 1.001 or w > 1.001 or h > 1.001:
                has_oob = True

            boxes.append((cls_id, x, y, w, h))

        if has_invalid_class:
            errors.append({"type": "invalid_class", "target": stem})
        if has_oob:
            errors.append({"type": "bbox_out_of_bounds", "target": stem})

        # 5. duplicate_box: cùng class_id, cùng kích thước w, h (sai số <= 1e-4) và tâm chỉ lệch 1-2 pixel
        has_dup = False
        n_boxes = len(boxes)
        for i in range(n_boxes):
            for j in range(i + 1, n_boxes):
                c1, x1, y1, w1, h1 = boxes[i]
                c2, x2, y2, w2, h2 = boxes[j]
                if c1 == c2 and abs(w1 - w2) < 1e-4 and abs(h1 - h2) < 1e-4:
                    # Kiểm tra độ lệch tâm: trong COCO độ phân giải ~500-640px, 2-3px ứng với normalized offset ~0.006-0.008
                    if abs(x1 - x2) <= 0.008 and abs(y1 - y2) <= 0.008:
                        has_dup = True
                        break
            if has_dup:
                break

        if has_dup:
            errors.append({"type": "duplicate_box", "target": stem})

    return errors


# ==============================================================================
# NHÓM 2: LUẬT METADATA & PANOPTIC (THÀNH VIÊN 2 PHỤ TRÁCH)
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
            errors.append({"type": "guideline_mismatch", "target": it["image"]})

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


# ==============================================================================
# NHÓM 3: ĐỐI CHIẾU CHÉO BBOX ↔ MASK SINH ỨNG VIÊN (CANDIDATES) CHO PHA 2
# ==============================================================================
def find_candidates(delivery_dir: Path, manifest: dict, panoptic: dict) -> list[dict]:
    """Đối chiếu chéo Detection ↔ Panoptic để trích xuất ứng viên cho Pha 2 xem mắt."""
    # Nạp danh mục và lớp
    cat_by_id = {c["id"]: c for c in panoptic.get("categories", [])}
    cat_name_by_id = {c["id"]: c["name"] for c in panoptic.get("categories", [])}
    cat_id_by_name = {c["name"]: c["id"] for c in panoptic.get("categories", [])}
    things = {c["id"] for c in panoptic.get("categories", []) if c.get("isthing")}

    classes_path = delivery_dir / "classes.txt"
    cls_to_name: dict[int, str] = {}
    if classes_path.is_file():
        for line in classes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                cid, name = line.split(maxsplit=1)
                cls_to_name[int(cid)] = name.strip()

    images_meta = {im["id"]: im for im in panoptic.get("images", [])}
    pan_by_stem = {Path(a["file_name"]).stem: a for a in panoptic.get("annotations", [])}

    candidates = []

    for stem, it in manifest.get("items", {}).items():
        ann = pan_by_stem.get(stem)
        if not ann:
            continue
        im_meta = images_meta.get(ann["image_id"])
        if not im_meta:
            continue

        w_img, h_img = im_meta["width"], im_meta["height"]
        lbl_path = delivery_dir / it["label"]
        boxes = []
        if lbl_path.is_file():
            for line in lbl_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    x, y, w, h = map(float, parts[1:5])
                    # Chuyển về tọa độ pixel [x_min, y_min, w_px, h_px]
                    px_w, px_h = w * w_img, h * h_img
                    px_x = (x - w / 2.0) * w_img
                    px_y = (y - h / 2.0) * h_img
                    boxes.append({
                        "cls_id": cls_id,
                        "cls_name": cls_to_name.get(cls_id, ""),
                        "bbox": [px_x, px_y, px_w, px_h],
                        "area_frac": w * h,
                    })

        segs = [s for s in ann.get("segments_info", []) if s.get("category_id") in things and not s.get("iscrowd")]

        # Khớp theo IoU giữa box detection và segment bbox
        matched_box = set()
        matched_seg = set()

        for b_idx, b in enumerate(boxes):
            bx, by, bw, bh = b["bbox"]
            best_iou = 0.0
            best_s_idx = -1
            for s_idx, s in enumerate(segs):
                sx, sy, sw, sh = s["bbox"]
                ix1 = max(bx, sx)
                iy1 = max(by, sy)
                ix2 = min(bx + bw, sx + sw)
                iy2 = min(by + bh, sy + sh)
                iw = max(0.0, ix2 - ix1)
                ih = max(0.0, iy2 - iy1)
                inter = iw * ih
                union = bw * bh + sw * sh - inter
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                    best_s_idx = s_idx

            if best_s_idx >= 0 and best_iou >= 0.25:
                s = segs[best_s_idx]
                s_name = cat_name_by_id.get(s["category_id"], "")
                matched_box.add(b_idx)
                matched_seg.add(best_s_idx)

                # Trường hợp lệch tên lớp: nghi vấn class_swap hoặc category_swap
                if b["cls_name"] != s_name:
                    candidates.append({
                        "image": stem,
                        "type": "class_swap",
                        "note": f"Bất đồng lớp: detection={b['cls_name']}, panoptic={s_name} (IoU={best_iou:.2f})",
                        "suspect_type": "class_swap_or_category_swap",
                    })

                # Trường hợp IoU trung bình (0.3 - 0.65) nhưng cùng lớp: nghi vấn bbox_drift
                elif best_iou < 0.60 and b["area_frac"] >= 0.008:
                    candidates.append({
                        "image": stem,
                        "type": "bbox_drift",
                        "note": f"Khung lệch tâm hoặc sai kích thước so với mặt nạ: lớp={b['cls_name']} (IoU={best_iou:.2f})",
                    })

        # Trường hợp segment lớn không có box detection: nghi vấn missing_box
        for s_idx, s in enumerate(segs):
            if s_idx not in matched_seg:
                area_frac = s.get("area", 0) / (w_img * h_img)
                if area_frac >= 0.01:
                    s_name = cat_name_by_id.get(s["category_id"], "")
                    candidates.append({
                        "image": stem,
                        "type": "missing_box",
                        "note": f"Phát hiện mặt nạ {s_name} có diện tích lớn ({area_frac*100:.1f}%) nhưng không có box detection",
                    })

    # Loại bỏ ứng viên trùng trên cùng một ảnh và loại lỗi
    unique_candidates = []
    seen = set()
    for c in candidates:
        key = (c["image"], c["type"])
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)

    return unique_candidates


# ==============================================================================
# HÀM ĐIỀU PHỐI CHÍNH (MAIN ENTRYPOINT)
# ==============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="Validator cho gói bàn giao dataset Day 10 Lab")
    parser.add_argument("delivery", type=str, help="Đường dẫn tới thư mục delivery")
    parser.add_argument("--out", type=str, required=True, help="Đường dẫn file errors.json xuất ra")
    parser.add_argument("--candidates", type=str, help="Đường dẫn file candidates.json xuất ra (tùy chọn)")
    args = parser.parse_args()

    delivery_dir = Path(args.delivery).resolve()
    if not delivery_dir.is_dir():
        print(f"Lỗi: Thư mục không tồn tại: {delivery_dir}", file=sys.stderr)
        return 1

    # Nạp các tệp siêu dữ liệu chính
    manifest_path = delivery_dir / "manifest.json"
    metadata_path = delivery_dir / "metadata.json"
    panoptic_path = delivery_dir / "panoptic.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    panoptic = json.loads(panoptic_path.read_text(encoding="utf-8")) if panoptic_path.is_file() else {}

    all_errors: list[dict] = []

    # 1. Quét lỗi luật Detection & File (Thành viên 1)
    all_errors.extend(check_file_and_hash_rules(delivery_dir, manifest))
    all_errors.extend(check_detection_rules(delivery_dir, manifest))

    # 2. Quét lỗi luật Metadata & Panoptic (Thành viên 2)
    all_errors.extend(check_metadata_rules(delivery_dir, metadata))
    all_errors.extend(check_panoptic_rules(delivery_dir, panoptic))

    # Khử trùng lặp lỗi theo (type, target) và sắp xếp chuẩn
    unique_pairs = sorted({(e["type"], e["target"]) for e in all_errors})
    formatted_errors = [{"type": t, "target": g} for t, g in unique_pairs]

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"errors": formatted_errors}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ Đã quét xong 9 lỗi luật: Tìm thấy {len(formatted_errors)} lỗi -> {out_path}")

    # 3. Trích xuất ứng viên đối chiếu chéo (nếu có yêu cầu --candidates)
    if args.candidates:
        cands = find_candidates(delivery_dir, manifest, panoptic)
        cand_path = Path(args.candidates).resolve()
        cand_path.parent.mkdir(parents=True, exist_ok=True)
        cand_path.write_text(json.dumps({"candidates": cands}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"🔍 Đã sinh danh sách {len(cands)} ứng viên đối chiếu chéo -> {cand_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
