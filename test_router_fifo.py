import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

@cocotb.test()
async def test_fifo_congestion(dut):
    """Verify FIFO buffer bounds, full/empty flags, and data integrity"""
    
    # 1. Start 100MHz Clock (Fixed 'unit' deprecation warning)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # 2. System Reset
    dut.rst_n.value = 0
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    assert dut.empty.value == 1, "Error: FIFO should be empty after reset"
    dut._log.info("✓ Reset successful. FIFO is empty.")

    # 3. Fill the FIFO to maximum depth (4 packets)
    dut._log.info("→ Simulating network congestion (Writing 4 packets)...")
    base_payload = 0xAA00BB00CC00DD00EE00
    
    for i in range(4):
        dut.wr_en.value = 1
        dut.wr_data.value = base_payload + i
        await RisingEdge(dut.clk)
    
    # Stop writing and wait a cycle for the full flag to assert
    dut.wr_en.value = 0
    await RisingEdge(dut.clk)
    
    assert dut.full.value == 1, "Error: FIFO failed to assert 'full' flag to upstream router"
    dut._log.info("✓ 'Full' flag correctly asserted. Backpressure working.")

    # 4. Drain the FIFO and verify strict First-In-First-Out order
    dut._log.info("← Clearing congestion (Reading 4 packets)...")
    for i in range(4):
        # WAIT FOR FALLING EDGE: Ensures combinational logic has completely settled
        await FallingEdge(dut.clk)
        
        expected_data = base_payload + i
        actual_data = int(dut.rd_data.value)
        
        assert actual_data == expected_data, f"Data mismatch! Expected {hex(expected_data)}, Got {hex(actual_data)}"
        
        # Pop the data
        dut.rd_en.value = 1
        await RisingEdge(dut.clk)
        
    # Stop reading and check empty flag
    dut.rd_en.value = 0
    await FallingEdge(dut.clk)

    assert dut.empty.value == 1, "Error: FIFO should be empty after draining"
    dut._log.info("✓ Data integrity verified. FIFO successfully drained.")
    dut._log.info("🚀 SUCCESS: Router FIFO is ready for integration!")