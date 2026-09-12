#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《BPSK 基带信号源设计说明书》Word 文档(docs/ 下)。

依赖 python-docx。内容与 README.md 同源但更正式,含推导与验证数据。
改完本文档内容后重新运行本脚本即可再生成。
"""

import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "BPSK基带信号源设计说明书_V1.1.docx")


def set_fonts(style, ascii_font, east, size=None, bold=None, color=None):
    """同时设置西文/中文字体(Word 中文必须设 eastAsia,否则回退宋体以外的字体)。"""
    style.font.name = ascii_font
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), east)
    if size:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color:
        style.font.color.rgb = color


def code_par(doc, text, size=8.5):
    """等宽代码/框图段落,浅灰底。"""
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.name = "Consolas"
    r.element.get_or_add_rPr()
    rf = OxmlElement("w:rFonts")
    rf.set(qn("w:eastAsia"), "宋体")
    r.element.rPr.append(rf)
    r.font.size = Pt(size)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "F2F2F2")
    ppr.append(shd)
    return p


def add_table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    for j, h in enumerate(headers):
        c = t.rows[0].cells[j]
        c.text = h
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
    for i, row in enumerate(rows, start=1):
        for j, v in enumerate(row):
            t.rows[i].cells[j].text = str(v)
    if widths:
        for j, w in enumerate(widths):
            for row in t.rows:
                row.cells[j].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = Document()

    # 页面 A4 + 常规页边距
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for a in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(sec, a, Cm(2.4))

    # 样式:正文宋体,标题黑体
    set_fonts(doc.styles["Normal"], "Calibri", "宋体", size=11)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.3
    for name, size in (("Title", 22), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)):
        set_fonts(doc.styles[name], "Arial", "黑体", size=size, bold=True, color=RGBColor(0, 0, 0))

    # ---------------- 封面 ----------------
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("BPSK 基带信号源")
    r.font.size = Pt(26)
    r.bold = True
    r.font.name = "Arial"
    r.element.get_or_add_rPr()
    rf = OxmlElement("w:rFonts")
    rf.set(qn("w:eastAsia"), "黑体")
    r.element.rPr.append(rf)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("设计说明书")
    r.font.size = Pt(20)
    r.bold = True
    for text in ("版本:V1.1", "日期:2026-09-12", "编写:izimu", "状态:已发布(验证通过)"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(text)
    doc.add_page_break()

    # ---------------- 1 概述 ----------------
    doc.add_heading("1 概述", level=1)
    doc.add_paragraph(
        "本设计为 BPSK 基带信号源,用于产生带 RRC 成形的伪随机码元测试激励,供接收机、"
        "解调算法的仿真与上板联调使用。码元由 PN23 伪随机序列发生器产生,经滚降系数 "
        "0.35 的根升余弦(RRC)滤波器成形后输出 13-bit 基带实信号。"
    )
    doc.add_paragraph(
        "核心难点在于输出采样率 50 MHz 与码元速率 4.08 MHz 之比不是整数"
        "(50/4.08 = 12.2549),因此码元定时采用相位累加器小数分频,RRC 滤波器"
        "直接在 50 MHz 采样域按连续时间轴取样设计,而不使用符号率多相插值结构。"
    )

    # ---------------- 2 技术指标 ----------------
    doc.add_heading("2 技术指标", level=1)
    add_table(doc,
              ["项目", "指标", "说明"],
              [["工作时钟", "100 MHz", "单时钟域,50 MHz 采样使能(每 2 拍一采样)"],
               ["输出采样率", "50 MHz", "out_valid 每 2 个时钟一拍"],
               ["码元速率", "4.08 MHz", "每码元 12.2549 个采样(非整数)"],
               ["码元序列", "PN23", "x²³+x¹⁸+1,周期 8 388 607 码元 ≈ 2.056 s"],
               ["脉冲成形", "RRC α=0.35", "149 阶(±6 码元),Q1.14,51 相位分数延迟合成"],
               ["占用带宽", "≈ 5.51 MHz", "(1+α)×Rs"],
               ["输出位宽", "13-bit 有符号", "满量程 ±4096,量化 SNR ≈ 80 dB"],
               ["输出幅度", "默认 2830(−3.21 dBFS)", "全 PN23 周期实测零削顶,幅度端口可调"],
               ["EVM_RMS", "0.2445%(−52.2 dB)", "匹配滤波 + 理想码元位置取样,详见波形质量报告 V1.1"]])

    # ---------------- 3 总体设计 ----------------
    doc.add_heading("3 总体设计", level=1)
    doc.add_heading("3.1 结构框图", level=2)
    code_par(doc,
             "clk(100M) ──> [50M 采样使能] ──┬──────────────────────────────┐\n"
             "                              ▼                              │\n"
             "  ┌───────────┐  符号   ┌───────────────┐  ±1冲激  ┌─────────┴──────┐  13bit\n"
             "  │ pn23_gen  │◄────────┤sym_timing_nco ├─────────►│   rrc_pulse    ├──────► out\n"
             "  │ x²³+x¹⁸+1 │         │ 32b 相位累加器  │          │149阶×51相位查表│\n"
             "  └───────────┘         └───────────────┘          └────────────────┘")
    doc.add_heading("3.2 关键设计决策", level=2)
    doc.add_paragraph(
        "(1) 小数分频定时:不存在实用的 k 使 50k/4.08 为整数(需 51|k,即时钟 ≥2.55 GHz),"
        "故码元节拍必须由 32-bit 相位累加器产生;“取 50 MHz 整数倍时钟”无法回避非整数比。"
    )
    doc.add_paragraph(
        "(2) 否决 102 MHz 方案:102 MHz = 25×4.08 可使码元分频整数化,但它既不是 50 MHz 的"
        "整数倍,且输出仍要求 50 MHz 采样,会引入双时钟域与重采样,得不偿失。"
    )
    doc.add_paragraph(
        "(3) 转置直接型无乘法器成形:成形滤波器的输入是内部生成的码元冲激串(约 92% 的采样点"
        "为零),采用转置直接型后每个抽头级的乘法退化为“查表 + 有条件地加减一个常数”,"
        "滤波器核内零乘法器,仅输出级保留一个乘法(累加器和 × 幅度)。"
    )
    doc.add_paragraph(
        "(4) 分数延迟相位合成:每码元 625/51 采样为非整数,若冲激只落在整数采样点,匹配滤波 "
        "EVM 存在 ≈4.65%(−26.7 dB)的定时栅格抖动地板(实测加长抽头至 ±12T 仍为 −26.7 dB,"
        "无法突破)。理想码元位置 t = m×625/51 的分数部分以 51 码元为周期遍历 {0,1/51,…,50/51},"
        "故预存 51 套分数延迟 RRC 系数,发端按 NCO 相位余量查表注入,码元位置精确到 1/51 采样"
        "(残余抖动 ≈0.09% EVM);配合 ±6 码元跨度(截断 0.22%,实测甜点,优于 ±5T 的 1.00% "
        "与 ±7T 的 0.57%),总 EVM ≈0.24%(−52.2 dB)。"
    )

    # ---------------- 4 模块设计 ----------------
    doc.add_heading("4 模块设计", level=1)
    doc.add_heading("4.1 sym_timing_nco(码元定时)", level=2)
    doc.add_paragraph(
        "32-bit 相位累加器仅在采样使能时步进,进位即码元边界。频率控制字:"
    )
    code_par(doc,
             "FTW = round(4.08e6 / 50e6 × 2³²) = round(0.0816 × 4 294 967 296)\n"
             "    = 350 469 331\n"
             "速率误差 ≈ 0.004 Hz(相对误差 ~1e-9)\n"
             "相邻码元 12/13 个采样交替,边界抖动 ≤ 1 个采样周期,经匹配滤波后可忽略。")
    doc.add_heading("4.2 pn23_gen(码元序列)", level=2)
    doc.add_paragraph(
        "Fibonacci 结构左移 LFSR,特征多项式 x²³+x¹⁸+1,种子参数化且必须非零。"
        "边界到来时先取 lfsr[0] 作为当前码元(0→+A,1→−A),再推进寄存器。"
        "周期 8 388 607 码元,在 4.08 MHz 码元速率下约 2.056 s。"
    )
    doc.add_heading("4.3 rrc_pulse(成形与定标)", level=2)
    doc.add_paragraph(
        "149 阶 Q1.14 抽头在 50 MHz 采样域按 t/T = n/12.2549 取样(峰值归一),51 个分数"
        "延迟相位由 scripts/gen_rrc_taps.py 生成,以可综合的两级 case 函数内嵌于 rrc_pulse.v"
        "(无 initial/$readmemh)。核内 149 级 20-bit 累加器做"
        "条件常数加减;输出级完成幅度乘法、round-half-up 取整与 ±4096 饱和:"
    )
    code_par(doc,
             "acc[i](n) = acc[i+1](n−1) + x(n)·tap[i],   x(n) ∈ {−1, 0, +1}\n"
             "out(n)    = sat13( (acc[0](n) × amplitude + 2¹³) >>> 14 )")
    doc.add_paragraph(
        "mode_nrz=1 时旁路成形器,直接输出按码元保持的 ±amplitude 阶梯波,供链路分段调试;"
        "sym_strobe 引出码元边界供接收端对齐。"
    )
    doc.add_heading("4.4 bpsk_src_top(顶层端口)", level=2)
    add_table(doc,
              ["端口", "方向", "位宽", "说明"],
              [["clk", "in", "1", "100 MHz 工作时钟"],
               ["rst_n", "in", "1", "异步复位,低有效"],
               ["mode_nrz", "in", "1", "1:NRZ 调试旁路"],
               ["amplitude", "in", "13", "冲激幅度 LSB(≤2830 保证零削顶)"],
               ["sym_strobe", "out", "1", "码元边界脉冲(联调对齐)"],
               ["out_valid", "out", "1", "50 MHz 采样有效"],
               ["out_sample", "out", "13", "有符号基带采样"]])

    # ---------------- 5 定点定标 ----------------
    doc.add_heading("5 定点定标与削顶分析", level=1)
    doc.add_heading("5.1 抽头量化", level=2)
    doc.add_paragraph(
        "抽头采用 Q1.14(定标 2¹⁴=16384)而非 Q1.15:峰值归一后中心抽头恰为 1.0,"
        "1.0×2¹⁵=32768 超出 16-bit 有符号表示范围,而 16384 可放下。抽头量化 SNR 约 84 dB,"
        "远高于 13-bit 输出的 80 dB,不构成精度瓶颈。"
    )
    doc.add_heading("5.2 位宽", level=2)
    code_par(doc,
             "Σ|tap| = 275 351(相位表最大) < 2¹⁹  →  累加器取 20-bit(理论最坏界内,含保护位)\n"
             "乘积位宽:|acc|max×amp_max = 524 287×4095 < 2³¹,输出级乘积 41-bit 容纳")
    doc.add_heading("5.3 幅度定标(为什么是 2830)", level=2)
    doc.add_paragraph(
        "RRC(α=0.35) 成形后 BPSK 波形的峰均比是固有属性。用定点 golden model 跑完整 "
        "PN23 周期(102 801 655 采样)实测:峰值 max|y| = 1.4466A(与种子无关——m-序列"
        "必含最坏局部图样,该峰值是确定值而非统计值),RMS = 0.9126A,峰均比 4.00 dB。"
    )
    doc.add_paragraph(
        "输出峰值与幅度成严格线性关系:max|out| = (max|y_r| × A + 2¹³) >> 14,其中 "
        "max|y_r| = 23 704(Q1.14 整数域)。零削顶条件 out ≤ 4095 给出幅度上限的整数推导:"
    )
    code_par(doc,
             "A_max = floor((4096×2¹⁴ − 8193) / 23 704)\n"
             "      = floor(67 100 671 / 23 704) = 2830.4 → 2830\n"
             "A = 2830 时输出峰值 = (23 704×2830 + 8192) >> 14 = 4094,\n"
             "恰好贴在正满量程 4095 下方 1 LSB(负向 −4094 对称)。")
    add_table(doc,
              ["幅度 A 配置", "削顶情况", "输出峰值 / RMS"],
              [["2830(−3.21 dBFS)", "零削顶(峰值 4094,全周期复核)", "4094 / −4.01 dBFS"],
               ["2797(V1.0 旧值,架构改动后勿沿用)", "零削顶,但峰值仅 ≈4047,低了约 0.1 dB", "4047 / −4.12 dBFS"],
               ["2831 及以上(≤4095)", "开始削顶,饱和逻辑钳位,带外杂散抬升", "4095 / —"]],
              widths=[5.6, 6.4, 4.0])
    doc.add_paragraph(
        "结论:削顶换电平是坏交易(削顶直接造成带内失真与带外杂散),默认幅度锁定 2830。"
        "注意区分两个上限:2830 是零削顶的“干净输出”上限;amplitude 端口位宽的硬上限是 "
        "4095,超出 2830 的取值会被输出级饱和逻辑钳位。幅度为运行时端口,若应用允许轻微"
        "削顶可自行上调。"
    )

    # ---------------- 6 验证 ----------------
    doc.add_heading("6 验证", level=1)
    doc.add_paragraph(
        "采用“定点逐位 golden model + RTL 比对”策略:scripts/golden_bpsk.c 以与 RTL 完全"
        "同构的整数运算(NCO 进位、LFSR 推进、转置累加、移位取整、饱和)生成参考序列,"
        "tb/tb_bpsk_src.v 在 out_valid 驱动下逐位比对,并检查 out_valid 节奏与码元节拍数。"
    )
    add_table(doc,
              ["验证项", "条件", "结果"],
              [["逐位比对", "iverilog 13.0,2 000 000 采样", "PASS,0 失配"],
               ["EVM_RMS", "匹配滤波 + 理想码元位置取样,163 199 码元", "0.2445%(−52.2 dB),峰值 0.797%"],
               ["码元节拍", "2M 采样", "163 200 个,与 FTW 理论值精确相等"],
               ["输出幅度", "2M 采样", "max=4094 / min=−4094,与浮点预测一致"],
               ["全周期削顶", "golden,102 801 655 采样,amp=2830", "max=4094,saturated=0(零削顶)"],
               ["NRZ 旁路", "100 000 采样", "±2830 阶梯波,节拍正确"],
               ["代码质量", "verilator --lint-only -Wall", "0 告警"]],
              widths=[4.0, 6.5, 5.5])

    # ---------------- 7 使用说明 ----------------
    doc.add_heading("7 使用说明", level=1)
    add_table(doc,
              ["命令", "作用"],
              [["make", "生成抽头 → golden → 2M 采样逐位比对(一键全流程)"],
               ["make peak", "golden 跑完整 PN23 周期,复核零削顶(约 1 分钟)"],
               ["make lint", "verilator lint"],
               ["vvp tb/sim.vvp +nrz +n=100000", "NRZ 调试模式冒烟"],
               ["vvp tb/sim.vvp +n=2000000 +vcd", "输出 tb/wave.vcd 波形"]],
              widths=[8.0, 8.0])
    doc.add_paragraph("集成到上层设计时,例化 bpsk_src_top 并按 4.4 节连接端口即可;"
                      "更换种子(非零)可改变序列相位,峰值不受影响。")
    doc.add_heading("7.1 移植注意事项", level=2)
    doc.add_paragraph(
        "(1) rrc_pulse 内所有累加运算均经由有符号中间变量完成。不要把抽头直接混入含无符号"
        "操作数的表达式——Verilog 会将整条表达式按无符号求值,负抽头被零扩展导致结果错误"
        "(本项目调试中实际踩过并已修复,详见 rrc_pulse.v 注释)。"
    )
    doc.add_paragraph(
        "(2) 抽头由脚本生成:改动 α/跨度/位宽后,需同步修改 rrc_pulse.v 的 "
        "TAP_W/TAP_FRAC/ACC_W 与 golden_bpsk.c 的 TAP_FRAC,并重跑 make 全量回归。"
    )

    # ---------------- 附录 ----------------
    doc.add_heading("附录 A 文件清单", level=1)
    add_table(doc,
              ["路径", "说明"],
              [["rtl/pn23_gen.v", "PN23 序列发生器"],
               ["rtl/sym_timing_nco.v", "码元定时 NCO"],
               ["rtl/rrc_pulse.v", "RRC 成形器 + 输出定标 + NRZ 旁路"],
               ["rtl/bpsk_src_top.v", "顶层"],
               ["rtl/rrc_pulse.v 内嵌相位函数", "51×149 系数以可综合 case 内嵌(脚本标记段自动生成)"],
               ["scripts/gen_rrc_taps.py", "相位系数表生成(Q1.14,含位宽校验)"],
               ["scripts/golden_bpsk.c", "定点逐位 golden model"],
               ["scripts/gen_design_doc.py", "本说明书的生成脚本"],
               ["scripts/analyze_wave.py", "波形质量分析(FFT/EVM/CCDF/眼图)"],
               ["tb/tb_bpsk_src.v", "自检测 testbench"],
               ["Makefile", "一键抽头/golden/仿真"]])

    doc.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
