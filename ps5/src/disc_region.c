/* Restart the same title in the matching, packaged regional executable.
 * SPDX-License-Identifier: MIT */
#include "disc_region.h"
#include <errno.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>
int sceSystemServiceLoadExec(const char *path, const char *const *argv);
int sceKernelUsleep(unsigned int microseconds);
void ps5_region_arguments(int argc, char **argv) {
    /* Carry the selected path even when settings could not be written.
     * Environment inheritance across LoadExec is not required. */
    if (argc != 5 || strcmp(argv[1], "--ps5-disc") || strcmp(argv[3], "--ps5-region"))
        return;
    setenv("COS_PS5_HANDOFF", argv[4], 1);
    if (argv[2][0] == '/' && (!strcmp(argv[4], "GZLE01") || !strcmp(argv[4], "GZLP01")))
        setenv("COS_DISC", argv[2], 1);
}
int ps5_load_disc_region(enum ps5_disc_region region, const char *disc) {
    const char *executable;
    const char *table;
    if (region == PS5_DISC_USA) {
        executable = "/app0/eboot.bin";
        table = "/app0/res/div-table.bin";
    } else if (region == PS5_DISC_EUR) {
        executable = "/app0/regions/eur.bin";
        table = "/app0/res/div-table-eur.bin";
    } else return -EINVAL;
    struct stat status;
    if (ps5_disc_region(disc) != region) return -EINVAL;
    if (stat(executable, &status) || !S_ISREG(status.st_mode) || access(executable, R_OK))
        return -ENOENT;
    if (stat(table, &status) || !S_ISREG(status.st_mode) || status.st_size < 20 || access(table, R_OK))
        return -ENOENT;
    const char *args[] = {"windwaker", "--ps5-disc", disc, "--ps5-region", ps5_disc_id(region), NULL};
    const int result = sceSystemServiceLoadExec(executable, args);
    if (result != 0) return result;
    /* LoadExec is asynchronous. Never resume the wrong game code. */
    for (;;) sceKernelUsleep(100000);
}
