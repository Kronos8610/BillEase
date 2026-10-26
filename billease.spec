# -*- mode: python ; coding: utf-8 -*-
"""
Receta de empaquetado de BillEase.

    pip install pyinstaller
    pyinstaller billease.spec

Deja en `dist/BillEase/` el programa listo para copiar o para meter en el
instalador (`installer/billease.iss`).

Tres decisiones:

- **Un directorio, no un fichero único.** `--onefile` descomprime la
  aplicación entera en una carpeta temporal en cada arranque: tarda varios
  segundos y algunos antivirus lo miran con lupa. Una carpeta arranca al
  instante, y el instalador la esconde igual.
- **`app.qss` viaja con el programa.** Es un fichero de datos, no código: si
  no se incluye, la aplicación arranca sin estilos.
- **Sin consola.** `console=False` para que no se abra una ventana negra
  detrás. Los mensajes de arranque siguen yendo a la salida estándar para
  quien ejecute el `.exe` desde una terminal.
"""

from PyInstaller.utils.hooks import collect_submodules

bloque_cifrado = None

datos = [
    ("theme/app.qss", "theme"),      # la hoja de estilos
]

ocultos = [
    # Las migraciones se importan por nombre desde `data/migrations/__init__`,
    # así que PyInstaller las ve; se declaran igual para que un módulo nuevo
    # no se quede fuera sin avisar.
    *collect_submodules("data.migrations"),
    "argon2",
    # El cifrado de la base: sin esto el ejecutable arranca y no puede abrir
    # los datos de nadie.
    "argon2.low_level",
    "cryptography",
    "cryptography.hazmat.primitives.ciphers.aead",
    "reportlab.graphics.barcode",
]

a = Analysis(
    ["main_start.py"],
    pathex=[],
    binaries=[],
    datas=datos,
    hiddenimports=ocultos,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Lo que no se usa y abulta: PyQt6 trae un navegador entero.
    excludes=[
        "tkinter", "unittest", "pydoc", "pytest", "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets", "PyQt6.QtQuick", "PyQt6.QtQml",
        "PyQt6.QtMultimedia", "PyQt6.QtNetwork", "PyQt6.Qt3DCore",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=bloque_cifrado)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BillEase",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                 # sin ventana negra detrás
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/billease.ico" if __import__("pathlib").Path("assets/billease.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BillEase",
)
