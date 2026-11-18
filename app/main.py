"""Web API + giao diện cho Hệ thống quản lý kho điện thoại thông minh.

Chạy:  uvicorn app.main:app --reload     rồi mở http://127.0.0.1:8000
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import sqlite3
from contextlib import contextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ml
from .database import BASE_DIR, DB_PATH, PHONE_SELECT, db, init_db, rows_to_dicts

app = FastAPI(title="Hệ thống quản lý kho điện thoại thông minh")
STATIC_DIR = BASE_DIR / "static"


@app.on_event("startup")
def startup():
    if not DB_PATH.exists():
        from .seed import seed
        seed()
    init_db()


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def integrity_as_400(action: str):
    """Lỗi ràng buộc CSDL (trùng tên/SKU, sai khóa ngoại) -> HTTP 400 thay vì 500."""
    try:
        yield
    except sqlite3.IntegrityError as e:
        raise HTTPException(400, f"{action}: {e}")


def require_phone(conn, phone_id: int) -> None:
    if not conn.execute("SELECT 1 FROM phone WHERE id=?", (phone_id,)).fetchone():
        raise HTTPException(404, "Không tìm thấy mặt hàng")


# =============================================================== schema
class PhoneIn(BaseModel):
    sku: str
    name: str
    id_brand: int
    id_cpu: int
    ram: float = Field(gt=0)
    rom: float = Field(gt=0)
    widescreen: float = Field(gt=0)
    ppi: float = Field(gt=0)
    battery: float = Field(gt=0)
    camera: float = Field(gt=0)
    release_year: int
    cost_price: float = Field(gt=0)
    price: float = Field(gt=0)
    min_stock: int = 5
    image: str | None = None


class ConfigIn(BaseModel):
    id_brand: int
    id_cpu: int
    ram: float
    rom: float
    widescreen: float
    ppi: float
    battery: float
    camera: float
    release_year: int


class StockIn(BaseModel):
    phone_id: int
    quantity: int = Field(gt=0)
    unit_price: float | None = None
    note: str | None = None


class SuggestIn(BaseModel):
    phone_id: int | None = None
    strategy: str = "LOI_NHUAN"
    weeks_to_clear: int = Field(8, ge=1, le=52)
    min_margin: float = Field(ml.DEFAULT_MIN_MARGIN, ge=0, le=0.5)


class BrandIn(BaseModel):
    name: str
    point: float = Field(ge=0, le=10)


class CpuIn(BaseModel):
    name_cpu: str
    point: float = Field(ge=0, le=100)


class MarketIn(ConfigIn):
    name: str
    price: float = Field(gt=0)


# =============================================================== danh mục
@app.get("/api/brands")
def list_brands():
    with db() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM brand ORDER BY point DESC, name"))


@app.post("/api/brands")
def add_brand(b: BrandIn):
    with db() as conn, integrity_as_400("Không thêm được hãng"):
        cur = conn.execute("INSERT INTO brand(name, point) VALUES (?, ?)", (b.name, b.point))
        return {"id": cur.lastrowid}


@app.get("/api/cpus")
def list_cpus():
    with db() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM cpu ORDER BY point DESC"))


@app.post("/api/cpus")
def add_cpu(c: CpuIn):
    with db() as conn, integrity_as_400("Không thêm được chip"):
        cur = conn.execute("INSERT INTO cpu(name_cpu, point) VALUES (?, ?)", (c.name_cpu, c.point))
        return {"id": cur.lastrowid}


# =============================================================== mặt hàng
@app.get("/api/phones")
def list_phones(q: str | None = None):
    sql = PHONE_SELECT
    args: list = []
    if q:
        sql += " WHERE p.name LIKE ? OR p.sku LIKE ? OR b.name LIKE ?"
        args = [f"%{q}%"] * 3
    with db() as conn:
        phones = rows_to_dicts(conn.execute(sql + " ORDER BY b.point DESC, p.price DESC", args))
        sold30 = {r["phone_id"]: r["qty"] for r in conn.execute(
            """SELECT phone_id, SUM(quantity) AS qty FROM stock_tx
               WHERE type='BAN' AND created_at >= datetime('now','localtime','-30 days') GROUP BY phone_id""")}
    for p in phones:
        p["sold_30d"] = sold30.get(p["id"], 0)
        p["low_stock"] = p["stock"] <= p["min_stock"]
    return phones


@app.get("/api/phones/{phone_id}")
def get_phone(phone_id: int):
    with db() as conn:
        p = conn.execute(PHONE_SELECT + " WHERE p.id=?", (phone_id,)).fetchone()
        if not p:
            raise HTTPException(404, "Không tìm thấy mặt hàng")
        history = rows_to_dicts(conn.execute(
            "SELECT * FROM price_history WHERE phone_id=? ORDER BY created_at DESC, id DESC LIMIT 20", (phone_id,)))
    return dict(p) | {"price_history": history}


@app.post("/api/phones")
def create_phone(p: PhoneIn):
    with db() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO phone(sku, name, id_brand, id_cpu, ram, rom, widescreen, ppi, battery, camera,
                                     release_year, image, cost_price, price, stock, min_stock, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)""",
                (p.sku, p.name, p.id_brand, p.id_cpu, p.ram, p.rom, p.widescreen, p.ppi, p.battery, p.camera,
                 p.release_year, p.image, p.cost_price, p.price, p.min_stock, now()))
        except Exception as e:  # trùng SKU, sai khóa ngoại...
            raise HTTPException(400, f"Không thêm được mặt hàng: {e}")
        conn.execute("INSERT INTO price_history(phone_id, old_price, new_price, source, created_at) VALUES (?,?,?,?,?)",
                     (cur.lastrowid, None, p.price, "MANUAL", now()))
        return {"id": cur.lastrowid}


@app.put("/api/phones/{phone_id}")
def update_phone(phone_id: int, p: PhoneIn):
    with db() as conn:
        old = conn.execute("SELECT price FROM phone WHERE id=?", (phone_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Không tìm thấy mặt hàng")
        with integrity_as_400("Không sửa được mặt hàng"):
            conn.execute(
                """UPDATE phone SET sku=?, name=?, id_brand=?, id_cpu=?, ram=?, rom=?, widescreen=?, ppi=?, battery=?,
                       camera=?, release_year=?, image=?, cost_price=?, price=?, min_stock=? WHERE id=?""",
                (p.sku, p.name, p.id_brand, p.id_cpu, p.ram, p.rom, p.widescreen, p.ppi, p.battery, p.camera,
                 p.release_year, p.image, p.cost_price, p.price, p.min_stock, phone_id))
        if old["price"] != p.price:
            conn.execute("INSERT INTO price_history(phone_id, old_price, new_price, source, created_at) VALUES (?,?,?,?,?)",
                         (phone_id, old["price"], p.price, "MANUAL", now()))
    return {"ok": True}


@app.delete("/api/phones/{phone_id}")
def delete_phone(phone_id: int):
    with db() as conn:
        conn.execute("DELETE FROM phone WHERE id=?", (phone_id,))
    ml._demand_file(phone_id).unlink(missing_ok=True)
    return {"ok": True}


# =============================================================== nhập / xuất kho
@app.post("/api/stock/import")
def stock_import(s: StockIn):
    """Nhập kho: cộng tồn và cập nhật giá nhập bình quân gia quyền."""
    with db() as conn:
        p = conn.execute("SELECT stock, cost_price FROM phone WHERE id=?", (s.phone_id,)).fetchone()
        if not p:
            raise HTTPException(404, "Không tìm thấy mặt hàng")
        unit = s.unit_price or p["cost_price"]
        new_stock = p["stock"] + s.quantity
        avg_cost = (max(p["stock"], 0) * p["cost_price"] + s.quantity * unit) / new_stock
        conn.execute("UPDATE phone SET stock=?, cost_price=? WHERE id=?", (new_stock, round(avg_cost, -3), s.phone_id))
        conn.execute("INSERT INTO stock_tx(phone_id, type, quantity, unit_price, note, created_at) VALUES (?,?,?,?,?,?)",
                     (s.phone_id, "NHAP", s.quantity, unit, s.note, now()))
    return {"stock": new_stock, "cost_price": round(avg_cost, -3)}


@app.post("/api/stock/sell")
def stock_sell(s: StockIn):
    with db() as conn:
        p = conn.execute("SELECT stock, price FROM phone WHERE id=?", (s.phone_id,)).fetchone()
        if not p:
            raise HTTPException(404, "Không tìm thấy mặt hàng")
        if s.quantity > p["stock"]:
            raise HTTPException(400, f"Không đủ hàng: tồn {p['stock']}, cần xuất {s.quantity}")
        unit = s.unit_price or p["price"]
        conn.execute("UPDATE phone SET stock=stock-? WHERE id=?", (s.quantity, s.phone_id))
        conn.execute("INSERT INTO stock_tx(phone_id, type, quantity, unit_price, note, created_at) VALUES (?,?,?,?,?,?)",
                     (s.phone_id, "BAN", s.quantity, unit, s.note, now()))
    return {"stock": p["stock"] - s.quantity}


@app.get("/api/stock/tx")
def list_tx(phone_id: int | None = None, type: str | None = None, limit: int = 200):
    sql = """SELECT t.*, p.name, p.sku FROM stock_tx t JOIN phone p ON p.id = t.phone_id WHERE 1=1"""
    args: list = []
    if phone_id:
        sql += " AND t.phone_id=?"
        args.append(phone_id)
    if type:
        sql += " AND t.type=?"
        args.append(type)
    sql += " ORDER BY t.created_at DESC, t.id DESC LIMIT ?"
    args.append(min(limit, 2000))
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, args))


# =============================================================== tổng quan
@app.get("/api/dashboard")
def dashboard():
    with db() as conn:
        s = conn.execute("""SELECT COUNT(*) AS n_phones, COALESCE(SUM(stock),0) AS total_stock,
                                   COALESCE(SUM(stock*cost_price),0) AS stock_value,
                                   SUM(CASE WHEN stock <= min_stock THEN 1 ELSE 0 END) AS n_low
                            FROM phone""").fetchone()
        r30 = conn.execute("""SELECT COALESCE(SUM(t.quantity*t.unit_price),0) AS revenue,
                                     COALESCE(SUM(t.quantity*(t.unit_price-p.cost_price)),0) AS profit,
                                     COALESCE(SUM(t.quantity),0) AS qty
                              FROM stock_tx t JOIN phone p ON p.id=t.phone_id
                              WHERE t.type='BAN' AND t.created_at >= datetime('now','localtime','-30 days')""").fetchone()
        weekly = rows_to_dicts(conn.execute(
            """SELECT date(created_at, 'weekday 0', '-6 days') AS week,
                      SUM(quantity*unit_price) AS revenue, SUM(quantity) AS qty
               FROM stock_tx WHERE type='BAN'
                 AND created_at >= date('now','localtime','weekday 0','-6 days','-175 days')
               GROUP BY week ORDER BY week"""))
        top = rows_to_dicts(conn.execute(
            """SELECT p.id, p.name, SUM(t.quantity) AS qty, SUM(t.quantity*t.unit_price) AS revenue
               FROM stock_tx t JOIN phone p ON p.id=t.phone_id
               WHERE t.type='BAN' AND t.created_at >= datetime('now','localtime','-30 days')
               GROUP BY p.id ORDER BY qty DESC LIMIT 5"""))
        low = rows_to_dicts(conn.execute(
            "SELECT id, sku, name, stock, min_stock FROM phone WHERE stock <= min_stock ORDER BY stock"))
        # mặt hàng tồn lâu: tồn kho > 8 tuần bán (theo tốc độ bán 4 tuần gần nhất)
        slow = rows_to_dicts(conn.execute(
            """SELECT p.id, p.sku, p.name, p.stock,
                      COALESCE((SELECT SUM(quantity) FROM stock_tx t WHERE t.phone_id=p.id AND t.type='BAN'
                                AND t.created_at >= datetime('now','localtime','-28 days')),0)/4.0 AS weekly_rate
               FROM phone p"""))
        slow = [x | {"weeks_cover": x["stock"] / x["weekly_rate"] if x["weekly_rate"] else None}
                for x in slow if not x["weekly_rate"] or x["stock"] / x["weekly_rate"] > 8]
        pending = conn.execute("SELECT COUNT(*) FROM price_suggestion WHERE status='CHO_DUYET'").fetchone()[0]
    return dict(s) | {"revenue_30d": r30["revenue"], "profit_30d": r30["profit"], "qty_30d": r30["qty"],
                      "weekly": weekly, "top": top, "low_stock": low,
                      "slow_moving": sorted(slow, key=lambda x: -(x["weeks_cover"] or 1e9)), "pending_suggestions": pending}


# =============================================================== dữ liệu thị trường
@app.get("/api/market")
def list_market():
    with db() as conn:
        return rows_to_dicts(conn.execute(
            """SELECT m.*, b.name AS brand, c.name_cpu AS cpu FROM market_phone m
               JOIN brand b ON b.id=m.id_brand JOIN cpu c ON c.id=m.id_cpu ORDER BY m.price DESC"""))


@app.post("/api/market")
def add_market(m: MarketIn):
    with db() as conn, integrity_as_400("Không thêm được mẫu thị trường"):
        cur = conn.execute(
            """INSERT INTO market_phone(name, id_brand, id_cpu, ram, rom, widescreen, ppi, battery, camera,
                                        release_year, price) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (m.name, m.id_brand, m.id_cpu, m.ram, m.rom, m.widescreen, m.ppi, m.battery, m.camera,
             m.release_year, m.price))
    return {"id": cur.lastrowid}


@app.post("/api/market/import-csv")
async def import_market_csv(file: UploadFile = File(...)):
    """CSV cột: name,brand,cpu,ram,rom,widescreen,ppi,battery,camera,release_year,price"""
    text = (await file.read()).decode("utf-8-sig")
    added, errors = 0, []
    with db() as conn:
        brands = {r["name"].lower(): r["id"] for r in conn.execute("SELECT id, name FROM brand")}
        cpus = {r["name_cpu"].lower(): r["id"] for r in conn.execute("SELECT id, name_cpu FROM cpu")}
        for i, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
            try:
                conn.execute(
                    """INSERT INTO market_phone(name, id_brand, id_cpu, ram, rom, widescreen, ppi, battery, camera,
                                                release_year, price) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["name"], brands[row["brand"].strip().lower()], cpus[row["cpu"].strip().lower()],
                     float(row["ram"]), float(row["rom"]), float(row["widescreen"]), float(row["ppi"]),
                     float(row["battery"]), float(row["camera"]), int(row["release_year"]), float(row["price"])))
                added += 1
            except Exception as e:
                errors.append(f"Dòng {i}: {e!r}")
    return {"added": added, "errors": errors[:20]}


@app.get("/api/market/export-csv")
def export_market_csv():
    rows = list_market()
    buf = io.StringIO()
    cols = ["name", "brand", "cpu", "ram", "rom", "widescreen", "ppi", "battery", "camera", "release_year", "price"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    path = BASE_DIR / "data" / "market_phones.csv"
    path.write_text(buf.getvalue(), encoding="utf-8-sig")
    return FileResponse(path, filename="market_phones.csv", media_type="text/csv")


# =============================================================== module học máy
def _features(conn, c: ConfigIn) -> dict:
    b = conn.execute("SELECT point FROM brand WHERE id=?", (c.id_brand,)).fetchone()
    p = conn.execute("SELECT point FROM cpu WHERE id=?", (c.id_cpu,)).fetchone()
    if not b or not p:
        raise HTTPException(400, "Hãng hoặc chip không tồn tại")
    return c.model_dump() | {"brand_point": b["point"], "cpu_point": p["point"]}


@app.get("/api/ml/config-model")
def config_model():
    return ml.config_model_info()


@app.post("/api/ml/config-model/train")
def train_config():
    try:
        return ml.train_config_model()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/ml/predict-config")
def predict_config(c: ConfigIn):
    """Giá tham chiếu cho một cấu hình — dùng khi nhập mặt hàng mới (giống form nhập kho Chương 4)."""
    with db() as conn:
        feats = _features(conn, c)
    price = ml.predict_config_price(feats)
    rmse = ml.load_config_model()["metrics"]["hold_out"]["test"]["RMSE"]
    return {"price": price, "rounded": ml.round_price(price), "low": max(0, price - rmse), "high": price + rmse}


@app.get("/api/ml/demand/{phone_id}")
def demand_model(phone_id: int):
    with db() as conn:
        require_phone(conn, phone_id)
    return ml.demand_info(phone_id)


@app.post("/api/ml/demand/{phone_id}/train")
def train_demand(phone_id: int):
    with db() as conn:
        require_phone(conn, phone_id)
    r = dict(ml.train_demand_model(phone_id))
    r.pop("model", None)
    return r


@app.post("/api/ml/retrain-all")
def retrain_all():
    return ml.retrain_all()


@app.get("/api/ml/runs")
def model_runs(limit: int = 100):
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            """SELECT r.*, p.name AS phone_name FROM model_run r LEFT JOIN phone p ON p.id=r.phone_id
               ORDER BY r.id DESC LIMIT ?""", (limit,)))
    for r in rows:
        r["params"] = json.loads(r["params"])
        r["metrics"] = json.loads(r["metrics"])
    return rows


# =============================================================== tối ưu giá
@app.post("/api/pricing/suggest")
def suggest(s: SuggestIn):
    if s.phone_id is None:
        raise HTTPException(400, "Thiếu phone_id")
    try:
        return ml.suggest_price(s.phone_id, s.strategy, s.weeks_to_clear, s.min_margin)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy mặt hàng")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/pricing/suggest-all")
def suggest_all(s: SuggestIn):
    with db() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM phone ORDER BY id")]
        conn.execute("UPDATE price_suggestion SET status='TU_CHOI' WHERE status='CHO_DUYET'")   # thay bằng lượt gợi ý mới
    out = []
    for i in ids:
        r = ml.suggest_price(i, s.strategy, s.weeks_to_clear, s.min_margin)
        r.pop("curve", None)
        r.pop("points", None)
        out.append(r)
    return out


@app.get("/api/pricing/suggestions")
def list_suggestions(status: str | None = None, limit: int = 200):
    sql = """SELECT s.*, p.name, p.sku, p.price AS price_now, p.cost_price FROM price_suggestion s
             JOIN phone p ON p.id=s.phone_id"""
    args: list = []
    if status:
        sql += " WHERE s.status=?"
        args.append(status)
    with db() as conn:
        rows = rows_to_dicts(conn.execute(sql + " ORDER BY s.id DESC LIMIT ?", args + [limit]))
        # Đánh giá trực tuyến: so sánh số bán thực tế/tuần sau khi áp dụng với dự kiến
        for r in rows:
            if r["status"] == "AP_DUNG" and r["applied_at"]:
                a = conn.execute(
                    """SELECT COALESCE(SUM(quantity),0) AS qty FROM stock_tx
                       WHERE phone_id=? AND type='BAN' AND created_at >= ?""", (r["phone_id"], r["applied_at"])).fetchone()
                days = max(1, (dt.datetime.now() - dt.datetime.fromisoformat(r["applied_at"])).days)
                r["actual_weekly_qty"] = a["qty"] / days * 7 if days >= 7 else None
                r["days_since"] = days
    return rows


@app.post("/api/pricing/suggestions/{sid}/apply")
def apply_suggestion(sid: int):
    with db() as conn:
        s = conn.execute("SELECT * FROM price_suggestion WHERE id=?", (sid,)).fetchone()
        if not s:
            raise HTTPException(404, "Không tìm thấy gợi ý")
        if s["status"] != "CHO_DUYET":
            raise HTTPException(400, "Gợi ý này đã được xử lý (áp dụng hoặc từ chối) trước đó")
        old = conn.execute("SELECT price FROM phone WHERE id=?", (s["phone_id"],)).fetchone()
        conn.execute("UPDATE phone SET price=? WHERE id=?", (s["suggested_price"], s["phone_id"]))
        conn.execute("INSERT INTO price_history(phone_id, old_price, new_price, source, created_at) VALUES (?,?,?,?,?)",
                     (s["phone_id"], old["price"], s["suggested_price"], "AI", now()))
        conn.execute("UPDATE price_suggestion SET status='AP_DUNG', applied_at=? WHERE id=?", (now(), sid))
    return {"ok": True}


@app.post("/api/pricing/suggestions/{sid}/reject")
def reject_suggestion(sid: int):
    with db() as conn:
        s = conn.execute("SELECT status FROM price_suggestion WHERE id=?", (sid,)).fetchone()
        if not s:
            raise HTTPException(404, "Không tìm thấy gợi ý")
        if s["status"] != "CHO_DUYET":
            raise HTTPException(400, "Gợi ý này đã được xử lý (áp dụng hoặc từ chối) trước đó")
        conn.execute("UPDATE price_suggestion SET status='TU_CHOI' WHERE id=?", (sid,))
    return {"ok": True}


@app.get("/api/pricing/strategies")
def strategies():
    return ml.STRATEGIES


# =============================================================== giao diện
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
