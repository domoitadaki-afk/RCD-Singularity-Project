#!/usr/bin/env python3
"""Same as build_all.bat but for Linux/macOS — used to verify the frozen
launcher logic end-to-end before running build_all.bat on Windows."""
import glob
import os
import shutil
import subprocess
import sys

OUT = "RCD Reviewer"
PYI = [sys.executable, "-m", "PyInstaller", "--onefile", "--windowed",
       "--noconfirm", "--distpath", "build_tmp",
       "--workpath", "build_tmp/work", "--specpath", "build_tmp"]


def build(script, name, dest):
    print(f"  building {name} ...", flush=True)
    subprocess.check_call(PYI + ["--name", name, script])
    shutil.copy2(os.path.join("build_tmp", name), os.path.join(OUT, dest, name))


shutil.rmtree(OUT, ignore_errors=True)
shutil.rmtree("build_tmp", ignore_errors=True)
os.makedirs(os.path.join(OUT, "Topics"))
os.makedirs(os.path.join(OUT, "Formulas"))

build("main_menu.py", "RCDReviewer", ".")
for f in sorted(glob.glob("Topics/*.py")):
    stem = os.path.splitext(os.path.basename(f))[0]
    build(f, stem, "Topics")
for f in sorted(glob.glob("Formulas/*.py")):
    stem = os.path.splitext(os.path.basename(f))[0]
    build(f, stem, "Formulas")

shutil.rmtree("build_tmp", ignore_errors=True)
print(f"DONE -> {OUT}/")
