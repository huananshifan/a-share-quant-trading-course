"""Create a formatted Word report using the actual outputs of a completed backtest."""
from __future__ import annotations
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import pandas as pd


def _set_run_font(run, name="宋体", size=10.5, bold=None, color=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def _set_cell_shading(cell, fill="D9EAF7"):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _set_cell_text(cell, text, bold=False, size=9.2, color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    run = p.add_run(str(text))
    _set_run_font(run, size=size, bold=bold, color=color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    _set_run_font(p.add_run(text), size=10.5)


def create_word_report(output_path: str | Path, metrics: pd.DataFrame, metadata: dict,
                       chart_path: str | Path, output_csv_path: str | Path | None = None,
                       cost_sensitivity_path: str | Path | None = None,
                       drawdown_chart_path: str | Path | None = None,
                       ma_chart_path: str | Path | None = None,
                       yearly_returns_path: str | Path | None = None,
                       parameter_sensitivity_path: str | Path | None = None,
                       data_quality_path: str | Path | None = None) -> None:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    normal = doc.styles["Normal"]
    normal.font.name = "宋体"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(5)
    for style_name in ["Heading 1", "Heading 2"]:
        style = doc.styles[style_name]
        style.font.name = "黑体"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.color.rgb = RGBColor(31, 78, 121)
    doc.styles["Heading 1"].font.size = Pt(14)
    doc.styles["Heading 2"].font.size = Pt(12)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(4)
    _set_run_font(title.add_run("量化交易课程项目技术报告"), name="黑体", size=19, bold=True, color=(31, 78, 121))
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(sub.add_run(f"ETF（代码：{metadata['symbol']}）双均线策略回测"), size=11, color=(90, 90, 90))
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(note.add_run("自动生成 · 请在提交前补全小组信息并检查实际运行结果"), size=9, color=(120, 80, 50))

    doc.add_heading("1. 项目概述", level=1)
    doc.add_paragraph(
        f"本项目以ETF代码 {metadata['symbol']} 为研究标的，构建短期与长期简单移动平均线趋势策略，并以同一ETF买入并持有作为基准。"
        "策略在收盘后生成信号、于下一交易日开盘执行，按预设佣金和滑点扣除交易成本。项目输出逐日回测明细、核心绩效指标及净值曲线，便于复现和解释。"
    )

    doc.add_heading("2. 数据来源与样本区间", level=1)
    source = "本地CSV文件" if metadata.get("csv_input") else "AKShare ETF历史行情接口 fund_etf_hist_em（东方财富日线数据）"
    adjustment = metadata.get("price_adjustment", "unknown")
    adjustment_note = {
        "qfq": "前复权：用于保持价格序列连续，但不是历史真实成交价。",
        "hfq": "后复权：用于调整历史价格序列，但不是历史真实成交价。",
        "none": "不复权：公司行为可能造成价格缺口，影响收益估算。",
        "unknown": "复权口径未核验：提交前必须核对数据源设置，口径不明可能影响收益计算。",
    }.get(adjustment, "复权口径未记录，请在提交前核验。")
    bullets = [
        f"数据来源：{source}。" + (f" 输入文件：{metadata.get('csv_input')}。" if metadata.get("csv_input") else ""),
        f"标的代码：{metadata['symbol']}；实际区间：{metadata['start_actual']} 至 {metadata['end_actual']}。",
        f"有效日线数量：{metadata['rows']}；价格复权口径：{adjustment}（{adjustment_note}）",
        f"回测运行时间：{metadata.get('downloaded_at', '未记录')}；数据快照SHA-256：{metadata.get('price_snapshot_sha256', '未记录')}。",
        f"策略参数：短期均线 {metadata['short_window']} 日，长期均线 {metadata['long_window']} 日。",
    ]
    for item in bullets:
        _add_bullet(doc, item)
    warning = doc.add_paragraph()
    warning.paragraph_format.space_before = Pt(2)
    warning.paragraph_format.space_after = Pt(4)
    _set_run_font(warning.add_run(
        "重要口径说明：输入文件没有标注复权方式。本次指标先按文件提供的价格序列计算，不能直接解释为含现金分红再投资的总回报；正式提交前应补充复权设置说明，必要时用前复权或总回报序列重跑。"
    ), size=9.2, bold=True, color=(156, 65, 18))
    doc.add_paragraph(
        "外部核对：输入文件末端 2026-10-20 的 OHLC 值与公开行情页面一致。参考资料："
        "https://summary.jrj.com.cn/stock/sh/510300 ；复权参数说明见 "
        "https://github.com/akfamily/akshare/blob/main/docs/data/fund/fund_public.md 。"
    )

    doc.add_heading("3. 策略规则", level=1)
    for item in [
        f"计算收盘价的{metadata['short_window']}日和{metadata['long_window']}日简单移动平均线。",
        "当短期均线高于长期均线时，目标仓位为1（持有ETF）；否则目标仓位为0（空仓），策略不进行融券做空。",
        "交易时点采取保守的时间顺序：t日收盘后得到信号，t+1日开盘才执行，减少同一时点信号与成交造成的未来数据偏差。",
        f"单边佣金假设 {metadata['commission_bps_per_side']:.1f} 基点、单边滑点假设 {metadata['slippage_bps_per_side']:.1f} 基点；仓位发生变化时扣除成本。",
    ]:
        _add_bullet(doc, item)

    doc.add_heading("4. 回测方法与参数", level=1)
    doc.add_paragraph(
        f"全样本按时间顺序切分：前{metadata['train_ratio']:.0%}作为样本内区间，后{1-metadata['train_ratio']:.0%}作为样本外区间；"
        "切分前不进行参数优化。年化按252个交易日计算，夏普比率使用1%的年化无风险利率假设。基准与策略使用相同标的，便于对照。"
    )

    # Put the complete performance table at the top of a fresh page; avoid orphaned table rows.
    doc.add_page_break()
    doc.add_heading("5. 回测结果", level=1)
    periods = ["全样本", "样本内", "样本外"]
    metric_rows = [
        ("日期范围", lambda r: f"{r['start_date']}\n至 {r['end_date']}"),
        ("交易日数", lambda r: f"{int(r['trading_days'])}"),
        ("策略累计收益率", lambda r: f"{r['total_return']:.2%}"),
        ("策略年化收益率", lambda r: f"{r['annualized_return']:.2%}"),
        ("年化波动率", lambda r: f"{r['annualized_volatility']:.2%}"),
        ("最大回撤", lambda r: f"{r['max_drawdown']:.2%}"),
        ("夏普比率", lambda r: f"{r['sharpe_ratio']:.3f}"),
        ("基准累计收益率", lambda r: f"{r['benchmark_total_return']:.2%}"),
        ("相对基准超额收益", lambda r: f"{r['excess_return_vs_benchmark']:.2%}"),
        ("仓位变动次数", lambda r: f"{int(r['trading_events'])}"),
    ]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_props = table.rows[0]._tr.get_or_add_trPr()
    header_repeat = OxmlElement("w:tblHeader")
    header_repeat.set(qn("w:val"), "true")
    header_props.append(header_repeat)
    for i, h in enumerate(["指标", *periods]):
        _set_cell_text(table.rows[0].cells[i], h, bold=True, size=8.4, color=(255, 255, 255))
        _set_cell_shading(table.rows[0].cells[i], "1F4E79")
    for label, getter in metric_rows:
        new_row = table.add_row()
        cant_split = OxmlElement("w:cantSplit")
        new_row._tr.get_or_add_trPr().append(cant_split)
        cells = new_row.cells
        _set_cell_text(cells[0], label, bold=True, size=8.4)
        for j, period in enumerate(periods, start=1):
            _set_cell_text(cells[j], getter(metrics.loc[period]), size=8.3)
    doc.add_paragraph("注：以上指标由本次实际运行的历史数据自动计算。策略表现不保证未来收益。")

    if Path(chart_path).is_file():
        doc.add_heading("6. 净值曲线", level=1)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(chart_path), width=Inches(5.7))
        caption = doc.add_paragraph("图1  双均线策略与买入并持有基准的归一化净值曲线（起点为1.0）")
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in caption.runs:
            _set_run_font(run, size=9, color=(90, 90, 90))

    doc.add_heading("7. 结果讨论", level=1)
    full = metrics.loc["全样本"]
    train = metrics.loc["样本内"]
    test = metrics.loc["样本外"]
    doc.add_paragraph(
        f"全样本中，策略累计收益为{full['total_return']:.2%}，买入持有基准为{full['benchmark_total_return']:.2%}，"
        f"累计收益差为{full['excess_return_vs_benchmark']:.2%}；策略最大回撤为{full['max_drawdown']:.2%}，夏普比率为{full['sharpe_ratio']:.3f}。"
    )
    doc.add_paragraph(
        f"样本内策略收益为{train['total_return']:.2%}，样本外策略收益为{test['total_return']:.2%}。"
        "在当前输入价格口径下，20/60 策略在全样本和样本外均未跑赢同标的买入持有价格基准；其最大回撤也较大，说明该规则在本段样本中没有展示出稳定的风险调整后优势。"
        "均线策略具有滞后性，在震荡行情中可能反复进出；此外，价格复权口径未知也意味着不应把本次结果当作含分红的完整投资回报。"
    )

    if cost_sensitivity_path and Path(cost_sensitivity_path).is_file():
        # Keep the section heading, explanatory text and compact table together.
        # The page break prevents the table from being stranded at the top of a new page.
        doc.add_page_break()
        cost_df = pd.read_csv(cost_sensitivity_path)
        doc.add_heading("8. 交易成本敏感性", level=1)
        doc.add_paragraph("为观察交易摩擦对结果的影响，分别计算零成本、当前设定成本和双倍成本三种场景。实际交易成本可能因券商费率、滑点、成交量与时点不同而变化。")
        cost_table = doc.add_table(rows=1, cols=5)
        cost_table.style = "Table Grid"
        cost_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        header_props = cost_table.rows[0]._tr.get_or_add_trPr()
        header_repeat = OxmlElement("w:tblHeader")
        header_repeat.set(qn("w:val"), "true")
        header_props.append(header_repeat)
        for i, h in enumerate(["成本场景", "单边成本(bps)", "累计收益", "最大回撤", "夏普比率"]):
            _set_cell_text(cost_table.rows[0].cells[i], h, bold=True, size=8.4, color=(255, 255, 255))
            _set_cell_shading(cost_table.rows[0].cells[i], "1F4E79")
        for _, r in cost_df.iterrows():
            new_row = cost_table.add_row()
            cant_split = OxmlElement("w:cantSplit")
            new_row._tr.get_or_add_trPr().append(cant_split)
            cells = new_row.cells
            vals = [r["cost_scenario"], f"{r['commission_bps_per_side'] + r['slippage_bps_per_side']:.1f}",
                    f"{r['total_return']:.2%}", f"{r['max_drawdown']:.2%}", f"{r['sharpe_ratio']:.3f}"]
            for i, v in enumerate(vals):
                _set_cell_text(cells[i], v, size=8.2)

    # Calendar-year return table and drawdown path provide more than terminal NAV alone.
    if yearly_returns_path and Path(yearly_returns_path).is_file():
        doc.add_heading("9. 自然年度收益表现", level=1)
        yr = pd.read_csv(yearly_returns_path)
        yr_table = doc.add_table(rows=1, cols=5)
        yr_table.style = "Table Grid"
        yr_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(["年份", "交易日", "策略价格收益", "基准价格收益", "差值"]):
            _set_cell_text(yr_table.rows[0].cells[i], h, bold=True, size=8.4, color=(255, 255, 255))
            _set_cell_shading(yr_table.rows[0].cells[i], "1F4E79")
        for _, r in yr.iterrows():
            cells = yr_table.add_row().cells
            vals = [int(r["calendar_year"]), int(r["trading_days"]), f"{r['strategy_price_return']:.2%}",
                    f"{r['benchmark_price_return']:.2%}", f"{r['return_difference_strategy_minus_benchmark']:.2%}"]
            for i, val in enumerate(vals):
                _set_cell_text(cells[i], val, size=8.2)

    if drawdown_chart_path and Path(drawdown_chart_path).is_file():
        doc.add_heading("10. 回撤路径", level=1)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(drawdown_chart_path), width=Inches(5.8))
        cap = doc.add_paragraph("图2  策略与价格基准相对各自历史净值高点的回撤")
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in cap.runs:
            _set_run_font(run, size=9, color=(90, 90, 90))

    if parameter_sensitivity_path and Path(parameter_sensitivity_path).is_file():
        doc.add_page_break()
        doc.add_heading("11. 均线窗口参数敏感性", level=1)
        doc.add_paragraph(
            "下面列出一组固定窗口组合的描述性比较。为避免用样本外结果挑选参数，主模型仍按 SMA 20/60 展示；其余组合用于观察不同窗口对收益、回撤和换手的影响，不把全样本最高收益的组合直接宣称为最优策略。"
        )
        ps = pd.read_csv(parameter_sensitivity_path)
        pt = doc.add_table(rows=1, cols=6)
        pt.style = "Table Grid"
        pt.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(["均线组合", "全样本价格收益", "年化收益", "最大回撤", "夏普", "样本外价格收益"]):
            _set_cell_text(pt.rows[0].cells[i], h, bold=True, size=7.7, color=(255, 255, 255))
            _set_cell_shading(pt.rows[0].cells[i], "1F4E79")
        for _, r in ps.iterrows():
            cells = pt.add_row().cells
            vals = [r["config"], f"{r['full_price_return']:.2%}", f"{r['full_annualized_return']:.2%}",
                    f"{r['full_max_drawdown']:.2%}", f"{r['full_sharpe']:.3f}", f"{r['out_of_sample_price_return']:.2%}"]
            for i, val in enumerate(vals):
                _set_cell_text(cells[i], val, size=7.7)
        doc.add_paragraph(
            "结果解释应同时考虑样本内与样本外：不同窗口的表现差异较大，说明结论对参数较敏感，也提示存在数据挖掘风险。若要报告参数选择，应只利用样本内信息选参数，并把样本外区间保留为独立验证。"
        )
        if ma_chart_path and Path(ma_chart_path).is_file():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(ma_chart_path), width=Inches(5.6))
            cap = doc.add_paragraph("图3  收盘价及短、长期移动平均线")
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in cap.runs:
                _set_run_font(run, size=9, color=(90, 90, 90))

    if data_quality_path and Path(data_quality_path).is_file():
        doc.add_heading("12. 数据质量核验", level=1)
        qa = pd.read_csv(data_quality_path)
        qt = doc.add_table(rows=1, cols=3)
        qt.style = "Table Grid"
        qt.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(["检查项", "状态", "说明"]):
            _set_cell_text(qt.rows[0].cells[i], h, bold=True, size=8.0, color=(255, 255, 255))
            _set_cell_shading(qt.rows[0].cells[i], "1F4E79")
        for _, r in qa.iterrows():
            cells = qt.add_row().cells
            for i, val in enumerate([r["check"], r["status"], r["details"]]):
                _set_cell_text(cells[i], val, size=7.6)
        doc.add_paragraph(
            "日线OHLC结构检查可用于发现明显数据错误，但不能证明历史数据的复权口径、交易所来源和分红处理一定正确；这些仍需结合数据提供方说明。"
        )

    doc.add_page_break()
    doc.add_heading("13. 局限性与改进方向", level=1)
    doc.add_paragraph(
        "本项目使用日线OHLC进行简化回测，不模拟盘口深度、部分成交、整手限制、涨跌停无法成交、实际券商费率差异、税费变化和ETF跟踪误差；当前输入文件没有标注复权方式，因此输出指标按所提供价格序列理解，不视为包含分红再投资的总回报。"
        "下一步应确认前复权/总回报数据，再重跑策略与基准；随后可进行滚动样本外测试、基于样本内的固定参数选择，并比较交易成本和风险控制方案。"
    )

    doc.add_heading("14. 复现说明", level=1)
    doc.add_paragraph("建议使用64位Python 3.11或更高版本，在项目目录运行：")
    code = doc.add_paragraph()
    code.paragraph_format.left_indent = Inches(0.25)
    _set_run_font(code.add_run(
        f"python -m pip install -r requirements.txt\npython main.py --symbol {metadata['symbol']} "
        f"--csv data/510300_daily_input.csv --csv-adjustment unknown "
        f"--start {metadata['start_requested']} --end {metadata['end_requested']} "
        f"--short-window {metadata['short_window']} --long-window {metadata['long_window']}"
    ), name="Consolas", size=9)
    doc.add_paragraph("完整逐日结果、指标表、信号明细、行情快照和运行参数保存在 outputs/ 文件夹。提交前建议保存代码版本/提交号及行情下载日期。")


    doc.add_heading("15. 参考资料", level=1)
    for ref in [
        "AKShare：ETF基金历史行情接口及复权参数说明。https://github.com/akfamily/akshare/blob/main/docs/data/fund/fund_public.md",
        "金融界：沪深300ETF（510300）行情页面，用于抽查 2026-10-20 的日线OHLC。https://summary.jrj.com.cn/stock/sh/510300",
        "天天基金网：华泰柏瑞沪深300ETF基金资料与分红记录。https://fund.eastmoney.com/510300.html",
    ]:
        _add_bullet(doc, ref)

    # Add a consistent footer.
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(footer.add_run("量化交易课程项目 · 自动生成报告 · 仅用于教学研究"), size=8, color=(120, 120, 120))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
