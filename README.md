# Hệ thống quản lý kho điện thoại thông minh – tối ưu giá bán bằng hồi quy

Đồ án môn **Phát triển các hệ thống thông minh**. Ứng dụng web có hai phần:

- **Module quản lý kho:**
  - Quản lý mặt hàng (theo bảng PHONE / CPU / BRAND như ví dụ Chương 4).
  - Nhập kho, xuất bán, theo dõi tồn kho.
  - Cảnh báo sắp hết hàng và tồn kho lâu.
- **Module học máy:**
  - **Hồi quy tuyến tính bội** để định giá theo cấu hình máy: hãng, chip, RAM, ROM, màn hình, ppi, pin, camera, năm ra mắt.
  - **Hồi quy tuyến tính đơn** (`np.polyfit`) để ước lượng đường cầu `Q = a·P + b` cho từng mặt hàng.
  - Từ đường cầu, tính **giá bán tối ưu** theo 3 chiến lược: tối đa lợi nhuận, tối đa doanh thu, giải phóng tồn kho.

Báo cáo phân tích – thiết kế – đánh giá: [docs/BaoCao_PhanTich_ThietKe.md](docs/BaoCao_PhanTich_ThietKe.md)

## Cài đặt và chạy

Yêu cầu: Python 3.10 trở lên.

```bash
pip install -r requirements.txt
```

```bash
python -m uvicorn app.main:app --port 8000
```

Sau đó mở http://127.0.0.1:8000. Trên Windows có thể bấm đúp `run.bat` thay cho hai lệnh trên.

Lần chạy đầu tiên, hệ thống tự tạo CSDL `data/kho_dien_thoai.db` với dữ liệu mẫu. Muốn tạo lại dữ liệu mẫu từ đầu (xóa toàn bộ dữ liệu cũ):

```bash
python -m app.seed
```

Các lệnh khác:

```bash
python -m unittest discover -s tests
```

```bash
python -m app.ml_cli train
```

```bash
python -m app.ml_cli suggest 5 XA_KHO 8
```

Xuất dữ liệu huấn luyện ra CSV (vào thư mục `data_train/`, mô tả cột trong [data_train/README.md](data_train/README.md)):

```bash
python -m app.export_train
```

## Cấu trúc thư mục

```
app/
  database.py     CSDL SQLite (brand, cpu, phone, market_phone, stock_tx, price_history, price_suggestion, model_run)
  seed.py         Sinh dữ liệu khởi động: 168 mẫu thị trường, 21 mặt hàng, 52 tuần nhập/bán mô phỏng
  regression.py   Thuật toán hồi quy: polyfit, hệ phương trình chuẩn w = A⁻¹B, RMSE/MSE/MAE/R², hold-out, k-fold
  ml.py           Module học máy: huấn luyện, lưu/nạp file tri thức (.sav, pickle), tối ưu giá
  ml_cli.py       Gọi module học máy từ dòng lệnh
  main.py         Web API (FastAPI)
static/           Giao diện: index.html, app.js, style.css
models/           File tri thức sinh ra khi huấn luyện
docs/             Báo cáo
tests/            Kiểm thử đơn vị
```

## Màn hình chính

| Màn hình | Chức năng |
|---|---|
| Tổng quan | KPI (tồn kho, giá trị tồn, doanh thu/lợi nhuận 30 ngày), biểu đồ doanh thu theo tuần, bán chạy, cảnh báo sắp hết và tồn lâu |
| Kho hàng | Danh sách, tìm kiếm, thêm/sửa/xóa mặt hàng; nút **Gợi ý giá theo cấu hình** khi nhập máy mới |
| Nhập/Xuất | Lập phiếu nhập (tự cập nhật giá nhập bình quân) và phiếu bán (kiểm tra tồn); lịch sử giao dịch |
| Tối ưu giá (AI) | Chọn mặt hàng và chiến lược, xem giá đề xuất, đồ thị đường cầu và đường lợi nhuận, rồi **áp dụng** hoặc **từ chối**; gợi ý cho toàn kho |
| Mô hình & dữ liệu | Độ đo hold-out/k-fold, hệ số hồi quy, biểu đồ thực tế so với dự đoán, dữ liệu thị trường (nhập/xuất CSV), huấn luyện lại |
| Nhật ký | Gợi ý giá cùng quyết định, so sánh số bán thực tế với dự kiến; lịch sử huấn luyện (telemetry) |

> **Lưu ý:** lịch sử bán trong dữ liệu mẫu là **mô phỏng** để minh họa thuật toán; giá thị trường chỉ là giá tham khảo xấp xỉ. Giao diện tải Bootstrap và Chart.js từ CDN, nên máy chạy cần có Internet.
