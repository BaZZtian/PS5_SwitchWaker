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
typedef unsigned long long Uint64;
extern int testFrame;
inline Uint64 SDL_GetTicks() { return testFrame < 0 ? 0 : testFrame * 1000; }
enum { SDL_SCANCODE_RETURN = 2, SDL_SCANCODE_ESCAPE, SDL_SCANCODE_UP, SDL_SCANCODE_DOWN,
       SDL_SCANCODE_PAGEUP, SDL_SCANCODE_PAGEDOWN, SDL_SCANCODE_H,
       SDL_SCANCODE_LEFT, SDL_SCANCODE_RIGHT };
enum { SDL_GAMEPAD_AXIS_LEFTY, SDL_GAMEPAD_AXIS_LEFTX, SDL_GAMEPAD_AXIS_RIGHTX, SDL_GAMEPAD_AXIS_RIGHTY,
       SDL_GAMEPAD_BUTTON_DPAD_UP, SDL_GAMEPAD_BUTTON_DPAD_DOWN,
       SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_BUTTON_EAST, SDL_GAMEPAD_BUTTON_LEFT_SHOULDER,
       SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER, SDL_GAMEPAD_BUTTON_WEST,
       SDL_GAMEPAD_BUTTON_DPAD_LEFT, SDL_GAMEPAD_BUTTON_DPAD_RIGHT };
extern bool testKeys[64];
extern bool testPadReady;
extern int testPadAxis;
extern float testMouseX;
inline bool SDL_GamepadConnected(SDL_Gamepad*) { return true; }
inline void SDL_CloseGamepad(SDL_Gamepad*) {}
inline SDL_JoystickID* SDL_GetGamepads(int* count) {
    *count = testPadReady ? 1 : 0;
    if (!testPadReady) return nullptr;
    auto* ids=(int*)malloc(sizeof(int)); *ids=1; return ids;
}
inline SDL_Gamepad* SDL_GetGamepadFromID(int) { static SDL_Gamepad pad; return &pad; }
inline SDL_Gamepad* SDL_OpenGamepad(int) { return nullptr; }
inline int SDL_GetGamepadAxis(SDL_Gamepad*, int axis) { return axis==SDL_GAMEPAD_AXIS_LEFTX ? testPadAxis : 0; }
inline bool SDL_GetGamepadButton(SDL_Gamepad*, int) { return false; }
inline void SDL_free(void* ptr) { free(ptr); }
inline const bool* SDL_GetKeyboardState(int* count) { *count = 64; return testKeys; }
inline void SDL_Delay(int) {}
inline unsigned SDL_GetMouseState(float* x, float* y) { *x=testMouseX; *y=0; return 0; }
'''
IMGUI = r'''
#pragma once
#include <string>
#include <vector>
struct ImVec2 { float x, y; ImVec2(float a=0, float b=0) : x(a), y(b) {} };
struct ImVec4 { float x,y,z,w; ImVec4(float a=0,float b=0,float c=0,float d=0):x(a),y(b),z(c),w(d){} };
struct ImFont { float FontSize=0; };
typedef unsigned long long ImTextureID;
struct ImFontConfig { float SizePixels=0; };
struct FontAtlas {
    ImFont fonts[4];
    std::vector<ImFont*> Fonts;
    ImFont* AddFontDefault(ImFontConfig* config=nullptr) {
        ImFont* font=&fonts[Fonts.size()]; font->FontSize=config ? config->SizePixels : 13.f;
        Fonts.push_back(font); return font;
    }
};
struct ImDrawList {
    void AddImage(ImTextureID,ImVec2,ImVec2,ImVec2,ImVec2) {}
    void AddRectFilledMultiColor(ImVec2,ImVec2,unsigned,unsigned,unsigned,unsigned) {}
    void AddRectFilled(ImVec2,ImVec2,unsigned,float) {}
    void AddCircleFilled(ImVec2,float,unsigned,int) {}
    void AddLine(ImVec2,ImVec2,unsigned,float) {}
    void AddConvexPolyFilled(const ImVec2*,int,unsigned) {}
    void AddTriangleFilled(ImVec2,ImVec2,ImVec2,unsigned) {}
    void AddText(ImFont*,float,ImVec2,unsigned,const char*,const char* = nullptr,float = 0) {}
};
#define IM_COL32(R,G,B,A) 0u
enum { ImGuiWindowFlags_NoDecoration = 1, ImGuiWindowFlags_NoSavedSettings = 2,
       ImGuiWindowFlags_NoBackground=4, ImGuiStyleVar_WindowPadding, ImGuiStyleVar_ItemSpacing,
       ImGuiCol_Text, ImGuiCol_Header, ImGuiCol_HeaderHovered, ImGuiCol_HeaderActive };
namespace ImGui {
struct IO { ImVec2 DisplaySize{1280, 720}; FontAtlas atlas; FontAtlas* Fonts=&atlas; ImFont* FontDefault=nullptr; };
extern int testDraws, testWarnings, testDefaultFolder, testSaveInfo;
inline IO& GetIO() { static IO io; return io; }
inline void SetNextWindowPos(ImVec2) {}
inline void SetNextWindowSize(ImVec2) {}
inline bool Begin(const char*, bool*, int) { ++testDraws; return true; }
inline void End() {}
inline ImDrawList* GetBackgroundDrawList() { static ImDrawList list; return &list; }
inline ImDrawList* GetWindowDrawList() { return GetBackgroundDrawList(); }
inline ImVec2 GetContentRegionAvail() { return {900,400}; }
inline ImVec2 GetItemRectMin() { return {}; }
inline ImVec2 CalcTextSize(const char*,const char*,bool,float) { return {800,35}; }
inline void PushFont(ImFont*) {}
inline void PopFont() {}
inline void PushStyleVar(int,ImVec2) {}
inline void PopStyleVar(int) {}
inline void PushStyleColor(int,ImVec4) {}
inline void PopStyleColor(int) {}
inline void SetWindowFontScale(float) {}
inline void TextUnformatted(const char*) {}
inline void TextWrapped(const char*, const char* value) {
    if (std::string(value).find("could not be saved") != std::string::npos) ++testWarnings;
    if (std::string(value) == "/data/homebrew/PPSA99309/") ++testDefaultFolder;
    if (std::string(value).find("/data/windwaker/user/") != std::string::npos) ++testSaveInfo;
}
inline void TextWrapped(const char*, const char*, const char*) {}
inline void TextWrapped(const char*, unsigned) {}
inline void Separator() {}
inline void BeginChild(const char*, ImVec2) {}
inline void EndChild() {}
inline float GetTextLineHeightWithSpacing() { return 20; }
inline void PushID(int) {}
inline void PopID() {}
inline bool Selectable(const char*, bool,int,ImVec2) { return false; }
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
#include "pc_ps5_disc_browser.h"
#include <fstream>
#include <iostream>
bool testKeys[64] = {};
bool testPadReady=false;
int testPadAxis=0;
float testMouseX=0;
int testFrame = -1;
std::string scenario;
namespace ImGui { int testDraws = 0, testWarnings = 0, testDefaultFolder = 0, testSaveInfo = 0; }
struct TestHandoff {};
static int testLoads=0;
extern "C" int ps5_load_disc_region(enum ps5_disc_region, const char*) {
    ++testLoads;
    if (scenario=="load-failure" && testLoads==1) return -123;
    throw TestHandoff{};
}
namespace pc {
TestConfig gConfig;
int testChecks = 0, testPulses = 0;
void ps5Default(const char* key, const char* value) { if (!getenv(key)) setenv(key, value, 0); }
__HELPERS__
__REGISTRY__
void ps5DiscStartupScreen();
int checkDisc() {
    ++testChecks;
    if (getenv("TEST_TRACE")) std::cerr << "check " << (gConfig.disc ? gConfig.disc : "null") << '\n';
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
    if (getenv("TEST_TRACE")) std::cerr << scenario << " frame " << testFrame << '\n';
    std::fill(testKeys, testKeys + 64, false);
    if (testFrame > 20) throw std::runtime_error("startup browser failed to accept selection");
    const bool saved = scenario == "remembered" || scenario == "renumbered" || scenario == "cancel-remembered" || scenario == "saved-help" || scenario.find("cancel-")==0;
    testPadReady = scenario == "cancel-held-stick";
    testPadAxis = testPadReady && testFrame < 3 ? 12000 : 0;
    testMouseX = scenario == "cancel-mouse" && testFrame >= 1 ? 50 : 0;
    if (!saved && testFrame <= 1) {
        testKeys[SDL_SCANCODE_RETURN] = testFrame == 1; // First setup opens storage information.
        static const AuroraEvent event{AURORA_NONE};
        return &event;
    }
    const int frame = testFrame - (saved ? 0 : 2);
    if (scenario == "missing") {
        if (frame == 6) image("/mnt/usb6/late.iso");
        testKeys[SDL_SCANCODE_DOWN] = frame == 2; // App folder is offered before mounted USB6.
        testKeys[SDL_SCANCODE_RETURN] = frame == 1 || frame == 3 || frame == 7 || frame == 9;
    } else if (scenario == "wrong-region") {
        if (frame == 6) image("/mnt/usb6/image.iso");
        testKeys[SDL_SCANCODE_DOWN] = frame == 2;
        testKeys[SDL_SCANCODE_RETURN] = frame == 1 || frame == 3 || frame == 5 || frame == 7;
    } else if (scenario == "remembered" || scenario == "renumbered") {
        // A valid saved choice launches without selecting it again.
    } else if (scenario == "cancel-horizontal" || scenario == "cancel-held-stick" || scenario == "cancel-mouse") {
        testKeys[SDL_SCANCODE_RIGHT] = scenario == "cancel-horizontal" && testFrame == 1;
        testKeys[SDL_SCANCODE_RETURN] = testFrame == 7;
    } else if (scenario == "cancel-remembered") {
        testKeys[SDL_SCANCODE_ESCAPE] = testFrame == 1;
        testKeys[SDL_SCANCODE_RETURN] = testFrame == 5;
    } else if (scenario == "saved-help") {
        testKeys[SDL_SCANCODE_H] = frame == 1;
        testKeys[SDL_SCANCODE_DOWN] = frame == 3 || frame == 5;
        testKeys[SDL_SCANCODE_RETURN] = frame == 7 || frame == 9;
    } else if (scenario == "ui-size") {
        testKeys[SDL_SCANCODE_PAGEUP] = frame == 1;
        testKeys[SDL_SCANCODE_RETURN] = frame == 3;
    } else {
        testKeys[SDL_SCANCODE_RETURN] = frame == 1 || frame == 3;
    }
    static const AuroraEvent event{AURORA_NONE};
    return &event;
}
bool aurora_begin_frame() { return true; }
void aurora_end_frame() {}
int main(int argc, char** argv) {
    require(argc == 2, "scenario supplied");
    scenario = argv[1];
    if (scenario == "wrong-region" || scenario == "cross-region" || scenario == "load-failure") image("/mnt/usb6/image.iso", !strcmp(COS_GAME_ID_STR,"GZLP01") ? "GZLE01" : "GZLP01");
    else if (scenario == "internal-only" || scenario == "internal-default") image("/app0/local.iso");
    else if (scenario != "missing") image("/mnt/usb6/image.iso");
    if (scenario == "internal-default") image("/mnt/usb6/image.iso");
    pc_settings_load_early();
    if (scenario == "existing-font") {
        ImFontConfig custom; custom.SizePixels=19;
        ImGui::GetIO().FontDefault=ImGui::GetIO().Fonts->AddFontDefault(&custom);
    }
    pc::ps5RegisterDiscSetting();
    if (getenv("TEST_TRACE")) {
        for (const auto& path : pc::ps5AvailableDiscs()) std::cerr << "available " << path << '\n';
        std::cerr << "preferred " << pc_settings_get("COS_DISC_PATH") << '\n';
    }
    try { pc::ps5DiscStartupScreen(); }
    catch (const TestHandoff&) {
        require(scenario=="cross-region" || scenario=="load-failure", "only a different ISO region requests handoff");
        require(pc::testChecks==0, "wrong regional engine is never initialized");
        require(!strcmp(pc_settings_get("COS_DISC_PATH"),"/mnt/usb6/image.iso"), "other-region choice is saved before handoff");
        require(access(pc_settings_path(),R_OK)==0, "other-region selection survives the process restart");
        require(testLoads==(scenario=="load-failure"?2:1), "failed handoff remains selectable and can be retried");
        return 0;
    }
    require(ImGui::GetIO().FontDefault && ImGui::GetIO().FontDefault->FontSize ==
        (scenario == "existing-font" ? 19.f : 13.f), "startup font does not replace the in-game/debug default font");
    require(ImGui::testDraws > 0 && pc::testChecks > 0, "screen is drawn before any disc check");
    require(pc::gConfig.disc && pc::ps5CompatibleDisc(pc::gConfig.disc), "a compatible selection launches in this session");
    require(pc::testPulses == testFrame + 1, "browser keeps the startup watchdog alive");
    require(!pc_settings_restart_pending("COS_DISC_PATH"), "startup choice is active without another restart");
    const auto* desc = pc_settings_at(0);
    bool offered = false;
    for (int i = 0; i < desc->choiceCount; ++i) offered |= !strcmp(desc->choices[i].value, pc::gConfig.disc);
    require(offered, "browsed image becomes an in-game menu choice");
    if (scenario == "missing") require(testFrame >= 11, "no ISO waits for browsing, rescan and later insertion");
    if (scenario == "wrong-region") require(testFrame >= 9 && pc::testChecks == 1, "wrong region is rejected in the browser without exiting");
    if (scenario == "remembered" || scenario == "renumbered") require(testFrame == 3, "saved choice starts automatically after countdown");
    if (scenario == "cancel-remembered") require(testFrame == 5, "input cancels automatic launch and keeps the browser open");
    if (scenario == "cancel-horizontal" || scenario == "cancel-held-stick" || scenario == "cancel-mouse")
        require(testFrame == 7, "horizontal, held-stick or mouse movement cancels automatic launch");
    if (scenario == "ui-size") require(!strcmp(pc_settings_get("COS_DISC_UI_SIZE"),"125"), "text size adjustment is persisted");
    if (scenario == "internal-only" || scenario == "internal-default") {
        require(!strcmp(pc::gConfig.disc,"/app0/local.iso"), "first setup selects internal default without needing USB2");
        require(ImGui::testDefaultFolder > 0, "first setup explains the physical internal default folder");
    }
    if (scenario == "internal-only") {
        pc::Ps5DiscBrowser roots(pc::ps5AvailableDiscs, pc::ps5CompatibleDisc);
        roots.detected = false; roots.refresh();
        require(roots.rows.front().path == "/app0", "internal app folder is the first readable root");
        for (const auto& row : roots.rows) require(row.path.find("/mnt/") != 0,
            "absent USB and expansion mounts are not offered");
    }
    if (scenario == "saved-help") require(testFrame == 9 && ImGui::testSaveInfo > 0,
        "storage help cancels saved autostart and explains persistent save location");
    if (scenario == "write-failure") {
        require(ImGui::testWarnings > 0 && testFrame == 5, "save failure needs explicit confirmation to start unsaved");
        require(access(pc_settings_path(), F_OK) != 0, "failed save does not claim a settings file");
    } else require(access(pc_settings_path(), R_OK) == 0, "startup path is persisted outside the app folder");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--multi-region", action="store_true")
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
        mapping = fixtures.MAPPING + '\n#include "disc_region.h"\n' + r'''
inline int testStat(const char* path, struct stat* result) { return ::stat(testPath(path).c_str(), result); }
#define stat(path, result) testStat(path, result)
'''
        for file, content in {"mapped.h": mapping, "pc_internal.h": INTERNAL, "SDL3/SDL.h": SDL,
                              "imgui.h": IMGUI, "aurora/aurora.h": AURORA,
                              "aurora/event.h": '#include "aurora.h"\n',
                              "aurora/imgui.h": '#include <imgui.h>\ninline ImTextureID aurora_imgui_add_texture(unsigned,unsigned,const void*) { return 1; }\n',
                              "pc/pc_game_id.h": '#define PC_GAME_REGION_EN "Europe"\n',
                              "settings.cpp": (native / "src/pc/features/pc_settings.cpp").read_text(),
                              "ui.cpp": (native / "src/pc/runtime/pc_ps5_disc_ui.cpp").read_text(),
                              "harness.cpp": HARNESS.replace("__HELPERS__", runtime[start:end])
                                                     .replace("__REGISTRY__", runtime[registry_start:registry_end])}.items():
            (work / file).write_text(content)
        for region in ("GZLE01", "GZLP01"):
            binary = work / region
            subprocess.run(shlex.split(args.cxx) + (["-DPS5_MULTI_REGION=1"] if args.multi_region else []) + ["-I", str(Path(__file__).resolve().parents[1] / "src"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", "-D__PROSPERO__", f'-DCOS_GAME_ID_STR="{region}"',
                "-include", str(work / "mapped.h"), "-I", str(work), "-I", str(native / "include"),
                "-I", str(native / "src/pc/runtime"), str(work / "settings.cpp"), str(work / "ui.cpp"),
                str(work / "harness.cpp"), "-o", str(binary)], check=True)
            scenarios = ["valid", "missing", "stale", "write-failure", "remembered", "renumbered", "cancel-remembered", "ui-size", "internal-only", "internal-default", "saved-help", "cancel-horizontal", "cancel-held-stick", "cancel-mouse", "existing-font"]
            scenarios += ["cross-region","load-failure"] if args.multi_region else ["wrong-region"]
            for scenario in scenarios:
                root = work / (region + "-" + scenario)
                if scenario != "internal-only":
                    (root / "mnt/usb6").mkdir(parents=True)
                (root / "app0").mkdir(parents=True)
                if scenario in ("stale", "remembered", "renumbered", "cancel-remembered", "saved-help") or scenario.startswith("cancel-"):
                    config = root / "data/windwaker/settings.ini"
                    config.parent.mkdir(parents=True)
                    path = "/mnt/usb2/missing.iso" if scenario == "stale" else "/mnt/usb2/image.iso" if scenario == "renumbered" else "/mnt/usb6/image.iso"
                    config.write_text("COS_DISC_PATH=" + path + "\n")
                env = {k: v for k, v in os.environ.items() if not k.startswith("COS_")}
                env["TEST_ROOT"] = str(root)
                if scenario == "write-failure":
                    env["TEST_WRITE_FAIL"] = "1"
                subprocess.run([str(binary), scenario], env=env, check=True)


if __name__ == "__main__":
    main()
