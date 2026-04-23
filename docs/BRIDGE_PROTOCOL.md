# PyHDL-IF 2-way Bridge Protocol

The Python RL agent and the UVM testbench exchange two flavours of messages:

* **Request** &mdash; Python &rarr; UVM stimulus descriptor
* **Response** &mdash; UVM &rarr; Python observation descriptor

Both messages are packed into a fixed 64-bit vector and sent through one of
PyHDL-IF's TLM FIFOs. FIFO sizing is configurable (default 16 entries). The
two FIFOs are instantiated in `tb_rl/bridge/alu_bridge_if.sv`:

| SV interface    | Direction        | PyHDL-IF module         |
|-----------------|------------------|-------------------------|
| `alu_req_if`    | Python &rarr; HDL | `tlm_hvl2hdl_fifo`     |
| `alu_rsp_if`    | HDL &rarr; Python | `tlm_hdl2hvl_fifo`     |

Both FIFOs carry a valid/ready handshake on the HDL side and blocking
get/put semantics on the Python side, so neither messages can be lost.

## Request format (64 bits, LSB-first)

| Bits    | Field           | Meaning |
|---------|-----------------|---------|
| `0`     | `reset`         | drive the DUT reset line |
| `1`     | `c_in`          | ALU carry-in |
| `5:2`   | `op_code`       | 0=ADD 1=SUB 2=MUL 3=DIV 4=AND 5=XOR |
| `13:6`  | `A`             | 8-bit operand A |
| `21:14` | `B`             | 8-bit operand B |
| `22`    | `end_of_episode`| Python requests the sequence to stop |
| `31:23` | reserved        | must be 0 |
| `63:32` | `gen_id`        | round-trip correlation id |

Python helpers live in `rl/bridge_env.py::pack_request`.

## Response format (64 bits, LSB-first)

| Bits    | Field     | Meaning |
|---------|-----------|---------|
| `15:0`  | `Result`  | 16-bit DUT result |
| `16`    | `C_out`   | carry-out |
| `17`    | `Z_flag`  | zero flag |
| `18`    | `mismatch`| 1 if scoreboard detected a mismatch |
| `19`    | `reset`   | was this a reset transaction |
| `27:20` | `cov_pct` | live functional-coverage percentage (0..100) |
| `31:28` | `op_code` | echoed op |
| `63:32` | `gen_id`  | echoed correlation id |

Python helper: `rl/bridge_env.py::unpack_response`.

## Handshake and timeout rules

### HDL side (`alu_rl_bridge`)

* `req_timeout_cycles` (default 2000): the bridge polls `alu_req_if.has_data()`
  every clock; if no request arrives in the budget it logs a UVM warning,
  injects a randomised `alu_seq_item` and keeps the episode alive.
* `rsp_timeout_cycles` (default 2000): if `alu_rsp_if.can_put()` is false
  for longer than this budget, the response is dropped with a warning and
  the bridge continues.
* `end_of_episode` request causes the bridge to drop its run-phase
  objection cleanly.

### Python side (`AluBridgeEnv`)

* `timeout_s` (default 2.0 s): each `step()` waits at most this long for a
  response. On timeout, the step returns with `truncated=True` and
  `info["timeout"]=True` and the agent can choose to reset the episode.

### Queue sizing

Both TLM FIFOs are parameterised to `Tdepth=16`. The Python side wraps the
PyHDL-IF handles in thread-safe `queue.Queue` objects (`uvm_bridge.py`)
which provide back-pressure between the RL rollout loop and the PyHDL-IF
event thread.

## Interoperability notes

The HDL side uses **only** the SystemVerilog artefacts shipped with
PyHDL-IF (`$PYHDLIF_SHARE/dpi/pyhdl_if.sv` and the three
`pyhdl_if_*_fifo.sv` source files). No DPI-C adapter is required or
created. The Makefile passes `-load $(PYHDLIF_LIB)` to VCS so that
PyHDL-IF's VPI entry point is registered at elaboration time and the
`UvmBridge` Python class becomes visible to SV.
