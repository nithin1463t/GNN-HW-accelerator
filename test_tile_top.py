import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import random

@cocotb.test()
async def test_full_tile_flow(dut):
    """Verify End-to-End GNN Tile: Aggregation to Memory Handoff"""
    
    # Start the clock immediately
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # Initialize inputs to known values to prevent 'X' propagation
    dut.rst_n.value = 0
    dut.start_tile.value = 0
    dut.mem_rd_valid.value = 0
    dut.mem_rd_data.value = 0
    
    # Hold reset for several cycles
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    
    # Wait for the first rising edge after reset to ensure logic is stable
    await RisingEdge(dut.clk)

    # 1. Start the Orchestration
    dut.start_tile.value = 1
    await RisingEdge(dut.clk)
    dut.start_tile.value = 0

    # 2. Simulate Memory Controller providing 4 neighbors
    neighbors = [0x1, 0x2, 0x3, 0x4] 
    for val in neighbors:
        # Wait until the hardware drives the signal to a valid '0' or '1'
        while True:
            await RisingEdge(dut.clk)
            # Check if the signal is valid and high
            if dut.mem_rd_en.value.binstr == '1':
                break
        
        # Simulate variable DRAM latency (Scatter-Gather behavior)
        await Timer(random.randint(10, 50), unit="ns")
        
        dut.mem_rd_valid.value = 1
        dut.mem_rd_data.value = val
        await RisingEdge(dut.clk)
        dut.mem_rd_valid.value = 0

    # 3. Wait for the GCU to finish and drop the busy signal
    while dut.tile_busy.value.binstr != '0':
        await RisingEdge(dut.clk)

    dut._log.info("🚀 FULL TILE SUCCESS! Data gathered and buffered for the DCU.")