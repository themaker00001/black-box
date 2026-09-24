# blackbox-sysmon

A small, dependency-free C++ service that samples CPU, memory, swap, and
network throughput directly from macOS's mach host-statistics and BSD socket
APIs — no `psutil`, no shelling out to `top`/`netstat`. It's a standalone CLI
tool: once per interval it prints one line of JSON to stdout and exits only
when killed.

```
./sysmon [interval_seconds]   # default 1.0
```

Example output:

```json
{"cpu_percent":11.88,"cpu_per_core":[33.33,28.00,...],"memory_percent":65.46,"memory_used_mb":16087.73,"memory_available_mb":8488.27,"swap_percent":88.44,"net_sent_bytes_per_sec":1024.00,"net_recv_bytes_per_sec":1024.00}
```

## Why this exists

The Python collectors (`app/capture/*.py`) use `psutil`, which is more than
enough for this project's needs. This exists alongside it as an optional,
lower-overhead alternative — and because reading mach APIs directly in C++ is
just a satisfying thing to build. `app/capture/system.py`'s
`NativeSystemMetricsCollector` spawns this binary and reads its stdout line
by line, the same way it would pipe any other CLI tool; the JSON shape lines
up with `SystemMetricsPayload` so nothing downstream needs to know which
collector produced it.

**Scope**: CPU (overall + per-core), memory, swap, and network throughput.
Disk I/O and GPU utilization are *not* read here — those stay on the psutil
path. `use_native_binary: false` (the default in `config.yaml`) uses psutil
for everything; setting it to `true` swaps in this binary for CPU/memory/
swap/network only.

## Building

Requires Xcode Command Line Tools (`xcode-select --install`) and CMake.

```bash
cd native
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

This produces `native/build/sysmon`, which `config.yaml`'s
`capture.system.native_binary_path` points at by default.

## Testing

```bash
../venv/bin/python -m pytest ../tests/test_native_sysmon.py
```

The pytest suite skips itself (rather than failing) when `native/build/sysmon`
hasn't been built yet — it's a real integration test against the compiled
binary, not a mock.
