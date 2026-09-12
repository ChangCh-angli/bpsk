// RRC 脉冲成形器(分数延迟相位合成 + 转置直接型)。
//
// 每码元采样数 625/51 为非整数,若冲激只落在整数采样点,匹配滤波 EVM 存在
// ≈4.65%(−26.7 dB)的定时栅格抖动地板。本模块按 NCO 的分数相位查表注入
// 分数延迟的 RRC 系数,把码元位置精确到 1/51 采样(残余抖动 ≈0.09% EVM),
// 配合 ±6 码元跨度(截断 ≈0.22% EVM,实测甜点),总 EVM ≈0.25%。
//
// 输入是码元冲激串(strobe 时 ±1,其余为 0),转置直接型中每个抽头级的
// 乘法退化为"查表 + 有条件加减常数",滤波器核内零乘法器,仅输出级一个
// 乘法(累加器和 × 幅度)。
//
// 系数表:51 相位 × 149 阶 Q1.14(2^14 定标,峰值归一),由
// scripts/gen_rrc_taps.py 生成,$readmemh 加载;表项 p*NTAPS+i 为相位 p
// 的第 i 个系数。位宽:|acc| <= Σ|tap| <= 275 351 < 2^19,20-bit 足够。
//
// 输出:out = sat13((acc[0] * amplitude + 2^13) >>> 14)
// 算术右移向下取整(round half up),与 scripts/golden_bpsk.c 逐位一致。
//
// mode_nrz = 1 为调试旁路:输出按码元保持的 ±amplitude 阶梯波(无成形)。
module rrc_pulse #(
    parameter integer NTAPS    = 149,
    parameter integer PHASES   = 51,
    parameter integer TAP_W    = 16,      // Q1.14 抽头位宽
    parameter integer TAP_FRAC = 14,      // 定标 2^14,与 gen_rrc_taps.py 一致
    parameter integer ACC_W    = 20,      // 累加器位宽
    parameter integer OUT_W    = 13,
    parameter         PHASE_FILE = "rtl/rrc_phases.mem"
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       ce,        // 采样使能,50 MHz
    input  wire                       imp_en,    // 冲激有效(码元边界)
    input  wire                       imp_neg,   // 冲激符号:0=+1, 1=-1
    input  wire [5:0]                 phase_idx, // 分数延迟相位(sym_timing_nco)
    input  wire                       mode_nrz,  // 1: NRZ 调试旁路
    input  wire signed [OUT_W-1:0]    amplitude, // 冲激幅度 LSB(<=2797 保证零削顶)
    output reg                        out_valid,
    output reg  signed [OUT_W-1:0]    out_sample
);

    reg signed [TAP_W-1:0] rom [0:PHASES*NTAPS-1];
    reg signed [ACC_W-1:0] rom_e [0:PHASES*NTAPS-1];  // 加载时显式符号扩展
    integer p_idx, j_idx;
    initial begin
        $readmemh(PHASE_FILE, rom);
        for (p_idx = 0; p_idx < PHASES; p_idx = p_idx + 1)
            for (j_idx = 0; j_idx < NTAPS; j_idx = j_idx + 1)
                rom_e[p_idx*NTAPS + j_idx] =
                    {{(ACC_W-TAP_W){rom[p_idx*NTAPS + j_idx][TAP_W-1]}}, rom[p_idx*NTAPS + j_idx]};
    end

    // ---- 转置直接型累加器阵列(滤波器核,无乘法器) ----
    // 注意:冲激贡献先经有符号中间变量(赋值语境完成符号扩展),
    // 再做同宽度有符号加法。若把抽头直接混入含无符号操作数的表达式,
    // 整条表达式会被污染成无符号求值,负抽头将被零扩展而出错。
    reg signed [ACC_W-1:0] acc   [0:NTAPS-1];
    reg signed [ACC_W-1:0] y_r;      // y(n) = 更新后的 acc[0]
    reg signed [ACC_W-1:0] y_inc;
    integer rom_base;
    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < NTAPS; i = i + 1)
                acc[i] <= {ACC_W{1'b0}};
            y_r <= {ACC_W{1'b0}};
        end else if (ce) begin
            /* verilator lint_off BLKSEQ */
            rom_base = phase_idx * NTAPS;
            for (i = 0; i < NTAPS; i = i + 1) begin : tapupd
                reg signed [ACC_W-1:0] prv;   // 后级旧值
                reg signed [ACC_W-1:0] inc;   // 本样本冲激贡献(查表)
                prv = (i == NTAPS-1) ? {ACC_W{1'b0}} : acc[i+1];
                inc = rom_e[rom_base + i];
                if (imp_neg)
                    inc = -inc;
                if (!imp_en)
                    inc = {ACC_W{1'b0}};
                acc[i] <= prv + inc;
            end
            // y(n) = acc[1](旧值) + x(n)*TAP[0],与 acc[0] 的下一状态同值
            y_inc = rom_e[rom_base];
            if (imp_neg)
                y_inc = -y_inc;
            if (!imp_en)
                y_inc = {ACC_W{1'b0}};
            /* verilator lint_on BLKSEQ */
            y_r <= acc[1] + y_inc;
        end
    end

    // ---- NRZ 调试旁路:±(amplitude << TAP_FRAC),按码元保持 ----
    // 与主通路共用输出流水线,延迟对齐。
    wire signed [2*ACC_W:0] amp_ext = {{(2*ACC_W+1-OUT_W){amplitude[OUT_W-1]}}, amplitude};
    reg signed [2*ACC_W:0]  nrz_lvl;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            nrz_lvl <= {(2*ACC_W+1){1'b0}};
        else if (ce && imp_en)
            nrz_lvl <= imp_neg ? -(amp_ext <<< TAP_FRAC)
                               :  (amp_ext <<< TAP_FRAC);
    end

    // ---- 输出级:幅度乘法、取整、饱和 ----
    reg                    v_d1, v_d2;
    reg signed [2*ACC_W:0] prod;

    localparam signed [2*ACC_W:0] HALF    = 1 <<< (TAP_FRAC-1);
    localparam signed [2*ACC_W:0] OUT_MAX = (1 << (OUT_W-1)) - 1;        // 4095
    localparam signed [2*ACC_W:0] OUT_MIN = -(1 << (OUT_W-1));           // -4096

    wire signed [2*ACC_W:0] rnd = (prod + HALF) >>> TAP_FRAC;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            prod       <= {(2*ACC_W+1){1'b0}};
            v_d1       <= 1'b0;
            v_d2       <= 1'b0;
            out_valid  <= 1'b0;
            out_sample <= {OUT_W{1'b0}};
        end else begin
            v_d1 <= ce;
            v_d2 <= v_d1;
            prod <= mode_nrz ? nrz_lvl : (y_r * $signed(amplitude));
            out_valid  <= v_d2;
            out_sample <= (rnd > OUT_MAX) ? OUT_MAX[OUT_W-1:0]
                        : (rnd < OUT_MIN) ? OUT_MIN[OUT_W-1:0]
                        :                   rnd[OUT_W-1:0];
        end
    end

endmodule
