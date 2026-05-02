// ============================================================================
//  AId-VO — VCS file list for the ALU UVM testbench
//  Usage: vcs -f filelist.f ...
// ============================================================================

// Compile options
-full64
-sverilog
+acc
-timescale=1ns/1ps
-ntb_opts uvm-1.2

// Include directories
+incdir+Testbench
+incdir+DUT

// DUT source
DUT/ALU_DUT.sv
DUT/ALU_interface.sv

// Testbench package (pulls in all TB components via `include)
Testbench/ALU_pkg.sv

// Top-level module
Testbench/ALU_Top.sv
