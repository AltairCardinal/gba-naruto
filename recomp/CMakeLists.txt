cmake_minimum_required(VERSION 3.20)
project(NarutoKonohaSenkiRecomp C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ─────────────────────────────────────────────────────────────────────
# 火影忍者：木叶战记 静态重编译移植版
#
# 接线方式对齐框架参考游戏 MinishCapRecomp：
#   1. add_subdirectory 引框架（提供 gbarecomp_runtime / _debug / _gba / _armv4t）
#   2. 生成的机器码重编译产物编成 gbarecomp_game 静态库
#   3. main.cpp + 生成库 + 框架库链成游戏可执行文件
#
# 目录约定：
#   recomp/gbarecomp/     框架源码（git submodule: mstan/gbarecomp）
#   recomp/generated/     gbarecomp 生成的 C++（不入库，可用 GENERATED_DIR 指向别处）
#   recomp/src/           游戏专属代码
#   recomp/symbols/       符号导入 TSV
#
# 生成产物：
#   .\gbarecomp.exe build --rom <rom> --output generated --force
#   或  .\gba_recompile.exe --rom <rom> --config config/naruto_konoha_senki.toml --out generated
# ─────────────────────────────────────────────────────────────────────

set(GBARECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/gbarecomp"
    CACHE PATH "gbarecomp 平台核心路径（git submodule）")
set(GENERATED_DIR "${CMAKE_CURRENT_SOURCE_DIR}/generated"
    CACHE PATH "重编译生成的 C++ 所在目录")

if(NOT EXISTS "${GBARECOMP_ROOT}/CMakeLists.txt")
    message(FATAL_ERROR
        "GBARECOMP_ROOT 未指向 gbarecomp 检出：${GBARECOMP_ROOT}\n"
        "  git clone --recurse-submodules https://github.com/mstan/gbarecomp.git gbarecomp\n"
        "  或用 -DGBARECOMP_ROOT=<path> 指定。")
endif()

if(NOT EXISTS "${GENERATED_DIR}/dispatch_table.cpp")
    message(FATAL_ERROR
        "生成目录为空：${GENERATED_DIR}\n"
        "  先运行：gbarecomp build --rom <rom> --output \"${GENERATED_DIR}\" --force")
endif()

add_subdirectory("${GBARECOMP_ROOT}" gbarecomp_build EXCLUDE_FROM_ALL)

# ── MSVC 兼容 shim ───────────────────────────────────────────────────
# 框架 main 分支的 bios_hle.cpp 用了 GCC 的 __builtin_clz（MSVC 没有）。
# 全框架仅此一处，故 force-include 一个 shim 即可。
if(MSVC)
    target_compile_options(gbarecomp_runtime PRIVATE
        "/FI${CMAKE_CURRENT_SOURCE_DIR}/compat/msvc_builtin_clz.h")
endif()

# ── 机器码重编译产物 ─────────────────────────────────────────────────
file(GLOB NARUTO_GENERATED_SOURCES CONFIGURE_DEPENDS
    "${GENERATED_DIR}/recompiled_*.cpp")
list(LENGTH NARUTO_GENERATED_SOURCES _naruto_shard_count)
message(STATUS "NarutoKonohaSenkiRecomp: ${_naruto_shard_count} recompiled shard(s) from ${GENERATED_DIR}")

add_library(gbarecomp_game STATIC
    ${NARUTO_GENERATED_SOURCES}
    "${GENERATED_DIR}/dispatch_table.cpp")
if(EXISTS "${GENERATED_DIR}/symbol_map.cpp")
    target_sources(gbarecomp_game PRIVATE "${GENERATED_DIR}/symbol_map.cpp")
endif()
target_include_directories(gbarecomp_game PRIVATE
    "${GENERATED_DIR}"
    "${GBARECOMP_ROOT}/src/armv4t")
set_target_properties(gbarecomp_game PROPERTIES
    CXX_STANDARD 20
    CXX_STANDARD_REQUIRED YES)
# 分片每个 11-14 MB，MSVC 默认的 COFF 段数上限会溢出（C1128），
# 必须开 /bigobj 大对象格式。
if(MSVC)
    target_compile_options(gbarecomp_game PRIVATE /bigobj)
endif()

# ── 游戏可执行文件 ───────────────────────────────────────────────────
#
# ⚠ 这里**只能编 src/main.cpp**，不要再把 ${NARUTO_GENERATED_SOURCES} 加进来。
#   分片已经在上面的 gbarecomp_game 静态库里编过一次；
#   同时编两遍会让构建时间**整整翻倍**（实测 42 s → 90 s+），
#   而且两套编译单元的链接顺序不同，容易产生诡异的重复符号。
#   exe 只需要链接 gbarecomp_game —— dispatch table 引用了全部函数，
#   链接器会把 8 个分片的对象全部拉进来。
add_executable(NarutoKonohaSenkiRecomp src/main.cpp)
target_include_directories(NarutoKonohaSenkiRecomp PRIVATE
    "${GBARECOMP_ROOT}/src/armv4t"
    "${GBARECOMP_ROOT}/src/gba"
    "${GBARECOMP_ROOT}/src/runtime"
    "${GBARECOMP_ROOT}/src/debug"
    "${GENERATED_DIR}"
    src)
target_link_libraries(NarutoKonohaSenkiRecomp PRIVATE
    gbarecomp_game
    gbarecomp_runtime
    gbarecomp_debug
    gbarecomp_gba
    gbarecomp_armv4t)
target_compile_definitions(NarutoKonohaSenkiRecomp PRIVATE
    GBARECOMP_DEFAULT_DEBUG_PORT=19842
    GBARECOMP_WINDOW_TITLE="NarutoKonohaSenkiRecomp"
    GBARECOMP_DEFAULT_GAME_CONFIG="game.toml")
set_target_properties(NarutoKonohaSenkiRecomp PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")

# 游戏栈帧很大（递归 + 大数组），MSVC 默认 1 MB 栈不够
if(MSVC)
    target_link_options(NarutoKonohaSenkiRecomp PRIVATE /STACK:16777216)
elseif(MINGW OR WIN32 OR CMAKE_SYSTEM_NAME STREQUAL "MSYS")
    target_link_options(NarutoKonohaSenkiRecomp PRIVATE -Wl,--stack,16777216)
endif()

# ── 导出自愈层需要的宿主符号 ───────────────────────────────────────────
#
# Stage-2 自愈（tcc overlay）把「被桥接的函数」现场编译成 DLL 加载进本进程。
# overlay 的函数体与静态语料逐字节相同，其中带函数内续执行点（alias entry）
# 的函数会引用宿主的 `g_runtime_resume_pc`。
#
# 该符号定义在框架的 src/armv4t/runtime_arm.cpp（extern "C"），
# 静态语料能编译是因为 runtime_arm.h 声明了它；
# 但 overlay 的 shim（src/runtime/overlay_runtime_arm.h）**没有**这份声明
# → tcc 报 "'g_runtime_resume_pc' undeclared"。
#
# build.ps1 会给暂存进 overlay_toolchain/include 的 shim 补上这份声明；
# 声明有了还不够 —— overlay DLL 要在**加载时**从宿主解析该符号，
# 而 exe 默认没有导出表 → 必须显式导出。
if(MSVC)
    target_link_options(NarutoKonohaSenkiRecomp PRIVATE /EXPORT:g_runtime_resume_pc)
endif()
