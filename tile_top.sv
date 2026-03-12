`timescale 1ns / 1ps

module tile_top #(
    parameter MY_X = 0,
    parameter MY_Y = 0,
    parameter MESH_X = 8,
    parameter MESH_Y = 8,
    parameter PACKET_WIDTH = 80
)(
    input  logic clk,
    input  logic rst_n,

    // North
    input  logic [PACKET_WIDTH-1:0] n_in_data, input logic n_in_valid, output logic n_in_ready,
    output logic [PACKET_WIDTH-1:0] n_out_data, output logic n_out_valid, input logic n_out_ready,
    // South
    input  logic [PACKET_WIDTH-1:0] s_in_data, input logic s_in_valid, output logic s_in_ready,
    output logic [PACKET_WIDTH-1:0] s_out_data, output logic s_out_valid, input logic s_out_ready,
    // East
    input  logic [PACKET_WIDTH-1:0] e_in_data, input logic e_in_valid, output logic e_in_ready,
    output logic [PACKET_WIDTH-1:0] e_out_data, output logic e_out_valid, input logic e_out_ready,
    // West
    input  logic [PACKET_WIDTH-1:0] w_in_data, input logic w_in_valid, output logic w_in_ready,
    output logic [PACKET_WIDTH-1:0] w_out_data, output logic w_out_valid, input logic w_out_ready,

    // External Memory Interface
    output logic mem_rd_en,
    output logic [31:0] mem_addr,
    input  logic mem_rd_valid,
    input  logic [255:0] mem_rd_data
);

    // =========================================================================
    // Local Interconnect (Tile Core to Router)
    // =========================================================================
    logic [PACKET_WIDTH-1:0] local_in_data, local_out_data;
    logic local_in_valid, local_in_ready, local_out_valid, local_out_ready;

    noc_router_5port #(
        .PACKET_WIDTH(PACKET_WIDTH),
        .MY_X(MY_X),
        .MY_Y(MY_Y),
        .MESH_X(MESH_X),
        .MESH_Y(MESH_Y)
    ) router_inst (
        .clk(clk), .rst_n(rst_n),
        .local_in_data(local_out_data), .local_in_valid(local_out_valid), .local_in_ready(local_out_ready),
        .local_out_data(local_in_data), .local_out_valid(local_in_valid), .local_out_ready(local_in_ready),
        
        .n_in_data(n_in_data), .n_in_valid(n_in_valid), .n_in_ready(n_in_ready),
        .n_out_data(n_out_data), .n_out_valid(n_out_valid), .n_out_ready(n_out_ready),
        
        .s_in_data(s_in_data), .s_in_valid(s_in_valid), .s_in_ready(s_in_ready),
        .s_out_data(s_out_data), .s_out_valid(s_out_valid), .s_out_ready(s_out_ready),
        
        .e_in_data(e_in_data), .e_in_valid(e_in_valid), .e_in_ready(e_in_ready),
        .e_out_data(e_out_data), .e_out_valid(e_out_valid), .e_out_ready(e_out_ready),
        
        .w_in_data(w_in_data), .w_in_valid(w_in_valid), .w_in_ready(w_in_ready),
        .w_out_data(w_out_data), .w_out_valid(w_out_valid), .w_out_ready(w_out_ready)
    );

    // =========================================================================
    // Compute Core Datapath
    // =========================================================================
    logic chip_busy, sau_start, sau_last_node, sau_done, dcu_valid_out;
    logic [31:0] sau_base_addr; logic [7:0] sau_neighbor_count; logic [15:0] sau_node_id;
    
    // Accept packet from router
    logic start_tile;
    assign start_tile = local_in_valid && local_in_ready;
    assign local_in_ready = ~chip_busy;

    gcu_top gcu_inst (
        .clk(clk), .rst_n(rst_n),
        .host_start(start_tile), .host_payload(local_in_data[63:0]),
        .chip_busy(chip_busy),
        .sau_start(sau_start), .sau_base_addr(sau_base_addr), .sau_neighbor_count(sau_neighbor_count),
        .sau_node_id(sau_node_id), .sau_last_node(sau_last_node), .sau_done(sau_done),
        .dcu_valid_out(dcu_valid_out)
    );

    logic fifo_full, fifo_wr_en; logic [272:0] fifo_wr_data;
    sau_top sau_inst (
        .clk(clk), .rst_n(rst_n),
        .start(sau_start), .base_addr(sau_base_addr), .neighbor_count(sau_neighbor_count),
        .node_id(sau_node_id), .last_node(sau_last_node), .done(sau_done),
        .mem_rd_en(mem_rd_en), .mem_addr(mem_addr), .mem_rd_valid(mem_rd_valid), .mem_rd_data(mem_rd_data),
        .fifo_full(fifo_full), .fifo_wr_en(fifo_wr_en), .fifo_wr_data(fifo_wr_data)
    );

    logic fifo_empty, fifo_rd_en; logic [272:0] fifo_rd_data;
    compute_fifo fifo_inst (
        .clk(clk), .rst_n(rst_n),
        .wr_en(fifo_wr_en), .wr_data(fifo_wr_data), .full(fifo_full),
        .rd_en(fifo_rd_en), .rd_data(fifo_rd_data), .empty(fifo_empty)
    );

    logic [63:0] dcu_data_out;
    assign fifo_rd_en = ~fifo_empty && local_out_ready;

    dcu_top dcu_inst (
        .clk(clk), .rst_n(rst_n),
        .start_comb(fifo_rd_en),
        .data_in(fifo_rd_data[255:0]),
        .data_out(dcu_data_out),
        .valid_out(dcu_valid_out)
    );

    // =========================================================================
    // Packing the Output Packet
    // =========================================================================
    // 0x02 prevents the Reduction Tree from merging independent node results
    assign local_out_valid = dcu_valid_out;
    assign local_out_data = {4'hF, 4'hF, 8'h02, dcu_data_out};

    // =========================================================================
    // Hardware Performance Monitoring Counters (PMCs)
    // =========================================================================
    logic [31:0] pmc_active_cycles;
    logic [31:0] pmc_mem_stall_cycles;
    logic [31:0] pmc_compute_cycles;
    logic [31:0] pmc_noc_stall_cycles;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pmc_active_cycles    <= '0;
            pmc_mem_stall_cycles <= '0;
            pmc_compute_cycles   <= '0;
            pmc_noc_stall_cycles <= '0;
        end else begin
            // Track total active time
            if (chip_busy) 
                pmc_active_cycles <= pmc_active_cycles + 1;
                
            // Track Memory Bottlenecks (Requesting data, but DRAM hasn't answered)
            if (mem_rd_en && !mem_rd_valid) 
                pmc_mem_stall_cycles <= pmc_mem_stall_cycles + 1;
                
            // Track ALU Utilization (DCU is actively firing)
            if (fifo_rd_en) 
                pmc_compute_cycles <= pmc_compute_cycles + 1;
                
            // Track NoC Congestion (Tile wants to egress, but Router is full)
            if (local_out_valid && !local_out_ready) 
                pmc_noc_stall_cycles <= pmc_noc_stall_cycles + 1;
        end
    end

endmodule