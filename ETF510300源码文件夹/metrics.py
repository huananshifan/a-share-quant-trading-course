"""Performance metrics and in-sample/out-of-sample summaries."""
from __future__ import annotations
import numpy as np
import pandas as pd


def calculate_metrics(returns: pd.Series, nav: pd.Series, benchmark_returns: pd.Series,
                      benchmark_nav: pd.Series, turnover: pd.Series,
                      trading_days_per_year: int = 252, risk_free_rate: float = 0.01) -> dict:
    returns = pd.Series(returns, dtype=float).fillna(0.0)
    nav = pd.Series(nav, dtype=float).reset_index(drop=True)
    benchmark_returns = pd.Series(benchmark_returns, dtype=float).fillna(0.0)
    benchmark_nav = pd.Series(benchmark_nav, dtype=float).reset_index(drop=True)
    turnover = pd.Series(turnover, dtype=float).fillna(0.0)
    n = len(returns)
    if n == 0 or len(nav) == 0 or len(benchmark_nav) == 0:
        return {"trading_days": 0}
    total_return = float(nav.iloc[-1] - 1)
    benchmark_total_return = float(benchmark_nav.iloc[-1] - 1)
    years = n / trading_days_per_year
    cagr = float(nav.iloc[-1] ** (1 / years) - 1) if years > 0 and nav.iloc[-1] > 0 else float("nan")
    daily_std = returns.std(ddof=1)
    annual_vol = float(daily_std * np.sqrt(trading_days_per_year)) if pd.notna(daily_std) else 0.0
    daily_rf = (1 + risk_free_rate) ** (1 / trading_days_per_year) - 1
    sharpe = float(((returns.mean() - daily_rf) / daily_std) * np.sqrt(trading_days_per_year)) if pd.notna(daily_std) and daily_std > 0 else float("nan")
    dd = nav / nav.cummax() - 1
    return {
        "trading_days": n,
        "total_return": total_return,
        "annualized_return": cagr,
        "annualized_volatility": annual_vol,
        "max_drawdown": float(dd.min()),
        "sharpe_ratio": sharpe,
        "benchmark_total_return": benchmark_total_return,
        "excess_return_vs_benchmark": total_return - benchmark_total_return,
        "trading_events": int((turnover > 0).sum()),
        "average_daily_turnover": float(turnover.mean()),
    }


def summarize_periods(results: pd.DataFrame, train_ratio: float = 0.7) -> pd.DataFrame:
    if not 0.5 <= train_ratio <= 0.9:
        raise ValueError("训练/样本内占比建议设置在0.5到0.9之间。")
    n = len(results)
    split_at = int(n * train_ratio)
    if split_at < 2 or n - split_at < 2:
        raise ValueError("样本过少，无法可靠切分样本内和样本外区间。")
    rows = []
    for name, subset in [("全样本", results), ("样本内", results.iloc[:split_at]), ("样本外", results.iloc[split_at:])]:
        # Reset both NAV curves to 1 within each segment so metrics are segment-local.
        r = subset["strategy_return"].reset_index(drop=True)
        b = subset["benchmark_return"].reset_index(drop=True)
        nav = (1 + r).cumprod()
        bnav = (1 + b).cumprod()
        metrics = calculate_metrics(r, nav, b, bnav, subset["turnover"].reset_index(drop=True))
        metrics["period"] = name
        metrics["start_date"] = subset["date"].iloc[0].strftime("%Y-%m-%d")
        metrics["end_date"] = subset["date"].iloc[-1].strftime("%Y-%m-%d")
        rows.append(metrics)
    return pd.DataFrame(rows).set_index("period")
