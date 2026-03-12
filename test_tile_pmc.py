import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly

class MockMemoryPMC:
    """A hostile memory controller with a strict 5-cycle delay"""
    def __init__(self, latency):
        self.latency = latency

    async def run(self, dut):
        dut.mem_rd_valid.value = 0
        dut.mem_rd_data.value = 0
        await RisingEdge(dut.clk)
        
        while True:
            await ReadOnly()
            if str(dut.mem_rd_en.value) == '1':
                await RisingEdge(dut.clk)
                # Force exact memory stall cycles
                for _ in range(self.latency):
                    await RisingEdge(dut.clk)
                    
                dut.mem_rd_valid.value = 1
                dut.mem_rd_data.value = 0x0001000100010001000100010001000100010001000100010001000100010001
                await RisingEdge(dut.clk)
                dut.mem_rd_valid.value = 0
            else:
                await RisingEdge(dut.clk)

@cocotb.test()
async def test_pmc_registers(dut):
    """Hostile environment test to trigger hardware PMCs"""
    
    # 1. Start System
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # Give memory an exact 5-cycle lag
    mem = MockMemoryPMC(latency=5)
    cocotb.start_soon(mem.run(dut))

    # Reset
    dut.rst_n.value = 0
    dut.n_in_valid.value = 0; dut.n_in_data.value = 0
    dut.s_in_valid.value = 0; dut.s_in_data.value = 0
    dut.e_in_valid.value = 0; dut.e_in_data.value = 0
    dut.w_in_valid.value = 0; dut.w_in_data.value = 0
    
    # 💥 HOSTILE ACT #1: Freeze the downstream NoC routers!
    dut.n_out_ready.value = 0
    dut.s_out_ready.value = 0
    dut.e_out_ready.value = 0
    dut.w_out_ready.value = 0

    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # 2. Inject 1 Node (Degree = 4, meaning 4 memory fetches)
    degree = 4
    payload = (1 << 63) | (0 << 47) | (degree << 39) | 0x10000000
    packet = (0x0 << 76) | (0x0 << 72) | (0x01 << 64) | payload

    dut.w_in_data.value = packet
    dut.w_in_valid.value = 1
    await RisingEdge(dut.clk)
    dut.w_in_valid.value = 0

    # 3. Wait exactly 30 cycles to let the traffic jam build up
    for _ in range(30):
        await RisingEdge(dut.clk)

    # 4. Release the stall! Open the floodgates.
    dut.n_out_ready.value = 1
    dut.s_out_ready.value = 1
    dut.e_out_ready.value = 1
    dut.w_out_ready.value = 1

    # 5. Wait for the result packet to pop out
    for _ in range(100):
        await RisingEdge(dut.clk)
        if str(dut.e_out_valid.value) == '1' or str(dut.s_out_valid.value) == '1':
            break

    # Wait 2 more cycles for PMCs to settle their final values
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    # 6. Read the internal hardware registers directly
    active_cycles = int(dut.pmc_active_cycles.value)
    mem_stall     = int(dut.pmc_mem_stall_cycles.value)
    compute       = int(dut.pmc_compute_cycles.value)
    noc_stall     = int(dut.pmc_noc_stall_cycles.value)

    dut._log.info("=====================================================")
    dut._log.info("📊 PMC HARDWARE DIAGNOSTICS READOUT")
    dut._log.info("=====================================================")
    dut._log.info(f"🟢 Total Active Cycles : {active_cycles}")
    dut._log.info(f"🟡 Memory Stall Cycles : {mem_stall}   (Expected: ~20)")
    dut._log.info(f"🔵 Compute ALUs Fired  : {compute}   (Expected: ~1)")
    dut._log.info(f"🔴 NoC Router Blocked  : {noc_stall}   (Expected: >0)")
    dut._log.info("=====================================================")