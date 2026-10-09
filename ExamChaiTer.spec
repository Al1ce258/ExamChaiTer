# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    *collect_data_files("rapidocr_onnxruntime"),
    *collect_data_files("pyttsx3"),
]

hiddenimports = [
    *collect_submodules("rapidocr_onnxruntime"),
    *collect_submodules("openai"),
    *collect_submodules("pyttsx3"),
    "win32com",
    "win32com.client",
    "pythoncom",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
]

excludes = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "matplotlib",
    "tkinter",
    "IPython",
    "jupyter",
]

a = Analysis(
    ["src/examchaiter/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="ExamChaiTer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/ExamChaiTer.ico",
    version="assets/version_info.txt",
)
