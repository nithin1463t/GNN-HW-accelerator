import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import random

@cocotb.test()
async def test_sau_aggregation(dut):
    """Verify Scatter-Gather and Reduction logic with random memory latency"""
    
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    await Timer(20, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # Setup 3 neighbors with specific feature values
    neighbors = [0x0001000100010001, 0x0002000200020002, 0x0003000300030003]
    expected_sum = 0x0006000600060006 # 1+2+3 for each 16-bit slot

    # Trigger SAU
    dut.start.value = 1
    dut.base_addr.value = 0x1000
    dut.neighbor_count.value = 3
    await RisingEdge(dut.clk)
    dut.start.value = 0

    # Simulate Memory Controller with variable latency
    for i in range(3):
        while dut.mem_rd_en.value == 0:
            await RisingEdge(dut.clk)
        
        # Random latency: 1 to 5 cycles
        for _ in range(random.randint(1, 5)):
            await RisingEdge(dut.clk)
        
        dut.mem_rd_valid.value = 1
        dut.mem_rd_data.value = neighbors[i]
        await RisingEdge(dut.clk)
        dut.mem_rd_valid.value = 0

    # Wait for completion
    while not dut.done.value:
        await RisingEdge(dut.clk)

    # Verify final handoff to UTM [cite: 34, 35]
    actual_sum = dut.utm_data.value.integer
    assert actual_sum == expected_sum, f"Sum Error! HW: {hex(actual_sum)}, Expected: {hex(expected_sum)}"
    dut._log.info(f"🚀 SAU PASSED! Aggregated {dut.neighbor_count.value} neighbors correctly.")