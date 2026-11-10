# a-share-quant-trading-course
A-share Quantitative Trading Course Project

# A股量化交易课程项目：沪深300 ETF 双均线策略

## 项目简介

本项目基于沪深300 ETF（510300）的历史日线行情，构建并实现了一套基于双均线交叉信号的量化交易系统。

项目采用 Python 实现，包含历史数据接入、交易策略、回测引擎、绩效评价、结果可视化和自动化技术报告等模块。

## 核心策略

- 标的：沪深300 ETF（510300）
- 策略：20日与60日简单移动平均线交叉策略
- 买卖信号：收盘后生成，下一交易日开盘执行
- 基准：同一 ETF 买入并持有
- 交易成本：考虑佣金和滑点

## 回测初步结果

| 指标 | 策略 | 基准 |
|---|---:|---:|
| 累计价格收益率 | +5.11% | +15.36% |
| 最大回撤（策略） | -40.95% | — |

注：上述结果基于所提供的历史价格序列，原始文件未明确复权口径，因此不能直接视为包含现金分红再投资的总回报。

## 项目目录

完整项目位于 `ETF510300源码文件夹/`：

- `main.py`：项目主程序
- `strategy.py`：交易策略
- `backtest.py`：回测引擎
- `data_loader.py`：数据读取模块
- `metrics.py`：绩效指标计算
- `report_docx.py`：Word技术报告生成
- `data/`：历史行情数据
- `outputs/`：回测结果与图表
- `tests/`：自动化测试
- `docs/`：项目技术文档
- `deliverables/`：课程交付材料
- `requirements.txt`：Python依赖清单

## 如何运行

请先安装 Python 环境及项目依赖：

```bash
pip install -r requirements.txt
```

运行单元测试：

```bash
python -m unittest discover -s tests -v
```

运行回测：

```bash
python main.py
```

具体的数据导入方式和参数说明请参考项目目录中的 README.md。

## 研究说明

本项目用于量化交易课程教学与历史数据回测研究，不构成投资建议。

回测结果受到数据复权口径、交易成本、样本区间及策略参数等因素影响。历史表现不代表未来收益。
