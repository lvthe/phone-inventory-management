# Dữ liệu huấn luyện

Các file trong thư mục này được sinh bằng lệnh `python -m app.export_train`:
- định dạng CSV, mã hóa UTF-8;
- mở trực tiếp được bằng Excel, hoặc đọc bằng `pandas.read_csv` như slide Chương 2.

> **Nguồn dữ liệu:**
> - Danh mục máy và giá thị trường dựa trên các mẫu máy có thật ở Việt Nam, nhưng giá chỉ là **giá tham khảo xấp xỉ**.
> - Lịch sử nhập/bán là **dữ liệu mô phỏng** 52 tuần, sinh bởi `app/seed.py` (seed = 7) để minh họa thuật toán.
> - Ngày tháng tính lùi từ ngày chạy lệnh, nên mỗi lần xuất lại thì cột ngày sẽ khác, còn số liệu giữ nguyên.

## Tổng quan

| File | Số dòng | Dùng cho |
|---|---|---|
| `01_brand.csv` | 10 | Danh mục hãng và điểm thương hiệu (0–10) |
| `02_cpu.csv` | 29 | Danh mục chip và điểm hiệu năng (0–100) |
| `03_market_phones_raw.csv` | 168 | **Mô hình 1**: định giá theo cấu hình (dữ liệu thô) |
| `04_market_phones_01.csv` | 168 | **Mô hình 1** sau khi biến đổi về [0, 1]; có ln(giá) và cột `split` (134 train / 34 test) |
| `04_market_phones_01_minmax.csv` | 9 | Giá trị min/max dùng để biến đổi 0–1 |
| `05_weekly_sales.csv` | 1.071 | **Mô hình 2**: đường cầu từng mặt hàng (21 mặt hàng × ~51 tuần; 920 tuần dùng để train) |
| `06_stock_transactions.csv` | 7.473 | Phiếu nhập/bán gốc, là nguồn để tổng hợp file 05 |
| `07_phones.csv` | 21 | Mặt hàng đang kinh doanh: giá nhập, giá bán, tồn kho |

## Mô hình 1: định giá theo cấu hình (hồi quy tuyến tính bội)

`ln(price) = w0 + w1·brand_point + … + w9·release_year`

| Cột | Ý nghĩa | Đơn vị |
|---|---|---|
| `name`, `brand`, `cpu` | Tên máy, hãng, chip | |
| `brand_point` | Điểm thương hiệu, lấy từ `01_brand.csv` | 0–10 |
| `cpu_point` | Điểm hiệu năng chip, lấy từ `02_cpu.csv` | 0–100 |
| `ram`, `rom` | Bộ nhớ RAM và bộ nhớ trong | GB |
| `widescreen` | Kích thước màn hình | inch |
| `ppi` | Mật độ điểm ảnh | điểm/inch |
| `battery` | Dung lượng pin | mAh |
| `camera` | Độ phân giải camera chính | MP |
| `release_year` | Năm ra mắt | |
| **`price`** | **Giá thị trường, là biến cần dự đoán (y)** | VNĐ |
| `ln_price` | ln(price), chỉ có ở file 04 | |
| `split` | `train` hoặc `test` theo hold-out 80/20, chỉ có ở file 04 | |

Cách biến đổi về 0–1 ở file 04 (min-max, giống ví dụ Chương 4): `x' = (x − min) / (max − min)`. Giá trị min và max lấy từ `04_market_phones_01_minmax.csv`.

## Mô hình 2: đường cầu Q = a·P + b (hồi quy tuyến tính đơn)

| Cột | Ý nghĩa |
|---|---|
| `phone_id`, `sku`, `name` | Mặt hàng |
| `week_start` | Ngày thứ Hai đầu tuần |
| **`avg_price`** / `avg_price_million` | **Giá bán bình quân trong tuần (P)**, tính bằng VNĐ / triệu VNĐ |
| **`qty_sold`** | **Số máy bán trong tuần (Q)**, đã trừ hàng khách trả |
| `stockout` | 1 nếu trong tuần có ngày hết hàng |
| `use_for_training` | `no` với tuần hết hàng, vì số bán bị giới hạn bởi tồn kho chứ không phản ánh nhu cầu thật |

Quy trình tạo file 05 từ file 06:
1. Cộng số máy bán theo ngày, trừ đi số máy khách trả.
2. Xác định giá có hiệu lực của từng ngày từ lịch sử giá.
3. Gộp các ngày thành tuần.
4. Bỏ tuần đầu chưa trọn và tuần hiện tại đang dở.

## Ví dụ dùng với pandas / numpy

```python
import numpy as np
import pandas as pd

# Mô hình 2 – đường cầu iPhone 15 bằng polyfit (như slide Chương 2)
df = pd.read_csv("05_weekly_sales.csv")
d = df[(df.sku == "IP15-128") & (df.use_for_training == "yes")]
a, b = np.polyfit(d.avg_price_million, d.qty_sold, 1)
print(f"Q = {a:.3f}·P + {b:.2f}")            # Q = -7.888·P + 157.95

# Mô hình 1 – hồi quy bội bằng hệ phương trình chuẩn w = A^-1 B
m = pd.read_csv("04_market_phones_01.csv")
feats = ["brand_point", "cpu_point", "ram", "rom", "widescreen", "ppi", "battery", "camera", "release_year"]
tr, te = m[m.split == "train"], m[m.split == "test"]
X = np.c_[np.ones(len(tr)), tr[feats]]
w = np.linalg.inv(X.T @ X) @ X.T @ tr.ln_price
pred = np.exp(np.c_[np.ones(len(te)), te[feats]] @ w)
rmse = np.sqrt(np.sum((pred - te.price) ** 2) / len(te))
print("RMSE test:", round(rmse))             # ≈ 3,22 triệu
```

Có thể nạp lại `03_market_phones_raw.csv`, hoặc một file cùng cấu trúc do bạn tự thu thập, vào hệ thống bằng nút **Nhập CSV thị trường** ở trang *Mô hình & dữ liệu*. Các cột bắt buộc: `name, brand, cpu, ram, rom, widescreen, ppi, battery, camera, release_year, price`. Tên `brand` và `cpu` phải có sẵn trong danh mục hãng và chip.
