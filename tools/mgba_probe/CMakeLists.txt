# Headless mGBA host, built as a sub-project of mGBA itself.
#
# Building the host *inside* mGBA's own CMake project guarantees that the
# preprocessor defines and the object selection match the static library
# exactly.  `struct mCore` embeds `#ifdef USE_DEBUGGERS` members, so a
# mismatch silently changes the ABI.
#
#   cmake -S tools/mgba_probe -B build/mgba-probe/cmake -DCMAKE_BUILD_TYPE=Release
#   cmake --build build/mgba-probe/cmake --config Release
#
# tools/mgba_probe/build.py offers a faster path that reuses an existing
# mGBA static library; see README.md.
cmake_minimum_required(VERSION 3.10)
project(mgba_probe C)

# host_main.c uses _Static_assert for the ABI fingerprint.
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

if(NOT MGBA_SRC)
  if(DEFINED ENV{KONOHA_MGBA_SRC})
    set(MGBA_SRC "$ENV{KONOHA_MGBA_SRC}")
  else()
    set(MGBA_SRC "D:/Shell/toolchain/mgba-0.10.5")
  endif()
endif()
set(MGBA_SRC "${MGBA_SRC}" CACHE PATH "mGBA source tree")

# The same option set build.py uses.
set(LIBMGBA_ONLY ON CACHE BOOL "" FORCE)
set(BUILD_QT OFF CACHE BOOL "" FORCE)
set(BUILD_SDL OFF CACHE BOOL "" FORCE)
set(BUILD_LIBRETRO OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(BUILD_STATIC ON CACHE BOOL "" FORCE)
set(M_CORE_GB OFF CACHE BOOL "" FORCE)
set(M_CORE_GBA ON CACHE BOOL "" FORCE)
set(USE_DEBUGGERS ON CACHE BOOL "" FORCE)
set(USE_EDITLINE OFF CACHE BOOL "" FORCE)
set(USE_GDB_STUB OFF CACHE BOOL "" FORCE)
set(USE_LUA OFF CACHE BOOL "" FORCE)
set(ENABLE_SCRIPTING OFF CACHE BOOL "" FORCE)
set(USE_FFMPEG OFF CACHE BOOL "" FORCE)
set(USE_PNG OFF CACHE BOOL "" FORCE)
set(USE_ZLIB OFF CACHE BOOL "" FORCE)
set(USE_LZMA OFF CACHE BOOL "" FORCE)
set(USE_SQLITE3 OFF CACHE BOOL "" FORCE)
set(USE_ELF OFF CACHE BOOL "" FORCE)
set(USE_LIBZIP OFF CACHE BOOL "" FORCE)
set(USE_MINIZIP OFF CACHE BOOL "" FORCE)
set(USE_DISCORD_RPC OFF CACHE BOOL "" FORCE)

add_subdirectory("${MGBA_SRC}" "${CMAKE_BINARY_DIR}/mgba")

add_executable(mgba-probe host_main.c)

# Reuse the library's own compile definitions (USE_DEBUGGERS, M_CORE_GBA,
# BUILD_STATIC, HAVE_STRDUP, ...).  The directory-level definitions mGBA
# adds with add_definitions() do not leak into this directory, so the
# platform ones are repeated here.
get_target_property(MGBA_COMPILE_DEFINITIONS mgba COMPILE_DEFINITIONS)
message(STATUS "mgba COMPILE_DEFINITIONS = ${MGBA_COMPILE_DEFINITIONS}")
if(MGBA_COMPILE_DEFINITIONS)
  target_compile_definitions(mgba-probe PRIVATE ${MGBA_COMPILE_DEFINITIONS})
endif()
if(M_CORE_GBA)
  target_compile_definitions(mgba-probe PRIVATE M_CORE_GBA)
endif()
if(USE_DEBUGGERS)
  target_compile_definitions(mgba-probe PRIVATE USE_DEBUGGERS)
endif()
if(WIN32)
  target_compile_definitions(mgba-probe PRIVATE
    WIN32 _WINDOWS _CRT_SECURE_NO_WARNINGS
    _WIN32_WINNT=0x0600 NOMINMAX WIN32_LEAN_AND_MEAN _UNICODE UNICODE)
endif()

target_include_directories(mgba-probe PRIVATE "${MGBA_SRC}/src")
target_link_libraries(mgba-probe PRIVATE mgba)
