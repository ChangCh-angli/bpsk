#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《BPSK 基带信号源原理与实现(基础教程)》Word 文档(教材风格)。

输出: docs/BPSK基带信号源基础教程.docx (不入 Git)
依赖: python-docx,复用 gen_design_doc.py 的样式助手。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from gen_design_doc import ROOT, set_fonts, add_table, code_par  # noqa: E402

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = os.path.join(ROOT, "docs", "BPSK基带信号源基础教程.docx")

FILL_EXAMPLE = "FFF7DC"   # 例题底色
FILL_KEYPOINT = "E8F1E4"  # 要点底色
FILL_THINK = "EAE6F4"     # 思考题底色


def box(doc, tag, text, fill):
    p = doc.add_paragraph()
    r = p.add_run(tag + "  ")
    r.bold = True
    r.font.size = Pt(10.5)
    r2 = p.add_run(text)
    r2.font.size = Pt(10.5)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    ppr.append(shd)
    return p


def example(doc, text):
    box(doc, "【例题】", text, FILL_EXAMPLE)


def keypoint(doc, text):
    box(doc, "【要点】", text, FILL_KEYPOINT)


def think(doc, items):
    box(doc, "【思考题】", "　".join("%d. %s" % (i + 1, t) for i, t in enumerate(items)), FILL_THINK)


def summary(doc, text):
    p = doc.add_paragraph()
    r = p.add_run("本章小结:")
    r.bold = True
    p.add_run(text)
    return p


def h1(doc, text):
    doc.add_heading(text, level=1)


def h2(doc, text):
    doc.add_heading(text, level=2)


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for a in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(sec, a, Cm(2.4))

    set_fonts(doc.styles["Normal"], "Calibri", "宋体", size=11)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.35
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)):
        set_fonts(doc.styles[name], "Arial", "黑体", size=size, bold=True,
                  color=RGBColor(0, 0, 0))

    # ================= 封面 =================
    for _ in range(5):
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
    r = p.add_run("原理与实现 · 基础教程")
    r.font.size = Pt(18)
    r.bold = True
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("—— 以 rx3829 工程为实例 ——")
    r.font.size = Pt(12)
    for _ in range(3):
        doc.add_paragraph()
    for text in ("适用读者:通信工程 / 集成电路设计专业本科生",
                 "先修知识:数字电路、二进制运算、基本的信号与系统概念",
                 "版本:V1.0(2026-09-12)"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(text)
    doc.add_page_break()

    # ================= 使用说明 =================
    doc.add_heading("如何使用本教程", level=1)
    doc.add_paragraph(
        "本教程讲一个真实工程的故事:如何在一块 FPGA 里,用纯数字电路造一个“会说话的”信号源——它每 20 纳秒输出一个数,这些数连成的波形是一路规范的 BPSK 调制信号。"
        "我们尽量把每一个工程决定都还原成课堂上能讲清楚的道理。"
    )
    doc.add_paragraph("全书分三部分:")
    doc.add_paragraph("第一部分(第 1~3 章)通信与采样的基本概念,回答“要做什么”。", style="List Bullet")
    doc.add_paragraph("第二部分(第 4~7 章)四大模块的原理与实现,回答“怎么做”。", style="List Bullet")
    doc.add_paragraph("第三部分(第 8~10 章)系统组装、指标与实验,回答“做得好不好”。", style="List Bullet")
    doc.add_paragraph(
        "例题给出完整解答;思考题供自测,多数可由正文直接推出。阅读时建议手边放一张草稿纸,"
        "全书所有数字都可以用笔验证。"
    )

    # ================= 第 1 章 =================
    h1(doc, "第 1 章 一个信号源的自我介绍")
    h2(doc, "1.1 它在系统里的位置")
    doc.add_paragraph(
        "一个典型的数字通信链路是“发端 → 信道 → 收端”。发端把比特变成适合传输的波形;"
        "收端从波形里把比特恢复出来。本项目做的是发端的最前半段——基带部分:它不产生"
        "高频载波,而是输出一路已经“调好”的基带实信号,经 DAC 与上变频后即可发射,"
        "也可以直接送给接收机做测试。"
    )
    h2(doc, "1.2 一句话描述")
    keypoint(doc,
             "每 20 纳秒输出一个 13-bit 有符号数;这些数连成的波形,以 4.08 Mb/s 的速率"
             "携带一串伪随机比特(PN23),波形形状经过 α=0.35 的根升余弦(RRC)整形。")
    doc.add_paragraph(
        "“每 20 纳秒一个数”就是采样率 50 MHz(1/50 MHz = 20 ns);“4.08 Mb/s”是码元速率;"
        "“PN23”是伪随机序列;“RRC α=0.35”是脉冲成形滤波器。这几个词后面章节逐一展开。"
    )
    summary(doc, "本教程造的是数字基带信号源,输入是时钟,输出是一串样本值。")

    # ================= 第 2 章 =================
    h1(doc, "第 2 章 码元与 BPSK")
    h2(doc, "2.1 比特与码元")
    doc.add_paragraph(
        "比特是信息的最小单位;码元(symbol)是承载比特的“波形单元”。一个码元可以携带"
        "1 个比特(如 BPSK),也可以携带 2 个比特(如 QPSK 的四种相位)。本项目用 BPSK:"
        "一个码元就是一个比特。"
    )
    h2(doc, "2.2 BPSK:正负号即信息")
    doc.add_paragraph(
        "BPSK(二相移位键控)只有两个“字母”:+A 与 −A。约定码元比特为 0 时发 +A,"
        "为 1 时发 −A。接收端只要判断波形的正负,就能恢复比特——这是所有调制方式里"
        "最 robust(抗噪声)的一种,也是教学与测试最常用的一种。"
    )
    keypoint(doc, "BPSK 的一码元 = 一比特,码元速率 = 比特速率 = 4.08 Mb/s。")
    h2(doc, "2.3 为什么要“成形”")
    doc.add_paragraph(
        "如果直接发一个 +A 跳到 −A 的矩形波,它的频谱会无限延伸(跳变沿含无穷多高频成分),"
        "会干扰邻居频道。解决办法:让每个码元的波形不是一个方波,而是一个圆滑的“钟形脉冲”,"
        "前后码元的脉冲互相重叠、平滑衔接。这个整形的滤波器叫成形滤波器。"
    )
    doc.add_paragraph(
        "选什么形状?通信原理中有一个漂亮的结论(奈奎斯特第一准则):若脉冲在其中心两边的"
        "整数倍码元周期处恰好为 0,那么在中心点取样时,邻居码元的影响恰好为零,无码间串扰"
        "(ISI)。升余弦(RC)族脉冲满足该条件;工程上把收发两端各用一半,即根升余弦(RRC):"
        "发射端用 RRC 成形,接收端再用一次 RRC 匹配滤波,两次合起来正好是 RC。"
    )
    example(doc,
            "占用带宽:RRC 滚降系数 α=0.35 时,信号占用带宽 = (1+α)×码元速率 "
            "= 1.35×4.08 = 5.508 MHz。α 越小带宽越省,但脉冲拖尾越长、对定时越敏感;"
            "0.35 是常见的折中。")
    think(doc, ["若改用 QPSK(一码元 2 比特),同样 4.08 MHz 码元速率下比特速率是多少?",
                "α→0 时 RRC 趋向什么形状?为什么说它对定时误差越来越敏感?"])
    summary(doc, "BPSK 用正负号携带比特;成形滤波让带宽有限且接收端取样无码间串扰。")

    # ================= 第 3 章 =================
    h1(doc, "第 3 章 采样率与 12.2549 这个数")
    h2(doc, "3.1 采样定理 30 秒版")
    doc.add_paragraph(
        "数字系统只能按固定节拍产生数值。按采样率 Fs 产生样本,能无失真表达的信号频率"
        "不超过 Fs/2(奈奎斯特频率)。本项目 Fs = 50 MHz,奈奎斯特频率 25 MHz,而信号只占"
        "5.5 MHz 带宽,非常宽裕。"
    )
    h2(doc, "3.2 三个节拍")
    add_table(doc,
              ["节拍", "频率", "含义"],
              [["工作时钟", "100 MHz", "电路里寄存器跳动的节奏"],
               ["输出采样", "50 MHz", "每 2 个时钟输出 1 个样本(out_valid)"],
               ["码元", "4.08 MHz", "每约 12.25 个样本换 1 个码元"]],
              widths=[4.0, 4.0, 8.0])
    h2(doc, "3.3 核心难点:除不尽")
    doc.add_paragraph(
        "50 MHz 采样率除以 4.08 MHz 码元速率:50/4.08 = 12.2549…,不是整数!也就是说,"
        "有的码元占 12 个采样点,有的占 13 个,长期平均恰好 12.2549。若图省事固定每码元"
        "12 个采样,码元速率就变成了 50M/12 = 4.1667 MHz,偏差 2.1%——对通信系统是"
        "不可接受的错误。"
    )
    example(doc,
            "精确分数:12.2549… 其实是 625/51(因为 50/4.08 = 5000/408 = 625/51)。"
            "它意味着每 51 个码元恰好对应 625 个采样点,分数部分以 51 个码元为周期循环。"
            "记住 51 这个数,第 6 章和第 7 章都会用到它。")
    think(doc, ["若采样率改为 150 MHz,每码元多少个采样点?(答案:36.7647 = 1225/33.3,仍是分数)",
                "能否找一个 50 MHz 的整数倍时钟,使每码元采样数为整数?(提示:需要 51|k,"
                "即时钟至少 2.55 GHz,不现实)"])
    summary(doc, "采样率与码元速率之比是无理般“难看”的分数,这决定了后文的小数分频设计。")

    # ================= 第 4 章 =================
    h1(doc, "第 4 章 定点数:硬件怎样表示小数")
    h2(doc, "4.1 Q 格式")
    doc.add_paragraph(
        "FPGA 寄存器只有整数。要表示小数,约定小数点位置即可:Q1.14 格式用 16 位有符号数,"
        "并把数值除以 2^14 = 16384 来理解。于是 16384 代表 1.0,8192 代表 0.5,"
        "-32768 代表最接近 −2 的数。乘法结果要右移 14 位恢复定标。"
    )
    example(doc, "把 0.375 写成 Q1.14:0.375×16384 = 6144。反过来,系数 100 代表 100/16384 ≈ 0.0061。")
    h2(doc, "4.2 本项目的定标选择")
    doc.add_paragraph(
        "RRC 抽头按峰值归一(最大抽头 = 1.0)。若用 2^15 定标,1.0×32768 = 32768 超出了"
        "16 位有符号数的最大值 32767;改用 2^14 = 16384,中心系数恰为 16384,稳妥放下。"
        "这就是工程文件里 Q1.14 的由来——不是拍脑袋,是被 16 位寄存器逼出来的选择。"
    )
    h2(doc, "4.3 舍入与右移")
    doc.add_paragraph(
        "乘累加结果放大了 2^14 倍,输出前要“除回来”。硬件用算术右移 14 位实现除法"
        "(向下取整);为减小累计偏差,先加 2^13(即 0.5 的定标值)再移位,等价于"
        "四舍五入。"
    )
    code_par(doc, "out = (acc × amplitude + 16384/2) >>> 14      // round half up\n"
                  "再饱和到 [−4096, +4095](13-bit 有符号满量程)")
    think(doc, ["−5 的 Q1.14 表示是多少?(答案:−81920,超出 16 位,说明中间结果必须用更宽的寄存器)",
                "为什么“先加再移”比直接移位更公平?"])
    summary(doc, "Q1.14 用 16384 代表 1.0;乘法后右移 14 位;饱和防止溢出。")

    # ================= 第 5 章 =================
    h1(doc, "第 5 章 PN 序列:伪装成随机的确定序列")
    h2(doc, "5.1 为什么不用真随机")
    doc.add_paragraph(
        "测试信号要“像真实数据一样乱”,否则频谱会集中在某些谱线上;但又必须“可复现”,"
        "否则每次测量无法对齐比较。伪随机序列两者兼得:看起来乱,实际上由确定的电路生成,"
        "同样的种子必然得到同样的序列。"
    )
    h2(doc, "5.2 LFSR 与 m 序列")
    doc.add_paragraph(
        "线性反馈移位寄存器(LFSR)是产生 PN 序列的经典电路:寄存器每拍左移一位,空出的位"
        "由寄存器中两位的异或填入。选对了反馈位置(特征多项式),序列长度达到最大值 "
        "2^n − 1,称为 m 序列。本项目用 23 级、特征多项式 x²³ + x¹⁸ + 1,周期 "
        "2²³ − 1 = 8 388 607 个码元,按 4.08 MHz 算约 2.056 秒循环一次。"
    )
    h2(doc, "5.3 映射与种子")
    doc.add_paragraph(
        "取寄存器最低位为当前码元:0 → +A,1 → −A。种子(初值)任意非零即可,不同种子给"
        "出序列的不同相位;由于 m 序列穷尽所有短图样,信号峰值与种子选择无关——这是一个"
        "非常适合测试的特性。"
    )
    example(doc, "PN23 周期 = 8 388 607 码元 ÷ 4.08 MHz ≈ 2.056 s。即每约 2 秒,波形严格重复一遍。")
    think(doc, ["为什么种子不能是全零?(提示:异或反馈对全零态无能为力,序列卡死在 0)",
                "周期 2^23−1 是怎么来的?"])
    summary(doc, "LFSR 产生确定可复现的伪随机比特流,PN23 周期约 2 秒。")

    # ================= 第 6 章 =================
    h1(doc, "第 6 章 NCO:用一只加法器做小数分频")
    h2(doc, "6.1 相位累加器")
    doc.add_paragraph(
        "第 3 章说每码元要 12.2549 个采样。电路不会数小数,但会做模运算:维护一个 32 位"
        "累加器,每个采样节拍加一个常数 FTW,溢出就丢掉 2^32(模 2^32)。溢出事件每隔"
        "固定的时间发生一次——它就是码元边界。"
    )
    example(doc,
            "FTW 取多少?每采样步进 FTW,每码元 12.2549 个采样,所以每码元累计相位 = "
            "12.2549×FTW,应恰为 2^32。故 FTW = 2^32/12.2549 = 0.0816×2^32 = "
            "350 469 331.35,取整 350 469 331,速率误差仅 0.004 Hz。")
    h2(doc, "6.2 12/13 交替与“抖动”")
    doc.add_paragraph(
        "溢出时刻只能落在整数采样点上,于是码元长度在 12 和 13 个采样之间交替,平均 "
        "12.2549。这带来 ±0.5 采样的定时“抖动”。初版设计直接在溢出点发冲激,实测 EVM "
        "卡在 4.9% 怎么都降不下去——后来才定位到,这块抖动本身就是 4.65% 的误差地板,"
        "与滤波器多长毫无关系。"
    )
    h2(doc, "6.3 51 相位:把抖动除以 51")
    doc.add_paragraph(
        "第 3 章埋的伏笔在此揭晓:12.2549 = 625/51,第 m 个码元的理想位置是 m×625/51,"
        "分数部分恰好以 51 为周期取遍 0, 1/51, …, 50/51。于是改进方案是:冲激不再“踩”在"
        "整数点上,而是按分数偏移查一张 51 行的系数表,把冲激“插”到两个整数采样点之间"
        "的正确位置——定时精度一步提高到 1/51 采样。这正是本项目 EVM 从 4.9% 降到 "
        "0.24% 的关键一步。"
    )
    think(doc, ["累加器为什么取 32 位?位数减少会带来什么?",
                "若相位表改为 17 行(1/17 采样精度),残余抖动约等于多少?"])
    summary(doc, "NCO 用加法实现任意小数分频;分数相位表把定时抖动从 ±0.5 采样压到 ±1/102 采样。")

    # ================= 第 7 章 =================
    h1(doc, "第 7 章 成形器:一只没有乘法器的 FIR 滤波器")
    h2(doc, "7.1 FIR 十分钟入门")
    doc.add_paragraph(
        "FIR 滤波器的输出是输入历史与一组固定系数(抽头)的加权求和:y[n] = Σ h[k]·x[n−k]。"
        "共 149 个抽头时,每个输出要做 149 次乘加——按 50 MHz 输出率算,每秒 74 亿次乘法,"
        "传统实现需要消耗大量乘法器(DSP)资源。"
    )
    h2(doc, "7.2 乘法是怎么消失的")
    doc.add_paragraph(
        "本滤波器的输入不是普通信号,而是自己生成的冲激串:绝大多数采样点是 0,只有码元"
        "边界处出现 ±1。把“乘法在输入侧”的转置直接型结构画出来就会发现:每个抽头级的"
        "乘法,一个节拍里最多发生一次,且被乘数只有 +1、−1 或 0 三种可能——乘法退化成"
        "“有条件地加一个常数、减一个常数,或者什么都不做”。149 级里没有一个乘法器,"
        "只有加法器和查表。"
    )
    h2(doc, "7.3 查的是哪张表")
    doc.add_paragraph(
        "第 6 章的 51 相位在这里登场:每个相位预先存一套分数延迟后的 149 个 RRC 系数"
        "(共 51×149 = 7 599 个,Q1.14 定点)。码元边界到来时,按 NCO 给出的相位号取出一套"
        "系数,依次加进 149 级累加器;其余采样周期,累加器只做“逐级搬运”。这些系数以"
        "可综合的 case 语句形式写在 rrc_pulse.v 内,由脚本自动生成,不需要任何初始化文件。"
    )
    h2(doc, "7.4 位宽账")
    add_table(doc,
              ["对象", "位宽", "理由"],
              [["系数", "16-bit(Q1.14)", "峰值 16384 恰好放下;量化误差 −102 dB,可忽略"],
               ["累加器", "20-bit", "最坏和 ≤ Σ|系数| = 275 351 < 2^19"],
               ["输出", "13-bit", "满量程 ±4096;饱和逻辑防溢出"]],
              widths=[4.0, 4.5, 7.5])
    doc.add_paragraph(
        "位宽设计的原则:先算理论上界,再留保护位,而不是“越多越好”。本设计 20 位累加器"
        "在数学上不可能溢出,这比“跑起来没炸”可靠得多。"
    )
    think(doc, ["若把幅度 amplitude 设为 4095(端口最大值),累加器会溢出吗?(不会,"
                "上界按幅度最大值计算;但输出会大量削顶)",
                "为什么输出级还保留一个乘法器?它乘的是什么?"])
    summary(doc, "冲激串 + 转置直接型 + 查表 = 零乘法器的成形滤波器;位宽由理论上界决定。")

    # ================= 第 8 章 =================
    h1(doc, "第 8 章 组装:一拍一拍发生什么")
    h2(doc, "8.1 数据流走查")
    doc.add_paragraph(
        "以某个码元边界所在的时钟拍为例:① NCO 累加器本拍溢出,产生码元边界;② 由溢出后"
        "的余量算出相位号 φ(0~50);③ PN23 取出当前比特,决定这次注入的是 +系数还是"
        "−系数;④ 成形器把该相位的一整套系数分发到 149 级累加器;⑤ 输出级把累加器队首的"
        "和乘以幅度寄存器、四舍五入并饱和,得到 13-bit 样本。"
    )
    h2(doc, "8.2 幅度与削顶:2830 的来历")
    doc.add_paragraph(
        "多个码元的脉冲叠加会使波形峰值超过码元电平 A 本身。实测(跑完整 PN23 周期,"
        "1.028 亿采样):波形峰值 = 1.4466A,RMS = 0.9126A,峰均比 4.00 dB。要完全不削顶,"
        "A×1.4466 ≤ 4095,解得 A ≤ 2830。2830 就是出厂默认幅度:输出峰值 4094,"
        "距满量程仅 1 LSB,一点电平都不浪费。"
    )
    h2(doc, "8.3 两级流水与延迟")
    doc.add_paragraph(
        "查表注入与输出计算分两拍完成,因此 out_valid 相对码元边界有固定的两拍延迟。"
        "对连续信号源而言,固定延迟毫无影响;联调时还专门引出了 sym_strobe 端口,"
        "方便接收机对齐码元边界。"
    )
    summary(doc, "四个模块在 100 MHz 单时钟域里协同;幅度 2830 由削顶分析精确导出。")

    # ================= 第 9 章 =================
    h1(doc, "第 9 章 怎么衡量信号好不好")
    h2(doc, "9.1 EVM:误差向量幅度")
    doc.add_paragraph(
        "把接收端恢复出的每个码元值与理想值(±A)相减,误差的均方根除以理想值均方根,"
        "就是 EVM_RMS。它综合反映了一切损伤:码间串扰、量化噪声、定时误差。本设计 "
        "EVM_RMS = 0.2445%(−52.2 dB),其中码元截断贡献 −53 dB,两处定点量化分别只有"
        " −60 dB 和 −90 dB——数字精度不是瓶颈,_pulse 形状的有限长度才是。"
    )
    h2(doc, "9.2 频谱与占用带宽")
    doc.add_paragraph(
        "用 FFT 观察信号功率随频率的分布:主瓣宽度应为 (1+α)×Rs = 5.508 MHz,"
        "实测分毫不差;带外功率与带内之比 −27.6 dB,越负越好。"
    )
    h2(doc, "9.3 CCDF 与峰均比")
    doc.add_paragraph(
        "CCDF 曲线回答“信号瞬时幅度超过某值的概率多大”。BPSK-RRC 波形峰均比 4.00 dB:"
        "峰值是 RMS 的 1.586 倍。设计 DAC 接口时,要按峰值而非 RMS 预留满量程。"
    )
    h2(doc, "9.4 眼图")
    doc.add_paragraph(
        "把匹配滤波后的波形按码元周期折叠重叠,就是教材里那张“眼睛”。眼睛张得越开,"
        "判决越可靠;交叉点越细,定时越容易。本设计 1200 条迹线的眼图完全张开。"
    )
    h2(doc, "9.5 验证方法学:逐位黄金参考")
    doc.add_paragraph(
        "工程用 C 语言写了一个与 RTL 逐位等价的“黄金模型”,让 FPGA 仿真的 200 万个输出"
        "与之一一对账,一个数都不能差;再用完整周期复核峰值不削顶。这比“看波形像”"
        "可靠一个量级,是数字设计推荐的验证习惯。"
    )
    summary(doc, "EVM 看综合质量,频谱看邻居干扰,CCDF 看动态范围,眼图看判决余量。")

    # ================= 第 10 章 =================
    h1(doc, "第 10 章 实验指导")
    h2(doc, "10.1 实验 1:复现基准")
    doc.add_paragraph("在仓库根目录执行 make,自动完成:生成系数表 → 编译黄金模型 → "
                      "200 万采样逐位比对。预期输出以 PASS 开头。")
    h2(doc, "10.2 实验 2:亲手制造削顶")
    doc.add_paragraph("执行 vvp tb/sim.vvp +n=2000000 +amp=3000。观察 max 是否顶到 4095,"
                      "并思考:削顶信号做 FFT,带外频谱会发生什么变化?")
    h2(doc, "10.3 实验 3:更换 PN 种子")
    doc.add_paragraph("用 +amp 与 SEED 参数(见 Makefile)更换种子,记录每次的 max|out|。"
                      "预期:无论怎么换,峰值都是 4094——验证 5.4 节“峰值与种子无关”。")
    h2(doc, "10.4 实验 4(进阶):定时敏感性")
    doc.add_paragraph("用分析脚本(scripts/analyze_wave.py)输出的 EVM-相位曲线,找出偏移 "
                      "±1 采样后的 EVM。体会为什么接收机的定时恢复如此重要。")
    h2(doc, "10.5 常见问题")
    add_table(doc,
              ["现象", "原因与处理"],
              [["$readmemh/文件打不开类报错", "系数已内嵌代码,无需外部文件;确认代码版本"],
               ["仿真输出全为 X", "忘记给 rst_n 拉高,或时钟未接"],
               ["PASS 但幅度偏低", "amplitude 端口接的不是 2830,检查约束"]],
              widths=[6.0, 10.0])

    # ================= 附录 =================
    h1(doc, "附录 A 术语表")
    add_table(doc,
              ["术语", "英文", "一句话解释"],
              [["码元", "symbol", "承载比特的基本波形单位"],
               ["BPSK", "Binary Phase Shift Keying", "用正负两个相位携带 1 比特"],
               ["PN 序列", "Pseudo-random Noise", "确定电路产生的“伪”随机序列"],
               ["LFSR", "Linear Feedback Shift Register", "线性反馈移位寄存器,PN 序列的发生器"],
               ["NCO", "Numerically Controlled Oscillator", "相位累加器构成的小数分频/波形发生器"],
               ["FTW", "Frequency Tuning Word", "NCO 每步的相位增量"],
               ["RRC", "Root Raised Cosine", "根升余弦成形脉冲,收发各一半合成升余弦"],
               ["ISI", "Inter-Symbol Interference", "码间串扰:邻居码元对本码元的拖累"],
               ["FIR", "Finite Impulse Response", "有限冲激响应滤波器(抽头加权求和)"],
               ["EVM", "Error Vector Magnitude", "调制误差向量幅度,综合质量指标"],
               ["CCDF", "Complementary Cumulative Distribution Function", "峰均比统计曲线"],
               ["Q1.14", "—", "16 位定点格式,16384 代表 1.0"]],
              widths=[3.6, 5.2, 7.2])

    h1(doc, "附录 B 关键参数速查")
    add_table(doc,
              ["参数", "数值"],
              [["工作时钟 / 输出采样率", "100 MHz / 50 MHz"],
               ["码元速率", "4.08 MHz(FTW = 350 469 331)"],
               ["每码元采样数", "625/51 ≈ 12.2549"],
               ["码元序列", "PN23,周期 8 388 607(≈2.056 s)"],
               ["成形滤波器", "RRC α=0.35,149 阶,51 相位,Q1.14"],
               ["输出", "13-bit 有符号,默认幅度 2830"],
               ["峰值 / RMS", "4094 / 2582.9(−4.01 dBFS),零削顶"],
               ["EVM_RMS", "0.2445%(−52.2 dB)"],
               ["占用带宽", "5.508 MHz"]],
              widths=[7.0, 9.0])

    h1(doc, "附录 C 进一步阅读")
    doc.add_paragraph("《BPSK 基带信号源设计说明书 V1.1》(docs/):面向工程实现,含全部设计推导。")
    doc.add_paragraph("《BPSK 信号源波形质量报告 V1.1》(docs/):面向验证数据,含 EVM 分解与频谱实测。")
    doc.add_paragraph("仓库根目录 README.md:参数速查与 make 命令。")

    doc.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
