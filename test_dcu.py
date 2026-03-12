import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import torch
import torch.nn.functional as F

# --- Helpers: Pack/Unpack ---
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
async def test_dcu_top(dut):
    """Test the fully integrated DCU (MatMul + Pipelined ReLU)"""
    
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.rst_n.value = 0
    dut.load_weights.value = 0
    dut.row_inputs_flat.value = 0
    dut.col_inputs_flat.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # 1. PyTorch Golden Model
    torch.manual_seed(42)
    W = torch.randint(-5, 5, (4, 4), dtype=torch.int32)
    X = torch.randint(-5, 5, (4,), dtype=torch.int32)
    
    Y_matmul = torch.matmul(X, W)
    Y_expected = F.relu(Y_matmul)  # Apply ReLU to the MatMul result
    
    dut._log.info(f"PyTorch Raw MatMul : {Y_matmul.numpy()}")
    dut._log.info(f"PyTorch Expected Y : {Y_expected.numpy()}")

    # 2. Load Weights
    dut.load_weights.value = 1
    for row_idx in reversed(range(4)):
        dut.col_inputs_flat.value = pack_array(W[row_idx].tolist())
        await RisingEdge(dut.clk)
    dut.load_weights.value = 0
    dut.col_inputs_flat.value = 0 

    # 3. Pipeline Flush
    dut.row_inputs_flat.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)

    # 4. Stream Features (Extended to 16 cycles for the extra ReLU delay)
    hardware_output_capture = []
    for cycle in range(16):
        current_row_inputs = [0, 0, 0, 0]
        for i in range(4):
            if cycle == i:
                current_row_inputs[i] = X[i].item()
                
        dut.row_inputs_flat.value = pack_array(current_row_inputs)
        await RisingEdge(dut.clk)
        
        out_val = dut.dcu_out_flat.value
        out_packed = out_val.to_unsigned() if out_val.is_resolvable else 0
        hardware_output_capture.append(unpack_array(out_packed))

    # 5. Verify Results
    # Notice the indices shifted down by exactly 1 cycle (from 4,5,6,7 to 5,6,7,8)!
    Y_hardware = [
        hardware_output_capture[5][0], 
        hardware_output_capture[6][1], 
        hardware_output_capture[7][2], 
        hardware_output_capture[8][3]  
    ]

    dut._log.info(f"Hardware Actual Y  : {Y_hardware}")
    assert list(Y_expected.numpy()) == Y_hardware, f"FAILED! Hardware got {Y_hardware}"
    dut._log.info("🚀 DCU TOP-LEVEL PASSED! MATMUL + RELU PERFECTLY PIPELINED!")