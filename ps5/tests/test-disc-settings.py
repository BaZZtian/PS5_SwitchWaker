#!/usr/bin/env python3
"""Test actual PS5 settings persistence and disc-menu registration on a POSIX host.

Supply a core checkout with ps5/patches/switchwaker.patch applied. Only synthetic
disc headers are used. No SDK or console is required. SPDX-License-Identifier: MIT
"""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

MAPPING = r'''
#include <algorithm>
#include <cerrno>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <map>
#include <set>
#include <string>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
inline std::string testPath(const char* path) { return std::string(getenv("TEST_ROOT")) + path; }
inline bool denied(const char* path) {
    return getenv("TEST_DENY") && std::string(path) == "/data/windwaker/settings.ini";
}
inline FILE* testFopen(const char* path, const char* mode) {
    if (denied(path) || (getenv("TEST_WRITE_FAIL") && std::strchr(mode, 'w'))) {
        errno = EACCES; return nullptr;
    }
    return ::fopen(testPath(path).c_str(), mode);
}
inline int testAccess(const char* path, int mode) {
    if (denied(path)) { errno = EACCES; return -1; }
    return ::access(testPath(path).c_str(), mode);
}
inline int testMkdir(const char* path, mode_t mode) { return ::mkdir(testPath(path).c_str(), mode); }
inline int testRename(const char* from, const char* to) {
    const auto source = testPath(from), target = testPath(to);
    return ::rename(source.c_str(), target.c_str());
}
inline int testRemove(const char* path) { return ::remove(testPath(path).c_str()); }
inline DIR* testOpendir(const char* path) { return ::opendir(testPath(path).c_str()); }
#define fopen testFopen
#define access testAccess
#define mkdir testMkdir
#define rename testRename
#define remove testRemove
#define opendir testOpendir
'''

INTERNAL = r'''
#pragma once
namespace pc {
inline void writef(int, const char*, ...) {}
inline bool executablePath(char*, unsigned long) { return false; }
inline bool menuBuiltinSetting(const char* key) {
    return std::strcmp(key, "COS_GAME_LANGUAGE") == 0;
}
}
'''

HARNESS = r'''
#include "pc/pc_settings.h"
#include "test_pc_internal.h"
#include <iostream>
using pc::writef;
static void ps5Default(const char* key, const char* value) {
    if (!getenv(key)) setenv(key, value, 0);
}
__DISC_HELPERS__
__DISC_MENU__
static void require(bool condition, const char* description) {
    if (!condition) { std::cerr << "FAIL: " << description << '\n'; std::exit(1); }
    std::cout << "PASS: " << description << '\n';
}
int main(int argc, char** argv) {
    require(argc == 2, "scenario supplied");
    const std::string scenario = argv[1];
    pc_settings_load_early();
    ps5RegisterDiscSetting();
    const auto* setting = pc_settings_at(0);
    require(setting && std::string(setting->key) == "COS_DISC_PATH" &&
            std::string(setting->labelEn) == "Disc image" &&
            (setting->flags & PC_SETTING_RESTART) && setting->choiceCount >= 1,
            "disc option is registered with restart semantics and persistent choices");
    if (scenario == "fresh") {
        require(std::string(pc_settings_path()) == "/data/windwaker/settings.ini",
                "default settings path is outside the replaceable app");
        require(std::string(pc_settings_get("COS_DISC_PATH")) == "auto",
                "fresh install defaults to automatic discovery");
        require(setting->choiceCount == 2 &&
                std::string(setting->choices[1].value) == "/mnt/usb6/disc.iso",
                "menu offers the matching external image");
        require(pc_settings_set("COS_DISC_PATH", setting->choices[1].value) == 0,
                "menu selection is accepted");
        require(pc_settings_restart_pending("COS_DISC_PATH"), "selection requires restart");
        require(access(pc_settings_path(), R_OK) == 0, "selection is written persistently");
    } else if (scenario == "restored") {
        require(std::string(pc_settings_get("COS_DISC_PATH")) == "/mnt/usb6/disc.iso",
                "selection survives replacement of the app directory");
        require(!pc_settings_restart_pending("COS_DISC_PATH"), "restored selection is active at boot");
        ps5FindDisc();
        require(getenv("COS_DISC") && std::string(getenv("COS_DISC")) == "/mnt/usb6/disc.iso",
                "restored menu preference selects the external disc");
    } else if (scenario == "legacy" || scenario == "write-failure") {
        require(std::string(pc_settings_get("COS_DISC_PATH")) == "/chosen/disc.iso",
                "legacy selection is imported");
        require(std::string(pc_settings_get("COS_GAME_LANGUAGE")) == "fr",
                "legacy language is preserved");
        require(access("/app0/user/settings.ini", R_OK) == 0, "legacy source remains intact");
        require((access(pc_settings_path(), R_OK) == 0) == (scenario == "legacy"),
                "migration writes a new file only when writable");
    } else if (scenario == "existing") {
        require(std::string(pc_settings_get("COS_DISC_PATH")) == "/mnt/usb6/disc.iso",
                "existing persistent settings take precedence over legacy values");
    } else if (scenario == "override") {
        require(std::string(pc_settings_path()) == "/custom/settings.ini" &&
                std::string(pc_settings_get("COS_DISC_PATH")) == "/chosen/disc.iso",
                "explicit COS_SETTINGS path remains supported");
        require(access("/data/windwaker/settings.ini", F_OK) != 0,
                "explicit settings path does not trigger default migration");
    } else if (scenario == "denied") {
        require(std::string(pc_settings_get("COS_DISC_PATH")) == "auto",
                "an access error is not treated as a missing persistent file");
    } else if (scenario == "startup") {
        require(pc_settings_set_startup("COS_DISC_PATH", "/mnt/usb6/disc.iso") == 0,
                "startup choice is saved");
        require(!pc_settings_restart_pending("COS_DISC_PATH"), "startup choice becomes the active baseline");
        require(pc_settings_set("COS_DISC_PATH", "auto") == 0 && pc_settings_restart_pending("COS_DISC_PATH"),
                "later in-game choices still require restart");
    } else {
        require(false, "known scenario");
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
    args = parser.parse_args()
    runtime = (args.core / "native/src/pc/runtime/pc_harness.cpp").read_text()
    start = runtime.index("// Select only the build's revision-0 disc")
    end = runtime.index("} // namespace", start)
    menu_start = runtime.index("void ps5RegisterDiscSetting()")
    menu_end = runtime.index("// Validate the current engine", menu_start)
    settings = (args.core / "native/src/pc/features/pc_settings.cpp").read_text()
    settings = settings.replace('#include "pc_internal.h"', '#include "test_pc_internal.h"')
    with tempfile.TemporaryDirectory(prefix="windwaker-settings-") as temporary:
        work = Path(temporary)
        (work / "mapped.h").write_text(MAPPING + '\n#include "disc_region.h"\n')
        (work / "test_pc_internal.h").write_text(INTERNAL)
        (work / "settings.cpp").write_text(settings)
        (work / "harness.cpp").write_text(HARNESS.replace("__DISC_HELPERS__", runtime[start:end])
                                           .replace("__DISC_MENU__", runtime[menu_start:menu_end]))
        binary = work / "settings-test"
        subprocess.run(shlex.split(args.cxx) + ["-I", str(Path(__file__).resolve().parents[1] / "src"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-D__PROSPERO__", '-DCOS_GAME_ID_STR="GZLP01"',
            "-include", str(work / "mapped.h"), "-I", str(args.core / "native/include"),
            "-I", str(work), str(work / "settings.cpp"), str(work / "harness.cpp"),
            "-o", str(binary)], check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("COS_")}
        for scenario in ("fresh", "restored", "legacy", "existing", "override", "denied", "write-failure", "startup"):
            root = work / ("fresh" if scenario == "restored" else scenario)
            root.mkdir(exist_ok=True)
            def text_file(path, content):
                target = root / path.lstrip("/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            if scenario != "restored":
                image = root / "mnt/usb6/disc.iso"
                image.parent.mkdir(parents=True)
                header = bytearray(32)
                header[:6] = b"GZLP01"
                header[28:32] = bytes.fromhex("c2339f3d")
                image.write_bytes(header)
            if scenario in ("legacy", "existing", "override", "denied", "write-failure"):
                text_file("/app0/user/settings.ini", "COS_DISC_PATH=/chosen/disc.iso\nCOS_GAME_LANGUAGE=fr\n")
            if scenario == "existing":
                text_file("/data/windwaker/settings.ini", "COS_DISC_PATH=/mnt/usb6/disc.iso\n")
            if scenario == "override":
                text_file("/custom/settings.ini", "COS_DISC_PATH=/chosen/disc.iso\n")
            if scenario == "restored":
                shutil.rmtree(root / "app0", ignore_errors=True)
                (root / "app0").mkdir()
            scenario_env = dict(env, TEST_ROOT=str(root))
            if scenario == "override":
                scenario_env["COS_SETTINGS"] = "/custom/settings.ini"
            if scenario == "denied":
                scenario_env["TEST_DENY"] = "1"
            if scenario == "write-failure":
                scenario_env["TEST_WRITE_FAIL"] = "1"
            subprocess.run([str(binary), scenario], env=scenario_env, check=True)


if __name__ == "__main__":
    main()
