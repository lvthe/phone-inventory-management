"""Xuất dữ liệu huấn luyện ra CSV (mở được bằng Excel, đọc được bằng pandas.read_csv).

Chạy:  python -m app.export_train          (ghi vào thư mục data_train/)

Các file:
  01_brand.csv                 danh mục hãng + điểm thương hiệu
  02_cpu.csv                   danh mục chip + điểm hiệu năng
  03_market_phones_raw.csv     dữ liệu train MÔ HÌNH 1 (định giá theo cấu hình) - dạng thô
  04_market_phones_01.csv      dữ liệu MÔ HÌNH 1 sau khi biến đổi về [0, 1], kèm ln(giá) và cột tập train/test
  05_weekly_sales.csv          dữ liệu train MÔ HÌNH 2 (đường cầu Q = a·P + b) - theo tuần, từng mặt hàng
  06_stock_transactions.csv    giao dịch nhập/bán gốc (nguồn để tổng hợp file 05)
  07_phones.csv                mặt hàng đang kinh doanh (giá nhập, giá bán, tồn kho)
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from . import ml
from .database import BASE_DIR, DB_PATH, PHONE_SELECT, db
from .regression import hold_out_split

OUT_DIR = BASE_DIR / "data_train"


def write_csv(name: str, header: list[str], rows) -> int:
    path = OUT_DIR / name
    with open(path, "w", newline="", encoding="utf-8-sig") as f:       # utf-8-sig để Excel hiển thị đúng tiếng Việt
        w = csv.writer(f)
        w.writerow(header)
        n = 0
        for r in rows:
            w.writerow(r)
            n += 1
    return n


def export() -> dict:
    if not DB_PATH.exists():
        from .seed import seed
        seed()
    OUT_DIR.mkdir(exist_ok=True)
    counts = {}
    with db() as conn:
        counts["01_brand.csv"] = write_csv(
            "01_brand.csv", ["id", "name", "point"],
            ((r["id"], r["name"], r["point"]) for r in conn.execute("SELECT * FROM brand ORDER BY id")))
        counts["02_cpu.csv"] = write_csv(
            "02_cpu.csv", ["id", "name_cpu", "point"],
            ((r["id"], r["name_cpu"], r["point"]) for r in conn.execute("SELECT * FROM cpu ORDER BY id")))

        # ---------------- Mô hình 1: dữ liệu thị trường
        rows, X, y = ml.config_dataset(conn)
        tr, te = hold_out_split(len(y), 0.2)          # cùng cách chia với lúc huấn luyện
        split = np.empty(len(y), dtype=object)
        split[tr], split[te] = "train", "test"
        counts["03_market_phones_raw.csv"] = write_csv(
            "03_market_phones_raw.csv",
            ["id", "name", "brand", "cpu", *ml.FEATURES, "price"],
            ((r["id"], r["name"], r["brand"], r["cpu"], *[r[f] for f in ml.FEATURES], int(r["price"])) for r in rows))

        lo, hi = X.min(axis=0), X.max(axis=0)
        rng = np.where(hi - lo == 0, 1, hi - lo)
        Z = (X - lo) / rng
        counts["04_market_phones_01.csv"] = write_csv(
            "04_market_phones_01.csv",
            ["id", "name", *ml.FEATURES, "ln_price", "price", "split"],
            ((r["id"], r["name"], *[round(float(v), 4) for v in Z[i]], round(float(np.log(y[i])), 4), int(y[i]), split[i])
             for i, r in enumerate(rows)))
        # min/max dùng để biến đổi: cần khi đưa một cấu hình mới vào mô hình
        write_csv("04_market_phones_01_minmax.csv", ["feature", "min", "max"],
                  ((f, float(lo[j]), float(hi[j])) for j, f in enumerate(ml.FEATURES)))

        # ---------------- Mô hình 2: bán theo tuần
        phones = conn.execute(PHONE_SELECT + " ORDER BY p.id").fetchall()
        weekly_rows = []
        for p in phones:
            for w in ml.weekly_sales(conn, p["id"]):
                weekly_rows.append((p["id"], p["sku"], p["name"], w["week"], round(w["price"]), round(w["price"] / 1e6, 4),
                                    w["qty"], int(w["stockout"]), "no" if w["stockout"] else "yes"))
        counts["05_weekly_sales.csv"] = write_csv(
            "05_weekly_sales.csv",
            ["phone_id", "sku", "name", "week_start", "avg_price", "avg_price_million", "qty_sold", "stockout", "use_for_training"],
            weekly_rows)

        counts["06_stock_transactions.csv"] = write_csv(
            "06_stock_transactions.csv", ["id", "phone_id", "sku", "type", "quantity", "unit_price", "note", "created_at"],
            ((r["id"], r["phone_id"], r["sku"], r["type"], r["quantity"], int(r["unit_price"]), r["note"] or "", r["created_at"])
             for r in conn.execute("""SELECT t.*, p.sku FROM stock_tx t JOIN phone p ON p.id = t.phone_id
                                       ORDER BY t.created_at, t.id""")))
        counts["07_phones.csv"] = write_csv(
            "07_phones.csv",
            ["id", "sku", "name", "brand", "cpu", *ml.FEATURES, "cost_price", "price", "stock", "min_stock"],
            ((p["id"], p["sku"], p["name"], p["brand"], p["cpu"], *[p[f] for f in ml.FEATURES],
              int(p["cost_price"]), int(p["price"]), p["stock"], p["min_stock"]) for p in phones))
    return counts


if __name__ == "__main__":
    for name, n in export().items():
        print(f"{name:32s} {n:6d} dòng")
    print("Đã ghi vào", OUT_DIR)
