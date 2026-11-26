# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller rhino2sw.spec  ->  dist/rhino2sw/rhino2sw.exe (+ cartella _internal)
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []
for pkg in ("OCP", "cadquery_ocp", "cadquery_ocp_proxy"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass
hiddenimports += collect_submodules("rhino2sw")
datas += [("assets/rhino2sw.ico", ".")]

a = Analysis(
    ["run_rhino2sw.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "vtk", "vtkmodules", "matplotlib", "numpy.tests", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtPdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="rhino2sw",
    icon="assets/rhino2sw.ico",
    console=False,            # nessuna finestra nera; il worker scrive il risultato su file JSON
    upx=False,
    version="assets/version_info.txt" if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="rhino2sw")
