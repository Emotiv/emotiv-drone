"""Record every motion frame to a CSV, so head drift can be measured.

The steering log answers "is a head turn reaching the drone" at one line a
second. It cannot answer "how far off centre does the headset sit when the
wearer holds still, and is that a fixed bias or a drift", because both live in
fractions of a degree between those lines.

So this writes every frame -- the raw quaternion, the angle derived from it,
and the heading that came out -- for the first minute of a session, starting
before calibration so the settling transient is in the file too. One minute at
64 Hz is under 4000 rows, and the file is overwritten each run: the point is to
have the last session's data already on disk when something looks wrong, not to
build an archive.
"""

import os
import time

from app_paths import user_data_dir

FILENAME = "motion-capture.csv"
PREVIOUS_NAME = "motion-capture.previous.csv"

HEADER = ("t_sec,q0,q1,q2,q3,calibrated,"
          "raw_angle_deg,smoothed_angle_deg,heading_deg\n")


class MotionCapture:
    """Writes motion frames to a CSV for a bounded window, then stops."""

    def __init__(self, seconds: float):
        self.seconds = float(seconds or 0.0)
        self._handle = None
        self._t0 = None
        self._done = self.seconds <= 0.0
        self.path = os.path.join(user_data_dir(), FILENAME)

    def _open(self) -> bool:
        try:
            # Roll the last one aside first. A capture worth analysing is
            # destroyed the moment the app is relaunched otherwise, and the
            # relaunch is usually the thing you do right after noticing the
            # problem you wanted the capture for. Same one-deep rollover the
            # log uses, so there is still exactly one file to hand over.
            if os.path.exists(self.path):
                previous = os.path.join(user_data_dir(), PREVIOUS_NAME)
                if os.path.exists(previous):
                    os.remove(previous)
                os.replace(self.path, previous)
        except Exception:
            pass
        try:
            self._handle = open(self.path, "w", encoding="utf-8", buffering=1)
            self._handle.write(HEADER)
        except Exception:
            # A capture failing must never take the flight down with it.
            self._handle = None
            self._done = True
            return False
        return True

    def write(self, w, x, y, z, calibrated, raw_deg, smooth_deg, heading_deg):
        """Record one frame. Silent no-op once the window has closed."""
        if self._done:
            return
        if self._handle is None and not self._open():
            return

        now = time.time()
        if self._t0 is None:
            self._t0 = now
        elapsed = now - self._t0
        if elapsed > self.seconds:
            self.close()
            return

        try:
            self._handle.write(
                f"{elapsed:.4f},{w:.6f},{x:.6f},{y:.6f},{z:.6f},"
                f"{1 if calibrated else 0},{raw_deg:.4f},"
                f"{smooth_deg:.4f},{heading_deg:.4f}\n")
        except Exception:
            self.close()

    def close(self):
        self._done = True
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None
