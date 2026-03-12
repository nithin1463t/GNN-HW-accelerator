`timescale 1ns / 1ps

module pipelined_relu #(
    parameter NUM_ELEMENTS = 4,
    parameter DATA_WIDTH = 16
)(
    input  logic clk,
    input  logic rst_n,
    input  logic [(NUM_ELEMENTS*DATA_WIDTH)-1:0] in_flat,
    output logic [(NUM_ELEMENTS*DATA_WIDTH)-1:0] out_flat
);

    // Internal arrays to make the math readable
    logic signed [DATA_WIDTH-1:0] in_unpacked  [NUM_ELEMENTS];
    logic signed [DATA_WIDTH-1:0] out_unpacked [NUM_ELEMENTS];

    // Combinational block to unpack the 64-bit flat bus into array slots
    genvar i;
    generate
        for (i = 0; i < NUM_ELEMENTS; i++) begin : unpack_pack
            assign in_unpacked[i] = in_flat[(i*DATA_WIDTH) +: DATA_WIDTH];
            assign out_flat[(i*DATA_WIDTH) +: DATA_WIDTH] = out_unpacked[i];
        end
    endgenerate

    // Sequential block: The Pipeline Registers
    integer j;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (j = 0; j < NUM_ELEMENTS; j++) begin
                out_unpacked[j] <= '0;
            end
        end else begin
            for (j = 0; j < NUM_ELEMENTS; j++) begin
                // ReLU Logic: Check the Most Significant Bit (Sign Bit)
                // If in_unpacked[j][15] is 1, the number is negative -> snap to 0
                // Otherwise, the number is positive -> pass it through
                if (in_unpacked[j][DATA_WIDTH-1]) begin
                    out_unpacked[j] <= '0;
                end else begin
                    out_unpacked[j] <= in_unpacked[j];
                end
            end
        end
    end

    // --- WAVEFORM DUMPING ---
    initial begin
        // Keep it simple: dump directly to the simulator's working directory
        $dumpfile("pipelined_relu.vcd");
        $dumpvars(0, pipelined_relu);
        
        // This will print to your terminal right before the Cocotb test starts
        $display("\n=======================================================");
        $display("WAVEFORM DUMP: Generating pipelined_relu.vcd inside sim_build/");
        $display("=======================================================\n");
    end

endmodule