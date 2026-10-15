# Automatic USA and European disc support

The default build produces one PS5 title supporting revision-0 GZLE01 (USA)
and GZLP01 (Europe). The startup browser identifies the selected ISO/GCM/CISO
by its disc header. USA runs in eboot.bin; Europe runs in regions/eur.bin.
The shell replaces the process before the other region initializes game data.
The selected path is carried explicitly in launch arguments, including when
saving settings failed. A successful handoff resumes without another picker
countdown. Missing engines and failed handoffs remain recoverable in the picker.

Both engines and their matching division tables are built and packaged together.
There is one title ID, PPSA99309, and one normal update archive. Users do not
choose a regional application download. Unsupported regions and revisions are
rejected. PAL defaults to German unless a language preference was saved.
USA and EUR memory-card directories remain separate; saves are not converted.

## Build and package

Use the normal Linux prerequisites and LLD 21+:

~~~sh
bash ps5/tools/build.sh -j6 switchwaker
bash ps5/tools/package-release.sh YOUR_VERSION
~~~

The build stages the engines independently under build/universal/usa and
build/universal/eur. Set PS5_MULTI_BUILD_DIR to put these trees elsewhere.
Assembly verifies each engine identity, binary/table hashes and shared runtime
files. Packaging rechecks the common manifest. Unknown or changed files in an
existing assembly output prevent replacement, protecting personal data.

Explicit PS5_GAME_VERSION=usa or eur builds remain available for development.
They use their own build directories and are not interchangeable with the
common release package. Never publish a regional-only archive as its update.

## Validation

~~~sh
python3 ps5/tests/test-region-dispatch.py --core vendor/switchwaker
python3 ps5/tests/test-disc-startup.py --core vendor/switchwaker --multi-region
python3 ps5/tests/test-disc-settings.py --core vendor/switchwaker
python3 ps5/tests/test-user-storage.py --core vendor/switchwaker
~~~

The handoff tests run the real header reader and dispatch code with the console
LoadExec call mocked. A PS5 test must separately confirm the native process
replacement and launch each actual region before release.
