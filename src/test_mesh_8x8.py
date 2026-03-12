import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly
import networkx as nx

class SharedMemoryController:
    """A centralized Mock DRAM that serves all 64 tiles simultaneously"""
    def __init__(self, num_tiles):
        self.num_tiles = num_tiles
        self.latency_cycles = 10
        self.pending_requests = [0] * num_tiles

    async def run(self, dut):
        dut.mem_rd_valid.value = 0
        for i in range(self.num_tiles):
            dut.mem_rd_data[i].value = 0
            
        await RisingEdge(dut.clk)
        
        while True:
            await ReadOnly()
            en_bits = int(dut.mem_rd_en.value)
            
            for i in range(self.num_tiles):
                if (en_bits >> i) & 1:
                    if self.pending_requests[i] == 0:
                        self.pending_requests[i] = self.latency_cycles

            await RisingEdge(dut.clk)
            
            valid_mask = 0
            for i in range(self.num_tiles):
                if self.pending_requests[i] > 0:
                    self.pending_requests[i] -= 1
                    if self.pending_requests[i] == 0:
                        valid_mask |= (1 << i)
                        dut.mem_rd_data[i].value = 0x0001000100010001000100010001000100010001000100010001000100010001
            
            dut.mem_rd_valid.value = valid_mask

@cocotb.test()
async def benchmark_8x8_mesh(dut):
    """Inject a massive 256-node graph into the full 64-core NoC"""
    
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    NUM_TILES = 64 
    mem_ctrl = SharedMemoryController(NUM_TILES)
    cocotb.start_soon(mem_ctrl.run(dut))

    # Reset
    dut.rst_n.value = 0
    dut.host_in_valid.value = 0; dut.host_in_data.value = 0
    dut.host_out_ready.value = 1
    
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # Generate a massive 256-node workload
    NUM_NODES = 256
    G = nx.barabasi_albert_graph(NUM_NODES, 2)
    degrees = [deg for node, deg in G.degree()]

    dut._log.info("=====================================================")
    dut._log.info(f"🌐 BOOTING 8x8 GRAPHCORE MESH (64 Cores Active!)")
    dut._log.info(f"📊 GRAPH: {NUM_NODES} Nodes, Max Degree: {max(degrees)}")
    dut._log.info("=====================================================")

    cycle_count = 0
    async def cycle_counter():
        nonlocal cycle_count
        while True:
            await RisingEdge(dut.clk)
            cycle_count += 1
            if cycle_count > 150000:
                assert False, "Simulation deadlock detected in 8x8 Mesh."
    cocotb.start_soon(cycle_counter())

    # Monitor Host Egress (Tile 7,7)
    results_received = 0
    async def result_monitor():
        nonlocal results_received
        while results_received < NUM_NODES:
            await RisingEdge(dut.clk)
            if str(dut.host_out_valid.value) == '1':
                results_received += 1
                if results_received % 32 == 0 or results_received == NUM_NODES:
                    dut._log.info(f"✅ Packet Exit! Computed Node {results_received}/{NUM_NODES}")

    monitor_task = cocotb.start_soon(result_monitor())

    # Inject into Host Ingress (Tile 0,0)
    for i, deg in enumerate(degrees):
        last_flag = 1 if i == (NUM_NODES - 1) else 0
        
        # Distribute workload dynamically across the 8x8 (64) tiles
        dest_x = i % 8 
        dest_y = (i // 8) % 8
        
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
    dut._log.info(f"🏆 8x8 MESH (64-CORE) SUCCESS! Latency: {cycle_count} Cycles")
    dut._log.info("=====================================================")