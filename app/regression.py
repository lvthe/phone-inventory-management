"""Các kỹ thuật hồi quy dùng trong hệ thống.

Bám theo bài giảng Chương 2 (file 3, slide 14-17):
  - Hồi quy tuyến tính đơn: np.polyfit(x, y, 1) -> (a, b) với y = a*x + b
  - Sai số: err = sqrt(sum((yr - yn)**2) / n)   (RMSE)
  - Giải hệ tuyến tính bằng ma trận: S = A^-1 * B
Mở rộng cho hồi quy tuyến tính bội: hệ phương trình chuẩn (X^T X) w = X^T y,
giải theo đúng cách S = A^-1 B với A = X^T X, B = X^T y.

Đánh giá mô hình theo Chương 2 (file 2, slide 30-35): Hold-out, k-fold.
"""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------- độ đo sai số
def rmse(y_true, y_pred) -> float:
    """err = sqrt(sum((yr - yn)**2) / n) — công thức trong slide polyfit."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.sqrt(np.sum((y_pred - y_true) ** 2) / len(y_true)))


def mse(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.mean((y_pred - y_true) ** 2))


def mae(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.mean(np.abs(y_pred - y_true)))


def r2(y_true, y_pred) -> float:
    """Hệ số xác định R^2 = 1 - SS_res / SS_tot."""
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def all_metrics(y_true, y_pred) -> dict:
    return {
        "MSE": mse(y_true, y_pred),
        "RMSE": rmse(y_true, y_pred),
        "MAE": mae(y_true, y_pred),
        "R2": r2(y_true, y_pred),
    }


# ---------------------------------------------------------- chia dữ liệu
def hold_out_split(n: int, test_size: float = 0.2, seed: int = 42):
    """Hold-out: D = train ∪ test, hai tập rời nhau, |train| >> |test|."""
    rng = np.random.RandomState(seed)
    idx = rng.permutation(n)
    n_test = max(1, int(round(n * test_size)))
    return idx[n_test:], idx[:n_test]


def k_fold_indices(n: int, k: int = 5, seed: int = 42):
    """k-fold: chia D thành k phần rời nhau; mỗi lượt 1 phần làm test, k-1 phần làm train."""
    rng = np.random.RandomState(seed)
    folds = np.array_split(rng.permutation(n), k)
    for i in range(k):
        test = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        yield train, test


# ------------------------------------------------ hồi quy tuyến tính đơn
class SimpleLinearRegression:
    """y = a*x + b, ước lượng bằng np.polyfit (bình phương tối thiểu)."""

    def __init__(self):
        self.a = 0.0
        self.b = 0.0

    def fit(self, x, y):
        self.a, self.b = (float(v) for v in np.polyfit(np.asarray(x, float), np.asarray(y, float), 1))
        return self

    def predict(self, x):
        return np.polyval([self.a, self.b], np.asarray(x, float))

    def params(self) -> dict:
        return {"a": self.a, "b": self.b}


# ------------------------------------------------ hồi quy tuyến tính bội
class MultipleLinearRegression:
    """y = w0 + w1*x1 + ... + wm*xm.

    Hệ số w là nghiệm của hệ phương trình chuẩn A w = B với A = X^T X, B = X^T y,
    tức w = A^-1 B (cùng cách giải hệ S = A^-1 B trong slide SciPy linear algebra).
    Thêm hệ số điều chuẩn ridge nhỏ (lam) để A luôn khả nghịch khi các cột gần phụ thuộc.
    Dữ liệu được biến đổi về đoạn [0, 1] (min-max) trước khi giải, giống bước
    "Biến đổi dữ liệu" trong ví dụ Chương 4.

    log_target=True: hồi quy trên ln(y) rồi dự đoán y = e^(...). Dùng cho giá bán vì giá
    tăng theo tỉ lệ (%) khi cấu hình tăng, không tăng theo một lượng cố định.
    """

    def __init__(self, lam: float = 1e-6, log_target: bool = False):
        self.lam = lam
        self.log_target = log_target
        self.min_ = None
        self.range_ = None
        self.w = None          # hệ số trên dữ liệu đã chuẩn hóa, w[0] là hệ số tự do
        self.feature_names: list[str] = []

    def _design(self, X):
        Z = (np.asarray(X, float) - self.min_) / self.range_
        return np.hstack([np.ones((Z.shape[0], 1)), Z])

    def fit(self, X, y, feature_names: list[str] | None = None):
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        if self.log_target:
            y = np.log(y)
        self.min_ = X.min(axis=0)
        self.range_ = X.max(axis=0) - self.min_
        self.range_[self.range_ == 0] = 1.0
        Xd = self._design(X)
        A = Xd.T @ Xd + self.lam * np.eye(Xd.shape[1])
        A[0, 0] -= self.lam                      # không điều chuẩn hệ số tự do
        B = Xd.T @ y
        self.w = np.linalg.inv(A) @ B            # S = A^-1 B
        self.feature_names = feature_names or [f"x{i + 1}" for i in range(X.shape[1])]
        return self

    def predict(self, X):
        z = self._design(X) @ self.w
        return np.exp(z) if self.log_target else z

    def coefficients(self) -> dict:
        """Hệ số quy đổi về thang đo gốc của X: y (hoặc ln y) = intercept + sum(coef_i * x_i)."""
        coef = self.w[1:] / self.range_
        intercept = self.w[0] - float(np.sum(coef * self.min_))
        return {"intercept": float(intercept), **{n: float(c) for n, c in zip(self.feature_names, coef)}}


def evaluate_hold_out(model_factory, X, y, test_size=0.2, seed=42) -> dict:
    """Huấn luyện trên train, đo sai số trên test (không dùng mẫu train để đánh giá)."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    tr, te = hold_out_split(len(y), test_size, seed)
    m = model_factory().fit(X[tr], y[tr])
    return {
        "train": all_metrics(y[tr], m.predict(X[tr])),
        "test": all_metrics(y[te], m.predict(X[te])),
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
    }


def evaluate_k_fold(model_factory, X, y, k=5, seed=42) -> dict:
    """Trung bình sai số của k lượt kiểm tra chéo."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    k = max(2, min(k, len(y)))
    scores = []
    for tr, te in k_fold_indices(len(y), k, seed):
        m = model_factory().fit(X[tr], y[tr])
        scores.append(all_metrics(y[te], m.predict(X[te])))
    return {key: float(np.mean([s[key] for s in scores])) for key in scores[0]} | {"k": k}
