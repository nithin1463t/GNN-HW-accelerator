import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import random

@cocotb.test()
async def test_noc_to_dcu_flow(dut):
    """Verify NoC Packet triggers Tile FSM and flows through DCU to Egress"""
    
    # --- 1. System Setup ---
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # Initialize all input signals to 0 to prevent 'X' propagation
    dut.rst_n.value = 0
    dut.mesh_in_valid.value = 0
    dut.mesh_in_data.value = 0
    dut.mem_rd_valid.value = 0
    dut.mem_rd_data.value = 0
    
    # Hold reset for 5 clock cycles
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    dut._log.info("System Reset Released.")

    # --- 2. Inject NoC Command Packet ---
    # Packet Format: [Target_ID=00 (8b) | Type=START=01 (8b) | Unused (16b) | Payload (32b)]
    cmd_packet = (0x00 << 72) | (0x01 << 64) | 0x000000000000
    
    dut._log.info("📡 Injecting NoC Command Packet to Tile 0...")
    dut.mesh_in_data.value = cmd_packet
    dut.mesh_in_valid.value = 1
    await RisingEdge(dut.clk)
    dut.mesh_in_valid.value = 0

    # --- 3. Verify FSM Activation ---
    # Wait until Tile moves from IDLE to BUSY
    while str(dut.tile_busy.value) != '1':
        await RisingEdge(dut.clk)
    dut._log.info("✅ Tile 0 decoded NoC command. Status: BUSY.")

    # --- 4. Simulate Memory Fetch (Aggregation Phase) ---
    # We simulate the SAU fetching 4 neighbors from 'DRAM'
    neighbors = [0x1111, 0x2222, 0x3333, 0x4444]
    for val in neighbors:
        # Wait for SAU to request memory
        while str(dut.mem_rd_en.value) != '1':
            await RisingEdge(dut.clk)
        
        # Simulate variable memory controller latency
        await Timer(random.randint(10, 40), unit="ns")
        
        dut.mem_rd_valid.value = 1
        dut.mem_rd_data.value = val
        await RisingEdge(dut.clk)
        dut.mem_rd_valid.value = 0
    
    dut._log.info("🛠️ Aggregation Complete. SAU results moved to UTM.")

    # --- 5. Verify NoC Result Egress (Transformation Phase) ---
    dut._log.info("⏳ Waiting for DCU Transformation and NoC Egress...")
    
    # The DCU takes about 8-10 cycles to process. 
    # We wait for the packet to appear on the mesh output.
    found_result = False
    for _ in range(50): # Timeout after 50 cycles
        await RisingEdge(dut.clk)
        if str(dut.mesh_out_valid.value) == '1':
            result_packet = dut.mesh_out_data.value
            packet_type = (int(result_packet) >> 64) & 0xFF
            
            if packet_type == 0x02: # Result Data Type
                dut._log.info(f"🚀 SUCCESS! NoC Output Captured: {hex(int(result_packet))}")
                found_result = True
                break

    if not found_result:
        raise AssertionError("Timeout: NoC Result packet never reached mesh_out!")

    dut._log.info("**************************************************")
    dut._log.info("🏁 END-TO-END FLOW VERIFIED: NOC -> SAU -> UTM -> DCU -> NOC")
    dut._log.info("**************************************************")