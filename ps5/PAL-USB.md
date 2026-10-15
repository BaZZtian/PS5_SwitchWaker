# Disc selection and persistent storage

The common PS5 build accepts revision-0 GZLP01 (Europe) and GZLE01 (USA) GameCube discs.
It selects the matching packaged engine automatically from the disc header. Supported formats are `.iso`,
`.gcm` and `.ciso`, with case-insensitive extensions.

## Startup selection

The standard internal disc folder is `/data/homebrew/PPSA99309/`, beside
`eboot.bin` (`/app0/` inside the app). It is the first automatic location after
an explicitly saved choice or search directory. **Replacing the app folder can
delete an ISO kept there. Back it up before updating**, or choose a separate
folder in the browser. No USB number or personal path is preconfigured.

The PS5 opens a controller-operated disc browser before checking or opening the
game disc. First setup shows storage information, including the default folder
and update precautions; Cross or Circle proceeds to selection. Square opens
the information again, and Up/Down move between its three pages. It stays open
when no compatible image is available. Use the D-pad
or left stick to navigate, Cross to select an image or folder, and Circle to
go back. Browse the app folder, available USB0-7, expansion storage or `/data`, and rescan
after connecting a drive. Images with an incompatible header stay in the browser
with an error message; they do not close the app. Only readable mount points
are offered, with the app folder first. The browser does not create missing
drive paths.

A compatible selection is saved and starts the game in the same session. On
later launches, a valid saved choice starts automatically after three seconds.
Movement of either stick, the D-pad, arrow keys or the mouse cancels the
countdown, including a stick held when the screen opens. Circle also cancels it.
USB renumbering is recovered only
when the saved filename has a unique compatible match.

The original app artwork is used behind the selector. Text scales with the
display resolution; L1/R1 adjust its size from 75% to 150% and save the preference.
This font is limited to the startup chooser; the in-game options and debug
menus keep their original default font and scaling.
Long filenames wrap within their selectable rows. If
the settings file is not writable, the screen explains that the choice applies
only to this session and requires confirmation before starting unsaved. Missing
sandbox mounts cannot be fixed by the browser: the loader must expose the drive.

## In-game options menu

Press the touchpad to open options, then choose **Debug â†’ Disc image**. Left
and right select **Automatic** or a detected compatible image. Close the title
fully and restart to apply the choice. The image list is refreshed at startup.

Settings are saved in `/data/windwaker/settings.ini`, outside the app folder.
When that file is absent, existing `/app0/user/settings.ini` values are imported
without removing the original file. An explicit `COS_SETTINGS` override still
selects its own settings file.

Choose arbitrary image locations in the startup browser; the selected absolute
path is saved as `COS_DISC_PATH`. To return to discovery, select **Automatic**
in the options menu. Advanced setups can set `COS_DISC_DIR` to an existing
absolute directory while the title is closed. Never copy another console's
USB number into a fresh installation. Directories are searched
one level deep. A missing or incompatible saved image falls back to automatic
discovery without overwriting the saved choice.

## Automatic discovery

The search order is:

1. A readable legacy `COS_DISC` override.
2. The compatible image selected by `COS_DISC_PATH`.
3. The directory configured by `COS_DISC_DIR`.
4. `/app0`, retaining the existing internal app-folder default.
5. `/mnt/usbN/Homebrew/WindWaker-Discs/`, for available USB0 through USB7.
6. USB0 through USB7 roots.

An external folder is optional and survives app-folder replacement. The
`Homebrew/WindWaker-Discs/` directory is searched across available USB numbers
after reconnection or reboot. An image selected in another nested directory
may need to be selected again after its drive number changes.
Discovery checks the region, revision and GameCube header. The disc reader
performs the remaining game-data checks after selection.

External volumes and `/data` must be mounted into the title sandbox with write
access for settings. **ShadowMountPlus 1.7beta4+** provides these mounts with
its sandbox watcher enabled; another loader must provide equivalent access.
Seeing a drive in a file manager does not establish title-sandbox access.

## Saved games

User data is stored in `/data/windwaker/user`, including `EUR/Card A` or the
matching region's card folder. On first launch the port copies existing regional
cards from `/app0/user`, retains the originals and never replaces an existing
persistent save. A completed-import marker prevents old deleted files being
restored on each startup. Failed imports stop before the game opens its card.
Shader caches remain in the title folder and can be regenerated after updates.

Close the app and back up `/data/windwaker/` before updating. Its settings and
regional save folders are outside the title and survive replacing that folder;
they are not a replacement for a separate backup. During an upgrade from
v1.0.4 or older, keep the old app's complete `user/` folder until the new app
has launched and imported the saves. Deleting it before first launch also
deletes the only copy of an unimported save. The old copies are retained by
the import; existing persistent saves take precedence. USA and European saves
remain separate. Texture packs in `/app0/user/hd_textures/` still belong to
the app folder and need a separate backup before replacement.

## Build and tests

Follow [PAL.md](PAL.md) for the common USA/Europe build and release packaging. Install the
complete title folder, including the matching `res/div-table.bin`. Updating to
a build without PAL or external-disc support removes those features even when
the external image and settings remain intact.

```sh
python3 ps5/tests/test-disc-discovery.py --cxx clang++
python3 ps5/tests/test-disc-settings.py --core vendor/switchwaker --cxx clang++
python3 ps5/tests/test-disc-startup.py --core vendor/switchwaker --cxx clang++
python3 ps5/tests/test-user-storage.py --core vendor/switchwaker --cxx clang++
python3 ps5/tests/test-pal-defaults.py --cxx clang++
```

Pillow is required by `make-disc-background.py` to package the existing artwork.
Run tests after `ps5/tools/setup-source.sh`. The host tests use synthetic headers
and compile the actual discovery, options registration and settings code with
AddressSanitizer and UndefinedBehaviorSanitizer. Coverage includes both disc
regions, stale paths, USB renumbering, custom paths, menu selection, app-folder
replacement, legacy settings import and write failures. Console validation
should cover external-disc startup, option selection followed by restart, and
saving and loading a game.
