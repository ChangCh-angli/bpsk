#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 RRC(α=0.35) 成形滤波器的定点抽头。

关键点:每码元采样数 = 50e6/4.08e6 = 12.2549(非整数),因此抽头直接在
50 MHz 采样域上按连续时间轴 t/T = n/sps 取样,不能用符号率多相结构。

输出:
  rtl/rrc_taps.mem        -- 16-bit 十六进制(补码),供 $readmemh 加载
  scripts/rrc_taps_dec.txt -- 十进制有符号,供 golden_bpsk.c 读取

定点格式 Q1.14(TAP_FRAC=14,定标 2^14=16384):选 14 而非 15 是因为
峰值归一后中心抽头 = 1.0,16384 能放进 16-bit 有符号(32768 放不进 15-bit)。
"""

import math
import os

ALPHA = 0.35                      # 滚降系数
FS = 50e6                         # 输出采样率
RS = 4.08e6                       # 码元速率
SPS = FS / RS                     # 12.254901960784...
NTAPS = 99                        # ±4 码元跨度
CENTER = 49                       # 中心抽头下标
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
    hf = [rrc((n - CENTER) / SPS) for n in range(NTAPS)]
    pk = hf[CENTER]                       # 峰值在 t=0(α<1 时唯一最大)
    assert pk == max(hf), "center tap is not the peak"
    hf = [x / pk for x in hf]             # 峰值归一

    # 四舍五入(远离零),保证对称抽头量化后仍对称
    gq = [int(x * SCALE + 0.5) if x >= 0 else -int(-x * SCALE + 0.5) for x in hf]

    s = sum(abs(g) for g in gq)
    print("sps = %.9f, taps = %d, Q1.%d" % (SPS, NTAPS, TAP_FRAC))
    print("center tap  = %+d (ideal %.6f)" % (gq[CENTER], SCALE))
    print("sum |g_q|   = %d  (20-bit 累加器界 524288)" % s)
    assert s < (1 << 19), "sum|h| exceeds 20-bit accumulator bound"
    assert gq[CENTER] <= 32767, "center tap overflows 16-bit signed"
    for g in gq:
        assert abs(g) <= 32767, "tap overflow 16-bit signed"

    mem = os.path.join(ROOT, "rtl", "rrc_taps.mem")
    dec = os.path.join(ROOT, "scripts", "rrc_taps_dec.txt")
    with open(mem, "w") as f:
        for g in gq:
            f.write("%04x\n" % (g & 0xFFFF))
    with open(dec, "w") as f:
        for g in gq:
            f.write("%d\n" % g)
    print("wrote %s" % mem)
    print("wrote %s" % dec)


if __name__ == "__main__":
    main()
