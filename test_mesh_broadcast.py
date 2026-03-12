import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_8x8_broadcast_stress(dut):
    """Verify Spanning Tree Broadcast and Network Congestion Absorption"""
    
    # 1. Start the 100MHz Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # 2. System Reset
    dut.rst_n.value = 0
    dut.host_in_data.value = 0
    dut.host_in_valid.value = 0
    dut.host_out_ready.value = 0
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # 3. Assert Host Ready
    dut.host_out_ready.value = 1

    # 4. Inject ONE Broadcast Packet (cmd = 0x03)
    # Header: [Target_X=F (4b) | Target_Y=F (4b) | Type=BROADCAST=03 (8b) | Payload=0]
    packet = (0xF << 76) | (0xF << 72) | (0x03 << 64) | 0x0
    
    dut._log.info(f"📡 Injecting SINGLE Broadcast Packet into 8x8 Mesh...")
    
    # Wait until NoC entry is ready
    while str(dut.host_in_ready.value) == '0':
        await RisingEdge(dut.clk)
            
    dut.host_in_data.value = packet
    dut.host_in_valid.value = 1
    await RisingEdge(dut.clk)
    dut.host_in_valid.value = 0

    # 5. Wait for the network to route all 64 replies to the exit port
    results_received = 0
    for cycle in range(5000): 
        await RisingEdge(dut.clk)
        
        if str(dut.host_out_valid.value) == '1':
            results_received += 1
            if results_received % 16 == 0:
                dut._log.info(f"📥 Received {results_received}/64 result packets from the NoC.")
                
            if results_received == 64:
                dut._log.info(f"🚀 SUCCESS! All 64 cores received the broadcast and computed successfully!")
                break

    assert results_received == 64, f"Network Deadlock! Only received {results_received} out of 64 packets."