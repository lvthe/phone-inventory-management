"""Chạy module học máy từ dòng lệnh (giống cách gọi file tri thức trong ví dụ Chương 4).

  python -m app.ml_cli train                    huấn luyện lại toàn bộ, lưu file .sav
  python -m app.ml_cli predict cau_hinh.sav <brand_point> <cpu_point> <ram> <rom> <inch> <ppi> <pin> <camera> <nam>
  python -m app.ml_cli suggest <phone_id> [LOI_NHUAN|DOANH_THU|XA_KHO] [so_tuan]
"""
import pickle
import sys

import numpy as np

from . import ml


def main(argv: list[str]) -> None:
    if not argv or argv[0] not in ("train", "predict", "suggest"):
        print(__doc__)
        return
    if argv[0] == "train":
        print(ml.retrain_all())
    elif argv[0] == "predict":
        filename = argv[1]
        loaded = pickle.load(open(ml.MODEL_DIR / filename, "rb"))        # nạp file tri thức
        x = np.array([[float(v) for v in argv[2:]]])
        print(round(float(loaded["model"].predict(x)[0])))
    else:
        r = ml.suggest_price(int(argv[1]), argv[2] if len(argv) > 2 else "LOI_NHUAN",
                             int(argv[3]) if len(argv) > 3 else 8, save=False)
        print(f"{r['name']}: {r['current_price']:,.0f} -> {r['suggested_price']:,.0f} đ ({r['method']})")
        for n in r["notes"]:
            print(" -", n)


if __name__ == "__main__":
    main(sys.argv[1:])
