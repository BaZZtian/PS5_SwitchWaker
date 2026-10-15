/* Disc-header identification shared by discovery, handoff and host tests.
 * SPDX-License-Identifier: MIT */
#ifndef PS5_DISC_REGION_H
#define PS5_DISC_REGION_H
#include <stdio.h>
#include <string.h>
enum ps5_disc_region { PS5_DISC_INVALID, PS5_DISC_USA, PS5_DISC_EUR };
static inline const char *ps5_disc_id(enum ps5_disc_region region) {
    return region == PS5_DISC_USA ? "GZLE01" : region == PS5_DISC_EUR ? "GZLP01" : "";
}
static inline enum ps5_disc_region ps5_disc_region(const char *path) {
    if (path == NULL || path[0] != '/') return PS5_DISC_INVALID;
    FILE *file = fopen(path, "rb");
    if (file == NULL) return PS5_DISC_INVALID;
    unsigned char header[32];
    int readable = fread(header, 1, sizeof(header), file) == sizeof(header);
    if (readable && memcmp(header, "CISO", 4) == 0) {
        readable = header[8] == 1 && fseek(file, 0x8000, SEEK_SET) == 0 &&
                   fread(header, 1, sizeof(header), file) == sizeof(header);
    }
    fclose(file);
    if (!readable || header[6] != 0 || header[7] != 0 ||
        header[28] != 0xC2 || header[29] != 0x33 || header[30] != 0x9F || header[31] != 0x3D)
        return PS5_DISC_INVALID;
    if (memcmp(header, "GZLE01", 6) == 0) return PS5_DISC_USA;
    if (memcmp(header, "GZLP01", 6) == 0) return PS5_DISC_EUR;
    return PS5_DISC_INVALID;
}
#ifdef __cplusplus
extern "C" {
#endif
void ps5_region_arguments(int argc, char **argv);
int ps5_load_disc_region(enum ps5_disc_region region, const char *disc);
#ifdef __cplusplus
}
#endif
#endif
