`timescale 1ns / 1ps

module noc_router #(
    parameter PACKET_WIDTH = 80, 
    parameter TILE_ID = 0
)(
    input  logic clk,
    input  logic rst_n,

    // Local Tile Interface (to/from internal logic)
    input  logic [PACKET_WIDTH-1:0] local_in_data,
    input  logic local_in_valid,
    output logic [PACKET_WIDTH-1:0] local_out_data,
    output logic local_out_valid,

    // Mesh Interface (to/from neighboring tiles)
    input  logic [PACKET_WIDTH-1:0] mesh_in_data,
    input  logic mesh_in_valid,
    output logic [PACKET_WIDTH-1:0] mesh_out_data,
    output logic mesh_out_valid
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            local_out_valid <= 0;
            mesh_out_valid  <= 0;
            local_out_data  <= 0;
            mesh_out_data   <= 0;
        end else begin
            // 1. Route Mesh Input
            if (mesh_in_valid) begin
                if (mesh_in_data[79:72] == TILE_ID) begin
                    local_out_data  <= mesh_in_data;
                    local_out_valid <= 1;
                end else begin
                    mesh_out_data   <= mesh_in_data;
                    mesh_out_valid  <= 1;
                end
            end else begin
                local_out_valid <= 0;
            end

            // 2. Route Local Output to Mesh
            if (local_in_valid) begin
                mesh_out_data  <= local_in_data;
                mesh_out_valid <= 1;
            end else if (!mesh_in_valid) begin
                mesh_out_valid <= 0;
            end
        end
    end
endmodule