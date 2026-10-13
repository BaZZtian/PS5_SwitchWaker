#!/usr/bin/env python3
"""Run the actual PS5 startup browser against synthetic storage and graphics/input stubs.

No SDK, console or disc data is needed. Requires an already patched core and
a POSIX C++17 compiler with AddressSanitizer/UndefinedBehaviorSanitizer.
SPDX-License-Identifier: MIT
"""
import argparse
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

INTERNAL = r'''
#pragma once
#include <stdexcept>
namespace pc {
struct TestConfig { const char* disc = nullptr; const char* smoke = nullptr; const char* milestone = nullptr; };
extern TestConfig gConfig;
extern int testChecks, testPulses;
extern int checkDisc();
extern void exitDisc();
inline void writef(int, const char*, ...) {}
inline bool executablePath(char*, unsigned long) { return false; }
inline bool menuBuiltinSetting(const char* key) { return !std::strcmp(key, "COS_GAME_LANGUAGE"); }
inline void watchdogPulse() { ++testPulses; }
enum { PC_EXIT_REACHED = 0 };
inline void pc_exit(int) { throw std::runtime_error("unexpected process exit"); }
}
'''
SDL = r'''
#pragma once
#include <cstdlib>
typedef int SDL_JoystickID;
struct SDL_Gamepad {};
enum { SDL_SCANCODE_RETURN = 2, SDL_SCANCODE_ESCAPE, SDL_SCANCODE_UP, SDL_SCANCODE_DOWN };
enum { SDL_GAMEPAD_AXIS_LEFTY, SDL_GAMEPAD_BUTTON_DPAD_UP, SDL_GAMEPAD_BUTTON_DPAD_DOWN,
       SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_BUTTON_EAST };
extern bool testKeys[64];
inline bool SDL_GamepadConnected(SDL_Gamepad*) { return true; }
inline void SDL_CloseGamepad(SDL_Gamepad*) {}
inline SDL_JoystickID* SDL_GetGamepads(int* count) { *count = 0; return nullptr; }
inline SDL_Gamepad* SDL_GetGamepadFromID(int) { return nullptr; }
inline SDL_Gamepad* SDL_OpenGamepad(int) { return nullptr; }
inline int SDL_GetGamepadAxis(SDL_Gamepad*, int) { return 0; }
inline bool SDL_GetGamepadButton(SDL_Gamepad*, int) { return false; }
inline void SDL_free(void* ptr) { free(ptr); }
inline const bool* SDL_GetKeyboardState(int* count) { *count = 64; return testKeys; }
inline void SDL_Delay(int) {}
'''
IMGUI = r'''
#pragma once
#include <string>
struct ImVec2 { float x, y; ImVec2(float a=0, float b=0) : x(a), y(b) {} };
enum { ImGuiWindowFlags_NoDecoration = 1, ImGuiWindowFlags_NoSavedSettings = 2 };
namespace ImGui {
struct IO { ImVec2 DisplaySize{1280, 720}; };
extern int testDraws, testWarnings;
inline IO& GetIO() { static IO io; return io; }
inline void SetNextWindowPos(ImVec2) {}
inline void SetNextWindowSize(ImVec2) {}
inline bool Begin(const char*, bool*, int) { ++testDraws; return true; }
inline void End() {}
inline void SetWindowFontScale(float) {}
inline void TextUnformatted(const char*) {}
inline void TextWrapped(const char*, const char* value) {
    if (std::string(value).find("could not be saved") != std::string::npos) ++testWarnings;
}
inline void TextWrapped(const char*, const char*, const char*) {}
inline void Separator() {}
inline void BeginChild(const char*, ImVec2) {}
inline void EndChild() {}
inline float GetTextLineHeightWithSpacing() { return 20; }
inline void PushID(int) {}
inline void PopID() {}
inline bool Selectable(const char*, bool) { return false; }
inline void SetScrollHereY() {}
}
'''
AURORA = r'''
#pragma once
enum { AURORA_NONE, AURORA_EXIT };
struct AuroraEvent { int type; };
const AuroraEvent* aurora_update();
bool aurora_begin_frame();
void aurora_end_frame();
'''
HARNESS = r'''
#include "pc_internal.h"
#include "pc/pc_settings.h"
#include "SDL3/SDL.h"
#include "imgui.h"
#include "aurora/aurora.h"
#include <fstream>
#include <iostream>
bool testKeys[64] = {};
int testFrame = -1;
std::string scenario;
namespace ImGui { int testDraws = 0, testWarnings = 0; }
namespace pc {
TestConfig gConfig;
int testChecks = 0, testPulses = 0;
void ps5Default(const char* key, const char* value) { if (!getenv(key)) setenv(key, value, 0); }
__HELPERS__
__REGISTRY__
void ps5DiscStartupScreen();
int checkDisc() {
    ++testChecks;
    if (ImGui::testDraws == 0) throw std::runtime_error("disc checked before startup screen");
    return gConfig.disc && ps5CompatibleDisc(gConfig.disc) ? 0 : 14;
}
void exitDisc() { throw std::runtime_error("missing disc exited the title"); }
}
void require(bool value, const char* why) {
    if (!value) { std::cerr << "FAIL: " << why << '\n'; std::exit(1); }
    std::cout << "PASS " << scenario << ": " << why << '\n';
}
void image(const char* path, const char* id = COS_GAME_ID_STR) {
    unsigned char header[32] = {};
    memcpy(header, id, 6);
    header[28] = 0xC2; header[29] = 0x33; header[30] = 0x9F; header[31] = 0x3D;
    std::ofstream out(testPath(path), std::ios::binary);
    out.write((const char*)header, sizeof(header));
}
const AuroraEvent* aurora_update() {
    ++testFrame;
    std::fill(testKeys, testKeys + 64, false);
    if (testFrame > 15) throw std::runtime_error("startup browser failed to accept selection");
    if (scenario == "missing") {
        if (testFrame == 6) image("/mnt/usb6/late.iso");
        testKeys[SDL_SCANCODE_RETURN] = testFrame == 1 || testFrame == 3 || testFrame == 7 || testFrame == 9;
    } else if (scenario == "wrong-region") {
        if (testFrame == 6) image("/mnt/usb6/image.iso");
        testKeys[SDL_SCANCODE_RETURN] = testFrame == 1 || testFrame == 3 || testFrame == 5 || testFrame == 7;
    } else {
        testKeys[SDL_SCANCODE_RETURN] = testFrame == 1 || testFrame == 3;
    }
    static const AuroraEvent event{AURORA_NONE};
    return &event;
}
bool aurora_begin_frame() { return true; }
void aurora_end_frame() {}
int main(int argc, char** argv) {
    require(argc == 2, "scenario supplied");
    scenario = argv[1];
    if (scenario == "wrong-region") image("/mnt/usb6/image.iso", !strcmp(COS_GAME_ID_STR,"GZLP01") ? "GZLE01" : "GZLP01");
    else if (scenario != "missing") image("/mnt/usb6/image.iso");
    pc_settings_load_early();
    pc::ps5RegisterDiscSetting();
    pc::ps5DiscStartupScreen();
    require(ImGui::testDraws > 0 && pc::testChecks > 0, "screen is drawn before any disc check");
    require(pc::gConfig.disc && pc::ps5CompatibleDisc(pc::gConfig.disc), "a compatible selection launches in this session");
    require(pc::testPulses == testFrame + 1, "browser keeps the startup watchdog alive");
    require(!pc_settings_restart_pending("COS_DISC_PATH"), "startup choice is active without another restart");
    const auto* desc = pc_settings_at(0);
    bool offered = false;
    for (int i = 0; i < desc->choiceCount; ++i) offered |= !strcmp(desc->choices[i].value, pc::gConfig.disc);
    require(offered, "browsed image becomes an in-game menu choice");
    if (scenario == "missing") require(testFrame >= 9, "no ISO waits for browsing, rescan and later insertion");
    if (scenario == "wrong-region") require(testFrame >= 7 && pc::testChecks == 1, "wrong region is rejected in the browser without exiting");
    if (scenario == "write-failure") {
        require(ImGui::testWarnings > 0 && testFrame == 3, "save failure needs explicit confirmation to start unsaved");
        require(access(pc_settings_path(), F_OK) != 0, "failed save does not claim a settings file");
    } else require(access(pc_settings_path(), R_OK) == 0, "startup path is persisted outside the app folder");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("settings_fixtures", Path(__file__).with_name("test-disc-settings.py"))
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    native = args.core / "native"
    runtime = (native / "src/pc/runtime/pc_harness.cpp").read_text()
    start = runtime.index("// Select only the build's revision-0 disc")
    end = runtime.index("} // namespace", start)
    registry_start = runtime.index("std::vector<std::string> ps5AvailableDiscs()")
    registry_end = runtime.index("// The console's defaults", registry_start)
    main_source = (native / "src/pc/runtime/pc_main.cpp").read_text()
    assert main_source.index("ps5DiscStartupScreen();", main_source.index("const AuroraInfo info = aurora_initialize")) < main_source.index("aurora_dvd_open(gConfig.disc)")
    assert "#if !defined(__PROSPERO__)\n    if (checkDisc()" in runtime
    with tempfile.TemporaryDirectory(prefix="windwaker-startup-") as temporary:
        work = Path(temporary)
        for folder in ("SDL3", "aurora", "pc"):
            (work / folder).mkdir()
        mapping = fixtures.MAPPING + r'''
inline int testStat(const char* path, struct stat* result) { return ::stat(testPath(path).c_str(), result); }
#define stat(path, result) testStat(path, result)
'''
        for file, content in {"mapped.h": mapping, "pc_internal.h": INTERNAL, "SDL3/SDL.h": SDL,
                              "imgui.h": IMGUI, "aurora/aurora.h": AURORA,
                              "aurora/event.h": '#include "aurora.h"\n',
                              "pc/pc_game_id.h": '#define PC_GAME_REGION_EN "Europe"\n',
                              "settings.cpp": (native / "src/pc/features/pc_settings.cpp").read_text(),
                              "ui.cpp": (native / "src/pc/runtime/pc_ps5_disc_ui.cpp").read_text(),
                              "harness.cpp": HARNESS.replace("__HELPERS__", runtime[start:end])
                                                     .replace("__REGISTRY__", runtime[registry_start:registry_end])}.items():
            (work / file).write_text(content)
        for region in ("GZLE01", "GZLP01"):
            binary = work / region
            subprocess.run(shlex.split(args.cxx) + ["-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", "-D__PROSPERO__", f'-DCOS_GAME_ID_STR="{region}"',
                "-include", str(work / "mapped.h"), "-I", str(work), "-I", str(native / "include"),
                "-I", str(native / "src/pc/runtime"), str(work / "settings.cpp"), str(work / "ui.cpp"),
                str(work / "harness.cpp"), "-o", str(binary)], check=True)
            for scenario in ("valid", "missing", "wrong-region", "stale", "write-failure"):
                root = work / (region + "-" + scenario)
                (root / "mnt/usb6").mkdir(parents=True)
                (root / "app0").mkdir()
                if scenario == "stale":
                    config = root / "data/windwaker/settings.ini"
                    config.parent.mkdir(parents=True)
                    config.write_text("COS_DISC_PATH=/mnt/usb2/missing.iso\n")
                env = {k: v for k, v in os.environ.items() if not k.startswith("COS_")}
                env["TEST_ROOT"] = str(root)
                if scenario == "write-failure":
                    env["TEST_WRITE_FAIL"] = "1"
                subprocess.run([str(binary), scenario], env=env, check=True)


if __name__ == "__main__":
    main()
