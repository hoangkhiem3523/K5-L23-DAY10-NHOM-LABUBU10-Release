# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Người thực hiện truy vết seed 3007 | Codex | Đọc ticket và changelog, lọc tier_a, tier_b và notify rồi ghi runs/r3007/trace.json. | Hai lần lọc độc lập cho cùng danh sách. | Codex đối chiếu 2 cảnh trong ticket, box bottle (ID 39) trong labels và guideline, người gán, người kiểm trong jobs.csv. |
| 2 | Người thực hiện truy vết seed 10007 | Codex | Làm lại truy vết theo ticket của lô r10007 và ghi vào runs/r10007/trace.json. | Kết quả ở dòng 1 thuộc seed 3007 theo yêu cầu trước. | Codex đối chiếu độc lập bằng Python và PowerShell. Cả hai cho cùng danh sách ảnh và người phụ trách từ J02, J03 và J04. |
