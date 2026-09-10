"""
Tello Drone BCI Controller – PyQt6 Dashboard
Flow: BCI Setup -> Test Controls -> Drone Setup -> Flight Dashboard
"""

import sys
import os
import time
import threading
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QGroupBox, QComboBox,
    QProgressBar, QScrollArea, QPlainTextEdit, QSlider, QStackedWidget,
    QSizePolicy, QGridLayout, QTabWidget, QDialog, QGraphicsOpacityEffect,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QObject, QRectF, QPointF, QSize
)
from PyQt6.QtGui import (
    QImage, QPixmap, QColor, QPalette, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPolygonF, QIcon,
)
import math
import random
from config_manager import ConfigManager
from app_paths import resource_path, window_icon_path
import leaderboard
import applog
import i18n
from i18n import t, bind, drone_action

# Pages in the QStackedWidget, in the order setup_page_* adds them. These used
# to be bare numbers scattered through the file, which is how the dashboard
# telemetry ended up gated on the EEG-check page instead of the dashboard.
PAGE_AUTH = 0
PAGE_HEADSET = 1
PAGE_PROFILE = 2
PAGE_EQ = 3
PAGE_TRAIN_NEUTRAL = 4
PAGE_TRAIN_PUSH = 5
PAGE_TEST = 6
PAGE_DRONE = 7
PAGE_DASHBOARD = 8
PAGE_BRAINMAP = 9
PAGE_GAMEOVER = 10
PAGE_LEADERBOARD = 11

# The real-drone path (Tello WiFi setup + flight dashboard) is built and wired
# but hidden: right now the product is the simulator. The pages stay registered
# so their indices and code paths are untouched — only the doors in are gone.
# Flip this to True to bring the whole flow back.
SHOW_REAL_DRONE = False

# Picking from a list of past profiles is off: each player creates their own,
# trains it, plays under that name, and the profile is dealt with at handoff.
# Listing everyone who came before just turns into clutter nobody prunes.
SHOW_PROFILE_LIST = False

# Whether motion tuning is reachable at all. The head-tilt and deadzone sliders
# are no longer built into any page; this decides whether the ⚙ Configurations
# dialog that still carries them is offered. Tuning these mid-demo is how a
# working setup gets broken between players, and Recenter covers the one
# adjustment that actually helps. Values still come from config.json.
SHOW_MOTION_TUNING = False

# Length of one competitive ring run. Long enough to recover from a bad start,
# short enough that a queue of people waiting their turn keeps moving.
RUN_SECONDS = 60

# Put every ring straight down the drone's nose instead of offset to one side.
#
# Steering is head yaw off the motion sensors, and on some machines it does not
# reach the drone at all -- see the [steer] lines in the log. Rings that need
# steering are unwinnable there: the player thinks forward, flies past the ring
# and never scores. Spawning them dead ahead keeps the demo playable on the one
# skill that does work, the trained mental command, while the yaw problem is
# still being tracked down.
#
# This is a stopgap and reads as one: the off-axis spawn below is intact, and
# flipping this back to False restores it in full. The game is easier this way
# -- forward is the only input needed -- which is the trade being made on
# purpose.
COINS_STRAIGHT_AHEAD = True


# Branding assets, all optional. Each is looked up once and cached; a missing
# file simply means that piece of chrome is not drawn, so the app runs from a
# fresh checkout before any artwork has been dropped in.
BRAND_DIR = "assets"
LOGO_FILE = "logo_white.png"          # company mark, light-on-dark, transparent
HERO_FILE = "hero_drone.png"          # backdrop for the headset screen

# The lockup stacks a drone mark over the wordmark, so it needs real height
# before the smaller line is legible. These are the two sizes it is used at.
LOGO_HEADER_H = 46
LOGO_HERO_H = 132

_ASSET_CACHE = {}


def brand_pixmap(filename: str):
    """QPixmap for a branding asset, or None when it is not installed."""
    if filename in _ASSET_CACHE:
        return _ASSET_CACHE[filename]

    pixmap = None
    candidates = [resource_path(BRAND_DIR, filename), resource_path(filename)]
    # Case-insensitive fallback: the artwork arrives named however it was
    # exported, and Windows does not care but a packaged Linux build would.
    brand_dir = resource_path(BRAND_DIR)
    if os.path.isdir(brand_dir):
        wanted = filename.lower()
        candidates += [os.path.join(brand_dir, f) for f in os.listdir(brand_dir)
                       if f.lower() == wanted]
    for candidate in candidates:
        if os.path.exists(candidate):
            loaded = QPixmap(candidate)
            if not loaded.isNull():
                pixmap = loaded
                break
    _ASSET_CACHE[filename] = pixmap
    return pixmap


# Headset artwork, keyed by the model prefix of a Cortex headset id such as
# "INSIGHT2-A3D208D9" or "EPOCX-3B7C11A2". Longest prefix wins, so INSIGHT2
# does not get swallowed by INSIGHT.
# The box each headset photo is fitted into on a device row. The artwork runs
# about 1.4:1, so the width binds and the height leaves a little air.
PRODUCT_SHOT = QSize(96, 72)

HEADSET_IMAGES = {
    "INSIGHT": "insight.png",
    "INSIGHT2": "insight.png",
    "EPOC": "EPOC.png",
    "EPOCX": "EPOC.png",
    "EPOCPLUS": "EPOC.png",
    "MN8": "MN8.png",
}


def headset_pixmap(headset_id: str):
    """Product shot for a headset id, or None when the model is unknown."""
    model = (headset_id or "").split("-")[0].upper()
    if not model:
        return None
    # Exact model first, then the longest prefix that matches, so an
    # unrecognised variant still shows the right family.
    if model in HEADSET_IMAGES:
        return brand_pixmap(HEADSET_IMAGES[model])
    for key in sorted(HEADSET_IMAGES, key=len, reverse=True):
        if model.startswith(key):
            return brand_pixmap(HEADSET_IMAGES[key])
    return None


def logo_label(height: int = 26, opacity: float = 1.0):
    """A QLabel carrying the company mark, or None if there is no logo file."""
    pixmap = brand_pixmap(LOGO_FILE)
    if pixmap is None:
        return None
    scaled = pixmap.scaledToHeight(
        height, Qt.TransformationMode.SmoothTransformation)
    label = QLabel()
    label.setPixmap(scaled)
    label.setFixedHeight(height)
    if opacity < 1.0:
        effect = QGraphicsOpacityEffect(label)
        effect.setOpacity(opacity)
        label.setGraphicsEffect(effect)
    return label


class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text):
        if text.strip():
            self.textWritten.emit(str(text))
    def flush(self):
        pass

STYLESHEET = """
QMainWindow { background-color: #0d1117; }
/* QDialog was never given a background, so Fusion painted the Settings and
   handoff dialogs light grey with near-invisible text. */
QDialog { background-color: #0d1117; }
QWidget { color: #e6edf3; font-family: 'Inter', 'SF Pro Text', 'Segoe UI', sans-serif; }
QGroupBox {
    border: 1px solid #30363d; border-radius: 10px;
    margin-top: 16px; padding: 18px 14px 14px 14px;
    background-color: #161b22; font-weight: bold; font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 14px; padding: 2px 8px; color: #58a6ff;
    background-color: #161b22; border-radius: 4px;
}
QLineEdit, QComboBox {
    background-color: #0d1117; border: 1px solid #30363d; border-radius: 8px;
    padding: 9px 12px; color: #e6edf3; font-size: 14px;
    selection-background-color: #1f6feb;
}
QLineEdit:hover, QComboBox:hover { border-color: #484f58; }
QLineEdit:focus, QComboBox:focus { border-color: #58a6ff; }
QLineEdit:disabled, QComboBox:disabled { color: #6e7681; background-color: #10151c; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background-color: #161b22; color: #e6edf3; border: 1px solid #30363d;
    border-radius: 8px; selection-background-color: #1f6feb; padding: 4px;
}
QPushButton {
    border-radius: 8px; padding: 10px 20px;
    font-weight: bold; font-size: 14px; color: #e6edf3;
    background-color: #21262d; border: 1px solid #30363d;
}
QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }
QPushButton:pressed { background-color: #1c2128; }
QPushButton:disabled { background-color: #161b22; color: #6e7681; border-color: #21262d; }
QPushButton#primaryBtn { background-color: #238636; border: 1px solid #2ea043; color: #ffffff; }
QPushButton#primaryBtn:hover { background-color: #2ea043; border-color: #3fb950; }
QPushButton#primaryBtn:disabled { background-color: #1a4220; color: #6e7681; border-color: #1a4220; }
QPushButton#heroBtn { background-color: #238636; border: 2px solid #3fb950; color: #ffffff;
                      font-size: 22px; font-weight: bold; border-radius: 12px; letter-spacing: 1px; }
QPushButton#heroBtn:hover { background-color: #2ea043; border-color: #56d364; }
QPushButton#heroBtn:disabled { background-color: #16281b; color: #6e7681; border-color: #21372a; }
QPushButton#ghostBtn { background-color: transparent; border: none; color: #6e7681;
                       font-size: 12px; font-weight: normal; padding: 6px 2px; }
QPushButton#ghostBtn:hover { color: #8b949e; text-decoration: underline; }
QPushButton#ghostBtn:pressed { color: #c9d1d9; }
QPushButton#dangerBtn { background-color: #da3633; border: 1px solid #f85149; color: #ffffff; }
QPushButton#dangerBtn:hover { background-color: #f85149; }
QPushButton#blueBtn { background-color: #1f6feb; border: 1px solid #388bfd; color: #ffffff; }
QPushButton#blueBtn:hover { background-color: #388bfd; }
QCheckBox { spacing: 9px; font-size: 14px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid #30363d; background: #0d1117; }
QCheckBox::indicator:hover { border-color: #58a6ff; }
QCheckBox::indicator:checked { background-color: #58a6ff; border-color: #58a6ff; }
QSlider::groove:horizontal { height: 6px; background: #21262d; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #58a6ff; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -6px 0; background: #e6edf3;
    border: 2px solid #58a6ff; border-radius: 9px;
}
QSlider::handle:horizontal:hover { background: #ffffff; }
QPlainTextEdit {
    background-color: #010409; color: #3fb950; border: 1px solid #30363d;
    border-radius: 8px; font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 12px;
    padding: 6px;
}
QLabel#titleLabel { font-size: 25px; font-weight: bold; color: #ffffff; }
QLabel#subtitleLabel { font-size: 14px; color: #8b949e; }
QLabel#statusBadge {
    background-color: #161b22; border: 1px solid #30363d; border-radius: 14px;
    padding: 7px 18px; font-size: 14px; font-weight: bold;
}
QProgressBar {
    border: 1px solid #30363d; border-radius: 5px; background-color: #0d1117;
    text-align: center; color: #e6edf3; height: 18px;
}
QProgressBar::chunk { background-color: #58a6ff; border-radius: 4px; }
/* A QScrollArea styles only its frame; the viewport widget inside keeps the
   default palette, which is how the leaderboard ended up on white. */
QScrollArea { background-color: #0b0f15; border: 1px solid #30363d; border-radius: 10px; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #30363d; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip {
    background-color: #1c2128; color: #e6edf3; border: 1px solid #58a6ff;
    border-radius: 6px; padding: 6px 8px; font-size: 12px;
}
"""

class VideoThread(QThread):
    frame_ready = pyqtSignal(QImage)
    status_update = pyqtSignal(str)

    def __init__(self, tello=None):
        super().__init__()
        self.tello = tello
        self._running = False
        self._av_container = None  # Direct PyAV container for color-correct decoding

    def run(self):
        self._running = True
        if self.tello:
            try:
                self.tello.streamon()
                self.status_update.emit(t("log.camera_started"))
            except Exception as e:
                self.status_update.emit(t("log.camera_error", detail=e))
                return

            # Open a direct PyAV container so we control the YUV→RGB conversion
            # instead of relying on djitellopy's to_image() which ignores VUI metadata.
            try:
                import av as _av
                udp_addr = self.tello.get_udp_video_address()
                # Use low-delay flags to prevent FFmpeg from buffering frames
                opts = {"fflags": "nobuffer", "flags": "low_delay"}
                self._av_container = _av.open(udp_addr, timeout=(10, None), options=opts)
                self.status_update.emit(t("log.pyav_active"))
            except Exception as e:
                self._av_container = None
                self.status_update.emit(t("log.pyav_failed", detail=e))

        if self._av_container:
            self._run_pyav_decode()
        else:
            self._run_fallback_decode()

    def _run_pyav_decode(self):
        """Decode via PyAV with explicit BT.709 / limited-range color conversion."""
        import av as _av

        try:
            for frame in self._av_container.decode(video=0):
                if not self._running:
                    break

                # Use to_ndarray with explicit format to force correct colorspace.
                # The Tello H.264 stream uses YUV420p; we convert to RGB24 here.
                # PyAV's reformatter applies the correct color matrix when we
                # set src_color_range and dst_color_range on the frame.
                frame.colorspace = _av.video.reformatter.Colorspace.ITU709
                rgb_frame = frame.to_ndarray(format='rgb24')

                h, w, ch = rgb_frame.shape
                # Apply limited-range (16-235) → full-range (0-255) stretch
                # to fix crushed blacks and washed-out highlights
                rgb_frame = self._stretch_limited_to_full(rgb_frame)
                img = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(img)
                
                # NOTE: No time.sleep() here! This is an iterator over a live stream.
                # Sleeping here causes the decode buffer to back up, creating massive lag.
                
        except Exception as e:
            print(f"[VideoThread] PyAV decode error, switching to fallback: {e}")
            self._av_container = None
            self._run_fallback_decode()

    def _run_fallback_decode(self):
        """Fallback: use djitellopy's built-in frame reader (to_image → RGB already)."""
        while self._running:
            if self.tello:
                try:
                    frame = self.tello.get_frame_read().frame
                    if frame is not None:
                        # djitellopy's to_image() already returns RGB via PIL,
                        # so do NOT apply cv2.cvtColor(BGR2RGB) — that swaps R↔B.
                        h, w, ch = frame.shape
                        img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                        self.frame_ready.emit(img)
                except Exception:
                    pass
            else:
                frame = self._generate_sim_frame()
                h, w, ch = frame.shape
                img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(img)
            time.sleep(0.033)

    @staticmethod
    def _stretch_limited_to_full(frame: np.ndarray) -> np.ndarray:
        """Rescale pixel values from limited range (16-235) to full range (0-255).
        
        H.264 streams typically use 'tv' / limited range. If the decoder outputs
        values in limited range but the display expects full range, blacks look
        gray and colors appear washed out. This stretches the range correctly.
        """
        # (x - 16) * 255 / (235 - 16), clamped to [0, 255]
        f = frame.astype(np.float32)
        f = (f - 16.0) * (255.0 / 219.0)
        return np.clip(f, 0, 255).astype(np.uint8)

    def stop(self):
        self._running = False
        if self.tello:
            try:
                self.tello.streamoff()
            except Exception:
                pass

    def _generate_sim_frame(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (13, 17, 23)
        for x in range(0, 640, 80): frame[:, x:x+1] = (48, 54, 61)
        for y in range(0, 480, 80): frame[y:y+1, :] = (48, 54, 61)
        cv2.line(frame, (300, 240), (340, 240), (88, 166, 255), 2)
        cv2.line(frame, (320, 220), (320, 260), (88, 166, 255), 2)
        cv2.circle(frame, (320, 240), 30, (88, 166, 255), 1)
        cv2.putText(frame, "SIMULATION MODE", (210, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (88, 166, 255), 2)
        return frame


class DroneSimulatorWidget(QWidget):
    """Third-person view of a virtual drone.

    Two modes, because the two screens that use it want opposite things:

      "game"      the live test screen — collectible rings, score, speed. Give
                  the user a reason to keep flying around.
      "training"  the mental-command recording screens — no rings, no score, no
                  scoreboard. Chasing a target while trying to hold a steady
                  mental state is exactly the wrong thing to ask for, and the
                  EEG picks up that split attention. Just the drone and a cue
                  for the action being recorded.
    """

    GAME = "game"
    TRAINING = "training"

    def __init__(self, main_app=None, parent=None, mode: str = GAME):
        super().__init__(parent)
        self.main_app = main_app
        self.mode = mode
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.drone_x = 0.0
        self.drone_y = 20.0
        self.drone_z = 0.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.speed = 0.0

        self.score = 0
        self.coins = []
        self.coin_counter = 1
        self.particles = []
        self.combo_flash = 0.0

        # A timed run, not free flight. Outside a run the drone still flies —
        # that is the practice mode — but no rings spawn and nothing scores.
        self.run_active = False
        self.time_left = 0.0
        # Run length, kept so overlays can work out how far in we are.
        self._run_seconds = 0.0

        # "Get Ready!" / 3 / 2 / 1 / "Go!" before a timed run. None when idle.
        self.countdown_caption = None
        self.countdown_value = None

        # Which action the user is recording right now; drives the on-screen cue.
        self.training_cue = None

        self._phase = 0.0          # propeller spin / idle bob
        self._idle_bob = 0.0

        from PyQt6.QtGui import QPixmap
        self.bg_image = QPixmap(resource_path("bg.png"))

        # Own animation clock. Without it the neutral training screen would be a
        # frozen still — nothing calls update_rc there.
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._animate)

    # ── Animation lifecycle ──────────────────────────────────────────────────
    def showEvent(self, event):
        super().showEvent(event)
        self._anim.start(33)  # ~30 FPS

    def hideEvent(self, event):
        super().hideEvent(event)
        self._anim.stop()

    def _animate(self):
        self._phase += 0.55
        self._idle_bob += 0.045
        self.combo_flash = max(0.0, self.combo_flash - 0.04)

        for coin in self.coins:
            coin[3] = (coin[3] + 3) % 360

        # Particles: rise, drift outward, fade.
        alive = []
        for p in self.particles:
            p["life"] -= 0.035
            if p["life"] > 0:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["z"] += p["vz"]
                p["vy"] -= 0.25
                alive.append(p)
        self.particles = alive

        self.update()

    def set_training_cue(self, cue):
        """'neutral', 'push' or None — shown as a hint over the scene."""
        self.training_cue = cue
        self.update()

    def set_countdown(self, caption, value):
        """Show (or clear, with None) the pre-run countdown over the scene."""
        self.countdown_caption = caption
        self.countdown_value = value
        self.update()

    def start_run(self, seconds: int):
        """Begin a timed run: clean slate, first ring in the air."""
        self.score = 0
        self.coins = []
        self.coin_counter = 1
        self.particles = []
        self.combo_flash = 0.0
        self.run_active = True
        self.time_left = float(seconds)
        self._run_seconds = float(seconds)
        self.countdown_caption = None
        self.countdown_value = None
        self.reset_flight()
        self.spawn_coin()
        self.update()

    def end_run(self):
        """Stop scoring and clear the field, leaving the final score readable."""
        self.countdown_caption = None
        self.countdown_value = None
        self.run_active = False
        self.time_left = 0.0
        self.coins = []
        self.update()

    def set_time_left(self, seconds: float):
        self.time_left = max(0.0, float(seconds))
        self.update()

    def reset_flight(self):
        """Put the drone back at the origin between training takes."""
        self.drone_x = self.drone_z = 0.0
        self.drone_y = 20.0
        self.yaw = self.pitch = self.roll = 0.0
        self.speed = 0.0
        self.particles.clear()
        self.update()

    # ── Simulation ───────────────────────────────────────────────────────────
    def spawn_coin(self):
        rad = math.radians(self.yaw)
        dist = random.uniform(150, 400)
        # Sideways displacement from the drone's heading -- the part that has
        # to be steered out. Zero puts the ring dead ahead.
        offset = 0.0 if COINS_STRAIGHT_AHEAD else random.uniform(-120, 120)

        # Forward vector is (sin, -cos), Right vector is (cos, sin)
        cx = self.drone_x + math.sin(rad) * dist + math.cos(rad) * offset
        cz = self.drone_z - math.cos(rad) * dist + math.sin(rad) * offset
        if COINS_STRAIGHT_AHEAD:
            # Height is worth keeping some variety in -- it still looks like a
            # course rather than a corridor -- but it has to stay inside the
            # collection radius on its own, since nothing the player can do
            # changes altitude. The full 15-80 range puts a ring 60 units above
            # a drone that never leaves y=20, which eats most of that radius.
            cy = self.drone_y + random.uniform(-8.0, 22.0)
        else:
            cy = random.uniform(15, 80)

        self.coins.append([cx, cy, cz, random.uniform(0, 360), self.coin_counter])
        self.coin_counter += 1

    def _burst(self, x, y, z):
        """Confetti where a ring was collected."""
        for _ in range(18):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1.5, 5.0)
            self.particles.append({
                "x": x, "y": y, "z": z,
                "vx": math.cos(angle) * speed,
                "vy": random.uniform(2.0, 6.0),
                "vz": math.sin(angle) * speed,
                "life": 1.0,
                "hue": random.choice(["#f1c40f", "#ffd966", "#ffffff", "#58a6ff"]),
            })

    def update_rc(self, lr, fb, ud, yaw, heading=None):
        speed_factor = 0.8
        rot_factor = 0.15

        if heading is None:
            # No head tracking behind this call -- the training screens drive
            # the drone forward for show and never steer it.
            self.yaw += yaw * rot_factor
        else:
            # Absolute: the head is pointing somewhere and so is the drone.
            # Nothing accumulates, so a steady head is a steady heading.
            self.yaw = heading

        # Dynamic pitch and roll based on joystick inputs to make it look alive
        self.pitch = -fb * 0.3
        self.roll = -lr * 0.3

        rad = math.radians(self.yaw)
        # Tello fb forward is +Z in our local coords maybe? Let's say Z is backward, so -Z is forward
        dz = -fb * math.cos(rad) * speed_factor + lr * math.sin(rad) * speed_factor
        dx = fb * math.sin(rad) * speed_factor + lr * math.cos(rad) * speed_factor
        dy = ud * speed_factor

        self.drone_x += dx
        self.drone_y += dy
        self.drone_z += dz
        self.speed = math.sqrt(dx * dx + dy * dy + dz * dz)

        # Bounding box for altitude only (infinite X and Z!)
        self.drone_y = max(5, min(1000, self.drone_y))

        # Coin collection logic — game mode only.
        if self.mode == self.GAME and self.run_active:
            collected = []
            for coin in self.coins:
                cx, cy, cz, rot, num = coin
                dist = math.sqrt((self.drone_x - cx)**2 + (self.drone_y - cy)**2 + (self.drone_z - cz)**2)
                if dist < 100:  # Huge hitbox for easier collection
                    collected.append(coin)
                    self.score += 10
                    self.combo_flash = 1.0
                    self._burst(cx, cy, cz)

            for c in collected:
                self.coins.remove(c)
                self.spawn_coin()

        self.update()

    def rotate_3d(self, x, y, z, pitch, yaw, roll):
        p, yw, r = math.radians(pitch), math.radians(yaw), math.radians(roll)
        # Roll (Z axis)
        x1 = x * math.cos(r) - y * math.sin(r)
        y1 = x * math.sin(r) + y * math.cos(r)
        z1 = z
        # Pitch (X axis)
        x2 = x1
        y2 = y1 * math.cos(p) - z1 * math.sin(p)
        z2 = y1 * math.sin(p) + z1 * math.cos(p)
        # Yaw (Y axis)
        x3 = x2 * math.cos(yw) - z2 * math.sin(yw)
        y3 = y2
        z3 = x2 * math.sin(yw) + z2 * math.cos(yw)
        return x3, y3, z3

    def project(self, x, y, z):
        # Chase camera positioning
        cam_dist = 250
        cam_height = 80
        rad = math.radians(self.yaw)
        
        # Position camera behind the drone
        cx = self.drone_x - math.sin(rad) * cam_dist
        cy = self.drone_y + cam_height
        cz = self.drone_z + math.cos(rad) * cam_dist
        
        # Translate to camera space
        x -= cx; y -= cy; z -= cz
        
        # Apply camera yaw (counter-rotate to look exactly in the direction the drone is facing)
        cam_yaw = -rad
        x1 = x * math.cos(cam_yaw) - z * math.sin(cam_yaw)
        z1 = x * math.sin(cam_yaw) + z * math.cos(cam_yaw)
        
        # Camera pitch (look down by 5 degrees for a better horizon view)
        cam_pitch = math.radians(5)
        y_cam = y * math.cos(cam_pitch) - z1 * math.sin(cam_pitch)
        z_cam = y * math.sin(cam_pitch) + z1 * math.cos(cam_pitch)
        
        # Perspective projection
        f = 400
        z_depth = z_cam if z_cam < -1 else -1 # Prevent div by zero
        
        px = (x1 * f) / abs(z_depth) + self.width() / 2
        py = (-y_cam * f) / abs(z_depth) + self.height() / 2 # Invert Y for screen coords
        return px, py, abs(z_depth)

    # ── Rendering ────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # True mathematical 3D horizon for the 5 degree camera pitch
        horizon_y = int(-math.tan(math.radians(5)) * 400 + self.height() / 2)

        self._paint_sky(painter, horizon_y)
        self._paint_ground(painter, horizon_y)
        if self.mode == self.GAME and self.run_active:
            self._paint_coins(painter)
        self._paint_particles(painter)
        self._paint_drone(painter)
        self._paint_training_cue(painter)
        self._paint_hud(painter)
        self._paint_mental_command(painter)

    def _paint_sky(self, painter, horizon_y):
        sky = QLinearGradient(0, 0, 0, max(horizon_y, 1))
        sky.setColorAt(0.0, QColor("#070b14"))
        sky.setColorAt(0.55, QColor("#132038"))
        sky.setColorAt(1.0, QColor("#2b4468"))
        painter.fillRect(0, 0, self.width(), max(horizon_y, 0), QBrush(sky))

        # Mountains pan as you yaw (parallax effect)
        if not self.bg_image.isNull():
            scaled_bg = self.bg_image.scaledToHeight(
                self.height(), Qt.TransformationMode.SmoothTransformation)
            sw = scaled_bg.width()
            offset_x = int(((self.yaw % 360) / 360.0) * sw * 2.0) % sw
            painter.setOpacity(0.85)
            curr_x = -offset_x
            while curr_x < self.width():
                painter.drawPixmap(curr_x, 0, scaled_bg)
                curr_x += sw
            painter.setOpacity(1.0)

        # Warm haze right at the horizon so sky and ground do not butt together
        haze = QLinearGradient(0, horizon_y - 60, 0, horizon_y + 10)
        haze.setColorAt(0.0, QColor(88, 166, 255, 0))
        haze.setColorAt(1.0, QColor(120, 180, 255, 70))
        painter.fillRect(0, horizon_y - 60, self.width(), 70, QBrush(haze))

    def _paint_ground(self, painter, horizon_y):
        ground = QLinearGradient(0, horizon_y, 0, self.height())
        ground.setColorAt(0.0, QColor("#1a2430"))
        ground.setColorAt(1.0, QColor("#080b10"))
        painter.fillRect(0, horizon_y, self.width(),
                         self.height() - horizon_y, QBrush(ground))

        # Infinite sliding floor grid centered on the drone. Lines fade with
        # distance instead of all being the same flat grey — that alone is most
        # of the depth cue.
        grid_size = 800
        step = 40
        start_x = int(self.drone_x // step) * step - grid_size // 2
        start_z = int(self.drone_z // step) * step - grid_size // 2

        def grid_line(ax, az, bx, bz):
            p1x, p1y, d1 = self.project(ax, 0, az)
            p2x, p2y, d2 = self.project(bx, 0, bz)
            depth = (d1 + d2) / 2
            alpha = int(max(0, min(150, 26000 / (depth + 60) - 20)))
            if alpha <= 2:
                return
            painter.setPen(QPen(QColor(88, 166, 255, alpha), 1))
            painter.drawLine(int(p1x), int(p1y), int(p2x), int(p2y))

        for i in range(0, grid_size + 1, step):
            grid_line(start_x + i, start_z, start_x + i, start_z + grid_size)
            grid_line(start_x, start_z + i, start_x + grid_size, start_z + i)

        # Pool of light directly under the drone
        gx, gy, gd = self.project(self.drone_x, 0, self.drone_z)
        if gd > 1.0:
            r = max(12, int(9000 / (gd + 100)))
            glow = QRadialGradient(QPointF(gx, gy), r)
            glow.setColorAt(0.0, QColor(88, 166, 255, 60))
            glow.setColorAt(1.0, QColor(88, 166, 255, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(gx, gy), r, r * 0.45)

    def _paint_coins(self, painter):
        for cx, cy, cz, rot, num in self.coins:
            px, py, depth = self.project(cx, cy, cz)
            if depth <= 1.0:
                continue  # behind the camera

            size = max(10, int(12000 / (depth + 100)))
            bounce = math.sin(math.radians(rot)) * 10
            py += bounce * (400 / (depth + 100))

            # Tether line to the ground so its position reads in 3D
            gx, gy, g_depth = self.project(cx, 0, cz)
            if g_depth > 1.0:
                painter.setPen(QPen(QColor(243, 156, 18, 90), 1, Qt.PenStyle.DotLine))
                painter.drawLine(int(px), int(py), int(gx), int(gy))

            # Halo
            halo = QRadialGradient(QPointF(px, py), size * 1.5)
            halo.setColorAt(0.0, QColor(241, 196, 15, 110))
            halo.setColorAt(1.0, QColor(241, 196, 15, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QPointF(px, py), size * 1.5, size * 1.5)

            # The ring itself, squashed as it spins for a bit of 3D
            squash = abs(math.cos(math.radians(rot))) * 0.75 + 0.25
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#f1c40f"), max(2, size // 6)))
            painter.drawEllipse(QPointF(px, py), size / 2 * squash, size / 2)
            painter.setPen(QPen(QColor(255, 240, 180, 200), max(1, size // 14)))
            painter.drawEllipse(QPointF(px, py), size / 2.6 * squash, size / 2.6)

            # Number, only while the ring is wide enough to hold it
            if squash > 0.55 and size > 18:
                painter.setPen(QColor("#ffe9a8"))
                font = painter.font()
                font.setPointSize(max(6, size // 3))
                font.setBold(True)
                painter.setFont(font)
                text = str(num)
                metrics = painter.fontMetrics()
                painter.drawText(int(px - metrics.horizontalAdvance(text) / 2),
                                 int(py + metrics.capHeight() / 2), text)

    def _paint_particles(self, painter):
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.particles:
            px, py, depth = self.project(p["x"], p["y"], p["z"])
            if depth <= 1.0:
                continue
            size = max(2, int(2200 / (depth + 100)))
            color = QColor(p["hue"])
            color.setAlpha(int(230 * p["life"]))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(px, py), size / 2, size / 2)

    def _paint_drone(self, painter):
        arms = [
            (25, 0, -25, "#ff7b72"),   # Front Right
            (-25, 0, -25, "#ff7b72"),  # Front Left
            (25, 0, 25, "#58a6ff"),    # Back Right
            (-25, 0, 25, "#58a6ff"),   # Back Left
        ]

        # A hover bob keeps the drone alive even when it is not being flown.
        bob = math.sin(self._idle_bob) * 1.6
        cx, cy, cz = self.rotate_3d(0, 0, 0, self.pitch, self.yaw, self.roll)
        c_px, c_py, c_depth = self.project(
            cx + self.drone_x, cy + self.drone_y + bob, cz + self.drone_z)

        # Ground shadow, tighter and darker the lower the drone flies
        gx, gy, gd = self.project(self.drone_x, 0, self.drone_z)
        if gd > 1.0:
            altitude_factor = max(0.25, min(1.0, 60.0 / max(self.drone_y, 1)))
            sr = max(6, int(5200 / (gd + 100))) * altitude_factor
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, int(120 * altitude_factor)))
            painter.drawEllipse(QPointF(gx, gy), sr, sr * 0.4)

        # Altitude tether
        painter.setPen(QPen(QColor(88, 166, 255, 90), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(c_px), int(c_py), int(gx), int(gy))

        for ax, ay, az, color in arms:
            rx, ry, rz = self.rotate_3d(ax, ay, az, self.pitch, self.yaw, self.roll)
            px, py, depth = self.project(
                rx + self.drone_x, ry + self.drone_y + bob, rz + self.drone_z)

            painter.setPen(QPen(QColor("#8b949e"), max(2, int(900 / (depth + 100)))))
            painter.drawLine(int(c_px), int(c_py), int(px), int(py))

            size = max(4, int(6000 / (depth + 100)))
            centre = QPointF(px, py)

            # Motor housing
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(centre, size * 0.22, size * 0.22)

            # Spinning blade disc: a faint filled circle plus two arcs that
            # actually rotate, which reads as motion far better than a dot.
            disc = QColor(color)
            disc.setAlpha(45)
            painter.setBrush(disc)
            painter.drawEllipse(centre, size * 0.6, size * 0.6)

            blade = QColor(color)
            blade.setAlpha(190)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(blade, max(1, size // 8)))
            rect = QRectF(px - size * 0.6, py - size * 0.6, size * 1.2, size * 1.2)
            spin = int(self._phase * 16) % 360
            painter.drawArc(rect, spin * 16, 70 * 16)
            painter.drawArc(rect, (spin + 180) * 16, 70 * 16)

        # Body: rounded, with a nose marker so heading is readable
        b = max(6, int(9000 / (c_depth + 100)))
        body = QLinearGradient(c_px - b / 2, c_py - b / 2, c_px + b / 2, c_py + b / 2)
        body.setColorAt(0.0, QColor("#f0f6fc"))
        body.setColorAt(1.0, QColor("#8b949e"))
        painter.setPen(QPen(QColor("#0d1117"), 1))
        painter.setBrush(QBrush(body))
        painter.drawRoundedRect(QRectF(c_px - b / 2, c_py - b / 2, b, b), b / 4, b / 4)

        nx, ny, nz = self.rotate_3d(0, 0, -34, self.pitch, self.yaw, self.roll)
        npx, npy, _ = self.project(
            nx + self.drone_x, ny + self.drone_y + bob, nz + self.drone_z)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3fb950"))
        painter.drawEllipse(QPointF(npx, npy), max(2, b / 6), max(2, b / 6))

    def _paint_training_cue(self, painter):
        """Calm, non-competitive hint about the action being recorded."""
        if self.mode != self.TRAINING or not self.training_cue:
            return

        cx = self.width() / 2
        cy = self.height() / 2
        pulse = (math.sin(self._idle_bob * 2.2) + 1) / 2

        if self.training_cue == "neutral":
            # Breathing ring: something to settle your eyes on, nothing to chase.
            radius = 70 + pulse * 18
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(63, 185, 80, int(70 + pulse * 90)), 2))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)
            painter.setPen(QPen(QColor(63, 185, 80, 40), 1))
            painter.drawEllipse(QPointF(cx, cy), radius * 1.35, radius * 1.35)
            label, colour = t("cue.neutral"), QColor("#3fb950")
        else:
            # Chevrons marching away from the viewer.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(3):
                offset = ((self._idle_bob * 26) + i * 34) % 102
                alpha = int(200 * (1 - offset / 102))
                painter.setPen(QPen(QColor(88, 166, 255, alpha), 3))
                y = cy + 60 - offset
                painter.drawPolyline(QPolygonF([
                    QPointF(cx - 34, y + 16), QPointF(cx, y), QPointF(cx + 34, y + 16),
                ]))
            label, colour = t("cue.push"), QColor("#58a6ff")

        font = painter.font()
        font.setPointSize(13)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(label)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(13, 17, 23, 170))
        painter.drawRoundedRect(QRectF(cx - tw / 2 - 14, self.height() - 54,
                                       tw + 28, 30), 15, 15)
        painter.setPen(colour)
        painter.drawText(int(cx - tw / 2), self.height() - 33, label)

    def _paint_hud(self, painter):
        font = painter.font()
        font.setBold(True)

        if self.mode == self.GAME:
            # Score card. It swells briefly on pickup.
            swell = 1.0 + self.combo_flash * 0.25
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(13, 17, 23, 165))
            painter.drawRoundedRect(QRectF(14, 14, 168, 62), 10, 10)
            painter.setPen(QPen(QColor(241, 196, 15, int(60 + 160 * self.combo_flash)), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(14, 14, 168, 62), 10, 10)

            font.setPointSize(int(17 * swell))
            painter.setFont(font)
            painter.setPen(QColor("#f1c40f"))
            painter.drawText(28, 44, t("sim.score", score=self.score))

            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QColor("#8b949e"))
            painter.drawText(28, 66, t("sim.readout",
                                       alt=int(self.drone_y),
                                       spd=f"{self.speed:.1f}"))
            self._paint_timer(painter)
            self._paint_controls_hint(painter)
            self._paint_countdown(painter)
        else:
            # Training: altitude only, small and out of the way.
            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QColor(139, 148, 158, 200))
            painter.drawText(20, 30, t("sim.altitude", alt=int(self.drone_y)))

        if self.isFullScreen():
            font.setPointSize(11)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 150))
            painter.drawText(self.width() - 210, 30, t("sim.esc_hint"))

    def _paint_countdown(self, painter):
        """Big centred 3 / 2 / 1 / Go! over a dimmed scene."""
        if self.countdown_value is None:
            return

        painter.fillRect(self.rect(), QColor(2, 5, 10, 150))

        font = painter.font()
        font.setBold(True)

        if self.countdown_caption:
            font.setPointSize(20)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            painter.setPen(QColor("#8b949e"))
            painter.drawText(
                int(self.width() / 2 - metrics.horizontalAdvance(self.countdown_caption) / 2),
                int(self.height() / 2 - 58), self.countdown_caption)

        # "Go!" is a word and the digits are digits; both want to look like the
        # same beat, so the size is chosen per-length rather than fixed.
        text = str(self.countdown_value)
        font.setPointSize(96 if len(text) <= 2 else 64)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        colour = QColor("#3fb950") if not text.isdigit() else QColor("#f1c40f")
        painter.setPen(colour)
        painter.drawText(
            int(self.width() / 2 - metrics.horizontalAdvance(text) / 2),
            int(self.height() / 2 + metrics.capHeight() / 2 + 10), text)

    def _paint_controls_hint(self, painter):
        """The two controls, along the bottom edge.

        The side panel explaining them is not on screen in fullscreen, which is
        exactly where a first-timer ends up. Fades out once the run is properly
        under way so it is not competing with the rings for attention.
        """
        if self.countdown_value is not None:
            return
        if self.run_active and self.time_left is not None:
            elapsed = self._run_seconds - self.time_left
            if elapsed > 12:
                return
            alpha = 235 if elapsed < 8 else int(235 * (12 - elapsed) / 4)
        else:
            alpha = 235
        if alpha <= 0:
            return

        forward = ""
        if self.main_app is not None:
            forward = self.main_app.forward_command_label()
        lines = [t("howto.overlay_steer")]
        if forward:
            lines.append(t("howto.overlay_forward", action=forward))
        if not self.run_active:
            # Only before the clock starts: once rings are on screen, what they
            # are for stops being a question.
            lines.append(t("howto.overlay_rings"))

        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        width = max(metrics.horizontalAdvance(line) for line in lines) + 36
        height = len(lines) * (metrics.height() + 4) + 16
        x = self.width() / 2 - width / 2
        bottom_reserved = 38 if not self.run_active else 16
        y = self.height() - height - bottom_reserved

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(13, 17, 23, int(alpha * 0.62)))
        painter.drawRoundedRect(QRectF(x, y, width, height), 12, 12)

        painter.setPen(QColor(230, 237, 243, alpha))
        for i, line in enumerate(lines):
            painter.drawText(
                int(self.width() / 2 - metrics.horizontalAdvance(line) / 2),
                int(y + 16 + i * (metrics.height() + 4)),
                line)

    def _paint_timer(self, painter):
        """Countdown clock, top-centre. Turns red and pulses in the last 10s."""
        if not self.run_active:
            # The countdown has already taken over the screen; telling the
            # player to press Start Run underneath it is stale advice.
            if self.countdown_value is not None:
                return
            painter.setPen(QColor(139, 148, 158, 190))
            font = painter.font()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            text = t("game.idle_hint")
            metrics = painter.fontMetrics()
            painter.drawText(int(self.width() / 2 - metrics.horizontalAdvance(text) / 2),
                             self.height() - 22, text)
            return

        seconds = int(math.ceil(self.time_left))
        urgent = seconds <= 10
        if urgent:
            # Pulse on the beat of the seconds, so the panic is legible.
            pulse = abs(math.sin(self._idle_bob * 3.0))
            colour = QColor(248, 81, 73)
            ring = QColor(248, 81, 73, int(120 + 135 * pulse))
        else:
            colour = QColor("#e6edf3")
            ring = QColor(88, 166, 255, 110)

        text = t("game.timer", seconds=seconds)
        font = painter.font()
        font.setPointSize(20 if not urgent else 23)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(text)
        cx = self.width() / 2
        rect = QRectF(cx - tw / 2 - 20, 14, tw + 40, 46)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(13, 17, 23, 185))
        painter.drawRoundedRect(rect, 23, 23)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(ring, 2))
        painter.drawRoundedRect(rect, 23, 23)

        painter.setPen(colour)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_mental_command(self, painter):
        if not (self.main_app and self.main_app.drone_client
                and getattr(self.main_app.drone_client, 'drone', None)):
            return

        action = getattr(self.main_app.drone_client.drone, 'last_executed_action', None)
        action_time = getattr(self.main_app.drone_client.drone, 'last_action_time', 0.0)
        elapsed = time.time() - action_time
        if not action or elapsed >= 2.0:
            return

        alpha = int(255 * (1.0 - elapsed / 2.0))
        if alpha <= 0:
            return

        text = t("sim.mental_command", action=drone_action(action).upper())
        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(text)
        th = metrics.capHeight()

        bx = self.width() // 2 - tw // 2 - 22
        bw = tw + 44
        bh = th + 24
        rect = QRectF(bx, 20, bw, bh)

        # It slides down a touch as it fades, so repeated commands read as
        # separate events instead of one flicker. save/restore rather than
        # resetTransform, which would also drop the device pixel ratio.
        painter.save()
        painter.translate(0, (1.0 - alpha / 255) * 6)
        painter.setBrush(QColor(31, 111, 235, alpha // 3))
        painter.setPen(QPen(QColor(88, 166, 255, alpha), 2))
        painter.drawRoundedRect(rect, bh / 2, bh / 2)
        painter.setPen(QColor(255, 255, 255, alpha))
        painter.drawText(int(bx + 22), int(20 + bh - 9), text)
        painter.restore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            if self.main_app:
                self.main_app.toggle_fullscreen()


def clear_grid(grid):
    """Empty a QGridLayout, unbinding any translated labels it held."""
    while grid.count():
        item = grid.takeAt(0)
        w = item.widget()
        if w is not None:
            i18n.unbind(w)
            # setParent(None) before deleteLater: deletion is deferred to the
            # event loop, and until it runs the widget is still drawn at its old
            # place — rebuilding a grid straight away stacked the new rows on
            # top of the old ones.
            w.setParent(None)
            w.deleteLater()


def add_board_row(grid, row, rank, entry, highlight):
    """One leaderboard line. Shared so the windowed and fullscreen results
    cannot drift apart visually."""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    cells = [
        medals.get(rank, f"{rank}."),
        entry.get("name", "?"),
        str(entry.get("score", 0)),
        t("game.coins_short", coins=entry.get("coins", 0)),
    ]
    widths = [46, None, 70, 90]
    colour = "#f1c40f" if highlight else ("#e6edf3" if rank <= 3 else "#8b949e")
    weight = "bold" if highlight or rank <= 3 else "normal"

    for col, (text, width) in enumerate(zip(cells, widths)):
        lbl = QLabel(text)
        if width:
            lbl.setFixedWidth(width)
        if col == 2:
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        style = (f"font-size: 14px; color: {colour}; font-weight: {weight};"
                 "padding: 6px 8px;")
        if highlight:
            if col == 0:
                style += ("background-color: #2b2109; border-top-left-radius: 6px;"
                          "border-bottom-left-radius: 6px;")
            elif col == len(cells) - 1:
                style += ("background-color: #2b2109; border-top-right-radius: 6px;"
                          "border-bottom-right-radius: 6px;")
            else:
                style += "background-color: #2b2109;"
        lbl.setStyleSheet(style)
        grid.addWidget(lbl, row, col)


def contact_percent(cq_list, overall_idx=None, keep_idx=None):
    """Overall electrode contact, 0-100, or None when nothing has arrived yet.

    Cortex ships an OVERALL column in the contact-quality stream that is already
    a percentage; prefer it. Without it, average the per-electrode 0-4 grades.
    Deliberately not `signal`, which is the wireless link to the dongle and says
    nothing about whether the electrodes are touching anyone's head.
    """
    if not cq_list:
        return None
    if overall_idx is not None and overall_idx < len(cq_list):
        try:
            return max(0.0, min(100.0, float(cq_list[overall_idx])))
        except (TypeError, ValueError):
            pass
    grades = ([cq_list[i] for i in keep_idx if i < len(cq_list)]
              if keep_idx is not None else list(cq_list))
    if not grades:
        return None
    return max(0.0, min(100.0, sum(grades) / len(grades) / 4.0 * 100.0))


def contact_grade(percent):
    """(translation key, colour) for a contact percentage. Same bands as
    emotiv-brain-light, so the two apps agree on what "good" means."""
    if percent is None:
        return "quality.unknown_state", "#8b949e"
    if percent >= 80:
        return "quality.good", "#3fb950"
    if percent >= 50:
        return "quality.fair", "#e3a01a"
    return "quality.poor", "#da3633"


def congratulation(rank: int, total: int):
    """Message, colour and whether this finish deserves confetti.

    Shared by the windowed result page and the fullscreen one so a player is
    congratulated in the same words either way. Top three gets the confetti;
    everyone else still gets told where they came.
    """
    if rank <= 0:
        return "", "#8b949e", False
    if rank == 1:
        key = "game.congrats_only" if total <= 1 else "game.congrats_first"
        return t(key), "#f1c40f", True
    if rank <= 3:
        return t("game.congrats_podium", rank=i18n.ordinal(rank)), "#f1c40f", True
    return (t("game.congrats_ranked", rank=i18n.ordinal(rank), total=total),
            "#58a6ff", False)


class HeroBackdrop(QWidget):
    """A page background: artwork bottom-right, dimmed, behind its content.

    Used on the headset screen so the first thing on screen says "drone
    simulator" rather than "configuration form". Draws nothing at all when the
    artwork is missing, so the page still works without it.
    """

    def __init__(self, filename: str, parent=None, opacity: float = 0.16,
                 coverage: float = 0.88):
        super().__init__(parent)
        self.pixmap = brand_pixmap(filename)
        self.opacity = opacity
        self.coverage = coverage

    def paintEvent(self, event):
        if self.pixmap is None or self.width() < 2 or self.height() < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(self.opacity)

        # Fit inside the page rather than cropping: the artwork is symmetric,
        # so losing one side to a bleed looks like a mistake rather than a
        # deliberate crop. Centred, and never upscaled past its own size.
        avail_w = int(self.width() * self.coverage)
        avail_h = int(self.height() * self.coverage)
        scaled = self.pixmap.scaled(
            min(avail_w, self.pixmap.width() * 2),
            min(avail_h, self.pixmap.height() * 2),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap((self.width() - scaled.width()) // 2,
                           (self.height() - scaled.height()) // 2,
                           scaled)


class ConfettiOverlay(QWidget):
    """A burst of falling confetti over whatever widget it is parented to.

    Used to mark a podium finish. Transparent to mouse events so the buttons
    underneath stay clickable, and it tracks the parent's size through an event
    filter rather than needing the parent to know it exists.
    """

    COLOURS = ("#f1c40f", "#58a6ff", "#3fb950", "#e3a01a", "#da3633", "#bc8cff")
    DURATION = 5.0          # seconds of falling before it stops on its own

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.pieces = []
        self._started = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == event.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def start(self, count: int = 140):
        parent = self.parent()
        if parent is None:
            return
        self.setGeometry(parent.rect())
        width = max(1, self.width())

        self.pieces = []
        for i in range(count):
            # Deterministic-ish spread across the width, then jittered, so the
            # burst covers the screen instead of clumping.
            self.pieces.append({
                "x": random.uniform(0, width),
                "y": random.uniform(-self.height() * 0.6, 0),
                "vx": random.uniform(-40, 40),
                "vy": random.uniform(90, 240),
                "w": random.uniform(5, 11),
                "h": random.uniform(8, 16),
                "angle": random.uniform(0, 360),
                "spin": random.uniform(-220, 220),
                "colour": QColor(random.choice(self.COLOURS)),
            })
        self._started = time.time()
        self.show()
        self.raise_()
        self.timer.start(33)

    def stop(self):
        self.timer.stop()
        self.pieces = []
        self.hide()

    def _tick(self):
        dt = 0.033
        elapsed = time.time() - self._started
        fading = elapsed > self.DURATION
        height = self.height()

        for p in self.pieces:
            p["vy"] += 90 * dt                 # gravity
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["angle"] += p["spin"] * dt

        self.pieces = [p for p in self.pieces if p["y"] < height + 30]
        if fading or not self.pieces:
            self.stop()
            return
        self.update()

    def paintEvent(self, event):
        if not self.pieces:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.pieces:
            painter.save()
            painter.translate(p["x"], p["y"])
            painter.rotate(p["angle"])
            painter.setBrush(p["colour"])
            painter.drawRoundedRect(
                QRectF(-p["w"] / 2, -p["h"] / 2, p["w"], p["h"]), 2, 2)
            painter.restore()


# Electrode positions in the international 10-20 system (and the 10-10
# extensions the EMOTIV headsets actually use), as unit-circle coordinates with
# the nose at +y and the right ear at +x. Drawing a sensor where it really sits
# is the difference between "S2 is red" and "the one above your left eyebrow
# needs reseating" — the second is something a player can act on.
ELECTRODE_POSITIONS = {
    "Nz":  (0.00,  1.05),
    "Fp1": (-0.31, 0.95), "Fpz": (0.00, 1.00), "Fp2": (0.31, 0.95),
    "AF7": (-0.59, 0.81), "AF3": (-0.33, 0.77), "AFz": (0.00, 0.75),
    "AF4": (0.33,  0.77), "AF8": (0.59, 0.81),
    "F7":  (-0.81, 0.59), "F5": (-0.64, 0.58), "F3": (-0.45, 0.55),
    "F1":  (-0.23, 0.52), "Fz": (0.00, 0.50), "F2": (0.23, 0.52),
    "F4":  (0.45,  0.55), "F6": (0.64, 0.58), "F8": (0.81, 0.59),
    "FT7": (-0.95, 0.31), "FC5": (-0.72, 0.29), "FC3": (-0.49, 0.27),
    "FC1": (-0.25, 0.26), "FCz": (0.00, 0.25), "FC2": (0.25, 0.26),
    "FC4": (0.49,  0.27), "FC6": (0.72, 0.29), "FT8": (0.95, 0.31),
    "T7":  (-1.00, 0.00), "T3": (-1.00, 0.00), "C5": (-0.75, 0.00),
    "C3":  (-0.50, 0.00), "C1": (-0.25, 0.00), "Cz": (0.00, 0.00),
    "C2":  (0.25,  0.00), "C4": (0.50, 0.00), "C6": (0.75, 0.00),
    "T8":  (1.00,  0.00), "T4": (1.00, 0.00),
    "TP7": (-0.95, -0.31), "CP5": (-0.72, -0.29), "CP3": (-0.49, -0.27),
    "CP1": (-0.25, -0.26), "CPz": (0.00, -0.25), "CP2": (0.25, -0.26),
    "CP4": (0.49, -0.27), "CP6": (0.72, -0.29), "TP8": (0.95, -0.31),
    "P7":  (-0.81, -0.59), "T5": (-0.81, -0.59), "P5": (-0.64, -0.58),
    "P3":  (-0.45, -0.55), "P1": (-0.23, -0.52), "Pz": (0.00, -0.50),
    "P2":  (0.23, -0.52), "P4": (0.45, -0.55), "P6": (0.64, -0.58),
    "P8":  (0.81, -0.59), "T6": (0.81, -0.59),
    "PO7": (-0.59, -0.81), "PO3": (-0.33, -0.77), "POz": (0.00, -0.75),
    "PO4": (0.33, -0.77), "PO8": (0.59, -0.81),
    "O1":  (-0.31, -0.95), "Oz": (0.00, -1.00), "O2": (0.31, -0.95),
    # Reference / mastoid electrodes sit on the ear, just outside the outline.
    "A1":  (-1.14, 0.00), "M1": (-1.14, 0.00),
    "A2":  (1.14,  0.00), "M2": (1.14, 0.00),
}

# Contact quality 0-4, matching the colours used elsewhere on the EQ screen.
CQ_COLOURS = {0: "#da3633", 1: "#da3633", 2: "#e3a01a", 3: "#58a6ff", 4: "#3fb950"}


class SensorHeadMapWidget(QWidget):
    """Contact quality drawn on a head, seen from above with the nose up."""

    def __init__(self, parent=None, compact: bool = False):
        super().__init__(parent)
        self.compact = compact
        if not compact:
            self.setMinimumSize(300, 300)
            self.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Expanding)
        self.sensors = []          # [(label, cq_int)] in stream order

    def set_sensors(self, labels, values):
        """Pair the stream's electrode names with its latest quality values."""
        pairs = []
        for i, value in enumerate(values):
            label = labels[i] if i < len(labels) else f"S{i}"
            try:
                cq = int(value)
            except (TypeError, ValueError):
                cq = 0
            pairs.append((str(label), max(0, min(4, cq))))
        self.sensors = pairs
        self.update()

    def clear(self):
        self.sensors = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Width usually binds first (the panel is tall and narrow); the height
        # term stops the head overflowing when it does not. Sat slightly high so
        # off-montage sensors have room on the row underneath.
        if self.compact:
            radius = min(self.width(), self.height()) * 0.36
            cx, cy = self.width() / 2, self.height() * 0.54
        else:
            radius = min(self.width() * 0.40, self.height() * 0.36)
            cx = self.width() / 2
            cy = self.height() * 0.46

        self._paint_head(painter, cx, cy, radius)

        if not self.sensors:
            if self.compact:
                return
            painter.setPen(QColor("#6e7681"))
            font = painter.font(); font.setPointSize(11); painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             t("eq.headmap_waiting"))
            return

        # Anything the table does not know about still has to appear somewhere,
        # or a headset with an unusual channel would silently lose a sensor.
        unknown = [s for s in self.sensors if s[0] not in ELECTRODE_POSITIONS]
        for i, (label, cq) in enumerate(unknown):
            step = self.width() / (len(unknown) + 1)
            self._paint_sensor(painter, step * (i + 1),
                               cy + radius * 1.42, label, cq, 0.0, 1.0)

        for label, cq in self.sensors:
            position = ELECTRODE_POSITIONS.get(label)
            if position is None:
                continue
            x, y = position
            # Push the caption away from the centre of the head, so a dense
            # montage labels outwards instead of writing over its neighbours.
            length = math.hypot(x, y)
            if length < 0.01:
                ux, uy = 0.0, 1.0
            else:
                ux, uy = x / length, -y / length
            self._paint_sensor(painter, cx + x * radius, cy - y * radius,
                               label, cq, ux, uy)

    def _paint_head(self, painter, cx, cy, radius):
        outline = QPen(QColor("#30363d"), 2)
        painter.setPen(outline)
        painter.setBrush(QColor("#0d1117"))

        # Nose: a wedge at the top, so "which way am I facing" needs no caption.
        nose = QPolygonF([
            QPointF(cx - radius * 0.13, cy - radius * 0.99),
            QPointF(cx, cy - radius * 1.20),
            QPointF(cx + radius * 0.13, cy - radius * 0.99),
        ])
        painter.drawPolygon(nose)

        for side in (-1, 1):
            painter.drawEllipse(
                QRectF(cx + side * radius * 1.0 - radius * 0.07,
                       cy - radius * 0.20, radius * 0.16, radius * 0.40))

        painter.setBrush(QColor("#0d1117"))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Midlines, faint: they make the left/right split readable at a glance.
        painter.setPen(QPen(QColor("#21262d"), 1))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))

        if self.compact:
            return
        font = painter.font(); font.setPointSize(8); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#6e7681"))
        metrics = painter.fontMetrics()
        front = t("eq.headmap_front")
        painter.drawText(int(cx - metrics.horizontalAdvance(front) / 2),
                         int(cy - radius * 1.28), front)

    def _paint_sensor(self, painter, x, y, label, cq, ux=0.0, uy=1.0):
        colour = QColor(CQ_COLOURS.get(cq, "#8b949e"))
        dot = min(self.width(), self.height()) * (0.10 if self.compact else 0.045)

        # Good contacts get a soft halo; bad ones just read as a flat red dot.
        if cq >= 3:
            glow = QRadialGradient(QPointF(x, y), dot * 2.1)
            glow.setColorAt(0.0, QColor(colour.red(), colour.green(), colour.blue(), 110))
            glow.setColorAt(1.0, QColor(colour.red(), colour.green(), colour.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(x, y), dot * 2.1, dot * 2.1)

        painter.setPen(QPen(QColor("#0d1117"), 2))
        painter.setBrush(colour)
        painter.drawEllipse(QPointF(x, y), dot, dot)

        if self.compact:
            return

        font = painter.font(); font.setPointSize(8); font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(label)
        gap = dot + 4
        lx = x + ux * (gap + width / 2)
        ly = y + uy * (gap + metrics.height() / 2)

        # A plate behind the text keeps it legible where a label ends up over
        # the head outline or close to another electrode.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(13, 17, 23, 205))
        painter.drawRoundedRect(
            QRectF(lx - width / 2 - 3, ly - metrics.height() / 2,
                   width + 6, metrics.height()), 3, 3)
        painter.setPen(QColor("#e6edf3"))
        painter.drawText(int(lx - width / 2),
                         int(ly + metrics.height() / 2 - metrics.descent()), label)


class ReconnectBanner(QWidget):
    """Full-window notice while a dropped headset is being chased.

    Covers whatever page is up rather than living on one of them, because a
    headset can drop during training, during a run, or while idle, and the
    message is the same in every case.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("reconnectBanner")
        self.setStyleSheet(
            "#reconnectBanner { background-color: rgba(2, 5, 10, 232); }")

        box = QVBoxLayout(self)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setSpacing(10)

        self.title = bind(QLabel(), "reconnect.title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(
            "font-size: 26px; font-weight: bold; color: #e3a01a;")
        box.addWidget(self.title)

        self.detail = QLabel()
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("font-size: 15px; color: #c9d1d9;")
        box.addWidget(self.detail)

        self.countdown = QLabel()
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown.setStyleSheet("font-size: 14px; color: #8b949e;")
        box.addWidget(self.countdown)

        self.hide()

    def show_for(self, headset_id: str, seconds: int):
        bind(self.detail, "reconnect.detail", headset=headset_id or "—")
        self.set_remaining(seconds)
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()

    def set_remaining(self, seconds: float):
        bind(self.countdown, "reconnect.remaining",
             seconds=max(0, int(round(seconds))))


class DevicePill(QWidget):
    """Which headset is flying this, and whether its electrodes are on.

    Modelled on the device pill in emotiv-brain-light: a small head map for
    where the problem is, one number for how bad it is, in the colours this
    project already uses. It lives on the flight screen because that is where
    a contact going bad shows up as the drone quietly not responding.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)

        self.head = SensorHeadMapWidget(compact=True)
        self.head.setFixedSize(40, 40)
        layout.addWidget(self.head)

        column = QVBoxLayout()
        column.setSpacing(0)
        self.name_lbl = QLabel("—")
        self.name_lbl.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #e6edf3;")
        column.addWidget(self.name_lbl)
        self.grade_lbl = bind(QLabel(), "quality.unknown_state")
        self.grade_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
        column.addWidget(self.grade_lbl)
        layout.addLayout(column)

        self.badge = QLabel("—")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedWidth(48)
        layout.addWidget(self.badge)

        # Headset battery. A run dying halfway because the headset was at 4%
        # is not something anyone should discover mid-flight.
        self.battery_lbl = QLabel("—")
        self.battery_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.battery_lbl.setFixedWidth(56)
        layout.addWidget(self.battery_lbl)
        self.set_battery(None)

        # Scoped by object name, or the frame is inherited by every child
        # label; WA_StyledBackground so a plain QWidget honours the fill.
        self.setObjectName("devicePill")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#devicePill { background-color: #0d1117;"
            " border: 1px solid #30363d; border-radius: 10px; }")
        self._paint_badge(None)

    def set_device(self, headset_id: str):
        self.name_lbl.setText(headset_id or "—")

    def set_battery(self, percent):
        """Headset charge, 0-100, or None when the headset has not said yet."""
        if percent is None:
            self.battery_lbl.setText("—")
            colour = "#6e7681"
        else:
            percent = max(0, min(100, int(percent)))
            icon = "🔋" if percent > 20 else "🪫"
            self.battery_lbl.setText(f"{icon}{percent}%")
            colour = ("#3fb950" if percent > 40
                      else "#e3a01a" if percent > 20 else "#da3633")
        self.battery_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {colour};")

    def set_quality(self, percent, cq_list, labels, keep_idx):
        grades = ([cq_list[i] for i in keep_idx if i < len(cq_list)]
                  if keep_idx is not None else list(cq_list or []))
        self.head.set_sensors(labels or [], grades)
        key, _ = contact_grade(percent)
        bind(self.grade_lbl, key)
        self._paint_badge(percent)

    def _paint_badge(self, percent):
        key, colour = contact_grade(percent)
        self.badge.setText("—" if percent is None else f"{int(round(percent))}%")
        self.badge.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {colour};"
            f"border: 1px solid {colour}; border-radius: 8px; padding: 3px 4px;")


class BrainMapWidget(QWidget):
    """Scatter plot of mentalCommandBrainMap.

    Cortex returns one (x, y) per trained action, x in [-1, 1] and y in [0, 1].
    The distance between two points is how distinguishable those two mental
    states were in the training data — points on top of each other mean Cortex
    keeps mixing them up, so the plot doubles as the "is my training any good?"
    answer.
    """

    ACTION_COLOURS = {
        "neutral": "#8b949e",
        "push": "#58a6ff",
        "pull": "#bc8cff",
        "lift": "#3fb950",
        "drop": "#f0883e",
        "left": "#39c5cf",
        "right": "#db61a2",
        "rotateLeft": "#e3b341",
        "rotateRight": "#ff7b72",
        "disappear": "#a371f7",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.points = []          # [(action, x, y), ...]
        self._reveal = 0.0        # 0 → 1 grow-in animation

        self._anim = QTimer(self)
        self._anim.timeout.connect(self._grow)

    def set_points(self, data):
        """Feed the raw Cortex result straight in."""
        self.points = []
        for entry in data or []:
            coords = entry.get("coordinates") or [0, 0]
            if len(coords) >= 2:
                self.points.append((entry.get("action", "?"),
                                    float(coords[0]), float(coords[1])))
        self._reveal = 0.0
        self._anim.start(16)
        self.update()

    def _grow(self):
        self._reveal = min(1.0, self._reveal + 0.05)
        if self._reveal >= 1.0:
            self._anim.stop()
        self.update()

    def separation(self):
        """Smallest gap between any two actions — the number that matters.

        Returns None when there are fewer than two points, since "separation"
        is meaningless for a single action.
        """
        if len(self.points) < 2:
            return None
        gaps = []
        for i in range(len(self.points)):
            for j in range(i + 1, len(self.points)):
                _, x1, y1 = self.points[i]
                _, x2, y2 = self.points[j]
                gaps.append(math.hypot(x2 - x1, y2 - y1))
        return min(gaps)

    def quality_key(self):
        """Translate the smallest gap into a verdict the user can act on."""
        gap = self.separation()
        if gap is None:
            return "brainmap.quality.unknown", "#8b949e"
        if gap < 0.15:
            return "brainmap.quality.poor", "#f85149"
        if gap < 0.35:
            return "brainmap.quality.fair", "#e3a01a"
        return "brainmap.quality.good", "#3fb950"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pad = 44
        w = self.width() - pad * 2
        h = self.height() - pad * 2
        if w <= 10 or h <= 10:
            return

        # Plot surface, a shade off the page so the chart reads as its own panel
        painter.setPen(QPen(QColor("#30363d"), 1))
        painter.setBrush(QColor("#0b0f15"))
        painter.drawRoundedRect(QRectF(pad, pad, w, h), 10, 10)

        def to_screen(x, y):
            # x in [-1, 1] → left..right, y in [0, 1] → bottom..top
            return (pad + (x + 1) / 2 * w, pad + (1 - y) * h)

        # Grid
        painter.setPen(QPen(QColor("#21262d"), 1))
        for frac in (0.25, 0.5, 0.75):
            painter.drawLine(int(pad + frac * w), int(pad),
                             int(pad + frac * w), int(pad + h))
            painter.drawLine(int(pad), int(pad + frac * h),
                             int(pad + w), int(pad + frac * h))

        # Centre axis, where "neutral" sits
        painter.setPen(QPen(QColor("#30363d"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(pad + w / 2), int(pad), int(pad + w / 2), int(pad + h))

        if not self.points:
            painter.setPen(QColor("#8b949e"))
            painter.drawText(QRectF(pad, pad, w, h),
                             Qt.AlignmentFlag.AlignCenter, t("brainmap.empty"))
            return

        # Faint lines between every pair, so "these two are too close" is visible
        # rather than something the user has to eyeball.
        for i in range(len(self.points)):
            for j in range(i + 1, len(self.points)):
                _, x1, y1 = self.points[i]
                _, x2, y2 = self.points[j]
                gap = math.hypot(x2 - x1, y2 - y1)
                if gap > 0.35:
                    continue  # well separated, no need to call it out
                sx1, sy1 = to_screen(x1, y1)
                sx2, sy2 = to_screen(x2, y2)
                colour = QColor("#f85149" if gap < 0.15 else "#e3a01a")
                colour.setAlpha(120)
                painter.setPen(QPen(colour, 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))

        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)

        # Dots first, then labels — otherwise a later halo washes out an earlier
        # label, which is exactly what happens in the clustered (bad) case.
        placed = []
        metrics = painter.fontMetrics()

        for action, x, y in self.points:
            sx, sy = to_screen(x, y)
            colour = QColor(self.ACTION_COLOURS.get(action, "#58a6ff"))
            r = 11 * self._reveal

            halo = QRadialGradient(QPointF(sx, sy), max(r * 3, 1))
            halo_colour = QColor(colour)
            halo_colour.setAlpha(70)
            halo.setColorAt(0.0, halo_colour)
            halo_colour.setAlpha(0)
            halo.setColorAt(1.0, halo_colour)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QPointF(sx, sy), r * 3, r * 3)

            painter.setBrush(colour)
            painter.setPen(QPen(QColor("#0d1117"), 2))
            painter.drawEllipse(QPointF(sx, sy), r, r)

        for action, x, y in self.points:
            sx, sy = to_screen(x, y)
            colour = QColor(self.ACTION_COLOURS.get(action, "#58a6ff"))
            label = t(f"action.{action}") if i18n.has(f"action.{action}") else action
            tw = metrics.horizontalAdvance(label)
            th = metrics.height()

            # Try positions around the dot until one is clear of every label
            # already drawn and still inside the plot.
            candidates = [(18, 4), (-18 - tw, 4), (-tw / 2, -20),
                          (-tw / 2, 26), (18, -18), (18, 24)]
            spot = None
            for dx, dy in candidates:
                rect = QRectF(sx + dx, sy + dy - th + 4, tw, th)
                if rect.left() < pad or rect.right() > pad + w:
                    continue
                if rect.top() < pad or rect.bottom() > pad + h:
                    continue
                if any(rect.intersects(other) for other in placed):
                    continue
                spot = rect
                break
            if spot is None:
                spot = QRectF(sx + 18, sy - th + 8, tw, th)
            placed.append(spot)

            # Leader line when the label had to move away from its dot.
            if abs(spot.left() - sx) > 26 or abs(spot.center().y() - sy) > 16:
                painter.setPen(QPen(QColor(110, 118, 129, 160), 1))
                painter.drawLine(int(sx), int(sy),
                                 int(spot.center().x()), int(spot.center().y()))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(13, 17, 23, 210))
            painter.drawRoundedRect(spot.adjusted(-5, -2, 5, 2), 5, 5)
            painter.setPen(colour)
            painter.drawText(spot, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             label)

        # Axis captions
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#6e7681"))
        painter.drawText(int(pad), int(pad + h + 22), t("brainmap.axis_x"))
        painter.save()
        painter.translate(int(pad) - 14, int(pad + h))
        painter.rotate(-90)
        painter.drawText(0, 0, t("brainmap.axis_y"))
        painter.restore()


class FullscreenHUDWidget(QWidget):
    """Fullscreen Camera HUD with Flight Controller Overlays"""
    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.latest_frame = QImage()

    def update_frame(self, img: QImage):
        self.latest_frame = img
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        cx = w // 2
        cy = h // 2

        # 1. Draw Camera Feed
        if not self.latest_frame.isNull():
            scaled = self.latest_frame.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            
            # Center the image
            draw_x = (w - scaled.width()) // 2
            draw_y = (h - scaled.height()) // 2
            painter.drawImage(draw_x, draw_y, scaled)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("hud.no_signal"))

        # 2. Draw HUD Elements
        painter.setPen(QPen(QColor(0, 255, 0, 200), 2))
        
        # Crosshair
        painter.drawLine(cx - 20, cy, cx - 5, cy)
        painter.drawLine(cx + 5, cy, cx + 20, cy)
        painter.drawLine(cx, cy - 20, cx, cy - 5)
        painter.drawLine(cx, cy + 5, cx, cy + 20)
        painter.drawPoint(cx, cy)

        # Get telemetry
        lr, fb, ud, yaw = 0, 0, 0, 0
        batt, alt, temp = 0, 0, 0
        action, action_time = None, 0.0
        now = time.time()

        if self.main_app:
            if self.main_app.drone_client and self.main_app.drone_client.drone:
                lr, fb, ud, yaw = self.main_app.drone_client.drone.get_rc_values()
                action = getattr(self.main_app.drone_client.drone, 'last_executed_action', None)
                action_time = getattr(self.main_app.drone_client.drone, 'last_action_time', 0.0)
            if self.main_app.tello:
                try:
                    batt = self.main_app.tello.get_battery()
                    alt = self.main_app.tello.get_height()
                    temp = self.main_app.tello.get_temperature()
                except:
                    pass

        # Font setup. Courier has no CJK glyphs, so only force it for Latin text —
        # otherwise the translated overlays would render as boxes.
        font = painter.font()
        if i18n.get_lang() == "en":
            font.setFamily("Courier")
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)

        # Telemetry Text
        painter.drawText(20, 40, f"PWR: {batt}%")
        painter.drawText(20, 65, f"ALT: {alt} cm")
        painter.drawText(20, 90, f"TMP: {temp} C")

        # RC Bars (Left side = UD/YAW, Right side = FB/LR)
        def draw_bar(x, y, val, label, is_horizontal=False):
            painter.setPen(QColor(0, 255, 0, 150))
            if is_horizontal:
                painter.drawLine(x - 50, y, x + 50, y)
                painter.drawLine(x, y - 5, x, y + 5)
                # Fill
                if val != 0:
                    bx = x if val > 0 else x + int(val / 2.0)
                    bw = abs(int(val / 2.0))
                    painter.fillRect(bx, y - 2, bw, 4, QColor(0, 255, 0, 200))
            else:
                painter.drawLine(x, y - 50, x, y + 50)
                painter.drawLine(x - 5, y, x + 5, y)
                if val != 0:
                    # Invert Y so positive is up
                    by = y - int(val / 2.0) if val > 0 else y
                    bh = abs(int(val / 2.0))
                    painter.fillRect(x - 2, by, 4, bh, QColor(0, 255, 0, 200))
            painter.drawText(x - 20, y + 70 if not is_horizontal else y + 25, label)

        draw_bar(50, cy, ud, "THR")
        draw_bar(w - 50, cy, fb, "PIT")
        draw_bar(cx - 150, h - 50, yaw, "YAW", True)
        draw_bar(cx + 150, h - 50, lr, "ROL", True)

        # Horizon Line (Pitch/Roll estimate from RC inputs)
        # Note: Tello doesn't provide live IMU roll/pitch via SDK, so we estimate it for the HUD
        sim_roll = math.radians(-lr * 0.3)
        sim_pitch = fb * 0.3
        
        hx1 = -150
        hx2 = 150
        hy1 = sim_pitch
        hy2 = sim_pitch
        
        # Rotate by roll
        rx1 = cx + hx1 * math.cos(sim_roll) - hy1 * math.sin(sim_roll)
        ry1 = cy + hx1 * math.sin(sim_roll) + hy1 * math.cos(sim_roll)
        rx2 = cx + hx2 * math.cos(sim_roll) - hy2 * math.sin(sim_roll)
        ry2 = cy + hx2 * math.sin(sim_roll) + hy2 * math.cos(sim_roll)
        
        painter.setPen(QPen(QColor(0, 255, 0, 200), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(rx1), int(ry1), int(rx2), int(ry2))

        # Mental Command Banner
        if action and (now - action_time) < 2.0:
            alpha = int(255 * (1.0 - (now - action_time) / 2.0))
            if alpha > 0:
                text = f"*** {drone_action(action).upper()} ***"
                font.setPointSize(20)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                tw = metrics.horizontalAdvance(text)
                
                painter.setPen(QColor(255, 0, 0, alpha))
                painter.drawText(cx - tw // 2, 60, text)
                
        # ESC prompt
        painter.setPen(QColor(255, 255, 255, 100))
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(w - 150, 30, t("hud.esc"))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.main_app:
                self.main_app.close_fullscreen_hud()
            self.close()


class TelloControllerApp(QMainWindow):
    log_signal = pyqtSignal(str)
    drone_connected_signal = pyqtSignal(bool, str)
    bci_status_signal = pyqtSignal(str)
    bci_telemetry_signal = pyqtSignal(int, int)
    profiles_signal = pyqtSignal(list)
    headsets_signal = pyqtSignal(list)
    training_signal = pyqtSignal(str)
    dev_data_signal = pyqtSignal(int, list)
    dev_labels_signal = pyqtSignal(list)
    # Run a callable on the GUI thread. QTimer.singleShot(0, fn) called from a
    # worker thread creates the timer on a thread with no event loop, so it
    # never fires — which is how the Refresh button ended up stuck disabled
    # after its first press.
    ui_task_signal = pyqtSignal(object)
    mc_config_signal = pyqtSignal(dict)
    brainmap_signal = pyqtSignal(list)
    profile_admin_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        # Idempotent: main() starts this too, but the window is also built
        # directly by tests and tooling, and those runs are worth logging.
        applog.start()
        self.resize(1100, 820)
        self.config = ConfigManager.load_config()
        # Language has to be settled before any widget is built, so the first
        # bind() call already produces text in the right language.
        i18n.set_lang(self.config.get("language", "en"))
        bind(self, "app.title", "setWindowTitle")
        self.tello = None
        self.drone_client = None
        self.video_thread = None
        self.client_thread = None

        # --- Signals ---
        self.log_signal.connect(self._append_log)
        self.drone_connected_signal.connect(self._on_drone_connection_result)
        self.bci_status_signal.connect(self._do_update_bci_status)
        self.bci_telemetry_signal.connect(self._do_update_bci_telemetry)
        self.profiles_signal.connect(self._populate_profiles)
        self.headsets_signal.connect(self._populate_headsets)
        self.training_signal.connect(self._on_training_update)
        self.dev_data_signal.connect(self._on_dev_data_update)
        self.dev_labels_signal.connect(self._on_dev_labels)
        self.ui_task_signal.connect(lambda fn: fn())
        self.mc_config_signal.connect(self._on_mc_config_update)
        self.brainmap_signal.connect(self._on_brain_map)
        self.profile_admin_signal.connect(self._on_profile_admin)

        # Ring-run state. Declared before init_ui because the page builders
        # connect buttons that read it.
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self._on_run_tick)
        self._run_deadline = 0.0

        # Pre-run countdown, so nobody's timed round starts while they are
        # still looking at the button they just pressed.
        self.run_countdown_timer = QTimer(self)
        self.run_countdown_timer.timeout.connect(self._on_countdown_step)
        self._countdown_left = 0

        # Chasing a headset that dropped out mid-session.
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self._on_reconnect_tick)
        self._reconnect_deadline = 0.0
        self._lost_headset = ""
        self._run_paused = False
        self.current_player = ""
        self.current_entry = None
        self.mc_active_actions = []
        self.mc_sensitivities = []
        # Written to credentials.json the moment Cortex authorizes, once.
        self._credentials_saved = False
        # True between pressing Connect and EMOTIV Launcher being answered.
        self._awaiting_approval = False
        self.dev_sensor_labels = []
        self._dev_keep_idx = None
        self._dev_overall_idx = None
        self.headset_rows = []
        # Every DevicePill on every page; they all show the same headset, so
        # they are driven together rather than each page wiring its own.
        self.all_pills = []
        self._board_return_page = PAGE_TEST

        self.stdout_stream = EmittingStream()
        self.stdout_stream.textWritten.connect(self.log_signal.emit)
        self.original_stdout = sys.stdout
        sys.stdout = self.stdout_stream

        self.init_ui()
        self.load_settings()
        # Deferred so the event loop is up: _start_bci spawns a thread and
        # expects to be able to post back into a running UI.
        QTimer.singleShot(0, self._maybe_auto_connect)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        header = QHBoxLayout()
        # Slightly held back: it is on every page, including the simulator,
        # and should read as a mark in the corner rather than as content.
        brand = logo_label(height=LOGO_HEADER_H, opacity=0.75)
        if brand is not None:
            header.addWidget(brand)
        header.addStretch()

        self.lang_lbl = QLabel()
        bind(self.lang_lbl, "header.language")
        header.addWidget(self.lang_lbl)

        self.lang_combo = QComboBox()
        self.lang_combo.setFixedWidth(120)
        for code, name in i18n.available_languages():
            self.lang_combo.addItem(name, userData=code)
        current = self.lang_combo.findData(i18n.get_lang())
        if current >= 0:
            self.lang_combo.setCurrentIndex(current)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        header.addWidget(self.lang_combo)

        self.settings_btn = QPushButton()
        bind(self.settings_btn, "btn.settings")
        self.settings_btn.setObjectName("blueBtn")
        self.settings_btn.clicked.connect(self.show_settings)
        # The Configurations dialog is almost entirely motion-sensor tuning and
        # real-drone mappings; it follows the same flag as the inline sliders.
        self.settings_btn.setVisible(SHOW_MOTION_TUNING or SHOW_REAL_DRONE)
        header.addWidget(self.settings_btn)
        main_layout.addLayout(header)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.currentChanged.connect(self._on_page_changed)
        main_layout.addWidget(self.stacked_widget)

        # Parented to the window, so it covers whichever page is showing.
        self.reconnect_banner = ReconnectBanner(self)

        self.setup_page_auth()
        self.setup_page_headset()
        self.setup_page_profile()
        self.setup_page_eq_check()
        self.setup_page_train_neutral()
        self.setup_page_train_push()
        self.setup_page_1()
        self.setup_page_2()
        self.setup_page_3()
        self.setup_page_brainmap()
        self.setup_page_gameover()
        self.setup_page_leaderboard()

        # _maybe_auto_connect decides between the credentials screen and the
        # headset list as soon as the event loop is up.

        self.telem_timer = QTimer()
        self.telem_timer.timeout.connect(self.update_telemetry)

    # Values that look filled in but are not. DEFAULT_CONFIG used to seed the
    # first two, and older installs still carry them.
    PLACEHOLDER_CREDENTIALS = {"", "YOUR_CLIENT_ID", "YOUR_CLIENT_SECRET"}

    def _credentials_ready(self) -> bool:
        """True when there is a real saved credential pair to connect with.

        DEFAULT_CONFIG seeds the placeholders below on first run, so "non-empty"
        is not enough — those would happily trigger a doomed auto-connect.
        """
        cid = (self.config.get("client_id") or "").strip()
        secret = (self.config.get("client_secret") or "").strip()
        return (cid not in self.PLACEHOLDER_CREDENTIALS
                and secret not in self.PLACEHOLDER_CREDENTIALS)

    def _maybe_auto_connect(self):
        """Ask for credentials once; after that, connect without being asked.

        The app ships with none, so the first launch stops on the credentials
        screen. Once Cortex has accepted them they live in credentials.json and
        every later launch goes straight to the headset list.
        """
        if self.simulate_cb.isChecked():
            return

        if not self._credentials_ready():
            self._show_credentials_page()
            return

        self.client_id_input.setText(self.config.get("client_id", ""))
        self.client_secret_input.setText(self.config.get("client_secret", ""))
        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
        self.log(t("log.auto_connecting"))
        self._start_bci()

    def _show_credentials_page(self, error: str = "", waiting: bool = False):
        """Land on the credentials screen.

        Three states: asking for the first time, waiting on EMOTIV Launcher,
        and reporting why the last attempt failed. Waiting is deliberately not
        an error — approving the app is a step everyone goes through once, and
        dressing it as a failure makes people think they typed something wrong.
        """
        if waiting:
            bind(self.auth_reason_lbl, "auth.awaiting_approval")
            self.auth_reason_lbl.setStyleSheet(
                "font-size: 12px; color: #58a6ff; background-color: #0d2440;"
                "border: 1px solid #1f6feb; border-radius: 6px; padding: 9px;")
            self.auth_reason_lbl.setVisible(True)
            bind(self.connect_bci_btn, "auth.waiting_approval")
            self.connect_bci_btn.setEnabled(False)
        elif error:
            bind(self.auth_reason_lbl, "auth.failed", detail=error)
            self.auth_reason_lbl.setStyleSheet(
                "font-size: 12px; color: #f0883e; background-color: #1f1300;"
                "border: 1px solid #e3a01a; border-radius: 6px; padding: 9px;")
            self.auth_reason_lbl.setVisible(True)
            self.connect_bci_btn.setEnabled(True)
            bind(self.connect_bci_btn, "auth.connect")
            applog.write(f"credentials screen shown: {error}")
        else:
            self.auth_reason_lbl.setVisible(False)
            self.connect_bci_btn.setEnabled(True)
            bind(self.connect_bci_btn, "auth.connect")

        self.stacked_widget.setCurrentIndex(PAGE_AUTH)
        if not waiting:
            if not self.client_id_input.text().strip():
                self.client_id_input.setFocus()
            else:
                self.client_secret_input.setFocus()

    def _submit_credentials(self):
        """Try the typed credentials. Saved only once Cortex accepts them."""
        cid = self.client_id_input.text().strip()
        secret = self.client_secret_input.text().strip()
        if (cid in self.PLACEHOLDER_CREDENTIALS
                or secret in self.PLACEHOLDER_CREDENTIALS):
            self._show_credentials_page(t("auth.both_required"))
            return

        # Held in memory for now; _on_authorized writes them out once Cortex
        # and EMOTIV Launcher have both said yes. Saving a bad pair would mean
        # the next launch skips this screen and fails silently instead.
        self.auth_reason_lbl.setVisible(False)
        self.connect_bci_btn.setEnabled(False)
        bind(self.connect_bci_btn, "auth.connecting")

        # A fresh client each attempt: the previous one may be sitting on a
        # dead socket or an unauthorised token.
        if self.drone_client:
            stale, self.drone_client = self.drone_client, None
            # Silence it before closing: its socket outlives this call and
            # would otherwise report the old failure into the new attempt.
            self._quietly(stale.detach_callbacks)
            threading.Thread(
                target=lambda: self._quietly(stale.close), daemon=True).start()

        self._conn_fail_detail = ""
        QTimer.singleShot(250, self._start_bci)

    def _on_authorized(self):
        """Cortex accepted the credentials and Launcher approved the app."""
        if self._credentials_saved:
            return
        self._credentials_saved = True
        self._awaiting_approval = False
        # Only now, with Cortex having accepted them, do these reach disk.
        self.config["client_id"] = self.client_id_input.text().strip()
        self.config["client_secret"] = self.client_secret_input.text().strip()
        ConfigManager.save_config(self.config)
        self.log(t("log.credentials_saved"))
        applog.write("credentials accepted and saved")

    def _make_abandon_button(self) -> QPushButton:
        """Way out of training, back to the device list.

        Training is the longest part of the flow and the easiest to get stuck
        in — a bad take, the wrong headset, or simply the wrong person sitting
        down. There was no exit from these pages at all.
        """
        button = bind(QPushButton(), "train.abandon")
        bind(button, "train.abandon.tip", "setToolTip")
        # Present but quiet: this throws away the training in progress, so it
        # should never catch the eye of someone reaching for Accept. Flat and
        # grey, and it only picks up contrast on hover.
        button.setObjectName("ghostBtn")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self._abandon_training)
        return button

    def _abandon_training(self):
        """Stop whatever take is running and hand the headset back."""
        for name in ("countdown_timer", "recording_timer"):
            timer = getattr(self, name, None)
            if timer is not None and timer.isActive():
                timer.stop()
        if getattr(self, "countdown_overlay", None) is not None:
            self.countdown_overlay.hide()
        if getattr(self, "push_anim_timer", None) is not None:
            self.push_anim_timer.stop()

        self.log(t("log.training_abandoned"))
        profile = (self.config.get("profile_name") or "").strip()
        self.config["profile_name"] = ""
        ConfigManager.save_config(self.config)
        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
        self._release_headset(profile)

    def _new_device_pill(self) -> "DevicePill":
        """A pill wired into the shared update path."""
        pill = DevicePill()
        self.all_pills.append(pill)
        return pill

    def _pills_device(self, headset_id: str):
        for pill in self.all_pills:
            pill.set_device(headset_id)

    def _pills_quality(self, percent, cq_list, labels, keep_idx):
        for pill in self.all_pills:
            pill.set_quality(percent, cq_list, labels, keep_idx)

    def _pills_battery(self, percent):
        for pill in self.all_pills:
            pill.set_battery(percent)

    def forward_command_label(self) -> str:
        """Translated name of the thought that flies the drone forward.

        Read from the live mapping rather than hard-coded to "Push": which
        command drives forward is configurable, and telling a player to think
        the wrong word is worse than saying nothing. Empty when nothing is
        mapped to a forward movement.
        """
        for mapping in (self.config.get("mental_mappings") or []):
            if mapping.get("action") == "MoveForward":
                command = (mapping.get("command") or "").strip()
                if not command:
                    return ""
                key = f"action.{command}"
                return t(key) if i18n.has(key) else command.capitalize()
        return ""

    def _refresh_player_name(self):
        """Show whichever profile is loaded — that is the name the board gets."""
        profile = (self.config.get("profile_name") or "").strip()
        if profile:
            self.player_name_lbl.setText(profile)
            i18n.unbind(self.player_name_lbl)
        else:
            bind(self.player_name_lbl, "game.no_profile")
        self.start_run_btn.setEnabled(bool(profile))

    def _on_page_changed(self, index: int):
        """Leaving the test screen mid-run abandons the run.

        Otherwise the timer would keep counting somewhere else and yank the user
        onto a results screen for a round they walked away from. _finish_ring_run
        stops the timer before it navigates, so a normal finish never lands here.
        """
        if index == PAGE_PROFILE and not (self.config.get("profile_name") or "").strip():
            # Nobody is mid-session, so whoever arrives here is a new player and
            # the box must be empty. It used to still hold the last person's
            # name: the handoff cleared config["profile_name"] but never the
            # field, so the next participant either played under someone else's
            # name or had to clear it themselves. Guarded on there being no
            # active profile, so stepping back here mid-flow keeps what was
            # typed.
            self.new_profile_input.clear()
            bind(self.profile_status_lbl, "profile.hint")
            self.profile_status_lbl.setStyleSheet(
                "color: #8b949e; font-size: 11px; font-style: italic; padding: 0 2px;")
            self.new_profile_input.setFocus()

        if index == PAGE_TEST:
            self._refresh_player_name()

        if index == PAGE_TEST and self.drone_client and not self.mc_sensitivities:
            # Cortex only answers per profile, and the profile is not known
            # until it has been loaded — so ask on arrival, not at startup.
            threading.Thread(target=self.drone_client.get_mc_config, daemon=True).start()

        if index != PAGE_TEST and (self.run_timer.isActive()
                                   or self.run_countdown_timer.isActive()):
            self.run_timer.stop()
            self.run_countdown_timer.stop()
            self.drone_sim.end_run()
            self.start_run_btn.setEnabled(True)
            bind(self.start_run_btn, "game.start")
            self.log(t("log.run_abandoned"))

    def _on_language_changed(self, index: int):
        code = self.lang_combo.itemData(index)
        if not code or code == i18n.get_lang():
            return
        i18n.set_lang(code)
        self.config["language"] = code
        ConfigManager.save_config(self.config)
        i18n.retranslate()
        self._retranslate_dynamic()

    def _retranslate_dynamic(self):
        """Redo the bits that bind() cannot reach: combo entries and repaints."""
        # A combo showing a placeholder holds no real data, so its single item
        # is safe to rewrite. _placeholder_key says which message is up.
        for combo in (self.profile_combo,):
            key = getattr(combo, "_placeholder_key", None)
            if key and combo.count() == 1:
                combo.setItemText(0, t(key))
        for widget in (self.drone_sim, self.neutral_sim, self.push_sim):
            widget.update()
        if getattr(self, "hud_widget", None) is not None:
            self.hud_widget.update()

    def setup_page_auth(self):
        """Credentials, and the only screen shown before a headset is picked.

        Seen once: the app ships without credentials, so the first launch has
        to ask. Once Cortex accepts them and the user approves the app in
        EMOTIV Launcher they are written to credentials.json and this page is
        skipped from then on — unless something stops the connection working,
        in which case it comes back carrying the reason.
        """
        page = HeroBackdrop(HERO_FILE)
        layout = QVBoxLayout(page)
        layout.addStretch(1)

        container = QWidget(); container.setFixedWidth(620)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(12)

        mark = logo_label(height=LOGO_HERO_H)
        if mark is not None:
            c_layout.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "auth.title")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        c_layout.addWidget(title)

        intro = bind(QLabel(), "auth.intro")
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        intro.setStyleSheet("font-size: 13px; color: #8b949e;")
        c_layout.addWidget(intro)

        # Whatever went wrong last time, in the user's own language when we
        # recognise it and Cortex's own words when we do not.
        self.auth_reason_lbl = QLabel()
        self.auth_reason_lbl.setWordWrap(True)
        self.auth_reason_lbl.setVisible(False)
        self.auth_reason_lbl.setStyleSheet(
            "font-size: 12px; color: #f0883e; background-color: #1f1300;"
            "border: 1px solid #e3a01a; border-radius: 6px; padding: 9px;")
        c_layout.addWidget(self.auth_reason_lbl)

        auth_group = QGroupBox()
        bind(auth_group, "auth.group", "setTitle")
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(6)

        auth_layout.addWidget(bind(QLabel(), "auth.client_id"))
        self.client_id_input = QLineEdit()
        self.client_id_input.setMinimumHeight(34)
        bind(self.client_id_input, "auth.client_id.hint", "setPlaceholderText")
        auth_layout.addWidget(self.client_id_input)

        auth_layout.addWidget(bind(QLabel(), "auth.client_secret"))
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setMinimumHeight(34)
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        bind(self.client_secret_input, "auth.client_secret.hint", "setPlaceholderText")
        auth_layout.addWidget(self.client_secret_input)

        where = bind(QLabel(), "auth.where")
        where.setWordWrap(True)
        where.setOpenExternalLinks(True)
        where.setStyleSheet("font-size: 11px; color: #6e7681; padding-top: 2px;")
        auth_layout.addWidget(where)

        self.connect_bci_btn = QPushButton()
        self.connect_bci_btn.setObjectName("primaryBtn")
        self.connect_bci_btn.setMinimumHeight(42)
        bind(self.connect_bci_btn, "auth.connect")
        self.connect_bci_btn.clicked.connect(self._submit_credentials)
        auth_layout.addWidget(self.connect_bci_btn)

        # Enter submits: this is a two-field form and nobody should have to
        # reach for the mouse.
        for field in (self.client_id_input, self.client_secret_input):
            field.returnPressed.connect(self._submit_credentials)

        c_layout.addWidget(auth_group)

        # Approving in EMOTIV Launcher is part of this same first-run step, so
        # the instructions belong on this page rather than a later one.
        self.auth_approval_lbl = bind(QLabel(), "auth.approval_note")
        self.auth_approval_lbl.setWordWrap(True)
        self.auth_approval_lbl.setStyleSheet(
            "font-size: 12px; color: #8b949e; padding: 2px 4px;")
        c_layout.addWidget(self.auth_approval_lbl)

        # Kept, but off the first-run path: these are developer switches.
        self.simulate_cb = QCheckBox()
        bind(self.simulate_cb, "auth.simulate")
        self.simulate_cb.setVisible(SHOW_REAL_DRONE)
        c_layout.addWidget(self.simulate_cb)

        self.auto_connect_cb = QCheckBox()
        bind(self.auto_connect_cb, "auth.auto_connect")
        bind(self.auto_connect_cb, "auth.auto_connect.tip", "setToolTip")
        self.auto_connect_cb.setVisible(SHOW_REAL_DRONE)
        c_layout.addWidget(self.auto_connect_cb)

        # Kept so _retry_connection and the log pane still have their widgets,
        # but neither belongs on a first-run screen.
        self.auth_retry_btn = bind(QPushButton(), "auth.retry")
        self.auth_retry_btn.clicked.connect(self._retry_connection)
        self.auth_retry_btn.setVisible(False)
        c_layout.addWidget(self.auth_retry_btn)

        log_hint = QLabel(t("auth.log_file", path=applog.log_path()))
        log_hint.setWordWrap(True)
        log_hint.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        log_hint.setStyleSheet("font-size: 10px; color: #4d5560;")
        c_layout.addWidget(log_hint)

        self.bci_log_terminal = QPlainTextEdit()
        self.bci_log_terminal.setReadOnly(True)
        self.bci_log_terminal.setMaximumBlockCount(200)
        self.bci_log_terminal.setFixedHeight(90)
        c_layout.addWidget(self.bci_log_terminal)

        layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self.stacked_widget.addWidget(page)

    def setup_page_headset(self):
        # Step one, and the first thing anybody sees. The drone backdrop is
        # here to say what this application is before the user has read a word.
        page = HeroBackdrop(HERO_FILE)
        layout = QVBoxLayout(page)
        # Stretch above and below rather than layout.setAlignment(): setting
        # alignment on a top-level layout does not stop its item from being
        # stretched, which left the group box with a tall empty well under the
        # device list.
        layout.addStretch(1)

        container = QWidget(); container.setFixedWidth(600)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        mark = logo_label(height=LOGO_HERO_H)
        if mark is not None:
            c_layout.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "headset.title")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        c_layout.addWidget(title)

        tagline = bind(QLabel(), "headset.tagline")
        tagline.setWordWrap(True)
        tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        tagline.setStyleSheet("font-size: 13px; color: #8b949e;")
        c_layout.addWidget(tagline)

        self.headset_group = QGroupBox()
        bind(self.headset_group, "headset.group", "setTitle")
        headset_layout = QVBoxLayout(self.headset_group)
        headset_hdr = QHBoxLayout()
        self.headset_count_lbl = bind(QLabel(), "headset.awaiting_auth")
        self.headset_count_lbl.setStyleSheet("font-size: 12px; color: #8b949e;")
        headset_hdr.addWidget(self.headset_count_lbl)
        headset_hdr.addStretch()
        self.refresh_headsets_btn = bind(QPushButton(), "headset.refresh")
        bind(self.refresh_headsets_btn, "headset.refresh.tip", "setToolTip")
        # Not setFixedWidth: "🔄 Refresh" clipped to "Refres", and the
        # translations are longer still.
        self.refresh_headsets_btn.setMinimumWidth(110)
        self.refresh_headsets_btn.clicked.connect(self._refresh_headsets)
        headset_hdr.addWidget(self.refresh_headsets_btn)
        headset_layout.addLayout(headset_hdr)

        # A list, not a dropdown: with a handful of headsets in the room the
        # useful information is how many there are and what state each is in,
        # and a collapsed combo hides exactly that until you click it.
        self.headset_list = QListWidget()
        self.headset_list.setMinimumHeight(96)
        self.headset_list.setStyleSheet(
            "QListWidget { background-color: #0d1117; border: 1px solid #30363d;"
            " border-radius: 6px; padding: 4px; color: #e6edf3; font-size: 14px; }"
            "QListWidget::item { padding: 9px 10px; border-radius: 5px; }"
            "QListWidget::item:selected { background-color: #1f6feb; color: #ffffff; }"
            "QListWidget::item:hover:!selected { background-color: #161b22; }"
        )
        self.headset_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection)
        self.headset_list.itemDoubleClicked.connect(
            lambda item: self._connect_headset(
                item.data(Qt.ItemDataRole.UserRole)))
        headset_layout.addWidget(self.headset_list)

        # Shown instead of the list while there is nothing to choose from.
        self.headset_empty_lbl = bind(QLabel(), "headset.awaiting_auth")
        self.headset_empty_lbl.setWordWrap(True)
        self.headset_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headset_empty_lbl.setStyleSheet(
            "color: #8b949e; font-size: 13px; padding: 26px 10px;"
            "border: 1px dashed #30363d; border-radius: 6px;")
        headset_layout.addWidget(self.headset_empty_lbl)
        self.headset_list.setVisible(False)
        
        # No standalone Connect button and no status badge: each row carries
        # its own Connect, and the badge spent most of its life showing
        # "Scan Finished / Not Found", which said nothing the list does not.
        # Connection progress still goes to the log.
        headset_layout.addStretch()
        c_layout.addWidget(self.headset_group)
        self.headset_page_layout = c_layout

        # No way back to the credentials screen. It is a one-time setup step,
        # not a place to revisit: the app returns there on its own if the
        # credentials ever stop working. An always-present door back to it just
        # invites someone mid-demo to wander into a form they cannot use.

        layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self.stacked_widget.addWidget(page)

    def setup_page_profile(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(680)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "profile.title")
        c_layout.addWidget(title)

        self.profile_group = QGroupBox()
        bind(self.profile_group, "profile.group", "setTitle")
        profile_layout = QVBoxLayout(self.profile_group)

        # Everything that exists only to reuse an earlier profile lives in this
        # container, so hiding it is one call and none of the wiring changes.
        self.profile_list_box = QWidget()
        list_layout = QVBoxLayout(self.profile_list_box)
        list_layout.setContentsMargins(0, 0, 0, 0)

        profile_hdr = QHBoxLayout()
        profile_hdr.addWidget(bind(QLabel(), "profile.label"))
        profile_hdr.addStretch()
        self.refresh_profiles_btn = QPushButton()
        bind(self.refresh_profiles_btn, "profile.refresh")
        bind(self.refresh_profiles_btn, "profile.refresh.tip", "setToolTip")
        self.refresh_profiles_btn.setFixedWidth(90)
        self.refresh_profiles_btn.clicked.connect(self._refresh_profiles)
        profile_hdr.addWidget(self.refresh_profiles_btn)
        list_layout.addLayout(profile_hdr)

        self.profile_combo = QComboBox()
        self.profile_combo._placeholder_key = "profile.connect_first"
        self.profile_combo.addItem(t("profile.connect_first"))
        self.profile_combo.setStyleSheet(
            "QComboBox { background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
            "padding: 8px 12px; color: #8b949e; font-size: 14px; }"
            "QComboBox:enabled { color: #e6edf3; }"
            "QComboBox QAbstractItemView { background-color: #161b22; color: #e6edf3;"
            "selection-background-color: #1f6feb; border: 1px solid #30363d; }"
        )
        list_layout.addWidget(self.profile_combo)

        self.load_profile_btn = QPushButton()
        bind(self.load_profile_btn, "profile.load")
        self.load_profile_btn.setObjectName("primaryBtn")
        self.load_profile_btn.clicked.connect(self._load_selected_profile)
        list_layout.addWidget(self.load_profile_btn)

        self.profile_list_box.setVisible(SHOW_PROFILE_LIST)
        profile_layout.addWidget(self.profile_list_box)

        self.profile_status_lbl = QLabel()
        bind(self.profile_status_lbl, "profile.hint")
        self.profile_status_lbl.setStyleSheet(
            "color: #8b949e; font-size: 13px; font-style: italic; margin-top: 8px;"
        )
        profile_layout.addWidget(self.profile_status_lbl)
        
        # The one path that stays visible: name yourself, then train.
        create_lbl = bind(QLabel(), "profile.create_label")
        create_lbl.setStyleSheet(
            "font-size: 13px; color: #58a6ff; font-weight: bold; padding-top: 4px;")
        profile_layout.addWidget(create_lbl)

        train_layout = QHBoxLayout()
        self.new_profile_input = QLineEdit()
        bind(self.new_profile_input, "profile.new_placeholder", "setPlaceholderText")

        self.train_profile_btn = QPushButton()
        bind(self.train_profile_btn, "profile.create_train")
        self.train_profile_btn.setObjectName("primaryBtn")
        self.train_profile_btn.clicked.connect(self._create_and_train_profile)
        
        train_layout.addWidget(self.new_profile_input)
        train_layout.addWidget(self.train_profile_btn)
        profile_layout.addLayout(train_layout)

        self.profile_group.setEnabled(False)
        c_layout.addWidget(self.profile_group)

        # ── Next Button & Back Button ──
        btn_row = QHBoxLayout()
        back_btn = QPushButton()
        bind(back_btn, "profile.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_HEADSET))

        self.p0_next_btn = QPushButton()
        bind(self.p0_next_btn, "profile.next")
        self.p0_next_btn.setObjectName("primaryBtn")
        self.p0_next_btn.setEnabled(False)
        self.p0_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_TEST))
        
        board_btn = bind(QPushButton(), "game.show_leaderboard")
        board_btn.clicked.connect(lambda: self._show_leaderboard(PAGE_PROFILE))

        btn_row.addWidget(back_btn)
        btn_row.addWidget(board_btn)
        btn_row.addWidget(self.p0_next_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def _get_artifact_image_path(self, filename: str) -> str:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gemini", "antigravity-ide", "brain", "d3a45a7c-55b3-4531-b454-34ccaf34c9bd", filename)
        if not os.path.exists(path):
            path = f"/Users/giovaniflorek/.gemini/antigravity-ide/brain/d3a45a7c-55b3-4531-b454-34ccaf34c9bd/{filename}"
        return path

    def setup_page_eq_check(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(700)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel()
        bind(title, "eq.title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #58a6ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(title)

        subtitle = QLabel()
        bind(subtitle, "eq.subtitle")
        subtitle.setStyleSheet("font-size: 14px; color: #8b949e;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(subtitle)

        self.eq_overall_lbl = QLabel()
        bind(self.eq_overall_lbl, "eq.overall_waiting")
        self.eq_overall_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.eq_overall_lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #e6edf3;"
            "padding: 10px; background-color: #161b22; border: 1px solid #30363d; border-radius: 8px;"
        )
        c_layout.addWidget(self.eq_overall_lbl)

        map_group = QGroupBox()
        bind(map_group, "eq.headmap_group", "setTitle")
        map_layout = QVBoxLayout(map_group)
        self.sensor_map = SensorHeadMapWidget()
        self.sensor_map.setMinimumHeight(320)
        map_layout.addWidget(self.sensor_map)
        map_hint = bind(QLabel(), "eq.headmap_hint")
        map_hint.setWordWrap(True)
        map_hint.setStyleSheet("font-size: 11px; color: #6e7681;")
        map_layout.addWidget(map_hint)

        sensor_group = QGroupBox()
        bind(sensor_group, "eq.group", "setTitle")
        self.eq_sensor_layout = QGridLayout(sensor_group)
        self.eq_sensor_layout.setSpacing(8)
        self.eq_sensor_labels = {}

        eq_split = QHBoxLayout()
        eq_split.setSpacing(12)
        eq_split.addWidget(map_group, stretch=3)
        eq_split.addWidget(sensor_group, stretch=2)
        c_layout.addLayout(eq_split)

        self.eq_status_lbl = QLabel()
        bind(self.eq_status_lbl, "eq.waiting_data")
        self.eq_status_lbl.setWordWrap(True)
        self.eq_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.eq_status_lbl.setStyleSheet("font-size: 14px; color: #e3a01a; margin-top: 10px;")
        c_layout.addWidget(self.eq_status_lbl)

        btn_row = QHBoxLayout()
        back_btn = QPushButton()
        bind(back_btn, "eq.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_PROFILE))

        self.eq_next_btn = QPushButton()
        bind(self.eq_next_btn, "eq.next")
        self.eq_next_btn.setObjectName("primaryBtn")
        self.eq_next_btn.setEnabled(False)
        self.eq_next_btn.clicked.connect(self._start_training_from_eq)

        btn_row.addWidget(back_btn)
        btn_row.addWidget(self.eq_next_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def _start_training_from_eq(self):
        self._begin_training_sequence("neutral")

    def _begin_training_sequence(self, action):
        self.current_training_action = action
        if action == "neutral":
            self.stacked_widget.setCurrentIndex(PAGE_TRAIN_NEUTRAL)
            self.neutral_sim.reset_flight()
        else:
            self.stacked_widget.setCurrentIndex(PAGE_TRAIN_PUSH)
            self.push_sim.reset_flight()

        # A retry from the result screen leaves the old buttons showing.
        for btn in (self.neutral_accept_btn, self.neutral_reject_btn,
                    self.push_accept_btn, self.push_reject_btn, self.push_next_btn):
            btn.hide()

        if not hasattr(self, "countdown_overlay"):
            self.countdown_overlay = QLabel(self.stacked_widget)
            self.countdown_overlay.setStyleSheet("font-size: 120px; font-weight: bold; color: rgba(255, 123, 114, 255); background-color: rgba(0, 0, 0, 150); border-radius: 20px;")
            self.countdown_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
        self.countdown_overlay.resize(200, 200)
        sw_rect = self.stacked_widget.rect()
        self.countdown_overlay.move(
            int((sw_rect.width() - 200) / 2),
            int((sw_rect.height() - 200) / 2)
        )
        
        self.countdown_val = 3
        self.countdown_overlay.setText(str(self.countdown_val))
        self.countdown_overlay.show()
        self.countdown_overlay.raise_()
        
        lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
        bind(lbl, "train.get_ready")

        if hasattr(self, "countdown_timer") and self.countdown_timer.isActive():
            self.countdown_timer.stop()
            
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(lambda: self._on_countdown_tick(action))
        self.countdown_timer.start(1000)

    def _on_countdown_tick(self, action):
        self.countdown_val -= 1
        if self.countdown_val > 0:
            self.countdown_overlay.setText(str(self.countdown_val))
        else:
            self.countdown_timer.stop()
            self.countdown_overlay.hide()
            
            lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
            self.recording_val = 8
            bind(lbl, "train.recording", seconds=self.recording_val)

            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
                
            self.recording_timer = QTimer(self)
            self.recording_timer.timeout.connect(lambda: self._on_recording_tick(action))
            self.recording_timer.start(1000)
            
            if action == "push":
                self.push_anim_timer.start(50)
                
            self.drone_client.start_training(action)

    def _on_recording_tick(self, action):
        self.recording_val -= 1
        lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
        if self.recording_val > 0:
            bind(lbl, "train.recording", seconds=self.recording_val)
        else:
            self.recording_timer.stop()
            bind(lbl, "train.finishing")

    def setup_page_train_neutral(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Contact quality belongs here more than anywhere: a training take
        # recorded through a loose electrode is what produces a profile that
        # never works, and the failure is invisible without this.
        pill_row = QHBoxLayout()
        pill_row.addStretch()
        pill_row.addWidget(self._new_device_pill())
        layout.addLayout(pill_row)

        title = QLabel()
        bind(title, "train.neutral.title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #58a6ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel()
        bind(subtitle, "train.neutral.subtitle")
        subtitle.setStyleSheet("font-size: 14px; color: #8b949e;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        self.neutral_sim = DroneSimulatorWidget(self, mode=DroneSimulatorWidget.TRAINING)
        self.neutral_sim.set_training_cue("neutral")
        self.neutral_sim.setMinimumSize(500, 350)
        layout.addWidget(self.neutral_sim, stretch=1)

        self.neutral_status_lbl = QLabel()
        bind(self.neutral_status_lbl, "train.waiting")
        self.neutral_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.neutral_status_lbl.setStyleSheet("font-size: 16px; color: #e6edf3;")
        layout.addWidget(self.neutral_status_lbl)
        
        btn_layout = QHBoxLayout()
        self.neutral_accept_btn = QPushButton()
        bind(self.neutral_accept_btn, "train.accept")
        self.neutral_accept_btn.setObjectName("primaryBtn")
        self.neutral_accept_btn.clicked.connect(lambda: self._on_training_accept("neutral"))
        self.neutral_accept_btn.hide()

        self.neutral_reject_btn = QPushButton()
        bind(self.neutral_reject_btn, "train.reject")
        self.neutral_reject_btn.setObjectName("dangerBtn")
        self.neutral_reject_btn.clicked.connect(lambda: self._on_training_reject("neutral"))
        self.neutral_reject_btn.hide()
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.neutral_accept_btn)
        btn_layout.addWidget(self.neutral_reject_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        exit_row = QHBoxLayout()
        exit_row.addWidget(self._make_abandon_button())
        exit_row.addStretch()
        layout.addLayout(exit_row)

        self.stacked_widget.addWidget(page)

    def setup_page_train_push(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        pill_row = QHBoxLayout()
        pill_row.addStretch()
        pill_row.addWidget(self._new_device_pill())
        layout.addLayout(pill_row)

        title = QLabel()
        bind(title, "train.push.title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #58a6ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel()
        bind(subtitle, "train.push.subtitle")
        subtitle.setStyleSheet("font-size: 14px; color: #8b949e;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        self.push_sim = DroneSimulatorWidget(self, mode=DroneSimulatorWidget.TRAINING)
        self.push_sim.set_training_cue("push")
        self.push_sim.setMinimumSize(500, 350)
        layout.addWidget(self.push_sim, stretch=1)
        
        # Timer to animate the push sim forward
        self.push_anim_timer = QTimer()
        self.push_anim_timer.timeout.connect(lambda: self.push_sim.update_rc(0, 10, 0, 0))
        
        self.push_status_lbl = QLabel()
        bind(self.push_status_lbl, "train.waiting")
        self.push_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.push_status_lbl.setStyleSheet("font-size: 16px; color: #e6edf3;")
        layout.addWidget(self.push_status_lbl)
        
        btn_layout = QHBoxLayout()
        self.push_accept_btn = QPushButton()
        bind(self.push_accept_btn, "train.accept")
        self.push_accept_btn.setObjectName("primaryBtn")
        self.push_accept_btn.clicked.connect(lambda: self._on_training_accept("push"))
        self.push_accept_btn.hide()

        self.push_reject_btn = QPushButton()
        bind(self.push_reject_btn, "train.reject")
        self.push_reject_btn.setObjectName("dangerBtn")
        self.push_reject_btn.clicked.connect(lambda: self._on_training_reject("push"))
        self.push_reject_btn.hide()

        self.push_next_btn = QPushButton()
        bind(self.push_next_btn, "train.finish")
        self.push_next_btn.setObjectName("primaryBtn")
        self.push_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_TEST))
        self.push_next_btn.hide()
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.push_accept_btn)
        btn_layout.addWidget(self.push_reject_btn)
        btn_layout.addWidget(self.push_next_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        exit_row = QHBoxLayout()
        exit_row.addWidget(self._make_abandon_button())
        exit_row.addStretch()
        layout.addLayout(exit_row)

        self.stacked_widget.addWidget(page)

    def setup_page_1(self):
        page = QWidget()
        # Unlike the setup pages, this one is not a form — it is a scene, and a
        # fixed 1000px column left most of a wide monitor empty. Grow with the
        # window up to a cap, centred by stretches on either side.
        layout = QHBoxLayout(page)
        layout.addStretch(1)

        container = QWidget()
        container.setMaximumWidth(1500)
        container.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(10)

        # ── Top bar: who is playing, and the board ───────────────────────────
        # No step title and no how-to panel here any more. Both were framing
        # around the game; the controls are explained inside the scene, where
        # the player is already looking.
        top_bar = QHBoxLayout()

        name_box = QVBoxLayout()
        name_box.setSpacing(0)
        playing_as = bind(QLabel(), "game.playing_as")
        playing_as.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #6e7681;"
            "letter-spacing: 2px;")
        name_box.addWidget(playing_as)

        # The player's name is the one piece of identity on screen and the name
        # that goes on the board, so it is sized like a scoreboard entry.
        self.player_name_lbl = bind(QLabel(), "game.no_profile")
        self.player_name_lbl.setStyleSheet(
            "font-size: 30px; font-weight: bold; color: #f1c40f;")
        name_box.addWidget(self.player_name_lbl)
        top_bar.addLayout(name_box)
        top_bar.addStretch()

        self.device_pill = self._new_device_pill()
        top_bar.addWidget(self.device_pill, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_bar.addSpacing(12)

        leaderboard_btn = bind(QPushButton(), "game.show_leaderboard")
        leaderboard_btn.setMinimumHeight(38)
        leaderboard_btn.clicked.connect(
            lambda: self._show_leaderboard(PAGE_TEST))
        top_bar.addWidget(leaderboard_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        c_layout.addLayout(top_bar)

        # ── The scene, given everything that is left ─────────────────────────
        self.state_layout = QVBoxLayout()
        # 1px of margin so the frame's border is not painted over by the
        # simulator, which fills its own rect opaquely.
        self.state_layout.setContentsMargins(1, 1, 1, 1)
        self.drone_sim = DroneSimulatorWidget(self)
        self.drone_sim.setMinimumSize(660, 400)
        self.drone_sim.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
        self.state_layout.addWidget(self.drone_sim, stretch=1)

        scene_frame = QWidget()
        scene_frame.setLayout(self.state_layout)
        scene_frame.setStyleSheet(
            "background-color: #05080d; border: 1px solid #30363d;"
            "border-radius: 10px;")
        c_layout.addWidget(scene_frame, stretch=1)

        # ── Bottom bar: settings and secondary actions left, the CTA right ───
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(16)

        left_stack = QVBoxLayout()
        left_stack.setSpacing(8)

        mc_row = QHBoxLayout()
        mc_row.setSpacing(12)
        mc_caption = bind(QLabel(), "tune.mental")
        mc_caption.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #6e7681;"
            "letter-spacing: 1px;")
        mc_row.addWidget(mc_caption)

        self.mc_sens_layout = QHBoxLayout()
        self.mc_sens_layout.setSpacing(16)
        mc_row.addLayout(self.mc_sens_layout)

        self.mc_sens_hint = bind(QLabel(), "tune.mental_waiting")
        self.mc_sens_hint.setStyleSheet("font-size: 11px; color: #6e7681;")
        mc_row.addWidget(self.mc_sens_hint)
        mc_row.addStretch()
        left_stack.addLayout(mc_row)

        self.inline_mc_sliders = []

        # Secondary actions, deliberately quiet next to Start Run.
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        back_btn = bind(QPushButton(), "test.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_PROFILE))

        self.recenter_btn_p1 = bind(QPushButton(), "test.recenter")
        self.recenter_btn_p1.setObjectName("blueBtn")
        # The old how-to panel's line about recentring lives here now: it is
        # advice about this button, so it belongs on it.
        bind(self.recenter_btn_p1, "howto.recenter", "setToolTip")
        self.recenter_btn_p1.clicked.connect(self.reset_headset)

        self.retrain_btn = bind(QPushButton(), "retrain.button")
        bind(self.retrain_btn, "retrain.tip", "setToolTip")
        self.retrain_btn.clicked.connect(self._reset_and_retrain)

        self.real_drone_btn = bind(QPushButton(), "test.next")
        self.real_drone_btn.clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(PAGE_DRONE))
        self.real_drone_btn.setVisible(SHOW_REAL_DRONE)

        for button in (back_btn, self.recenter_btn_p1, self.retrain_btn,
                       self.real_drone_btn):
            action_row.addWidget(button)
        action_row.addStretch()
        left_stack.addLayout(action_row)

        bottom_bar.addLayout(left_stack, stretch=1)

        # The one thing the screen is asking you to do, in the corner a game
        # puts it and sized to match.
        cta_box = QVBoxLayout()
        cta_box.setSpacing(2)
        run_caption = bind(QLabel(), "game.group", seconds=RUN_SECONDS)
        run_caption.setStyleSheet("font-size: 11px; color: #6e7681;")
        run_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        cta_box.addWidget(run_caption)

        self.start_run_btn = bind(QPushButton(), "game.start")
        self.start_run_btn.setObjectName("heroBtn")
        self.start_run_btn.setMinimumSize(300, 68)
        self.start_run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_run_btn.clicked.connect(self._start_ring_run)
        cta_box.addWidget(self.start_run_btn)
        bottom_bar.addLayout(cta_box)

        c_layout.addLayout(bottom_bar)


        layout.addWidget(container, stretch=20)
        layout.addStretch(1)
        self.stacked_widget.addWidget(page)

    def setup_page_2(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(500)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(20)

        title = bind(QLabel(), "drone.title"); title.setObjectName("titleLabel")
        subtitle = bind(QLabel(), "drone.subtitle")
        subtitle.setObjectName("subtitleLabel"); subtitle.setWordWrap(True)
        c_layout.addWidget(title); c_layout.addWidget(subtitle)

        self.drone_conn_status_lbl = bind(QLabel(), "drone.ready")
        self.drone_conn_status_lbl.setObjectName("subtitleLabel")
        c_layout.addWidget(self.drone_conn_status_lbl)

        self.connect_drone_btn = bind(QPushButton(), "drone.connect")
        self.connect_drone_btn.setObjectName("blueBtn")
        self.connect_drone_btn.clicked.connect(self.check_drone_connection)
        c_layout.addWidget(self.connect_drone_btn)

        self.p2_next_btn = bind(QPushButton(), "drone.launch"); self.p2_next_btn.setObjectName("primaryBtn")
        self.p2_next_btn.setEnabled(False)
        self.p2_next_btn.clicked.connect(self.go_to_dashboard)
        c_layout.addWidget(self.p2_next_btn)

        back_btn = bind(QPushButton(), "drone.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_TEST))
        c_layout.addWidget(back_btn)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def setup_page_3(self):
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(15, 15, 15, 15)

        left = QVBoxLayout()
        cam_group = bind(QGroupBox(), "dash.camera", "setTitle")
        cam_layout = QVBoxLayout()
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setStyleSheet("background-color: #010409; border-radius: 8px; border: 1px solid #30363d;")
        self.camera_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cam_layout.addWidget(self.camera_label)
        cam_group.setLayout(cam_layout)
        left.addWidget(cam_group, stretch=1)

        telem_group = bind(QGroupBox(), "dash.telemetry", "setTitle")
        telem_grid = QGridLayout()
        self.battery_lbl = bind(QLabel(), "dash.battery_empty")
        self.height_lbl = bind(QLabel(), "dash.height_empty")
        self.temp_lbl = bind(QLabel(), "dash.temp_empty")
        self.bci_telem_lbl = bind(QLabel(), "dash.headset_empty")
        for i, lbl in enumerate([self.battery_lbl, self.height_lbl, self.temp_lbl, self.bci_telem_lbl]):
            lbl.setStyleSheet("font-size: 13px; color: #8b949e;")
            telem_grid.addWidget(lbl, 0, i)
        
        self.rc_lbl = QLabel("RC: lr=0 fb=0 ud=0 yaw=0")
        self.rc_lbl.setStyleSheet("font-size: 13px; color: #58a6ff; font-family: monospace;")
        telem_grid.addWidget(self.rc_lbl, 1, 0, 1, 4)
        telem_group.setLayout(telem_grid)
        left.addWidget(telem_group)

        btn_group = bind(QGroupBox(), "dash.controls", "setTitle")
        btn_layout = QHBoxLayout()
        self.takeoff_btn = bind(QPushButton(), "dash.takeoff"); self.takeoff_btn.setObjectName("primaryBtn")
        self.takeoff_btn.clicked.connect(self.takeoff)
        self.land_btn = bind(QPushButton(), "dash.land"); self.land_btn.setObjectName("dangerBtn")
        self.land_btn.clicked.connect(self.land)
        self.emergency_btn = bind(QPushButton(), "dash.emergency"); self.emergency_btn.setObjectName("dangerBtn")
        self.emergency_btn.setStyleSheet("border: 2px solid #fff;")
        self.emergency_btn.clicked.connect(self.emergency_stop)
        self.recenter_btn_p3 = bind(QPushButton(), "dash.recenter"); self.recenter_btn_p3.setObjectName("blueBtn")
        self.recenter_btn_p3.clicked.connect(self.reset_headset)
        
        btn_layout.addWidget(self.takeoff_btn)
        btn_layout.addWidget(self.land_btn)
        btn_layout.addWidget(self.recenter_btn_p3)
        btn_layout.addWidget(self.emergency_btn)
        btn_group.setLayout(btn_layout)
        left.addWidget(btn_group)

        root.addLayout(left, stretch=3)

        right = QVBoxLayout()
        top_bar = QVBoxLayout()
        status_row = QHBoxLayout()
        self.dash_drone_lbl = bind(QLabel(), "dash.drone_connected"); self.dash_drone_lbl.setObjectName("statusBadge")
        self.dash_bci_lbl = bind(QLabel(), "badge.bci_active"); self.dash_bci_lbl.setObjectName("statusBadge")
        status_row.addWidget(self.dash_drone_lbl); status_row.addWidget(self.dash_bci_lbl)
        status_row.addStretch()
        top_bar.addLayout(status_row)
        
        # MC Indicator
        self.dash_mc_lbl = bind(QLabel(), "dash.mc_none")
        self.dash_mc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dash_mc_lbl.setStyleSheet(
            "background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
            "padding: 8px 12px; color: #8b949e; font-size: 14px; font-weight: bold;"
        )
        top_bar.addWidget(self.dash_mc_lbl)
        right.addLayout(top_bar)

        # Action Buttons
        act_group = bind(QGroupBox(), "dash.system", "setTitle")
        act_layout = QVBoxLayout()
        self.hud_btn = bind(QPushButton(), "dash.hud")
        self.hud_btn.setObjectName("blueBtn")
        self.hud_btn.clicked.connect(self.open_fullscreen_hud)
        act_layout.addWidget(self.hud_btn)

        self.disconnect_btn = bind(QPushButton(), "dash.disconnect")
        self.disconnect_btn.setObjectName("dangerBtn")
        self.disconnect_btn.clicked.connect(self._disconnect_and_quit)
        act_layout.addWidget(self.disconnect_btn)
        act_group.setLayout(act_layout)
        right.addWidget(act_group)

        term_group = bind(QGroupBox(), "dash.log", "setTitle")
        term_layout = QVBoxLayout()
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setMaximumBlockCount(500)
        term_layout.addWidget(self.terminal)
        term_group.setLayout(term_layout)
        right.addWidget(term_group, stretch=1)

        root.addLayout(right, stretch=1)
        self.stacked_widget.addWidget(page)

    # ──────────────────────────────────────────────
    # Ring run: timed game, results, leaderboard
    # ──────────────────────────────────────────────
    def setup_page_gameover(self):
        """Where a run lands: your score, your rank, and what to do next."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(640)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(14)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "game.over_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(title)

        self.final_score_lbl = QLabel("0")
        self.final_score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_score_lbl.setStyleSheet(
            "font-size: 64px; font-weight: bold; color: #f1c40f;")
        c_layout.addWidget(self.final_score_lbl)

        self.final_detail_lbl = QLabel()
        self.final_detail_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_detail_lbl.setStyleSheet("font-size: 14px; color: #8b949e;")
        c_layout.addWidget(self.final_detail_lbl)

        self.rank_lbl = QLabel()
        self.rank_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rank_lbl.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #58a6ff; padding: 4px;")
        c_layout.addWidget(self.rank_lbl)

        self.congrats_lbl = QLabel()
        self.congrats_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.congrats_lbl.setWordWrap(True)
        c_layout.addWidget(self.congrats_lbl)

        # The whole point of the exercise, said out loud: they flew it with EEG.
        self.mind_lbl = bind(QLabel(), "game.mind_message")
        self.mind_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mind_lbl.setWordWrap(True)
        self.mind_lbl.setStyleSheet("font-size: 15px; color: #bc8cff;")
        c_layout.addWidget(self.mind_lbl)

        podium_group = QGroupBox()
        bind(podium_group, "game.podium", "setTitle")
        self.podium_grid = QGridLayout(podium_group)
        self.podium_grid.setSpacing(6)
        c_layout.addWidget(podium_group)

        btn_row = QHBoxLayout()
        self.try_again_btn = bind(QPushButton(), "game.try_again")
        self.try_again_btn.setObjectName("primaryBtn")
        self.try_again_btn.clicked.connect(self._try_again)

        full_board_btn = bind(QPushButton(), "game.show_leaderboard")
        full_board_btn.clicked.connect(lambda: self._show_leaderboard(PAGE_GAMEOVER))

        finish_btn = bind(QPushButton(), "game.finish")
        finish_btn.clicked.connect(self._finish_session)

        btn_row.addWidget(self.try_again_btn)
        btn_row.addWidget(full_board_btn)
        btn_row.addWidget(finish_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)
        self.gameover_confetti = ConfettiOverlay(page)

    def setup_page_leaderboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(660)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(12)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "game.leaderboard_title")
        c_layout.addWidget(title)

        subtitle = bind(QLabel(), "game.leaderboard_subtitle")
        subtitle.setObjectName("subtitleLabel"); subtitle.setWordWrap(True)
        c_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(360)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #30363d; border-radius: 10px;"
            " background-color: #0b0f15; }")
        holder = QWidget()
        self.board_grid = QGridLayout(holder)
        self.board_grid.setSpacing(6)
        self.board_grid.setContentsMargins(14, 14, 14, 14)
        self.board_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(holder)
        c_layout.addWidget(scroll)

        # When the player is not in the visible top slice, pin their row here so
        # "where did I come?" never needs scrolling.
        self.board_you_lbl = QLabel()
        self.board_you_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.board_you_lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #58a6ff;"
            "background-color: #131c2b; border: 1px solid #1f6feb;"
            "border-radius: 8px; padding: 8px;")
        c_layout.addWidget(self.board_you_lbl)

        back_btn = bind(QPushButton(), "game.back")
        back_btn.clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(self._board_return_page))
        c_layout.addWidget(back_btn)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    # ── Run lifecycle ────────────────────────────────────────────────────────
    COUNTDOWN_SECONDS = 3

    def _start_ring_run(self):
        if self.run_timer.isActive() or self.run_countdown_timer.isActive():
            return
        name = (self.config.get("profile_name") or "").strip() or t("game.anonymous")
        self.current_player = name

        self.start_run_btn.setEnabled(False)
        bind(self.start_run_btn, "game.get_ready")

        # Clean slate to fly from, but no clock and no scoring until "Go!".
        self.drone_sim.end_run()
        self.drone_sim.reset_flight()
        self._countdown_left = self.COUNTDOWN_SECONDS
        self.drone_sim.set_countdown(t("game.get_ready"), self._countdown_left)
        self.run_countdown_timer.start(1000)

    def _on_countdown_step(self):
        self._countdown_left -= 1
        if self._countdown_left > 0:
            self.drone_sim.set_countdown(t("game.get_ready"), self._countdown_left)
            return

        if self._countdown_left == 0:
            # "Go!" gets its own beat before the clock appears.
            self.drone_sim.set_countdown(None, t("game.go"))
            return

        self.run_countdown_timer.stop()
        self._begin_timed_run()

    def _begin_timed_run(self):
        # Recentre on the spot. The countdown has just finished, so the player
        # is looking at the screen with their head where they mean it to be --
        # the one moment in the whole flow when "straight ahead" is known
        # rather than guessed. Whatever the headset accumulated while the
        # previous player wore it, or during naming and training, goes with it.
        #
        # This is what drift correction was reaching for, without an estimator
        # that can mistake a held turn for a drifting sensor.
        if self.drone_client:
            self.drone_client.reset_center()
            self.log(t("log.recenter"))

        self.drone_sim.start_run(RUN_SECONDS)
        self._run_deadline = time.monotonic() + RUN_SECONDS
        self.run_timer.start(100)
        bind(self.start_run_btn, "game.running")
        self.log(t("log.run_started", name=self.current_player, seconds=RUN_SECONDS))

    def _on_run_tick(self):
        remaining = self._run_deadline - time.monotonic()
        self.drone_sim.set_time_left(remaining)
        if remaining <= 0:
            self._finish_ring_run()

    def _finish_ring_run(self):
        self.run_timer.stop()
        score = self.drone_sim.score
        coins = score // 10
        self.drone_sim.end_run()
        self.start_run_btn.setEnabled(True)
        bind(self.start_run_btn, "game.start")

        self.current_entry = leaderboard.add(
            self.current_player, score, coins,
            profile=self.config.get("profile_name", ""))
        self.log(t("log.run_finished", name=self.current_player, score=score))

        if self.drone_sim.isFullScreen():
            self._show_fullscreen_result()
        else:
            self._populate_gameover()
            self.stacked_widget.setCurrentIndex(PAGE_GAMEOVER)

    def _show_fullscreen_result(self):
        """Result over the fullscreen simulator, so nobody has to leave it."""
        entries = leaderboard.load()
        rank = leaderboard.rank_of(self.current_entry, entries)

        dialog = FullscreenResultDialog(
            self.current_entry, rank, len(entries), entries, self)
        dialog.setGeometry(self.drone_sim.screen().geometry())
        dialog.showFullScreen()
        dialog.exec()

        if dialog.choice == "again":
            self._start_ring_run()          # stays fullscreen
            return

        # Everything else means leaving fullscreen, so the main window is
        # visible again before we navigate it.
        if self.drone_sim.isFullScreen():
            self.toggle_fullscreen()

        if dialog.choice == "finish":
            self._finish_session()
        else:
            self._populate_gameover()
            self.stacked_widget.setCurrentIndex(PAGE_GAMEOVER)

    def _try_again(self):
        self.stacked_widget.setCurrentIndex(PAGE_TEST)
        self._start_ring_run()

    def _finish_session(self):
        """Finish: bin the training and hand the headset to the next person.

        No prompt any more. The score already lives on the leaderboard under the
        player's name, so the trained profile has nothing left worth keeping, and
        asking about it every single handoff was a question with one sensible
        answer. Landing on the device list rather than profile creation is
        deliberate too: the next person may well be on a different headset, so
        the list is rescanned on the way in.
        """
        profile = (self.config.get("profile_name") or "").strip()
        if profile and self.drone_client:
            self.log(t("log.profile_deleting", profile=profile))
            self.config["profile_name"] = ""
            ConfigManager.save_config(self.config)
        else:
            profile = ""

        # The sensitivity panel is showing the outgoing player's actions; blank
        # it so the next profile rebuilds it from its own training.
        self.mc_active_actions = []
        self.mc_sensitivities = []
        self._build_inline_mc_sliders()

        self.current_entry = None
        self._refresh_player_name()
        self.drone_sim.end_run()
        self.drone_sim.reset_flight()

        # Hand the headset back: close the session and drop the link, then
        # rescan. Without the disconnect the next player lands on a list still
        # showing a headset held open by the run that just ended, and picking it
        # reuses the outgoing session instead of starting clean.
        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
        self._release_headset(profile)
        self.log(t("log.session_handoff"))

    def _release_headset(self, profile: str = ""):
        """Delete the outgoing profile, disconnect, then rescan for headsets.

        One worker thread for the whole sequence: the steps are ordered and
        every one of them is a blocking Cortex send.
        """
        if not self.drone_client:
            self.log(t("log.client_not_init"))
            return

        # Back to the pre-connection look while the rescan runs, so the list
        # cannot be mistaken for a live one.
        self.headset_list.clear()
        self.headset_rows = []
        self.headset_list.setVisible(False)
        self.headset_empty_lbl.setVisible(True)
        bind(self.headset_empty_lbl, "headset.refreshing")
        bind(self.headset_count_lbl, "headset.refreshing")
        self.refresh_headsets_btn.setEnabled(False)
        bind(self.refresh_headsets_btn, "headset.refreshing")
        self.profile_group.setEnabled(False)

        # The outgoing headset's electrodes are not the next one's: clear the
        # map and the rows so nothing stale is on screen when the list rebuilds.
        self.dev_sensor_labels = []
        self._dev_keep_idx = None
        self._dev_overall_idx = None
        self.sensor_map.clear()
        self._pills_device("")
        self._pills_quality(None, [], [], None)
        self._pills_battery(None)
        clear_grid(self.eq_sensor_layout)
        self.eq_sensor_labels = {}
        self.log(t("log.releasing_headset"))

        def done():
            self.refresh_headsets_btn.setEnabled(True)
            bind(self.refresh_headsets_btn, "headset.refresh")

        def work():
            try:
                self.drone_client.finish_session(profile)
            except Exception as e:
                self.log(t("log.refresh_failed", detail=e))
            finally:
                self.ui_task_signal.emit(done)

        threading.Thread(target=work, daemon=True).start()

    def _on_profile_admin(self, event: dict):
        kind = event.get("type")
        profile = event.get("profile", "")
        if kind == "deleted":
            self.log(t("log.profile_deleted", profile=profile))
            bind(self.profile_status_lbl, "profile.deleted", profile=profile)
        elif kind == "reset":
            self.log(t("log.profile_reset", profile=profile))
            bind(self.profile_status_lbl, "profile.reset_done", profile=profile)
        self.profile_status_lbl.setStyleSheet(
            "color: #8b949e; font-size: 11px; font-style: italic; padding: 0 2px;")

    # ── Result rendering ─────────────────────────────────────────────────────
    def _clear_grid(self, grid):
        clear_grid(grid)

    def _add_board_row(self, grid, row, rank, entry, highlight):
        add_board_row(grid, row, rank, entry, highlight)

    def _populate_gameover(self):
        entry = self.current_entry or {}
        score = entry.get("score", 0)
        self.final_score_lbl.setText(str(score))
        self.final_detail_lbl.setText(t(
            "game.final_detail",
            name=entry.get("name", ""),
            coins=entry.get("coins", 0),
            seconds=RUN_SECONDS,
        ))

        entries = leaderboard.load()
        rank = leaderboard.rank_of(entry, entries)
        total = len(entries)
        if rank == 1 and total > 1:
            self.rank_lbl.setText(t("game.rank_first"))
            self.rank_lbl.setStyleSheet(
                "font-size: 20px; font-weight: bold; color: #f1c40f; padding: 4px;")
        else:
            self.rank_lbl.setText(t("game.rank", rank=rank, total=total))
            self.rank_lbl.setStyleSheet(
                "font-size: 20px; font-weight: bold; color: #58a6ff; padding: 4px;")

        message, colour, celebrate = congratulation(rank, total)
        self.rank_lbl.setVisible(not message)
        self.congrats_lbl.setText(message)
        self.congrats_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {colour}; padding: 2px;")
        self.mind_lbl.setVisible(bool(message))
        if celebrate:
            self.gameover_confetti.start()
        else:
            self.gameover_confetti.stop()

        self._clear_grid(self.podium_grid)
        for i, e in enumerate(entries[:5]):
            self._add_board_row(self.podium_grid, i, i + 1, e, e is entry)
        # Player finished outside the top 5 — show their row underneath so the
        # screen always answers "how did I do?" without another click.
        if rank > 5:
            gap = QLabel("⋯")
            gap.setStyleSheet("color: #6e7681; padding: 2px 8px;")
            self.podium_grid.addWidget(gap, 5, 0)
            self._add_board_row(self.podium_grid, 6, rank, entry, True)

    def _show_leaderboard(self, return_page: int):
        self._board_return_page = return_page
        entries = leaderboard.load()
        self._clear_grid(self.board_grid)

        if not entries:
            empty = bind(QLabel(), "game.board_empty")
            empty.setStyleSheet("color: #8b949e; font-size: 14px; padding: 20px;")
            self.board_grid.addWidget(empty, 0, 0, 1, 4)
            self.board_you_lbl.hide()
            self.stacked_widget.setCurrentIndex(PAGE_LEADERBOARD)
            return

        shown = entries[:20]
        rank = leaderboard.rank_of(self.current_entry, entries) if self.current_entry else 0
        for i, e in enumerate(shown):
            self._add_board_row(self.board_grid, i, i + 1, e,
                                self.current_entry is not None and e is self.current_entry)

        # Always pin the player's own line, whether or not their row is visible
        # above — the question this screen has to answer is "where did I come?".
        if rank:
            self.board_you_lbl.setText(t(
                "game.your_position", rank=rank, total=len(entries),
                score=self.current_entry.get("score", 0)))
            self.board_you_lbl.show()
        else:
            self.board_you_lbl.hide()

        self.stacked_widget.setCurrentIndex(PAGE_LEADERBOARD)

    def setup_page_brainmap(self):
        """Training result: the brain map, a verdict, and a way to redo it."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(760)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(12)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "brainmap.title")
        c_layout.addWidget(title)

        subtitle = bind(QLabel(), "brainmap.subtitle")
        subtitle.setObjectName("subtitleLabel"); subtitle.setWordWrap(True)
        c_layout.addWidget(subtitle)

        self.brain_map = BrainMapWidget()
        c_layout.addWidget(self.brain_map)

        self.brainmap_verdict_lbl = bind(QLabel(), "brainmap.loading")
        self.brainmap_verdict_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brainmap_verdict_lbl.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #8b949e; padding: 6px;")
        c_layout.addWidget(self.brainmap_verdict_lbl)

        self.brainmap_hint_lbl = QLabel()
        self.brainmap_hint_lbl.setWordWrap(True)
        self.brainmap_hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brainmap_hint_lbl.setStyleSheet("font-size: 13px; color: #8b949e;")
        c_layout.addWidget(self.brainmap_hint_lbl)

        btn_row = QHBoxLayout()
        self.brainmap_retrain_btn = bind(QPushButton(), "brainmap.retrain")
        self.brainmap_retrain_btn.clicked.connect(self._retrain_from_brainmap)

        refresh_btn = bind(QPushButton(), "brainmap.refresh")
        refresh_btn.clicked.connect(self._request_brain_map)

        self.brainmap_next_btn = bind(QPushButton(), "brainmap.continue")
        self.brainmap_next_btn.setObjectName("primaryBtn")
        self.brainmap_next_btn.clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(PAGE_TEST))

        btn_row.addWidget(self.brainmap_retrain_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(self.brainmap_next_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def _request_brain_map(self):
        if self.drone_client:
            bind(self.brainmap_verdict_lbl, "brainmap.loading")
            self.brainmap_verdict_lbl.setStyleSheet(
                "font-size: 15px; font-weight: bold; color: #8b949e; padding: 6px;")
            threading.Thread(target=self.drone_client.get_brain_map, daemon=True).start()

    def _on_brain_map(self, data: list):
        """Cortex answered mentalCommandBrainMap — plot it and grade it."""
        self.brain_map.set_points(data)
        key, colour = self.brain_map.quality_key()

        gap = self.brain_map.separation()
        if gap is None:
            bind(self.brainmap_verdict_lbl, key)
        else:
            bind(self.brainmap_verdict_lbl, key)
            self.brainmap_verdict_lbl.setText(
                f"{t(key)}   ·   {t('brainmap.separation', gap=f'{gap:.2f}')}")
        self.brainmap_verdict_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {colour}; padding: 6px;")

        hint = {"brainmap.quality.good": "brainmap.hint.good",
                "brainmap.quality.fair": "brainmap.hint.fair",
                "brainmap.quality.poor": "brainmap.hint.poor"}.get(key)
        if hint:
            bind(self.brainmap_hint_lbl, hint)
        else:
            i18n.unbind(self.brainmap_hint_lbl)
            self.brainmap_hint_lbl.setText("")

        # Nudge, don't block: a poor result still lets the user carry on.
        self.brainmap_next_btn.setObjectName(
            "primaryBtn" if key != "brainmap.quality.poor" else "")
        self.brainmap_retrain_btn.setObjectName(
            "primaryBtn" if key == "brainmap.quality.poor" else "")
        for btn in (self.brainmap_next_btn, self.brainmap_retrain_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.log(t("log.brainmap_ready", quality=t(key)))

    def _retrain_from_brainmap(self):
        self._begin_training_sequence("neutral")

    def _start_bci(self):
        self.save_settings()
        from drone_controller import TelloDroneClient

        is_sim = self.simulate_cb.isChecked()
        cid = 'SIM' if is_sim else self.client_id_input.text().strip()
        csec = 'SIM' if is_sim else self.client_secret_input.text().strip()

        self.connect_bci_btn.setEnabled(False)

        self.drone_client = TelloDroneClient(
            cid, csec, tello=None,
            fix_indices=self.config.get("fix_indices", False),
            debug=False, config=self.config,
            bci_status_callback=self.update_bci_status,
            bci_telemetry_callback=self.update_bci_telemetry,
            profiles_callback=self.update_profiles,
            headsets_callback=self.update_headsets,
            training_callback=self.training_signal.emit,
            dev_data_callback=self.dev_data_signal.emit,
            dev_labels_callback=self.dev_labels_signal.emit,
            mc_config_callback=self.mc_config_signal.emit,
            brainmap_callback=self.brainmap_signal.emit,
            profile_admin_callback=self.profile_admin_signal.emit
        )

        self.client_thread = threading.Thread(
            target=lambda: self.drone_client.simulate() if is_sim else self.drone_client.start(
                headset_id="", # User will pick after auth
                profile_name="" # profile is auto-selected in on_query_profile_done
            ), daemon=True
        )
        self.client_thread.start()
        self.telem_timer.start(50)

    def update_bci_status(self, status: str):
        self.bci_status_signal.emit(status)

    def update_profiles(self, profiles: list):
        """Thread-safe: forward profile list to the Qt main thread."""
        self.profiles_signal.emit(profiles)

    def update_headsets(self, headsets: list):
        """Thread-safe: forward headset list to the Qt main thread."""
        self.headsets_signal.emit(headsets)
        
    def update_training(self, event: str):
        self.training_signal.emit(event)

    def update_dev_data(self, signal: int, cq_list: list):
        self.dev_data_signal.emit(signal, cq_list)

    # ──────────────────────────────────────────────
    # Signal Handlers (Main Thread)
    # ──────────────────────────────────────────────
    def _populate_headsets(self, headsets: list):
        """Populate the headset dropdown."""
        # Keep whatever was highlighted, so a rescan does not move the
        # selection out from under someone about to press Connect.
        self.headset_list.clear()
        self.headset_rows = []

        if not headsets:
            self.headset_list.setVisible(False)
            self.headset_empty_lbl.setVisible(True)
            bind(self.headset_empty_lbl, "headset.none_found")
            bind(self.headset_count_lbl, "headset.count", count=0)
            self.log(t("log.no_headsets"))
            return

        for hs in headsets:
            hs_id = hs.get('id', 'Unknown')
            status = hs.get('status', 'Unknown')
            row = self._build_headset_row(hs_id, status)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, hs_id)
            item.setSizeHint(row.sizeHint())
            self.headset_list.addItem(item)
            self.headset_list.setItemWidget(item, row)

        # Height follows the contents up to four rows, then scrolls.
        rows = min(len(headsets), 4)
        row_h = self.headset_list.item(0).sizeHint().height()
        self.headset_list.setFixedHeight(rows * row_h + 14)
        bind(self.headset_count_lbl, "headset.count", count=len(headsets))

        self.headset_empty_lbl.setVisible(False)
        self.headset_list.setVisible(True)
        self.headset_group.setEnabled(True)
        self.log(t("log.headsets_available", count=len(headsets)))
        # Auto-advance to headset selection screen on successful authentication & headset query
        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)

    def _set_headset_rows_busy(self, busy: bool, active_id: str = ""):
        """Lock every row's Connect while one connection is in flight.

        Two headsets cannot be brought up at once, and a second press during
        the handshake would leave the app talking to a device the user is no
        longer expecting.
        """
        for headset_id, button in getattr(self, "headset_rows", []):
            button.setEnabled(not busy)
            bind(button, "headset.connecting_btn"
                 if busy and headset_id == active_id else "headset.connect")

    def _build_headset_row(self, headset_id: str, status: str) -> QWidget:
        """One device: product shot, name and state, and its own Connect.

        Choosing a headset and connecting to it were two steps for no reason —
        nobody selects a device they do not intend to use — so the button lives
        on the row it acts on.
        """
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(14)

        shot = headset_pixmap(headset_id)
        if shot is not None:
            picture = QLabel()
            # Fixed box, and the label is sized to match it. Setting only a
            # width let the row squeeze the label shorter than its pixmap,
            # which QLabel resolves by cropping — the headsets lost their top
            # and bottom edges.
            scaled = shot.scaled(
                PRODUCT_SHOT.width(), PRODUCT_SHOT.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            picture.setPixmap(scaled)
            picture.setFixedSize(PRODUCT_SHOT)
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            picture.setScaledContents(False)
            layout.addWidget(picture)

        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(headset_id)
        name.setStyleSheet("font-size: 14px; font-weight: bold; color: #e6edf3;")
        text.addWidget(name)

        state = QLabel(i18n.headset_status(status))
        connected = str(status).lower() == "connected"
        state.setStyleSheet(
            "font-size: 12px; color: %s;" % ("#3fb950" if connected else "#8b949e"))
        text.addWidget(state)
        layout.addLayout(text)
        layout.addStretch()

        button = bind(QPushButton(), "headset.connect")
        button.setObjectName("blueBtn")
        button.setMinimumWidth(132)
        button.setMinimumHeight(36)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _c=False, hid=headset_id: self._connect_headset(hid))
        layout.addWidget(button)

        self.headset_rows.append((headset_id, button))
        return row

    def _connect_headset(self, headset_id: str = ""):
        """Connect to a headset, named by the row whose button was pressed."""
        if not headset_id:
            self.log(t("log.no_headset_selected"))
            return

        # Switching devices: let go of the old one first. Cortex keeps the
        # previous headset connected otherwise, and the session that follows is
        # still bound to it.
        previous = (self.config.get("device_id") or "").strip()
        switching = bool(previous) and previous != headset_id and self.drone_client

        self._set_headset_rows_busy(True, headset_id)
        self._pills_device(headset_id)

        # Load and apply device-specific config profile
        device_type = headset_id.split('-')[0]
        self.config = ConfigManager.get_device_config(self.config, device_type)
        self.config["device_id"] = headset_id
        
        self._apply_config_to_client()
        
        self.log(t("log.connecting_headset", headset=headset_id))

        if self.drone_client:
            def connect():
                if switching:
                    self.log(t("log.switching_headset", headset=previous))
                    try:
                        self.drone_client.release_headset(rescan=False)
                    except Exception as e:
                        applog.exception("release before switch", e)
                self.drone_client.connect_headset(headset_id)

            threading.Thread(target=connect, daemon=True).start()
        else:
            self.log(t("log.client_not_init"))
            self._set_headset_rows_busy(False)

    # ── Live sensitivity tuning ──────────────────────────────────────────────
    def _build_inline_mc_sliders(self):
        """One slider per trained action, straight from Cortex's own list."""
        for widget, _ in self.inline_mc_sliders:
            widget.deleteLater()
        self.inline_mc_sliders.clear()

        actions = self.mc_active_actions
        values = self.mc_sensitivities
        if not actions or not values:
            self.mc_sens_hint.setVisible(True)
            return

        self.mc_sens_hint.setVisible(False)
        for i, action in enumerate(actions):
            if i >= len(values):
                break
            row = QHBoxLayout()
            # bind, not a bare t(): these labels live on a persistent page, so
            # they have to follow a language switch like everything else.
            name = QLabel()
            key = f"action.{action}"
            if i18n.has(key):
                bind(name, key)
            else:
                name.setText(action)
            name.setStyleSheet("font-size: 12px; color: #c9d1d9;")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 10)
            slider.setValue(int(values[i]))
            slider.setMinimumWidth(110)
            value_lbl = QLabel(str(slider.value()))
            value_lbl.setFixedWidth(18)
            value_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
            slider.valueChanged.connect(lambda v, l=value_lbl: l.setText(str(v)))
            # Cortex writes to the profile on every call, so only push when the
            # user lets go rather than on every pixel of drag.
            slider.sliderReleased.connect(self._push_mc_sensitivity)
            row.addWidget(name); row.addWidget(slider); row.addWidget(value_lbl)

            row.setContentsMargins(0, 0, 0, 0)
            holder = QWidget()
            holder.setLayout(row)
            # A row under the scene rather than a column beside it, so the
            # trained commands read left-to-right like the rest of the strip.
            self.mc_sens_layout.addWidget(holder)
            self.inline_mc_sliders.append((holder, slider))

    def _push_mc_sensitivity(self):
        if not (self.drone_client and self.inline_mc_sliders):
            return
        values = [s.value() for _, s in self.inline_mc_sliders]
        if values == list(self.mc_sensitivities):
            return
        self.mc_sensitivities = values
        self.drone_client.set_mc_sensitivity(values)
        self.log(t("log.mc_sensitivity", values=", ".join(str(v) for v in values)))

    # ── Reset and redo the training ──────────────────────────────────────────
    def _reset_and_retrain(self):
        """Wipe the trained actions and walk the user back through training.

        Offered here because this is where you find out the training is no good
        — the drone twitches, or a command never fires — and the alternative was
        finishing a run you already know is spoiled.
        """
        profile = self.config.get("profile_name", "")
        if not profile or not self.drone_client:
            self.log(t("log.no_profile_to_retrain"))
            return

        dialog = ConfirmDialog(
            t("retrain.title"),
            t("retrain.body", profile=profile),
            t("retrain.confirm"),
            self,
        )
        dialog.exec()
        if not dialog.confirmed:
            return

        self.log(t("log.profile_resetting", profile=profile))
        threading.Thread(
            target=lambda: self.drone_client.reset_profile_training(profile),
            daemon=True).start()
        # Straight to the signal check: retraining on bad contact is what
        # produced the unusable profile in the first place.
        self.stacked_widget.setCurrentIndex(PAGE_EQ)

    def _refresh_headsets(self):
        """Re-scan for headsets. Cortex needs controlDevice/refresh then a
        fresh queryHeadset, and both are blocking sends, so run them off-thread."""
        if not self.drone_client:
            self.log(t("log.client_not_init"))
            return
        self.refresh_headsets_btn.setEnabled(False)
        bind(self.refresh_headsets_btn, "headset.refreshing")
        self.log(t("log.refreshing_headsets"))

        def done():
            self.refresh_headsets_btn.setEnabled(True)
            bind(self.refresh_headsets_btn, "headset.refresh")

        def work():
            try:
                self.drone_client.refresh_headsets()
            finally:
                self.ui_task_signal.emit(done)

        threading.Thread(target=work, daemon=True).start()

    def _populate_profiles(self, profiles: list):
        """Populate the profile dropdown so the user can pick which one to load."""
        self.refresh_profiles_btn.setEnabled(True)
        self.profile_combo.clear()

        if not profiles:
            self.profile_combo._placeholder_key = "profile.none_found"
            self.profile_combo.addItem(t("profile.none_found"))
            self.profile_combo.setEnabled(False)
            self.load_profile_btn.setEnabled(False)
            bind(self.profile_status_lbl, "profile.none_hint")
            self.profile_status_lbl.setStyleSheet(
                "color: #f85149; font-size: 11px; font-style: italic; padding: 0 2px;"
            )
            return

        self.profile_combo._placeholder_key = None
        for p in profiles:
            self.profile_combo.addItem(f"🧠  {p}", userData=p)

        self.profile_combo.setEnabled(True)
        self.load_profile_btn.setEnabled(True)

        # Pre-select the profile from config if it exists in the list
        saved_profile = self.config.get("profile_name", "")
        if saved_profile:
            for i in range(self.profile_combo.count()):
                if self.profile_combo.itemData(i) == saved_profile:
                    self.profile_combo.setCurrentIndex(i)
                    break

        count = len(profiles)
        bind(self.profile_status_lbl, "profile.available", count=count)
        self.profile_status_lbl.setStyleSheet(
            "color: #8b949e; font-size: 11px; font-style: italic; padding: 0 2px;"
        )
        self.log(t("log.profiles_available", count=count))

    def _load_selected_profile(self):
        """Load the profile the user selected in the dropdown."""
        idx = self.profile_combo.currentIndex()
        profile_name = self.profile_combo.itemData(idx)
        if not profile_name:
            self.log(t("log.no_profile_selected"))
            return

        self.load_profile_btn.setEnabled(False)
        bind(self.load_profile_btn, "profile.loading_btn")
        self.config["profile_name"] = profile_name
        self.log(t("log.loading_profile", profile=profile_name))

        if self.drone_client:
            threading.Thread(
                target=self.drone_client.load_profile,
                args=(profile_name,),
                daemon=True
            ).start()
        else:
            self.log(t("log.bci_not_connected"))
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")

    def _refresh_profiles(self):
        """Re-send queryProfile to Cortex (available once authorized)."""
        if self.drone_client and hasattr(self.drone_client, 'c'):
            try:
                self.drone_client.c.query_profile()
                self.log(t("log.refreshing_profiles"))
            except Exception as e:
                self.log(t("log.refresh_failed", detail=e))

    def _do_update_bci_status(self, status: str):
        # The Cortex layer still speaks in finished English sentences; translate
        # them at this boundary so the badge and the log follow the UI language.
        self.log(t("log.bci_status", status=i18n.backend_status(status)))

        if status.startswith("AUTHORIZED:"):
            self._on_authorized()
            return

        if status.startswith("AUTH_FAILED:"):
            self._show_credentials_page(status[len("AUTH_FAILED:"):].strip())
            return

        if status.startswith("CONNECTION_FAILED:"):
            if self._awaiting_approval:
                return
            self._show_connection_problem(status[len("CONNECTION_FAILED:"):])
            return

        if status.startswith("HEADSET_LOST:"):
            self._on_headset_lost(status[len("HEADSET_LOST:"):])
            return

        if status.startswith("HEADSET_NOT_FOUND:"):
            headset = status[len("HEADSET_NOT_FOUND:"):]
            self._set_headset_rows_busy(False)
            self.log(t("log.headset_gone", headset=headset))
            return

        if status.startswith("ACCESS_REJECTED:"):
            # Declined in Launcher. Nothing retries by itself from here, so say
            # so on the page that has the Retry button.
            self._show_connection_problem("", rejected=True)
            return

        if status.startswith("PENDING_ACCESS:"):
            # Approving in EMOTIV Launcher is part of entering credentials for
            # the first time, so it belongs on that screen — the user is
            # standing there having just pressed Connect. Once authorized, a
            # later pending state is a re-approval and the headset page is the
            # right place for it.
            if not self._credentials_saved:
                self._awaiting_approval = True
                self._show_credentials_page(waiting=True)
                return
            if self.stacked_widget.currentIndex() <= PAGE_HEADSET:
                self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
            self._show_access_pending_ui(status[len("PENDING_ACCESS:"):])
            return

        if status.startswith("PROFILE_LOADED:"):
            self.log(t("badge.profile_loaded",
                       profile=i18n.profile_name_from_loaded(
                           status[len("PROFILE_LOADED:"):])))
            self._hide_access_pending_ui()
            self.p0_next_btn.setEnabled(True)
            # Re-enable the Load button so the user can switch profiles
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")
            bind(self.profile_status_lbl, "profile.selected",
                 profile=self.profile_combo.currentText())
            self.profile_status_lbl.setStyleSheet(
                "color: #3fb950; font-size: 11px; font-style: italic; padding: 0 2px;"
            )
            return

        if "Active" in status:
            self._hide_access_pending_ui()
            # Session is active — user can now select and load a profile.
            self.profile_group.setEnabled(True)
            self.profile_combo.setEnabled(True)
            bind(self.profile_status_lbl, "profile.session_active")
            # Auto-advance to profile selection screen only if still on auth/headset screens
            if self.stacked_widget.currentIndex() <= PAGE_HEADSET:
                self.stacked_widget.setCurrentIndex(PAGE_PROFILE)
            # Enable Next for simulation; otherwise wait for profile load.
            is_sim = self.simulate_cb.isChecked()
            if is_sim:
                self.p0_next_btn.setEnabled(True)
        elif "Error" in status or "error" in status.lower() or "finished" in status.lower() or "warning" in status.lower() or "failed" in status.lower():
            # Give the rows back: a connection that failed leaves every Connect
            # button disabled otherwise, with nothing to press.
            self._set_headset_rows_busy(False)
            bind(self.connect_bci_btn, "auth.retry")
            self.connect_bci_btn.setEnabled(True)
            # Re-enable load button in case of profile load error
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")

    # How long to keep trying before giving the headset up as gone.
    RECONNECT_SECONDS = 30

    def _on_headset_lost(self, headset_id: str):
        """The headset dropped mid-session: say so, then try to get it back.

        The session is left alone. Cortex resumes the existing subscriptions
        once the device is back, so the loaded profile and any run in progress
        survive a brief dropout — which is most of them.
        """
        if self.reconnect_timer.isActive():
            return

        self._lost_headset = headset_id or (self.config.get("device_id") or "")
        self._reconnect_deadline = time.monotonic() + self.RECONNECT_SECONDS
        self.log(t("log.headset_lost", headset=self._lost_headset))

        # A run cannot continue while the headset is off, but it is not
        # abandoned yet — the clock stops and waits for the retry to resolve.
        self._run_paused = self.run_timer.isActive()
        if self._run_paused:
            self.run_timer.stop()
        if self.run_countdown_timer.isActive():
            self.run_countdown_timer.stop()

        self.reconnect_banner.show_for(self._lost_headset, self.RECONNECT_SECONDS)
        self.reconnect_timer.start(1000)
        self._try_reconnect()

    def _try_reconnect(self):
        if not self.drone_client:
            return
        threading.Thread(
            target=lambda: self.drone_client.reconnect_headset(self._lost_headset),
            daemon=True).start()

    def _on_reconnect_tick(self):
        remaining = self._reconnect_deadline - time.monotonic()
        if remaining <= 0:
            self._give_up_reconnect()
            return
        self.reconnect_banner.set_remaining(remaining)
        # Retry every other second; each attempt is a queryHeadset round trip.
        if int(remaining) % 2 == 0:
            self._try_reconnect()

    def _on_headset_recovered(self):
        """Called when streams come back while the banner is up."""
        if not self.reconnect_timer.isActive():
            return
        self.reconnect_timer.stop()
        self.reconnect_banner.hide()
        self.log(t("log.headset_recovered", headset=self._lost_headset))
        if self._run_paused:
            # Give the player a beat to get their head back before the clock
            # starts again, rather than resuming mid-sentence.
            self._run_paused = False
            self._run_deadline = time.monotonic() + max(
                1.0, self.drone_sim.time_left)
            self.run_timer.start(100)

    def _give_up_reconnect(self):
        """Out of time: drop the run and go back to the device list."""
        self.reconnect_timer.stop()
        self.reconnect_banner.hide()
        self._run_paused = False
        self.log(t("log.headset_lost_final", headset=self._lost_headset))

        self.run_timer.stop()
        self.run_countdown_timer.stop()
        self.drone_sim.end_run()
        self.start_run_btn.setEnabled(True)
        bind(self.start_run_btn, "game.start")

        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
        self._release_headset()

    def _show_connection_problem(self, detail: str, rejected: bool = False):
        # Folded into the credentials screen: it is the same page now, and the
        # user is either there already or about to be sent there.
        if rejected:
            self._show_credentials_page(t("access.rejected_body"))
            return
        if detail:
            self._conn_fail_detail = detail
        self._show_credentials_page(
            getattr(self, "_conn_fail_detail", "") or t("auth.unreachable"))
        return

    def _retry_connection(self):
        """Start over from scratch after the user has fixed whatever was wrong."""
        self.auth_retry_btn.setEnabled(False)
        bind(self.auth_retry_btn, "auth.retrying")
        self.auth_reason_lbl.setVisible(False)
        self._conn_fail_detail = ""

        if self.drone_client:
            # The old socket is dead or unauthorized; drop it rather than
            # stacking a second client on top of it. close() blocks for about a
            # second, so it does not belong on the UI thread.
            stale, self.drone_client = self.drone_client, None
            # Silence it before closing: its socket outlives this call and
            # would otherwise report the old failure into the new attempt.
            self._quietly(stale.detach_callbacks)
            threading.Thread(
                target=lambda: self._quietly(stale.close), daemon=True).start()

        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
        QTimer.singleShot(400, self._start_bci)

    @staticmethod
    def _quietly(fn):
        """Run a teardown call whose failure should not matter."""
        try:
            fn()
        except Exception as e:
            print(f"[teardown] {e}", flush=True)

    def _show_access_pending_ui(self, message: str):
        """Show a prominent inline banner asking the user to approve via EMOTIV Launcher."""

        # Cortex sends its own English sentence here; swap in the translated one
        # when it is the stock message, otherwise show what Cortex said.
        default_en = i18n.I18N["en"]["access.default_msg"]
        message_key = "access.default_msg" if message.strip() == default_en else None

        # Build or reuse the banner widget
        if not hasattr(self, '_access_banner') or self._access_banner is None:
            from PyQt6.QtWidgets import QFrame
            banner = QFrame()
            banner.setStyleSheet(
                "QFrame { background-color: #1f1300; border: 1px solid #e3a01a; "
                "border-radius: 8px; padding: 6px; }"
            )
            b_layout = QVBoxLayout(banner)
            b_layout.setSpacing(8)

            icon_row = QHBoxLayout()
            warn_icon = QLabel("⚠️")
            warn_icon.setStyleSheet("font-size: 22px; background: transparent; border: none;")
            warn_title = bind(QLabel(), "access.title")
            warn_title.setStyleSheet(
                "font-weight: bold; font-size: 14px; color: #e3a01a; "
                "background: transparent; border: none;"
            )
            icon_row.addWidget(warn_icon)
            icon_row.addWidget(warn_title)
            icon_row.addStretch()
            b_layout.addLayout(icon_row)

            self._access_msg_lbl = QLabel(message)
            if message_key:
                bind(self._access_msg_lbl, message_key)
            self._access_msg_lbl.setWordWrap(True)
            self._access_msg_lbl.setStyleSheet(
                "color: #c9d1d9; font-size: 13px; background: transparent; border: none;"
            )
            b_layout.addWidget(self._access_msg_lbl)

            instructions = bind(QLabel(), "access.steps")
            instructions.setWordWrap(True)
            instructions.setStyleSheet(
                "color: #8b949e; font-size: 12px; background: transparent; border: none; "
                "line-height: 1.6;"
            )
            b_layout.addWidget(instructions)

            retry_btn = bind(QPushButton(), "access.retry")
            retry_btn.setObjectName("blueBtn")
            retry_btn.clicked.connect(self._retry_access_request)
            b_layout.addWidget(retry_btn)

            self._access_banner = banner
            # and where auto-connect leaves the user. This used to target the
            # auth page while anchoring on a widget that is not on it, so
            # indexOf() returned -1 and the banner landed on a page nobody sees.
            layout = getattr(self, "headset_page_layout", None)
            if layout is not None:
                layout.insertWidget(layout.indexOf(self.headset_group) + 1, banner)
        else:
            if message_key:
                bind(self._access_msg_lbl, message_key)
            else:
                i18n.unbind(self._access_msg_lbl)
                self._access_msg_lbl.setText(message)
            self._access_banner.setVisible(True)

    def _hide_access_pending_ui(self):
        if hasattr(self, '_access_banner') and self._access_banner is not None:
            self._access_banner.setVisible(False)

    def _retry_access_request(self):
        """Re-send requestAccess so Cortex re-checks or EMOTIV Launcher re-prompts."""
        if self.drone_client and hasattr(self.drone_client, 'c'):
            self.log(t("log.retry_access"))
            try:
                self.drone_client.c.request_access()
            except Exception as e:
                self.log(t("log.retry_failed", detail=e))

    def _create_and_train_profile(self):
        new_name = self.new_profile_input.text().strip()
        if not new_name:
            self.log(t("log.enter_profile_name"))
            return
            
        # This name is the player's identity from here on: the profile, the
        # leaderboard row, and what the handoff prompt offers to clean up.
        self.config["profile_name"] = new_name
        ConfigManager.save_config(self.config)
        self.current_training_action = "neutral"
        self.stacked_widget.setCurrentIndex(PAGE_EQ)
        self.drone_client.create_and_train_profile(new_name)
        
    def _on_training_accept(self, action: str):
        if action == "neutral":
            self.neutral_accept_btn.hide()
            self.neutral_reject_btn.hide()
            bind(self.neutral_status_lbl, "train.accepting")
        else:
            self.push_accept_btn.hide()
            self.push_reject_btn.hide()
            bind(self.push_status_lbl, "train.accepting")
        self.drone_client.accept_training(action)
        
    def _on_training_reject(self, action: str):
        """Discard the take and immediately record another one.

        'reject' only tells Cortex to throw the sample away — it does not start
        a new round. Nothing here restarted it either, so the screen sat on
        "Retrying training..." forever. The restart is driven locally rather
        than off the MC_Rejected event, so a reject that Cortex never
        acknowledges (rejecting after a failed take, for instance) cannot wedge
        the screen again.
        """
        if action == "neutral":
            self.neutral_accept_btn.hide()
            self.neutral_reject_btn.hide()
            bind(self.neutral_status_lbl, "train.retrying")
        else:
            self.push_accept_btn.hide()
            self.push_reject_btn.hide()
            bind(self.push_status_lbl, "train.retrying")
        if self.push_anim_timer.isActive():
            self.push_anim_timer.stop()

        self.drone_client.reject_training(action)
        # Let the reject land before asking for a new take. The 3-second
        # countdown inside _begin_training_sequence adds more slack on top.
        QTimer.singleShot(700, lambda: self._begin_training_sequence(action))
        
    def _on_training_update(self, event: str):
        idx = self.stacked_widget.currentIndex()
        if idx not in (PAGE_TRAIN_NEUTRAL, PAGE_TRAIN_PUSH):
            return
            
        action = getattr(self, "current_training_action", "neutral")
        
        lbl = self.neutral_status_lbl if action == "neutral" else self.push_status_lbl
        btn_acc = self.neutral_accept_btn if action == "neutral" else self.push_accept_btn
        btn_rej = self.neutral_reject_btn if action == "neutral" else self.push_reject_btn
        
        if event.startswith("PROFILE_LOADED:"):
            self.stacked_widget.setCurrentIndex(PAGE_EQ)
            return

        event_lower = event.lower()
        if "rejected" in event_lower or "erased" in event_lower:
            # Acknowledged only. _on_training_reject already queued the retake;
            # restarting here as well would run two countdowns at once.
            self.log(t("log.training_rejected", action=(
                t(f"action.{action}") if i18n.has(f"action.{action}") else action)))
        elif "started" in event_lower:
            pass # Handled by local recording timer
        elif "succeeded" in event_lower:
            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
            bind(lbl, "train.succeeded")
            btn_acc.show()
            btn_rej.show()
            bind(btn_rej, "train.reject")
        elif "failed" in event_lower:
            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
            bind(lbl, "train.failed")
            btn_acc.hide()
            btn_rej.show()
            bind(btn_rej, "train.retry")
        elif "completed" in event_lower:
            if hasattr(self, "recording_timer") and self.recording_timer.isActive():
                self.recording_timer.stop()
            if action == "neutral":
                self._begin_training_sequence("push")
            else:
                self.push_anim_timer.stop()
                bind(lbl, "train.complete")
                self.drone_client.save_profile()
                # Straight to the result instead of a dead-end "done" message —
                # the brain map is what tells the user whether to redo this.
                self.stacked_widget.setCurrentIndex(PAGE_BRAINMAP)
                QTimer.singleShot(900, self._request_brain_map)

    # Cortex ends the contact-quality columns with a summary channel rather
    # than an electrode. It already has its own readout at the top of the
    # screen, and it has no place on a scalp map.
    NON_ELECTRODE_CHANNELS = {"OVERALL", "BATTERY"}

    def _on_dev_labels(self, labels: list):
        """Electrode names for this headset, e.g. ['AF3','T7','Pz','T8','AF4']."""
        keep = [i for i, name in enumerate(labels)
                if str(name).upper() not in self.NON_ELECTRODE_CHANNELS]
        self._dev_keep_idx = keep
        # OVERALL is not an electrode and not a 0-4 grade — it is the headset's
        # own contact-quality percentage. Remember where it sits so the summary
        # can come from the sensors rather than from wireless signal strength.
        self._dev_overall_idx = next(
            (i for i, name in enumerate(labels) if str(name).upper() == "OVERALL"),
            None)
        self.dev_sensor_labels = [str(labels[i]) for i in keep]
        clear_grid(self.eq_sensor_layout)
        self.eq_sensor_labels = {}
        self.log(t("log.sensor_labels", labels=", ".join(self.dev_sensor_labels)))

    def _on_dev_data_update(self, signal: int, cq_list: list):
        """Per-sensor contact quality: the EQ screen and the in-flight pill."""
        if self.reconnect_timer.isActive():
            self._on_headset_recovered()
        overall_now = contact_percent(cq_list,
                                      getattr(self, "_dev_overall_idx", None),
                                      getattr(self, "_dev_keep_idx", None))
        self._pills_quality(overall_now, cq_list,
                            getattr(self, "dev_sensor_labels", []),
                            getattr(self, "_dev_keep_idx", None))

        # Everything below draws the EQ screen, which is not always on top.
        if self.stacked_widget.currentIndex() != PAGE_EQ:
            return

        # The summary comes from the electrodes, not from `signal`. `signal` is
        # the wireless link between headset and dongle — a different
        # measurement that a simulated headset pins at 1, which is why this
        # read "Very Bad" with every sensor green.
        overall = contact_percent(cq_list, getattr(self, "_dev_overall_idx", None),
                                  getattr(self, "_dev_keep_idx", None))
        grade, colour = contact_grade(overall)
        bind(self.eq_overall_lbl, "eq.overall", quality=t(grade),
             value="—" if overall is None else int(round(overall)))
        self.eq_overall_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {colour};"
            f"padding: 10px; background-color: #161b22; border: 1px solid {colour}; border-radius: 8px;"
        )
        # Per-sensor contact quality
        # CQ values: 0=No Signal, 1=Bad, 2=Poor, 3=Fair, 4=Good
        cq_colors = {0: "#da3633", 1: "#da3633", 2: "#e3a01a", 3: "#58a6ff", 4: "#3fb950"}
        cq_keys = {0: "quality.none", 1: "quality.bad", 2: "quality.poor",
                   3: "quality.fair", 4: "quality.good"}

        labels = getattr(self, "dev_sensor_labels", []) or []
        keep = getattr(self, "_dev_keep_idx", None)
        if keep is not None:
            cq_list = [cq_list[i] for i in keep if i < len(cq_list)]
        self.sensor_map.set_sensors(labels, cq_list)

        for i, cq_val in enumerate(cq_list):
            # Real electrode names when Cortex has sent them; S0..Sn only as a
            # fallback for a headset that reports quality without labels.
            sensor_name = labels[i] if i < len(labels) else f"S{i}"
            cq_val_int = int(cq_val) if isinstance(cq_val, (int, float)) else 0
            color = cq_colors.get(cq_val_int, "#8b949e")
            cq_key = cq_keys.get(cq_val_int, "quality.short_unknown")

            if sensor_name not in self.eq_sensor_labels:
                name_lbl = QLabel(sensor_name)
                name_lbl.setToolTip(sensor_name)
                name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #e6edf3;")
                name_lbl.setFixedWidth(40)

                bar = QProgressBar()
                bar.setRange(0, 4)
                bar.setFixedHeight(20)
                bar.setTextVisible(False)

                status_lbl = bind(QLabel(), cq_key)
                status_lbl.setFixedWidth(80)

                row = len(self.eq_sensor_labels)
                self.eq_sensor_layout.addWidget(name_lbl, row, 0)
                self.eq_sensor_layout.addWidget(bar, row, 1)
                self.eq_sensor_layout.addWidget(status_lbl, row, 2)
                self.eq_sensor_labels[sensor_name] = (name_lbl, bar, status_lbl)

            _, bar, status_lbl = self.eq_sensor_labels[sensor_name]
            bar.setValue(cq_val_int)
            bar.setStyleSheet(
                f"QProgressBar {{ background-color: #21262d; border: 1px solid #30363d; border-radius: 4px; }}"
                f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
            )
            bind(status_lbl, cq_key)
            status_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")

        # Contact quality alone decides this. Wireless signal strength used to
        # be part of it, which produced a warning about moving closer to the
        # USB receiver on a screen that is about electrodes.
        good_enough = overall is not None and overall >= 50

        bind(self.eq_status_lbl, "eq.ok" if good_enough else "eq.bad")
        self.eq_status_lbl.setStyleSheet(
            "font-size: 14px; color: %s; margin-top: 10px;"
            % ("#3fb950" if good_enough else "#e3a01a"))
        self.eq_next_btn.setEnabled(good_enough)

    def _on_mc_config_update(self, data: dict):
        # The settings dialog and the inline panel both want this; keep a copy
        # on the app so the panel survives the dialog being closed.
        kind = data.get('type')
        if kind == 'active_actions':
            self.mc_active_actions = data.get('data') or []
            self._build_inline_mc_sliders()
        elif kind == 'action_sensitivity':
            self.mc_sensitivities = data.get('data') or []
            self._build_inline_mc_sliders()

        if hasattr(self, 'settings_dialog_ref') and self.settings_dialog_ref:
            self.settings_dialog_ref.handle_mc_config(data)

    def update_bci_telemetry(self, battery: int, signal: int):
        self.bci_telemetry_signal.emit(battery, signal)

    def _do_update_bci_telemetry(self, battery: int, signal: int):
        bind(self.bci_telem_lbl, "dash.headset", battery=battery, signal=signal)
        # Cortex sends 0 before the headset has reported a real reading.
        self._pills_battery(battery if battery else None)

    def reset_headset(self):
        if self.drone_client:
            self.drone_client.reset_center()
            self.log(t("log.recenter"))

    def toggle_fullscreen(self):
        if self.drone_sim.isFullScreen():
            self.drone_sim.setWindowFlags(Qt.WindowType.Widget)
            self.drone_sim.showNormal()
            self.state_layout.addWidget(self.drone_sim)
        else:
            self.drone_sim.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
            self.drone_sim.showFullScreen()
            self.drone_sim.setFocus()

    def check_drone_connection(self):
        self.connect_drone_btn.setEnabled(False)
        bind(self.drone_conn_status_lbl, "drone.connecting")

        is_sim = self.simulate_cb.isChecked()
        if is_sim:
            self.drone_connected_signal.emit(True, t("drone.sim_skip"))
            return

        def _connect():
            try:
                from djitellopy import Tello
                tello = Tello()
                tello.connect()
                batt = tello.get_battery()
                self.tello = tello
                self.drone_connected_signal.emit(True, t("drone.connected", battery=batt))
            except Exception as e:
                self.tello = None
                self.drone_connected_signal.emit(False, t("drone.failed", detail=e))

        threading.Thread(target=_connect, daemon=True).start()

    def _on_drone_connection_result(self, success, message):
        self.connect_drone_btn.setEnabled(True)
        # `message` is already-translated text, not a key.
        i18n.unbind(self.drone_conn_status_lbl)
        self.drone_conn_status_lbl.setText(message)
        
        if success:
            self.p2_next_btn.setEnabled(True)
            self.drone_conn_status_lbl.setStyleSheet("color: #3fb950; font-weight: bold;")
            if self.drone_client:
                self.drone_client.drone.tello = self.tello

    def go_to_dashboard(self):
        self.stacked_widget.setCurrentIndex(PAGE_DASHBOARD)
        is_sim = self.simulate_cb.isChecked()
        bind(self.dash_drone_lbl, "dash.drone_sim" if is_sim else "dash.drone_connected")
        self.video_thread = VideoThread(tello=self.tello)
        self.video_thread.frame_ready.connect(self.update_camera)
        self.video_thread.status_update.connect(self.log)
        self.video_thread.start()

    def _head_heading(self):
        """Where the head is pointing, in degrees, or None if it cannot say.

        Returns None rather than 0 before calibration finishes: 0 is a real
        heading meaning "dead ahead", and snapping there while the centre is
        still being measured would twitch the drone straight.
        """
        client = self.drone_client
        if not client or not client.program:
            return None
        qp = client.program.quaternion_processor
        if not qp.is_calibrated:
            return None
        return qp.head_heading_deg

    def update_telemetry(self):
        if self.drone_client and self.stacked_widget.currentIndex() in (PAGE_TEST, PAGE_DASHBOARD):
            if self.drone_client and self.drone_client.drone:
                lr, fb, ud, yaw = self.drone_client.drone.get_rc_values()
                self.rc_lbl.setText(f"RC: lr={lr:+4d}  fb={fb:+4d}  ud={ud:+4d}  yaw={yaw:+4d}")
                if self.stacked_widget.currentIndex() == PAGE_TEST:
                    self.drone_sim.update_rc(lr, fb, ud, yaw,
                                             heading=self._head_heading())
                
                # Update MC Dashboard Indicator
                action = getattr(self.drone_client.drone, 'last_executed_action', None)
                action_time = getattr(self.drone_client.drone, 'last_action_time', 0.0)
                now = time.time()
                if action and (now - action_time) < 2.0:
                    bind(self.dash_mc_lbl, "dash.mc", action=drone_action(action))
                    self.dash_mc_lbl.setStyleSheet(
                        "background-color: #1f6feb; border: 1px solid #58a6ff; border-radius: 6px;"
                        "padding: 8px 12px; color: #ffffff; font-size: 14px; font-weight: bold;"
                    )
                else:
                    bind(self.dash_mc_lbl, "dash.mc_none")
                    self.dash_mc_lbl.setStyleSheet(
                        "background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
                        "padding: 8px 12px; color: #8b949e; font-size: 14px; font-weight: bold;"
                    )

            # The raw MOT/COM dump moved out with the side column. Both streams
            # are still printed to the log pane, which is where they were
            # actually read from when debugging.

        # Update Drone Dashboard Stats
        if self.tello and self.stacked_widget.currentIndex() == PAGE_DASHBOARD:
            try:
                bind(self.battery_lbl, "dash.battery", value=self.tello.get_battery())
                bind(self.height_lbl, "dash.height", value=self.tello.get_height())
                bind(self.temp_lbl, "dash.temp", value=self.tello.get_temperature())
            except Exception:
                pass

    def _disconnect_and_quit(self):
        """Clean up connection and return to setup page."""
        self.log(t("log.disconnecting"))
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait(1000)
            self.video_thread = None
        
        if self.drone_client:
            if getattr(self.drone_client, 'drone', None):
                self.drone_client.drone.stop_movement()
                self.drone_client.drone.is_flying = False
            self.drone_client.running = False
            if hasattr(self.drone_client, 'c'):
                try: self.drone_client.c.close()
                except: pass
            
        if self.tello:
            threading.Thread(target=self._safe_land_and_end, daemon=True).start()

        # The headset list, not the credentials screen: disconnecting a drone
        # says nothing about whether the Cortex credentials are still good.
        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
        self.log(t("log.disconnected"))

    def _safe_land_and_end(self):
        try:
            self.tello.land()
        except:
            pass
        try:
            self.tello.end()
        except:
            pass
        self.tello = None

    def update_camera(self, img: QImage):
        scaled = img.scaled(self.camera_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.camera_label.setPixmap(QPixmap.fromImage(scaled))
        
        if hasattr(self, 'hud_widget') and self.hud_widget is not None:
            self.hud_widget.update_frame(img)

    def open_fullscreen_hud(self):
        if not hasattr(self, 'hud_widget') or self.hud_widget is None:
            self.hud_widget = FullscreenHUDWidget(main_app=self)
            # Setup an update timer for the HUD telemetry elements
            self.hud_timer = QTimer(self)
            self.hud_timer.timeout.connect(self.hud_widget.update)
            self.hud_timer.start(50)  # 20 FPS refresh for the HUD overlays

        self.hud_widget.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.hud_widget.showFullScreen()
        self.hud_widget.setFocus()
        self.log(t("log.hud_opened"))

    def close_fullscreen_hud(self):
        if hasattr(self, 'hud_widget') and self.hud_widget is not None:
            self.hud_timer.stop()
            self.hud_widget.close()
            self.hud_widget = None
        self.log(t("log.hud_closed"))

    # ─── Flight actions ───
    def takeoff(self):
        if self.tello:
            threading.Thread(target=self._safe_takeoff, daemon=True).start()
        elif self.drone_client:
            self.drone_client.drone.is_flying = True
            self.drone_client.drone.start_rc_loop()
            self.log(t("log.sim_takeoff"))

    def _safe_takeoff(self):
        try:
            self.tello.takeoff()
            # Default takeoff height is ~1.2m. The user wants ~1.6m.
            self.tello.move_up(40)
            if self.drone_client:
                self.drone_client.drone.is_flying = True
                self.drone_client.drone.start_rc_loop()
            self.log_signal.emit(t("log.airborne"))
        except Exception as e:
            self.log_signal.emit(t("log.takeoff_failed", detail=e))

    def land(self):
        if self.drone_client:
            self.drone_client.drone.stop_movement()
            self.drone_client.drone.is_flying = False
        if self.tello:
            threading.Thread(target=lambda: self._safe_cmd(self.tello.land, t("log.landed")), daemon=True).start()
        else:
            self.log(t("log.sim_landing"))

    def emergency_stop(self):
        if self.drone_client:
            self.drone_client.drone.stop_movement()
            self.drone_client.drone.is_flying = False
        if self.tello:
            threading.Thread(target=lambda: self._safe_cmd(self.tello.emergency, t("log.motors_stopped")), daemon=True).start()
        else:
            self.log(t("log.sim_emergency"))

    def _safe_cmd(self, func, ok_msg):
        try:
            func()
            self.log_signal.emit(ok_msg)
        except Exception as e:
            self.log_signal.emit(t("log.error", detail=e))

    def load_settings(self):
        c = self.config
        cid = (c.get("client_id") or "").strip()
        secret = (c.get("client_secret") or "").strip()
        self.client_id_input.setText(
            "" if cid in self.PLACEHOLDER_CREDENTIALS else cid)
        self.client_secret_input.setText(
            "" if secret in self.PLACEHOLDER_CREDENTIALS else secret)
        self.simulate_cb.setChecked(c.get("simulate", False))
        self.auto_connect_cb.setChecked(c.get("auto_connect", True))
        # Profile combo is populated dynamically; just remember the saved name
        # so _populate_profiles can re-select it once the list arrives.

    def save_settings(self):
        # Deliberately not the credentials. _start_bci calls this before it has
        # any idea whether they work, so writing them here persisted a bad pair
        # — and the next launch would then skip the credentials screen and fail
        # with nowhere to correct it. _on_authorized saves them once Cortex and
        # EMOTIV Launcher have both accepted.
        self.config["language"] = i18n.get_lang()
        # profile_name is set automatically by _populate_profiles when profiles arrive
        self.config["simulate"] = self.simulate_cb.isChecked()
        self.config["auto_connect"] = self.auto_connect_cb.isChecked()
        ConfigManager.save_config(self.config)

    def _apply_config_to_client(self):
        if self.drone_client and self.drone_client.program:
            qp = self.drone_client.program.quaternion_processor
            qp.invert_yaw = self.config.get("invert_yaw", False)
            qp.invert_pitch = self.config.get("invert_pitch", False)
            qp.sens_left = self.config.get("sens_left", 70.0)
            qp.sens_right = self.config.get("sens_right", 70.0)
            qp.sens_fwd = self.config.get("sens_fwd", 50.0)
            qp.sens_back = self.config.get("sens_back", 50.0)
            qp.movement_deadzone = self.config.get("deadzone", 0.02)
            qp.head_gain = float(self.config.get("head_gain", 3.0))
            qp.head_deadzone_deg = float(self.config.get("head_deadzone_deg", 2.0))
            qp.head_expo = float(self.config.get("head_expo", 0.6))
            qp.drift_correction = bool(
                self.config.get("head_drift_correction", True))
            sw = self.config.get("smoothing_window", 4)
            qp.SmoothingWindow = sw
            qp._movement_buffer = __import__('collections').deque(maxlen=sw)
            
            # Update mental mappings
            mappings = self.config.get("mental_mappings", [])
            self.drone_client.program.mental_processor.mappings = mappings
            if hasattr(self.drone_client, 'drone'):
                mental_move_actions = {
                    m.get("action") for m in mappings
                    if m.get("action", "").startswith("Move")
                }
                self.drone_client.drone.set_mental_move_actions(mental_move_actions)

    def show_settings(self):
        dialog = SettingsDialog(self.config, self)
        self.settings_dialog_ref = dialog
        if dialog.exec():
            new_config = dialog.get_config()
            self.config.update(new_config)
            
            # Save the new configuration
            device_id = self.config.get("device_id", "")
            if device_id:
                device_type = device_id.split('-')[0]
                ConfigManager.update_device_profile(self.config, device_type, new_config)
            else:
                ConfigManager.save_config(self.config)
                
            # Apply to active client if running
            self._apply_config_to_client()

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        formatted = f"[{ts}] {msg.strip()}"
        applog.write(msg)
        
        # Append to both terminals
        if hasattr(self, 'bci_log_terminal'):
            self.bci_log_terminal.appendPlainText(formatted)
            # scroll to bottom
            bar = self.bci_log_terminal.verticalScrollBar()
            bar.setValue(bar.maximum())

        if hasattr(self, 'terminal'):
            self.terminal.appendPlainText(formatted)
            bar = self.terminal.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _append_log(self, msg: str):
        self.log(msg)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        banner = getattr(self, "reconnect_banner", None)
        if banner is not None and banner.isVisible():
            banner.setGeometry(self.rect())

    def closeEvent(self, event):
        applog.write("window closed, shutting down")

        # Pressing Finish deletes the player's profile; closing the window did
        # not, so every session that ended by clicking the X left a trained
        # profile behind on the Cortex account. Same setupProfile/delete call,
        # just on the way out.
        profile = (self.config.get("profile_name") or "").strip()
        if profile and self.drone_client:
            applog.write(f"deleting profile '{profile}' on exit")
            try:
                self.drone_client.delete_profile(profile)
                # delete_profile only queues the sends; give the socket a
                # moment to flush them before the process goes away.
                time.sleep(0.8)
            except Exception as e:
                applog.exception("profile delete on exit", e)
            self.config["profile_name"] = ""
            ConfigManager.save_config(self.config)

        sys.stdout = self.original_stdout
        if self.drone_client:
            self.drone_client.running = False
            self.drone_client.drone.cleanup()
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait(2000)
        if self.tello:
            try: self.tello.end()
            except: pass
        event.accept()

class FullscreenResultDialog(QDialog):
    """Run result, shown over the fullscreen simulator.

    In fullscreen the simulator is its own frameless window, so navigating the
    stacked widget underneath just hid the result behind it — the player was
    left staring at a frozen scene with no way forward. This covers the same
    screen instead, and carries the leaderboard inline so checking it does not
    force anyone out of fullscreen either.
    """

    def __init__(self, entry, rank, total, entries, parent=None):
        super().__init__(parent)
        self.choice = "exit"          # what Esc / closing means
        self._celebrate = False
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setStyleSheet("QDialog { background-color: rgba(2, 5, 10, 242); }")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_result(entry, rank, total, entries))
        self.stack.addWidget(self._build_board(entry, entries))
        outer.addWidget(self.stack)

        # Built after the pages, since _build_result decides whether this run
        # earned a celebration. Started from showEvent so the dialog already has
        # its final fullscreen size when the pieces are laid out.
        self.confetti = ConfettiOverlay(self)

    def showEvent(self, event):
        super().showEvent(event)
        if self._celebrate:
            QTimer.singleShot(0, self.confetti.start)

    # ── Result ───────────────────────────────────────────────────────────────
    def _build_result(self, entry, rank, total, entries):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(10)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(t("game.over_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: bold; color: #e6edf3;")
        box.addWidget(title)

        score = QLabel(str(entry.get("score", 0)))
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score.setStyleSheet("font-size: 96px; font-weight: bold; color: #f1c40f;")
        box.addWidget(score)

        detail = QLabel(t("game.final_detail", name=entry.get("name", ""),
                          coins=entry.get("coins", 0), seconds=RUN_SECONDS))
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setStyleSheet("font-size: 15px; color: #8b949e;")
        box.addWidget(detail)

        clock = QLabel(t("game.finished_at",
                         time=time.strftime("%H:%M:%S",
                                            time.localtime(entry.get("time", time.time())))))
        clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clock.setStyleSheet("font-size: 13px; color: #6e7681;")
        box.addWidget(clock)

        message, colour, self._celebrate = congratulation(rank, total)
        if not message:
            rank_lbl = QLabel(t("game.rank", rank=rank, total=total))
            rank_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_lbl.setStyleSheet(
                "font-size: 22px; font-weight: bold; color: #58a6ff; padding: 6px;")
            box.addWidget(rank_lbl)
        if message:
            congrats = QLabel(message)
            congrats.setAlignment(Qt.AlignmentFlag.AlignCenter)
            congrats.setWordWrap(True)
            congrats.setStyleSheet(
                f"font-size: 26px; font-weight: bold; color: {colour}; padding: 2px;")
            box.addWidget(congrats)

            mind = QLabel(t("game.mind_message"))
            mind.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mind.setWordWrap(True)
            mind.setStyleSheet("font-size: 16px; color: #bc8cff; padding-bottom: 4px;")
            box.addWidget(mind)

        podium = QWidget()
        podium.setFixedWidth(430)
        grid = QGridLayout(podium)
        grid.setSpacing(4)
        for i, e in enumerate(entries[:3]):
            add_board_row(grid, i, i + 1, e, e is entry)
        # Finished outside the podium: pin their own line under it, or the
        # screen shows three strangers and nothing about the run just played.
        if rank > 3:
            gap = QLabel("⋯")
            gap.setStyleSheet("color: #6e7681; padding: 2px 8px;")
            grid.addWidget(gap, 3, 0)
            add_board_row(grid, 4, rank, entry, True)
        box.addWidget(podium, alignment=Qt.AlignmentFlag.AlignCenter)

        row = QHBoxLayout()
        again = QPushButton(t("game.try_again"))
        again.setObjectName("primaryBtn")
        again.setMinimumWidth(180)
        again.clicked.connect(lambda: self._pick("again"))

        board = QPushButton(t("game.show_leaderboard"))
        board.setMinimumWidth(180)
        board.clicked.connect(lambda: self.stack.setCurrentIndex(1))

        finish = QPushButton(t("game.finish"))
        finish.setMinimumWidth(180)
        finish.clicked.connect(lambda: self._pick("finish"))

        row.addStretch(); row.addWidget(again); row.addWidget(board)
        row.addWidget(finish); row.addStretch()
        box.addLayout(row)

        hint = QLabel(t("game.fullscreen_hint"))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 11px; color: #6e7681; padding-top: 6px;")
        box.addWidget(hint)
        return page

    # ── Leaderboard ──────────────────────────────────────────────────────────
    def _build_board(self, entry, entries):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(10)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(t("game.leaderboard_title"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #e6edf3;")
        box.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedSize(500, 420)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #30363d; border-radius: 10px;"
            " background-color: #0b0f15; }")
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setSpacing(4)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        for i, e in enumerate(entries[:30]):
            add_board_row(grid, i, i + 1, e, e is entry)
        scroll.setWidget(holder)
        box.addWidget(scroll, alignment=Qt.AlignmentFlag.AlignCenter)

        back = QPushButton(t("game.back"))
        back.setMinimumWidth(180)
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        box.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)
        return page

    def _pick(self, choice: str):
        self.choice = choice
        self.accept()


class ConfirmDialog(QDialog):
    """Yes/no for a destructive step. Cancel is the default; confirm is red."""

    def __init__(self, title: str, body: str, confirm_label: str, parent=None):
        super().__init__(parent)
        self.confirmed = False
        self.setWindowTitle(title)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 16px; font-weight: bold; color: #e6edf3;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        message = QLabel(body)
        message.setWordWrap(True)
        message.setStyleSheet("font-size: 13px; color: #8b949e;")
        layout.addWidget(message)

        row = QHBoxLayout()
        cancel = QPushButton(t("common.cancel"))
        cancel.clicked.connect(self.reject)
        confirm = QPushButton(confirm_label)
        confirm.setObjectName("dangerBtn")
        confirm.clicked.connect(self._confirm)
        row.addStretch(); row.addWidget(cancel); row.addWidget(confirm)
        layout.addLayout(row)

    def _confirm(self):
        self.confirmed = True
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(400)
        self.config = config.copy()

        layout = QVBoxLayout(self)

        # Motion Settings. The dialog is modal and rebuilt on every open, so its
        # strings are resolved once here instead of going through bind().
        motion_group = QGroupBox(t("settings.motion"))
        motion_layout = QVBoxLayout()
        def add_slider(name, min_v, max_v, step, fmt_func, default_v, tooltip=""):
            row = QHBoxLayout()
            lbl = QLabel(f"{name} ⓘ" if tooltip else name)
            lbl.setFixedWidth(110)
            if tooltip:
                lbl.setToolTip(tooltip)
                lbl.setStyleSheet("QToolTip { font-size: 13px; color: #ffffff; background-color: #2b2b2b; border: 1px solid #58a6ff; padding: 4px; }")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setSingleStep(step)
            slider.setValue(int(default_v))
            val_lbl = QLabel(fmt_func(default_v)); val_lbl.setFixedWidth(45)
            slider.valueChanged.connect(lambda v: val_lbl.setText(fmt_func(v)))
            row.addWidget(lbl); row.addWidget(slider); row.addWidget(val_lbl)
            slider.valueChanged.connect(self._live_update)
            motion_layout.addLayout(row)
            return slider

        self.invert_yaw_cb = QCheckBox(t("settings.invert_yaw"))
        self.invert_yaw_cb.setChecked(self.config.get("invert_yaw", False))
        self.invert_yaw_cb.stateChanged.connect(self._live_update)
        motion_layout.addWidget(self.invert_yaw_cb)

        self.sens_left_slider = add_slider(t("settings.sens_left"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_left", 70.0), t("settings.sens_left.tip"))
        self.sens_right_slider = add_slider(t("settings.sens_right"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_right", 70.0), t("settings.sens_right.tip"))
        self.sens_fwd_slider = add_slider(t("settings.sens_fwd"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_fwd", 50.0), t("settings.sens_fwd.tip"))
        self.sens_back_slider = add_slider(t("settings.sens_back"), 1, 300, 1, lambda x: f"{x:.0f}",
            self.config.get("sens_back", 50.0), t("settings.sens_back.tip"))

        self.dead_slider = add_slider(t("settings.deadzone"), 0, 500, 1, lambda x: f"{x/1000:.3f}",
            self.config.get("deadzone", 0.03) * 1000, t("settings.deadzone.tip"))
        self.smooth_slider = add_slider(t("settings.smoothing"), 1, 20, 1, str,
            self.config.get("smoothing_window", 6), t("settings.smoothing.tip"))
        self.speed_slider = add_slider(t("settings.max_speed"), 10, 100, 5, str,
            self.config.get("max_speed", 60), t("settings.max_speed.tip"))
        motion_group.setLayout(motion_layout)
        layout.addWidget(motion_group)

        # Emotiv API Settings
        emotiv_group = QGroupBox(t("settings.emotiv"))
        self.emotiv_layout = QVBoxLayout()
        self.emotiv_status_lbl = QLabel(t("settings.loading"))
        self.emotiv_status_lbl.setStyleSheet("color: #8b949e;")
        self.emotiv_layout.addWidget(self.emotiv_status_lbl)
        emotiv_group.setLayout(self.emotiv_layout)
        layout.addWidget(emotiv_group)
        
        self.mc_active_actions = []
        self.mc_sensitivities = []
        self.mc_sensitivity_sliders = []
        
        app = self.parent()
        if app and hasattr(app, 'drone_client') and app.drone_client:
            app.drone_client.get_mc_config()
        else:
            self.emotiv_status_lbl.setText(t("settings.not_connected"))

        # Mental Commands. The Cortex command names and drone action names are
        # protocol values, so they stay verbatim — only "None" is translated,
        # and the real value always travels in the item's userData.
        mental_group = QGroupBox(t("settings.mental"))
        self.mental_layout = QVBoxLayout()
        self.mapping_rows = []
        CMDS = ["None", "push", "pull", "lift", "drop", "click"]
        ACTIONS = [
            "None",
            "TakeOff", "Land", "EmergencyStop",
            "MoveForward", "MoveBack", "MoveLeft", "MoveRight", "MoveUp", "MoveDown",
            "FlipForward", "FlipBack", "FlipLeft", "FlipRight",
        ]

        def fill(combo, values):
            for value in values:
                combo.addItem(t("settings.none") if value == "None" else value, userData=value)

        mappings = self.config.get("mental_mappings", [])
        for i in range(4):
            row = QHBoxLayout()
            cmd_combo = QComboBox(); fill(cmd_combo, CMDS)
            action_combo = QComboBox(); fill(action_combo, ACTIONS)

            if i < len(mappings):
                idx = cmd_combo.findData(mappings[i].get("command", "None"))
                if idx >= 0: cmd_combo.setCurrentIndex(idx)
                idx = action_combo.findData(mappings[i].get("action", "None"))
                if idx >= 0: action_combo.setCurrentIndex(idx)

            cmd_combo.currentIndexChanged.connect(self._live_update)
            action_combo.currentIndexChanged.connect(self._live_update)
            
            row.addWidget(cmd_combo); row.addWidget(action_combo)
            self.mapping_rows.append({"command": cmd_combo, "action": action_combo})
            self.mental_layout.addLayout(row)
        mental_group.setLayout(self.mental_layout)
        layout.addWidget(mental_group)

        # Buttons
        btn_layout = QHBoxLayout()
        # "Save" button is now just "Close" since changes are live
        close_btn = QPushButton(t("settings.close")); close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def handle_mc_config(self, event: dict):
        etype = event.get('type')
        data = event.get('data')
        
        if etype == 'active_actions':
            self.mc_active_actions = data
        elif etype == 'training_threshold':
            if hasattr(self, 'threshold_lbl'):
                self.threshold_lbl.deleteLater()
            self.threshold_lbl = QLabel(t(
                "settings.threshold",
                threshold=data.get('currentThreshold', 'N/A'),
                score=data.get('lastTrainingScore', 'N/A'),
            ))
            self.threshold_lbl.setStyleSheet("font-weight: bold; color: #58a6ff;")
            self.emotiv_layout.insertWidget(0, self.threshold_lbl)
        elif etype == 'action_sensitivity':
            self.mc_sensitivities = data
            self.emotiv_status_lbl.hide()
            self._build_sensitivity_sliders()
            
    def _build_sensitivity_sliders(self):
        for s in self.mc_sensitivity_sliders:
            s[0].deleteLater()
        self.mc_sensitivity_sliders.clear()
        
        if not self.mc_active_actions or not self.mc_sensitivities:
            return
            
        for i, action in enumerate(self.mc_active_actions):
            if i >= len(self.mc_sensitivities): break
            val = self.mc_sensitivities[i]
            
            row = QHBoxLayout()
            lbl = QLabel(t("settings.action_sens", action=action.capitalize()))
            lbl.setFixedWidth(110)
            
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 10)
            slider.setSingleStep(1)
            slider.setValue(val)
            
            val_lbl = QLabel(str(val))
            val_lbl.setFixedWidth(20)
            slider.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
            
            row.addWidget(lbl)
            row.addWidget(slider)
            row.addWidget(val_lbl)
            
            w = QWidget()
            w.setLayout(row)
            self.emotiv_layout.addWidget(w)
            
            self.mc_sensitivity_sliders.append((w, slider))

    def accept(self):
        # Save emotiv sensitivities
        if self.mc_active_actions and self.mc_sensitivity_sliders:
            new_sens = [s[1].value() for s in self.mc_sensitivity_sliders]
            if new_sens != self.mc_sensitivities:
                app = self.parent()
                if app and hasattr(app, 'drone_client') and app.drone_client:
                    app.drone_client.set_mc_sensitivity(new_sens)
        super().accept()

    def _live_update(self, *args):
        # Push current slider values to config instantly
        self.config["invert_yaw"] = self.invert_yaw_cb.isChecked()
        self.config["sens_left"] = float(self.sens_left_slider.value())
        self.config["sens_right"] = float(self.sens_right_slider.value())
        self.config["sens_fwd"] = float(self.sens_fwd_slider.value())
        self.config["sens_back"] = float(self.sens_back_slider.value())
        self.config["deadzone"] = self.dead_slider.value() / 1000.0
        self.config["smoothing_window"] = self.smooth_slider.value()
        self.config["max_speed"] = self.speed_slider.value()

        mappings = []
        for w in self.mapping_rows:
            cmd = w["command"].currentData()
            if cmd != "None":
                mappings.append({
                    "command": cmd,
                    "action": w["action"].currentData(),
                    "threshold": 0.5,
                    "auto_release": 0
                })
        self.config["mental_mappings"] = mappings
        
        ConfigManager.save_config(self.config)
        
        # Apply to active client immediately
        app = self.parent()
        if app and app.drone_client and app.drone_client.program:
            qp = app.drone_client.program.quaternion_processor
            qp.sens_left = self.config.get("sens_left", 70.0)
            qp.sens_right = self.config.get("sens_right", 70.0)
            qp.sens_fwd = self.config.get("sens_fwd", 50.0)
            qp.sens_back = self.config.get("sens_back", 50.0)
            qp.movement_deadzone = self.config.get("deadzone", 0.02)
            qp.head_gain = float(self.config.get("head_gain", 3.0))
            qp.head_deadzone_deg = float(self.config.get("head_deadzone_deg", 2.0))
            qp.head_expo = float(self.config.get("head_expo", 0.6))
            qp.drift_correction = bool(
                self.config.get("head_drift_correction", True))
            sw = self.config.get("smoothing_window", 6)
            qp.SmoothingWindow = sw
            # Don't reset deque here, too disruptive during live tweaking
            
            app.drone_client.program.mental_processor.mappings = mappings

    def get_config(self):
        # We still return the config just in case
        return self.config

def _apply_app_icon(app):
    """Put the app's own mark on the window, the Dock and the taskbar.

    The executable carries an icon of its own, which is what Explorer and the
    Start menu read, but Qt draws the title bar and the macOS Dock from
    setWindowIcon and would otherwise show a default.
    """
    if os.name == "nt":
        # Windows groups taskbar buttons by Application User Model ID, and a
        # process that does not set one inherits the host interpreter's.
        # Without this, a source run shows Python's icon whatever Qt is told.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "com.emotiv.dronebci")
        except Exception:
            # Cosmetic only, and shell32 is not worth failing a launch over.
            pass

    icon = window_icon_path()
    if icon:
        app.setWindowIcon(QIcon(icon))


def main():
    # Before anything else, so a failure during construction is still recorded.
    path = applog.start()
    applog.install_excepthook()
    print(f"[log] writing to {path}", flush=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    _apply_app_icon(app)
    window = TelloControllerApp()
    window.show()
    code = app.exec()
    applog.close()
    sys.exit(code)

if __name__ == "__main__":
    main()
