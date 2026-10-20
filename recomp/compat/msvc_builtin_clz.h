// compat/msvc_builtin_clz.h - MSVC compatibility shim (ASCII ONLY!)
//
// WHY ASCII ONLY:
//   This file is force-included (/FI) at the top of EVERY translation unit.
//   MSVC reads sources in the system codepage (936/GBK on this machine), so
//   any non-ASCII byte sequence in this header can be mis-decoded and
//   corrupt the preprocessor state (observed: the "#if defined(_MSC_VER)"
//   line stopped being a directive -> "C2059 syntax error: if").
//   Keep this file pure ASCII. Put Chinese prose in ordinary .cpp files.
//
// WHAT IT FIXES:
//   The framework's main branch uses GCC/LLVM's __builtin_clz in
//   src/runtime/bios_hle.cpp:
//       bios_hle.cpp(52,43): error C3861: "__builtin_clz": identifier not found
//
//   Measured behaviour of MSVC 19.44 (VS 2022 BuildTools):
//     * C mode   (.c)   : intrin.h DOES provide __builtin_clz (clang compat)
//     * C++ mode (.cpp) : intrin.h does NOT provide it
//   bios_hle.cpp is a .cpp, so it fails.
//
// WHY A MACRO, NOT A SAME-NAMED FUNCTION:
//   Defining "static int __builtin_clz(...)" collides with the declaration
//   that intrin.h provides in C mode. The redeclaration makes the compiler
//   treat the function body as a file-scope compound statement, producing a
//   pile of misleading errors (C2059 "if", C2365 "_BitScanReverse
//   redefinition", ...). A macro has no such problem.
//
// WHY NO inline AND NO static_cast:
//   /FI inserts this header into .c files too, and MSVC compiles .c as
//   C89 by default, where neither "inline" nor "static_cast" exists.
//
// USAGE (in the parent project, on the gbarecomp_runtime target):
//   if(MSVC)
//       target_compile_options(gbarecomp_runtime PRIVATE
//           "/FI${CMAKE_CURRENT_SOURCE_DIR}/compat/msvc_builtin_clz.h")
//   endif()

#pragma once

#if defined(_MSC_VER)

#include <intrin.h>

#pragma warning(push)
#pragma warning(disable : 4505) /* unreferenced static function */

static unsigned int gbarecomp_msvc_clz32(unsigned int v) {
    unsigned long index = 0;
    if (v == 0u) {
        return 32u;
    }
    _BitScanReverse(&index, v);
    return 31u - (unsigned int)index;
}

#define __builtin_clz(x) gbarecomp_msvc_clz32((unsigned int)(x))

#pragma warning(pop)

#endif /* _MSC_VER */
