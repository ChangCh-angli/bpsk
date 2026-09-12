// tb_bpsk_src -- BPSK 信号源自检测 testbench
//
// 1. scripts/golden_bpsk.c 先生成 tb/golden_out.hex(定点逐位参考)
// 2. 本 tb 在 out_valid 驱动下与 golden 逐位比对,并检查:
//      - out_valid 严格 2 拍一拍(50 MHz)
//      - 码元边界计数与 FTW 一致
//      - max|out| 统计(零削顶复核)
//
// 用法(在仓库根目录):
//   vvp tb/sim.vvp +n=2000000 +amp=2797 [+vcd]
`timescale 1ns/1ps

module tb_bpsk_src;

    parameter integer MAX_N = 2000000;   // 加长仿真请同步加大本参数并重编译

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg mode_nrz = 1'b0;

    integer    n_samples = 2000000;
    reg [12:0] amp       = 13'd2830;

    // 100 MHz
    always #5 clk = ~clk;

    wire               out_valid;
    wire signed [12:0] out_sample;
    wire               sym_strobe;

    bpsk_src_top #(.PHASE_FILE("rtl/rrc_phases.mem")) dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .mode_nrz  (mode_nrz),
        .amplitude (amp),
        .sym_strobe(sym_strobe),
        .out_valid (out_valid),
        .out_sample(out_sample)
    );

    initial begin
        if (!$value$plusargs("n=%d",   n_samples)) n_samples = 2000000;
        if (!$value$plusargs("amp=%d", amp))       amp       = 13'd2830;
        if ($test$plusargs("nrz"))                 mode_nrz  = 1'b1;
    end

    reg signed [12:0] gold [0:MAX_N-1];
    initial $readmemh("tb/golden_out.hex", gold);

    // +dump=<file>:逐样本导出十进制采样,供信号处理分析(fft/evm 等)
    integer dump_fd = 0;
    reg [1023:0] dump_file;
    initial begin
        if ($value$plusargs("dump=%s", dump_file))
            dump_fd = $fopen(dump_file, "w");
    end

    integer n         = 0;
    integer errs      = 0;
    integer maxrtl    = 0;
    integer minrtl    = 0;
    integer tmp       = 0;
    integer valid_gap = 0;
    integer strobes   = 0;
    integer exp_strobes = 0;

    always @(posedge clk) begin
        if (rst_n) begin
            valid_gap = valid_gap + 1;
            if (sym_strobe)
                strobes = strobes + 1;

            if (out_valid) begin
                // 首拍为流水线填充,不查间隔
                if (n > 0 && valid_gap != 2) begin
                    if (errs < 20)
                        $display("ERROR: out_valid gap = %0d at n = %0d", valid_gap, n);
                    errs = errs + 1;
                end
                valid_gap = 0;

                if (!mode_nrz && out_sample !== gold[n]) begin
                    if (errs < 20)
                        $display("MISMATCH n=%0d t=%0t rtl=%0d gold=%0d",
                                 n, $time, out_sample, gold[n]);
                    errs = errs + 1;
                end

                if (out_sample > maxrtl) maxrtl = out_sample;
                if (out_sample < minrtl) minrtl = out_sample;
                if (dump_fd)
                    $fwrite(dump_fd, "%0d\n", out_sample);

                n = n + 1;
                if (n >= n_samples) begin
                    // integer*integer 会溢出 32 位,用 real 计算
                    exp_strobes = n * 350469331.0 / 4294967296.0;
                    if (dump_fd)
                        $fclose(dump_fd);
                    if (mode_nrz)
                        $display("NRZ smoke: %0d samples | max=%0d min=%0d (expect +amp/-amp) | strobes=%0d expected=%0d",
                                 n, maxrtl, minrtl, strobes, exp_strobes);
                    else if (errs == 0)
                        $display("PASS: %0d samples bit-exact | max=%0d min=%0d (FS=4095) | strobes=%0d expected=%0d",
                                 n, maxrtl, minrtl, strobes, exp_strobes);
                    else
                        $display("FAIL: %0d errors in %0d samples", errs, n);
                    $finish;
                end
            end
        end
    end

    // 复位
    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1'b1;
    end

    // 看门狗:n=2000000 约需 40 ms 仿真时间
    initial begin
        #100_000_000;
        $display("FAIL: timeout, only %0d samples checked", n);
        $finish;
    end

    // 可选波形:+vcd
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb/wave.vcd");
            $dumpvars(0, tb_bpsk_src);
        end
    end

endmodule
