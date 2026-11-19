# Nhóm LABUBU10 — Day 10 Lab

- **Mã nhóm:** LABUBU10 (NHOM LABUBU10)
- **Seed luyện tập:** 10007 (Bộ bàn giao v1 `lab250_634019b57111`, v2 `lab250_634019b57111_v2`)
- **Đề ẩn lựa chọn:** Đề 10 (`de_an_10` / `de_an.zip`, Release ID: `lab250_278031cc6eb2`)
- **Repo GitHub:** https://github.com/hoangkhiem3523/K5-L23-DAY10-NHOM-LABUBU10-Release
- **Nhánh chính thực hiện:** `Tny`

---

## Danh sách Thành viên & Phân công vai trò (Mô hình 7 Người)

| STT | Họ và tên | MSHV | Tài khoản GitHub | Vai trò chuyên trách | Nhiệm vụ chính trong dự án |
|:---:|---|:---:|:---:|---|---|
| **01** | **Hoàng Sỹ Khiêm** | **2A202603244** | `hoangkhiem3523` | **Thành viên 1 — Trưởng nhóm & Detection Rules Lead** | Kiến trúc khung CLI `validator/validate.py`. Cài đặt 5 bộ quy tắc kiểm tra Detection: `missing_image`, `wrong_hash` (đọc byte nhị phân SHA-256), `invalid_class`, `bbox_out_of_bounds`, `duplicate_box`. Review ảnh 0001–0035. |
| **02** | **Phan Đình Giáp** | **2A202603252** | `giap-pd` | **Thành viên 2 — Panoptic & Metadata Rules Lead** | Tích hợp thư viện `pngutil.py` giải mã màu RGB sang segment ID (`R + G×256 + B×65536`). Cài đặt kiểm tra `invalid_category_id`, `thing_overlap` (đếm pixel thực tế so với diện tích `area`), `scene_leak` (rò rỉ phân chia tập dữ liệu) và `guideline_mismatch`. Review ảnh 0036–0070. |
| **03** | **Nguyễn Thảo Linh** | **2A202603253** | `thaolinh-ng` | **Thành viên 3 — Cross-check & Candidates Engine Lead** | Xây dựng thuật toán ghép đôi bounding box YOLO ↔ Mask Panoptic (chuyển đổi tọa độ, tính toán IoU, mapping 80 lớp qua `classes.txt`). Trích xuất danh sách ứng viên nghi vấn `candidates.json` cho 5 loại lỗi ngữ nghĩa (`class_swap`, `category_swap`, `bbox_drift`, `missing_box`, `instance_merge`). Review ảnh 0071–0105. |
| **04** | **Phạm Việt Hoàng** | **2A202603254** | `hoang-pv` | **Thành viên 4 — QC Review Lead & Đảm bảo chất lượng** | Điều phối quy trình kiểm tra trực quan 250 ảnh, quản trị `review_log.csv`. Xây dựng công cụ xem ảnh trực quan với bounding box và nhãn đè. Chuẩn hóa 100% dòng ghi chú đạt độ dài &ge; 20 ký tự mô tả chi tiết bằng chứng mắt thấy. Hợp nhất danh sách lỗi cuối cùng `errors.json`. Review ảnh 0106–0145. |
| **05** | **Mai Văn Phong** | **2A202603256** | `phong-mv` | **Thành viên 5 — Handover v2 & Rework Lead** | Thiết kế và đóng gói gói bàn giao sửa chữa `handover/<release_id>_v2/` đạt chuẩn 17/17 tiêu chí `check_handover.py`. Tách lỗi detection sang `rework_queue.csv` giao đúng người theo `jobs.csv`. Lập `manifest.csv`, `label_summary.csv`, `truyvet.csv`, `README.txt`. Review ảnh 0146–0180. |
| **06** | **Nguyễn Văn Hùng** | **2A202603295** | `hung-nv` | **Thành viên 6 — Lineage & Audit Trail Lead** | Tính toán tỷ lệ lỗi lô v1 (vượt ngưỡng 2% &rarr; quyết định HOLD). Ghi nhận nhật ký sự kiện vào `lineage.jsonl`. Phân tích rủi ro tác động lên mô hình huấn luyện `R-021`. Xây dựng thuật toán truy vết ngược theo dòng đời sản phẩm `trace.json` (`tier_a`, `tier_b`, `notify`). Review ảnh 0181–0215. |
| **07** | **Hoàng Thuận Thiện** | **2A202603270** | `Tiny208` | **Thành viên 7 — Security & Submission Lead** | Xây dựng hồ sơ bảo mật dữ liệu `security.md` (xử lý tình huống USB, vi phạm bản quyền dữ liệu, phát hiện khuôn mặt chưa làm mờ &rarr; HOLD + báo phụ trách). Soạn thảo `REPORT.md`, `prompts.md`. Phụ trách đóng gói ZIP và cổng nộp bài Submission Gate cho Đề ẩn 10. Review ảnh 0216–0250. |
