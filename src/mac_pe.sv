module mac_pe #(
    parameter int WIDTH = 16
)(
    input  logic clk,
    input  logic rst_n,
    input  logic load_weight,
    
    input  logic signed [WIDTH-1:0] in_a,      // Feature flowing from Left -> Right
    input  logic signed [WIDTH-1:0] in_b,      // Partial sum flowing Top -> Bottom
    input  logic signed [WIDTH-1:0] weight_in, // Weight flowing Top -> Bottom (during load phase)
    
    output logic signed [WIDTH-1:0] out_a,     // Feature passed to Right neighbor
    output logic signed [WIDTH-1:0] out_b      // Sum/Weight passed to Bottom neighbor
);

    logic signed [WIDTH-1:0] stored_weight;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stored_weight <= '0;
            out_a <= '0;
            out_b <= '0;
        end else begin
            // Phase 1: Loading Weights into the array
            if (load_weight) begin
                stored_weight <= weight_in;
                out_b <= weight_in; // Pass weight down to the next PE
            end 
            // Phase 2: Computing Neural Network Math
            else begin
                out_a <= in_a; // Pass feature to the right
                out_b <= in_b + (in_a * stored_weight); // Multiply and Accumulate
            end
        end
    end
endmodule