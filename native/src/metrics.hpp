#pragma once

#include <cstdint>
#include <vector>

namespace blackbox {

struct CpuSample {
    double overall_percent = 0.0;
    std::vector<double> per_core_percent;
};

struct MemorySample {
    double percent = 0.0;
    double used_mb = 0.0;
    double available_mb = 0.0;
};

struct NetSample {
    double sent_bytes_per_sec = 0.0;
    double recv_bytes_per_sec = 0.0;
};

// Stateful samplers: each holds the previous raw counters so consecutive
// sample() calls return a delta-based rate/percentage, matching what the
// Python psutil-based collector already reports. The first call after
// construction has nothing to diff against, so it returns zeros — callers
// should prime with one throwaway sample before using real readings.
class CpuSampler {
public:
    CpuSample sample();

private:
    struct CoreTicks {
        uint64_t user = 0, system = 0, idle = 0, nice = 0;
    };
    std::vector<CoreTicks> previous_;
    bool primed_ = false;
};

class NetSampler {
public:
    NetSample sample(double interval_seconds);

private:
    uint64_t previous_in_bytes_ = 0;
    uint64_t previous_out_bytes_ = 0;
    bool primed_ = false;
};

MemorySample sample_memory();
double sample_swap_percent();

}  // namespace blackbox
