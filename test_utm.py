import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import random

@cocotb.test()
async def test_pingpong_buffer(dut):
    """Verify Double-Buffered SRAM Swap Logic"""
    
    # 1. Start Clock & Reset
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    dut.rst_n.value = 0
    dut.swap.value = 0
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    dut._log.info("--- PHASE 1: Write to Bank 0 ---")
    # Generate some random 64-bit test data
    test_data_bank0 = [random.getrandbits(64) for _ in range(4)]
    
    dut.wr_en.value = 1
    for i in range(4):
        dut.wr_addr.value = i
        dut.wr_data.value = test_data_bank0[i]
        await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    
    dut._log.info("--- THE SWAP ---")
    # Flip the buffer! Bank 0 becomes Read, Bank 1 becomes Write
    dut.swap.value = 1
    await RisingEdge(dut.clk)
    dut.swap.value = 0
    
    dut._log.info("--- PHASE 2: Read Bank 0 WHILE Writing Bank 1 ---")
    test_data_bank1 = [random.getrandbits(64) for _ in range(4)]
    
    dut.wr_en.value = 1
    dut.rd_en.value = 1
    
    for i in range(4):
        # Write to Bank 1
        dut.wr_addr.value = i
        dut.wr_data.value = test_data_bank1[i]
        
        # Read from Bank 0
        dut.rd_addr.value = i
        
        # Wait for the combinational read and sequential write to resolve
        await RisingEdge(dut.clk) 
        
        read_val = dut.rd_data.value.integer
        assert read_val == test_data_bank0[i], f"Collision! Expected {test_data_bank0[i]}, got {read_val}"
        dut._log.info(f"Cycle {i} | Safely read: {read_val}")

    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut._log.info("🚀 PING-PONG BUFFER PASSED! ZERO READ/WRITE COLLISIONS!")