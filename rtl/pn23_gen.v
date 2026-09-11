// PN23 伪随机序列发生器:特征多项式 x^23 + x^18 + 1(ITU-T O.150 同族),
// Fibonacci 结构左移,周期 2^23-1 = 8388607 码元(约 2.056 s @ 4.08 MHz)。
//
// 与 golden model 的约定:边界到来时先取 lfsr[0] 作为当前码元,再推进。
// 映射:位 0 = 0 -> +A,位 0 = 1 -> -A(即 d = 1 - 2*bit)。
module pn23_gen #(
    parameter [22:0] SEED = 23'h000001   // 非零种子
) (
    input  wire clk,
    input  wire rst_n,
    input  wire sym_strobe,              // 来自 sym_timing_nco
    output wire pn_bit                   // 当前码元原始位(0=+A, 1=-A)
);

    reg [22:0] lfsr;
    wire       fb = lfsr[22] ^ lfsr[17]; // x^23 与 x^18 项

    assign pn_bit = lfsr[0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            lfsr <= SEED;
        else if (sym_strobe)
            lfsr <= {lfsr[21:0], fb};
    end

endmodule
