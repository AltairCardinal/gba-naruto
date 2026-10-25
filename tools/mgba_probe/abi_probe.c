/* Print the ABI fingerprint of the structures the host shares with libmgba.
 *
 * The values are pasted into tools/mgba_probe/host_main.c as compile-time
 * assertions, so a mismatch between the host and the library becomes a build
 * error instead of a crash at runtime.
 *
 * Build it with the same preprocessor defines as the library.  The easiest
 * way is to reuse the generated mgba.vcxproj's define list; this file is only
 * a helper, the host itself never includes it.
 */
#include <mgba/core/core.h>
#include <mgba/debugger/debugger.h>
#include <mgba/internal/debugger/cli-debugger.h>

#include <stddef.h>
#include <stdio.h>

int main(void) {
	printf("sizeof(struct mCore) = %zu\n", sizeof(struct mCore));
	printf("offsetof(mCore, init) = %zu\n", offsetof(struct mCore, init));
	printf("offsetof(mCore, loadROM) = %zu\n", offsetof(struct mCore, loadROM));
	printf("offsetof(mCore, stateSize) = %zu\n", offsetof(struct mCore, stateSize));
	printf("offsetof(mCore, runFrame) = %zu\n", offsetof(struct mCore, runFrame));
	printf("offsetof(mCore, setKeys) = %zu\n", offsetof(struct mCore, setKeys));
	printf("offsetof(mCore, clearKeys) = %zu\n", offsetof(struct mCore, clearKeys));
	printf("offsetof(mCore, busRead8) = %zu\n", offsetof(struct mCore, busRead8));
	printf("sizeof(struct CLIDebugger) = %zu\n", sizeof(struct CLIDebugger));
	printf("offsetof(CLIDebugger, system) = %zu\n", offsetof(struct CLIDebugger, system));
	printf("offsetof(CLIDebugger, backend) = %zu\n", offsetof(struct CLIDebugger, backend));
	printf("sizeof(struct CLIDebuggerSystem) = %zu\n", sizeof(struct CLIDebuggerSystem));
	printf("sizeof(struct CLIDebuggerBackend) = %zu\n", sizeof(struct CLIDebuggerBackend));
	return 0;
}
