#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BPSK 信号源波形质量分析:时域 / 频谱 / 解调 EVM 及误差分解 / CCDF / 眼图。

输入:tb 导出的十进制采样文本(tb_bpsk_src.v +dump=...)
输出:docs/figs/ 下 5 张 PNG + docs/波形质量报告.md + 关键指标打印

用法: python3 scripts/analyze_wave.py tb/rtl_samples.txt 2000000
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import signal

FS = 50e6                      # 输出采样率
RS = 4.08e6                    # 码元速率
SPS = FS / RS                  # 12.2549
FTW = 350469331
ALPHA = 0.35
NTAPS = 99
CENTER = 49
FRAC = 14
AMP = 2797                     # 幅度寄存器默认值
FS_CODE = 4095                 # 13-bit 满量程

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 中文字体:优先使用 fontTools 从系统 TTC 中提取的简体字面(见仓库说明),
# 否则回退到 matplotlib 能识别的 JP 字面/英文字体
import matplotlib.font_manager as fm
_sc_otf = os.path.expanduser("~/.local/share/fonts/NotoSerifCJK-SC.otf")
if os.path.exists(_sc_otf):
    fm.fontManager.addfont(_sc_otf)
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Serif CJK SC",
                                   "Noto Sans CJK JP", "AR PL UMing CN", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# ---------- 与 RTL/golden 同源的参数 ----------
def rrc(t):
    t = np.asarray(t, dtype=np.float64)
    q = 4.0 * ALPHA * t
    with np.errstate(divide="ignore", invalid="ignore"):
        h = (np.sin(np.pi * t * (1 - ALPHA)) + q * np.cos(np.pi * t * (1 + ALPHA))) \
            / (np.pi * t * (1 - q * q))
    return np.where(np.abs(t) < 1e-12, 1.0 - ALPHA + 4.0 * ALPHA / np.pi, h)


def make_taps():
    n = np.arange(NTAPS)
    hf = rrc((n - CENTER) / SPS)
    hf = hf / hf[CENTER]                                   # 浮点理想(峰值归一)
    gq = np.array([int(v * 2**FRAC + 0.5) if v >= 0 else -int(-v * 2**FRAC + 0.5)
                   for v in hf], dtype=np.float64) / 2**FRAC   # Q1.14 量化
    return hf, gq


def strobes_and_data(n_samp):
    """码元边界位置与 ±1 数据,与 RTL 精确一致(种子=1)。"""
    m = np.arange(1, n_samp * FTW // 2**32 + 1, dtype=np.uint64)
    nm = ((m * (np.uint64(1) << np.uint64(32)) + np.uint64(FTW - 1))
          // np.uint64(FTW)).astype(np.int64) - 1
    lfsr, d, ds = 1, -1, np.empty(len(nm), dtype=np.float64)
    for k in range(len(nm)):
        ds[k] = d
        fb = ((lfsr >> 22) ^ (lfsr >> 17)) & 1
        lfsr = ((lfsr << 1) | fb) & 0x7FFFFF
        d = -1.0 if (lfsr & 1) else 1.0
    return nm, ds


def evm_at(y, nm, ds, off, k_lo, k_hi):
    yk = y[nm[k_lo:k_hi] + off]
    dk = ds[k_lo:k_hi]
    g = np.mean(yk * dk)
    err = yk - g * dk
    return np.sqrt(np.mean(err**2)) / g, g


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tb/rtl_samples.txt"
    n_samp = int(sys.argv[2]) if len(sys.argv) > 2 else 2_000_000
    figdir = os.path.join(ROOT, "docs", "figs")
    os.makedirs(figdir, exist_ok=True)

    x = np.loadtxt(src, dtype=np.float64)
    assert len(x) == n_samp, f"样本数 {len(x)} != {n_samp}"
    hf, gq = make_taps()
    nm, ds = strobes_and_data(n_samp)
    M = len(nm)
    rms = np.sqrt(np.mean(x**2))
    print(f"样本 {len(x)},码元 {M},rms = {rms:.2f} LSB,幅度 = {AMP}")

    # ---------- 图1 时域 ----------
    n0, n1 = 120, 620
    fig, ax = plt.subplots(figsize=(10, 4.6), constrained_layout=True)
    ax.plot(np.arange(n0, n1), x[n0:n1], lw=1.0, color="#0a6ebd")
    for ns in nm[(nm >= n0) & (nm < n1)]:
        ax.axvline(ns, color="gray", lw=0.4, alpha=0.5)
    ax.axhline(AMP, color="green", lw=0.7, ls=":", label="+A / −A (±2797)")
    ax.axhline(-AMP, color="green", lw=0.7, ls=":")
    ax.axhline(FS_CODE, color="red", lw=0.7, ls="--", label="满量程 ±4095")
    ax.axhline(-FS_CODE, color="red", lw=0.7, ls="--")
    ax.set_xlim(n0, n1)
    ax.set_title(f"图1  输出时域波形(RTL 仿真导出,50 MSPS,{n1-n0} 采样 ≈ {(n1-n0)/SPS:.0f} 码元;\n灰色竖线为码元边界)")
    ax.set_xlabel("采样序号 n(20 ns/采样)")
    ax.set_ylabel("幅度 (LSB)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)
    fig.savefig(os.path.join(figdir, "fig1_time.png"), dpi=140)
    plt.close(fig)

    # ---------- 图2 频谱(Welch PSD) ----------
    f, pxx = signal.welch(x, fs=FS, window="hamming", nperseg=2**16,
                          noverlap=2**15, return_onesided=False, detrend="constant")
    order = np.argsort(f)
    f, pxx = f[order] / 1e6, pxx[order]
    pxx_db = 10 * np.log10(pxx / 4096**2 + 1e-30)   # dBFS/Hz(满量程 4096)
    edge = RS * (1 + ALPHA) / 2 / 1e6               # 2.754 MHz
    inb = np.abs(f) < edge
    oob1 = (np.abs(f) >= edge) & (np.abs(f) < 8.0)
    oob2 = np.abs(f) >= 8.0
    p_in, p_o1, p_o2 = (np.trapezoid(pxx[w], f[w]) for w in (inb, oob1, oob2))
    floor = np.median(pxx_db[np.abs(f) > 12])

    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    ax.plot(f, pxx_db, lw=0.7, color="#0a6ebd")
    ax.axvspan(-edge, edge, color="green", alpha=0.08)
    ax.axvline(edge, color="green", ls="--", lw=0.8)
    ax.axvline(-edge, color="green", ls="--", lw=0.8)
    ax.axhline(floor, color="red", ls=":", lw=0.8,
               label=f"噪声底 ≈ {floor:.1f} dBFS/Hz")
    ax.annotate(f"占用带宽 (1+α)Rs = {2*edge:.2f} MHz", xy=(edge, pxx_db[inb].max()),
                xytext=(3.2, pxx_db[inb].max() + 3),
                arrowprops=dict(arrowstyle="->", color="green"), color="green", fontsize=9)
    ax.set_xlim(-8, 8)
    ax.set_ylim(floor - 10, 5)
    ax.set_title("图2  功率谱(Welch,汉明窗 65536 点 50% 重叠,FFT 谱密度)")
    ax.set_xlabel("频率 (MHz)")
    ax.set_ylabel("PSD (dBFS/Hz)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower center", fontsize=9)
    fig.savefig(os.path.join(figdir, "fig2_spectrum.png"), dpi=140)
    plt.close(fig)
    spec = dict(mainlobe=2 * edge, floor=floor,
                p_in=p_in, p_oob=(p_o1 + p_o2),
                oob_ratio=10 * np.log10((p_o1 + p_o2) / p_in))
    print(f"频谱: 主瓣 {spec['mainlobe']:.3f} MHz, 噪声底 {floor:.1f} dBFS/Hz, "
          f"带外/带内功率比 {spec['oob_ratio']:.1f} dB")

    # ---------- 图3 解调 / EVM 及误差分解 ----------
    taps_rx = hf                                   # 接收端匹配滤波(浮点理想)
    y = np.convolve(x, taps_rx)                    # y[m] = Σ taps_rx[j]·x[m−j]
    # 对齐扫描:找 |Σ y·d| 最大的整数延迟
    k_lo, k_hi = 100, M - 100
    best = (-1, 0)
    for off in range(-150, 151):
        c = abs(np.dot(y[nm[k_lo:k_hi] + off], ds[k_lo:k_hi]))
        if c > best[0]:
            best = (c, off)
    off_best = best[1]
    evm_meas, gain = evm_at(y, nm, ds, off_best, k_lo, k_hi)
    yk0 = y[nm[k_lo:k_hi] + off_best]
    dk0 = ds[k_lo:k_hi]
    evm_peak = np.max(np.abs(yk0 - gain * dk0)) / gain

    # 分解:各误差源在符号级直接作差(避免被主导项淹没)
    #   A 链:浮点理想抽头(仅 RRC ±4 截断 ISI)
    #   B 链:Q1.14 抽头(A 与 B 之差 = 抽头量化)
    #   RTL:x 即 RTL 输出(B 与 RTL 之差 = 13bit 输出量化 + 取整)
    imp = np.zeros(n_samp)
    imp[nm[:M]] = ds
    xa = np.convolve(imp, hf)[:n_samp]
    yA = np.convolve(xa, taps_rx)
    evm_a, _ = evm_at(yA, nm, ds, off_best, k_lo, k_hi)
    xb = np.convolve(imp, gq)[:n_samp]
    yB = np.convolve(xb, taps_rx)
    yAk = yA[nm[k_lo:k_hi] + off_best]
    yBk = yB[nm[k_lo:k_hi] + off_best]
    yRk = y[nm[k_lo:k_hi] + off_best]
    dref = ds[k_lo:k_hi]
    g0 = np.mean(yAk * dref)
    evm_tapq = np.sqrt(np.mean((yBk - yAk) ** 2)) / g0
    # RTL 输出在 AMP 缩放域,先做最小二乘增益对齐再作差
    g_rtl = np.mean(yRk * dref)
    yBn = yBk * (g_rtl / np.mean(yBk * dref))
    evm_quant = np.sqrt(np.mean((yRk - yBn) ** 2)) / g_rtl
    evm_comb = np.sqrt(evm_a**2 + evm_tapq**2 + evm_quant**2)

    offsets = np.arange(off_best - 6, off_best + 7)
    evm_curve = [evm_at(y, nm, ds, int(o), k_lo, k_hi)[0] for o in offsets]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True)
    ax1.semilogy(offsets - off_best, np.array(evm_curve) * 100, "o-", ms=4, color="#0a6ebd")
    ax1.set_xlabel("采样相位偏移 (采样)")
    ax1.set_ylabel("EVM_RMS (%)")
    ax1.set_title(f"匹配滤波后 EVM 对采样相位的敏感度\n(最优相位 = 码元边界 +{off_best})")
    ax1.grid(alpha=0.3, which="both")
    items = [("RRC ±4 码元截断 (ISI)", evm_a),
             ("抽头 Q1.14 量化", evm_tapq),
             ("13-bit 输出量化+取整", evm_quant),
             ("实测总计 (RTL)", evm_meas)]
    names = [i[0] for i in items]
    vals_db = [20 * np.log10(i[1]) for i in items]
    bars = ax2.bar(range(len(items)), vals_db, color=["#88b8d8", "#88b8d8", "#88b8d8", "#c44e52"])
    ax2.set_xticks(range(len(items)))
    ax2.set_xticklabels(["RRC截断\n(ISI)", "抽头\nQ1.14", "13bit\n量化", "实测\n总计"], fontsize=9)
    for b, v in zip(bars, vals_db):
        ax2.text(b.get_x() + b.get_width() / 2, v - 6, f"{v:.1f} dB",
                 ha="center", fontsize=9, color="black")
    ax2.set_ylim(min(vals_db) - 12, 2)
    ax2.set_ylabel("EVM (dB,越小越好)")
    ax2.set_title("EVM 误差分解")
    ax2.grid(alpha=0.3, axis="y")
    fig.suptitle(f"图3  解调与 EVM   ——  EVM_RMS = {evm_meas*100:.4f} %  "
                 f"({20*np.log10(evm_meas):.1f} dB),  EVM_peak = {evm_peak*100:.3f} %", fontsize=11)
    fig.savefig(os.path.join(figdir, "fig3_evm.png"), dpi=140)
    plt.close(fig)
    yk = y[nm[k_lo:k_hi] + off_best]
    dk = ds[k_lo:k_hi]
    g = np.mean(yk * dk)
    evm_peak = np.max(np.abs(yk - g * dk)) / g
    print(f"EVM: RMS {evm_meas*100:.4f}% ({20*np.log10(evm_meas):.1f} dB), "
          f"peak {evm_peak*100:.3f}%, 对齐延迟 {off_best}, 合成校验 "
          f"{evm_comb*100:.4f}% (实测 {evm_meas*100:.4f}%), "
          f"截断ISI {evm_a:.2e} / 抽头量化 {evm_tapq:.2e} / 13bit量化 {evm_quant:.2e}")

    # ---------- 图4 CCDF ----------
    ax_abs = np.sort(np.abs(x))
    t_db = np.arange(0, 8.001, 0.01)
    thr = rms * 10 ** (t_db / 20)   # 幅度 dB:20log10
    ccdf = 1.0 - np.searchsorted(ax_abs, thr) / len(ax_abs)
    crest = 20 * np.log10(np.max(np.abs(x)) / rms)
    margin_fs = 20 * np.log10(FS_CODE / rms)

    fig, ax = plt.subplots(figsize=(8.5, 5), constrained_layout=True)
    ax.semilogy(t_db, np.maximum(ccdf, 1 / len(x) * 0.7), lw=1.6, color="#0a6ebd",
                label="CCDF(|x|/RMS),2M 采样")
    ax.axvline(crest, color="green", ls="--", lw=1,
               label=f"实测峰值 {crest:.2f} dB(零削顶)")
    ax.axvline(margin_fs, color="red", ls=":", lw=1.2,
               label=f"满量程线 {margin_fs:.2f} dB(越过即削顶)")
    ax.set_ylim(5e-7, 2)
    ax.set_xlim(0, 8)
    ax.set_title("图4  CCDF 峰均比统计")
    ax.set_xlabel("瞬时幅度 / RMS (dB)")
    ax.set_ylabel("超越概率 P(|x| > 阈值)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=9)
    fig.savefig(os.path.join(figdir, "fig4_ccdf.png"), dpi=140)
    plt.close(fig)
    print(f"CCDF: rms {rms:.2f}, 峰值 {np.max(np.abs(x))}, crest {crest:.2f} dB, FS 裕量 {margin_fs:.2f} dB")

    # ---------- 图5 眼图 ----------
    w_l, w_r = 6, 18          # 码元边界前 6 / 后 18 采样 ≈ ±0.5T
    rows = []
    for k in range(500, min(1700, M - 100)):
        s = nm[k] + off_best
        if s - w_l < 0 or s + w_r >= len(y):
            continue
        rows.append(y[s - w_l: s + w_r])
    seg = np.array(rows)
    t_sym = (np.arange(-w_l, w_r)) / SPS
    fig, ax = plt.subplots(figsize=(8.5, 5), constrained_layout=True)
    ax.plot(t_sym, seg.T, color="#0a6ebd", lw=0.5, alpha=0.06)
    ax.axvline(0, color="red", ls=":", lw=1)
    ax.set_title(f"图5  匹配滤波后眼图({len(seg)} 码元迹线叠加,红色竖线=判决时刻)")
    ax.set_xlabel("相对码元边界的时间 (码元周期)")
    ax.set_ylabel("匹配滤波输出 (LSB)")
    ax.grid(alpha=0.3)
    fig.savefig(os.path.join(figdir, "fig5_eye.png"), dpi=140)
    plt.close(fig)

    # ---------- 汇总 ----------
    print("DONE")


if __name__ == "__main__":
    main()
