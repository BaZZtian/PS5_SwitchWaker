#!/usr/bin/env bash
# Region selection shared by source setup and the PS5 build.
# SPDX-License-Identifier: MIT
case ${PS5_GAME_VERSION:-usa} in
    usa) cos_version=2; cos_game_id=GZLE01; cos_build_suffix= ;;
    eur) cos_version=3; cos_game_id=GZLP01; cos_build_suffix=-eur ;;
    *) echo "PS5_GAME_VERSION must be usa or eur" >&2; return 2 ;;
esac
