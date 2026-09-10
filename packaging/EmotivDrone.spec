# PyInstaller spec for the Tello BCI Controller.
#
# Build from the repository root:
#     pyinstaller packaging/EmotivDrone.spec --noconfirm
#
# Produces dist/EMOTIV Drone BCI/ on Windows and dist/EMOTIV Drone BCI.app on
# macOS. Both are unsigned.

import os
import sys

APP_NAME = "EMOTIV Drone BCI"
# SPECPATH is injected by PyInstaller and points at packaging/; the sources sit
# one level up. Deriving it this way keeps the build independent of the cwd.
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

# Built from assets/logo_white.png by packaging/make_icon.py, which the build
# workflow runs before PyInstaller. The source logo is white on transparent,
# which disappears against a light taskbar, so the icons sit on the app's own
# dark rounded square. None of them is checked in -- they are derived artwork,
# and a stale committed icon is worse than none -- so the build tolerates their
# absence rather than failing on a checkout where make_icon.py has not run.
ICON = os.path.join(SPECPATH, "app_icon.ico")
ICON_MAC = os.path.join(SPECPATH, "app_icon.icns")

datas = [
    (os.path.join(ROOT, "certificates", "rootCA.pem"), "certificates"),
    # The exe's own icon covers Explorer and the Start menu, but Qt draws the
    # title bar from setWindowIcon, which reads this .ico and picks its frame.
    *([(ICON, ".")] if os.path.exists(ICON) else []),
    (os.path.join(ROOT, "bg.png"), "."),
    # Branding artwork. Optional at runtime — brand_pixmap() returns None and
    # the chrome is simply not drawn — but a build without it looks unfinished.
    (os.path.join(ROOT, "assets"), "assets"),
]

# PyQt6 pulls in a lot it does not need here. Dropping the heavy optional
# modules keeps the bundle from ballooning and avoids Qt WebEngine, which needs
# signing help on macOS.
excludes = [
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineQuick",
    "PyQt6.Qt3DCore", "PyQt6.Qt3DRender", "PyQt6.QtQuick3D",
    "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtDesigner",
    "tkinter", "matplotlib", "PySide6", "PyQt5",
]

a = Analysis(
    [os.path.join(ROOT, "ui.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    # Imported lazily inside functions, so the dependency graph misses them.
    hiddenimports=["av", "pydispatch", "djitellopy"],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    icon=ICON if os.path.exists(ICON) else None,
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON_MAC if os.path.exists(ICON_MAC) else None,
        bundle_identifier="com.emotiv.dronebci",
        info_plist={
            "NSHighResolutionCapable": True,
            # The app talks to EMOTIV Cortex over localhost and to the Tello
            # over WiFi; macOS asks for these two before letting it.
            "NSLocalNetworkUsageDescription":
                "Connects to EMOTIV Cortex and to the Tello drone on your local network.",
            "NSCameraUsageDescription":
                "Displays the video stream coming from the Tello drone.",
            "CFBundleShortVersionString": "1.0.0",
        },
    )
