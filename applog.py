"""A log file on disk, so a failure can be diagnosed after the fact.

Everything the app prints already goes to the in-window log pane, which is fine
while someone is watching it and useless the moment the window is closed — or
when the app is a packaged bundle with no console attached at all. This mirrors
the same stream to a file next to the user's settings.

The file lives in user_data_dir(), not beside the executable: the app directory
is read-only inside a macOS .app and lands in a temp folder that gets wiped.
"""

import os
import sys
import time
import traceback

from app_paths import user_data_dir

LOG_NAME = "emotiv-drone.log"
PREVIOUS_NAME = "emotiv-drone.previous.log"

# Big enough to hold a full session including Cortex's chatter, small enough to
# attach to a bug report. One rollover is kept, which covers "it broke, I
# restarted, now tell me what happened the first time".
MAX_BYTES = 4 * 1024 * 1024

_handle = None
_path = None


def log_path() -> str:
    """Absolute path of the current log file."""
    return _path or os.path.join(user_data_dir(), LOG_NAME)


def start() -> str:
    """Open the log file, rolling the previous one aside. Safe to call twice."""
    global _handle, _path
    if _handle is not None:
        return _path

    _path = os.path.join(user_data_dir(), LOG_NAME)
    try:
        if os.path.exists(_path) and os.path.getsize(_path) > MAX_BYTES:
            previous = os.path.join(user_data_dir(), PREVIOUS_NAME)
            if os.path.exists(previous):
                os.remove(previous)
            os.replace(_path, previous)
        # Line buffered: a crash must not swallow the lines explaining it.
        _handle = open(_path, "a", encoding="utf-8", errors="replace", buffering=1)
    except Exception:
        # Logging must never be the thing that stops the app starting.
        _handle = None
        return _path

    write("=" * 72)
    write(f"session started {time.strftime('%Y-%m-%d %H:%M:%S')}")
    write(f"python {sys.version.split()[0]} on {sys.platform}, "
          f"frozen={getattr(sys, 'frozen', False)}")
    return _path


def write(message: str) -> None:
    """Append one timestamped line. Never raises."""
    if _handle is None:
        return
    try:
        stamp = time.strftime("%H:%M:%S")
        for line in str(message).rstrip().splitlines() or [""]:
            _handle.write(f"{stamp}  {line}\n")
    except Exception:
        pass


def exception(context: str, exc: BaseException) -> None:
    """Record a caught exception with its traceback."""
    write(f"[error] {context}: {exc!r}")
    try:
        write("".join(traceback.format_exception(
            type(exc), exc, exc.__traceback__)))
    except Exception:
        pass


def install_excepthook() -> None:
    """Send anything that escapes to the log as well as the console.

    An unhandled exception in a packaged build otherwise vanishes: there is no
    console for the default hook to print to.
    """
    previous = sys.excepthook

    def hook(kind, value, tb):
        write("[fatal] unhandled exception")
        try:
            write("".join(traceback.format_exception(kind, value, tb)))
        except Exception:
            pass
        previous(kind, value, tb)

    sys.excepthook = hook


def close() -> None:
    global _handle
    if _handle is not None:
        write("session ended")
        try:
            _handle.close()
        except Exception:
            pass
        _handle = None
