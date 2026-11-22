#!/usr/bin/env python3
"""Dựng lô bàn giao v2 (Pha 4) từ delivery v1 + errors.json của nhóm. Không sửa gì trong delivery/.

  py -X utf8 tools/build_v2.py --run runs/r<seed>
  py -X utf8 tools/build_v2.py --run runs/r<seed> --corrupt 000000001234   # ảnh wrong_hash đã mở xem và thấy hỏng

Ghi runs/r<seed>/handover/<release_id>_v2/ gồm 7 phần:
  images/, labels/, rework_queue.csv, manifest.csv, label_summary.csv, truyvet.csv, README.txt
Sau đó chạy:
  py scripts/pack_release.py runs/r<seed>/handover/<release_id>_v2
  py scripts/check_handover.py --run runs/r<seed>

Cách xử lý từng loại lỗi (GUIDE Pha 4):
  - Lỗi nhãn detection hoặc thiếu file -> rework_queue.csv, ảnh rời v2.
  - Lỗi chỉ ở panoptic -> ảnh ở lại v2, ghi vào Ghi chú README để báo team panoptic.
  - wrong_hash -> ảnh còn nguyên thì giữ, manifest.csv ghi hash thật; ảnh hỏng (--corrupt) thì vào rework.
  - guideline_mismatch -> truyvet.csv lấy guideline theo job.
  - scene_leak -> cả cảnh về split của số đông ảnh trong cảnh.
Chỉ thư viện chuẩn.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

# Lỗi làm sai nhãn detection hoặc thiếu file: ảnh phải gán lại, rời khỏi v2.
DET_REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box",
              "class_swap", "bbox_drift", "missing_box"}
# Lỗi chỉ ở panoptic: nhãn detection vẫn đúng, ảnh ở lại v2.
PANOPTIC_ONLY = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}
# Sửa được ngay trong v2.
FIX_IN_V2 = {"wrong_hash", "guideline_mismatch", "scene_leak"}
THRESHOLD = 0.02  # Day 7: trên 2% ảnh lỗi thì không Release

ACTION = {
    "missing_image": "giao lại file ảnh còn thiếu, kiểm lại nhãn",
    "invalid_class": "sửa class_id ngoài 0-79 về đúng lớp",
    "bbox_out_of_bounds": "vẽ lại box tràn ra ngoài ảnh",
    "duplicate_box": "xoá box lặp cùng lớp lệch 1-2 px",
    "class_swap": "sửa lớp box bị gán nhầm lớp dễ nhầm",
    "bbox_drift": "vẽ lại box bị lệch khỏi vật",
    "missing_box": "thêm box cho vật còn thiếu",
    "wrong_hash": "ảnh hỏng: giao lại file ảnh gốc, tính lại hash",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jpeg_intact(path: Path) -> bool:
    """Kiểm thô: đúng đầu/đuôi JPEG. Vẫn phải mở ảnh bằng mắt trước khi kết luận."""
    data = path.read_bytes()
    return len(data) > 4 and data[:2] == b"\xff\xd8" and data.rstrip(b"\x00")[-2:] == b"\xff\xd9"


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dựng lô bàn giao v2")
    ap.add_argument("--run", required=True, help="runs/r<seed>")
    ap.add_argument("--errors", help="mặc định <run>/errors.json")
    ap.add_argument("--corrupt", nargs="*", default=[],
                    help="ảnh wrong_hash đã mở xem và thấy hỏng: đưa vào rework thay vì giữ lại")
    args = ap.parse_args()

    run = Path(args.run)
    d = run / "delivery"
    err_path = Path(args.errors) if args.errors else run / "errors.json"
    if not err_path.is_file():
        raise SystemExit(f"Chưa có {err_path}. Đợi nhóm chốt errors.json (Pha 2) rồi chạy lại.")

    rid = json.loads((d / "release.json").read_text(encoding="utf-8"))["release_id"]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = {m["image"]: m for m in json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]}
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {row["job_id"]: row for row in csv.DictReader(f)}
    names80 = [ln.split(" ", 1)[1].strip() for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    errors = json.loads(err_path.read_text(encoding="utf-8"))["errors"]

    # ---------------------------------------------------------------- phân loại lỗi
    by_image: dict[str, str] = {}      # ảnh -> loại lỗi
    leak_scenes: list[str] = []
    unknown = []
    for e in errors:
        t, target = e["type"], e["target"]
        if t == "scene_leak":
            leak_scenes.append(target)
        elif target in man:
            by_image[target] = t
        else:
            unknown.append((t, target))
    if unknown:
        print(f"CẢNH BÁO: errors.json có target không nằm trong lô: {unknown[:5]}", file=sys.stderr)

    corrupt = set(args.corrupt)
    bad_corrupt = corrupt - {s for s, t in by_image.items() if t == "wrong_hash"}
    if bad_corrupt:
        raise SystemExit(f"--corrupt chỉ dành cho ảnh có wrong_hash trong errors.json: {sorted(bad_corrupt)}")

    rework, panoptic_keep, hash_fixed, guide_fixed = [], [], [], []
    for stem, t in sorted(by_image.items()):
        if t in DET_REWORK or (t == "wrong_hash" and stem in corrupt):
            rework.append((stem, t))
        elif t in PANOPTIC_ONLY:
            panoptic_keep.append((stem, t))
        elif t == "wrong_hash":
            img = d / man[stem]["image"]
            if not jpeg_intact(img):
                print(f"CẢNH BÁO: {stem} (wrong_hash) không có đầu/đuôi JPEG chuẩn. Mở ảnh xem; "
                      f"nếu hỏng thì chạy lại với --corrupt {stem}", file=sys.stderr)
            hash_fixed.append(stem)
        elif t == "guideline_mismatch":
            guide_fixed.append(stem)
    rework_set = {s for s, _ in rework}

    # ---------------------------------------------------------------- split theo cảnh
    scene_members: dict[str, list[str]] = {}
    for stem, m in meta.items():
        scene_members.setdefault(m["scene_id"], []).append(stem)
    scene_split: dict[str, str] = {}
    leak_fix = []
    for sc, members in scene_members.items():
        cnt = Counter(meta[s]["split"] for s in members)
        top = cnt.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            print(f"CẢNH BÁO: cảnh {sc} chia đều train/val {dict(cnt)}; tạm chọn 'train', hãy kiểm lại.", file=sys.stderr)
            split = "train"
        else:
            split = top[0][0]
        scene_split[sc] = split
        if len(cnt) > 1:
            moved = sorted(s for s in members if meta[s]["split"] != split)
            leak_fix.append((sc, split, moved))
    missed_leaks = sorted({sc for sc, _, _ in leak_fix} - set(leak_scenes))
    if missed_leaks:
        print(f"CẢNH BÁO: cảnh rò train/val chưa có trong errors.json: {missed_leaks} (vẫn sửa split trong v2)", file=sys.stderr)

    # ---------------------------------------------------------------- dựng thư mục v2
    v2 = run / "handover" / f"{rid}_v2"
    if v2.exists():
        shutil.rmtree(v2)
    (v2 / "images").mkdir(parents=True)
    (v2 / "labels").mkdir()

    kept = []
    for stem in sorted(man):
        if stem in rework_set:
            continue
        img, lab = d / man[stem]["image"], d / man[stem]["label"]
        if not img.is_file():
            print(f"CẢNH BÁO: {stem} thiếu file ảnh nhưng errors.json không ghi missing_image; bỏ khỏi v2.", file=sys.stderr)
            continue
        shutil.copyfile(img, v2 / "images" / img.name)   # chép nguyên bytes, không sửa
        shutil.copyfile(lab, v2 / "labels" / lab.name)
        kept.append(stem)

    # rework_queue.csv: giao đúng người theo jobs.csv
    rq_rows = []
    for stem, t in rework:
        job = jobs[meta[stem]["job_id"]]
        rq_rows.append([stem, t, job["annotator"], job["reviewer"], ACTION.get(t, "gán lại nhãn detection")])
    write_csv(v2 / "rework_queue.csv", ["image", "type", "annotator", "reviewer", "action"], rq_rows)

    # manifest.csv: sha256 thật của mọi file trong images/ và labels/
    files = sorted(p for sub in ("images", "labels") for p in (v2 / sub).iterdir() if p.is_file())
    write_csv(v2 / "manifest.csv", ["file", "sha256"], [[p.relative_to(v2).as_posix(), sha(p)] for p in files])

    # label_summary.csv
    counts: Counter = Counter()
    for stem in kept:
        for ln in (v2 / "labels" / f"{stem}.txt").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                c = int(float(ln.split()[0]))
                counts[names80[c] if 0 <= c < len(names80) else str(c)] += 1
    n_labels = sum(counts.values())
    order = {n: i for i, n in enumerate(names80)}
    summ = [[n, counts[n]] for n in sorted(counts, key=lambda n: order.get(n, 999))]
    write_csv(v2 / "label_summary.csv", ["class", "count"], summ + [["TOTAL", n_labels]])

    # truyvet.csv: guideline theo job, split theo cảnh
    tv_rows = []
    for stem in kept:
        m = meta[stem]
        job = jobs[m["job_id"]]
        tv_rows.append([stem, m["scene_id"], scene_split[m["scene_id"]], m["job_id"],
                        job["annotator"], job["reviewer"], job["guideline"]])
    write_csv(v2 / "truyvet.csv", ["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"], tv_rows)

    # README.txt
    err_units = {e["target"] for e in errors}  # mỗi ảnh / mỗi cảnh (scene_leak) tính một lần
    total = len(man)
    rate = len(err_units) / total
    pct = f"{rate * 100:.1f}".replace(".", ",")
    v1_dec = "Hold" if rate > THRESHOLD else "Release"
    guide_by_job = {}
    for j in sorted(jobs):
        guide_by_job.setdefault(jobs[j]["guideline"], []).append(j)
    guide_str = ", ".join(f"{g} ({js[0]}-{js[-1]})" if len(js) > 1 else f"{g} ({js[0]})" for g, js in sorted(guide_by_job.items()))

    owners: dict[tuple, list[str]] = {}
    for stem, t, a, r, _ in rq_rows:
        owners.setdefault((a, r), []).append(stem)
    notes = []
    if hash_fixed:
        notes.append(f"wrong_hash {len(hash_fixed)} ảnh ({', '.join(hash_fixed)}): đã mở ảnh kiểm, ảnh còn nguyên nên chỉ manifest v1 sai; manifest.csv v2 ghi sha256 tính lại từ file")
    if corrupt:
        notes.append(f"wrong_hash ảnh hỏng {len(corrupt)} ảnh ({', '.join(sorted(corrupt))}): đưa vào rework_queue")
    if guide_fixed:
        notes.append(f"guideline_mismatch {len(guide_fixed)} ảnh ({', '.join(guide_fixed)}): truyvet.csv lấy guideline theo job trong jobs.csv")
    if leak_fix:
        notes.append("scene_leak " + "; ".join(f"{sc}: ảnh {', '.join(mv)} chuyển về {sp} cùng cả cảnh" for sc, sp, mv in leak_fix))
    if rq_rows:
        notes.append(f"rework {len(rq_rows)} ảnh lỗi nhãn detection/thiếu file rời v2, giao lại: "
                     + "; ".join(f"{a}/{r}: {', '.join(s)}" for (a, r), s in sorted(owners.items())))
    if panoptic_keep:
        notes.append(f"lỗi panoptic {len(panoptic_keep)} ảnh ở lại v2 vì nhãn detection vẫn đúng, báo team panoptic: "
                     + ", ".join(f"{s} ({t})" for s, t in panoptic_keep))
    notes.append("nhãn detection trong v2 giữ nguyên bytes như v1, không sửa tay; v1 không bị ghi đè")

    v2_parts = []
    if rq_rows:
        v2_parts.append(f"đã tách {len(rq_rows)} ảnh lỗi detection sang rework")
    v2_parts.append("đã sửa hash/guideline/split trong hồ sơ")
    if panoptic_keep:
        v2_parts.append(f"còn {len(panoptic_keep)} ảnh lỗi panoptic không ảnh hưởng nhãn detection")
    readme = "\n".join([
        f"Release: {rid}_v2",
        f"Parent: {rid}",
        f"Số ảnh: {len(kept)}",
        f"Số nhãn: {n_labels}",
        f"Guideline: {guide_str}",
        f"QC v1: {len(err_units)}/{total} = {pct}%",
        f"Kết luận v1: {v1_dec} — {len(err_units)}/{total} = {pct}% ảnh lỗi "
        + ("vượt ngưỡng 2%, không Release; run R-021 đã train trên v1 phải xem lại hoặc train lại" if v1_dec == "Hold" else "không vượt ngưỡng 2%"),
        f"Kết luận v2: Release — {'; '.join(v2_parts)}",
        f"Ghi chú: {' | '.join(notes)}",
        "",
    ])
    (v2 / "README.txt").write_text(readme, encoding="utf-8")

    print(f"Đã dựng {v2}")
    print(f"  v2: {len(kept)} ảnh, {n_labels} nhãn | rework: {len(rq_rows)} | panoptic ở lại: {len(panoptic_keep)}")
    print(f"  QC v1: {len(err_units)}/{total} = {pct}% => {v1_dec}")
    if hash_fixed:
        print(f"  NHỚ mở xem các ảnh wrong_hash trước khi chốt: {', '.join(hash_fixed)}")
    print(f"Tiếp theo: py scripts/pack_release.py {v2.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
