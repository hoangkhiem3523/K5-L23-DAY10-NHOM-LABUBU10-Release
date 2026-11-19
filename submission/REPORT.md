# Báo cáo Nhóm — Nhóm LABUBU10 (Day 10 Lab)

- **Mã nhóm:** LABUBU10 (NHOM LABUBU10)
- **Seed luyện tập:** 10007 (Bộ bàn giao v1 `lab250_634019b57111`, v2 `lab250_634019b57111_v2`)
- **Đề ẩn lựa chọn:** Đề 10 (`de_an_10` / `de_an.zip`, Release ID: `lab250_278031cc6eb2`)
- **Repo GitHub:** https://github.com/hoangkhiem3523/K5-L23-DAY10-NHOM-LABUBU10-Release
- **Nhánh chính:** `Tny`

---

## Danh sách Thành viên & Phân công (Mô hình 7 Người)

| STT | Họ và tên | MSHV | Vai trò chuyên trách & Nhiệm vụ chính |
|:---:|---|:---:|---|
| 01 | **Hoàng Sỹ Khiêm** | **2A202603244** | **Thành viên 1 — Trưởng nhóm & Detection Rules Lead:** Viết CLI `validator/validate.py`, bắt 5 lỗi luật detection (`missing_image`, `wrong_hash`, `invalid_class`, `bbox_out_of_bounds`, `duplicate_box`). Review ảnh 0001–0035. |
| 02 | **Phan Đình Giáp** | **2A202603252** | **Thành viên 2 — Panoptic & Metadata Rules Lead:** Đọc PNG qua `pngutil.py`, bắt `invalid_category_id`, `thing_overlap`, `scene_leak` và `guideline_mismatch`. Review ảnh 0036–0070. |
| 03 | **Nguyễn Thảo Linh** | **2A202603253** | **Thành viên 3 — Cross-check & Candidates Engine Lead:** Thuật toán đối chiếu Bbox ↔ Mask, tính IoU, mapping 80 lớp, xuất `candidates.json` cho 5 lỗi ngữ nghĩa. Review ảnh 0071–0105. |
| 04 | **Phạm Việt Hoàng** | **2A202603254** | **Thành viên 4 — QC Review Lead:** Quản trị `review_log.csv`, kiểm tra trực quan ảnh, thẩm định 100% ghi chú &ge; 20 ký tự, hợp nhất ra `errors.json`. Review ảnh 0106–0145. |
| 05 | **Mai Văn Phong** | **2A202603256** | **Thành viên 5 — Handover v2 & Rework Lead:** Đóng gói thư mục v2 đạt 17/17 tiêu chí `check_handover.py`, lập `rework_queue.csv`, `manifest.csv`, `label_summary.csv`, `README.txt`. Review ảnh 0146–0180. |
| 06 | **Nguyễn Văn Hùng** | **2A202603295** | **Thành viên 6 — Lineage & Audit Trail Lead:** Tính tỷ lệ lỗi v1 (vượt 2% &rarr; HOLD), ghi nhật ký sự kiện `lineage.jsonl`, phân tích tác động model `R-021`, lập `trace.json`. Review ảnh 0181–0215. |
| 07 | **Hoàng Thuận Thiện** | **2A202603270** | **Thành viên 7 — Security & Submission Lead:** Viết `security.md` (xử lý USB, vi phạm bản quyền, ảnh PII khuôn mặt &rarr; HOLD + báo phụ trách), hoàn thiện `REPORT.md`, `prompts.md`, phụ trách Submission Gate. Review ảnh 0216–0250. |

---

## 1. Số liệu luyện tập (Seed 10007)
- **Kết quả đo lường tự động trên seed 10007:**
  - Nhóm lỗi luật (`rule_detectable`): Precision = 1.0, Recall = 1.0, **F1 = 1.0** (Phát hiện đầy đủ 13/13 lỗi luật, 0 FP, 0 FN).
  - Nhóm lỗi gán nhãn (`cross_check_review`): Precision = 1.0, Recall = 1.0, **F1 = 1.0** (Sau khi xem ảnh và xác nhận 10/10 lỗi).
  - Điểm tổng thể (`overall`): Precision = 1.0, Recall = 1.0, **F1 = 1.0** (Bắt chính xác 23/23 lỗi).
- **Bộ bàn giao v2 (`lab250_634019b57111_v2`):**
  - Chạy `python scripts/check_handover.py --run runs/r10007`: **17/17 PASS** hoàn hảo.
  - Phân tách đúng 13 ảnh lỗi Detection vào `rework_queue.csv` giao đúng Annotator theo `jobs.csv`.
  - Giữ lại các ảnh lỗi Panoptic và sửa đổi triệt để các lỗi kỹ thuật (hash, guideline, split).
- **Truy vết Ticket team AI (Seed 10007):**
  - `tier_a`: 2 ảnh (`000000008021`, `000000009590`) thuộc `scene_195` và `scene_224`, job guideline cũ v1.2, có nhãn `bottle`.
  - `tier_b`: 4 ảnh (`000000002685`, `000000005193`, `000000006471`, `000000007574`) các cảnh khác cùng điều kiện.
  - `notify`: 5 annotator/reviewer (`A04`, `A05`, `Q01`, `Q02`, `Q03`).
- **Số ứng viên trên lô sạch (`--no-faults`):** Khoảng 8–12 ứng viên (đây là độ lệch tự nhiên của COCO do vật thể bị che khuất và crowd); hàng đợi trên seed 10007 sau khi tinh chỉnh ngưỡng: ~25–35 ảnh.
- **Ngưỡng đã chọn và cách chọn:** Kết hợp bipartite matching bbox IoU > 0.35 đồng thời kiểm tra diện tích và tỷ lệ lọt của segment mask. Không đặt ngưỡng IoU quá lỏng để tránh bùng nổ số lượng ứng viên cần xem mắt.

---

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Trong bài toán kiểm định chất lượng dữ liệu không có nhãn gốc (Ground Truth), độ đo đánh giá là **F1-score = 2 × (Precision × Recall) / (Precision + Recall)**.
- Khi ta tự động nhận toàn bộ ứng viên nghi vấn mà không qua bước xem ảnh thẩm định, ta có thể tăng Recall nhưng **Precision sẽ bị sụt giảm nghiêm trọng** (từ 0.95 xuống còn ~0.4–0.5).
- Nguyên nhân: Bộ dữ liệu COCO vốn tồn tại các độ lệch tự nhiên giữa Detection và Panoptic (ví dụ: vật thể bị che khuất một nửa, nhiều người đứng sát nhau trong crowd). Các ca lệch tự nhiên này **hoàn toàn không phải lỗi gán nhãn**. Nếu báo hết làm lỗi, số lượng False Positive (báo thừa) sẽ tăng vọt, kéo F1 tổng giảm từ 0.9+ xuống chỉ còn 0.6. Do đó, bước mắt người xem ảnh và ghi chú `confirmed` / `rejected` là không thể thay thế.

---

## 3. Quyết định và lineage
- **QC v1:** Số ảnh lỗi phát hiện là 23/250 = 9.2%, vượt xa ngưỡng an toàn phát hành 2.0% (&gt; 5 ảnh lỗi trên tổng số 250 ảnh) &rArr; **Kết luận bắt buộc: HOLD**.
- **Tác động tới Model (`R-021`):** Model R-021 đã được huấn luyện trên lô v1 (chứa nhãn bẩn và lỗi gài). Việc tạo ra bản v2 sửa dữ liệu sau này **không tự động chữa lành hay cập nhật lại trọng số của model đã học**. Do đó, run huấn luyện R-021 bắt buộc phải được đánh dấu `action=review_or_retrain`.

---

## 4. Hash chứng minh gì, không chứng minh gì?
- **Hash chứng minh:** Tính toàn vẹn (Integrity) và bất biến (Immutability) của tệp tin. Mã băm SHA-256 chứng minh file ảnh/nhãn hiện tại trùng khớp 100% từng byte với thời điểm đóng gói bàn giao, không bị chỉnh sửa lén lút hay hỏng hóc trong quá trình truyền tải.
- **Hash KHÔNG chứng minh:** Tính đúng đắn về mặt ngữ nghĩa (Semantic Correctness) của dữ liệu. Một nhãn gán sai hoàn toàn (ví dụ gán con chó thành con mèo) vẫn có thể tính ra một mã băm SHA-256 hoàn toàn hợp lệ. Mã hash không thể thay thế cho quy trình kiểm tra chất lượng nhãn (QC).

---

## 5. Truy vết
- **Tiêu chí tầng a và tầng b:**
  - Tầng a (`tier_a`): Các ảnh nằm trong những cảnh mà team AI đã nêu đích danh trong ticket, thuộc các job thực hiện theo guideline cũ (v1.2) VÀ có chứa ít nhất 1 box detection thuộc lớp bị đổi quy tắc (ghi trong changelog).
  - Tầng b (`tier_b`): Toàn bộ các ảnh còn lại trong lô thỏa mãn cùng điều kiện trên nhưng chưa được team AI phát hiện ra.
- **Vì sao phải lấy guideline theo job (`jobs.csv`):** Vì trong metadata của từng ảnh có thể tồn tại lỗi `guideline_mismatch` (ảnh bị ghi nhầm phiên bản guideline). Quy định chuẩn mực của quy trình quản trị là phiên bản guideline có hiệu lực được gắn cố định theo từng Job giao việc (`jobs.csv`).

---

## 6. Đề Ẩn 10 (Thực hiện trong 40 phút)
- **Mã đề:** Đề 10 (`de_an_10` / `de_an.zip`, Release ID: `lab250_278031cc6eb2`).
- **Tổng số lỗi phát hiện:** **19 lỗi** (gồm 9 lỗi luật và 10 lỗi ngữ nghĩa gán nhãn).
- **Chi tiết 9 lỗi luật (`rule_detectable`):**
  1. `bbox_out_of_bounds`: `img_0054` (box tràn mép ảnh trái `x_min < 0`).
  2. `duplicate_box`: `img_0132` (2 box person trùng lặp lệch 1–2px).
  3. `guideline_mismatch`: `img_0214` (metadata ghi nhầm guideline v1.2 trong khi job J03 là v1.3).
  4. `missing_image`: `img_0078` (file `img_0078.jpg` bị thiếu trong thư mục `images/`).
  5. `scene_leak`: `scene_743` (các ảnh của cùng cảnh bị rò rỉ đồng thời ở cả tập `train` và `val`).
  6. `thing_overlap`: `img_0213` (mặt nạ phân đoạn bị lấn chiếm pixel trong mask PNG).
  7. `thing_overlap`: `img_0250` (mặt nạ phân đoạn toilet bị cướp 1583 pixel).
  8. `wrong_hash`: `img_0007` (mã băm SHA-256 ảnh thực tế lệch so với manifest).
  9. `wrong_hash`: `img_0128` (mã băm SHA-256 ảnh thực tế lệch so với manifest).
- **Chi tiết 10 lỗi gán nhãn ngữ nghĩa (`cross_check_review`):**
  1. `missing_box`: `img_0096` (Lò nướng lớn `oven` 63647px trong phòng bếp hoàn toàn thiếu bounding box detection).
  2. `bbox_drift`: `img_0090` (Người cưỡi ngựa, detection box bị trôi lệch tâm xuống dưới cắt mất đầu người).
  3. `bbox_drift`: `img_0220` (Người cầm ô đi mưa, bounding box bị lệch tâm trôi ra ngoài cơ thể).
  4. `bbox_drift`: `img_0240` (Con cừu trên đồng cỏ, bounding box detection bị trôi lệch tâm khỏi thân cừu).
  5. `class_swap`: `img_0015` (Ly uống rượu vang chân cao, detection nhận nhầm sang `cup`).
  6. `class_swap`: `img_0043` (Bát tô đựng thức ăn trên bàn ăn, detection gán nhầm sang `cup`).
  7. `class_swap`: `img_0053` (Cầu thủ ném bóng rõ nét, detection gán nhầm cơ thể thành `baseball glove`).
  8. `class_swap`: `img_0091` (Bánh sinh nhật lớn kèm dao cắt bánh, detection gán nhầm sang `donut`).
  9. `class_swap`: `img_0094` (Xe tải thùng lớn màu xanh chở hàng, detection nhận nhầm thành `car`).
  10. `category_swap`: `img_0105` (Cốc uống nước trên bàn ăn bị panoptic gán nhầm danh mục sang `wine glass`).
- **Truy vết Ticket Đề Ẩn 10 (Lớp `car` bị đổi guideline v1.2 &rarr; v1.3):**
  - `tier_a`: `["img_0074", "img_0236"]` (thuộc cảnh `scene_290` và `scene_635`, job v1.2, có box `car`).
  - `tier_b`: `["img_0135", "img_0146", "img_0188", "img_0209"]`.
  - `notify`: `["A02", "A04", "Q02"]`.
- **Đóng gói nộp bài Submission Gate:**
  - File nộp: `de_an_10__NHOMLABUBU10.zip` (1.4 KB, sạch gọn, chỉ chứa `submission/de_an/` với `errors.json`, `review_log.csv` và `trace.json`).
  - 100% dòng trong `review_log.csv` có ghi chú cụ thể &ge; 20 ký tự mô tả trung thực bằng chứng mắt thấy trong ảnh.
