#include "metrics.hpp"

#include <ifaddrs.h>
#include <mach/mach.h>
#include <mach/mach_host.h>
#include <mach/processor_info.h>
#include <mach/vm_statistics.h>
#include <net/if.h>
#include <sys/sysctl.h>
#include <sys/types.h>

namespace blackbox {

CpuSample CpuSampler::sample() {
    CpuSample result;

    natural_t cpu_count = 0;
    processor_info_array_t info_array = nullptr;
    mach_msg_type_number_t info_count = 0;

    kern_return_t status = host_processor_info(mach_host_self(), PROCESSOR_CPU_LOAD_INFO, &cpu_count,
                                                &info_array, &info_count);
    if (status != KERN_SUCCESS) {
        return result;  // leave zeroed; caller treats this as "unavailable this tick"
    }

    auto* loads = reinterpret_cast<processor_cpu_load_info_data_t*>(info_array);

    std::vector<CoreTicks> current(cpu_count);
    for (natural_t i = 0; i < cpu_count; ++i) {
        current[i].user = loads[i].cpu_ticks[CPU_STATE_USER];
        current[i].system = loads[i].cpu_ticks[CPU_STATE_SYSTEM];
        current[i].idle = loads[i].cpu_ticks[CPU_STATE_IDLE];
        current[i].nice = loads[i].cpu_ticks[CPU_STATE_NICE];
    }
    vm_deallocate(mach_task_self(), reinterpret_cast<vm_address_t>(info_array),
                  info_count * sizeof(integer_t));

    if (primed_ && previous_.size() == current.size()) {
        uint64_t total_busy = 0, total_ticks = 0;
        result.per_core_percent.reserve(current.size());
        for (size_t i = 0; i < current.size(); ++i) {
            const auto& prev = previous_[i];
            const auto& cur = current[i];
            uint64_t busy = (cur.user - prev.user) + (cur.system - prev.system) + (cur.nice - prev.nice);
            uint64_t idle = cur.idle - prev.idle;
            uint64_t total = busy + idle;
            double pct = total > 0 ? (100.0 * static_cast<double>(busy) / static_cast<double>(total)) : 0.0;
            result.per_core_percent.push_back(pct);
            total_busy += busy;
            total_ticks += total;
        }
        result.overall_percent = total_ticks > 0 ? (100.0 * static_cast<double>(total_busy) /
                                                      static_cast<double>(total_ticks))
                                                   : 0.0;
    }

    previous_ = std::move(current);
    primed_ = true;
    return result;
}

MemorySample sample_memory() {
    MemorySample result;

    vm_size_t page_size = 0;
    host_page_size(mach_host_self(), &page_size);

    vm_statistics64_data_t vm_stat;
    mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
    kern_return_t status =
        host_statistics64(mach_host_self(), HOST_VM_INFO64, reinterpret_cast<host_info64_t>(&vm_stat), &count);
    if (status != KERN_SUCCESS) {
        return result;
    }

    uint64_t total_bytes = 0;
    size_t total_size = sizeof(total_bytes);
    sysctlbyname("hw.memsize", &total_bytes, &total_size, nullptr, 0);

    // "Available" mirrors psutil's macOS convention: free pages plus inactive
    // pages the kernel would reclaim under pressure, not just literally-free.
    uint64_t available_bytes = static_cast<uint64_t>(vm_stat.free_count + vm_stat.inactive_count) * page_size;
    uint64_t used_bytes = total_bytes > available_bytes ? total_bytes - available_bytes : 0;

    result.used_mb = static_cast<double>(used_bytes) / (1024.0 * 1024.0);
    result.available_mb = static_cast<double>(available_bytes) / (1024.0 * 1024.0);
    result.percent = total_bytes > 0 ? (100.0 * static_cast<double>(used_bytes) / static_cast<double>(total_bytes))
                                      : 0.0;
    return result;
}

double sample_swap_percent() {
    struct xsw_usage swap {};
    size_t size = sizeof(swap);
    if (sysctlbyname("vm.swapusage", &swap, &size, nullptr, 0) != 0) {
        return 0.0;
    }
    if (swap.xsu_total == 0) {
        return 0.0;
    }
    return 100.0 * static_cast<double>(swap.xsu_used) / static_cast<double>(swap.xsu_total);
}

namespace {
// Sums ibytes/obytes across every non-loopback interface's AF_LINK entry —
// this is the same counter `netstat -ib` reads, no IOKit needed.
void total_interface_bytes(uint64_t& in_bytes, uint64_t& out_bytes) {
    in_bytes = 0;
    out_bytes = 0;

    struct ifaddrs* addrs = nullptr;
    if (getifaddrs(&addrs) != 0) {
        return;
    }
    for (struct ifaddrs* cursor = addrs; cursor != nullptr; cursor = cursor->ifa_next) {
        if (cursor->ifa_addr == nullptr || cursor->ifa_addr->sa_family != AF_LINK) {
            continue;
        }
        if (cursor->ifa_flags & IFF_LOOPBACK) {
            continue;
        }
        auto* data = reinterpret_cast<struct if_data*>(cursor->ifa_data);
        if (data == nullptr) {
            continue;
        }
        in_bytes += data->ifi_ibytes;
        out_bytes += data->ifi_obytes;
    }
    freeifaddrs(addrs);
}
}  // namespace

NetSample NetSampler::sample(double interval_seconds) {
    NetSample result;
    uint64_t in_bytes = 0, out_bytes = 0;
    total_interface_bytes(in_bytes, out_bytes);

    if (primed_ && interval_seconds > 0) {
        // Counters can reset (interface reconnect) between samples; clamp
        // instead of reporting a garbage negative rate.
        if (in_bytes >= previous_in_bytes_) {
            result.recv_bytes_per_sec = static_cast<double>(in_bytes - previous_in_bytes_) / interval_seconds;
        }
        if (out_bytes >= previous_out_bytes_) {
            result.sent_bytes_per_sec = static_cast<double>(out_bytes - previous_out_bytes_) / interval_seconds;
        }
    }

    previous_in_bytes_ = in_bytes;
    previous_out_bytes_ = out_bytes;
    primed_ = true;
    return result;
}

}  // namespace blackbox
