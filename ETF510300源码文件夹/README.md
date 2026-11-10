# A股量化交易课程项目：沪深300 ETF 双均线策略

本项目以沪深300 ETF（510300）为标的，使用 20/60 日简单移动平均线构建多头/空仓策略，以同一 ETF 的买入持有价格收益为基准。交付包已经包含从用户提供的 Excel 转换得到的 CSV、实际回测输出、完整代码、单元测试与自动技术报告。

> **结果解释的重要限制：** 输入 Excel 没有标明价格复权口径。报告中的收益率因此表示“在所提供价格序列上的价格收益”，不能直接解读为包括 ETF 现金分红再投资的总回报。正式提交前应确认来源中的复权设置；如果拿到确认的前复权或总回报数据，请重新运行并更新报告。

## 1. 已完成的回测

- 标的：沪深300 ETF，代码 510300。
- 实际样本：2020-01-02 至 2026-10-20，共 1,645 条日线。
- 输入数据质量：无重复日期、无无法解析日期、OHLC 关键字段完整、没有发现非正价格或高低价关系异常；末端 2026-10-20 的 OHLC 经公开行情抽查一致。
- 主要策略：SMA 20/60；收盘后生成信号，下一交易日开盘执行。
- 成本假设：单边佣金 3 bp、单边滑点 2 bp。
- 初步结果：策略累计价格收益约 +5.11%，基准累计价格收益约 +15.36%，策略最大回撤约 -40.95%，夏普比率约 0.051。由于价格复权/分红口径未核验，这些是用于课程分析的价格序列回测结果，不应被表述为含分红总收益。

策略表现不佳并不意味着项目失败。课程项目的重点是数据、信号时点、成本、基准、样本内外和局限都处理清楚，且对未跑赢基准的结果作出诚实解释。参数敏感性表仅作描述性检查，不应用全样本选择参数后再宣称样本外有效。

## 2. 运行环境

建议使用 64 位 Python 3.11 或更新版本。Windows PowerShell：

```powershell
cd quant_a_share_project
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

macOS/Linux：

```bash
cd quant_a_share_project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## 3. 使用附带的本地数据复现

项目的 `data/510300_daily_input.csv` 由附带的 `data/510300_沪深300ETF_日线数据.xlsx` 转出，保留原始 8 列行情。运行：

```bash
python main.py --csv data/510300_daily_input.csv --csv-adjustment unknown --start 20200102 --end 20261020 --short-window 20 --long-window 60 --commission-bps 3 --slippage-bps 2 --train-ratio 0.7
```

命令使用 `unknown` 而非擅自标记 `qfq`，是因为原始 Excel 没有提供复权口径元数据。若向数据来源确认该文件是前复权，可使用 `--csv-adjustment qfq` 重跑；只有在确认之后才应该这样标记。

若希望从行情接口重新取数，可在能连接目标行情服务器的网络环境中安装 AKShare 后运行：

```bash
python main.py --symbol 510300 --start 20200102 --end 20261020 --short-window 20 --long-window 60
```

## 4. 输出文件清单

所有运行输出位于 `outputs/`：

| 文件 | 内容 |
|---|---|
| `metrics.csv` | 全样本、样本内、样本外核心指标 |
| `equity_curve.png` | 策略与买入持有基准的归一化净值曲线 |
| `drawdown_curve.png` | 策略与基准的回撤路径 |
| `price_moving_averages.png` | 收盘价与两条移动平均线 |
| `annual_returns.csv` | 自然年度策略/基准价格收益 |
| `parameter_sensitivity.csv` | 多组均线窗口的描述性稳健性比较 |
| `cost_sensitivity.csv` | 零成本、基准成本、双倍成本场景 |
| `data_quality.csv` | 输入数据字段、日期、OHLC 检查结果 |
| `backtest_results.csv` | 完整逐日回测序列 |
| `signals.csv` | 均线、信号、仓位和调仓信息 |
| `trades.csv` | 仓位变化事件及成本假设 |
| `prices.csv` | 本次实际使用的规范化行情快照 |
| `run_metadata.json` | 参数、数据区间、环境版本和 SHA-256 |
| `report_auto.docx` | 可编辑 Word 技术报告 |
| `report_auto.md` | Markdown 版技术报告 |

## 5. 策略与回测方法

1. 收盘后计算 20 日、60 日简单移动平均线；短均线高于长均线则目标持仓为 1，否则空仓。
2. 信号仅在下一交易日开盘执行；前一持仓承担隔夜收益，新持仓承担开盘至收盘的日内收益。
3. 仓位变化时扣除每边佣金和滑点；参数默认合计每边 5 bp。
4. 基准用同一 ETF 的买入持有价格序列，起点净值设为 1.0。由于复权口径不明，当前比较不应被称为含分红再投资的总回报比较。
5. 样本按时间先后切分，前 70% 为样本内，后 30% 为样本外。参数敏感性表并非自动挑选最优参数，避免事后挑选。

## 6. 单元测试

```bash
python -m unittest discover -s tests -v
```

测试使用合成数据验证程序机械逻辑，包括结果列、净值有限、信号只在下一交易日执行、交易成本方向和中文字段解析。合成数据仅用于软件测试，不用于市场业绩结论。当前交付包的 5 项单元测试全部通过。

## 7. 局限性与建议改进

- 日线 OHLC 回测不会模拟盘口深度、部分成交、整手限制、涨跌停无法成交、真实券商费率差异、税费变化和跟踪误差。
- 输入 Excel 没有标注复权方式；确认复权设置并重跑应作为提交前的优先事项。510300 历史上存在现金分红，价格收益不等于总回报。可参考 [AKShare ETF 历史行情复权说明](https://github.com/akfamily/akshare/blob/main/docs/data/fund/fund_public.md) 与 [天天基金产品资料](https://fund.eastmoney.com/510300.html)。
- 不应仅因某一组均线参数的全样本结果更好就将其选为最终模型。更严谨的扩展是仅用样本内选择参数，并完全保留样本外作为验证。

## 8. 汇报分工

五人组可以分工为：组长统稿、架构和复现；组员 2 讲数据源与数据质量；组员 3 讲策略与避免未来函数；组员 4 讲实际回测结果与年度表现；组员 5 讲交易成本、局限性和改进方向。详细页纲见 `docs/ppt_outline.md`。

## 9. 提交前检查清单

- [ ] 确认复权口径，必要时更新命令并重新生成所有报告。
- [ ] 亲自运行测试和回测，确认 `metrics.csv` 与 Word 报告数值一致。
- [ ] 补全小组信息、班级、组号、仓库地址。
- [ ] 汇报中展示价格复权口径、样本外表现和策略未跑赢基准的实际结果。
- [ ] 保存代码版本号、输入数据和运行参数；不提交密钥或个人账户信息。

## 10. 附加交付材料

- `outputs/report_auto.docx`：正式可编辑技术报告。
- `deliverables/量化交易项目_回测结果与数据审计.xlsx`：汇总仪表板和8张工作表，包含核心指标、年度收益、成本敏感性、参数敏感性、数据质量、逐日回测和原始行情。
- `docs/结果结论速览.md`：方便组长统稿与PPT核对的结果摘要。

正式提交前仍需确认原始Excel的复权口径，并填写小组/班级/组号等课程信息。
