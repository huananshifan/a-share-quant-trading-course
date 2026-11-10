"""Offline unit tests. Synthetic prices test mechanics only, never market performance."""
import sys
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import run_backtest
from metrics import summarize_periods
from data_loader import _normalize_columns


class BacktestTests(unittest.TestCase):
    def setUp(self):
        n = 400
        dates = pd.bdate_range("2023-01-02", periods=n)
        # Deterministic synthetic series solely for mechanical testing.
        t = np.arange(n)
        close = 3.8 + 0.0009 * t + 0.10 * np.sin(t / 10) + 0.035 * np.sin(t / 3.4)
        open_ = close * (1 + 0.002 * np.cos(t / 4))
        self.prices = pd.DataFrame({
            "date": dates,
            "open": open_,
            "high": np.maximum(open_, close) * 1.002,
            "low": np.minimum(open_, close) * 0.998,
            "close": close,
            "volume": 100000,
        })

    def test_backtest_columns_and_finite_nav(self):
        result = run_backtest(self.prices, 10, 30)
        for col in ["strategy_return", "benchmark_return", "strategy_nav", "benchmark_nav", "signal", "position"]:
            self.assertIn(col, result.columns)
        self.assertTrue(np.isfinite(result["strategy_nav"]).all())
        self.assertTrue(np.isfinite(result["benchmark_nav"]).all())
        self.assertAlmostEqual(float(result["strategy_nav"].iloc[0]), 1.0, places=8)

    def test_no_same_day_signal_execution(self):
        result = run_backtest(self.prices, 10, 30)
        expected = result["signal"].shift(1).fillna(0).astype(int)
        pd.testing.assert_series_equal(result["position"], expected, check_names=False)

    def test_costs_do_not_increase_nav_for_same_signals(self):
        free = run_backtest(self.prices, 10, 30, 0, 0)
        charged = run_backtest(self.prices, 10, 30, 3, 2)
        self.assertTrue((charged["strategy_nav"] <= free["strategy_nav"] + 1e-10).all())
        self.assertGreater(int((charged["turnover"] > 0).sum()), 0)

    def test_period_metrics_include_train_and_test(self):
        result = run_backtest(self.prices, 10, 30)
        metrics = summarize_periods(result, 0.7)
        self.assertEqual(set(metrics.index), {"全样本", "样本内", "样本外"})
        self.assertIn("max_drawdown", metrics.columns)
        self.assertIn("sharpe_ratio", metrics.columns)

    def test_chinese_csv_column_names_and_dates(self):
        raw = pd.DataFrame({
            "日期": [f"2020年1月{i:02d}日" for i in range(1, 121)],
            "开盘": np.linspace(2, 3, 120),
            "收盘": np.linspace(2, 3.2, 120),
            "高": np.maximum(np.linspace(2, 3, 120), np.linspace(2, 3.2, 120)) + 0.05,
            "低": np.minimum(np.linspace(2, 3, 120), np.linspace(2, 3.2, 120)) - 0.05,
            "交易量": ["100M"] * 120,
        })
        # Use actual business-day dates for parseability, then assert localized field names.
        raw["日期"] = pd.bdate_range("2020-01-01", periods=120).strftime("%Y年%m月%d日")
        clean = _normalize_columns(raw)
        self.assertIn("date", clean.columns)
        self.assertEqual(len(clean), 120)
        self.assertEqual(clean["date"].iloc[0].strftime("%Y-%m-%d"), "2020-01-01")
        self.assertEqual(float(clean["volume"].iloc[0]), 100_000_000.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
