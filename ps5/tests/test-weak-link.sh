#!/usr/bin/env bash
# Verify optional weak-symbol handling without any SDK or console files.
# SPDX-License-Identifier: MIT
set -euo pipefail
cc=${CC:-clang}
lld=${LD_LLD:-ld.lld}
readelf=${LLVM_READELF:-llvm-readelf}
version=$("$lld" --version)
if [[ ! $version =~ LLD[[:space:]]+([0-9]+)\. ]] || (( BASH_REMATCH[1] < 21 )); then
    echo 'LLD 21 or newer is required' >&2
    exit 2
fi
test_root=$(mktemp -d "${TMPDIR:-/tmp}/windwaker-weak-link.XXXXXXXX")
trap 'rm -rf -- "$test_root"' EXIT
cat > "$test_root/provider.c" <<'C'
void provided(void) {}
C
cat > "$test_root/reference.c" <<'C'
extern void absent(void) __attribute__((weak));
extern void provided(void) __attribute__((weak));
void (*entries[2])(void) = { absent, provided };
C
cat > "$test_root/required.c" <<'C'
extern void required(void);
void (*entry)(void) = required;
C
for source in provider reference required; do
    "$cc" -fPIC -c "$test_root/$source.c" -o "$test_root/$source.o"
done
"$lld" -shared "$test_root/provider.o" -soname provider.so -o "$test_root/provider.so"
"$lld" -pie -z nodynamic-undefined-weak -e 0 "$test_root/reference.o" \
    "$test_root/provider.so" -o "$test_root/references.elf"
"$readelf" --dyn-symbols "$test_root/references.elf" > "$test_root/dynamic.txt"
! grep -q 'absent' "$test_root/dynamic.txt"
grep -q 'provided' "$test_root/dynamic.txt"
if "$lld" -pie -z nodynamic-undefined-weak -e 0 "$test_root/required.o" \
    "$test_root/provider.so" -o "$test_root/required.elf" > "$test_root/required.log" 2>&1; then
    echo 'FAIL: missing required function was accepted' >&2
    exit 1
fi
grep -q 'undefined symbol: required' "$test_root/required.log"
printf 'PASS: missing optional function stays NULL; provided function remains imported; missing required function is rejected.\n'
