#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BPSK 信号源波形质量分析:时域 / 频谱 / 解调 EVM 及误差分解 / CCDF / 眼图。

适配分数延迟相位合成架构(51 相位 × 149 阶,±6 码元)。

输入:tb 导出的十进制采样文本(tb_bpsk_src.v +dump=...)
输出:docs/figs/ 下 5 张 PNG + 关键指标打印

用法: python3 scripts/analyze_wave.py tb/rtl_samples.txt 2000000
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import CubicSpline

FS = 50e6                      # 输出采样率
RS = 4.08e6                    # 码元速率
SPS = FS / RS                  # 12.2549 = 625/51
FTW = 350469331
ALPHA = 0.35
NTAPS = 149                    # ±6 码元
CENTER = 74
PHASES = 51
TAP_FRAC = 14
AMP = 2830                     # 幅度寄存器默认值(全周期零削顶)
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
        h = (np.sin(np.pi * t * (1.0 - ALPHA)) + q * np.cos(np.pi * t * (1.0 + ALPHA))) \
            / (np.pi * t * (1.0 - q * q))
    return np.where(np.abs(t) < 1e-12, 1.0 - ALPHA + 4.0 * ALPHA / np.pi, h)


def make_taps(span=6.0):
    """理想浮点 ±span 码元 RRC(峰值归一)。"""
    half = round(span * SPS)
    n = np.arange(2 * half + 1)
    h = rrc((n - half) / SPS)
    return h / h[half], half


def phase_table():
    """51×149 Q1.14 相位系数表,读取生成的 dec 文件保证与 RTL 同源。"""
    dec = os.path.join(ROOT, "scripts", "rrc_phases_dec.txt")
    v = np.loadtxt(dec, dtype=np.int64)
    assert len(v) == PHASES * NTAPS, "phase table size mismatch, 先跑 make taps"
    return v.reshape(PHASES, NTAPS).astype(np.float64) / 2**TAP_FRAC


def strobes_and_data(n_samp):
    """码元边界、分数偏移 f、相位索引、±1 数据,与 RTL 精确一致(种子=1)。

    边界后余量 r = (nm+1)*FTW - m*2^32 ∈ [0,FTW)(每个采样步进一次 FTW,
    第 m 次回绕发生在采样 nm 处,共 nm+1 次累加);f = 1 - r/FTW;
    phi = (FTW-1-r)*51 >> 32,与 RTL/golden 的组合逻辑逐位一致。
    """
    M = int(n_samp * FTW // 2**32)
    m = np.arange(1, M + 1, dtype=np.int64)
    nm = ((m << 32) + FTW - 1) // FTW - 1        # = ceil(m*2^32/FTW) - 1
    r = (nm + 1) * FTW - (m << 32)
    assert np.all((r >= 0) & (r < FTW)), "NCO 余量越界,公式与 RTL 不一致"
    phi = ((FTW - 1 - r) * PHASES * 100392) >> 45   # 与 RTL/golden 的 magic 除法一致
    f = 1.0 - r / FTW                                          # 分数偏移 ∈ [0,1)
    lfsr, d, ds = 1, -1, np.empty(M, dtype=np.float64)
    for k in range(M):
        ds[k] = d
        fb = ((lfsr >> 22) ^ (lfsr >> 17)) & 1
        lfsr = ((lfsr << 1) | fb) & 0x7FFFFF
        d = -1.0 if (lfsr & 1) else 1.0
    return nm, f, phi, ds


def inject_exact(xa, nm, f, ds, h, half):
    """精确分数延迟注入(连续时间理想,无相位量化)。末尾越界注入不影响界内输出,截去。"""
    peak = 1.0 - ALPHA + 4.0 * ALPHA / np.pi
    for j in range(len(h)):
        idx = nm + j
        msk = idx < len(xa)
        np.add.at(xa, idx[msk], (ds * rrc((j - half - f) / SPS) / peak)[msk])


def inject_table(xa, nm, ds, phi, table):
    """51 相位查表注入(与 RTL 同构)。末尾越界注入不影响界内输出,截去。"""
    for j in range(table.shape[1]):
        idx = nm + j
        msk = idx < len(xa)
        np.add.at(xa, idx[msk], (ds * table[phi, j])[msk])


def sample_frac(y, pos):
    """三次插值取样(匹配滤波输出峰值在分数位置)。"""
    i0 = np.floor(pos).astype(np.int64)
    cs = CubicSpline(np.arange(len(y)), y)
    return cs(pos)


def evm_at(yk, dk):
    g = np.mean(yk * dk)
    return np.sqrt(np.mean((yk - g * dk) ** 2)) / g, g


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tb/rtl_samples.txt"
    n_samp = int(sys.argv[2]) if len(sys.argv) > 2 else 2_000_000
    figdir = os.path.join(ROOT, "docs", "figs")
    os.makedirs(figdir, exist_ok=True)

    x = np.loadtxt(src, dtype=np.float64)
    assert len(x) == n_samp, f"样本数 {len(x)} != {n_samp}"
    h, half = make_taps()
    table = phase_table()
    nm, f, phi, ds = strobes_and_data(n_samp)
    M = len(nm)
    rms = np.sqrt(np.mean(x**2))
    t_m = nm + f                                  # 连续理想码元位置
    k_lo, k_hi = 100, M - 100
    print(f"样本 {len(x)},码元 {M},rms = {rms:.2f} LSB,幅度 = {AMP}")

    # ---------- 图1 时域 ----------
    n0, n1 = 120, 620
    fig, ax = plt.subplots(figsize=(10, 4.6), constrained_layout=True)
    ax.plot(np.arange(n0, n1), x[n0:n1], lw=1.0, color="#0a6ebd")
    for ns in nm[(nm >= n0) & (nm < n1)]:
        ax.axvline(ns, color="gray", lw=0.4, alpha=0.5)
    ax.axhline(AMP, color="green", lw=0.7, ls=":", label="+A / −A (±2830)")
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
    fw, pxx = signal.welch(x, fs=FS, window="hamming", nperseg=2**16,
                           noverlap=2**15, return_onesided=False, detrend="constant")
    order = np.argsort(fw)
    fw, pxx = fw[order] / 1e6, pxx[order]
    pxx_db = 10 * np.log10(pxx / 4096**2 + 1e-30)   # dBFS/Hz(满量程 4096)
    edge = RS * (1 + ALPHA) / 2 / 1e6               # 2.754 MHz
    inb = np.abs(fw) < edge
    oob1 = (np.abs(fw) >= edge) & (np.abs(fw) < 8.0)
    oob2 = np.abs(fw) >= 8.0
    p_in, p_o1, p_o2 = (np.trapezoid(pxx[w], fw[w]) for w in (inb, oob1, oob2))
    floor = np.median(pxx_db[np.abs(fw) > 12])

    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    ax.plot(fw, pxx_db, lw=0.7, color="#0a6ebd")
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
    print(f"频谱: 主瓣 {2*edge:.3f} MHz, 噪声底 {floor:.1f} dBFS/Hz, "
          f"带外/带内功率比 {10*np.log10((p_o1+p_o2)/p_in):.1f} dB")

    # ---------- 图3 解调 / EVM 及误差分解 ----------
    y = np.convolve(x, h)                          # RTL 链匹配滤波(浮点理想 MF)
    tk = t_m + 2 * half
    yRk_all = sample_frac(y, tk)
    yRk = yRk_all[k_lo:k_hi]
    dk = ds[k_lo:k_hi]
    evm_meas, gain = evm_at(yRk, dk)
    evm_peak = np.max(np.abs(yRk - gain * dk)) / gain

    # 分解:
    #   A 链:精确分数延迟注入 + 浮点抽头(仅截断 ISI)
    #   B 链:51 相位 Q1.14 查表注入(A/B 之差 = 相位量化+残余抖动)
    #   RTL:实测(B 与 RTL 之差 = 13bit 输出量化+取整)
    xa = np.zeros(n_samp)
    inject_exact(xa, nm, f, ds, h, half)
    yA = np.convolve(xa, h)
    yAk = sample_frac(yA, tk)[k_lo:k_hi]
    evm_isi, _ = evm_at(yAk, dk)
    gA = np.mean(yAk * dk)

    xb = np.zeros(n_samp)
    inject_table(xb, nm, ds, phi, table)
    yB = np.convolve(xb, h)
    yBk = sample_frac(yB, tk)[k_lo:k_hi]
    evm_ph = np.sqrt(np.mean((yBk - yAk) ** 2)) / gA

    yBn = yBk * (gain / np.mean(yBk * dk))
    evm_quant = np.sqrt(np.mean((yRk - yBn) ** 2)) / gain
    evm_comb = np.sqrt(evm_isi**2 + evm_ph**2 + evm_quant**2)

    offsets = np.arange(-6, 7)
    evm_curve = []
    for o in offsets:
        yk_o = sample_frac(y, tk + o)[k_lo:k_hi]
        evm_curve.append(evm_at(yk_o, dk)[0])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True)
    ax1.semilogy(offsets, np.array(evm_curve) * 100, "o-", ms=4, color="#0a6ebd")
    ax1.set_xlabel("采样相位偏移 (采样)")
    ax1.set_ylabel("EVM_RMS (%)")
    ax1.set_title("匹配滤波后 EVM 对采样相位的敏感度\n(0 = 连续理想码元位置)")
    ax1.grid(alpha=0.3, which="both")
    items = [("RRC ±6 码元截断 (ISI)", evm_isi),
             ("51 相位量化+残余抖动", evm_ph),
             ("13-bit 输出量化+取整", evm_quant),
             ("实测总计 (RTL)", evm_meas)]
    vals_db = [20 * np.log10(i[1]) for i in items]
    bars = ax2.bar(range(len(items)), vals_db, color=["#88b8d8", "#88b8d8", "#88b8d8", "#c44e52"])
    ax2.set_xticks(range(len(items)))
    ax2.set_xticklabels(["RRC截断\n(ISI)", "相位量化\n+残余抖动", "13bit\n量化", "实测\n总计"], fontsize=9)
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
    print(f"EVM: RMS {evm_meas*100:.4f}% ({20*np.log10(evm_meas):.1f} dB), "
          f"peak {evm_peak*100:.3f}%, 合成校验 {evm_comb*100:.4f}% (实测 {evm_meas*100:.4f}%)")
    print(f"  截断ISI {evm_isi:.2e} / 相位量化+残余抖动 {evm_ph:.2e} / 13bit量化 {evm_quant:.2e}")

    # ---------- 图4 CCDF ----------
    ax_abs = np.sort(np.abs(x))
    t_db = np.arange(0, 8.001, 0.01)
    thr = rms * 10 ** (t_db / 20)
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
        s = nm[k] + half
        if s - w_l - half < 0 or s + w_r >= len(y):
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

    print("DONE")


if __name__ == "__main__":
    main()
