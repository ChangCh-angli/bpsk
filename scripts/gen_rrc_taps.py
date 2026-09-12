#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 RRC(α=0.35) 分数延迟相位系数表(路线 A:消除码元定时栅格抖动)。

背景:每码元采样数 = 50e6/4.08e6 = 625/51(非整数),若码元冲激只能落在整数
采样点上,匹配滤波 EVM 存在 ≈4.65%(−26.7 dB)的定时栅格抖动地板。
改进:码元冲激以 1/51 采样的分数延迟精度合成——NCO 相位余量 r(=acc)唯一
确定分数偏移,φ_idx = (FTW−1−r)×51 >> 32 ∈ [0,50],每个相位预存一套
分数延迟 RRC 系数,发端查表注入。相位量化残余抖动 ≈0.09%,配合 ±6 码元
跨度(截断 0.22%),总 EVM 预期 ≈0.25%(−52 dB)。

为何是 51:理想码元位置 t_m = m×625/51,分数部分 (13m mod 51)/51 恰好以
51 码元为周期取遍 {0,1/51,…,50/51};跨度选 ±6T(149 阶)是实测甜点
(±6T 截断 0.22%,好于 ±5T 的 1.00% 和 ±7T 的 0.57%,非单调)。

输出:
  rtl/rrc_phases.mem        -- 51×149 个 16-bit 十六进制(补码),$readmemh 用,
                               排布:相位 p 的第 i 个系数位于 p*NTAPS+i
  scripts/rrc_phases_dec.txt -- 十进制有符号,golden_bpsk.c 读取

定点格式 Q1.14(2^14=16384):中心系数 = 1.0 → 16384 可放进 16-bit 有符号。
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rrc(t):
    """连续时间 RRC,t 以码元周期为单位。"""
    if abs(t) < 1e-12:
        return 1.0 - ALPHA + 4.0 * ALPHA / math.pi
    q = 4.0 * ALPHA * t
    return (math.sin(math.pi * t * (1.0 - ALPHA)) + q * math.cos(math.pi * t * (1.0 + ALPHA))) \
        / (math.pi * t * (1.0 - q * q))


def main():
    peak = 1.0 - ALPHA + 4.0 * ALPHA / math.pi   # h(0),统一各相位定标
    s = 0
    rows = []
    for p in range(PHASES):
        dlt = (p + 0.5) / PHASES                 # 相位中心,量化误差 ≤ 1/(2*51) 采样
        hf = [rrc((i - CENTER - dlt) / SPS) / peak for i in range(NTAPS)]
        gq = [int(x * SCALE + 0.5) if x >= 0 else -int(-x * SCALE + 0.5) for x in hf]
        rows.append(gq)
        s = max(s, sum(abs(g) for g in gq))

    print("sps = %.9f = 625/51, span = ±%dT, taps = %d, phases = %d, Q1.%d"
          % (SPS, SPAN, NTAPS, PHASES, TAP_FRAC))
    print("max over phases of Σ|g_q| = %d  (20-bit 累加器界 524288)" % s)
    assert s < (1 << 19), "sum|h| exceeds 20-bit accumulator bound"
    for gq in rows:
        for g in gq:
            assert abs(g) <= 32767, "tap overflow 16-bit signed"

    mem = os.path.join(ROOT, "rtl", "rrc_phases.mem")
    dec = os.path.join(ROOT, "scripts", "rrc_phases_dec.txt")
    with open(mem, "w") as f:
        for gq in rows:
            for g in gq:
                f.write("%04x\n" % (g & 0xFFFF))
    with open(dec, "w") as f:
        for gq in rows:
            for g in gq:
                f.write("%d\n" % g)
    print("wrote %s (%d words)" % (mem, PHASES * NTAPS))
    print("wrote %s" % dec)


if __name__ == "__main__":
    main()
