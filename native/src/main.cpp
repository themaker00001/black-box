// blackbox-sysmon: a small always-on macOS system-metrics sampler.
//
// Talks to nothing but stdout: once per interval it prints one line of JSON
// with CPU/memory/swap/network numbers, gathered directly via mach host
// statistics and getifaddrs (no psutil, no subprocess shell-outs). The
// Python side (app/capture/system.py's NativeSystemMetricsCollector) just
// spawns this and reads lines — same Unix-pipe pattern as any other CLI
// tool, so it's independently runnable and testable:
//
//   ./sysmon 1.0
//
// prints a fresh sample every second until killed.

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>

#include "metrics.hpp"

namespace {

void print_json_line(const blackbox::CpuSample& cpu, const blackbox::MemorySample& mem, double swap_percent,
                      const blackbox::NetSample& net) {
    std::printf("{\"cpu_percent\":%.2f,\"cpu_per_core\":[", cpu.overall_percent);
    for (size_t i = 0; i < cpu.per_core_percent.size(); ++i) {
        std::printf("%s%.2f", i == 0 ? "" : ",", cpu.per_core_percent[i]);
    }
    std::printf(
        "],\"memory_percent\":%.2f,\"memory_used_mb\":%.2f,\"memory_available_mb\":%.2f,"
        "\"swap_percent\":%.2f,\"net_sent_bytes_per_sec\":%.2f,\"net_recv_bytes_per_sec\":%.2f}\n",
        mem.percent, mem.used_mb, mem.available_mb, swap_percent, net.sent_bytes_per_sec, net.recv_bytes_per_sec);
    std::fflush(stdout);
}

}  // namespace

int main(int argc, char** argv) {
    double interval_seconds = 1.0;
    if (argc > 1) {
        try {
            interval_seconds = std::stod(argv[1]);
        } catch (const std::exception&) {
            std::cerr << "usage: sysmon [interval_seconds]\n";
            return 1;
        }
    }
    if (interval_seconds <= 0) {
        std::cerr << "interval_seconds must be > 0\n";
        return 1;
    }

    blackbox::CpuSampler cpu_sampler;
    blackbox::NetSampler net_sampler;
    // Prime both samplers: their first sample() has no prior reading to diff
    // against, so it's thrown away rather than printed as a bogus all-zero line.
    cpu_sampler.sample();
    net_sampler.sample(interval_seconds);

    while (true) {
        std::this_thread::sleep_for(std::chrono::duration<double>(interval_seconds));
        auto cpu = cpu_sampler.sample();
        auto mem = blackbox::sample_memory();
        auto swap_percent = blackbox::sample_swap_percent();
        auto net = net_sampler.sample(interval_seconds);
        print_json_line(cpu, mem, swap_percent, net);
    }
}
