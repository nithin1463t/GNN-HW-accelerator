import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly
import random

@cocotb.test()
async def test_gcu_orchestration(dut):
    """Verify GCU Master FSM: Command Dispatch & Phase Swapping"""
    
    # Start Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # Reset
    dut.rst_n.value = 0
    dut.host_start.value = 0
    dut.sau_done.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # 1. Trigger Chip Start (Simulating Host PCIe command)
    dut._log.info("--- Phase 1: Host Start ---")
    dut.host_start.value = 1
    await RisingEdge(dut.clk)
    dut.host_start.value = 0

    # 2. Check for SAU Dispatch
    while str(dut.sau_start.value) != '1':
        await RisingEdge(dut.clk)
    
    assert dut.chip_busy.value == 1
    # Fix: Use to_unsigned() instead of .integer to clear the DeprecationWarning
    addr_val = dut.sau_base_addr.value.to_unsigned()
    dut._log.info(f"GCU Dispatched SAU to Address: {hex(addr_val)}")

    # 3. Simulate SAU Processing Time
    dut._log.info("--- Phase 2: Waiting for Tile Aggregation ---")
    for _ in range(random.randint(5, 15)):
        await RisingEdge(dut.clk)
    
    # 4. Signal SAU Done (Simulating Tile completion)
    dut.sau_done.value = 1
    await RisingEdge(dut.clk)
    dut.sau_done.value = 0

    # --- THE ROBUST FIX ---
    # 1. Wait for the clock edge that triggers the state change to TRIGGER_COMB
    await RisingEdge(dut.clk)
    # 2. Use Timer(1) to move 1 picosecond past the edge so the register 
    # value actually updates in the simulator memory
    await cocotb.triggers.Timer(1, units='ps')
    
    # 5. Verify the UTM Swap
    assert dut.utm_swap.value == 1, "Error: GCU failed to trigger UTM Swap after SAU completion!"
    
    dut._log.info("🚀 GCU PASSED! Successfully managed handoff from SAU to UTM.")