"""Kết nối và khởi tạo cơ sở dữ liệu SQLite.

Thiết kế CSDL theo ví dụ "Module quản lý kho" ở Chương 4: bảng PHONE liên kết
với bảng CPU (name_cpu, point) và BRAND (name, point), bổ sung các bảng nghiệp vụ
kho (phiếu nhập/xuất) và các bảng phục vụ module học máy.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "kho_dien_thoai.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS brand (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    point         REAL NOT NULL                 -- điểm thương hiệu (0-10)
);

CREATE TABLE IF NOT EXISTS cpu (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name_cpu      TEXT NOT NULL UNIQUE,
    point         REAL NOT NULL                 -- điểm hiệu năng chip (0-100)
);

-- Dữ liệu thị trường tham chiếu (dữ liệu khởi động - bootstrap) dùng huấn luyện
-- mô hình định giá theo cấu hình.
CREATE TABLE IF NOT EXISTS market_phone (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    id_brand      INTEGER NOT NULL REFERENCES brand(id),
    id_cpu        INTEGER NOT NULL REFERENCES cpu(id),
    ram           REAL NOT NULL,                -- GB
    rom           REAL NOT NULL,                -- GB
    widescreen    REAL NOT NULL,                -- inch
    ppi           REAL NOT NULL,                -- mật độ điểm ảnh
    battery       REAL NOT NULL,                -- mAh
    camera        REAL NOT NULL,                -- MP camera chính
    release_year  INTEGER NOT NULL,
    price         REAL NOT NULL                 -- giá thị trường (VNĐ)
);

-- Mặt hàng điện thoại đang kinh doanh trong kho (bảng PHONE của Chương 4)
CREATE TABLE IF NOT EXISTS phone (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sku           TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    id_brand      INTEGER NOT NULL REFERENCES brand(id),
    id_cpu        INTEGER NOT NULL REFERENCES cpu(id),
    ram           REAL NOT NULL,
    rom           REAL NOT NULL,
    widescreen    REAL NOT NULL,
    ppi           REAL NOT NULL,
    battery       REAL NOT NULL,
    camera        REAL NOT NULL,
    release_year  INTEGER NOT NULL,
    image         TEXT,
    cost_price    REAL NOT NULL,                -- giá nhập bình quân
    price         REAL NOT NULL,                -- giá bán hiện hành
    stock         INTEGER NOT NULL DEFAULT 0,   -- số lượng tồn
    min_stock     INTEGER NOT NULL DEFAULT 5,   -- ngưỡng cảnh báo tồn tối thiểu
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Phiếu nhập / xuất kho. type: NHAP (nhập hàng), BAN (xuất bán), TRA (khách trả), HUY (xuất hủy)
CREATE TABLE IF NOT EXISTS stock_tx (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_id      INTEGER NOT NULL REFERENCES phone(id) ON DELETE CASCADE,
    type          TEXT NOT NULL CHECK (type IN ('NHAP','BAN','TRA','HUY')),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    REAL NOT NULL,
    note          TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_phone_date ON stock_tx(phone_id, created_at);

-- Lịch sử thay đổi giá bán (nguồn: MANUAL - nhân viên, AI - áp dụng gợi ý)
CREATE TABLE IF NOT EXISTS price_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_id      INTEGER NOT NULL REFERENCES phone(id) ON DELETE CASCADE,
    old_price     REAL,
    new_price     REAL NOT NULL,
    source        TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- Nhật ký huấn luyện (telemetry): theo dõi chất lượng tri thức qua từng lần huấn luyện lại
CREATE TABLE IF NOT EXISTS model_run (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type    TEXT NOT NULL,                -- CAU_HINH | NHU_CAU
    phone_id      INTEGER,
    n_samples     INTEGER NOT NULL,
    params        TEXT NOT NULL,                -- JSON hệ số
    metrics       TEXT NOT NULL,                -- JSON: MSE, RMSE, MAE, R2
    model_file    TEXT,                         -- file tri thức (.sav)
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Gợi ý giá và quyết định của người quản lý (dữ liệu phản hồi: ngữ cảnh - hành động - kết quả)
CREATE TABLE IF NOT EXISTS price_suggestion (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_id          INTEGER NOT NULL REFERENCES phone(id) ON DELETE CASCADE,
    current_price     REAL NOT NULL,
    suggested_price   REAL NOT NULL,
    expected_qty      REAL,                     -- số lượng bán dự kiến / tuần
    expected_profit   REAL,                     -- lợi nhuận dự kiến / tuần
    strategy          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'CHO_DUYET',   -- CHO_DUYET | AP_DUNG | TU_CHOI
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    applied_at        TEXT
);
"""

# Truy vấn mặt hàng kèm tên hãng/chip — dùng chung cho nhiều API
PHONE_SELECT = """
SELECT p.*, b.name AS brand, b.point AS brand_point, c.name_cpu AS cpu, c.point AS cpu_point
FROM phone p
JOIN brand b ON b.id = p.id_brand
JOIN cpu c ON c.id = p.id_cpu
"""


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]
