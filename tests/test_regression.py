"""Kiểm thử module hồi quy.  Chạy:  python -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.regression import (MultipleLinearRegression, SimpleLinearRegression, evaluate_hold_out,  # noqa: E402
                            hold_out_split, k_fold_indices, r2, rmse)


class TestRegression(unittest.TestCase):
    def test_polyfit_example_from_slide(self):
        """Ví dụ slide SciPy: y = 0.8x - 4 cộng nhiễu, polyfit phải tìm lại a, b gần đúng."""
        rng = np.random.RandomState(0)
        x = np.linspace(-5, 5, 50)
        yn = np.polyval([0.8, -4], x) + rng.randn(50)
        m = SimpleLinearRegression().fit(x, yn)
        # sai số chuẩn của a ≈ σ/(std(x)·√n) ≈ 0.05 -> cho phép lệch ~4 lần
        self.assertAlmostEqual(m.a, 0.8, delta=0.2)
        self.assertAlmostEqual(m.b, -4, delta=0.4)
        np.testing.assert_allclose([m.a, m.b], np.polyfit(x, yn, 1))
        yr = m.predict(x)
        self.assertAlmostEqual(rmse(yn, yr), np.sqrt(sum((yr - yn) ** 2) / 50))

    def test_linear_system_from_slide(self):
        """S = A^-1 B với hệ x+3y+5z=0, 2x+5y+z=-7, 2x+3y+8z=4 -> (1, -2, 1)."""
        A = np.array([[1, 3, 5], [2, 5, 1], [2, 3, 8]], float)
        B = np.array([0, -7, 4], float)
        np.testing.assert_allclose(np.linalg.inv(A) @ B, [1, -2, 1], atol=1e-9)

    def test_multiple_regression_matches_lstsq(self):
        rng = np.random.RandomState(1)
        X = rng.rand(80, 4) * [10, 100, 5, 1000]
        y = 3 + X @ [2.0, -0.5, 7.0, 0.01] + rng.randn(80) * 0.1
        m = MultipleLinearRegression(lam=0).fit(X, y)
        coef = m.coefficients()
        ref, *_ = np.linalg.lstsq(np.hstack([np.ones((80, 1)), X]), y, rcond=None)
        self.assertAlmostEqual(coef["intercept"], ref[0], places=6)
        np.testing.assert_allclose([coef[f"x{i + 1}"] for i in range(4)], ref[1:], rtol=1e-6)
        self.assertGreater(r2(y, m.predict(X)), 0.999)

    def test_log_target(self):
        rng = np.random.RandomState(2)
        X = rng.rand(60, 2) * 10
        y = np.exp(1 + 0.3 * X[:, 0] + 0.1 * X[:, 1])
        m = MultipleLinearRegression(lam=0, log_target=True).fit(X, y)
        np.testing.assert_allclose(m.predict(X), y, rtol=1e-6)

    def test_splits_are_disjoint(self):
        tr, te = hold_out_split(100, 0.2)
        self.assertEqual(len(te), 20)
        self.assertFalse(set(tr) & set(te))
        seen = []
        for tr, te in k_fold_indices(23, 5):
            self.assertFalse(set(tr) & set(te))
            seen.extend(te)
        self.assertEqual(sorted(seen), list(range(23)))

    def test_hold_out_reports_test_metrics(self):
        x = np.arange(30, dtype=float)
        y = 2 * x + 1
        r = evaluate_hold_out(SimpleLinearRegression, x, y)
        self.assertAlmostEqual(r["test"]["R2"], 1.0, places=9)
        self.assertEqual(r["n_train"] + r["n_test"], 30)


if __name__ == "__main__":
    unittest.main()
