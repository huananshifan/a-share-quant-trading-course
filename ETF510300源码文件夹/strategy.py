"""Simple moving-average trend strategy."""
from __future__ import annotations
import pandas as pd


def add_signals(prices: pd.DataFrame, short_window: int = 20,
                long_window: int = 60) -> pd.DataFrame:
    if short_window < 2 or long_window <= short_window:
        raise ValueError("均线参数必须满足：2 <= 短期均线 < 长期均线。")
    df = prices.copy()
    df["ma_short"] = df["close"].rolling(short_window, min_periods=short_window).mean()
    df["ma_long"] = df["close"].rolling(long_window, min_periods=long_window).mean()
    # Signal is calculated after the close. It may only be executed at the next session's open.
    df["signal"] = (df["ma_short"] > df["ma_long"]).astype(int)
    df.loc[df["ma_long"].isna(), "signal"] = 0
    df["position"] = df["signal"].shift(1).fillna(0).astype(int)
    return df
