import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

async def mock_external_memory(dut):
    """Simulate realistic external DRAM with a 10-cycle read latency"""
    dut.mem_rd_valid.value = 0
    dut.mem_rd_data.value = 0
    
    while True:
        await RisingEdge(dut.clk)
        if str(dut.mem_rd_en.value) == '1':
            # DRAM received a read request, simulate 10 cycles of latency
            for _ in range(10):
                await RisingEdge(dut.clk)
            
            # Return the 256-bit vector payload
            dut.mem_rd_valid.value = 1
            dut.mem_rd_data.value = 0x0001000100010001000100010001000100010001000100010001000100010001
            await RisingEdge(dut.clk)
            dut.mem_rd_valid.value = 0

@cocotb.test()
async def test_l1_cache_performance(dut):
    """Inject two identical tasks to prove L1 Cache latency reduction"""
    
    # Start the Clock and the Mock DRAM Coroutine
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    cocotb.start_soon(mock_external_memory(dut))

    # Reset System
    dut.rst_n.value = 0
    dut.n_in_valid.value = 0; dut.n_in_data.value = 0
    dut.s_in_valid.value = 0; dut.s_in_data.value = 0
    dut.e_in_valid.value = 0; dut.e_in_data.value = 0
    dut.w_in_valid.value = 0; dut.w_in_data.value = 0

    dut.n_out_ready.value = 1
    dut.s_out_ready.value = 1
    dut.e_out_ready.value = 1
    dut.w_out_ready.value = 1

    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # Standard Unicast START Packet
    packet = (0x0 << 76) | (0x0 << 72) | (0x01 << 64) | 0x0
    
    # =========================================================================
    # RUN 1: Cold Cache (Expect Misses and High Latency)
    # =========================================================================
    dut._log.info("📡 Injecting Packet 1 (Cold Cache)...")
    dut.w_in_data.value = packet
    dut.w_in_valid.value = 1
    await RisingEdge(dut.clk)
    dut.w_in_valid.value = 0

    cycles_1 = 0
    while str(dut.s_out_valid.value) == '0':
        await RisingEdge(dut.clk)
        cycles_1 += 1
        
    dut._log.info(f"🐢 Run 1 Finished in {cycles_1} clock cycles (Suffered DRAM Latency)")

    # Wait a few cycles for the pipeline to fully drain
    for _ in range(10): 
        await RisingEdge(dut.clk)

    # =========================================================================
    # RUN 2: Warm Cache (Expect Hits and Low Latency)
    # =========================================================================
    dut._log.info("📡 Injecting Packet 2 (Warm Cache)...")
    dut.w_in_data.value = packet
    dut.w_in_valid.value = 1
    await RisingEdge(dut.clk)
    dut.w_in_valid.value = 0

    cycles_2 = 0
    while str(dut.s_out_valid.value) == '0':
        await RisingEdge(dut.clk)
        cycles_2 += 1
        
    dut._log.info(f"⚡ Run 2 Finished in {cycles_2} clock cycles (L1 Cache Hits!)")

    # Assert that the cache actually improved performance
    assert cycles_2 < cycles_1, "Cache failed to improve performance! Hardware Bug!"
    dut._log.info("🚀 SUCCESS! L1 Feature Cache heavily accelerated the pipeline.")