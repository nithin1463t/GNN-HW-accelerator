`timescale 1ns / 1ps

module router_fifo #(
    parameter DATA_WIDTH = 80,
    parameter DEPTH = 4
)(
    input  logic clk,
    input  logic rst_n,

    // Write Interface (From Upstream Router)
    input  logic wr_en,
    input  logic [DATA_WIDTH-1:0] wr_data,
    output logic full,

    // Read Interface (To Local Arbiter/Crossbar)
    input  logic rd_en,
    output logic [DATA_WIDTH-1:0] rd_data,
    output logic empty
);

    // Calculate how many bits are needed for the pointers
    localparam PTR_WIDTH = $clog2(DEPTH);

    // Memory array for the buffer
    logic [DATA_WIDTH-1:0] mem [0:DEPTH-1];
    
    // Internal state
    logic [PTR_WIDTH-1:0] wr_ptr;
    logic [PTR_WIDTH-1:0] rd_ptr;
    logic [$clog2(DEPTH+1)-1:0] count;

    // Status Flags
    assign full  = (count == DEPTH);
    assign empty = (count == 0);

    // Continuous read assignment (First-Word Fall-Through style for faster routing)
    assign rd_data = mem[rd_ptr];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= '0;
            rd_ptr <= '0;
            count  <= '0;
            
            // Clear memory on reset for cleaner waveforms
            for (int i = 0; i < DEPTH; i++) begin
                mem[i] <= '0;
            end
            
        end else begin
            // 1. Write Logic
            if (wr_en && !full) begin
                mem[wr_ptr] <= wr_data;
                wr_ptr <= wr_ptr + 1;
            end

            // 2. Read Logic
            if (rd_en && !empty) begin
                rd_ptr <= rd_ptr + 1;
            end

            // 3. Count Tracking (Handle simultaneous Read & Write)
            if ((wr_en && !full) && !(rd_en && !empty)) begin
                count <= count + 1;
            end else if (!(wr_en && !full) && (rd_en && !empty)) begin
                count <= count - 1;
            end
        end
    end

endmodule