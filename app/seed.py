"""Sinh dữ liệu khởi động (bootstrap) cho hệ thống.

Theo Chương 3: khi chưa có dữ liệu sử dụng thực tế, hệ thống cần dữ liệu khởi động
(tìm trên web / tạo từ thực tế / mua). Ở đây gồm:
  1. Danh mục hãng, chip (điểm hiệu năng).
  2. Dữ liệu thị trường tham chiếu: các mẫu máy và biến thể cấu hình với giá tham khảo.
  3. Mặt hàng trong kho + 52 tuần lịch sử nhập/bán MÔ PHỎNG: giá bán thay đổi theo
     các đợt điều chỉnh, số lượng bán phụ thuộc giá (càng đắt bán càng ít) + yếu tố mùa
     vụ + nhiễu ngẫu nhiên. Dữ liệu này chỉ để minh họa, không phải số liệu bán thật.

Chạy:  python -m app.seed          (tạo mới toàn bộ CSDL)
"""
from __future__ import annotations

import datetime as dt
import shutil

import numpy as np

from .database import BASE_DIR, DB_PATH, db, init_db

TODAY = dt.date.today()
HISTORY_DAYS = 364

BRANDS = {  # tên: điểm thương hiệu (0-10)
    "Apple": 10, "Samsung": 9, "Google": 8.5, "Xiaomi": 7.5, "OPPO": 7.5,
    "vivo": 7, "Honor": 7, "realme": 6.5, "Nokia": 5, "Tecno": 4.5,
}

CPUS = {  # tên chip: điểm hiệu năng (0-100)
    "Apple A19 Pro": 100, "Apple A19": 95, "Apple A18 Pro": 96, "Apple A18": 91,
    "Apple A16 Bionic": 80, "Apple A15 Bionic": 73,
    "Snapdragon 8 Elite": 98, "Snapdragon 8 Gen 3": 90, "Snapdragon 7 Gen 3": 60,
    "Snapdragon 6 Gen 3": 48, "Snapdragon 6 Gen 1": 45, "Snapdragon 4 Gen 2": 30,
    "Snapdragon 685": 22,
    "Dimensity 9400": 97, "Dimensity 8400 Ultra": 78, "Dimensity 7300 Energy": 52,
    "Dimensity 7025 Ultra": 44, "Dimensity 6300": 30,
    "Exynos 2400": 86, "Exynos 1580": 55, "Exynos 1380": 43,
    "Tensor G4": 79, "Tensor G3": 72,
    "Helio G99 Ultra": 33, "Helio G99": 32, "Helio G92 Max": 26, "Helio G81 Ultra": 21,
    "Unisoc T612": 18, "Unisoc T606": 17,
}

# name, brand, cpu, ram, rom, inch, ppi, pin, camera, năm, giá tham khảo (VNĐ)
STOCKED = [
    ("IP17PM-256", "iPhone 17 Pro Max 256GB", "Apple", "Apple A19 Pro", 12, 256, 6.9, 460, 4823, 48, 2025, 37_990_000),
    ("IP17-256", "iPhone 17 256GB", "Apple", "Apple A19", 8, 256, 6.3, 460, 3692, 48, 2025, 24_990_000),
    ("IP16PM-256", "iPhone 16 Pro Max 256GB", "Apple", "Apple A18 Pro", 8, 256, 6.9, 460, 4685, 48, 2024, 30_490_000),
    ("IP16-128", "iPhone 16 128GB", "Apple", "Apple A18", 8, 128, 6.1, 460, 3561, 48, 2024, 19_990_000),
    ("IP15-128", "iPhone 15 128GB", "Apple", "Apple A16 Bionic", 6, 128, 6.1, 460, 3349, 48, 2023, 16_490_000),
    ("SS-S25U-256", "Galaxy S25 Ultra 12/256GB", "Samsung", "Snapdragon 8 Elite", 12, 256, 6.9, 498, 5000, 200, 2025, 28_990_000),
    ("SS-S25-256", "Galaxy S25 12/256GB", "Samsung", "Snapdragon 8 Elite", 12, 256, 6.2, 416, 4000, 50, 2025, 19_990_000),
    ("SS-A56-128", "Galaxy A56 5G 8/128GB", "Samsung", "Exynos 1580", 8, 128, 6.7, 385, 5000, 50, 2025, 9_490_000),
    ("SS-A36-128", "Galaxy A36 5G 8/128GB", "Samsung", "Snapdragon 6 Gen 3", 8, 128, 6.7, 385, 5000, 50, 2025, 7_690_000),
    ("SS-A16-128", "Galaxy A16 4/128GB", "Samsung", "Helio G99", 4, 128, 6.7, 385, 5000, 50, 2024, 4_290_000),
    ("GG-P9-128", "Google Pixel 9 12/128GB", "Google", "Tensor G4", 12, 128, 6.3, 422, 4700, 50, 2024, 17_990_000),
    ("XM-15T-256", "Xiaomi 15T 12/256GB", "Xiaomi", "Dimensity 8400 Ultra", 12, 256, 6.83, 446, 5500, 50, 2025, 13_990_000),
    ("XM-RN14-128", "Redmi Note 14 8/128GB", "Xiaomi", "Helio G99 Ultra", 8, 128, 6.67, 395, 5500, 108, 2025, 4_990_000),
    ("XM-R14C-128", "Redmi 14C 4/128GB", "Xiaomi", "Helio G81 Ultra", 4, 128, 6.88, 260, 5160, 50, 2024, 2_990_000),
    ("OP-FX8-512", "OPPO Find X8 16/512GB", "OPPO", "Dimensity 9400", 16, 512, 6.59, 460, 5630, 50, 2024, 22_990_000),
    ("OP-R14F-256", "OPPO Reno14 F 5G 8/256GB", "OPPO", "Snapdragon 6 Gen 1", 8, 256, 6.57, 402, 6000, 50, 2025, 10_490_000),
    ("OP-A5P-128", "OPPO A5 Pro 8/128GB", "OPPO", "Dimensity 6300", 8, 128, 6.67, 270, 5800, 50, 2025, 6_290_000),
    ("VV-V50-256", "vivo V50 12/256GB", "vivo", "Snapdragon 7 Gen 3", 12, 256, 6.77, 388, 6000, 50, 2025, 13_490_000),
    ("VV-Y19S-128", "vivo Y19s 6/128GB", "vivo", "Unisoc T612", 6, 128, 6.68, 264, 5500, 50, 2024, 3_990_000),
    ("RM-14P-256", "realme 14 Pro 5G 8/256GB", "realme", "Dimensity 7300 Energy", 8, 256, 6.77, 453, 6000, 50, 2025, 9_990_000),
    ("RM-C75-128", "realme C75 8/128GB", "realme", "Helio G92 Max", 8, 128, 6.72, 391, 6000, 50, 2024, 4_590_000),
]

# Các mẫu chỉ có trong dữ liệu thị trường (không kinh doanh)
MARKET_ONLY = [
    ("iPhone 16e 128GB", "Apple", "Apple A18", 8, 128, 6.1, 460, 4005, 48, 2025, 16_990_000),
    ("iPhone 14 128GB", "Apple", "Apple A15 Bionic", 6, 128, 6.1, 460, 3279, 12, 2022, 13_490_000),
    ("Galaxy Z Fold7 12/256GB", "Samsung", "Snapdragon 8 Elite", 12, 256, 8.0, 368, 4400, 200, 2025, 46_990_000),
    ("Galaxy Z Flip7 12/256GB", "Samsung", "Exynos 2400", 12, 256, 6.9, 397, 4300, 50, 2025, 28_990_000),
    ("Galaxy S24 FE 8/128GB", "Samsung", "Exynos 2400", 8, 128, 6.7, 385, 4700, 50, 2024, 12_990_000),
    ("Galaxy A26 5G 8/128GB", "Samsung", "Exynos 1380", 8, 128, 6.7, 385, 5000, 50, 2025, 6_290_000),
    ("Pixel 9a 8/128GB", "Google", "Tensor G4", 8, 128, 6.3, 422, 5100, 48, 2025, 12_490_000),
    ("Pixel 8 8/128GB", "Google", "Tensor G3", 8, 128, 6.2, 428, 4575, 50, 2023, 11_990_000),
    ("Xiaomi 15 Ultra 16/512GB", "Xiaomi", "Snapdragon 8 Elite", 16, 512, 6.73, 522, 5410, 50, 2025, 32_990_000),
    ("Xiaomi 15 12/256GB", "Xiaomi", "Snapdragon 8 Elite", 12, 256, 6.36, 460, 5240, 50, 2025, 21_990_000),
    ("Redmi Note 14 Pro 5G 8/256GB", "Xiaomi", "Dimensity 7300 Energy", 8, 256, 6.67, 446, 5110, 200, 2025, 8_990_000),
    ("POCO X7 Pro 12/256GB", "Xiaomi", "Dimensity 8400 Ultra", 12, 256, 6.67, 446, 6000, 50, 2025, 9_990_000),
    ("Redmi A5 4/128GB", "Xiaomi", "Unisoc T606", 4, 128, 6.88, 260, 5200, 32, 2025, 2_490_000),
    ("OPPO Reno14 5G 12/256GB", "OPPO", "Dimensity 8400 Ultra", 12, 256, 6.59, 460, 6000, 50, 2025, 15_990_000),
    ("OPPO A3 6/128GB", "OPPO", "Snapdragon 6 Gen 1", 6, 128, 6.67, 264, 5100, 50, 2024, 4_990_000),
    ("vivo X200 12/256GB", "vivo", "Dimensity 9400", 12, 256, 6.67, 452, 5800, 50, 2024, 22_990_000),
    ("vivo Y29 8/128GB", "vivo", "Snapdragon 4 Gen 2", 8, 128, 6.68, 264, 6500, 50, 2025, 5_290_000),
    ("Honor X9c 12/256GB", "Honor", "Snapdragon 6 Gen 1", 12, 256, 6.78, 437, 6600, 108, 2025, 8_990_000),
    ("Honor X6c 6/128GB", "Honor", "Helio G81 Ultra", 6, 128, 6.61, 270, 5300, 50, 2025, 3_290_000),
    ("realme 14 5G 12/256GB", "realme", "Snapdragon 6 Gen 3", 12, 256, 6.67, 395, 6000, 50, 2025, 8_490_000),
    ("realme Note 60 4/128GB", "realme", "Unisoc T612", 4, 128, 6.74, 260, 5000, 32, 2024, 2_890_000),
    ("Nokia C32 4/64GB", "Nokia", "Unisoc T606", 4, 64, 6.5, 270, 5000, 50, 2023, 2_190_000),
    ("Nokia G42 5G 6/128GB", "Nokia", "Snapdragon 4 Gen 2", 6, 128, 6.56, 269, 5000, 50, 2023, 3_990_000),
    ("Tecno Spark 30 8/128GB", "Tecno", "Helio G92 Max", 8, 128, 6.78, 396, 5000, 64, 2024, 3_690_000),
    ("Tecno Camon 30 8/256GB", "Tecno", "Helio G99 Ultra", 8, 256, 6.78, 393, 5000, 50, 2024, 5_490_000),
    ("Galaxy A06 4/64GB", "Samsung", "Helio G99", 4, 64, 6.7, 262, 5000, 50, 2024, 2_890_000),
    ("Galaxy A55 5G 8/128GB", "Samsung", "Exynos 1380", 8, 128, 6.6, 390, 5000, 50, 2024, 8_490_000),
]

ROM_STEPS = [64, 128, 256, 512, 1024]


def round_price(v: float) -> float:
    """Làm tròn giá kiểu bán lẻ: ...90.000đ."""
    return max(990_000.0, round(v / 100_000) * 100_000 - 10_000)


def market_rows(rng: np.random.RandomState) -> list[tuple]:
    """Mỗi mẫu máy sinh thêm các biến thể bộ nhớ/RAM; giá có nhiễu ±4% giữa các nơi bán."""
    base = [s[1:] for s in STOCKED] + MARKET_ONLY
    rows = []
    for name, brand, cpu, ram, rom, inch, ppi, pin, cam, year, price in base:
        variants = [(ram, rom, price)]
        i = ROM_STEPS.index(rom)
        step_cost = max(0.12 * price, 800_000) * (1.4 if brand == "Apple" else 1.0)
        for k in (1, 2):
            if i + k < len(ROM_STEPS):
                variants.append((ram, ROM_STEPS[i + k], price + k * step_cost))
        if brand != "Apple" and ram < 12:
            variants.append((ram + 4, rom, price * 1.08))
        for v_ram, v_rom, v_price in variants:
            short = " ".join(t for t in name.split() if "GB" not in t and "/" not in t)
            rom_label = f"{int(v_rom // 1024)}TB" if v_rom >= 1024 else f"{int(v_rom)}GB"
            rows.append((f"{short} {int(v_ram)}/{rom_label}", brand, cpu, v_ram, v_rom, inch, ppi, pin, cam, year,
                         round_price(v_price * np.exp(rng.normal(0, 0.04)))))
    return rows


def simulate_sales(rng, phone_id, ref_price, cost, days, start):
    """Mô phỏng nhập/bán theo ngày cho 1 mặt hàng. Trả về (giao dịch, lịch sử giá, tồn cuối, giá cuối)."""
    # Nhu cầu cơ sở/ngày theo phân khúc giá: máy rẻ bán nhiều hơn
    if ref_price < 5e6:
        base = rng.uniform(6.0, 9.0)
    elif ref_price < 10e6:
        base = rng.uniform(4.0, 6.0)
    elif ref_price < 20e6:
        base = rng.uniform(2.5, 4.0)
    else:
        base = rng.uniform(1.8, 3.0)
    elasticity = rng.uniform(3.5, 6.5)       # độ nhạy của nhu cầu theo giá (thị trường cạnh tranh)
    min_stock = int(max(3, round(base * 4)))

    txs, history = [], []
    price = round_price(ref_price * rng.uniform(1.0, 1.06))
    history.append((None, price, start))
    stock = int(round(base * 42))
    txs.append(("NHAP", stock, cost, "Nhập hàng đầu kỳ", start))
    next_change = int(rng.randint(14, 42))
    pending_import = None

    for d in range(days):
        day = start + dt.timedelta(days=d)
        if d == next_change:
            new_price = round_price(ref_price * rng.uniform(0.85, 1.12))
            if new_price != price:
                history.append((price, new_price, day))
                price = new_price
            next_change = d + int(rng.randint(14, 42))
        if pending_import and pending_import[0] == d:
            qty = pending_import[1]
            stock += qty
            txs.append(("NHAP", qty, round(cost * rng.uniform(0.98, 1.02), -4), "Nhập bổ sung", day))
            pending_import = None

        season = 1.0
        if (day.month, day.day) >= (1, 20) and (day.month, day.day) <= (2, 10):     # mua sắm Tết
            season = 1.35
        elif day.month == 11 and 22 <= day.day <= 30:                               # Black Friday
            season = 1.25
        if day.weekday() >= 5:
            season *= 1.3
        lam = base * max(0.03, 1 - elasticity * (price / ref_price - 1)) * season
        qty = min(stock, int(rng.poisson(lam)))
        if qty > 0:
            stock -= qty
            txs.append(("BAN", qty, price, None, day))
        if rng.rand() < 0.004 and stock > 0:
            txs.append(("TRA", 1, price, "Khách đổi trả", day))
            stock += 1
        if stock <= min_stock and pending_import is None:
            pending_import = (d + int(rng.randint(2, 6)), int(round(base * rng.uniform(25, 40))))
    return txs, history, stock, price, min_stock


def seed(reset: bool = True, seed_value: int = 7) -> None:
    if reset:
        DB_PATH.unlink(missing_ok=True)
        shutil.rmtree(BASE_DIR / "models", ignore_errors=True)    # tri thức cũ không còn khớp dữ liệu mới
    init_db()
    rng = np.random.RandomState(seed_value)
    start = TODAY - dt.timedelta(days=HISTORY_DAYS)

    with db() as conn:
        conn.executemany("INSERT INTO brand(name, point) VALUES (?, ?)", BRANDS.items())
        conn.executemany("INSERT INTO cpu(name_cpu, point) VALUES (?, ?)", CPUS.items())
        brand_id = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM brand")}
        cpu_id = {r["name_cpu"]: r["id"] for r in conn.execute("SELECT id, name_cpu FROM cpu")}

        conn.executemany(
            """INSERT INTO market_phone(name, id_brand, id_cpu, ram, rom, widescreen, ppi, battery,
                                         camera, release_year, price) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [(n, brand_id[b], cpu_id[c], *rest) for n, b, c, *rest in market_rows(rng)],
        )

        overstock = {"IP15-128", "OP-A5P-128", "VV-V50-256"}   # mặt hàng tồn nhiều để minh họa xả kho
        for sku, name, brand, cpu, ram, rom, inch, ppi, pin, cam, year, ref in STOCKED:
            launch = max(start, dt.date(year, 9, 20) if brand == "Apple" else dt.date(year, 3, 15))
            launch = min(launch, TODAY - dt.timedelta(days=200))
            cost = round(ref * rng.uniform(0.80, 0.87), -4)
            cur = conn.execute(
                """INSERT INTO phone(sku, name, id_brand, id_cpu, ram, rom, widescreen, ppi, battery, camera,
                                      release_year, cost_price, price, stock, min_stock, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,5,?)""",
                (sku, name, brand_id[brand], cpu_id[cpu], ram, rom, inch, ppi, pin, cam, year, cost, ref,
                 f"{launch} 08:00:00"),
            )
            pid = cur.lastrowid
            days = (TODAY - launch).days
            txs, history, stock, price, min_stock = simulate_sales(rng, pid, ref, cost, days, launch)
            if sku in overstock:
                qty = int(stock + 150 + rng.randint(0, 80))
                day = TODAY - dt.timedelta(days=12)
                txs.append(("NHAP", qty, cost, "Nhập lô lớn theo chương trình hãng", day))
                stock += qty

            conn.executemany(
                "INSERT INTO stock_tx(phone_id, type, quantity, unit_price, note, created_at) VALUES (?,?,?,?,?,?)",
                [(pid, t, q, p, note, f"{d} {9 + (i % 10):02d}:{(i * 7) % 60:02d}:00")
                 for i, (t, q, p, note, d) in enumerate(txs)],
            )
            conn.executemany(
                "INSERT INTO price_history(phone_id, old_price, new_price, source, created_at) VALUES (?,?,?,?,?)",
                [(pid, o, n, "MANUAL", f"{d} 08:00:00") for o, n, d in history],
            )
            conn.execute("UPDATE phone SET stock=?, price=?, min_stock=? WHERE id=?", (stock, price, min_stock, pid))


if __name__ == "__main__":
    seed()
    with db() as c:
        n_m = c.execute("SELECT COUNT(*) FROM market_phone").fetchone()[0]
        n_p = c.execute("SELECT COUNT(*) FROM phone").fetchone()[0]
        n_t = c.execute("SELECT COUNT(*) FROM stock_tx").fetchone()[0]
    print(f"Đã tạo CSDL {DB_PATH}: {n_m} mẫu thị trường, {n_p} mặt hàng, {n_t} giao dịch kho")
