#!/usr/bin/env bash
# Build the native hot-kernels shared library (needs gcc or clang).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
CC="${CC:-$(command -v gcc || command -v clang)}"
[ -z "$CC" ] && { echo "No C compiler found. Install one (see request) then re-run."; exit 1; }
"$CC" -O3 -shared -fPIC -o "$HERE/libfastops.so" "$HERE/fastops.c" -lm
echo "Built $HERE/libfastops.so with $CC"
