#!/usr/bin/env python3
"""Exercise actual PS5 save import and TV layout with synthetic user data."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

HARNESS = r'''
#include "pc_ps5_user_storage.h"
#include "pc_ps5_disc_layout.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
void require(bool good, const char* message) {
    if (!good) throw std::runtime_error(message);
    std::cout << "PASS: " << message << '\n';
}
void write(const std::string& file, const char* data) { std::ofstream(file) << data; }
std::string read(const std::string& file) {
    std::ifstream input(file);
    return std::string(std::istreambuf_iterator<char>(input), {});
}
int main(int argc, char** argv) {
    require(argc == 2, "fixture directory supplied");
    const std::string root(argv[1]), legacy=root+"/app", persistent=root+"/stable/user";
    pc::ps5UserDirectory(legacy);
    pc::ps5UserDirectory(legacy+"/EUR");
    pc::ps5UserDirectory(legacy+"/EUR/Card A");
    write(legacy+"/EUR/Card A/save.gci", "original save contents");
    write(legacy+"/imgui.ini", "ui placement");
    require(pc::ps5PrepareUserStorage(legacy.c_str(), persistent.c_str()), "existing saves imported outside app directory");
    require(read(persistent+"/EUR/Card A/save.gci") == "original save contents", "save contents copied intact");
    require(read(legacy+"/EUR/Card A/save.gci") == "original save contents", "legacy save retained");
    write(persistent+"/EUR/Card A/save.gci", "newer persistent save");
    write(legacy+"/EUR/Card A/old.gci", "obsolete app save");
    require(pc::ps5PrepareUserStorage(legacy.c_str(), persistent.c_str()), "next startup succeeds");
    require(read(persistent+"/EUR/Card A/save.gci") == "newer persistent save", "newer persistent save never overwritten");
    require(access((persistent+"/EUR/Card A/old.gci").c_str(),F_OK) != 0, "one-time import does not resurrect old saves");
    remove((persistent+"/.legacy-cards-imported").c_str());
    require(pc::ps5PrepareUserStorage(legacy.c_str(), persistent.c_str()), "interrupted import can be retried");
    require(read(persistent+"/EUR/Card A/save.gci") == "newer persistent save", "retry preserves destination conflicts");
    const std::string failed = root+"/blocked/user";
    pc::ps5UserDirectory(root+"/blocked");
    write(failed, "not a directory");
    require(!pc::ps5PrepareUserStorage(legacy.c_str(),failed.c_str()), "invalid storage fails without claiming migration");
    require(read(legacy+"/EUR/Card A/save.gci") == "original save contents", "failed migration preserves source");
    for (const float height : {720.f,1080.f,2160.f}) {
        const auto layout=pc::ps5DiscLayout(height*16/9,height);
        require(layout.text/height > .029f && layout.text/height < .031f, "text scales proportionally at 720p, 1080p and 4K");
        require(layout.panelY+layout.panelHeight < height*.95f, "panel stays inside output");
    }
    require(pc::ps5DiscLayout(3840,2160,1.5f).text==96.f, "4K large preference draws 96px text");
}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core',type=Path,required=True)
    parser.add_argument('--cxx',default=os.environ.get('CXX','clang++'))
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='windwaker-user-') as directory:
        work=Path(directory)
        source=work/'test.cpp'
        source.write_text(HARNESS)
        binary=work/'test'
        subprocess.run(shlex.split(args.cxx)+['-std=c++17','-Wall','-Wextra','-Werror',
            '-fsanitize=address,undefined','-I',str(args.core/'native/src/pc/runtime'),
            str(source),'-o',str(binary)],check=True)
        fixture=work/'fixture'
        fixture.mkdir()
        subprocess.run([str(binary),str(fixture)],check=True)

if __name__=='__main__':
    main()
