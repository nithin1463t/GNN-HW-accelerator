import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly
import networkx as nx

class MockMemory:
    def __init__(self):
        self.actual_dram_reads = 0
        self.latency_cycles = 10

    async def run(self, dut):
        dut.mem_rd_valid.value = 0
        dut.mem_rd_data.value = 0
        await RisingEdge(dut.clk)
        while True:
            await ReadOnly() 
            if str(dut.mem_rd_en.value) == '1':
                self.actual_dram_reads += 1
                await RisingEdge(dut.clk)
                for _ in range(self.latency_cycles):
                    await RisingEdge(dut.clk)
                dut.mem_rd_valid.value = 1
                dut.mem_rd_data.value = 0x0001000100010001000100010001000100010001000100010001000100010001
                await RisingEdge(dut.clk)
                dut.mem_rd_valid.value = 0
            else:
                await RisingEdge(dut.clk)

@cocotb.test()
async def benchmark_gnn_workload(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start()) 
    mem = MockMemory()
    cocotb.start_soon(mem.run(dut))

    dut.rst_n.value = 0
    dut.w_in_valid.value = 0; dut.w_in_data.value = 0
    dut.n_in_valid.value = 0; dut.n_in_data.value = 0
    dut.s_in_valid.value = 0; dut.s_in_data.value = 0
    dut.e_in_valid.value = 0; dut.e_in_data.value = 0
    dut.n_out_ready.value = 1; dut.s_out_ready.value = 1
    dut.e_out_ready.value = 1; dut.w_out_ready.value = 1

    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    NUM_NODES = 64
    G = nx.barabasi_albert_graph(NUM_NODES, 2)
    degrees = [deg for node, deg in G.degree()]
    total_feature_fetches = sum(degrees)

    dut._log.info("=====================================================")
    dut._log.info(f"📊 GENERATED POWER-LAW GRAPH: {NUM_NODES} Nodes, {total_feature_fetches} Edges")
    dut._log.info(f"🔥 Max Supernode Degree: {max(degrees)}")
    dut._log.info("=====================================================")

    cycle_count = 0
    async def cycle_counter():
        nonlocal cycle_count
        while True:
            await RisingEdge(dut.clk)
            cycle_count += 1
            if cycle_count > 35000:
                dut._log.error("💥 DEADLOCK TIMEOUT!")
                assert False, "Simulation deadlock detected."
    cocotb.start_soon(cycle_counter())

    results_received = 0
    async def result_monitor():
        nonlocal results_received
        while results_received < NUM_NODES:
            await RisingEdge(dut.clk)
            if str(dut.s_out_valid.value) == '1' or str(dut.e_out_valid.value) == '1':
                results_received += 1
                if results_received % 8 == 0 or results_received == NUM_NODES:
                    dut._log.info(f"✅ Computed Node {results_received}/{NUM_NODES}")
                    
    monitor_task = cocotb.start_soon(result_monitor())

    for i, deg in enumerate(degrees):
        last_flag = 1 if i == (NUM_NODES - 1) else 0
        payload = (last_flag << 63) | (i << 47) | (deg << 39) | 0x10000000
        packet = (0x0 << 76) | (0x0 << 72) | (0x01 << 64) | payload

        while str(dut.w_in_ready.value) == '0':
            await RisingEdge(dut.clk)

        dut.w_in_data.value = packet
        dut.w_in_valid.value = 1
        await RisingEdge(dut.clk)
        
        # THE FIX: Drop valid to 0 AND force a 1-cycle gap so the simulator registers it!
        dut.w_in_valid.value = 0
        await RisingEdge(dut.clk) 

    await monitor_task

    actual_reads = mem.actual_dram_reads
    cache_hits = total_feature_fetches - actual_reads
    hit_rate = (cache_hits / total_feature_fetches) * 100 if total_feature_fetches > 0 else 0
    throughput_gbs = ((NUM_NODES * 32) / 1e9) / (cycle_count * 10e-9)

    dut._log.info("=====================================================")
    dut._log.info("🏆 GRAPHCORE-X BENCHMARK RESULTS")
    dut._log.info("=====================================================")
    dut._log.info(f"Total Execution Latency : {cycle_count} Clock Cycles")
    dut._log.info(f"L1 Cache Hit Rate       : {hit_rate:.2f}% ({cache_hits} misses avoided!)")
    dut._log.info(f"Effective Throughput    : {throughput_gbs:.4f} GB/s")
    dut._log.info("=====================================================")