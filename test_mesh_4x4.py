import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_4x4_routing_and_compute(dut):
    """Verify XY Routing from Host (0,0) across a 16-Tile Grid to (3,3)"""
    
    # 1. Start the 100MHz Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # 2. System Reset
    dut.rst_n.value = 0
    dut.host_in_data.value = 0
    dut.host_in_valid.value = 0
    
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # 3. Construct the 5-Port Routing Packet
    # Header: [Target_X=3 (4b) | Target_Y=3 (4b) | Type=START=01 (8b) | Payload=0]
    target_x = 0x3
    target_y = 0x3
    cmd_type = 0x01
    
    packet = (target_x << 76) | (target_y << 72) | (cmd_type << 64) | 0x0
    
    dut._log.info(f"📡 Injecting Packet to Mesh Entry. Target: Tile ({target_x},{target_y})")
    dut.host_in_data.value = packet
    dut.host_in_valid.value = 1
    await RisingEdge(dut.clk)
    dut.host_in_valid.value = 0

    # 4. Wait for the multi-hop traversal and local computation
    # In a 4x4 grid, a packet going from (0,0) to (3,3) takes 6 routing hops.
    # We give it 200 cycles to allow for routing + SAU fetch + DCU compute + egress routing.
    success = False
    for cycle in range(200):
        await RisingEdge(dut.clk)
        
        if str(dut.host_out_valid.value) == '1':
            res = int(dut.host_out_data.value)
            
            # Extract header from the resulting packet
            res_x = (res >> 76) & 0xF
            res_y = (res >> 72) & 0xF
            res_type = (res >> 64) & 0xFF
            
            # The tile was hardcoded to reply to Host (F,F) with Type 0x02
            if res_x == 0xF and res_y == 0xF and res_type == 0x02:
                dut._log.info(f"🚀 SUCCESS! Computed Result captured at Mesh Exit at {cocotb.utils.get_sim_time('ns')}ns")
                success = True
                break

    assert success, "Timeout: Packet lost in the NoC or Tile failed to compute!"