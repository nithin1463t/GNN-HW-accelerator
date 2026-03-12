`timescale 1ns / 1ps

module noc_mesh_top #(
    parameter MESH_X = 8, 
    parameter MESH_Y = 8, 
    parameter PACKET_WIDTH = 80,
    parameter FIFO_DEPTH = 4
)(
    input  logic clk,
    input  logic rst_n,

    // Host Injection (West port of Tile 0,0)
    input  logic [PACKET_WIDTH-1:0] host_in_data,
    input  logic host_in_valid,
    output logic host_in_ready,

    // Host Extraction (East port of Tile 7,7)
    output logic [PACKET_WIDTH-1:0] host_out_data,
    output logic host_out_valid,
    input  logic host_out_ready
);

    // =========================================================================
    // 2D Interconnect Arrays (Data, Valid, and Ready for all 4 directions)
    // =========================================================================
    logic [PACKET_WIDTH-1:0] e_data [0:MESH_X-1][0:MESH_Y-1];
    logic e_valid[0:MESH_X-1][0:MESH_Y-1]; logic e_ready[0:MESH_X-1][0:MESH_Y-1];
    
    logic [PACKET_WIDTH-1:0] w_data [0:MESH_X-1][0:MESH_Y-1];
    logic w_valid[0:MESH_X-1][0:MESH_Y-1]; logic w_ready[0:MESH_X-1][0:MESH_Y-1];
    
    logic [PACKET_WIDTH-1:0] s_data [0:MESH_X-1][0:MESH_Y-1];
    logic s_valid[0:MESH_X-1][0:MESH_Y-1]; logic s_ready[0:MESH_X-1][0:MESH_Y-1];
    
    logic [PACKET_WIDTH-1:0] n_data [0:MESH_X-1][0:MESH_Y-1];
    logic n_valid[0:MESH_X-1][0:MESH_Y-1]; logic n_ready[0:MESH_X-1][0:MESH_Y-1];

    // =========================================================================
    // Mesh Generation Loop
    // =========================================================================
    genvar x, y;
    generate
        for (x = 0; x < MESH_X; x++) begin : col
            for (y = 0; y < MESH_Y; y++) begin : row
                
                logic [PACKET_WIDTH-1:0] in_n_data, in_s_data, in_e_data, in_w_data;
                logic in_n_valid, in_s_valid, in_e_valid, in_w_valid;
                logic out_n_ready, out_s_ready, out_e_ready, out_w_ready;

                // --- NORTH PORT MAPPING ---
                if (y > 0) begin
                    assign in_n_data = s_data[x][y-1];
                    assign in_n_valid = s_valid[x][y-1];
                    assign out_n_ready = s_ready[x][y-1];
                end else begin
                    assign in_n_data = '0; assign in_n_valid = 1'b0; assign out_n_ready = 1'b1;
                end

                // --- SOUTH PORT MAPPING ---
                if (y < MESH_Y-1) begin
                    assign in_s_data = n_data[x][y+1];
                    assign in_s_valid = n_valid[x][y+1];
                    assign out_s_ready = n_ready[x][y+1];
                end else begin
                    assign in_s_data = '0; assign in_s_valid = 1'b0; assign out_s_ready = 1'b1;
                end

                // --- EAST PORT MAPPING ---
                if (x < MESH_X-1) begin
                    assign in_e_data = w_data[x+1][y];
                    assign in_e_valid = w_valid[x+1][y];
                    assign out_e_ready = w_ready[x+1][y];
                end else if (x == MESH_X-1 && y == MESH_Y-1) begin
                    // Exit to Host
                    assign in_e_data = '0; assign in_e_valid = 1'b0; assign out_e_ready = host_out_ready;
                end else begin
                    assign in_e_data = '0; assign in_e_valid = 1'b0; assign out_e_ready = 1'b1;
                end

                // --- WEST PORT MAPPING ---
                if (x == 0 && y == 0) begin
                    // Entry from Host
                    assign in_w_data = host_in_data;
                    assign in_w_valid = host_in_valid;
                    assign out_w_ready = 1'b1; // Host doesn't receive data back this way
                end else if (x > 0) begin
                    assign in_w_data = e_data[x-1][y];
                    assign in_w_valid = e_valid[x-1][y];
                    assign out_w_ready = e_ready[x-1][y];
                end else begin
                    assign in_w_data = '0; assign in_w_valid = 1'b0; assign out_w_ready = 1'b1;
                end

                // =============================================================
                // Tile Instantiation
                // =============================================================
                tile_top #(
                    .X_COORD(x), .Y_COORD(y), 
                    .MESH_X(MESH_X), .MESH_Y(MESH_Y),
                    .PACKET_WIDTH(PACKET_WIDTH), .FIFO_DEPTH(FIFO_DEPTH)
                ) tile_inst (
                    .clk(clk), .rst_n(rst_n),
                    
                    .n_in_data(in_n_data), .n_in_valid(in_n_valid), .n_in_ready(n_ready[x][y]),
                    .n_out_data(n_data[x][y]), .n_out_valid(n_valid[x][y]), .n_out_ready(out_n_ready),
                    
                    .s_in_data(in_s_data), .s_in_valid(in_s_valid), .s_in_ready(s_ready[x][y]),
                    .s_out_data(s_data[x][y]), .s_out_valid(s_valid[x][y]), .s_out_ready(out_s_ready),
                    
                    .e_in_data(in_e_data), .e_in_valid(in_e_valid), .e_in_ready(e_ready[x][y]),
                    .e_out_data(e_data[x][y]), .e_out_valid(e_valid[x][y]), .e_out_ready(out_e_ready),
                    
                    .w_in_data(in_w_data), .w_in_valid(in_w_valid), .w_in_ready(w_ready[x][y]),
                    .w_out_data(w_data[x][y]), .w_out_valid(w_valid[x][y]), .w_out_ready(out_w_ready),

                    // Local memory bypass (Mock External Memory for simulation)
                    .mem_rd_en(), .mem_addr(), .mem_rd_valid(1'b1), .mem_rd_data(256'hDEADBEEF)
                );
            end
        end
    endgenerate

    // =========================================================================
    // Hook up Host Handshake interfaces
    // =========================================================================
    assign host_in_ready  = w_ready[0][0]; 
    assign host_out_data  = e_data[MESH_X-1][MESH_Y-1];
    assign host_out_valid = e_valid[MESH_X-1][MESH_Y-1];

endmodule