`timescale 1ns / 1ps

module mesh_top #(
    parameter MESH_X = 16,
    parameter MESH_Y = 16,
    parameter PACKET_WIDTH = 80
)(
    input  logic clk,
    input  logic rst_n,

    // Host Input (Injects into Tile 0,0 West)
    input  logic host_in_valid,
    input  logic [PACKET_WIDTH-1:0] host_in_data,
    output logic host_in_ready,

    // Host Output (Exits from Bottom-Right East)
    output logic host_out_valid,
    output logic [PACKET_WIDTH-1:0] host_out_data,
    input  logic host_out_ready,

    // Flattened 1D Arrays for 100% Cocotb Compatibility
    output logic [MESH_X*MESH_Y-1:0] mem_rd_en,
    output logic [31:0] mem_addr   [0:MESH_X*MESH_Y-1],
    input  logic [MESH_X*MESH_Y-1:0] mem_rd_valid,
    input  logic [255:0] mem_rd_data  [0:MESH_X*MESH_Y-1]
);

    // Interconnect Wire Declarations
    logic [PACKET_WIDTH-1:0] n_in_d[0:MESH_X-1][0:MESH_Y-1], n_out_d[0:MESH_X-1][0:MESH_Y-1]; 
    logic n_in_v[0:MESH_X-1][0:MESH_Y-1], n_in_r[0:MESH_X-1][0:MESH_Y-1], n_out_v[0:MESH_X-1][0:MESH_Y-1], n_out_r[0:MESH_X-1][0:MESH_Y-1];
    
    logic [PACKET_WIDTH-1:0] s_in_d[0:MESH_X-1][0:MESH_Y-1], s_out_d[0:MESH_X-1][0:MESH_Y-1]; 
    logic s_in_v[0:MESH_X-1][0:MESH_Y-1], s_in_r[0:MESH_X-1][0:MESH_Y-1], s_out_v[0:MESH_X-1][0:MESH_Y-1], s_out_r[0:MESH_X-1][0:MESH_Y-1];
    
    logic [PACKET_WIDTH-1:0] e_in_d[0:MESH_X-1][0:MESH_Y-1], e_out_d[0:MESH_X-1][0:MESH_Y-1]; 
    logic e_in_v[0:MESH_X-1][0:MESH_Y-1], e_in_r[0:MESH_X-1][0:MESH_Y-1], e_out_v[0:MESH_X-1][0:MESH_Y-1], e_out_r[0:MESH_X-1][0:MESH_Y-1];
    
    logic [PACKET_WIDTH-1:0] w_in_d[0:MESH_X-1][0:MESH_Y-1], w_out_d[0:MESH_X-1][0:MESH_Y-1]; 
    logic w_in_v[0:MESH_X-1][0:MESH_Y-1], w_in_r[0:MESH_X-1][0:MESH_Y-1], w_out_v[0:MESH_X-1][0:MESH_Y-1], w_out_r[0:MESH_X-1][0:MESH_Y-1];

    genvar x, y;
    generate
        for (x = 0; x < MESH_X; x++) begin : X_DIM
            for (y = 0; y < MESH_Y; y++) begin : Y_DIM
                
                localparam ID = x * MESH_Y + y;

                tile_top #(
                    .MY_X(x),
                    .MY_Y(y),
                    .MESH_X(MESH_X),
                    .MESH_Y(MESH_Y)
                ) tile_inst (
                    .clk(clk), .rst_n(rst_n),
                    .n_in_data(n_in_d[x][y]), .n_in_valid(n_in_v[x][y]), .n_in_ready(n_in_r[x][y]),
                    .n_out_data(n_out_d[x][y]), .n_out_valid(n_out_v[x][y]), .n_out_ready(n_out_r[x][y]),
                    
                    .s_in_data(s_in_d[x][y]), .s_in_valid(s_in_v[x][y]), .s_in_ready(s_in_r[x][y]),
                    .s_out_data(s_out_d[x][y]), .s_out_valid(s_out_v[x][y]), .s_out_ready(s_out_r[x][y]),
                    
                    .e_in_data(e_in_d[x][y]), .e_in_valid(e_in_v[x][y]), .e_in_ready(e_in_r[x][y]),
                    .e_out_data(e_out_d[x][y]), .e_out_valid(e_out_v[x][y]), .e_out_ready(e_out_r[x][y]),
                    
                    .w_in_data(w_in_d[x][y]), .w_in_valid(w_in_v[x][y]), .w_in_ready(w_in_r[x][y]),
                    .w_out_data(w_out_d[x][y]), .w_out_valid(w_out_v[x][y]), .w_out_ready(w_out_r[x][y]),

                    // Flattened Memory mapping
                    .mem_rd_en(mem_rd_en[ID]), .mem_addr(mem_addr[ID]),
                    .mem_rd_valid(mem_rd_valid[ID]), .mem_rd_data(mem_rd_data[ID])
                );

                // NORTH wiring (Connect to Y-1 South)
                if (y > 0) begin
                    assign n_in_d[x][y] = s_out_d[x][y-1];
                    assign n_in_v[x][y] = s_out_v[x][y-1];
                    assign n_out_r[x][y] = s_in_r[x][y-1];
                end else begin
                    assign n_in_d[x][y] = '0; assign n_in_v[x][y] = 0; assign n_out_r[x][y] = 1;
                end

                // SOUTH wiring (Connect to Y+1 North)
                if (y < MESH_Y - 1) begin
                    assign s_in_d[x][y] = n_out_d[x][y+1];
                    assign s_in_v[x][y] = n_out_v[x][y+1];
                    assign s_out_r[x][y] = n_in_r[x][y+1];
                end else begin
                    assign s_in_d[x][y] = '0; assign s_in_v[x][y] = 0; assign s_out_r[x][y] = 1;
                end

                // EAST wiring (Connect to X+1 West)
                if (x < MESH_X - 1) begin
                    assign e_in_d[x][y] = w_out_d[x+1][y];
                    assign e_in_v[x][y] = w_out_v[x+1][y];
                    assign e_out_r[x][y] = w_in_r[x+1][y];
                end else if (x == MESH_X - 1 && y == MESH_Y - 1) begin
                    // HOST EGRESS (Dynamically targets the bottom-right tile)
                    assign host_out_data = e_out_d[x][y];
                    assign host_out_valid = e_out_v[x][y];
                    assign e_out_r[x][y] = host_out_ready;
                    assign e_in_d[x][y] = '0; assign e_in_v[x][y] = 0;
                end else begin
                    assign e_in_d[x][y] = '0; assign e_in_v[x][y] = 0; assign e_out_r[x][y] = 1;
                end

                // WEST wiring (Connect to X-1 East)
                if (x > 0) begin
                    assign w_in_d[x][y] = e_out_d[x-1][y];
                    assign w_in_v[x][y] = e_out_v[x-1][y];
                    assign w_out_r[x][y] = e_in_r[x-1][y];
                end else if (x == 0 && y == 0) begin
                    // HOST INGRESS (Top-left tile)
                    assign w_in_d[x][y] = host_in_data;
                    assign w_in_v[x][y] = host_in_valid;
                    assign host_in_ready = w_in_r[x][y];
                    assign w_out_r[x][y] = 1;
                end else begin
                    assign w_in_d[x][y] = '0; assign w_in_v[x][y] = 0; assign w_out_r[x][y] = 1;
                end
            end
        end
    endgenerate

endmodule