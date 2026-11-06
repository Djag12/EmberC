# EmberC

**Original project date (from memory):** November 2025  
**Published on GitHub:** November 6, 2026

EmberC compiles a small integer subset of C to WebAssembly. Its Python frontend parses functions and control flow, and the linker emits DWARF line information so a debugger can pause on the original C line. A separate driver uses Clang and LLD for broader C17 programs.

## Run the example

From Linux or Ubuntu in WSL with Python 3.10 or newer and Node.js 24, run `make demo`. The example calls a C function in WebAssembly and prints 127. Follow the source from `emberc/examples/functions.c` into `emberc/frontend.py`.

## Check an incremental build

Run `make test` with GCC, Clang, LLD and the LLVM DWARF tools installed. If your LLVM tools have versioned names, set CLANG, WASM_LD and LLVM_DWARFDUMP to the corresponding executables.

The incremental test builds 100 source files, edits a single expression, and runs the result. In the saved run, EmberC reused 99 units and rebuilt the edited unit in a 35.9 ms build. A separate suite compared 2,000 generated integer programs against native Clang. See `results/emberc_custom_project.json` for the build timings and breakpoint result.

Developed with AI assistance.
