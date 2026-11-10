"""Daily-bar backtest with next-session-open execution and configurable trading costs."""
from __future__ import annotations
import numpy as np
import pandas as pd
from strategy import add_signals


def run_backtest(prices: pd.DataFrame, short_window: int = 20, long_window: int = 60,
                 commission_bps: float = 3.0, slippage_bps: float = 2.0) -> pd.DataFrame:
    """Run a long/cash strategy. One-way cost = commission + slippage in basis points.

    A signal computed from session t's close is executed at session t+1's open.
    The prior position earns the overnight close-to-open return; the new position
    earns the open-to-close return. Turnover costs are charged at the open.
    This is a simplified daily-bar model and does not simulate order-book fills,
    lot sizes, limit-up/down constraints, taxes, or partial fills.
    """
    if commission_bps < 0 or slippage_bps < 0:
        raise ValueError("佣金与滑点参数不能为负数。")
    df = add_signals(prices, short_window, long_window)
    previous_close = df["close"].shift(1)
    overnight_return = (df["open"] / previous_close - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    intraday_return = (df["close"] / df["open"] - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    held_overnight = df["position"].shift(1).fillna(0).astype(int)
    turnover = (df["position"] - held_overnight).abs()
    cost_per_side = (commission_bps + slippage_bps) / 10000.0
    gross_growth = (1 + held_overnight * overnight_return) * (1 + df["position"] * intraday_return)
    net_growth = gross_growth * (1 - turnover * cost_per_side)
    df["overnight_return"] = overnight_return
    df["intraday_return"] = intraday_return
    df["held_overnight"] = held_overnight
    df["turnover"] = turnover
    df["strategy_return"] = (net_growth - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    df["benchmark_return"] = df["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    df["strategy_nav"] = (1 + df["strategy_return"]).cumprod()
    df["benchmark_nav"] = (1 + df["benchmark_return"]).cumprod()
    df["excess_nav_ratio"] = df["strategy_nav"] / df["benchmark_nav"]
    df["turnover_event"] = (turnover > 0).astype(int)
    return df
