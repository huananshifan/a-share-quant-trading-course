"""Run the A-share ETF moving-average backtest and export report artifacts."""
from __future__ import annotations
import argparse
from datetime import date
from pathlib import Path
import json
import hashlib
import platform
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from data_loader import load_price_data
from backtest import run_backtest
from metrics import summarize_periods
from report_docx import create_word_report

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A股ETF双均线策略回测（教学项目）")
    parser.add_argument("--symbol", default="510300", help="ETF代码，默认510300（沪深300ETF）")
    parser.add_argument("--start", default="20180101", help="开始日期 YYYYMMDD，默认20180101")
    parser.add_argument("--end", default=date.today().strftime("%Y%m%d"), help="结束日期 YYYYMMDD，默认今天")
    parser.add_argument("--short-window", type=int, default=20, help="短期均线窗口，默认20")
    parser.add_argument("--long-window", type=int, default=60, help="长期均线窗口，默认60")
    parser.add_argument("--commission-bps", type=float, default=3.0, help="单边佣金基点，默认3，即0.03%")
    parser.add_argument("--slippage-bps", type=float, default=2.0, help="单边滑点基点，默认2，即0.02%")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="样本内区间占比，默认0.7")
    parser.add_argument("--csv", default=None, help="可选：本地历史行情CSV路径")
    parser.add_argument("--csv-adjustment", choices=["qfq", "hfq", "none", "unknown"], default="unknown",
                        help="使用本地CSV时标注其复权口径；默认unknown，不会擅自假定前复权")
    return parser



def write_supplementary_outputs(prices: pd.DataFrame, results: pd.DataFrame, args: argparse.Namespace) -> None:
    """Create calendar-year, parameter-sensitivity, drawdown, MA and data-QA outputs.

    Parameter comparisons are descriptive robustness checks only. The default 20/60
    strategy remains the primary model; alternate windows are not selected using the
    held-out period.
    """
    # Calendar-year price returns based on the same return stream as the main run.
    annual_rows = []
    for year, subset in results.groupby(results["date"].dt.year, sort=True):
        strategy_return = float((1.0 + subset["strategy_return"]).prod() - 1.0)
        benchmark_return = float((1.0 + subset["benchmark_return"]).prod() - 1.0)
        annual_rows.append({
            "calendar_year": int(year),
            "trading_days": int(len(subset)),
            "strategy_price_return": strategy_return,
            "benchmark_price_return": benchmark_return,
            "return_difference_strategy_minus_benchmark": strategy_return - benchmark_return,
        })
    pd.DataFrame(annual_rows).to_csv(OUTPUT_DIR / "annual_returns.csv", index=False, encoding="utf-8-sig", float_format="%.8f")

    # A small, predeclared comparison set. The primary model is still the default 20/60.
    parameter_rows = []
    configurations = [(10, 30), (20, 60), (30, 90), (50, 120), (50, 200), (100, 200)]
    for short_window, long_window in configurations:
        candidate = run_backtest(
            prices, short_window, long_window, args.commission_bps, args.slippage_bps
        )
        cm = summarize_periods(candidate, args.train_ratio)
        full, train, test = cm.loc["全样本"], cm.loc["样本内"], cm.loc["样本外"]
        parameter_rows.append({
            "short_window": short_window,
            "long_window": long_window,
            "config": f"SMA{short_window}/{long_window}",
            "full_price_return": full["total_return"],
            "full_annualized_return": full["annualized_return"],
            "full_max_drawdown": full["max_drawdown"],
            "full_sharpe": full["sharpe_ratio"],
            "in_sample_price_return": train["total_return"],
            "out_of_sample_price_return": test["total_return"],
            "benchmark_price_return": full["benchmark_total_return"],
            "position_changes": int(full["trading_events"]),
        })
    pd.DataFrame(parameter_rows).to_csv(OUTPUT_DIR / "parameter_sensitivity.csv", index=False, encoding="utf-8-sig", float_format="%.8f")

    # Drawdown chart: compares peak-to-trough paths, not only terminal returns.
    strategy_dd = results["strategy_nav"] / results["strategy_nav"].cummax() - 1.0
    benchmark_dd = results["benchmark_nav"] / results["benchmark_nav"].cummax() - 1.0
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.plot(results["date"], strategy_dd, label="SMA 20/60 strategy", linewidth=1.5)
    ax.plot(results["date"], benchmark_dd, label="Buy-and-hold price benchmark", linewidth=1.2)
    ax.set_title("Drawdown Comparison (Price-Return Backtest)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown from Running Peak")
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "drawdown_curve.png", dpi=170)
    plt.close(fig)

    # Close and MAs for a visually interpretable strategy chart.
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.plot(results["date"], results["close"], label="Close", linewidth=1.0, alpha=0.85)
    ax.plot(results["date"], results["ma_short"], label=f"SMA {args.short_window}", linewidth=1.2)
    ax.plot(results["date"], results["ma_long"], label=f"SMA {args.long_window}", linewidth=1.2)
    ax.set_title(f"510300 Close and Moving Averages ({results['date'].iloc[0].date()} to {results['date'].iloc[-1].date()})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (CNY; adjustment status unverified)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "price_moving_averages.png", dpi=170)
    plt.close(fig)

    # Reproducible local CSV QA, performed before any cleaning by the normalizer.
    qa = []
    def add_check(name: str, passed: bool, details: str) -> None:
        qa.append({"check": name, "status": "PASS" if passed else "REVIEW", "details": details})

    if args.csv:
        raw = pd.read_csv(args.csv)
        columns = {str(c).strip().lower(): c for c in raw.columns}
        aliases = {
            "date": ["date", "日期", "时间", "datetime", "交易日期", "time"],
            "open": ["open", "开盘", "开盘价", "今开"],
            "high": ["high", "最高", "最高价", "高"],
            "low": ["low", "最低", "最低价", "低"],
            "close": ["close", "收盘", "收盘价", "最新价", "价格"],
        }
        found = {k: next((columns[a.lower()] for a in v if a.lower() in columns), None) for k, v in aliases.items()}
        required_found = all(found[k] is not None for k in ["date", "open", "high", "low", "close"])
        add_check("核心字段", required_found, f"原始行数={len(raw)}；识别字段={found}")
        add_check("空数据行", not raw.empty, f"原始数据行={len(raw)}")
        if found["date"] is not None:
            dates = pd.to_datetime(raw[found["date"]], errors="coerce")
            add_check("日期完整", bool(dates.notna().all()), f"无法解析日期数={int(dates.isna().sum())}")
            add_check("日期唯一", int(dates.duplicated().sum()) == 0, f"重复日期数={int(dates.duplicated().sum())}")
            add_check("日期升序", bool(dates.is_monotonic_increasing), f"原始数据按日期升序={bool(dates.is_monotonic_increasing)}")
        if required_found:
            nums = {k: pd.to_numeric(raw[v], errors="coerce") for k, v in found.items() if k != "date"}
            miss = sum(int(nums[k].isna().sum()) for k in nums)
            add_check("OHLC数值完整", miss == 0, f"开高低收非数值/缺失单元格数={miss}")
            positive = pd.Series(True, index=raw.index)
            for k in ["open", "high", "low", "close"]:
                positive &= nums[k] > 0
            add_check("价格为正", bool(positive.all()), f"非正价格行数={int((~positive).sum())}")
            valid = (nums["high"] >= pd.concat([nums["open"], nums["close"], nums["low"]], axis=1).max(axis=1)) & (nums["low"] <= pd.concat([nums["open"], nums["close"], nums["high"]], axis=1).min(axis=1))
            add_check("OHLC逻辑一致", bool(valid.all()), f"高低价关系异常行数={int((~valid).sum())}")
    else:
        add_check("本地输入CSV", True, "本次使用远程行情接口；请查看数据源和请求参数记录。")
    add_check("复权口径", args.csv_adjustment != "unknown" if args.csv else True,
              f"本次标记={args.csv_adjustment if args.csv else 'AKShare adjust=qfq'}；请根据来源说明核验。")
    external_ok = False
    external_detail = "输入数据不含 2026-10-20 或 OHLC 值不同；请重新核对数据源。"
    if args.csv and all(found.get(k) is not None for k in ["date", "open", "high", "low", "close"]):
        date_values = pd.to_datetime(raw[found["date"]], errors="coerce").dt.strftime("%Y-%m-%d")
        match_rows = raw.loc[date_values == "2026-10-20"]
        if not match_rows.empty:
            r = match_rows.iloc[-1]
            actual = [float(pd.to_numeric(pd.Series([r[found[k]]]), errors="coerce").iloc[0]) for k in ["open", "high", "low", "close"]]
            expected = [4.229, 4.250, 4.186, 4.220]
            external_ok = all(abs(a - e) <= 0.001 for a, e in zip(actual, expected))
            external_detail = f"2026-10-20 实际OHLC={actual}；公开行情抽查值={expected}；容差=0.001。"
    add_check("外部行情抽查", external_ok, external_detail + " 参考：https://summary.jrj.com.cn/stock/sh/510300")
    pd.DataFrame(qa).to_csv(OUTPUT_DIR / "data_quality.csv", index=False, encoding="utf-8-sig")

def write_report(results: pd.DataFrame, metrics: pd.DataFrame, args: argparse.Namespace) -> None:
    full = metrics.loc["全样本"]
    train = metrics.loc["样本内"]
    test = metrics.loc["样本外"]
    source_label = f"本地CSV文件：{Path(args.csv).name}" if args.csv else "AKShare 的 ETF 历史行情接口 fund_etf_hist_em（东方财富历史行情）"
    adjustment_label = (args.csv_adjustment if args.csv else "qfq（前复权）")
    adjustment_description = {
        "qfq": "前复权",
        "hfq": "后复权",
        "none": "不复权",
        "unknown": "未核验；提交前必须确认数据源的复权设置",
    }.get(args.csv_adjustment, "前复权") if args.csv else "前复权"
    report = f'''# 量化交易课程项目回测报告（自动生成）

> 本报告根据本次输入行情和代码自动生成。请在提交前核对行情是否来自真实、可核验的数据源，并检查运行环境与图表；历史回测不代表未来收益。

## 1. 项目概述

本项目以沪深300 ETF（代码：{args.symbol}）为交易标的，构建短期/长期移动平均线趋势策略，并以同一 ETF 的买入并持有收益作为基准。策略在收盘后计算信号，在下一交易日开盘执行。回测包含单边佣金与滑点假设。

## 2. 数据来源与区间

- 数据来源：{source_label}
- 价格复权口径：{adjustment_label}（{'请核对CSV来源设置' if args.csv else '来自接口参数adjust=qfq'}）
- 代码：{args.symbol}
- 实际数据区间：{results['date'].iloc[0].strftime('%Y-%m-%d')} 至 {results['date'].iloc[-1].strftime('%Y-%m-%d')}
- 有效交易日：{len(results)}
- 价格处理：使用开盘价和收盘价近似模拟隔夜与日内收益；复权说明：{adjustment_description}。由于输入文件未标注复权口径，本次结果仅解释为所提供价格序列上的价格收益，不应视为已包含现金分红再投资的总回报。

## 3. 策略规则

1. 计算收盘价的{args.short_window}日简单移动平均线和{args.long_window}日简单移动平均线。
2. 短期均线高于长期均线时，目标仓位为1（持有）；否则仓位为0（空仓）。本策略不做融券做空。
3. 收盘后产生的信号在下一交易日开盘执行，避免在同一根日线收盘价上产生信号并假设同时成交。
4. 单边佣金假设为{args.commission_bps:.1f}基点，单边滑点假设为{args.slippage_bps:.1f}基点；每次仓位变化时计入成本。

## 4. 回测设置与局限

- 样本内/样本外切分：按时间先后划分，样本内约{args.train_ratio:.0%}，样本外约{1-args.train_ratio:.0%}；切分前未进行参数优化。
- 基准：同一ETF买入并持有。
- 交易日年化参数：252；夏普比率采用年化无风险利率1%的假设。
- 这是基于日线OHLC的简化模型，不模拟盘口成交、整手限制、涨跌停无法成交、实际券商费率差异、跟踪误差及税费变化。复权价格仅用于连续价格序列的收益近似，不代表历史真实成交单；本地CSV的复权口径须由提交者核验。

## 5. 结果

详见 `outputs/metrics.csv`、`outputs/backtest_results.csv`、`outputs/trades.csv`、`outputs/cost_sensitivity.csv`、`outputs/equity_curve.png` 与 `outputs/report_auto.docx`。

| 区间 | 日期范围 | 策略累计收益 | 策略年化收益 | 最大回撤 | 夏普比率 | 基准累计收益 | 超额收益 |
|---|---|---:|---:|---:|---:|---:|---:|
| 全样本 | {full['start_date']} 至 {full['end_date']} | {full['total_return']:.2%} | {full['annualized_return']:.2%} | {full['max_drawdown']:.2%} | {full['sharpe_ratio']:.3f} | {full['benchmark_total_return']:.2%} | {full['excess_return_vs_benchmark']:.2%} |
| 样本内 | {train['start_date']} 至 {train['end_date']} | {train['total_return']:.2%} | {train['annualized_return']:.2%} | {train['max_drawdown']:.2%} | {train['sharpe_ratio']:.3f} | {train['benchmark_total_return']:.2%} | {train['excess_return_vs_benchmark']:.2%} |
| 样本外 | {test['start_date']} 至 {test['end_date']} | {test['total_return']:.2%} | {test['annualized_return']:.2%} | {test['max_drawdown']:.2%} | {test['sharpe_ratio']:.3f} | {test['benchmark_total_return']:.2%} | {test['excess_return_vs_benchmark']:.2%} |

## 6. 结果分析

- 全样本策略累计收益为 {full['total_return']:.2%}，基准为 {full['benchmark_total_return']:.2%}，累计收益差为 {full['excess_return_vs_benchmark']:.2%}；策略最大回撤为 {full['max_drawdown']:.2%}，夏普比率为 {full['sharpe_ratio']:.3f}。
- 样本内策略累计收益为 {train['total_return']:.2%}，样本外为 {test['total_return']:.2%}。{'样本外收益低于样本内，提示趋势信号可能受到市场阶段影响。' if test['total_return'] < train['total_return'] else '样本外收益不低于样本内，但仍需结合区间长度和风险指标判断稳健性。'}
- 双均线策略规则简单且可解释，但存在滞后性，震荡行情中可能反复进出。结论应以本次真实行情回测为准，不应只挑选表现较好的区间。

## 7. 逐年表现、参数稳健性与数据质量

- `annual_returns.csv`：按自然年度列出策略与基准价格收益，用于识别市场状态差异。
- `parameter_sensitivity.csv`：比较事先列出的多组均线窗口；该表用于展示参数敏感性，不代表应从全样本中挑选最优参数。主结果仍为 SMA 20/60。
- `data_quality.csv`：记录本地输入的字段、日期与 OHLC 检查。
- `drawdown_curve.png` 和 `price_moving_averages.png`：补充展示回撤风险与均线信号。

## 8. 可复现说明

1. 安装 `requirements.txt` 中的依赖。
2. 运行 `python main.py --symbol {args.symbol} --start {args.start} --end {args.end} --short-window {args.short_window} --long-window {args.long_window} --train-ratio {args.train_ratio}`。
3. 运行完成后，查看 `outputs/` 文件夹。`run_metadata.json` 记录参数和数据区间；`prices.csv` 保存本次行情快照。

## 9. 小组信息

- 课程/班级：待填写
- 组号与组员：待填写
- 代码仓库地址：提交GitHub后填写
'''
    (OUTPUT_DIR / "report_auto.md").write_text(report, encoding="utf-8")


def main() -> None:
    args = build_parser().parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prices = load_price_data(args.symbol, args.start, args.end, args.csv)
    if args.csv and args.csv_adjustment == "unknown":
        print("提醒：本地CSV复权口径未标注，请在报告中核对/说明。")
    results = run_backtest(prices, args.short_window, args.long_window,
                           args.commission_bps, args.slippage_bps)
    metrics = summarize_periods(results, args.train_ratio)
    results.to_csv(OUTPUT_DIR / "backtest_results.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    prices.to_csv(OUTPUT_DIR / "prices.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    metrics.to_csv(OUTPUT_DIR / "metrics.csv", encoding="utf-8-sig", float_format="%.8f")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(results["date"], results["strategy_nav"], label="Dual MA Strategy", linewidth=1.8)
    ax.plot(results["date"], results["benchmark_nav"], label="Buy & Hold Benchmark", linewidth=1.5)
    ax.set_title(f"{args.symbol} ETF: Strategy vs Buy-and-Hold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized NAV (start = 1.0)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "equity_curve.png", dpi=160)
    plt.close(fig)
    results[["date", "close", "ma_short", "ma_long", "signal", "position", "turnover"]].to_csv(
        OUTPUT_DIR / "signals.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    trades = results.loc[results["turnover"] > 0,
                         ["date", "open", "close", "held_overnight", "position", "turnover"]].copy()
    trades["action"] = trades.apply(lambda r: "BUY" if r["position"] > r["held_overnight"] else "SELL", axis=1)
    trades["execution_price_proxy"] = trades["open"]
    trades["assumed_one_way_cost_bps"] = args.commission_bps + args.slippage_bps
    trades.to_csv(OUTPUT_DIR / "trades.csv", index=False, encoding="utf-8-sig", float_format="%.8f")

    # Cost sensitivity: zero cost, base cost (3+2 bps/side), and doubled base assumptions.
    cost_rows = []
    for label, commission, slippage in [
        ("无交易成本", 0.0, 0.0),
        ("基准成本", args.commission_bps, args.slippage_bps),
        ("双倍交易成本", args.commission_bps * 2, args.slippage_bps * 2),
    ]:
        cost_result = run_backtest(prices, args.short_window, args.long_window, commission, slippage)
        cm = summarize_periods(cost_result, args.train_ratio).loc["全样本"]
        cost_rows.append({"cost_scenario": label, "commission_bps_per_side": commission,
                          "slippage_bps_per_side": slippage, "total_return": cm["total_return"],
                          "annualized_return": cm["annualized_return"], "max_drawdown": cm["max_drawdown"],
                          "sharpe_ratio": cm["sharpe_ratio"], "trading_events": cm["trading_events"]})
    pd.DataFrame(cost_rows).to_csv(OUTPUT_DIR / "cost_sensitivity.csv", index=False,
                                   encoding="utf-8-sig", float_format="%.8f")
    # Hash the normalized snapshot, making the exact backtest data auditable.
    price_snapshot = (OUTPUT_DIR / "prices.csv").read_bytes()
    metadata = {
        "symbol": args.symbol, "start_requested": args.start, "end_requested": args.end,
        "start_actual": results["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_actual": results["date"].iloc[-1].strftime("%Y-%m-%d"),
        "rows": len(results), "short_window": args.short_window, "long_window": args.long_window,
        "commission_bps_per_side": args.commission_bps, "slippage_bps_per_side": args.slippage_bps,
        "train_ratio": args.train_ratio, "csv_input": (Path(args.csv).name if args.csv else None),
        "data_source": ("local_csv" if args.csv else "AKShare fund_etf_hist_em / Eastmoney"),
        "price_adjustment": (args.csv_adjustment if args.csv else "qfq"),
        "downloaded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "price_snapshot_sha256": hashlib.sha256(price_snapshot).hexdigest(),
        "input_file_sha256": hashlib.sha256(Path(args.csv).read_bytes()).hexdigest() if args.csv else None,
        "return_basis": "provided_price_series; dividend-adjustment/total-return status unverified" if args.csv_adjustment == "unknown" else f"price_adjustment={args.csv_adjustment}",
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "project_version": "1.1.0",
    }
    (OUTPUT_DIR / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_supplementary_outputs(prices, results, args)
    write_report(results, metrics, args)
    create_word_report(
        OUTPUT_DIR / "report_auto.docx",
        metrics,
        metadata,
        OUTPUT_DIR / "equity_curve.png",
        OUTPUT_DIR / "metrics.csv",
        OUTPUT_DIR / "cost_sensitivity.csv",
        drawdown_chart_path=OUTPUT_DIR / "drawdown_curve.png",
        ma_chart_path=OUTPUT_DIR / "price_moving_averages.png",
        yearly_returns_path=OUTPUT_DIR / "annual_returns.csv",
        parameter_sensitivity_path=OUTPUT_DIR / "parameter_sensitivity.csv",
        data_quality_path=OUTPUT_DIR / "data_quality.csv",
    )
    print("\n回测完成。文件已输出到：", OUTPUT_DIR)
    print(metrics[["start_date", "end_date", "total_return", "annualized_return", "max_drawdown", "sharpe_ratio", "benchmark_total_return", "excess_return_vs_benchmark"]].to_string())
    print("\n注意：指标是历史回测结果，不代表未来收益；提交前请检查输出文件并核对数据来源。")

if __name__ == "__main__":
    main()
