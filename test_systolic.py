import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import torch

# --- Helpers: Pack Python Arrays into 64-bit Verilog buses ---
def pack_array(tensor_array, width=16):
    packed_val = 0
    for i, val in enumerate(tensor_array):
        val_int = int(val) & ((1 << width) - 1)
        packed_val |= (val_int << (i * width))
    return packed_val

def unpack_array(packed_val, array_size=4, width=16):
    res = []
    for i in range(array_size):
        val = (packed_val >> (i * width)) & ((1 << width) - 1)
        if val & (1 << (width - 1)):
            val -= (1 << width)
        res.append(val)
    return res

@cocotb.test()
async def test_pytorch_systolic(dut):
    """Inject PyTorch Tensors into the Systolic Array"""
    
    # Start a 10ns Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # Initial Reset
    dut.rst_n.value = 0
    dut.load_weights.value = 0
    dut.row_inputs_flat.value = 0
    dut.col_inputs_flat.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # =================================================================
    # STEP 1: GENERATE PYTORCH GOLDEN MODEL
    # =================================================================
    torch.manual_seed(42)
    W = torch.randint(-5, 5, (4, 4), dtype=torch.int32)
    X = torch.randint(-5, 5, (4,), dtype=torch.int32)
    Y_expected = torch.matmul(X, W)
    
    dut._log.info(f"PyTorch Expected Y: {Y_expected.numpy()}")

    # =================================================================
        # STEP 2: LOAD WEIGHTS INTO HARDWARE
    # =================================================================
    dut.load_weights.value = 1
    for row_idx in reversed(range(4)):
        weight_row = W[row_idx].tolist()
        dut.col_inputs_flat.value = pack_array(weight_row)
        await RisingEdge(dut.clk)
        
    dut.load_weights.value = 0
    dut.col_inputs_flat.value = 0 

    # =================================================================
    # STEP 2.5: THE PIPELINE FLUSH FIX
    # =================================================================
    dut._log.info("Flushing residual weights from the pipeline...")
    dut.row_inputs_flat.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)

    # =================================================================
    # STEP 3: STREAM FEATURES (WITH SYSTOLIC SKEW)
    # =================================================================
    hardware_output_capture = []

    # Extended to 15 cycles to ensure we capture the entire diagonal cascade
    for cycle in range(15):
        current_row_inputs = [0, 0, 0, 0]
        for i in range(4):
            if cycle == i:
                current_row_inputs[i] = X[i].item()
                
        dut.row_inputs_flat.value = pack_array(current_row_inputs)
        
        # Advance the clock so data propagates
        await RisingEdge(dut.clk)
        
        # Read outputs safely
        out_val = dut.col_outputs_flat.value
        if out_val.is_resolvable:
            out_packed = out_val.to_unsigned()
        else:
            out_packed = 0 
            
        hardware_output_capture.append(unpack_array(out_packed))

    # =================================================================
    # STEP 4: VERIFY RESULTS (WITH DEBUG GRID)
    # =================================================================
        dut._log.info("--- RAW HARDWARE OUTPUT GRID ---")
    for i, row in enumerate(hardware_output_capture):
        dut._log.info(f"Capture Cycle {i}: {row}")
    dut._log.info("--------------------------------")

    # The exact indices where valid data should drop out of the 4x4 array
    Y_hardware = [
        hardware_output_capture[4][0], 
        hardware_output_capture[5][1], 
        hardware_output_capture[6][2], 
        hardware_output_capture[7][3]  
    ]

    dut._log.info(f"Hardware Actual Y : {Y_hardware}")
    assert list(Y_expected.numpy()) == Y_hardware, f"FAILED! Hardware got {Y_hardware}"
    dut._log.info("🚀 SYSTOLIC ARRAY PASSED! MATCHES PYTORCH PERFECTLY!")