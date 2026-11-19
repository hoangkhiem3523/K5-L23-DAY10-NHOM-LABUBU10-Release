# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): <<seed: ... / ... / ...>>
- Số ứng viên trên lô sạch (`--no-faults`): <<...>>; hàng đợi trên seed luyện tập: <<... ảnh>>
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): <<...>>

## 2. Vì sao báo hết ứng viên làm F1 giảm?
<<Trả lời bằng số của nhóm.>>

## 3. Quyết định và lineage
QC v1 có 23 lỗi trên 250 ảnh (23/250 = 9,2%). Tỉ lệ này vượt ngưỡng 2%, nên kết luận v1 là **HOLD**, không phát hành.

Lineage đã ghi `decision=HOLD` cho release `lab250_d6fae03acae5`. Truy vấn impact trả `R-021: affected=True action=review_or_retrain`; R-021 đã train trên v1 nên cần được xem xét lại hoặc train lại.

Bản v2 `lab250_d6fae03acae5_v2` có 236 ảnh và 1.666 nhãn. Đã chuyển 14 ảnh có lỗi detection/thiếu file sang rework; 6 ảnh chỉ có lỗi panoptic được giữ lại để báo nhóm panoptic. Ảnh `000000022479` mở được và nội dung còn nguyên nên manifest v2 ghi SHA-256 tính lại; guideline mismatch và split của scene leak cũng đã được sửa trong hồ sơ. Kết luận của công cụ dựng v2 là **Release**.

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
