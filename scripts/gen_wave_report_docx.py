#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Word 版《BPSK 信号源波形质量报告》(docs/ 下)。

复用 gen_design_doc.py 的样式助手;图片取自 docs/figs/(analyze_wave.py 产出)。
数据更新后先跑 analyze_wave.py 再跑本脚本即可再生成。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_design_doc import ROOT, set_fonts, add_table  # noqa: E402

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = os.path.join(ROOT, "docs", "波形质量报告_V1.1.docx")
FIGDIR = os.path.join(ROOT, "docs", "figs")


def figure(doc, name, width_cm=16.0):
    path = os.path.join(FIGDIR, name)
    doc.add_picture(path, width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


def bullet(doc, text):
    p = doc.add_paragraph(text, style="List Bullet")
    return p


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for a in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(sec, a, Cm(2.2))

    set_fonts(doc.styles["Normal"], "Calibri", "宋体", size=11)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.3
    for name, size in (("Heading 1", 15), ("Heading 2", 12.5)):
        set_fonts(doc.styles[name], "Arial", "黑体", size=size, bold=True,
                  color=RGBColor(0, 0, 0))

    # ---- 标题与报告信息 ----
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("BPSK 信号源波形质量报告")
    r.font.size = Pt(20)
    r.bold = True
    r.font.name = "Arial"
    r.element.get_or_add_rPr()
    rf = OxmlElement("w:rFonts")
    rf.set(qn("w:eastAsia"), "黑体")
    r.element.rPr.append(rf)

    add_table(doc,
              ["项目", "内容"],
              [["被测对象", "rtl/bpsk_src_top.v(PN23 + RRC α=0.35,149 阶 Q1.14 + 51 相位分数延迟合成,13-bit 输出,幅度 = 2830)"],
               ["数据来源", "iverilog RTL 仿真实测导出(tb_bpsk_src.v +dump=),2 000 000 采样 / 163 199 码元,导出同时通过 golden 逐位比对(PASS)"],
               ["分析工具", "scripts/analyze_wave.py(numpy / scipy / matplotlib)"],
               ["日期 / 版本", "2026-09-12 / V1.1(V1.0 为 ±4 码元直接冲激架构,本版为分数延迟合成架构,详见第 7 节)"]])

    # ---- 1 时域 ----
    doc.add_heading("1 时域波形", level=1)
    doc.add_paragraph(
        "下图给出 500 个采样(≈41 个码元)的 RTL 输出。波形在 ±A(±2830,绿色点线)附近"
        "游走、码元过渡处过冲,最大值 4094 距满量程 ±4095(红色虚线)仅 1 LSB——这是幅度"
        "定标刻意锁定的零削顶工作点。灰色竖线为码元边界,边界处波形连续、无跳变毛刺。"
    )
    figure(doc, "fig1_time.png")

    # ---- 2 频谱 ----
    doc.add_heading("2 频谱(FFT / Welch 功率谱)", level=1)
    figure(doc, "fig2_spectrum.png")
    add_table(doc,
              ["指标", "实测", "理论", "结论"],
              [["占用带宽 (1+α)Rs", "5.508 MHz", "5.508 MHz", "精确一致"],
               ["主瓣 PSD 高度", "≈ −71 dBFS/Hz", "−71.1 dBFS/Hz", "一致"],
               ["噪声底(12~25 MHz 中位)", "−139.6 dBFS/Hz", "—", "无杂散岛"],
               ["带外/带内功率比", "−27.6 dB", "—", "较上版 −23.6 dB 改善 4 dB(跨度 ±4T→±6T)"]],
              widths=[5.0, 4.0, 3.6, 3.4])
    doc.add_paragraph("谱形为标准 RRC 主瓣 + 截断旁瓣,平滑滚降、无谱线、无杂散。")

    # ---- 3 EVM ----
    doc.add_heading("3 解调与 EVM", level=1)
    doc.add_paragraph(
        "方法:接收端用理想浮点 RRC 匹配滤波,在连续理想码元位置 t = n + f 处三次插值取样"
        "(f 由 NCO 相位余量精确恢复),符号判决后与 PN23 参照序列求误差。"
    )
    figure(doc, "fig3_evm.png")
    add_table(doc,
              ["指标", "本版(分数延迟合成)", "上版(±4T 直接冲激)"],
              [["EVM_RMS", "0.2445%(−52.2 dB)", "4.9236%(−26.2 dB)"],
               ["EVM_peak", "0.797%(亦 <1%)", "13.3%"],
               ["定时敏感度", "偏移 ±1 采样 → EVM 恶化约 4 倍(≈1%),判决时刻须压在理想码元位置", "同左"]],
              widths=[4.0, 6.0, 6.0])
    doc.add_paragraph("误差分解(符号级直接作差;合成校验 0.2442% vs 实测 0.2445%,闭合):")
    add_table(doc,
              ["误差源", "EVM", "折合 dB"],
              [["RRC ±6 码元截断(ISI)", "2.24e-3", "−53.0 dB(主导)"],
               ["51 相位量化 + 残余定时抖动", "9.63e-4", "−60.3 dB"],
               ["13-bit 输出量化 + 取整", "3.19e-5", "−89.9 dB"]],
              widths=[7.0, 4.0, 5.0])
    doc.add_paragraph(
        "两处定点化(−60 / −90 dB)均可忽略,EVM 由 ±6 码元截断主导。若需进一步压低,可"
        "试探 ±8T(193 阶,实测无抖动截断 −50.3 dB);对绝大多数应用当前指标已有充分裕量。"
    )

    # ---- 4 CCDF ----
    doc.add_heading("4 CCDF 峰均比统计", level=1)
    figure(doc, "fig4_ccdf.png", width_cm=13.5)
    bullet(doc, "RMS = 2582.86 LSB;实测峰值 4094 → 峰均比 4.00 dB")
    bullet(doc, "满量程线 4.00 dB:曲线恰好终止于满量程线,全程零削顶——幅度 2830 经完整 PN23 周期 102 801 655 采样复核,saturated = 0")

    # ---- 5 眼图 ----
    doc.add_heading("5 眼图", level=1)
    figure(doc, "fig5_eye.png", width_cm=14.5)
    doc.add_paragraph(
        "匹配滤波后 1200 码元迹线叠加:交叉点汇聚干净,判决时刻(红色竖线)眼图完全张开,"
        "无可见抖动/噪声模糊。"
    )

    # ---- 6 结论 ----
    doc.add_heading("6 结论", level=1)
    add_table(doc,
              ["项目", "结果", "判定"],
              [["码元速率", "4.08 MHz(FTW 定时,163 200 节拍/2M 采样精确吻合)", "通过"],
               ["占用带宽", "5.508 MHz = (1+α)Rs", "通过"],
               ["EVM_RMS", "0.2445%(−52.2 dB),达成 <1% 目标且余量 4 倍", "通过"],
               ["零削顶", "峰值 4094 < 4095,完整 PN23 周期复核零削顶", "通过"],
               ["频谱纯度", "噪声底 −139.6 dBFS/Hz,无杂散;带外 −27.6 dB", "通过"],
               ["可解调性", "匹配滤波 + 理想码元位置取样即恢复 PN23,眼图全开", "通过"]],
              widths=[3.4, 9.6, 3.0])

    # ---- 7 版本说明 ----
    doc.add_heading("7 版本说明(V1.0 → V1.1 架构改进)", level=1)
    doc.add_paragraph(
        "V1.0(±4 码元直接冲激)实测 EVM 4.92%(−26.2 dB)。经误差溯源发现主导项并非抽头"
        "截断,而是码元定时栅格量化:每码元 12.2549 采样,冲激只能落在 20 ns 整数栅格上,"
        "±0.5 采样的定时抖动贡献了 ≈4.65%(−26.7 dB)的 EVM 地板——实测加长抽头(±12T)"
        "仍为 −26.7 dB,加窗亦无效。"
    )
    doc.add_paragraph(
        "V1.1 改为分数延迟相位合成:利用理想码元位置 t = m×625/51 的分数部分以 51 码元为"
        "周期遍历 {0, 1/51, …, 50/51} 的性质,预存 51 套分数延迟 RRC 系数(±6 码元 149 阶,"
        "Q1.14),发端按 NCO 相位余量查表注入,码元位置精确到 1/51 采样;滤波器核仍为零"
        "乘法器(查表 + 条件加减)。幅度默认值由 2797 调整为 2830(新波形峰值比变化,经完整"
        "周期复核零削顶)。"
    )

    doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run("复现:make golden && iverilog … && vvp tb/sim.vvp +n=2000000 +amp=2830 "
                  "+dump=tb/rtl_samples.txt;python3 scripts/analyze_wave.py tb/rtl_samples.txt 2000000")
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    doc.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
