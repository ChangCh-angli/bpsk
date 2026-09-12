#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 RRC(α=0.35) 分数延迟相位系数表,并内嵌为 rrc_pulse.v 的可综合 case 函数。

背景:每码元采样数 = 50e6/4.08e6 = 625/51(非整数),若码元冲激只能落在整数
采样点上,匹配滤波 EVM 存在 ≈4.65%(−26.7 dB)的定时栅格抖动地板。
改进:码元冲激以 1/51 采样的分数延迟精度合成——NCO 相位余量 r(=acc)唯一
确定分数偏移,φ_idx = (FTW−1−r)×51/FTW ∈ [0,50](除法用 magic number
M = floor(2^45/FTW) = 100392,见 sym_timing_nco.v),每个相位预存一套
分数延迟 RRC 系数,发端查表注入。相位量化残余抖动 ≈0.09%,配合 ±6 码元
跨度(截断 0.22%,实测甜点),总 EVM ≈0.24%(−52.2 dB)。

输出:
  rtl/rrc_pulse.v           -- 在 BEGIN/END AUTO-GENERATED 标记区间内重写
                               两级 case(外层相位/内层抽头)的系数函数;
                               综合时 tap_idx 为常量,自动剪枝为每抽头 51 选 1
  scripts/rrc_phases_dec.txt -- 同一张表的十进制文本,golden_bpsk.c 读取

定点格式 Q1.14(2^14=16384):每套剖面的峰值系数 = 16384 = 1.0。
改动 α/SPAN/PHASES/TAP_FRAC 后重跑本脚本,并同步 rrc_pulse.v / golden_bpsk.c
的 NTAPS/PHASES/TAP_FRAC 与 sym_timing_nco.v 的 M(仅 FTW 变时)。
"""

import math
import os

ALPHA = 0.35                      # 滚降系数
FS = 50e6                         # 输出采样率
RS = 4.08e6                       # 码元速率
SPS = FS / RS                     # 12.254901960784... = 625/51
SPAN = 6                          # ±6 码元跨度(实测截断 EVM 甜点,见上)
NTAPS = 149                       # 2*round(6*SPS)+1 = 149
CENTER = 74                       # 中心抽头下标
PHASES = 51                       # 分数延迟相位数(= 码元分数周期)
TAP_FRAC = 14                     # Q1.14
SCALE = 1 << TAP_FRAC             # 16384
ACC_W = 20                        # 与 rrc_pulse.v 的 ACC_W 参数保持一致

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BEGIN_MARK = "// ==== BEGIN AUTO-GENERATED PHASE ROM"
END_MARK = "// ==== END AUTO-GENERATED PHASE ROM"


def rrc(t):
    """连续时间 RRC,t 以码元周期为单位。"""
    if abs(t) < 1e-12:
        return 1.0 - ALPHA + 4.0 * ALPHA / math.pi
    q = 4.0 * ALPHA * t
    return (math.sin(math.pi * t * (1.0 - ALPHA)) + q * math.cos(math.pi * t * (1.0 + ALPHA))) \
        / (math.pi * t * (1.0 - q * q))


def build_table():
    peak = 1.0 - ALPHA + 4.0 * ALPHA / math.pi   # h(0),统一各相位定标
    rows, s = [], 0
    for p in range(PHASES):
        dlt = (p + 0.5) / PHASES                 # 相位中心,量化误差 ≤ 1/(2*PHASES) 采样
        hf = [rrc((i - CENTER - dlt) / SPS) / peak for i in range(NTAPS)]
        gq = [int(x * SCALE + 0.5) if x >= 0 else -int(-x * SCALE + 0.5) for x in hf]
        rows.append(gq)
        s = max(s, sum(abs(g) for g in gq))
    print("sps = %.9f = 625/51, span = ±%dT, taps = %d, phases = %d, Q1.%d"
          % (SPS, SPAN, NTAPS, PHASES, TAP_FRAC))
    print("max over phases of Σ|g_q| = %d  (20-bit 累加器界 524288)" % s)
    assert s < (1 << 19), "sum|h| exceeds 20-bit accumulator bound"
    assert ACC_W == 20, "系数字面量按 20-bit 有符号生成,改 ACC_W 需同步生成分支文本"
    return rows


def emit_dec(rows):
    dec = os.path.join(ROOT, "scripts", "rrc_phases_dec.txt")
    with open(dec, "w") as f:
        for gq in rows:
            for g in gq:
                f.write("%d\n" % g)
    print("wrote %s (%d words)" % (dec, PHASES * NTAPS))


def emit_rom_into_pulse(rows):
    """把系数表写成两级 case 函数,替换 rrc_pulse.v 中标记区间内的旧内容。"""
    src_path = os.path.join(ROOT, "rtl", "rrc_pulse.v")
    src = open(src_path, encoding="utf-8").read().splitlines()
    b = next(i for i, l in enumerate(src) if l.strip().startswith(BEGIN_MARK))
    e = next(i for i, l in enumerate(src) if l.strip().startswith(END_MARK))
    assert b < e, "rrc_pulse.v 标记区间非法"

    def lit(g):
        return ("%d'sd%d" % (ACC_W, g)) if g >= 0 else ("-%d'sd%d" % (ACC_W, -g))

    out = [BEGIN_MARK + " —— 本段由 scripts/gen_rrc_taps.py 生成,勿手改 ===="]
    out.append("    // %d 相位 × %d 抽头 Q1.14 系数,两级 case(外层相位/内层抽头)。" % (PHASES, NTAPS))
    out.append("    // 仅码元边界周期被求值;综合时 tap_idx 为常量,自动剪枝为每抽头 51 选 1。")
    out.append("    function signed [ACC_W-1:0] rrc_rom_coef(input [5:0] phs, input [7:0] tix);")
    out.append("        begin")
    out.append("            case (phs)")
    for p in range(PHASES):
        out.append("            6'd%d: begin" % p)
        out.append("                case (tix)")
        for i, g in enumerate(rows[p]):
            out.append("                8'd%d: rrc_rom_coef = %s;" % (i, lit(g)))
        out.append("                default: rrc_rom_coef = %d'sd0;" % ACC_W)
        out.append("                endcase")
        out.append("            end")
    out.append("            default: rrc_rom_coef = %d'sd0;" % ACC_W)
    out.append("            endcase")
    out.append("        end")
    out.append("    endfunction")

    new_src = "\n".join(src[:b] + out + src[e:]) + "\n"
    open(src_path, "w", encoding="utf-8").write(new_src)
    print("wrote %s (标记区间 %d 行 -> %d 行)" % (src_path, e - b - 1, len(out) - 1))


def main():
    rows = build_table()
    emit_dec(rows)
    emit_rom_into_pulse(rows)


if __name__ == "__main__":
    main()
