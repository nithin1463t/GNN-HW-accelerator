import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly
import networkx as nx

class SharedMemoryController:
    """A centralized Mock DRAM that serves all tiles in the mesh simultaneously"""
    def __init__(self, num_tiles):
        self.num_tiles = num_tiles
        self.latency_cycles = 10
        self.pending_requests = [0] * num_tiles

    async def run(self, dut):
        dut.mem_rd_valid.value = 0
        
        # Initialize an array of 0s for the 256-bit data lines
        for i in range(self.num_tiles):
            dut.mem_rd_data[i].value = 0
            
        await RisingEdge(dut.clk)
        
        while True:
            await ReadOnly()
            
            # 1. Scan all memory channels for new requests
            en_bits = int(dut.mem_rd_en.value)
            for i in range(self.num_tiles):
                if (en_bits >> i) & 1:
                    # If this channel just requested data, start its countdown
                    if self.pending_requests[i] == 0:
                        self.pending_requests[i] = self.latency_cycles

            await RisingEdge(dut.clk)
            
            # 2. Process countdowns and deliver data
            valid_mask = 0
            for i in range(self.num_tiles):
                if self.pending_requests[i] > 0:
                    self.pending_requests[i] -= 1
                    if self.pending_requests[i] == 0:
                        # Timer finished! Deliver payload
                        valid_mask |= (1 << i)
                        dut.mem_rd_data[i].value = 0x0001000100010001000100010001000100010001000100010001000100010001
            
            dut.mem_rd_valid.value = valid_mask

@cocotb.test()
async def benchmark_2x2_mesh(dut):
    """Inject a small graph into a 2x2 multi-core NoC"""
    
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # 2x2 = 4 Tiles
    NUM_TILES = 4 
    mem_ctrl = SharedMemoryController(NUM_TILES)
    cocotb.start_soon(mem_ctrl.run(dut))

    # Reset
    dut.rst_n.value = 0
    dut.host_in_valid.value = 0; dut.host_in_data.value = 0
    dut.host_out_ready.value = 1
    
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # Generate a small 8-node test graph
    NUM_NODES = 8
    G = nx.barabasi_albert_graph(NUM_NODES, 2)
    degrees = [deg for node, deg in G.degree()]

    dut._log.info("=====================================================")
    dut._log.info(f"🌐 BOOTING 2x2 GRAPHCORE MESH (4 Cores Active)")
    dut._log.info(f"📊 GRAPH: {NUM_NODES} Nodes, Max Degree: {max(degrees)}")
    dut._log.info("=====================================================")

    cycle_count = 0
    async def cycle_counter():
        nonlocal cycle_count
        while True:
            await RisingEdge(dut.clk)
            cycle_count += 1
            if cycle_count > 10000:
                assert False, "Simulation deadlock detected in Mesh."
    cocotb.start_soon(cycle_counter())

    # Monitor Host Egress (Tile 1,1)
    results_received = 0
    async def result_monitor():
        nonlocal results_received
        while results_received < NUM_NODES:
            await RisingEdge(dut.clk)
            if str(dut.host_out_valid.value) == '1':
                results_received += 1
                dut._log.info(f"✅ Packet Exit! Computed Node {results_received}/{NUM_NODES}")

    monitor_task = cocotb.start_soon(result_monitor())

    # Inject into Host Ingress (Tile 0,0)
    for i, deg in enumerate(degrees):
        last_flag = 1 if i == (NUM_NODES - 1) else 0
        
        # Calculate Target Tile X/Y dynamically (distribute workload)
        dest_x = i % 2 
        dest_y = (i // 2) % 2
        
        # Header: [Dest_X(4) | Dest_Y(4) | CMD=0x01(8)]
        header = (dest_x << 76) | (dest_y << 72) | (0x01 << 64)
        payload = (last_flag << 63) | (i << 47) | (deg << 39) | 0x10000000
        packet = header | payload

        while str(dut.host_in_ready.value) == '0':
            await RisingEdge(dut.clk)

        dut.host_in_data.value = packet
        dut.host_in_valid.value = 1
        await RisingEdge(dut.clk)
        dut.host_in_valid.value = 0
        await RisingEdge(dut.clk) 

    await monitor_task

    dut._log.info("=====================================================")
    dut._log.info(f"🏆 2x2 MESH SUCCESS! Latency: {cycle_count} Cycles")
    dut._log.info("=====================================================")