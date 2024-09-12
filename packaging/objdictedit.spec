# -*- mode: python ; coding: utf-8 -*-
import os
import sys
sys.path.append("packaging")
from filereplacer import convert

basepath = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

workpath = basepath
os.chdir(workpath)

script = """
from objdictgen.ui import objdictedit
objdictedit.main()
"""

os.makedirs("build", exist_ok=True)
with open("build/objdictedit.py", "w", encoding="utf-8") as f:
    f.write(script)

icon = basepath + "/src/objdictgen/img/networkedit.ico"

convert("packaging/objdictedit.ver.in", "build/objdictedit.ver")

a = Analysis(
    [basepath + '/build/objdictedit.py'],
    pathex=[],
    binaries=[],
    datas=[
        (basepath + "/src/objdictgen/img/*", "objdictgen/img"),
        (basepath + "/src/objdictgen/config/*.prf", "objdictgen/config"),
        (basepath + "/src/objdictgen/schema/*.json", "objdictgen/schema"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='objdictedit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version=basepath + '/build/objdictedit.ver',
)
