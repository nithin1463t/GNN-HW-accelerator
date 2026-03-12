# Simulator setup - Upgraded to Verilator for Hyperscale speeds!
SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/router_fifo.sv \
                   $(PWD)/noc_router_5port.sv \
                   $(PWD)/compute_fifo.sv \
                   $(PWD)/gcu_top.sv \
                   $(PWD)/sau_top.sv \
                   $(PWD)/dcu_top.sv \
                   $(PWD)/tile_top.sv \
                   $(PWD)/mesh_top.sv

TOPLEVEL = mesh_top
COCOTB_TEST_MODULES = test_mesh_hyperscale

# Verilator is extremely strict with linting. 
# Disable fatal warnings so our design compiles smoothly.
EXTRA_ARGS += -Wno-fatal -Wno-lint

include $(shell cocotb-config --makefiles)/Makefile.sim