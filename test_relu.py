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
async def test_pipelined_relu(dut):
    """Test PyTorch ReLU against hardware Pipelined ReLU"""
    
    # 1. Start Clock & Reset
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.in_flat.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # 2. Generate Test Data (Mix of positive and negative)
    torch.manual_seed(42)
    # Generate 5 cycles worth of data, values between -20 and 20
    test_vectors = torch.randint(-20, 20, (5, 4), dtype=torch.int32)
    
    # PyTorch Golden Model
    expected_outputs = F.relu(test_vectors)

    dut._log.info("Starting Pipeline Streaming...")

    # 3. Stream data in and capture data out
    hardware_capture = []
    
    # We run for 6 cycles to let the final data flush out of the pipeline
    for cycle in range(6):
        
        # Inject data on cycles 0-4
        if cycle < 5:
            current_input = test_vectors[cycle].tolist()
            dut.in_flat.value = pack_array(current_input)
            dut._log.info(f"Cycle {cycle} | Injecting : {current_input}")
        else:
            dut.in_flat.value = 0 # Flush the pipeline
            
        await RisingEdge(dut.clk)
        
        # Capture data safely (Outputs arrive 1 cycle after input)
        if cycle > 0:
            out_val = dut.out_flat.value
            out_packed = out_val.to_unsigned() if out_val.is_resolvable else 0
            captured_array = unpack_array(out_packed)
            hardware_capture.append(captured_array)
            dut._log.info(f"Cycle {cycle} | Captured  : {captured_array}")

    # 4. Verify Results
    dut._log.info("--- VERIFICATION ---")
    for i in range(5):
        hw_result = hardware_capture[i]
        py_expected = expected_outputs[i].tolist()
        
        assert hw_result == py_expected, f"Mismatch at index {i}! HW: {hw_result}, PyTorch: {py_expected}"
        
    dut._log.info("🚀 PIPELINED RELU PASSED! CYCLE-ACCURATE TIMING VERIFIED!")