# BPSK 信号源 -- 生成抽头 / golden model / 仿真
# 用法:  make          (等价于 make taps golden sim)
#         make peak    (golden 跑完整 PN23 周期,复核零削顶,约 1 分钟)
#         make sim N_SAMPLES=8000000 AMP=2796   (改参数复跑)

N_SAMPLES ?= 2000000
AMP       ?= 2797
SEED      ?= 1
FTW       ?= 350469331
PEAK_N    ?= 102801655    # 一个 PN23 周期的采样数(8388607 码元)

RTL = rtl/pn23_gen.v rtl/sym_timing_nco.v rtl/rrc_pulse.v rtl/bpsk_src_top.v

.PHONY: all taps golden sim peak lint clean

all: taps golden sim

taps:
	python3 scripts/gen_rrc_taps.py

tb/golden_bpsk: scripts/golden_bpsk.c
	gcc -O2 -Wall -o $@ $<

golden: tb/golden_bpsk
	./tb/golden_bpsk $(N_SAMPLES) $(AMP) $(SEED) $(FTW) scripts/rrc_taps_dec.txt tb/golden_out.hex

tb/sim.vvp: $(RTL) tb/tb_bpsk_src.v
	iverilog -g2005 -Wall -o $@ $(RTL) tb/tb_bpsk_src.v

sim: tb/sim.vvp golden
	vvp tb/sim.vvp +n=$(N_SAMPLES) +amp=$(AMP)

# 完整 PN23 周期峰值复核(零削顶 => saturated 必须为 0)
peak: tb/golden_bpsk
	./tb/golden_bpsk $(PEAK_N) $(AMP) $(SEED) $(FTW) scripts/rrc_taps_dec.txt /dev/null

lint:
	verilator --lint-only -Wall --top-module bpsk_src_top $(RTL)

clean:
	rm -f tb/golden_bpsk tb/golden_out.hex tb/sim.vvp tb/wave.vcd
