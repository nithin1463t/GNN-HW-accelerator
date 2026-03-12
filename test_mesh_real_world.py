import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly
import urllib.request
import gzip
import os

class SharedMemoryController:
    """HBM3 High-Bandwidth Memory Controller (2.5D Stacked)"""
    def __init__(self, num_tiles):
        self.num_tiles = num_tiles
        self.latency_cycles = 3 
        self.pending_requests = [0] * num_tiles

    async def run(self, dut):
        dut.mem_rd_valid.value = 0
        for i in range(self.num_tiles): dut.mem_rd_data[i].value = 0
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

def download_and_parse_snap_dataset():
    url = "https://snap.stanford.edu/data/facebook_combined.txt.gz"
    file_path = "facebook_combined.txt.gz"
    if not os.path.exists(file_path):
        print("🌐 Downloading Stanford SNAP Facebook Dataset...")
        urllib.request.urlretrieve(url, file_path)
    degrees = {}
    with gzip.open(file_path, 'rt') as f:
        for line in f:
            u, v = map(int, line.strip().split())
            degrees[u] = degrees.get(u, 0) + 1
            degrees[v] = degrees.get(v, 0) + 1
    max_node = max(degrees.keys())
    return [degrees.get(i, 1) for i in range(max_node + 1)]

@cocotb.test()
async def benchmark_real_world_mesh(dut):
    """Stress test the massive 256-core NoC"""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    
    # UPGRADE: 256 Memory Channels for HBM3
    mem_ctrl = SharedMemoryController(256)
    cocotb.start_soon(mem_ctrl.run(dut))

    dut.rst_n.value = 0
    dut.host_in_valid.value = 0; dut.host_in_data.value = 0
    dut.host_out_ready.value = 1
    
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    degrees = download_and_parse_snap_dataset()
    NUM_NODES = len(degrees)
    total_edges = sum(degrees)

    dut._log.info("=====================================================")
    dut._log.info(f"🚀 BOOTING 16x16 GRAPHCORE MESH (256 CORES ACTIVE)")
    dut._log.info(f"📚 DATASET: Stanford SNAP Facebook Ego Network")
    dut._log.info(f"📊 GRAPH: {NUM_NODES} Nodes, {total_edges} Edges")
    dut._log.info("=====================================================")

    cycle_count = 0
    async def cycle_counter():
        nonlocal cycle_count
        while True:
            await RisingEdge(dut.clk)
            cycle_count += 1
            if cycle_count > 1000000:
                assert False, "Simulation deadlock detected!"
    cocotb.start_soon(cycle_counter())

    results_received = 0
    async def result_monitor():
        nonlocal results_received
        while results_received < NUM_NODES:
            await RisingEdge(dut.clk)
            if str(dut.host_out_valid.value) == '1':
                results_received += 1
                if results_received % 500 == 0 or results_received == NUM_NODES:
                    dut._log.info(f"✅ Packet Exit! Computed Node {results_received}/{NUM_NODES}")

    monitor_task = cocotb.start_soon(result_monitor())

    for i, deg in enumerate(degrees):
        last_flag = 1 if i == (NUM_NODES - 1) else 0
        
        # UPGRADE: Distribute across a 16x16 grid
        dest_x = i % 16 
        dest_y = (i // 16) % 16
        
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
    for _ in range(20): await RisingEdge(dut.clk)

    # =========================================================================
    # EXTREMELY DETAILED PERFORMANCE LOGS (2D HEATMAPS + GOPS)
    # =========================================================================
    # UPGRADE: 16 columns by 16 rows
    active_grid = [[0]*16 for _ in range(16)]
    mem_grid    = [[0]*16 for _ in range(16)]
    
    total_active, total_mem, max_active, max_x, max_y = 0, 0, 0, 0, 0

    for y in range(16):
        for x in range(16):
            tile = dut.X_DIM[x].Y_DIM[y].tile_inst
            act = int(tile.pmc_active_cycles.value)
            mem = int(tile.pmc_mem_stall_cycles.value)
            
            active_grid[y][x] = act
            mem_grid[y][x] = mem
            
            total_active += act
            total_mem += mem
            
            if act > max_active:
                max_active = act
                max_x, max_y = x, y

    total_operations = total_edges * 16
    projected_time_seconds = cycle_count * 1e-9
    effective_gops = (total_operations / projected_time_seconds) / 1e9

    dut._log.info("=====================================================")
    dut._log.info(" 16x16 SILICON UTILIZATION HEATMAP (Active Cycles) ")
    dut._log.info("=====================================================")
    for y in range(16):
        row_str = " | ".join(f"{val:5d}" for val in active_grid[y])
        dut._log.info(f"Row {y:2d}: | {row_str} |")

    dut._log.info("=====================================================")
    dut._log.info(" GRAPHCORE-X 256-CORE BENCHMARK RESULTS")
    dut._log.info("=====================================================")
    dut._log.info(f"-  Total Mesh Latency : {cycle_count} Clock Cycles")
    dut._log.info(f"- Effective Compute  : {effective_gops:.2f} GOPS (at 1 GHz)")
    dut._log.info(f"- Heaviest Bottleneck: Tile ({max_x},{max_y}) ran for {max_active} cycles.")
    dut._log.info(f"- Global Mem Stall % : {(total_mem / total_active * 100) if total_active > 0 else 0:.2f}%")
    dut._log.info("=====================================================")