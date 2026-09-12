# BPSK 基带信号源(Verilog)

PN23 码元 + RRC(α=0.35) 成形的 BPSK 基带信号源,用于测试/联调激励。

## 关键参数

| 项目 | 取值 | 说明 |
|---|---|---|
| 工作时钟 | 100 MHz | 单时钟域,50 MHz 采样使能(每 2 拍一采样) |
| 输出采样率 | 50 MHz | `out_valid` 每 2 个时钟一拍 |
| 码元速率 | 4.08 MHz | 每码元 12.2549 采样(非整数) |
| 码元定时 | FTW = 350469331 | 32-bit 相位累加器小数分频,速率误差 ≈ 0.004 Hz |
| 码元序列 | PN23 | x²³+x¹⁸+1,周期 8 388 607 ≈ 2.056 s |
| 脉冲成形 | RRC α=0.35 | 149 阶(±6 码元),Q1.14,51 相位分数延迟合成,滤波核无乘法器 |
| 输出 | 13-bit 有符号 | FS = ±4096,占用带宽 (1+α)Rs ≈ 5.51 MHz |
| EVM_RMS | 0.2445%(−52.2 dB) | 匹配滤波 + 理想码元位置取样,详见 docs/波形质量报告 V1.1 |
| 幅度 | 默认 2830(−3.21 dBFS) | 实测整周期峰值 4094,零削顶;`amplitude` 端口可调 |

## 结构

```
clk(100M) ──> [50M 采样使能] ──┬──────────────────────────────┐
                              ▼                              │
  ┌───────────┐  符号   ┌───────────────┐  ±1冲激  ┌─────────┴──────┐  13bit
  │ pn23_gen  │◄────────┤sym_timing_nco ├─────────►│   rrc_pulse    ├──────► out
  │ x²³+x¹⁸+1 │         │ 32b 相位累加器  │          │149阶×51相位查表│  幅度×/取整/饱和
  └───────────┘         └───────────────┘          └────────────────┘
```

- 由于每码元采样数非整数(625/51),RRC 抽头直接在 50 MHz 采样域按 t/T = n/12.2549 取样
  (不能用符号率多相插值结构);冲激位置以 1/51 采样的分数延迟精度合成(51 相位查表),
  消除定时栅格抖动,否则 EVM 存在 ≈4.65% 的地板。
- 滤波器输入是内部冲激串,转置直接型把乘法化为"有条件加减常数",核内零乘法器;
  仅输出级一个乘法(`y * amplitude`)。
- `mode_nrz = 1` 旁路成形器输出 ±amplitude 阶梯波(NRZ),供链路分段调试。
- `sym_strobe` 引出码元边界,便于接收端对齐。
- 幅度上界:20-bit 累加器可容纳任意幅度(Σ|tap|×4095 < 2¹⁹);零削顶要求
  `amplitude ≤ 2830`(完整 PN23 周期复核)。

## 目录

```
rtl/pn23_gen.v          PN23 序列发生器(参数化种子,须非零)
rtl/sym_timing_nco.v    码元定时 NCO(参数化 FTW)
rtl/rrc_pulse.v         RRC 成形器 + 输出定标 + NRZ 旁路
rtl/bpsk_src_top.v      顶层
rtl/rrc_phases.mem     51×149 分数延迟相位系数表(由脚本生成)
scripts/gen_rrc_taps.py 相位系数表生成(Q1.14,含位宽校验)
scripts/golden_bpsk.c   定点逐位 golden model(与 RTL 同构)
tb/tb_bpsk_src.v        自检测 testbench(逐位比对 + 节拍/幅度检查)
```

## 使用

```sh
make            # 生成抽头 -> golden -> 2M 采样逐位比对
make peak       # golden 跑完整 PN23 周期(1.028 亿采样),复核零削顶
make lint       # verilator lint
vvp tb/sim.vvp +n=100000 +amp=2797 +nrz    # NRZ 调试模式冒烟
vvp tb/sim.vvp +n=2000000 +vcd             # 输出 tb/wave.vcd 波形
```

加长 RTL 仿真需同步加大 `tb_bpsk_src.MAX_N` 并重新 `iverilog`。

## 实测结果(iverilog 13.0)

- `make sim`:2 000 000 采样与 golden model **逐位一致**,max=4094 / min=−4094,
  码元节拍数与 FTW 理论值一致。
- `make peak`:完整 PN23 周期 102 801 655 采样,saturated=0(零削顶)。
- EVM_RMS = 0.2445%(−52.2 dB),其中 ±6 码元截断 −53.0 dB、51 相位量化 −60.3 dB、
  13-bit 输出量化 −89.9 dB;峰均比 4.00 dB。详见 docs/波形质量报告 V1.1。

## 移植注意事项

- `rrc_pulse` 的累加运算全部经由有符号中间变量完成。不要把 `tap[i]` 直接混入
  含无符号操作数(如未加 `$signed` 的拼接常量)的表达式——Verilog 会把整条
  表达式按无符号求值,负抽头将被零扩展而出错。
- 相位系数表由 `scripts/gen_rrc_taps.py` 生成,改 α/跨度/相位数/位宽后需同步修改
  `rrc_pulse.v` 的 `NTAPS/PHASES/TAP_W/TAP_FRAC/ACC_W`、`golden_bpsk.c` 对应常量,以及
  `sym_timing_nco.v` 中的 magic number `M = floor(2^45/FTW)`,并重跑 `make` 全量回归。
