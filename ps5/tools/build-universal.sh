#!/usr/bin/env bash
# Build both native engines and assemble a single PS5 title.
# SPDX-License-Identifier: MIT
set -euo pipefail
ps5=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
root=$(dirname "$ps5")
title_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["titleId"])' "$ps5/sce_sys/param.json")
base=${PS5_MULTI_BUILD_DIR:-$root/build/universal}
for region in usa eur; do
    PS5_GAME_VERSION=$region PS5_MULTI_REGION=ON PS5_BUILD_DIR="$base/$region" \
        bash "$ps5/tools/build.sh" "$@"
done
python3 "$ps5/tools/assemble-universal.py" \
    "$base/usa/title/$title_id" "$base/eur/title/$title_id" "$root/dist/$title_id"
