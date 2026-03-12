`timescale 1ns / 1ps

module utm_pingpong #(
    parameter DATA_WIDTH = 256
)(
    input  logic clk,
    input  logic rst_n,
    input  logic swap,         // Signal from GCU to switch banks
    
    // Write Port (from SAU)
    input  logic wr_en,
    input  logic [DATA_WIDTH-1:0] wr_data,
    
    // Read Port (to DCU)
    output logic [DATA_WIDTH-1:0] rd_data
);

    // Two banks of 256-bit registers
    logic [DATA_WIDTH-1:0] bank_a, bank_b;
    logic active_bank; // 0: A is for Write, 1: B is for Write

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_bank <= 0;
            bank_a <= '0;
            bank_b <= '0;
        end else begin
            // Swap Banks
            if (swap) begin
                active_bank <= ~active_bank;
            end

            // Ping-Pong Write Logic
            if (wr_en) begin
                if (active_bank == 0) bank_a <= wr_data;
                else                  bank_b <= wr_data;
            end
        end
    end

    // Ping-Pong Read Logic (Opposite of Write)
    assign rd_data = (active_bank == 0) ? bank_b : bank_a;

endmodule