`timescale 1ns / 1ps

module gcu_top (
    input  logic clk,
    input  logic rst_n,
    
    // Interface with NoC Router (Tile Wrapper)
    input  logic host_start,
    input  logic [63:0] host_payload, // Dynamic Payload from NoC
    output logic chip_busy,
    
    // Interface with SAU (Dispatching Metadata)
    output logic sau_start,
    output logic [31:0] sau_base_addr,
    output logic [7:0] sau_neighbor_count,
    output logic [15:0] sau_node_id,
    output logic sau_last_node,
    input  logic sau_done,
    
    // Interface with DCU (Tracking Pipeline Completion)
    input  logic dcu_valid_out
);

    typedef enum logic [1:0] {
        IDLE, 
        SAU_BUSY, 
        WAIT_DCU
    } state_t;

    state_t state, next_state;
    
    // Latch for the NoC packet payload
    logic [63:0] latched_payload;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            latched_payload <= '0;
        end else begin
            state <= next_state;
            
            // Latch the payload the exact moment a new valid packet arrives
            if (host_start && state == IDLE) begin
                latched_payload <= host_payload;
            end
        end
    end

    always_comb begin
        next_state = state;
        sau_start = 0;
        chip_busy = 1;

        case (state)
            IDLE: begin
                chip_busy = 0; // Ready to accept a new command from NoC
                if (host_start) begin
                    sau_start = 1;
                    next_state = SAU_BUSY;
                end
            end
            
            SAU_BUSY: begin
                // Wait for the SAU to push the features into the compute FIFO
                if (sau_done) next_state = WAIT_DCU;
            end
            
            WAIT_DCU: begin
                // Wait for the DCU to pull the features, multiply, and output
                if (dcu_valid_out) next_state = IDLE;
            end
        endcase
    end

    // =========================================================================
    // DYNAMIC PAYLOAD DECODING (1-Cycle Pipeline Bug Fix)
    // =========================================================================
    // Decode directly from the active packet to prevent a 1-cycle latency bug!
    // If we are in IDLE, use the live incoming host_payload so SAU gets it instantly.
    // Otherwise, use the latched_payload to hold it stable while SAU operates.
    
    wire [63:0] active_payload = (state == IDLE) ? host_payload : latched_payload;
    
    // Unpack the 64-bit payload matching the Python compiler's bit shifting:
    // [LAST(1) | ID(16) | COUNT(8) | ADDR(32) | UNUSED(7)]
    assign sau_last_node      = active_payload[63];
    assign sau_node_id        = active_payload[62:47];
    assign sau_neighbor_count = active_payload[46:39];
    assign sau_base_addr      = active_payload[31:0];

endmodule