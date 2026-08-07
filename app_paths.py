"""
Where files live, both when running from source and inside a PyInstaller bundle.

Two different answers are needed:

  resource_path()  read-only files shipped with the app (bg.png, rootCA.pem).
                   PyInstaller unpacks those into sys._MEIPASS, and inside a
                   macOS .app that directory is not the working directory, so a
                   relative path like "./certificates/rootCA.pem" misses.

  user_data_dir()  files the app writes (config.json, credentials.json). The
                   bundle directory is read-only on macOS and lives in a temp
                   folder that gets wiped, so settings have to go to the user's
                   own application-support/AppData folder.
"""

import os
import sys

APP_DIR_NAME = "EmotivDrone"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_path(*parts: str) -> str:
    """Absolute path to a read-only file shipped alongside the code."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def user_data_dir() -> str:
    """Per-user directory for settings, created on first use."""
    if not is_frozen():
        # Running from a checkout: keep config next to the source, as before.
        return os.path.dirname(os.path.abspath(__file__))

    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")

    path = os.path.join(base, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path
