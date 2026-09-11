// 码元定时 NCO:相位累加器小数分频。
//
// 输出采样率 50 MHz,码元速率 4.08 MHz,每码元 12.2549 个采样(非整数),
// 因此码元边界由 32-bit 相位累加器的进位产生:
//     FTW = round(4.08e6 / 50e6 * 2^32) = 350469331
// 速率误差 ≈ 0.004 Hz;相邻码元 12/13 个采样交替,边界抖动 <= 1 个采样周期。
module sym_timing_nco #(
    parameter [31:0] FTW = 32'd350469331
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       ce,         // 采样使能,50 MHz(时钟的 1/2 占空比)
    output wire       sym_strobe  // 码元边界脉冲,与 ce 同相位,每码元一拍
);

    reg  [31:0] acc;
    wire [32:0] sum = {1'b0, acc} + FTW;

    // 本采样步发生回绕 <=> 步进后越过 2^32 <=> 码元边界
    assign sym_strobe = ce & sum[32];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            acc <= 32'd0;
        else if (ce)
            acc <= sum[31:0];
    end

endmodule
