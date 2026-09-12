/*
 * golden_bpsk.c -- BPSK 信号源的定点逐位 golden model(分数延迟相位合成版)
 *
 * 与 RTL 逐位等价,数据通路完全同构(务必与 rtl/ 保持同步):
 *   - 32-bit 相位累加器,FTW = 350469331,进位即码元边界;
 *     边界处相位余量 r = acc 唯一确定分数偏移 f = 1 - r/FTW
 *   - 相位索引 phi = ((FTW - 1 - acc) * 51) >> 32 ∈ [0,50]
 *   - PN23: x^23+x^18+1,Fibonacci 左移,位 0 为当前码元(0 -> +A, 1 -> -A)
 *   - 注入:查相位表 row = tap[phi*149 .. +148],转置直接型
 *     acc[i] = acc[i+1] + x*row[i](x ∈ {-1,0,+1})
 *   - 输出:out = sat13( (y*A + 2^13) >>> 14 ),算术右移向下取整,
 *     饱和到 [-4096, 4095]
 *
 * 用法: golden_bpsk <n_samples> <amp> <seed> <ftw> <phases_dec> <out_hex>
 * 例:   golden_bpsk 2000000 2797 1 350469331 scripts/rrc_phases_dec.txt tb/golden_out.hex
 * 全周期峰值复核(约 1.028e8 采样,数十秒):
 *        golden_bpsk 102801655 2797 1 350469331 scripts/rrc_phases_dec.txt /dev/null
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define NTAPS   149
#define PHASES  51
#define TAP_FRAC 14                  /* Q1.14,与 gen_rrc_taps.py 一致 */
#define OUT_MAX  4095
#define OUT_MIN  (-4096)

static int32_t tap[PHASES * NTAPS];

int main(int argc, char **argv)
{
    if (argc != 7) {
        fprintf(stderr, "usage: %s <n_samples> <amp> <seed> <ftw> <phases_dec> <out_hex>\n",
                argv[0]);
        return 1;
    }
    long long   n_samp = atoll(argv[1]);
    int32_t     amp    = (int32_t)strtol(argv[2], NULL, 0);
    uint32_t    seed   = (uint32_t)strtoul(argv[3], NULL, 0);
    uint32_t    ftw    = (uint32_t)strtoul(argv[4], NULL, 0);
    FILE       *f = fopen(argv[5], "r");
    if (!f || seed == 0) { fprintf(stderr, "bad phase file or zero seed\n"); return 1; }
    for (int i = 0; i < PHASES * NTAPS; i++)
        if (fscanf(f, "%d", &tap[i]) != 1) { fprintf(stderr, "phase file short\n"); return 1; }
    fclose(f);

    FILE *o = fopen(argv[6], "w");
    if (!o) { fprintf(stderr, "cannot open output\n"); return 1; }

    uint32_t lfsr = seed, acc = 0;
    int32_t  accr[NTAPS];
    memset(accr, 0, sizeof(accr));
    int32_t  d = (lfsr & 1u) ? -1 : 1;
    int32_t  maxabs = 0;
    long long sat = 0;

    for (long long s = 0; s < n_samp; s++) {
        /* --- 码元定时 NCO --- */
        uint32_t prev = acc;
        acc += ftw;
        int strobe = (acc < prev);

        /* --- 相位索引(仅边界处有效;非边界 acc 无意义,不计算) ---
         * phi = (FTW-1-acc)*51/FTW,除法用 magic number:
         * M = floor(2^45/FTW) = 100392,误差可忽略(同 RTL) */
        const int32_t *row = NULL;

        /* --- PN23:先取当前位,再推进 --- */
        int32_t x = 0;
        if (strobe) {
            uint32_t phi = (uint32_t)(((uint64_t)(ftw - 1u - acc) * 51ULL * 100392ULL) >> 45);
            if (phi >= PHASES) phi = PHASES - 1;   /* 防御,正常不会触发 */
            row = &tap[phi * NTAPS];
            x = d;
            uint32_t fb = ((lfsr >> 22) ^ (lfsr >> 17)) & 1u;
            lfsr = ((lfsr << 1) | fb) & 0x7FFFFFu;
            d = (lfsr & 1u) ? -1 : 1;
        }

        /* --- 转置直接型:先算输出(用更新前的 acc[1]),再更新累加器 --- */
        int32_t y = accr[1] + (row ? x * row[0] : 0);
        for (int i = 0; i < NTAPS; i++) {
            int32_t nxt = (i == NTAPS - 1) ? 0 : accr[i + 1];
            accr[i] = row ? (nxt + x * row[i]) : nxt;
        }

        /* --- 幅度 + 取整 + 饱和 --- */
        int64_t prod = (int64_t)y * amp;
        int64_t rnd  = (prod + (1LL << (TAP_FRAC - 1))) >> TAP_FRAC;
        int32_t out;
        if (rnd > OUT_MAX)      { out = OUT_MAX; sat++; }
        else if (rnd < OUT_MIN) { out = OUT_MIN; sat++; }
        else                    out = (int32_t)rnd;
        if (out > maxabs) maxabs = out;
        if (-out > maxabs) maxabs = -out;

        fprintf(o, "%04x\n", (unsigned)out & 0x1FFFu);
    }
    fclose(o);

    printf("golden: n=%lld amp=%d seed=0x%X ftw=%u  max|out|=%d  saturated=%lld\n",
           n_samp, amp, seed, ftw, maxabs, sat);
    return 0;
}
