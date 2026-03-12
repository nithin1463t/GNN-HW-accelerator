module systolic_array #(
    parameter int WIDTH = 16,
    parameter int ARRAY_SIZE = 4
)(
    input  logic clk,
    input  logic rst_n,
    input  logic load_weights,
    
    // 64-bit wide buses (4 lanes x 16 bits each)
    input  logic [ARRAY_SIZE*WIDTH-1:0] row_inputs_flat,
    input  logic [ARRAY_SIZE*WIDTH-1:0] col_inputs_flat,
    output logic [ARRAY_SIZE*WIDTH-1:0] col_outputs_flat
);
// Unpack flattened buses into SystemVerilog arrays
    logic signed [WIDTH-1:0] row_inputs [ARRAY_SIZE-1:0];
    logic signed [WIDTH-1:0] col_inputs [ARRAY_SIZE-1:0];
    logic signed [WIDTH-1:0] col_outputs [ARRAY_SIZE-1:0];

    genvar i;
    generate
        for (i = 0; i < ARRAY_SIZE; i++) begin : unpack
            assign row_inputs[i] = row_inputs_flat[(i+1)*WIDTH-1 : i*WIDTH];
            assign col_inputs[i] = col_inputs_flat[(i+1)*WIDTH-1 : i*WIDTH];
            assign col_outputs_flat[(i+1)*WIDTH-1 : i*WIDTH] = col_outputs[i];
        end
    endgenerate

    // Internal wires connecting the 16 MAC PEs
    logic signed [WIDTH-1:0] h_wires [ARRAY_SIZE-1:0][ARRAY_SIZE:0]; 
    logic signed [WIDTH-1:0] v_wires [ARRAY_SIZE:0][ARRAY_SIZE-1:0]; 

    // --- THE FIX: Assign the outer edges ONCE in a 1D loop ---
    genvar edge_idx;
    generate
        for (edge_idx = 0; edge_idx < ARRAY_SIZE; edge_idx++) begin : edges
            assign h_wires[edge_idx][0] = row_inputs[edge_idx];
            assign v_wires[0][edge_idx] = col_inputs[edge_idx];
        end
    endgenerate

    // Instantiate the 4x4 Grid of PEs
    genvar r, c;
    generate
        for (r = 0; r < ARRAY_SIZE; r++) begin : rows
            for (c = 0; c < ARRAY_SIZE; c++) begin : cols
                
                mac_pe #(.WIDTH(WIDTH)) pe_inst (
                    .clk(clk),
                    .rst_n(rst_n),
                    .load_weight(load_weights),
                    .in_a(h_wires[r][c]),       
                    .in_b(v_wires[r][c]),       
                    .weight_in(v_wires[r][c]),  
                    .out_a(h_wires[r][c+1]),    
                    .out_b(v_wires[r+1][c])     
                );
                
            end
        end
        
        // Connect the bottom of the grid to the outputs
        for (c = 0; c < ARRAY_SIZE; c++) begin : map_outs
            assign col_outputs[c] = v_wires[ARRAY_SIZE][c];
        end
    endgenerate
    // --- WAVEFORM DUMPING ---
    // This acts as a camera, recording every wire in the module
    initial begin
        $dumpfile("sim.vcd");
        $dumpvars(0, systolic_array);
    end

endmodule