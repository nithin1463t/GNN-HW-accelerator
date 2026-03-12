`timescale 1ns / 1ps

module sau_top #(
    parameter ADDR_WIDTH = 32
)(
    input  logic clk, input  logic rst_n,
    input  logic start,
    input  logic [ADDR_WIDTH-1:0] base_addr,
    input  logic [7:0] neighbor_count,
    input  logic [15:0] node_id,       
    input  logic last_node,            
    output logic done,

    output logic mem_rd_en,
    output logic [ADDR_WIDTH-1:0] mem_addr,
    input  logic mem_rd_valid,
    input  logic [255:0] mem_rd_data,

    input  logic fifo_full,
    output logic fifo_wr_en,
    output logic [272:0] fifo_wr_data  
);

    // 128-Entry L1 Cache
    logic         cache_valid [0:127];
    logic [19:0]  cache_tag   [0:127];
    logic [255:0] cache_data  [0:127];

    // =========================================================================
    // ENGINE 1: The Access Engine (Hardware Prefetcher)
    // =========================================================================
    logic [7:0] fetch_count;
    logic [ADDR_WIDTH-1:0] fetch_addr;
    logic is_fetching;

    wire [6:0]  fetch_idx = fetch_addr[11:5];
    wire [19:0] fetch_tag = fetch_addr[31:12];
    wire fetch_hit = (cache_valid[fetch_idx] && (cache_tag[fetch_idx] == fetch_tag));

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            is_fetching <= 0;
            fetch_count <= 0;
            fetch_addr <= 0;
            mem_rd_en <= 0;
            mem_addr <= 0;
            for (int j = 0; j < 128; j++) cache_valid[j] <= 1'b0;
        end else begin
            if (start) begin
                is_fetching <= 1;
                fetch_count <= neighbor_count;
                fetch_addr  <= base_addr;
                mem_rd_en   <= 0;
            end else if (is_fetching) begin
                if (fetch_count == 0) begin
                    is_fetching <= 0;
                    mem_rd_en <= 0;
                end else if (fetch_hit) begin
                    // Already in L1 Cache! Sprint ahead to the next address.
                    fetch_addr <= fetch_addr + 32;
                    fetch_count <= fetch_count - 1;
                    mem_rd_en <= 0;
                end else begin
                    // Miss. Command DRAM to fetch it.
                    mem_rd_en <= 1;
                    mem_addr <= fetch_addr;
                    if (mem_rd_valid) begin
                        // Data arrived! Write to L1 Cache.
                        cache_valid[fetch_idx] <= 1'b1;
                        cache_tag[fetch_idx]   <= fetch_tag;
                        cache_data[fetch_idx]  <= mem_rd_data;

                        fetch_addr <= fetch_addr + 32;
                        fetch_count <= fetch_count - 1;
                        mem_rd_en <= 0; // 1-cycle breather for DRAM handshake
                    end
                end
            end else begin
                mem_rd_en <= 0;
            end
        end
    end

    // =========================================================================
    // ENGINE 2: The Execute Engine (Vector Compute)
    // =========================================================================
    typedef enum logic [1:0] { IDLE, EXECUTE, PUSH } state_t;
    state_t exec_state;

    logic [7:0] exec_count;
    logic [ADDR_WIDTH-1:0] exec_addr;
    logic [255:0] accumulator;
    logic [15:0] saved_node_id;
    logic saved_last_node;

    wire [6:0]  exec_idx = exec_addr[11:5];
    wire [19:0] exec_tag = exec_addr[31:12];
    
    // The Execute Engine ONLY proceeds if the Prefetcher has loaded the data
    wire exec_hit = (cache_valid[exec_idx] && (cache_tag[exec_idx] == exec_tag));

    logic [255:0] next_accum;
    genvar i;
    generate
        for (i = 0; i < 16; i++) begin : vec_add
            assign next_accum[(i*16)+15 : i*16] = accumulator[(i*16)+15 : i*16] + cache_data[exec_idx][(i*16)+15 : i*16];
        end
    endgenerate

    assign fifo_wr_en   = (exec_state == PUSH && !fifo_full);
    assign fifo_wr_data = {saved_last_node, saved_node_id, accumulator};
    assign done         = (exec_state == PUSH && !fifo_full);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            exec_state <= IDLE;
            exec_count <= 0;
            exec_addr <= 0;
            accumulator <= '0;
            saved_node_id <= '0;
            saved_last_node <= 0;
        end else begin
            case (exec_state)
                IDLE: begin
                    if (start) begin
                        exec_count <= neighbor_count;
                        exec_addr <= base_addr;
                        accumulator <= '0;
                        saved_node_id <= node_id;
                        saved_last_node <= last_node;
                        exec_state <= EXECUTE;
                    end
                end
                EXECUTE: begin
                    // Wait for the Prefetch Engine to deliver the cache hit
                    if (exec_hit) begin 
                        accumulator <= next_accum;
                        exec_addr <= exec_addr + 32;
                        if (exec_count == 1) begin
                            exec_state <= PUSH;
                        end else begin
                            exec_count <= exec_count - 1;
                        end
                    end
                end
                PUSH: begin
                    if (!fifo_full) exec_state <= IDLE;
                end
            endcase
        end
    end
endmodule