`timescale 1ns / 1ps

module noc_mesh_2x2 (
    input  logic clk,
    input  logic rst_n,
    
    // External Mesh Ports (Entry at Top-Left, Exit at Bottom-Right)
    input  logic [79:0] mesh_in_top_left,
    input  logic mesh_in_valid_top_left,
    output logic [79:0] mesh_out_bottom_right,
    output logic mesh_out_valid_bottom_right
);

    // Interconnect wires: naming convention [SourceTile]_to_[DestTile]
    logic [79:0] t0_to_t1_data, t1_to_t3_data;
    logic t0_to_t1_valid, t1_to_t3_valid;

    // Tile (0,0) - ID 0: Receives from outside, forwards to Tile 1
    tile_top #(.TILE_ID(0)) tile00 (
        .clk(clk), .rst_n(rst_n),
        .mesh_in_data(mesh_in_top_left), .mesh_in_valid(mesh_in_valid_top_left),
        .mesh_out_data(t0_to_t1_data), .mesh_out_valid(t0_to_t1_valid),
        .mem_rd_en(), .mem_addr(), .mem_rd_valid(1'b0), .mem_rd_data(256'h0)
    );

    // Tile (1,0) - ID 1: Receives from Tile 0, forwards to Tile 3
    tile_top #(.TILE_ID(1)) tile10 (
        .clk(clk), .rst_n(rst_n),
        .mesh_in_data(t0_to_t1_data), .mesh_in_valid(t0_to_t1_valid),
        .mesh_out_data(t1_to_t3_data), .mesh_out_valid(t1_to_t3_valid),
        .mem_rd_en(), .mem_addr(), .mem_rd_valid(1'b0), .mem_rd_data(256'h0)
    );

    // Tile (1,1) - ID 3: Target Tile. Receives from Tile 1, sends to outside
    // Note: We use ID 3 to represent the (1,1) coordinate in a 2x2 grid
    tile_top #(.TILE_ID(3)) tile11 (
        .clk(clk), .rst_n(rst_n),
        .mesh_in_data(t1_to_t3_data), .mesh_in_valid(t1_to_t3_valid),
        .mesh_out_data(mesh_out_bottom_right), .mesh_out_valid(mesh_out_valid_bottom_right),
        .mem_rd_en(), .mem_addr(), 
        .mem_rd_valid(1'b1), .mem_rd_data(256'hCAFEBABE_DEADBEEF_12345678_87654321) 
    );

    // Tile (0,1) - ID 2: Optional for this specific path test, keeping ports tied
    tile_top #(.TILE_ID(2)) tile01 (
        .clk(clk), .rst_n(rst_n),
        .mesh_in_data(80'h0), .mesh_in_valid(1'b0),
        .mesh_out_data(), .mesh_out_valid(),
        .mem_rd_en(), .mem_addr(), .mem_rd_valid(1'b0), .mem_rd_data(256'h0)
    );
    // =======================================================
    // HARDWARE PERFORMANCE PROBE
    // =======================================================
    logic [31:0] global_cycle_count;
    logic [31:0] packet_start_cycle;
    logic packet_in_flight;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            global_cycle_count <= 0;
            packet_start_cycle <= 0;
            packet_in_flight <= 0;
        end else begin
            // 1. Keep a running count of clock cycles
            global_cycle_count <= global_cycle_count + 1;

            // 2. Timestamp when a packet enters Tile (0,0)
            if (mesh_in_valid_top_left && !packet_in_flight) begin
                packet_start_cycle <= global_cycle_count;
                packet_in_flight <= 1;
                $display("[%0t ns] ⏱️ PROBE: Packet entered mesh at Tile (0,0). Cycle: %0d", $time, global_cycle_count);
            end

            // 3. Timestamp when the result exits Tile (1,1)
            if (mesh_out_valid_bottom_right && packet_in_flight) begin
                packet_in_flight <= 0;
                $display("[%0t ns] ⏱️ PROBE: Result exited mesh at Tile (1,1). Cycle: %0d", $time, global_cycle_count);
                $display("==================================================");
                $display(" 🚀 TOTAL MULTI-HOP LATENCY: %0d Clock Cycles", (global_cycle_count - packet_start_cycle));
                $display("==================================================");
            end
        end
    end
// --- Waveform Generation Block ---
    initial begin
        $dumpfile("tile_top_waveform.vcd"); // Creates the VCD file
        $dumpvars(0, noc_mesh_2x2);         // Dumps ALL signals in the 2x2 mesh
    end
endmodule