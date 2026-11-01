"""Module học máy: huấn luyện, lưu/nạp file tri thức và tối ưu giá bán.

Hai mô hình hồi quy:
  1. Mô hình CAU_HINH (hồi quy tuyến tính bội): giá thị trường ~ cấu hình máy
       price = w0 + w1*brand_point + w2*cpu_point + w3*ram + w4*rom + w5*widescreen
               + w6*ppi + w7*battery + w8*camera + w9*release_year
     -> "giá tham chiếu" của một cấu hình, dùng khi nhập mặt hàng mới hoặc khi
        mặt hàng chưa đủ lịch sử bán.
  2. Mô hình NHU_CAU (hồi quy tuyến tính đơn, np.polyfit): mỗi mặt hàng một đường cầu
       Q = a*P + b     (Q: số lượng bán/tuần, P: giá bán; kỳ vọng a < 0)
     -> tìm giá P tối ưu theo chiến lược:
        LOI_NHUAN : max (P - c)*Q(P)   => P* = c/2 - b/(2a)
        DOANH_THU : max P*Q(P)         => P* = -b/(2a)
        XA_KHO    : max (P - c)*Q(P) với ràng buộc Q(P)*W >= tồn kho  => P <= (S/W - b)/a

File tri thức được lưu bằng pickle như ví dụ Chương 4 (pickle.dump / pickle.load).
"""
from __future__ import annotations

import datetime as dt
import json
import pickle
from pathlib import Path

import numpy as np

from .database import BASE_DIR, PHONE_SELECT, db
from .regression import (MultipleLinearRegression, SimpleLinearRegression, all_metrics,
                         evaluate_hold_out, evaluate_k_fold, hold_out_split)

MODEL_DIR = BASE_DIR / "models"
CONFIG_MODEL_FILE = MODEL_DIR / "cau_hinh.sav"

FEATURES = ["brand_point", "cpu_point", "ram", "rom", "widescreen", "ppi", "battery", "camera", "release_year"]
FEATURE_LABELS = {
    "brand_point": "Điểm thương hiệu", "cpu_point": "Điểm chip", "ram": "RAM (GB)", "rom": "ROM (GB)",
    "widescreen": "Màn hình (inch)", "ppi": "Mật độ điểm ảnh", "battery": "Pin (mAh)",
    "camera": "Camera (MP)", "release_year": "Năm ra mắt",
}

MIN_WEEKS = 8            # số tuần dữ liệu tối thiểu để tin cậy mô hình nhu cầu
DEMAND_MAX_AGE = dt.timedelta(days=1)
DEFAULT_MIN_MARGIN = 0.03
STRATEGIES = {"LOI_NHUAN": "Tối đa lợi nhuận", "DOANH_THU": "Tối đa doanh thu", "XA_KHO": "Giải phóng tồn kho"}


def round_price(v: float) -> float:
    return float(max(990_000, round(v / 100_000) * 100_000 - 10_000))


def _save(path: Path, obj) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def _load(path: Path):
    with open(path, "rb") as f:
        return pickle.load(f)


def _log_run(conn, model_type, phone_id, n, params, metrics, model_file):
    conn.execute(
        "INSERT INTO model_run(model_type, phone_id, n_samples, params, metrics, model_file) VALUES (?,?,?,?,?,?)",
        (model_type, phone_id, n, json.dumps(params), json.dumps(metrics), str(model_file.name)),
    )


# ===================================================== 1. Mô hình định giá theo cấu hình
def _config_factory():
    return MultipleLinearRegression(log_target=True)


def config_dataset(conn):
    rows = conn.execute(
        """SELECT m.*, b.name AS brand, b.point AS brand_point, c.name_cpu AS cpu, c.point AS cpu_point
           FROM market_phone m JOIN brand b ON b.id = m.id_brand JOIN cpu c ON c.id = m.id_cpu ORDER BY m.id"""
    ).fetchall()
    X = np.array([[r[f] for f in FEATURES] for r in rows], float)
    y = np.array([r["price"] for r in rows], float)
    return rows, X, y


def train_config_model() -> dict:
    with db() as conn:
        rows, X, y = config_dataset(conn)
        if len(y) < 15:
            raise ValueError("Cần tối thiểu 15 mẫu dữ liệu thị trường để huấn luyện")
        hold = evaluate_hold_out(_config_factory, X, y, test_size=0.2)
        kfold = evaluate_k_fold(_config_factory, X, y, k=5)
        model = _config_factory().fit(X, y, FEATURES)     # mô hình triển khai: học trên toàn bộ D
        coef = model.coefficients()
        metrics = {"hold_out": hold, "k_fold": kfold}
        _save(CONFIG_MODEL_FILE, {"model": model, "features": FEATURES, "trained_at": dt.datetime.now().isoformat(),
                                  "n_samples": int(len(y)), "metrics": metrics})
        _log_run(conn, "CAU_HINH", None, len(y), coef, metrics, CONFIG_MODEL_FILE)
    return config_model_info()


def load_config_model():
    if not CONFIG_MODEL_FILE.exists():
        train_config_model()
    return _load(CONFIG_MODEL_FILE)


def config_model_info() -> dict:
    know = load_config_model()
    model = know["model"]
    with db() as conn:
        rows, X, y = config_dataset(conn)
    # Biểu đồ giá thực tế vs dự đoán trên tập test (hold-out, mô hình chỉ học trên train)
    tr, te = hold_out_split(len(y), 0.2)
    m_tr = _config_factory().fit(X[tr], y[tr], FEATURES)
    pred = m_tr.predict(X[te])
    coef = model.coefficients()
    return {
        "trained_at": know["trained_at"],
        "n_samples": know["n_samples"],
        "metrics": know["metrics"],
        "intercept": coef["intercept"],
        # ln(giá) = w0 + Σ coef_i·x_i  =>  tăng x_i thêm 1 đơn vị thì giá nhân với e^coef_i
        "coefficients": [{"feature": f, "label": FEATURE_LABELS[f], "coef": coef[f],
                          "pct_per_unit": float(np.expm1(coef[f])),
                          "weight_01": float(model.w[i + 1])} for i, f in enumerate(FEATURES)],
        "test_points": [{"name": rows[i]["name"], "actual": float(y[i]), "predicted": float(p)}
                        for i, p in zip(te, pred)],
    }


def predict_config_price(features: dict) -> float:
    model = load_config_model()["model"]
    x = np.array([[float(features[f]) for f in FEATURES]])
    return float(model.predict(x)[0])


# ===================================================== 2. Mô hình nhu cầu theo giá
def weekly_sales(conn, phone_id: int, today: dt.date | None = None) -> list[dict]:
    """Tổng hợp dữ liệu bán theo tuần: (giá bình quân trong tuần, số lượng bán).

    Loại bỏ: tuần đang diễn ra (chưa đủ dữ liệu) và tuần có ngày hết hàng
    (nhu cầu thật bị che khuất bởi việc không có hàng để bán).
    """
    today = today or dt.date.today()
    txs = conn.execute(
        "SELECT type, quantity, unit_price, date(created_at) AS d FROM stock_tx WHERE phone_id=? ORDER BY created_at, id",
        (phone_id,),
    ).fetchall()
    prices = conn.execute(
        "SELECT new_price, date(created_at) AS d FROM price_history WHERE phone_id=? ORDER BY created_at, id",
        (phone_id,),
    ).fetchall()
    if not txs:
        return []
    first = dt.date.fromisoformat(txs[0]["d"])
    first_monday = first - dt.timedelta(days=first.weekday()) + dt.timedelta(days=7)  # bỏ tuần đầu không trọn
    this_monday = today - dt.timedelta(days=today.weekday())

    stock, sold, stockout = 0, {}, set()
    by_day = {}
    for t in txs:
        by_day.setdefault(t["d"], []).append(t)
    day = first
    while day < this_monday:
        for t in by_day.get(day.isoformat(), []):
            sign = 1 if t["type"] in ("NHAP", "TRA") else -1
            stock += sign * t["quantity"]
            if t["type"] == "BAN":
                sold[day] = sold.get(day, 0) + t["quantity"]
            elif t["type"] == "TRA":
                sold[day] = sold.get(day, 0) - t["quantity"]
        if stock <= 0:
            stockout.add(day - dt.timedelta(days=day.weekday()))
        day += dt.timedelta(days=1)

    def price_on(d: dt.date) -> float | None:
        p = None
        for r in prices:
            if dt.date.fromisoformat(r["d"]) <= d:
                p = r["new_price"]
            else:
                break
        return p

    weeks = []
    monday = first_monday
    while monday < this_monday:
        days = [monday + dt.timedelta(days=i) for i in range(7)]
        ps = [price_on(d) for d in days]
        if all(p is not None for p in ps):
            weeks.append({
                "week": monday.isoformat(),
                "price": float(np.mean(ps)),
                "qty": int(sum(sold.get(d, 0) for d in days)),
                "stockout": monday in stockout,
            })
        monday += dt.timedelta(days=7)
    return weeks


def _demand_file(phone_id: int) -> Path:
    return MODEL_DIR / f"nhu_cau_{phone_id}.sav"


def train_demand_model(phone_id: int, today: dt.date | None = None) -> dict:
    with db() as conn:
        weeks = weekly_sales(conn, phone_id, today)
        usable = [w for w in weeks if not w["stockout"]]
        result = {"phone_id": phone_id, "weeks": weeks, "n_weeks": len(usable), "trained_at": dt.datetime.now().isoformat()}
        if len(usable) < MIN_WEEKS or len({round(w["price"]) for w in usable}) < 2:
            result.update(valid=False, reason=f"Cần tối thiểu {MIN_WEEKS} tuần có bán và ít nhất 2 mức giá khác nhau")
            return result
        x = np.array([w["price"] for w in usable])
        y = np.array([w["qty"] for w in usable], float)
        hold = evaluate_hold_out(SimpleLinearRegression, x, y, test_size=0.2)
        kfold = evaluate_k_fold(SimpleLinearRegression, x, y, k=5)
        model = SimpleLinearRegression().fit(x, y)
        fit = all_metrics(y, model.predict(x))
        metrics = {"fit": fit, "hold_out": hold, "k_fold": kfold}
        result.update(model=model, a=model.a, b=model.b, metrics=metrics, valid=model.a < 0,
                      reason=None if model.a < 0 else "Hệ số a ≥ 0: dữ liệu chưa thể hiện quan hệ giá tăng thì bán giảm",
                      price_min=float(x.min()), price_max=float(x.max()))
        _save(_demand_file(phone_id), result)
        _log_run(conn, "NHU_CAU", phone_id, len(y), {"a": model.a, "b": model.b}, metrics, _demand_file(phone_id))
    return result


def load_demand_model(phone_id: int) -> dict:
    """Nạp file tri thức; tự huấn luyện lại khi chưa có hoặc đã cũ hơn DEMAND_MAX_AGE (dữ liệu bán mới)."""
    f = _demand_file(phone_id)
    if f.exists():
        know = _load(f)
        if dt.datetime.now() - dt.datetime.fromisoformat(know["trained_at"]) < DEMAND_MAX_AGE:
            return know
    return train_demand_model(phone_id)


def demand_info(phone_id: int) -> dict:
    r = dict(load_demand_model(phone_id))
    r.pop("model", None)
    return r


# ===================================================== 3. Tối ưu giá bán
def suggest_price(phone_id: int, strategy: str = "LOI_NHUAN", weeks_to_clear: int = 8,
                  min_margin: float = DEFAULT_MIN_MARGIN, save: bool = True) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"Chiến lược không hợp lệ: {strategy}")
    with db() as conn:
        phone = conn.execute(PHONE_SELECT + " WHERE p.id=?", (phone_id,)).fetchone()
    if phone is None:
        raise KeyError(phone_id)
    phone = dict(phone)
    cost, cur, stock = phone["cost_price"], phone["price"], phone["stock"]
    ref_price = predict_config_price(phone)
    dm = load_demand_model(phone_id)

    out = {
        "phone_id": phone_id, "name": phone["name"], "sku": phone["sku"], "strategy": strategy,
        "strategy_label": STRATEGIES[strategy], "cost_price": cost, "current_price": cur, "stock": stock,
        "reference_price": ref_price, "demand_valid": bool(dm.get("valid")), "notes": [],
    }

    if not dm.get("valid"):
        # Không đủ tri thức về nhu cầu -> giảm mức độ thông minh: dùng giá tham chiếu theo cấu hình
        suggested = round_price(max(ref_price, cost * (1 + min_margin)))
        out.update(suggested_price=suggested, expected_qty=None, expected_profit=None, curve=[],
                   method="Giá tham chiếu theo cấu hình (mô hình hồi quy bội)")
        out["notes"].append(dm.get("reason") or "Chưa có mô hình nhu cầu")
    else:
        a, b = dm["a"], dm["b"]
        q = lambda p: np.maximum(0.0, a * p + b)        # noqa: E731
        lo = max(cost * (1 + min_margin), dm["price_min"] * 0.9)
        hi = max(dm["price_max"] * 1.1, lo * 1.05)
        grid = np.linspace(lo, hi, 300)
        qty, revenue, profit = q(grid), grid * q(grid), (grid - cost) * q(grid)

        closed = {"LOI_NHUAN": cost / 2 - b / (2 * a), "DOANH_THU": -b / (2 * a)}
        if strategy == "XA_KHO":
            need = stock / max(1, weeks_to_clear)
            p_clear = (need - b) / a                     # giá cao nhất vẫn bán đủ need/tuần
            closed["XA_KHO"] = p_clear
            feasible = qty >= need
            if feasible.any():
                idx = int(np.argmax(np.where(feasible, profit, -np.inf)))
            else:
                idx = 0
                out["notes"].append(f"Với biên lợi nhuận tối thiểu {min_margin:.0%}, không thể bán hết {stock} máy "
                                    f"trong {weeks_to_clear} tuần; đề xuất mức giá thấp nhất cho phép.")
        else:
            idx = int(np.argmax(profit if strategy == "LOI_NHUAN" else revenue))
        p_star = float(grid[idx])
        if closed[strategy] < lo or closed[strategy] > hi:
            out["notes"].append("Nghiệm giải tích nằm ngoài vùng giá đã quan sát; giá đề xuất được giới hạn trong vùng an toàn.")
        suggested = round_price(p_star)
        cur_q = float(q(cur))
        out.update(
            method="Đường cầu hồi quy tuyến tính Q = a·P + b (np.polyfit)",
            a=a, b=b, r2=dm["metrics"]["fit"]["R2"], rmse=dm["metrics"]["fit"]["RMSE"],
            closed_form_price=float(closed[strategy]), price_range=[lo, hi],
            suggested_price=suggested,
            expected_qty=float(q(suggested)), expected_revenue=float(suggested * q(suggested)),
            expected_profit=float((suggested - cost) * q(suggested)),
            current_qty=cur_q, current_profit=float((cur - cost) * cur_q), current_revenue=float(cur * cur_q),
            weeks_of_stock_current=(stock / cur_q) if cur_q > 0 else None,
            weeks_of_stock_suggested=(stock / float(q(suggested))) if q(suggested) > 0 else None,
            curve=[{"price": float(p), "qty": float(qq), "revenue": float(r), "profit": float(pr)}
                   for p, qq, r, pr in zip(grid[::5], qty[::5], revenue[::5], profit[::5])],
            points=[{"price": w["price"], "qty": w["qty"]} for w in dm["weeks"] if not w["stockout"]],
        )
        if out["r2"] < 0.3:
            out["notes"].append("R² thấp: giá giải thích được ít biến động số lượng bán, cần thận trọng khi áp dụng.")

    if abs(ref_price - cur) / cur > 0.2:
        out["notes"].append("Giá hiện hành lệch hơn 20% so với giá tham chiếu theo cấu hình.")
    out["change_pct"] = (out["suggested_price"] - cur) / cur

    if save:
        with db() as conn:
            cur_row = conn.execute(
                """INSERT INTO price_suggestion(phone_id, current_price, suggested_price, expected_qty,
                                                expected_profit, strategy) VALUES (?,?,?,?,?,?)""",
                (phone_id, cur, out["suggested_price"], out.get("expected_qty"), out.get("expected_profit"), strategy),
            )
            out["suggestion_id"] = cur_row.lastrowid
    return out


def retrain_all() -> dict:
    """Huấn luyện lại toàn bộ tri thức trên dữ liệu mới (bảo trì và cải thiện - Chương 3)."""
    info = train_config_model()
    with db() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM phone")]
    demand = [train_demand_model(i) for i in ids]
    return {
        "config_r2_test": info["metrics"]["hold_out"]["test"]["R2"],
        "demand_models": len(demand),
        "demand_valid": sum(1 for d in demand if d.get("valid")),
    }
