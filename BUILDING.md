# Build and developer documentation

[Back to the user guide](README.md)

## Development

To try a change without the console:

```sh
cmake -S vendor/switchwaker/native -B build/native-mac -G Ninja \
    -DFETCHCONTENT_SOURCE_DIR_AURORA=$PWD/.deps/aurora -DCOS_AURORA_PREPATCHED=ON \
    -DCOS_RECOMPCORE_DIR=$PWD/.deps/recompcore \
    -DCOS_RUNTIME_ASSETS=ON -DCOS_ASSETS_DIR=$PWD/.deps/assets/GZLE01
ninja -C build/native-mac switchwaker
COS_BUILD_DIR=$PWD/build/native-mac COS_DISC=/path/to/GZLE01.iso COS_FPS60=1 \
    COS_BUTTON_GLYPHS=$PWD/ps5/art/glyphs vendor/switchwaker/native/tools/run.sh run \
    --preset sailing --aspect 16:9 --frames 700 --shot 690
```

**Finding a fault on the console.** The game's own `[cos]` lines go to the
console's log (klog, port 3232) with the driver's. A `[dev]` section at the end
of `user/settings.ini` sets developer variables at the next start, for example
`COS_TRACE=scene,res` for every scene created and every file opened. A scene
change that stays in one step logs `scene-req-watch` lines every 300 calls: the
step, and the processes still waiting to be deleted.

The stop that 1.0.1 fixes was found that way. Some actors declare their methods
as returning `bool` and the game's process framework calls them as returning
`int` and compares with `TRUE`. On x86-64 the rest of the register is undefined,
so a delete could be refused for ever and the next scene never came; on ARM (the
Mac, the Switch) it does not show. The framework now reads only the low byte
([`f_pc_method.cpp` in the patch](ps5/patches/switchwaker.patch)). On the Mac, `COS_EVENT_SWEEP_FOLLOW=1` lets
`run.sh event-sweep` go on through a stage change an event asks for.

The crash that 1.0.3 fixes is a third one. A hanging platform of Dragon Roost
Cavern whose ropes were cut on an earlier visit is created with them cut, and
the rope points are simulated from values nothing has set. A NaN among them
reaches the arctangent table as an index: the conversion to an integer gives
0x80000000, which the GameCube's 32 bit address wraps back to the first entry
and x86-64 turns into a read 4 GB below the table. The lookup now gives the
first entry for a NaN or a ratio outside the table ([`c_math.cpp` in the patch](ps5/patches/switchwaker.patch)).
It was found from a player's photograph of the console's error message: the
two addresses in it, less the load address 0x400000, name `cM_atan2s` and
`himo_move` in the release's ELF.

The crash that 1.0.2 fixes is the same kind of difference. The boss of Dragon
Roost Cavern turns towards the player with a step count that is still zero the
first time, an integer division by zero: the GameCube and ARM give a quotient
and go on, x86-64 raises SIGFPE. The three helpers involved now give 0
([`c_lib.cpp` in the patch](ps5/patches/switchwaker.patch)), and so that the next one elsewhere is not a crash,
the title handles SIGFPE itself: it finishes the division as ARM does (quotient
0, remainder the dividend), logs `integer division fault` with the address, and
goes on. The console's code cannot be read at run time, so the build lists
every division instruction of the linked title in `res/div-table.bin`
([`make-div-table.py`](ps5/tools/make-div-table.py)) and the handler looks the address up; a fault
that is not in the list is still a crash with the console's record.
`COS_DIV_TEST=1` in `[dev]` divides by zero once at the start to check it. On
the Mac, `COS_SAVE_LOAD_WALK=<frames>` makes `run.sh save-load` walk forward
from a loaded save (`COS_CARD_DIR` names a card folder holding a player's
`.gci`).

`COS_TEXTURE_DUMPS=1` writes every texture drawn into the cache folder's
`texture_dumps`, named as a replacement for it must be named.


## Build

As PS5_Dusklight: on Linux (on a Mac, in the Lima VM) with PS5_Vulkan, PS5_Mesa
and PS5_PayloadSDK beside this folder.

```sh
ps5/tools/vm.sh build     # from macOS; ps5/tools/build.sh inside the VM
ps5/tools/vm.sh deploy
ps5/tools/vm.sh run
```

`build.sh` runs `setup-source.sh` first, which patches `vendor/switchwaker`
(`ps5/patches/switchwaker.patch`, every hunk behind `__PROSPERO__`) and fetches
into `.deps/` Aurora at SwitchWaker's pin with its patches, Dolphin's DSP HLE
sources and the stub asset headers. While changing `vendor/switchwaker`, run
`git -C vendor/switchwaker diff > ps5/patches/switchwaker.patch` before a build.

