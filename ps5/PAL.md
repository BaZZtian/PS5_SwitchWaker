# European disc builds

Select the region with `PS5_GAME_VERSION`:

| Build | Disc, revision 0 | Build directory |
| --- | --- | --- |
| `usa` (default) | GZLE01 | build/game |
| `eur` | GZLP01 | build/game-eur |

The European build uses SwitchWaker's PAL implementation at
`054dd0eb99ab79e546709cdee2ac5886075b5d7f`. It defaults to German while preserving
saved language choices. The touchpad options menu selects another supported
European language, applied after restart. Memory-card storage remains specific
to the disc region; this does not convert USA saves to PAL.

## Build and package

Use the repository's Linux build prerequisites and **LLD 21+**. The PS5 link
uses `-z nodynamic-undefined-weak` to resolve absent optional Mesa imports to
null while retaining errors for missing required symbols. Ensure the SDK's
`prospero-lld` selects that linker.

```sh
bash ps5/tools/build.sh
PS5_GAME_VERSION=eur bash ps5/tools/build.sh
PS5_GAME_VERSION=eur PS5_BUILD_DIR=/path/to/pal-build bash ps5/tools/build.sh
PS5_GAME_VERSION=eur bash ps5/tools/package-release.sh YOUR_VERSION
```

Regional builds have separate build directories and asset stubs. Reusing a
build directory configured for the other region is rejected. Both builds use
title ID `PPSA99309` and write to `dist/PPSA99309/`; package immediately after
building with the same region selection. European archives have an `-eur`
suffix, and `SOURCE.txt` records GZLP01 and the source revisions.

Deploy the complete built title folder. `res/div-table.bin` is generated from
the linked executable and must be replaced together with `eboot.bin`. The PS5
v1.0.3 fixes remain included.

Supply a matching `.iso`, `.gcm` or `.ciso` beside `eboot.bin`. Installing a
USA-only release replaces the PAL executable, so it cannot run a GZLP01 disc.

## Tests

```sh
python3 ps5/tests/test-pal-defaults.py --cxx clang++
bash ps5/tests/test-weak-link.sh
```

The language tests compile the PS5 defaults for both regions with
AddressSanitizer and UndefinedBehaviorSanitizer. The linker test checks absent
and supplied optional imports and required-symbol errors. Set `CC`, `LD_LLD`
and `LLVM_READELF` to select the local LLVM tools.
