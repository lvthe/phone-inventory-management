"""Kiểm thử làm tròn giá bán.  Chạy:  python -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ml import round_price  # noqa: E402


class TestRoundPrice(unittest.TestCase):
    def test_retail_rounding(self):
        self.assertEqual(round_price(12_340_000), 12_290_000)
        self.assertEqual(round_price(12_360_000), 12_390_000)
        self.assertEqual(round_price(100_000), 990_000)

    def test_never_below_floor(self):
        # giá nhập 31,21 tr, biên tối thiểu 3% -> sàn 32.146.300; làm tròn thường cho 32.090.000
        floor = 31_210_000 * 1.03
        self.assertEqual(round_price(floor, floor), 32_190_000)
        # biên 0%: giá nhập tròn 100.000 không được bị trừ 10.000 thành dưới giá nhập
        self.assertEqual(round_price(31_200_000, 31_200_000), 31_290_000)
        # đã ở đúng mức ...90.000 thì giữ nguyên
        self.assertEqual(round_price(31_290_000, 31_290_000), 31_290_000)

    def test_floor_brute_force(self):
        for v in range(1_000_000, 40_000_000, 7_919):
            self.assertGreaterEqual(round_price(v, v), v)


if __name__ == "__main__":
    unittest.main()
