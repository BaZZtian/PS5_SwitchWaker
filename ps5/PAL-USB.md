# Disc selection and persistent storage

The PS5 build accepts its matching revision-0 GameCube disc: GZLP01 for the
European build or GZLE01 for the USA build. Supported formats are `.iso`,
`.gcm` and `.ciso`, with case-insensitive extensions.

## Startup selection

The PS5 opens a controller-operated disc browser before checking or opening the
game disc. It stays open when no compatible image is available. Use the D-pad
or left stick to navigate, Cross to select an image or folder, and Circle to
go back. Browse USB0-7, expansion storage, the app folder or `/data`, and rescan
after connecting a drive. Images with an incompatible header stay in the browser
with an error message; they do not close the app.

A compatible selection is saved and starts the game in the same session. If
the settings file is not writable, the screen explains that the choice applies
only to this session and requires confirmation before starting unsaved. Missing
sandbox mounts cannot be fixed by the browser: the loader must expose the drive.

## In-game options menu

Press the touchpad to open options, then choose **Debug → Disc image**. Left
and right select **Automatic** or a detected compatible image. Close the title
fully and restart to apply the choice. The image list is refreshed at startup.

Settings are saved in `/data/windwaker/settings.ini`, outside the app folder.
When that file is absent, existing `/app0/user/settings.ini` values are imported
without removing the original file. An explicit `COS_SETTINGS` override still
selects its own settings file.

For an arbitrary image location, edit the file while the title is closed:

```ini
COS_DISC_PATH=/mnt/usb2/MyDiscs/windwaker.iso
```

For automatic discovery in another directory:

```ini
COS_DISC_PATH=auto
COS_DISC_DIR=/mnt/usb2/MyDiscs
```

Use absolute paths visible inside the title sandbox. Directories are searched
one level deep. A missing or incompatible saved image falls back to automatic
discovery without overwriting the saved choice.

## Automatic discovery

The search order is:

1. A readable legacy `COS_DISC` override.
2. The compatible image selected by `COS_DISC_PATH`.
3. The directory configured by `COS_DISC_DIR`.
4. `/mnt/usbN/Homebrew/WindWaker-Discs/`, for USB0 through USB7.
5. `/app0`, retaining the existing app-folder layout.
6. USB0 through USB7 roots.

The dedicated external directory is recommended: it survives app-folder
replacement and is searched across USB numbers after reconnection or reboot.
Discovery checks the region, revision and GameCube header. The disc reader
performs the remaining game-data checks after selection.

External volumes and `/data` must be mounted into the title sandbox with write
access for settings. **ShadowMountPlus 1.7beta4+** provides these mounts with
its sandbox watcher enabled; another loader must provide equivalent access.
Seeing a drive in a file manager does not establish title-sandbox access.

## Build and tests

Follow [PAL.md](PAL.md) for regional builds and release packaging. Install the
complete title folder, including the matching `res/div-table.bin`. Updating to
a build without PAL or external-disc support removes those features even when
the external image and settings remain intact.

```sh
python3 ps5/tests/test-disc-discovery.py --cxx clang++
python3 ps5/tests/test-disc-settings.py --core vendor/switchwaker --cxx clang++
python3 ps5/tests/test-disc-startup.py --core vendor/switchwaker --cxx clang++
python3 ps5/tests/test-pal-defaults.py --cxx clang++
```

Run after `ps5/tools/setup-source.sh`. The host tests use synthetic headers and
compile the actual discovery, options registration and settings code with
AddressSanitizer and UndefinedBehaviorSanitizer. Coverage includes both disc
regions, stale paths, USB renumbering, custom paths, menu selection, app-folder
replacement, legacy settings import and write failures. Console validation
should cover external-disc startup, option selection followed by restart, and
saving and loading a game.
