#!/usr/bin/env python3
"""Exercise the PS5 disc-discovery helpers with synthetic headers, not game data.

By default, compile the exact helper additions from the PS5 source patch. Use
--source to check an already patched pc_harness.cpp instead. Requires a POSIX
host, Python 3 and a C++17 compiler with Address/UndefinedBehaviorSanitizer.
SPDX-License-Identifier: MIT
"""
import argparse
import os
import pathlib
import shlex
import subprocess
import tempfile


def helpers_from(text, patch):
    marker = "// Select only the build's revision-0 disc"
    prefix = "+" if patch else ""
    start = text.index(prefix + marker)
    end = text.index(prefix + "} // namespace", start)
    lines = text[start:end].splitlines()
    if patch:
        if not all(line.startswith("+") for line in lines):
            raise ValueError("discovery helpers must be a contiguous patch addition")
        lines = [line[1:] for line in lines]
    return "\n".join(lines)


HARNESS = r'''
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <strings.h>
#include <unistd.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
namespace fs = std::filesystem;
static std::string root;
static std::string mapped(const char* path) { return root + path; }
static DIR* mappedOpenDir(const char* path) { return ::opendir(mapped(path).c_str()); }
static FILE* mappedOpenFile(const char* path, const char* mode) { return ::fopen(mapped(path).c_str(), mode); }
static int mappedAccess(const char* path, int mode) { return ::access(mapped(path).c_str(), mode); }
static void ps5Default(const char* name, const char* value) {
    if (::getenv(name) == nullptr) ::setenv(name, value, 0);
}
static const char* pc_settings_get(const char* key) {
    const char* value = ::getenv(key);
    return value == nullptr ? "" : value;
}
static void writef(int, const char*, ...) {}
#define opendir mappedOpenDir
#define fopen mappedOpenFile
#define access mappedAccess
__DISC_HELPERS__
#undef opendir
#undef fopen
#undef access
static void require(bool condition, const char* description) {
    if (!condition) { std::cerr << "FAIL: " << description << '\n'; std::exit(1); }
    std::cout << "PASS " << COS_GAME_ID_STR << ": " << description << '\n';
}
static void image(const std::string& path, const char* id = COS_GAME_ID_STR,
                  unsigned revision = 0, bool compressed = false) {
    fs::create_directories(fs::path(root + path).parent_path());
    std::vector<unsigned char> bytes(compressed ? 0x8020 : 0x20, 0);
    size_t offset = compressed ? 0x8000 : 0;
    if (compressed) { std::memcpy(bytes.data(), "CISO", 4); bytes[8] = 1; }
    std::memcpy(bytes.data() + offset, id, 6);
    bytes[offset + 7] = revision;
    bytes[offset + 0x1C] = 0xC2; bytes[offset + 0x1D] = 0x33;
    bytes[offset + 0x1E] = 0x9F; bytes[offset + 0x1F] = 0x3D;
    std::ofstream out(root + path, std::ios::binary);
    out.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
}
int main(int argc, char** argv) {
    require(argc == 2, "test filesystem path supplied");
    root = argv[1]; fs::create_directories(root);
    const char* otherRegion = std::strcmp(COS_GAME_ID_STR, "GZLP01") == 0 ? "GZLE01" : "GZLP01";
    ::unsetenv("COS_DISC"); ps5FindDisc();
    require(::getenv("COS_DISC") == nullptr, "missing drives leave no invented disc path");
    ::setenv("COS_DISC", "", 1); ps5FindDisc();
    require(::getenv("COS_DISC") == nullptr, "empty saved path does not suppress discovery");
    image("/mnt/usb0/Homebrew/WindWaker-Discs/wrong.iso", otherRegion);
    image("/mnt/usb0/Homebrew/WindWaker-Discs/revision1.iso", COS_GAME_ID_STR, 1);
    image("/app0/local.iso");
    image("/mnt/usb2/Homebrew/WindWaker-Discs/matching.ISO");
    ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/mnt/usb2/Homebrew/WindWaker-Discs/matching.ISO",
            "dedicated USB2 folder wins over app0; other region and revision 1 skipped");
    fs::create_directories(root + "/mnt/usb7/Homebrew");
    fs::rename(root + "/mnt/usb2/Homebrew/WindWaker-Discs", root + "/mnt/usb7/Homebrew/WindWaker-Discs");
    ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/mnt/usb7/Homebrew/WindWaker-Discs/matching.ISO",
            "stale saved path recovered after USB renumbering");
    image("/chosen/explicit.iso"); ::setenv("COS_DISC", "/chosen/explicit.iso", 1); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/chosen/explicit.iso", "existing explicit choice preserved");
    image("/samples/compressed.ciso", COS_GAME_ID_STR, 0, true);
    require(ps5DiscMatches("/samples/compressed.ciso"), "supported CISO header accepted");
    require(!ps5DiscMatches("/mnt/usb0/Homebrew/WindWaker-Discs/wrong.iso"), "other-region header rejected");
    require(!ps5DiscMatches("/mnt/usb0/Homebrew/WindWaker-Discs/revision1.iso"), "revision 1 rejected");
    { std::ofstream(root + "/samples/truncated.iso") << COS_GAME_ID_STR; }
    require(!ps5DiscMatches("/samples/truncated.iso"), "short image header rejected");
    image("/samples/bad-magic.iso");
    { std::fstream out(root + "/samples/bad-magic.iso", std::ios::in | std::ios::out | std::ios::binary);
      out.seekp(0x1C); out.put(0); }
    require(!ps5DiscMatches("/samples/bad-magic.iso"), "invalid GameCube magic rejected");
    image("/samples/absent-first-block.ciso", COS_GAME_ID_STR, 0, true);
    { std::fstream out(root + "/samples/absent-first-block.ciso", std::ios::in | std::ios::out | std::ios::binary);
      out.seekp(8); out.put(0); }
    require(!ps5DiscMatches("/samples/absent-first-block.ciso"), "CISO without a first data block rejected");
    fs::rename(root + "/mnt/usb7/Homebrew/WindWaker-Discs", root + "/archived");
    ::unsetenv("COS_DISC"); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/app0/local.iso", "legacy app0 fallback retained");
    fs::rename(root + "/app0/local.iso", root + "/archived/local.iso");
    image("/mnt/usb6/root.gcm"); ::unsetenv("COS_DISC"); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/mnt/usb6/root.gcm", "USB root fallback beyond USB1");
    image("/custom/location/preferred.iso");
    ::setenv("COS_DISC_PATH", "/custom/location/preferred.iso", 1);
    ::unsetenv("COS_DISC"); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/custom/location/preferred.iso",
            "configured absolute image wins over automatic search");
    ::setenv("COS_DISC_PATH", "/missing/selection.iso", 1);
    ::unsetenv("COS_DISC"); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/mnt/usb6/root.gcm",
            "unavailable configured image falls back without changing the preference");
    require(std::string(::getenv("COS_DISC_PATH")) == "/missing/selection.iso",
            "automatic fallback preserves the user's configured image");
    ::setenv("COS_DISC_DIR", "/custom/location", 1);
    ::setenv("COS_DISC_PATH", "auto", 1);
    ::unsetenv("COS_DISC"); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/custom/location/preferred.iso",
            "configured search directory precedes default USB roots");
    ::setenv("COS_DISC_PATH", "/mnt/usb0/Homebrew/WindWaker-Discs/wrong.iso", 1);
    ::unsetenv("COS_DISC"); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/custom/location/preferred.iso",
            "configured wrong-region image is skipped");
    ::setenv("COS_DISC_PATH", "/custom/location/preferred.iso", 1);
    const auto menuPaths = ps5DiscPaths();
    require(std::count(menuPaths.begin(), menuPaths.end(), "/custom/location/preferred.iso") == 1,
            "options contain configured images once with stable path values");
    require(std::find(menuPaths.begin(), menuPaths.end(),
                     "/mnt/usb0/Homebrew/WindWaker-Discs/wrong.iso") == menuPaths.end(),
            "options do not offer incompatible images");
    ::setenv("COS_DISC_DIR", "relative/folder", 1);
    ::setenv("COS_DISC_PATH", "relative/image.iso", 1);
    ::unsetenv("COS_DISC"); ps5FindDisc();
    require(std::string(::getenv("COS_DISC")) == "/mnt/usb6/root.gcm",
            "relative configuration does not replace an absolute discovered path");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path, help="patched pc_harness.cpp; default: extract from source patch")
    parser.add_argument("--cxx", default=os.environ.get("CXX", "clang++"), help="C++17 compiler command")
    args = parser.parse_args()
    source = args.source or pathlib.Path(__file__).resolve().parents[1] / "patches/switchwaker.patch"
    helpers = helpers_from(source.read_text(), args.source is None)
    with tempfile.TemporaryDirectory(prefix="windwaker-disc-tests-") as temporary:
        directory = pathlib.Path(temporary)
        cpp = directory / "discovery.cpp"
        cpp.write_text(HARNESS.replace("__DISC_HELPERS__", helpers))
        for game_id in ("GZLE01", "GZLP01"):
            binary = directory / game_id
            subprocess.run(shlex.split(args.cxx) + ["-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", f'-DCOS_GAME_ID_STR="{game_id}"', str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary), str(directory / (game_id + "-fixtures"))], check=True)


if __name__ == "__main__":
    main()
