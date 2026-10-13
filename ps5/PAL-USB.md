# European disc and external storage

This change adds a separate European build using SwitchWaker's upstream PAL
implementation at `054dd0eb99ab79e546709cdee2ac5886075b5d7f`. It accepts
`GZLP01`, revision 0; the default USA build still accepts `GZLE01`, revision 0.
The region-specific stub headers contain symbol names and sizes, not game data.
The player supplies their own matching GameCube disc image.

The source proposal is rebased on PS5 v1.0.3, preserving its crash fixes.
Deploy the complete built title folder: `res/div-table.bin` is generated for
that executable and must be replaced together with it.

## Build

Follow the repository's existing build prerequisites. The title linker now
requires **LLD 21 or newer** for `-z nodynamic-undefined-weak`. This resolves
unimplemented optional Mesa entrypoints to null while retaining strong-symbol
errors and supplied SDK imports. The compiler and linker versions need not be
the same; ensure the SDK's `prospero-lld` resolves to the newer linker.

```sh
# USA: existing default; build/game
bash ps5/tools/build.sh

# Europe: separate configuration and stub assets; build/game-eur
PS5_GAME_VERSION=eur bash ps5/tools/build.sh

# Optional overrides still work, but cannot reuse a build tree from the other region.
PS5_GAME_VERSION=eur PS5_BUILD_DIR=/path/to/europe-build bash ps5/tools/build.sh
```

Both variants use title ID `PPSA99309` and write `dist/PPSA99309/`; only one
region is installed in that title folder at a time. The cache check prevents a
build tree configured for the wrong region from being silently reused.

Package immediately after building, with the same region selection:

```sh
PS5_GAME_VERSION=eur bash ps5/tools/package-release.sh YOUR_VERSION
```

The European ZIP has an `-eur` suffix and its `SOURCE.txt` names `GZLP01`;
the USA ZIP retains its existing name. The packaging selection must match the
last linked executable in the shared `dist/PPSA99309` folder.

The European build defaults to German. An existing player choice is preserved;
use the touchpad options menu to choose another European language, then restart.
USA and Europe use their upstream region-specific memory-card storage, so a USA
save should not be assumed to be interchangeable with a PAL save.

## Disc storage

For a disc that survives replacement of the app folder, put it directly in
`/mnt/usbN/Homebrew/WindWaker-Discs/` on an external drive. The app probes USB0
through USB7, allowing the drive number to change after reconnecting or rebooting.
Supported extensions are `.iso`, `.gcm` and `.ciso`, case-insensitively.

Search order:

1. A readable explicitly configured `COS_DISC` path.
2. The dedicated `Homebrew/WindWaker-Discs` folder on USB0 through USB7.
3. The app's `/app0` folder, preserving the existing install layout.
4. USB0 through USB7 roots, preserving older external layouts.

An empty or missing saved path is cleared and rediscovered. Folder discovery
skips images with another region, a nonzero disc revision, truncated headers or
an invalid GameCube magic value. The normal reader still performs full disc and
game-data checks after selection; discovery is not a full dump-integrity check.
Subdirectories are not recursively searched.

External paths must be visible inside the running title's sandbox. Finding a
drive in a web file manager alone does not prove the title can read it. Test
with the internal app-root disc moved aside while the title is fully closed,
then confirm the selected `COS_DISC` path in the console log and a successful
start. Keep a source copy until that succeeds.

Replacing the app folder preserves an external ISO, but an official USA-only
update can still replace the European executable. Keep the matching European
build or use an official release that includes the same support.

## Checks and remaining console coverage

No ROM, SDK or PS5 is needed for the host discovery tests:

```sh
python3 ps5/tests/test-disc-discovery.py --cxx clang++
# Or test the same helpers in an already patched checkout:
python3 ps5/tests/test-disc-discovery.py --source vendor/switchwaker/native/src/pc/runtime/pc_harness.cpp
# With LLD 21+ and the LLVM tools in PATH:
bash ps5/tests/test-weak-link.sh
```

The tests compile the exact helper additions from the patch for both regions,
use only synthetic 32-byte disc headers, and enable AddressSanitizer and
UndefinedBehaviorSanitizer. They cover missing drives, empty/stale settings,
wrong-region/revision filtering, USB renumbering, explicit choices, CISO checks,
app-root fallback and USB-root fallback beyond USB1.

The weak-link test confirms that an absent optional function stays null, a
provided optional function remains imported and a missing required function
still fails the link. Override `CC`, `LD_LLD` and `LLVM_READELF` if needed.

The earlier v1.0.1-based European PS5 title built successfully and passed SELF integrity,
`cos_scaffold_check`, `cos_sdk_header_check` and `cos_layout_check`. The layout
check reports 213 structs and 1,465 checks with one upstream ignored header
analysis issue. A PS5 on firmware 12.40 was confirmed to start with German
texts on 2026-10-13. The installed executable was verified by SHA-256:
`1741d0acb3006c22861513459d6dd1232383a1820af4d81124c905b6db9de181`.

**Pending:** a console start using only the HDD ISO, a save/load round trip,
longer PAL gameplay, and a USA console regression run after the upstream bump.
The host checks do not establish those results.
The v1.0.3 rebase passes fresh-patch and host checks, but a rebuilt executable
and its console runtime are not claimed by this proposal.
