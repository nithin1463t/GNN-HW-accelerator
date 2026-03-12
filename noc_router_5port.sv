`timescale 1ns / 1ps

module noc_router_5port #(
    parameter PACKET_WIDTH = 80,
    parameter MY_X = 0,
    parameter MY_Y = 0,
    parameter MESH_X = 8,
    parameter MESH_Y = 8,
    parameter FIFO_DEPTH = 4
)(
    input  logic clk, input  logic rst_n,

    input  logic [PACKET_WIDTH-1:0] local_in_data, input logic local_in_valid, output logic local_in_ready,
    output logic [PACKET_WIDTH-1:0] local_out_data, output logic local_out_valid, input logic local_out_ready,

    input  logic [PACKET_WIDTH-1:0] n_in_data, input logic n_in_valid, output logic n_in_ready,
    output logic [PACKET_WIDTH-1:0] n_out_data, output logic n_out_valid, input logic n_out_ready,

    input  logic [PACKET_WIDTH-1:0] s_in_data, input logic s_in_valid, output logic s_in_ready,
    output logic [PACKET_WIDTH-1:0] s_out_data, output logic s_out_valid, input logic s_out_ready,

    input  logic [PACKET_WIDTH-1:0] e_in_data, input logic e_in_valid, output logic e_in_ready,
    output logic [PACKET_WIDTH-1:0] e_out_data, output logic e_out_valid, input logic e_out_ready,

    input  logic [PACKET_WIDTH-1:0] w_in_data, input logic w_in_valid, output logic w_in_ready,
    output logic [PACKET_WIDTH-1:0] w_out_data, output logic w_out_valid, input logic w_out_ready
);

    logic [4:0] fifo_empty, fifo_full, fifo_rd_en;
    logic [PACKET_WIDTH-1:0] fifo_rd_data [0:4];

    assign local_in_ready = ~fifo_full[0];
    assign n_in_ready     = ~fifo_full[1];
    assign s_in_ready     = ~fifo_full[2];
    assign e_in_ready     = ~fifo_full[3];
    assign w_in_ready     = ~fifo_full[4];

    router_fifo #(.DATA_WIDTH(PACKET_WIDTH), .DEPTH(FIFO_DEPTH)) f_loc (.clk(clk), .rst_n(rst_n), .wr_en(local_in_valid), .wr_data(local_in_data), .full(fifo_full[0]), .rd_en(fifo_rd_en[0]), .rd_data(fifo_rd_data[0]), .empty(fifo_empty[0]));
    router_fifo #(.DATA_WIDTH(PACKET_WIDTH), .DEPTH(FIFO_DEPTH)) f_n   (.clk(clk), .rst_n(rst_n), .wr_en(n_in_valid), .wr_data(n_in_data), .full(fifo_full[1]), .rd_en(fifo_rd_en[1]), .rd_data(fifo_rd_data[1]), .empty(fifo_empty[1]));
    router_fifo #(.DATA_WIDTH(PACKET_WIDTH), .DEPTH(FIFO_DEPTH)) f_s   (.clk(clk), .rst_n(rst_n), .wr_en(s_in_valid), .wr_data(s_in_data), .full(fifo_full[2]), .rd_en(fifo_rd_en[2]), .rd_data(fifo_rd_data[2]), .empty(fifo_empty[2]));
    router_fifo #(.DATA_WIDTH(PACKET_WIDTH), .DEPTH(FIFO_DEPTH)) f_e   (.clk(clk), .rst_n(rst_n), .wr_en(e_in_valid), .wr_data(e_in_data), .full(fifo_full[3]), .rd_en(fifo_rd_en[3]), .rd_data(fifo_rd_data[3]), .empty(fifo_empty[3]));
    router_fifo #(.DATA_WIDTH(PACKET_WIDTH), .DEPTH(FIFO_DEPTH)) f_w   (.clk(clk), .rst_n(rst_n), .wr_en(w_in_valid), .wr_data(w_in_data), .full(fifo_full[4]), .rd_en(fifo_rd_en[4]), .rd_data(fifo_rd_data[4]), .empty(fifo_empty[4]));

    logic [2:0] rr_ptr; 
    logic [4:0] target_ready;
    assign target_ready[0] = local_out_ready; assign target_ready[1] = n_out_ready;
    assign target_ready[2] = s_out_ready;     assign target_ready[3] = e_out_ready;
    assign target_ready[4] = w_out_ready;

    logic [3:0] dest_x; logic [3:0] dest_y; logic [7:0] cmd_type; logic [4:0] target_mask;
    
    // --- IN-NETWORK REDUCTION LOGIC (Combinational) ---
    logic is_reduce;
    logic match_found;
    logic [2:0] match_idx;
    logic [63:0] merged_payload;
    logic [PACKET_WIDTH-1:0] final_packet;

    always_comb begin
        is_reduce = (!fifo_empty[rr_ptr] && fifo_rd_data[rr_ptr][71:64] == 8'h04);
        match_found = 1'b0;
        match_idx = '0;

        // Search the other 4 FIFOs for a matching REDUCE packet with the same Destination
        if (is_reduce) begin
            if (!fifo_empty[0] && 0 != rr_ptr && fifo_rd_data[0][71:64] == 8'h04 && fifo_rd_data[0][79:72] == fifo_rd_data[rr_ptr][79:72]) begin match_found = 1; match_idx = 0; end
            else if (!fifo_empty[1] && 1 != rr_ptr && fifo_rd_data[1][71:64] == 8'h04 && fifo_rd_data[1][79:72] == fifo_rd_data[rr_ptr][79:72]) begin match_found = 1; match_idx = 1; end
            else if (!fifo_empty[2] && 2 != rr_ptr && fifo_rd_data[2][71:64] == 8'h04 && fifo_rd_data[2][79:72] == fifo_rd_data[rr_ptr][79:72]) begin match_found = 1; match_idx = 2; end
            else if (!fifo_empty[3] && 3 != rr_ptr && fifo_rd_data[3][71:64] == 8'h04 && fifo_rd_data[3][79:72] == fifo_rd_data[rr_ptr][79:72]) begin match_found = 1; match_idx = 3; end
            else if (!fifo_empty[4] && 4 != rr_ptr && fifo_rd_data[4][71:64] == 8'h04 && fifo_rd_data[4][79:72] == fifo_rd_data[rr_ptr][79:72]) begin match_found = 1; match_idx = 4; end
        end
        
        // Parallel Vector Addition (4x 16-bit)
        if (match_found) begin
             merged_payload[15:0]  = fifo_rd_data[rr_ptr][15:0]  + fifo_rd_data[match_idx][15:0];
             merged_payload[31:16] = fifo_rd_data[rr_ptr][31:16] + fifo_rd_data[match_idx][31:16];
             merged_payload[47:32] = fifo_rd_data[rr_ptr][47:32] + fifo_rd_data[match_idx][47:32];
             merged_payload[63:48] = fifo_rd_data[rr_ptr][63:48] + fifo_rd_data[match_idx][63:48];
        end else begin
             merged_payload = fifo_rd_data[rr_ptr][63:0];
        end
    end

    // =========================================================================
    // Arbitration & Routing Sequential Logic
    // =========================================================================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rr_ptr <= '0;
            local_out_valid <= 0; n_out_valid <= 0; s_out_valid <= 0; e_out_valid <= 0; w_out_valid <= 0;
            local_out_data <= '0; n_out_data <= '0; s_out_data <= '0; e_out_data <= '0; w_out_data <= '0;
            fifo_rd_en <= '0;
        end else begin
            fifo_rd_en <= '0;
            
            if (local_out_valid && local_out_ready) local_out_valid <= 0;
            if (n_out_valid && n_out_ready) n_out_valid <= 0;
            if (s_out_valid && s_out_ready) s_out_valid <= 0;
            if (e_out_valid && e_out_ready) e_out_valid <= 0;
            if (w_out_valid && w_out_ready) w_out_valid <= 0;

            if (!fifo_empty[rr_ptr]) begin
                dest_x = fifo_rd_data[rr_ptr][79:76];
                dest_y = fifo_rd_data[rr_ptr][75:72];
                cmd_type = fifo_rd_data[rr_ptr][71:64];
                target_mask = '0;
                final_packet = {dest_x, dest_y, cmd_type, merged_payload};

                if (cmd_type == 8'h03) begin
                    // BROADCAST
                    target_mask[0] = 1'b1; target_mask[2] = 1'b1; 
                    if (MY_Y == 0) target_mask[3] = 1'b1;
                end else if (dest_x == 4'hF && dest_y == 4'hF) begin
                    // HOST EGRESS (Y-then-X Routing)
                    if      (MY_Y < MESH_Y - 1) target_mask[2] = 1'b1; // SOUTH
                    else if (MY_X < MESH_X - 1) target_mask[3] = 1'b1; // EAST
                    else                        target_mask[3] = 1'b1; // EXIT
                end else begin
                    // UNICAST XY ROUTING
                    if      (dest_x > MY_X) target_mask[3] = 1'b1; // EAST
                    else if (dest_x < MY_X) target_mask[4] = 1'b1; // WEST
                    else if (dest_y > MY_Y) target_mask[2] = 1'b1; // SOUTH
                    else if (dest_y < MY_Y) target_mask[1] = 1'b1; // NORTH
                    else                    target_mask[0] = 1'b1; // LOCAL
                end

                if ((target_mask & target_ready) == target_mask) begin
                    if (target_mask[0]) begin local_out_data <= final_packet; local_out_valid <= 1; end
                    if (target_mask[1]) begin n_out_data <= final_packet;     n_out_valid <= 1; end
                    if (target_mask[2]) begin s_out_data <= final_packet;     s_out_valid <= 1; end
                    if (target_mask[3]) begin e_out_data <= final_packet;     e_out_valid <= 1; end
                    if (target_mask[4]) begin w_out_data <= final_packet;     w_out_valid <= 1; end
                    
                    // Pop the primary packet
                    fifo_rd_en[rr_ptr] <= 1;
                    
                    // IF A COLLISION OCCURRED, POP THE SECOND PACKET TOO!
                    if (match_found) begin
                        fifo_rd_en[match_idx] <= 1;
                    end
                end
            end
            rr_ptr <= (rr_ptr == 4) ? 0 : rr_ptr + 1;
        end
    end
endmodule