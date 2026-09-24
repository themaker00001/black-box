cmake_minimum_required(VERSION 3.16)
project(blackbox_sysmon CXX)

if(NOT APPLE)
    message(FATAL_ERROR "blackbox_sysmon reads macOS mach/BSD system APIs directly and only builds on macOS")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

add_executable(sysmon
    src/main.cpp
    src/metrics.cpp
)
target_include_directories(sysmon PRIVATE src)
target_compile_options(sysmon PRIVATE -Wall -Wextra)
