// 码元定时 NCO:相位累加器小数分频 + 分数相位输出。
//
// 输出采样率 50 MHz,码元速率 4.08 MHz,每码元 12.2549 = 625/51 个采样
// (非整数),码元边界由 32-bit 相位累加器的进位产生:
//     FTW = round(4.08e6 / 50e6 * 2^32) = 350469331
// 速率误差 ≈ 0.004 Hz;相邻码元 12/13 个采样交替。
//
// 分数相位:边界处理想码元位置 t = n + f,f = 1 - r/FTW(r 为更新后的
// 相位余量 acc)。f 以 1/51 采样为步长量化输出 phase_idx,供 rrc_pulse
// 查分数延迟系数表,消除定时栅格抖动(51 相位残余抖动 ≈0.09% EVM)。
module sym_timing_nco #(
    parameter [31:0] FTW = 32'd350469331
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       ce,         // 采样使能,50 MHz(时钟的 1/2 占空比)
    output wire       sym_strobe, // 码元边界脉冲,与 ce 同相位,每码元一拍
    output wire [5:0] phase_idx   // 分数延迟相位索引,与 sym_strobe 同相位有效
);

    reg  [31:0] acc;
    wire [32:0] sum = {1'b0, acc} + FTW;

    // 本采样步发生回绕 <=> 步进后越过 2^32 <=> 码元边界
    assign sym_strobe = ce & sum[32];

    // 分数相位:用更新后的余量 r = sum[31:0],phi = (FTW-1-r)*51/FTW。
    // 除以 FTW 用 magic number 实现:M = floor(2^45/FTW) = 100392,
    // 误差 <= (N/FTW)*(2^45-M*FTW)/2^45 <= 51*4.1e-8,可忽略。
    // acc 恒 < FTW,故 FTW-1-r 不回绕,phi <= 50.99,截位后 [0,50]。
    /* verilator lint_off UNUSEDSIGNAL */
    wire [31:0] acc_next   = sum[31:0];
    wire [31:0] phase_rem  = FTW - 32'd1 - acc_next;
    wire [34:0] phase_num  = phase_rem * 35'd51;
    wire [51:0] phase_prod = {{17{1'b0}}, phase_num} * {{35{1'b0}}, 17'd100392};
    // verilator lint_on UNUSEDSIGNAL
    // phi 上界 50.99 < 51,prod[51] 恒为 0,7 截 6 位安全
    /* verilator lint_off WIDTHTRUNC */
    assign phase_idx = phase_prod[51:45];
    /* verilator lint_on WIDTHTRUNC */

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            acc <= 32'd0;
        else if (ce)
            acc <= sum[31:0];
    end

endmodule
