#!/usr/bin/env python3
"""Assemble verified regional engines into one title; never merge into user data.
SPDX-License-Identifier: MIT
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(app, expected):
    record=json.loads((app/"BUILD.json").read_text())
    if record.get("disc")!=expected or record.get("multi_region") is not True:
        raise ValueError(f"{app}: expected multi-region engine {expected}")
    for name in ("eboot.bin","res/div-table.bin"):
        if digest(app/name)!=record.get(name):
            raise ValueError(f"{app}: {name} differs from its linked build")
    return record
def assemble(usa, eur, output):
    records={region:verify(app,region) for app,region in ((usa,"GZLE01"),(eur,"GZLP01"))}
    special={"eboot.bin","res/div-table.bin","BUILD.json","SOURCE.txt"}
    def shared(app):
        return {str(p.relative_to(app)):digest(p) for p in app.rglob("*") if p.is_file() and str(p.relative_to(app)) not in special}
    if shared(usa)!=shared(eur):
        raise ValueError("regional builds contain different shared runtime files")
    if output.exists():
        if not (output/"UNIVERSAL.json").is_file():
            raise ValueError(f"{output}: existing output is not a universal build; choose an empty output directory")
        previous=json.loads((output/"UNIVERSAL.json").read_text())
        known=previous.get("contents",{})
        for p in output.rglob("*"):
            if p.is_file() and p.name!="UNIVERSAL.json":
                name=str(p.relative_to(output))
                if name not in known or digest(p)!=known[name]:
                    raise ValueError(f"{output}: unknown or changed file {name}; refusing replacement")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".windwaker-auto-",dir=output.parent) as temp:
        stage=Path(temp)/output.name
        shutil.copytree(usa,stage)
        (stage/"regions").mkdir()
        shutil.copy2(eur/"eboot.bin",stage/"regions/eur.bin")
        shutil.copy2(eur/"res/div-table.bin",stage/"res/div-table-eur.bin")
        (stage/"BUILD.json").unlink()
        manifest={"regions":records, "files":{}}
        for name in ("eboot.bin","regions/eur.bin","res/div-table.bin","res/div-table-eur.bin"):
            manifest["files"][name]=digest(stage/name)
        manifest["contents"]={str(p.relative_to(stage)):digest(p) for p in stage.rglob("*") if p.is_file()}
        (stage/"UNIVERSAL.json").write_text(json.dumps(manifest,indent=2)+"\n")
        if output.exists(): shutil.rmtree(output)
        shutil.move(str(stage),output)
if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("usa",type=Path);parser.add_argument("eur",type=Path);parser.add_argument("output",type=Path)
    args=parser.parse_args()
    assemble(args.usa.resolve(),args.eur.resolve(),args.output.resolve())
