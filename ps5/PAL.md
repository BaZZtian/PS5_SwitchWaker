# European disc builds

The PS5 port can now build against SwitchWaker's PAL implementation at
`054dd0eb99ab79e546709cdee2ac5886075b5d7f`. Region selection is explicit:

| Build | Disc, revision 0 | Default build directory |
| --- | --- | --- |
| `PS5_GAME_VERSION=usa` (default) | GZLE01 | build/game |
| `PS5_GAME_VERSION=eur` | GZLP01 | build/game-eur |

The region-specific runtime asset stubs contain names and sizes, not disc data.
The player supplies their own matching `.iso`, `.gcm` or `.ciso`. The image can
remain beside `eboot.bin` in `/data/homebrew/PPSA99309/` or use the external
storage search described in PAL-USB.md.

This proposal is based on PS5 v1.0.3 (`3c0f213f2d4c17606ac8637eda2c5da6cbcc73b0`),
preserving its scene-transition, division-by-zero and arctangent-table fixes.
Its generated `res/div-table.bin` belongs to the linked executable: deploy the
complete built title folder, keeping this table and executable together.

## Build and release

Use the repository's existing Linux build prerequisites. **LLD 21 or newer**
is required for `-z nodynamic-undefined-weak`: optional unsupported Mesa symbols
remain null, supplied imports remain imported, and missing required symbols
still fail linking. Ensure the SDK's `prospero-lld` selects that linker; compiler
and linker versions need not be identical.

```sh
bash ps5/tools/build.sh
PS5_GAME_VERSION=eur bash ps5/tools/build.sh
PS5_GAME_VERSION=eur PS5_BUILD_DIR=/path/to/pal-build bash ps5/tools/build.sh
```

A build directory configured for the other region is rejected. Both versions
use title ID PPSA99309 and write to the shared `dist/PPSA99309/` folder, so only
one region is installed in that folder at a time. Package immediately after
building, using the same region selection:

```sh
PS5_GAME_VERSION=eur bash ps5/tools/package-release.sh YOUR_VERSION
```

The European archive is named `WindWaker-PS5-vYOUR_VERSION-eur.zip`, and its
SOURCE.txt names GZLP01. USA archive naming remains unchanged. The packaging
region must match the last executable linked into the shared dist folder.

The European build defaults to German when no player language has been saved.
An existing preference takes priority; the touchpad options menu can select
another European game language, applied after restarting. Region-specific
memory-card storage remains separate; USA saves are not automatically converted.
Disc error notifications now name the region and ID selected by the build.

## Validation

```sh
python3 ps5/tests/test-pal-defaults.py --cxx clang++
bash ps5/tests/test-weak-link.sh
```

The language test compiles the actual PS5-default additions from the patch for
VERSION 2 and VERSION 3, with AddressSanitizer and UndefinedBehaviorSanitizer.
It checks that a fresh PAL session selects German, USA does not acquire a PAL
language default, and an existing player language remains unchanged. The weak
test accepts CC, LD_LLD and LLVM_READELF overrides.

The earlier v1.0.1-based PAL-only PS5 executable built and passed SELF integrity plus
cos_scaffold_check, cos_sdk_header_check and cos_layout_check. The layout check
reported 213 structs / 1,465 checks and one upstream ignored header-analysis
issue. Its SHA-256 is
`f8d7580d3b88f52258f1ea697bf9e7b19dcf5320949c2d234c1ee1c7f17bff18`.

The same v1.0.1-based PAL/language changes were subsequently confirmed to start with German
texts on PS5 firmware 12.40 in a build that also contains a separate USB-disc
follow-up. That combined executable has SHA-256
`1741d0acb3006c22861513459d6dd1232383a1820af4d81124c905b6db9de181`.
The PAL-only executable was installed and hash-verified before that but was not
independently given a console start test. Save/load, extended PAL gameplay,
and a USA console regression after the upstream bump remain unverified.
The rebased v1.0.3 sources pass the host checks and apply to the fresh core pin;
a rebuilt v1.0.3 executable and console runtime test are not claimed here.

External disc discovery and network downloads are separate follow-ups and are
not required to build this PAL variant. No ROM or personal console data is part
of the source changes.
