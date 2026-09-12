// BPSK 基带信号源顶层。
//
//   输出采样率 50 MHz(out_valid 每 2 个时钟一拍)
//   码元速率   4.08 MHz(NCO 小数分频,FTW=350469331)
//   码元       PN23(x²³+x¹⁸+1,种子参数)
//   成形       RRC α=0.35,149 阶 Q1.14,±6 码元跨度,
//              51 相位分数延迟合成(消除定时栅格抖动)
//   输出       13-bit 有符号基带实信号,FS = ±4096
//
// amplitude 默认 2797 时 PN23 全周期(8388607 码元)零削顶(见波形质量报告;
// 幅度与波形峰值绑定,改动成形参数后需用 make peak 复核)。
// mode_nrz = 1 输出未成形的 NRZ 阶梯波,供链路分段调试。
module bpsk_src_top #(
    parameter [22:0]  PN_SEED   = 23'h000001,
    parameter [31:0]  FTW       = 32'd350469331,
    parameter         PHASE_FILE = "rtl/rrc_phases.mem"
) (
    input  wire                      clk,        // 100 MHz(50 MHz 的 2 倍)
    input  wire                      rst_n,      // 异步低有效
    input  wire                      mode_nrz,   // 1: NRZ 调试旁路
    input  wire signed [12:0]        amplitude,  // 冲激幅度 LSB
    output wire                      sym_strobe, // 码元边界(联调对齐用)
    output wire                      out_valid,  // 50 MHz 采样有效
    output wire signed [12:0]        out_sample
);

    // 采样使能:每 2 个时钟一拍 => 50 MHz
    reg ce_phase;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            ce_phase <= 1'b0;
        else
            ce_phase <= ~ce_phase;
    end
    wire ce = ce_phase;

    wire pn_bit;
    wire [5:0] phase_idx;

    sym_timing_nco #(.FTW(FTW)) u_nco (
        .clk(clk), .rst_n(rst_n), .ce(ce),
        .sym_strobe(sym_strobe), .phase_idx(phase_idx)
    );

    pn23_gen #(.SEED(PN_SEED)) u_pn (
        .clk(clk), .rst_n(rst_n), .sym_strobe(sym_strobe), .pn_bit(pn_bit)
    );

    rrc_pulse #(.PHASE_FILE(PHASE_FILE)) u_shaper (
        .clk       (clk),
        .rst_n     (rst_n),
        .ce        (ce),
        .imp_en    (sym_strobe),
        .imp_neg   (pn_bit),
        .phase_idx (phase_idx),
        .mode_nrz  (mode_nrz),
        .amplitude (amplitude),
        .out_valid (out_valid),
        .out_sample(out_sample)
    );

endmodule
