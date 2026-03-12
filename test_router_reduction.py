import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_in_network_reduction(dut):
    """Verify that the NoC Router intercepts and mathematically merges REDUCE packets"""
    
    # 1. Start the Clock
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # 2. System Reset
    dut.rst_n.value = 0
    
    # Initialize all inputs
    dut.local_in_valid.value = 0; dut.local_in_data.value = 0
    dut.n_in_valid.value = 0; dut.n_in_data.value = 0
    dut.s_in_valid.value = 0; dut.s_in_data.value = 0
    dut.e_in_valid.value = 0; dut.e_in_data.value = 0
    dut.w_in_valid.value = 0; dut.w_in_data.value = 0

    # Assert downstream readiness
    dut.local_out_ready.value = 1
    dut.n_out_ready.value = 1
    dut.s_out_ready.value = 1
    dut.e_out_ready.value = 1
    dut.w_out_ready.value = 1

    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # 3. Construct the Colliding Packets
    # Dest = (0xF, 0xF), Command = 0x04 (REDUCE)
    header = (0xF << 76) | (0xF << 72) | (0x04 << 64)
    
    payload_A = 0x0001000200030004
    payload_B = 0x0010002000300040
    
    packet_A = header | payload_A
    packet_B = header | payload_B

    dut._log.info(f"📡 Injecting Packet A (North): Payload = {hex(payload_A)}")
    dut._log.info(f"📡 Injecting Packet B (West) : Payload = {hex(payload_B)}")

    # 4. Inject Both Packets Simultaneously!
    dut.n_in_data.value = packet_A
    dut.n_in_valid.value = 1
    
    dut.w_in_data.value = packet_B
    dut.w_in_valid.value = 1
    
    await RisingEdge(dut.clk)
    dut.n_in_valid.value = 0
    dut.w_in_valid.value = 0

    # 5. Monitor the SOUTH Port for the Merged Result
    packets_received = 0
    expected_payload = 0x0011002200330044
    
    for cycle in range(50): 
        await RisingEdge(dut.clk)
        
        if str(dut.s_out_valid.value) == '1':
            packets_received += 1
            res = int(dut.s_out_data.value)
            res_payload = res & 0xFFFFFFFFFFFFFFFF # Extract lower 64 bits
            
            dut._log.info(f"💥 COLLISION MERGE SUCCESS! Emitted Packet Payload: {hex(res_payload)}")
            
            assert res_payload == expected_payload, f"Math Error! Expected {hex(expected_payload)}, got {hex(res_payload)}"

    # 6. Verify we only received exactly ONE packet (the other was absorbed)
    assert packets_received == 1, f"Routing Error! Expected 1 merged packet, but {packets_received} exited the router."
    dut._log.info("🚀 SUCCESS! The NoC Router is now a distributed Math Engine.")