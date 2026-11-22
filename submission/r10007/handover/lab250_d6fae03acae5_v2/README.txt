Release: lab250_d6fae03acae5_v2
Parent: lab250_d6fae03acae5
Số ảnh: 236
Số nhãn: 1666
Guideline: v1.2 (J01-J04), v1.3 (J05-J10)
QC v1: 23/250 = 9,2%
Kết luận v1: Hold — 23/250 = 9,2% ảnh lỗi vượt ngưỡng 2%, không Release; run R-021 đã train trên v1 phải xem lại hoặc train lại
Lineage: decision HOLD đã ghi cho lab250_d6fae03acae5; impact xác nhận R-021 affected=True action=review_or_retrain
Kết luận v2: Release — đã tách 14 ảnh lỗi detection sang rework; đã sửa hash/guideline/split trong hồ sơ; còn 6 ảnh lỗi panoptic không ảnh hưởng nhãn detection
Ghi chú: wrong_hash 1 ảnh (000000022479): đã mở ảnh kiểm, ảnh còn nguyên nên chỉ manifest v1 sai; manifest.csv v2 ghi sha256 tính lại từ file | guideline_mismatch 1 ảnh (000000021503): truyvet.csv lấy guideline theo job trong jobs.csv | scene_leak scene_322: ảnh 000000006213 chuyển về train cùng cả cảnh | rework 14 ảnh lỗi nhãn detection/thiếu file rời v2, giao lại: A01/Q03: 000000021879, 000000022192, 000000022892; A02/Q01: 000000001490, 000000017905, 000000019402; A02/Q03: 000000013597, 000000014888; A03/Q02: 000000015660; A04/Q02: 000000009769, 000000009772; A05/Q01: 000000003156; A05/Q03: 000000005586, 000000006954 | lỗi panoptic 6 ảnh ở lại v2 vì nhãn detection vẫn đúng, báo team panoptic: 000000002153 (thing_overlap), 000000013923 (thing_overlap), 000000015440 (instance_merge), 000000016249 (category_swap), 000000021167 (invalid_category_id), 000000023899 (instance_merge) | nhãn detection trong v2 giữ nguyên bytes như v1, không sửa tay; v1 không bị ghi đè
