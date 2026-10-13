#!/usr/bin/env python3
"""Compile the actual PS5 PAL language-default additions with synthetic state.
Requires Python 3, a POSIX host and a C++17 compiler with sanitizers.
SPDX-License-Identifier: MIT
"""
import argparse
import os
import pathlib
import shlex
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
    args = parser.parse_args()
    patch = (pathlib.Path(__file__).resolve().parents[1] / "patches/switchwaker.patch").read_text()
    marker = "diff --git a/native/src/pc/runtime/pc_harness.cpp"
    start = patch.index(marker)
    end = patch.index("diff --git ", start + len(marker))
    additions = "\n".join(line[1:] for line in patch[start:end].splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    helper_start = additions.index("void ps5Default(")
    helper_end = additions.index("\n}", helper_start) + 2
    language_start = additions.index("void ps5Defaults() {")
    language_end = additions.index('    ps5Default("COS_RUN_DIR"', language_start)
    cpp = r'''
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <unistd.h>
static int writef(int, const char*, ...) { return 0; }
static void ps5FindDisc() {}
''' + additions[helper_start:helper_end] + additions[language_start:language_end] + r'''
}
int main() {
    unsetenv("COS_GAME_LANGUAGE"); ps5Defaults();
#if VERSION == 3
    if (!getenv("COS_GAME_LANGUAGE") || strcmp(getenv("COS_GAME_LANGUAGE"), "de")) return 1;
    std::cout << "PASS: fresh European build chooses German\n";
#else
    if (getenv("COS_GAME_LANGUAGE")) return 1;
    std::cout << "PASS: USA build keeps its existing language default\n";
#endif
    setenv("COS_GAME_LANGUAGE", "en", 1); ps5Defaults();
    if (strcmp(getenv("COS_GAME_LANGUAGE"), "en")) return 1;
    std::cout << "PASS: existing English player preference is preserved\n";
    setenv("COS_GAME_LANGUAGE", "fr", 1); ps5Defaults();
    if (strcmp(getenv("COS_GAME_LANGUAGE"), "fr")) return 1;
    std::cout << "PASS: existing French player preference is preserved\n";
}
'''
    with tempfile.TemporaryDirectory(prefix="windwaker-pal-defaults-") as temporary:
        directory = pathlib.Path(temporary)
        source = directory / "defaults.cpp"
        source.write_text(cpp)
        for version in (2, 3):
            binary = directory / f"defaults-{version}"
            subprocess.run(shlex.split(args.cxx) + ["-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", f"-DVERSION={version}", str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
