# Bảo mật khi làm việc với Dữ liệu — Seed 10007

> Báo cáo đánh giá an toàn thông tin và bảo mật dữ liệu gắn liền với lô bàn giao `lab250_d6fae03acae5`.

## 1. Ca USB: Hết giờ làm việc, muốn chép lô dữ liệu về nhà làm tiếp

Hành động chép dữ liệu ra USB hoặc gửi qua email cá nhân/nhờ người khác làm hộ là hành vi vi phạm nghiêm trọng chính sách bảo mật thông tin (Data Leakage & Unauthorized Access). Dữ liệu huấn luyện thị giác máy tính của tổ chức chứa quyền sở hữu trí tuệ, thông tin nhạy cảm và có nguy cơ bị lây nhiễm mã độc khi cắm thiết bị lưu trữ ngoài không được kiểm duyệt vào máy trạm công ty. Thay vào đó, nhân viên phải xin cấp quyền truy cập từ xa thông qua mạng riêng ảo nội bộ (VPN công ty) với cơ chế xác thực đa yếu tố (MFA), hoặc làm việc trên môi trường Cloud/VDI được cô lập an toàn, tuyệt đối không di chuyển dữ liệu ra khỏi ranh giới hạ tầng được phê duyệt.

## 2. Năm việc: Được hay Không được làm trong quản trị dữ liệu

- **Mở job được giao trên máy công ty:** ĐƯỢC LÀM. Đây là thiết bị tiêu chuẩn do tổ chức quản lý, đã cài đặt phần mềm phòng chống mã độc và giám sát an ninh mạng.
- **Chụp màn hình gửi người quen:** KHÔNG ĐƯỢC LÀM. Đây là hành vi phát tán dữ liệu nội bộ ra bên ngoài, vi phạm thỏa thuận bảo mật NDA và có nguy cơ để lộ nhãn/hình ảnh độc quyền.
- **Chép lô ra USB:** KHÔNG ĐƯỢC LÀM. Thiết bị USB cá nhân không được mã hóa, dễ thất lạc và là nguồn lây truyền virus/ransomware vào hệ thống huấn luyện AI.
- **Dán nhãn thật lên chatbot công cộng:** KHÔNG ĐƯỢC LÀM. Dữ liệu dán vào các chatbot thương mại bên ngoài có thể bị nhà cung cấp bên thứ ba lưu trữ và sử dụng lại để tái huấn luyện, gây rò rỉ dữ liệu.
- **Đưa tài khoản CVAT cho đồng nghiệp:** KHÔNG ĐƯỢC LÀM. Mỗi tài khoản gán nhãn được định danh riêng biệt để phục vụ quy trình kiểm toán (Audit Trail) và phân định trách nhiệm cá nhân (Annotator/Reviewer). Đưa tài khoản làm phá vỡ tính toàn vẹn của hồ sơ truy vết.

## 3. Ca khuôn mặt: Thấy mặt người rõ trong lô, guideline yêu cầu làm mờ

Khi phát hiện hình ảnh chứa khuôn mặt người thật nhìn rõ mà chưa được làm mờ (De-identification/Anonymization) theo đúng guideline bảo mật dữ liệu cá nhân (GDPR/PII), quyết định bắt buộc là phải đưa lô dữ liệu vào trạng thái HOLD ngay lập tức. Sau đó, kỹ sư dữ liệu phải báo cáo ngay cho người phụ trách an toàn dữ liệu (Data Privacy Officer) và quản lý dự án để kích hoạt pipeline làm mờ tự động hoặc gửi trả nhà cung cấp thu thập. Tuyệt đối không tự ý dùng phần mềm cá nhân để xóa ảnh hay chỉnh sửa thủ công trên máy cục bộ, vì sẽ làm mất tính toàn vẹn phả hệ và sai lệch mã băm kiểm toán (Audit Hash). Cụ thể trong lô thực hành r10007, ảnh `000000000785` và ảnh `000000000139` chứa người thật rõ nét cần được đưa vào diện cảnh báo và thẩm tra bảo mật trước khi xem xét phát hành.
