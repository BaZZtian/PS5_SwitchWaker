#!/usr/bin/env python3
"""Exercise real disc identification, regional dispatch and package assembly.
Synthetic headers only. The console LoadExec call is mocked.
SPDX-License-Identifier: MIT
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

HARNESS=r"""
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <strings.h>
#include <unistd.h>
#include <sys/stat.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
namespace fs=std::filesystem;
static std::string root;
static std::string mapped(const char* p) { return root+p; }
static FILE* testOpen(const char* p,const char* m) { return ::fopen(mapped(p).c_str(),m); }
static int testAccess(const char* p,int m) { return ::access(mapped(p).c_str(),m); }
static int testStat(const char* p,struct stat* s) { return ::stat(mapped(p).c_str(),s); }
#define fopen testOpen
#define access testAccess
#define stat(p,s) testStat(p,s)
#include "disc_region.c"
#undef fopen
#undef access
#undef stat
struct Dispatched {};
static std::string target;
static std::vector<std::string> launchArgs;
static int loadError=0, loads=0;
int sceSystemServiceLoadExec(const char* p,const char*const* args) {
    ++loads; target=p;launchArgs.clear();
    for (int i=0;args[i];++i) launchArgs.emplace_back(args[i]);
    if (loadError) return loadError;
    throw Dispatched{};
}
int sceKernelUsleep(unsigned int) { std::abort(); }
static void require(bool ok,const char* why) {
    if(!ok) {std::cerr<<"FAIL "<<COS_GAME_ID_STR<<": "<<why<<"\n";std::exit(1);}
    std::cout<<"PASS "<<COS_GAME_ID_STR<<": "<<why<<"\n";
}
static void image(const char* p,const char* id,unsigned revision=0,bool ciso=false) {
    fs::create_directories(fs::path(mapped(p)).parent_path());
    std::vector<unsigned char> data(ciso?0x8020:32,0);
    const int offset=ciso?0x8000:0;
    if(ciso) {memcpy(data.data(),"CISO",4);data[8]=1;}
    memcpy(data.data()+offset,id,6);data[offset+7]=revision;
    data[offset+28]=0xc2;data[offset+29]=0x33;data[offset+30]=0x9f;data[offset+31]=0x3d;
    std::ofstream out(mapped(p),std::ios::binary);out.write((char*)data.data(),data.size());
}
namespace pc {
struct {const char* disc=nullptr;} gConfig;
static int checked=0;
static int checkDisc() {++checked;return !strcmp(ps5_disc_id(ps5_disc_region(gConfig.disc)),COS_GAME_ID_STR)?0:14;}
static void writef(int,const char*,...) {}
__DISPATCH__
}
int main(int argc,char** argv) {
    require(argc==2,"temporary filesystem supplied");root=argv[1];
    const char* other=!strcmp(COS_GAME_ID_STR,"GZLE01")?"GZLP01":"GZLE01";
    const auto otherRegion=!strcmp(other,"GZLP01")?PS5_DISC_EUR:PS5_DISC_USA;
    image("/roms/named something else.iso",COS_GAME_ID_STR);
    image("/roms/with spaces 'quotes'.ciso",other,0,true);
    require(ps5_disc_region("/roms/named something else.iso")!=PS5_DISC_INVALID,"region comes from header, not filename");
    require(!strcmp(ps5_disc_id(ps5_disc_region("/roms/with spaces 'quotes'.ciso")),other),"CISO detects the other region");
    image("/roms/revision.iso",other,1);image("/roms/japan.iso","GZLJ01");
    require(ps5_disc_region("/roms/revision.iso")==PS5_DISC_INVALID,"unsupported revision rejected");
    require(ps5_disc_region("/roms/japan.iso")==PS5_DISC_INVALID,"unsupported region rejected");
    {std::ofstream out(mapped("/roms/short.iso"));out<<"GZLE01";}
    require(ps5_disc_region("/roms/short.iso")==PS5_DISC_INVALID,"truncated header rejected");
    pc::gConfig.disc="/roms/named something else.iso";
    require(pc::ps5ValidateSelectedDisc() && pc::checked==1 && pc::ps5StartSelectedDisc() && loads==0,
            "matching engine keeps running and performs strict disc validation");
    pc::gConfig.disc="/roms/with spaces 'quotes'.ciso";
    require(pc::ps5ValidateSelectedDisc() && pc::checked==1,"other region never reaches the wrong engine's strict disc check");
    require(!pc::ps5StartSelectedDisc() && loads==0,"missing engine fails without a process handoff");
    fs::create_directories(root+"/app0/regions");fs::create_directories(root+"/app0/res");
    for(const char* p:{"/app0/eboot.bin","/app0/regions/eur.bin","/app0/res/div-table.bin","/app0/res/div-table-eur.bin"})
        {std::ofstream out(mapped(p));out<<std::string(32,'x');}
    loadError=-123;
    require(!pc::ps5StartSelectedDisc() && loads==1,"LoadExec error returns to the picker");
    loadError=0;
    try {pc::ps5StartSelectedDisc();require(false,"successful handoff never returns");} catch(const Dispatched&) {}
    require(target==(otherRegion==PS5_DISC_EUR?"/app0/regions/eur.bin":"/app0/eboot.bin"),"correct packaged executable selected");
    require(launchArgs==std::vector<std::string>{"windwaker","--ps5-disc",pc::gConfig.disc,"--ps5-region",other},
            "exact disc path and target region passed as arguments");
    std::vector<char*> args;for(auto& arg:launchArgs)args.push_back(arg.data());
    unsetenv("COS_DISC");ps5_region_arguments(args.size(),args.data());
    require(!strcmp(getenv("COS_DISC"),pc::gConfig.disc),"handoff restores exact ISO without saved settings");
    const int before=loads;
    require(!pc::ps5ResumeSelectedDisc() && !pc::ps5StartSelectedDisc() && loads==before,
            "mismatched or stale engine cannot create an executable restart loop");
    setenv("COS_PS5_HANDOFF",COS_GAME_ID_STR,1);pc::gConfig.disc="/roms/named something else.iso";
    require(pc::ps5ResumeSelectedDisc(),"correct engine validates and resumes without a second picker countdown");
    unsetenv("COS_PS5_HANDOFF");
    require(!pc::ps5ResumeSelectedDisc(),"ordinary starts retain the picker");
}
"""
def package_tests(tool,work):
    spec=importlib.util.spec_from_file_location("assembly",tool)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    usa=work/"usa";eur=work/"eur";output=work/"out"/"PPSA99309"
    for app,region in ((usa,"GZLE01"),(eur,"GZLP01")):
        (app/"res").mkdir(parents=True)
        (app/"eboot.bin").write_bytes(region.encode()*10)
        (app/"res/div-table.bin").write_bytes(region.encode()*20)
        (app/"res/common").write_text("shared")
        record={"disc":region,"multi_region":True}
        for name in ("eboot.bin","res/div-table.bin"):record[name]=module.digest(app/name)
        (app/"BUILD.json").write_text(json.dumps(record))
    module.assemble(usa,eur,output)
    assert (output/"eboot.bin").read_bytes()==(usa/"eboot.bin").read_bytes()
    assert (output/"regions/eur.bin").read_bytes()==(eur/"eboot.bin").read_bytes()
    assert (output/"res/div-table-eur.bin").read_bytes()==(eur/"res/div-table.bin").read_bytes()
    module.assemble(usa,eur,output)
    (output/"save.gci").write_bytes(b"keep")
    try:module.assemble(usa,eur,output)
    except ValueError:pass
    else:raise AssertionError("personal data replacement accepted")
    assert (output/"save.gci").read_bytes()==b"keep"
    (eur/"eboot.bin").write_bytes(b"wrong engine")
    try:module.assemble(usa,eur,work/"broken")
    except ValueError:pass
    else:raise AssertionError("stale engine accepted")
    print("PASS assembly: regional binaries/tables verified; stale builds and personal data rejected")
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core",type=Path,required=True)
    parser.add_argument("--cxx",default=os.getenv("CXX","clang++"))
    args=parser.parse_args();ps5=Path(__file__).resolve().parents[1]
    runtime=(args.core/"native/src/pc/runtime/pc_harness.cpp").read_text()
    start=runtime.index("// Validate the current engine")
    end=runtime.index("// The console's defaults",start)
    with tempfile.TemporaryDirectory(prefix="windwaker-regions-") as temporary:
        work=Path(temporary)
        source=work/"dispatch.cpp";source.write_text(HARNESS.replace("__DISPATCH__",runtime[start:end]))
        for region in ("GZLE01","GZLP01"):
            binary=work/region
            subprocess.run(shlex.split(args.cxx)+["-std=c++17","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",
                "-DPS5_MULTI_REGION=1",f'-DCOS_GAME_ID_STR="{region}"',"-I",str(ps5/"src"),str(source),"-o",str(binary)],check=True)
            fs=work/(region+"-data");fs.mkdir()
            env={k:v for k,v in os.environ.items() if not k.startswith("COS_")}
            subprocess.run([str(binary),str(fs)],env=env,check=True)
        package_tests(ps5/"tools/assemble-universal.py",work)
if __name__=="__main__":main()
