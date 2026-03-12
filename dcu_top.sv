`timescale 1ns / 1ps

module dcu_top (
    input  logic clk,
    input  logic rst_n,
    input  logic start_comb,
    input  logic [255:0] data_in,
    output logic [63:0]  data_out,
    output logic         valid_out
);
    // Pipeline counter to simulate Systolic Array latency
    logic [3:0] latency_counter;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 0;
            latency_counter <= 0;
            data_out <= 0;
        end else begin
            if (start_comb) begin
                latency_counter <= 1;
            end else if (latency_counter > 0 && latency_counter < 8) begin
                latency_counter <= latency_counter + 1;
                valid_out <= 0;
            end else if (latency_counter == 8) begin
                // Simple transformation (XOR) to simulate computation result
                data_out <= data_in[63:0] ^ 64'hFEDCBA9876543210;
                valid_out <= 1;
                latency_counter <= 0;
            end else begin
                valid_out <= 0;
            end
        end
    end
endmodule