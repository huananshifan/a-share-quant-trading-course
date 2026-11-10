"""Download or load daily ETF OHLC data and normalize its column names."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

COLUMN_ALIASES = {
    "date": ["date", "日期", "时间", "datetime", "交易日期", "time"],
    "open": ["open", "开盘", "开盘价", "今开"],
    "high": ["high", "最高", "最高价", "高"],
    "low": ["low", "最低", "最低价", "低"],
    "close": ["close", "收盘", "收盘价", "最新价", "价格"],
    "volume": ["volume", "成交量", "成交量(手)", "交易量", "vol"],
}


def _parse_numeric_column(series: pd.Series, column: str) -> pd.Series:
    """Parse numeric strings, including common volume suffixes such as 100M or 3.2亿."""
    text = series.astype(str).str.strip().str.replace(",", "", regex=False)
    text = text.replace({"": np.nan, "nan": np.nan, "None": np.nan, "--": np.nan, "-": np.nan})
    if column != "volume":
        return pd.to_numeric(text, errors="coerce")

    # Data portals often display human-readable volume units rather than raw numbers.
    parts = text.str.extract(r"^([-+]?(?:\d+\.?\d*|\.\d+))\s*(亿|万|[KkMmBb])?$")
    values = pd.to_numeric(parts[0], errors="coerce")
    suffix = parts[1].fillna("").str.lower()
    multipliers = suffix.map({"亿": 1e8, "万": 1e4, "k": 1e3, "m": 1e6, "b": 1e9}).fillna(1.0)
    return values * multipliers


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise ValueError("数据为空。请检查代码、日期范围或数据源是否可用。")
    rename = {}
    lower_to_original = {str(col).strip().lower(): col for col in df.columns}
    for standard, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower_to_original:
                rename[lower_to_original[alias.lower()]] = standard
                break
    df = df.rename(columns=rename)
    required = ["date", "open", "close"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"缺少必要字段 {missing}。CSV至少需要日期、开盘、收盘列；"
            "可使用英文 date/open/close 或中文 日期/开盘/收盘。"
        )
    if "high" not in df.columns:
        df["high"] = df["close"]
    if "low" not in df.columns:
        df["low"] = df["close"]
    if "volume" not in df.columns:
        df["volume"] = 0
    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    # Normalize dates such as "2022年10月14日" often found in downloaded tables.
    date_text = df["date"].astype(str).str.strip()
    date_text = (date_text.str.replace("年", "-", regex=False)
                          .str.replace("月", "-", regex=False)
                          .str.replace("日", "", regex=False))
    df["date"] = pd.to_datetime(date_text, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = _parse_numeric_column(df[col], col)
    df = df.dropna(subset=["date", "open", "close"])
    df["high"] = df["high"].fillna(df["close"])
    df["low"] = df["low"].fillna(df["close"])
    df["volume"] = df["volume"].fillna(0)
    df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    df = df[(df["open"] > 0) & (df["close"] > 0) & (df["high"] > 0) & (df["low"] > 0)]
    df = df[(df["high"] >= df[["open", "close", "low"]].max(axis=1))
            & (df["low"] <= df[["open", "close", "high"]].min(axis=1))]
    if len(df) < 100:
        raise ValueError(f"有效行情只有 {len(df)} 行，建议至少提供100个交易日的数据。")
    return df


def load_price_data(symbol: str, start_date: str, end_date: str,
                    csv_path: str | None = None) -> pd.DataFrame:
    """Load historical prices from CSV or AKShare's Eastmoney ETF endpoint.

    Use front-adjusted daily ETF bars. Network/data provider availability can vary;
    if download fails, export the same symbol's daily history to CSV and pass --csv.
    """
    if csv_path:
        path = Path(csv_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"找不到CSV文件：{path}")
        raw = pd.read_csv(path)
    else:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError(
                "尚未安装 akshare。请先运行：python -m pip install -r requirements.txt"
            ) from exc
        try:
            raw = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        except Exception as exc:
            raise RuntimeError(
                f"通过AKShare下载 {symbol} 行情失败：{exc}\n"
                "请检查网络，或从行情数据源导出包含日期、开盘、收盘的CSV，使用 --csv 路径.csv 重试。"
            ) from exc
    prices = _normalize_columns(raw)
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    prices = prices[(prices["date"] >= start) & (prices["date"] <= end)].copy()
    prices = prices.reset_index(drop=True)
    if len(prices) < 100:
        raise ValueError(
            f"{start_date}至{end_date}筛选后仅有{len(prices)}行有效数据，"
            "请扩大日期范围或确认CSV日期列格式。"
        )
    return prices
