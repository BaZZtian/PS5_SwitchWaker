#!/usr/bin/env bash
# Wind Waker for the PlayStation 5 - pack the built title folder as a release archive.
#
#   ps5/tools/package-release.sh VERSION      (through tools/vm.sh package-release 1.0.0)
#
# Writes dist/WindWaker-PS5-vVERSION.zip: the title folder dist/<TITLE_ID>/ as the
# console takes it (eboot.bin, sce_sys/, sce_module/, res/, licenses/), with
# SOURCE.txt beside eboot.bin naming the revision of every part the build
# linked. A built title is under GPL-3.0: that file is how a release says where
# its source is. No disc image, save or texture pack goes in, and it refuses if
# one is in the folder.
#
# After PS5_Dusklight's package-release.sh.
# SPDX-License-Identifier: MIT
set -euo pipefail
version=${1:?usage: package-release.sh VERSION}
ps5=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
root=$(dirname "$ps5")
universal=false
if [[ ${PS5_GAME_VERSION:-auto} == auto ]]; then
    universal=true
    cos_game_id="GZLE01 / GZLP01"
    cos_build_suffix=
else
    source "$ps5/tools/game-version.sh"
fi
vulkan=$(cd -- "${PS5_VULKAN_DIR:-$root/../PS5_Vulkan}" && pwd)
upstream="$root/vendor/switchwaker"
title_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["titleId"])' "$ps5/sce_sys/param.json")
app="$root/dist/$title_id"
for file in eboot.bin initial_pipeline_cache.db sce_sys/param.json sce_sys/icon0.png sce_sys/pic0.dds \
    sce_sys/pic1.dds sce_module/libc.prx res/ps5-glyphs res/shader-cache/dawn_cache.db res/div-table.bin; do
    [[ -e $app/$file ]] || { echo "missing $app/$file: run build.sh first" >&2; exit 2; }
done
if $universal; then
    python3 - "$app" <<'PY'
import hashlib,json,pathlib,sys
app=pathlib.Path(sys.argv[1])
manifest=json.loads((app/"UNIVERSAL.json").read_text())
expected={"eboot.bin","regions/eur.bin","res/div-table.bin","res/div-table-eur.bin"}
if set(manifest["files"])!=expected: raise SystemExit("incomplete universal manifest")
for name,sha in manifest["files"].items():
    if hashlib.sha256((app/name).read_bytes()).hexdigest()!=sha:
        raise SystemExit("universal package differs from linked engines: "+name)
PY
fi
# the caches the title ships are under res/; a console's own, a save or a pack are not for a release
stray=$(find "$app" \( -iname '*.iso' -o -iname '*.ciso' -o -iname '*.gcm' -o -iname '*.rvz' -o -iname '*.gci' \
    -o -path "$app/user" -o -path "$app/radv-shader-cache" -o -name hd_textures \) -print -quit)
[[ -z $stray ]] || { echo "game data or a save in the title folder ($stray): a release never carries it" >&2; exit 2; }
# the submodule's working tree carries the console's patches: that is not a change here
[[ -z $(git -C "$root" status --porcelain --ignore-submodules=dirty) ]] ||
    { echo "uncommitted changes: a release is built from a commit" >&2; exit 2; }
provenance="$vulkan/.deps/native/radv-release/PROVENANCE.txt"
versions="$root/.deps/aurora/cmake/AuroraDependencyVersions.cmake"
mkdir -p "$app/licenses"
cp "$root/licenses/GPL-3.0.txt" "$root/licenses/MIT.txt" "$root/licenses/Zlib.txt" "$app/licenses/"
cp "$root/LICENSING.md" "$app/licenses/LICENSING.md"
cat > "$app/SOURCE.txt" <<SOURCE
Wind Waker for PlayStation 5, version $version
An unofficial homebrew port. Not affiliated with the SwitchWaker project, Nintendo
or Sony Interactive Entertainment.

This title is distributed under the GNU General Public License, version 3
(licenses/GPL-3.0.txt). Its source is these projects at these revisions:

The port (patches, SDL3 drivers, disc reader, platform layer, build)
  $(git -C "$root" remote get-url origin 2>/dev/null || echo "this repository")
  $(git -C "$root" rev-parse HEAD)
The game's code: SwitchWaker (MIT) and the decompilation it compiles (CC0-1.0),
with ps5/patches/switchwaker.patch
  https://github.com/centollOS/SwitchWaker
  $(git -C "$upstream" rev-parse HEAD)
Sound: Dolphin's DSP HLE (GPL-2.0-or-later), fetched by SwitchWaker's
native/tools/fetch_recompcore.sh at the revision that script names
The GameCube layer: Aurora (MIT), with SwitchWaker's patches and ps5/patches/aurora.patch
  https://github.com/encounter/aurora
  $(sed -n 's/^set(COS_AURORA_COMMIT "\([0-9a-f]\{40\}\)".*/\1/p' "$upstream/native/cmake/Aurora.cmake")
WebGPU: Dawn (BSD-3-Clause), with ps5/patches/dawn.patch and dawn-abseil.patch
  https://github.com/encounter/dawn
  $(sed -n 's/^_aurora_dependency_version(AURORA_DAWN_REF "\([0-9a-f]\{40\}\)".*/\1/p' "$versions")
SDL3 (Zlib), with ps5/patches/sdl.patch and the drivers in ps5/sdl
  https://github.com/libsdl-org/SDL
  $(sed -n 's/^_aurora_dependency_version(AURORA_SDL3_REF "refs\/tags\/\([^"]*\)".*/\1/p' "$versions")
The Vulkan driver: RADV, from PS5_Mesa (MIT)
  https://github.com/mihawk-99/PS5_Mesa
  $(sed -n 's/^revision: //p' "$provenance")
The link recipe, CRT, libc.prx and packaging: PS5_Vulkan (GPL-3.0)
  https://github.com/mihawk-99/PS5_Vulkan
  $(git -C "$vulkan" rev-parse HEAD)
The platform layer and SDK: PS5_PayloadSDK (GPL-3.0), over ps5-payload-dev/sdk
  https://github.com/mihawk-99/PS5_PayloadSDK
  title: $(sed -n 's/^sdk_revision=//p' "$ps5/tools/setup-sdk.sh")
  RADV archive: $(sed -n 's/^sdk: //p' "$provenance")
The other libraries Aurora and SwitchWaker fetch (fmt, zstd, libpng, Dear ImGui,
SQLite, xxHash and others) are at the versions those two projects name, at the
revisions above.
Compiler: $(${PS5_CLANG:-clang} --version | head -1)

No game data is included. The Legend of Zelda: The Wind Waker belongs to
Nintendo; this ${PS5_GAME_VERSION:-auto} build needs your own GameCube disc image
($cos_game_id revision 0, .iso, .gcm or .ciso). Select an image in the startup
browser or continue with the saved choice. The default internal disc folder
is /data/homebrew/$title_id/ (/app0/ inside the app), beside eboot.bin.
Replacing this folder can delete a disc kept there. Select a separate readable
folder to keep the disc outside the app. No USB drive is preconfigured.
Settings are in /data/windwaker/settings.ini; saves are in /data/windwaker/user.
Back up /data/windwaker/ before updating. On upgrading an older build, retain
its user/ folder until first launch imports the regional cards. HD textures
still in the app's user/hd_textures also need a backup before replacement.
See ps5/PAL-USB.md for custom locations. The startup backdrop uses the original
app artwork; its lossless RGBA copy is in res/disc-background.rgba. The
pictures in sce_sys/ are the port's own, and the files in res/ are button
symbols from Kenney's CC0 Input Prompts and shader caches this build produced
on a console.

Regions in a common package are selected from the disc header. USA runs in
eboot.bin; Europe runs in regions/eur.bin. Each engine uses its matching division
table. Region-specific saves remain separate; no save conversion is performed.
eboot.bin sha256: $(sha256sum "$app/eboot.bin" | cut -d' ' -f1)
SOURCE
if $universal; then
    python3 - "$app" <<'PY'
import hashlib,json,pathlib,sys
app=pathlib.Path(sys.argv[1])
path=app/"UNIVERSAL.json"
manifest=json.loads(path.read_text())
manifest["contents"]={str(p.relative_to(app)):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in app.rglob("*") if p.is_file() and p!=path}
path.write_text(json.dumps(manifest,indent=2)+"\n")
PY
fi
out="$root/dist/WindWaker-PS5-v$version$cos_build_suffix.zip"
rm -f "$out"
(cd "$root/dist" && zip -q -r -X "$out" "$title_id" -x '*/.DS_Store')
printf '==> %s (%s bytes)\n' "$out" "$(stat -c %s "$out")"
