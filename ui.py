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
    QSizePolicy, QGridLayout, QTabWidget, QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, QRectF, QPointF
from PyQt6.QtGui import (
    QImage, QPixmap, QColor, QPalette, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPolygonF,
)
import math
import random
from config_manager import ConfigManager
from app_paths import resource_path
import leaderboard
import i18n
from i18n import t, bind

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

# Length of one competitive ring run. Long enough to recover from a bad start,
# short enough that a queue of people waiting their turn keeps moving.
RUN_SECONDS = 60


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

    def start_run(self, seconds: int):
        """Begin a timed run: clean slate, first ring in the air."""
        self.score = 0
        self.coins = []
        self.coin_counter = 1
        self.particles = []
        self.combo_flash = 0.0
        self.run_active = True
        self.time_left = float(seconds)
        self.reset_flight()
        self.spawn_coin()
        self.update()

    def end_run(self):
        """Stop scoring and clear the field, leaving the final score readable."""
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
        offset = random.uniform(-120, 120)

        # Forward vector is (sin, -cos), Right vector is (cos, sin)
        cx = self.drone_x + math.sin(rad) * dist + math.cos(rad) * offset
        cz = self.drone_z - math.cos(rad) * dist + math.sin(rad) * offset
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

    def update_rc(self, lr, fb, ud, yaw):
        speed_factor = 0.8
        rot_factor = 0.15

        self.yaw += yaw * rot_factor

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

    def _paint_timer(self, painter):
        """Countdown clock, top-centre. Turns red and pulses in the last 10s."""
        if not self.run_active:
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

        text = t("sim.mental_command", action=action.upper())
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
                text = f"*** {action.upper()} ***"
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
    mc_config_signal = pyqtSignal(dict)
    brainmap_signal = pyqtSignal(list)
    profile_admin_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
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
        self.mc_config_signal.connect(self._on_mc_config_update)
        self.brainmap_signal.connect(self._on_brain_map)
        self.profile_admin_signal.connect(self._on_profile_admin)

        # Ring-run state. Declared before init_ui because the page builders
        # connect buttons that read it.
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self._on_run_tick)
        self._run_deadline = 0.0
        self.current_player = ""
        self.current_entry = None
        self.mc_active_actions = []
        self.mc_sensitivities = []
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
        header.addWidget(self.settings_btn)
        main_layout.addLayout(header)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.currentChanged.connect(self._on_page_changed)
        main_layout.addWidget(self.stacked_widget)

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

        self.telem_timer = QTimer()
        self.telem_timer.timeout.connect(self.update_telemetry)

    def _credentials_ready(self) -> bool:
        """True when there is a real saved credential pair to connect with.

        DEFAULT_CONFIG seeds the placeholders below on first run, so "non-empty"
        is not enough — those would happily trigger a doomed auto-connect.
        """
        cid = (self.config.get("client_id") or "").strip()
        secret = (self.config.get("client_secret") or "").strip()
        placeholders = {"", "YOUR_CLIENT_ID", "YOUR_CLIENT_SECRET"}
        return cid not in placeholders and secret not in placeholders

    def _maybe_auto_connect(self):
        """Skip the credentials form when we already know how to log in.

        Landing on a filled-in form and asking the user to press Authenticate is
        pure friction once the credentials are stored — and this app is meant to
        be handed between people, so every extra step gets paid repeatedly. The
        form stays one click away via 'Back to Auth' on the headset screen.
        """
        if not self.auto_connect_cb.isChecked():
            return
        if self.simulate_cb.isChecked():
            return
        if not self._credentials_ready():
            return
        self.log(t("log.auto_connecting"))
        self._start_bci()

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
        if index == PAGE_TEST:
            self._refresh_player_name()

        if index == PAGE_TEST and self.drone_client and not self.mc_sensitivities:
            # Cortex only answers per profile, and the profile is not known
            # until it has been loaded — so ask on arrival, not at startup.
            threading.Thread(target=self.drone_client.get_mc_config, daemon=True).start()

        if index != PAGE_TEST and self.run_timer.isActive():
            self.run_timer.stop()
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
        for combo in (self.headset_combo, self.profile_combo):
            key = getattr(combo, "_placeholder_key", None)
            if key and combo.count() == 1:
                combo.setItemText(0, t(key))
        for widget in (self.drone_sim, self.neutral_sim, self.push_sim):
            widget.update()
        if getattr(self, "hud_widget", None) is not None:
            self.hud_widget.update()

    def setup_page_auth(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(600)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "auth.title")
        c_layout.addWidget(title)

        auth_group = QGroupBox()
        bind(auth_group, "auth.group", "setTitle")
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.addWidget(bind(QLabel(), "auth.client_id"))
        self.client_id_input = QLineEdit()
        auth_layout.addWidget(self.client_id_input)
        auth_layout.addWidget(bind(QLabel(), "auth.client_secret"))
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        auth_layout.addWidget(self.client_secret_input)

        self.simulate_cb = QCheckBox()
        bind(self.simulate_cb, "auth.simulate")
        auth_layout.addWidget(self.simulate_cb)

        self.auto_connect_cb = QCheckBox()
        bind(self.auto_connect_cb, "auth.auto_connect")
        bind(self.auto_connect_cb, "auth.auto_connect.tip", "setToolTip")
        auth_layout.addWidget(self.auto_connect_cb)

        self.connect_bci_btn = QPushButton(); self.connect_bci_btn.setObjectName("blueBtn")
        bind(self.connect_bci_btn, "auth.connect")
        self.connect_bci_btn.clicked.connect(self._start_bci)
        auth_layout.addWidget(self.connect_bci_btn)
        c_layout.addWidget(auth_group)

        c_layout.addWidget(bind(QLabel(), "auth.logs"))
        self.bci_log_terminal = QPlainTextEdit()
        self.bci_log_terminal.setReadOnly(True)
        self.bci_log_terminal.setMaximumBlockCount(200)
        self.bci_log_terminal.setFixedHeight(120)
        c_layout.addWidget(self.bci_log_terminal)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def setup_page_headset(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(600)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(15)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "headset.title")
        c_layout.addWidget(title)

        self.headset_group = QGroupBox()
        bind(self.headset_group, "headset.group", "setTitle")
        headset_layout = QVBoxLayout(self.headset_group)
        headset_hdr = QHBoxLayout()
        headset_hdr.addWidget(bind(QLabel(), "headset.label"))
        headset_hdr.addStretch()
        self.refresh_headsets_btn = bind(QPushButton(), "headset.refresh")
        bind(self.refresh_headsets_btn, "headset.refresh.tip", "setToolTip")
        self.refresh_headsets_btn.setFixedWidth(90)
        self.refresh_headsets_btn.clicked.connect(self._refresh_headsets)
        headset_hdr.addWidget(self.refresh_headsets_btn)
        headset_layout.addLayout(headset_hdr)

        self.headset_combo = QComboBox()
        self.headset_combo._placeholder_key = "headset.awaiting_auth"
        self.headset_combo.addItem(t("headset.awaiting_auth"))
        self.headset_combo.setStyleSheet(
            "QComboBox { background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
            "padding: 8px 12px; color: #8b949e; font-size: 14px; }"
            "QComboBox:enabled { color: #e6edf3; }"
            "QComboBox QAbstractItemView { background-color: #161b22; color: #e6edf3;"
            "selection-background-color: #1f6feb; border: 1px solid #30363d; }"
        )
        headset_layout.addWidget(self.headset_combo)
        
        self.connect_headset_btn = QPushButton()
        bind(self.connect_headset_btn, "headset.connect")
        self.connect_headset_btn.setObjectName("blueBtn")
        self.connect_headset_btn.clicked.connect(self._connect_headset)
        headset_layout.addWidget(self.connect_headset_btn)

        self.bci_conn_status_lbl = QLabel()
        bind(self.bci_conn_status_lbl, "badge.not_connected")
        self.bci_conn_status_lbl.setObjectName("statusBadge")
        self.bci_conn_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headset_layout.addWidget(self.bci_conn_status_lbl)
        c_layout.addWidget(self.headset_group)

        # Back button
        back_btn = QPushButton()
        bind(back_btn, "headset.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_AUTH))
        c_layout.addWidget(back_btn)

        layout.addWidget(container)
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

        sensor_group = QGroupBox()
        bind(sensor_group, "eq.group", "setTitle")
        self.eq_sensor_layout = QGridLayout(sensor_group)
        self.eq_sensor_layout.setSpacing(8)
        self.eq_sensor_labels = {}
        c_layout.addWidget(sensor_group)

        self.eq_status_lbl = QLabel()
        bind(self.eq_status_lbl, "eq.waiting_data")
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
        
        self.stacked_widget.addWidget(page)

    def setup_page_train_push(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
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
        
        self.stacked_widget.addWidget(page)

    def setup_page_1(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget(); container.setFixedWidth(1000)
        c_layout = QVBoxLayout(container); c_layout.setSpacing(14)

        title = QLabel(); title.setObjectName("titleLabel")
        bind(title, "test.title")
        subtitle = QLabel()
        bind(subtitle, "test.subtitle")
        subtitle.setObjectName("subtitleLabel"); subtitle.setWordWrap(True)
        c_layout.addWidget(title); c_layout.addWidget(subtitle)

        # ── Ring run: the competitive bit ────────────────────────────────────
        game_group = QGroupBox()
        bind(game_group, "game.group", "setTitle", seconds=RUN_SECONDS)
        game_row = QHBoxLayout(game_group)

        # The player already named themselves when they created the training
        # profile. Asking again invites a second, different name on the board.
        game_row.addWidget(bind(QLabel(), "game.playing_as"))
        self.player_name_lbl = bind(QLabel(), "game.no_profile")
        self.player_name_lbl.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #f1c40f;")
        game_row.addWidget(self.player_name_lbl, stretch=1)

        self.start_run_btn = bind(QPushButton(), "game.start")
        self.start_run_btn.setObjectName("primaryBtn")
        self.start_run_btn.clicked.connect(self._start_ring_run)
        game_row.addWidget(self.start_run_btn)

        leaderboard_btn = bind(QPushButton(), "game.show_leaderboard")
        leaderboard_btn.clicked.connect(
            lambda: self._show_leaderboard(PAGE_TEST))
        game_row.addWidget(leaderboard_btn)

        c_layout.addWidget(game_group)

        top_split = QHBoxLayout()
        top_split.setSpacing(12)

        # Left: the simulator, given the room it deserves.
        state_group = QGroupBox()
        bind(state_group, "test.state_group", "setTitle")
        self.state_layout = QVBoxLayout()
        self.drone_sim = DroneSimulatorWidget(self)
        self.drone_sim.setMinimumSize(660, 430)
        self.drone_sim.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
        self.state_layout.addWidget(self.drone_sim, stretch=1)
        state_group.setLayout(self.state_layout)
        top_split.addWidget(state_group, stretch=3)

        # Right: everything that is a readout, stacked out of the way.
        side = QVBoxLayout()
        side.setSpacing(10)

        status_group = QGroupBox()
        bind(status_group, "test.status_group", "setTitle")
        status_layout = QVBoxLayout(status_group)
        self.virtual_flight_state_lbl = QLabel()
        bind(self.virtual_flight_state_lbl, "test.landed")
        self.virtual_flight_state_lbl.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: #8b949e;")
        status_layout.addWidget(self.virtual_flight_state_lbl)

        self.last_action_lbl = QLabel()
        bind(self.last_action_lbl, "test.last_command_none")
        self.last_action_lbl.setStyleSheet("color: #58a6ff;")
        self.last_action_lbl.setWordWrap(True)
        status_layout.addWidget(self.last_action_lbl)
        side.addWidget(status_group)

        rc_group = QGroupBox()
        bind(rc_group, "test.rc_group", "setTitle")
        rc_grid = QGridLayout()
        def make_bar():
            b = QProgressBar()
            b.setRange(-100, 100); b.setValue(0); b.setTextVisible(True); b.setFormat("%v")
            return b
        self.test_yaw_bar = make_bar()
        self.test_fb_bar = make_bar()
        rc_grid.addWidget(bind(QLabel(), "test.yaw"), 0, 0)
        rc_grid.addWidget(self.test_yaw_bar, 0, 1)
        rc_grid.addWidget(bind(QLabel(), "test.pitch"), 1, 0)
        rc_grid.addWidget(self.test_fb_bar, 1, 1)
        self.rc_lbl = QLabel("RC: lr=   0  fb=   0  ud=   0  yaw=   0")
        self.rc_lbl.setStyleSheet(
            "font-family: monospace; font-size: 12px; color: #58a6ff;"
            "background: #0d1117; padding: 8px; border-radius: 5px;")
        rc_grid.addWidget(self.rc_lbl, 2, 0, 1, 2)
        rc_group.setLayout(rc_grid)
        side.addWidget(rc_group)

        # Sensitivity, tunable while flying. Getting the feel right belongs here
        # rather than behind the Configurations dialog: this is the screen where
        # you can actually see the effect of a change, and the one you want it
        # settled on before starting a timed run.
        sens_group = QGroupBox()
        bind(sens_group, "tune.group", "setTitle")
        sens_layout = QVBoxLayout(sens_group)
        sens_layout.setSpacing(4)

        tilt_lbl = bind(QLabel(), "tune.tilt")
        tilt_lbl.setStyleSheet("font-size: 11px; color: #58a6ff; font-weight: bold;")
        sens_layout.addWidget(tilt_lbl)

        self.tilt_sliders = {}
        tilt_grid = QGridLayout()
        tilt_grid.setSpacing(4)
        for row, (key, label, default) in enumerate((
                ("sens_left", "◀", 70.0), ("sens_right", "▶", 70.0),
                ("sens_fwd", "▲", 50.0), ("sens_back", "▼", 50.0))):
            arrow = QLabel(label)
            arrow.setFixedWidth(16)
            arrow.setStyleSheet("font-size: 12px; color: #8b949e;")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 300)
            slider.setValue(int(self.config.get(key, default)))
            value = QLabel(str(slider.value()))
            value.setFixedWidth(28)
            value.setStyleSheet("font-size: 11px; color: #8b949e;")
            slider.valueChanged.connect(
                lambda v, k=key, lab=value: self._on_tilt_sens(k, v, lab))
            tilt_grid.addWidget(arrow, row, 0)
            tilt_grid.addWidget(slider, row, 1)
            tilt_grid.addWidget(value, row, 2)
            self.tilt_sliders[key] = slider
        sens_layout.addLayout(tilt_grid)

        dead_row = QHBoxLayout()
        dead_lbl = bind(QLabel(), "tune.deadzone")
        dead_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
        self.dead_slider_inline = QSlider(Qt.Orientation.Horizontal)
        self.dead_slider_inline.setRange(0, 500)
        self.dead_slider_inline.setValue(int(self.config.get("deadzone", 0.02) * 1000))
        self.dead_value_lbl = QLabel(f"{self.dead_slider_inline.value()/1000:.3f}")
        self.dead_value_lbl.setFixedWidth(38)
        self.dead_value_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
        self.dead_slider_inline.valueChanged.connect(self._on_deadzone)
        dead_row.addWidget(dead_lbl); dead_row.addWidget(self.dead_slider_inline)
        dead_row.addWidget(self.dead_value_lbl)
        sens_layout.addLayout(dead_row)

        mc_lbl = bind(QLabel(), "tune.mental")
        mc_lbl.setStyleSheet(
            "font-size: 11px; color: #58a6ff; font-weight: bold; padding-top: 6px;")
        sens_layout.addWidget(mc_lbl)

        # Filled in once Cortex answers mentalCommandActionSensitivity — the
        # action list is whatever this profile was actually trained on.
        self.mc_sens_layout = QVBoxLayout()
        self.mc_sens_layout.setSpacing(4)
        sens_layout.addLayout(self.mc_sens_layout)
        self.mc_sens_hint = bind(QLabel(), "tune.mental_waiting")
        self.mc_sens_hint.setWordWrap(True)
        self.mc_sens_hint.setStyleSheet("font-size: 10px; color: #6e7681;")
        sens_layout.addWidget(self.mc_sens_hint)

        self.inline_mc_sliders = []
        side.addWidget(sens_group)

        # Raw Cortex dumps: useful when debugging, noise the rest of the time.
        self.raw_group = QGroupBox()
        bind(self.raw_group, "test.raw_group", "setTitle")
        raw_layout = QVBoxLayout()
        self.raw_mot_lbl = QLabel("MOT: None")
        self.raw_mot_lbl.setStyleSheet("color: #8b949e; font-family: monospace; font-size: 10px;")
        self.raw_mot_lbl.setWordWrap(True)
        self.raw_com_lbl = QLabel("COM: None")
        self.raw_com_lbl.setStyleSheet("color: #8b949e; font-family: monospace; font-size: 10px;")
        self.raw_com_lbl.setWordWrap(True)
        raw_layout.addWidget(self.raw_mot_lbl)
        raw_layout.addWidget(self.raw_com_lbl)
        self.raw_group.setLayout(raw_layout)
        self.raw_group.setVisible(SHOW_REAL_DRONE)
        side.addWidget(self.raw_group)

        side.addStretch()
        top_split.addLayout(side, stretch=1)
        c_layout.addLayout(top_split, stretch=1)

        btn_row = QHBoxLayout()
        back_btn = bind(QPushButton(), "test.back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(PAGE_PROFILE))

        fs_btn = bind(QPushButton(), "test.fullscreen")
        fs_btn.clicked.connect(self.toggle_fullscreen)

        self.recenter_btn_p1 = bind(QPushButton(), "test.recenter")
        self.recenter_btn_p1.setObjectName("blueBtn")
        self.recenter_btn_p1.clicked.connect(self.reset_headset)

        self.retrain_btn = bind(QPushButton(), "retrain.button")
        bind(self.retrain_btn, "retrain.tip", "setToolTip")
        self.retrain_btn.clicked.connect(self._reset_and_retrain)
        self.real_drone_btn = bind(QPushButton(), "test.next")
        self.real_drone_btn.setObjectName("primaryBtn")
        self.real_drone_btn.clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(PAGE_DRONE))
        self.real_drone_btn.setVisible(SHOW_REAL_DRONE)

        btn_row.addWidget(back_btn); btn_row.addWidget(fs_btn)
        btn_row.addWidget(self.recenter_btn_p1); btn_row.addWidget(self.retrain_btn)
        btn_row.addWidget(self.real_drone_btn)
        c_layout.addLayout(btn_row)

        layout.addWidget(container)
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
    def _start_ring_run(self):
        if self.run_timer.isActive():
            return
        name = (self.config.get("profile_name") or "").strip() or t("game.anonymous")
        self.current_player = name

        self.drone_sim.start_run(RUN_SECONDS)
        self._run_deadline = time.monotonic() + RUN_SECONDS
        self.run_timer.start(100)
        self.start_run_btn.setEnabled(False)
        bind(self.start_run_btn, "game.running")
        self.log(t("log.run_started", name=name, seconds=RUN_SECONDS))

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
            self._run_profile_admin(
                lambda: self.drone_client.delete_profile(profile),
                "log.profile_deleting", profile)
            self.config["profile_name"] = ""
            ConfigManager.save_config(self.config)

        # The sensitivity panel is showing the outgoing player's actions; blank
        # it so the next profile rebuilds it from its own training.
        self.mc_active_actions = []
        self.mc_sensitivities = []
        self._build_inline_mc_sliders()

        self.current_entry = None
        self._refresh_player_name()
        self.drone_sim.end_run()
        self.drone_sim.reset_flight()

        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)
        self._refresh_headsets()
        self.log(t("log.session_handoff"))

    def _run_profile_admin(self, fn, log_key: str, profile: str):
        """Profile admin talks to Cortex with blocking sends and sleeps."""
        self.log(t(log_key, profile=profile))
        threading.Thread(target=fn, daemon=True).start()

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
        cid = 'SIM' if is_sim else self.client_id_input.text()
        csec = 'SIM' if is_sim else self.client_secret_input.text()

        self.connect_bci_btn.setEnabled(False)
        bind(self.bci_conn_status_lbl, "badge.connecting")

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
        self.headset_combo.clear()
        
        if not headsets:
            self.headset_combo._placeholder_key = "headset.none_found"
            self.headset_combo.addItem(t("headset.none_found"))
            self.headset_combo.setEnabled(False)
            self.connect_headset_btn.setEnabled(False)
            self.log(t("log.no_headsets"))
            return

        self.headset_combo._placeholder_key = None
        for hs in headsets:
            hs_id = hs.get('id', 'Unknown')
            status = hs.get('status', 'Unknown')
            self.headset_combo.addItem(t("headset.item", id=hs_id, status=status), userData=hs_id)

        self.headset_combo.setEnabled(True)
        self.connect_headset_btn.setEnabled(True)
        self.headset_group.setEnabled(True)
        self.log(t("log.headsets_available", count=len(headsets)))
        # Auto-advance to headset selection screen on successful authentication & headset query
        self.stacked_widget.setCurrentIndex(PAGE_HEADSET)

    def _connect_headset(self):
        """Connect to the selected headset."""
        idx = self.headset_combo.currentIndex()
        headset_id = self.headset_combo.itemData(idx)
        if not headset_id:
            self.log(t("log.no_headset_selected"))
            return

        self.connect_headset_btn.setEnabled(False)
        bind(self.connect_headset_btn, "headset.connecting_btn")
        
        # Load and apply device-specific config profile
        device_type = headset_id.split('-')[0]
        self.config = ConfigManager.get_device_config(self.config, device_type)
        self.config["device_id"] = headset_id
        
        self._apply_config_to_client()
        
        self.log(t("log.connecting_headset", headset=headset_id))

        if self.drone_client:
            threading.Thread(
                target=self.drone_client.connect_headset,
                args=(headset_id,),
                daemon=True
            ).start()
        else:
            self.log(t("log.client_not_init"))
            self.connect_headset_btn.setEnabled(True)
            bind(self.connect_headset_btn, "headset.connect")

    # ── Live sensitivity tuning ──────────────────────────────────────────────
    def _on_tilt_sens(self, key: str, value: int, label: QLabel):
        label.setText(str(value))
        self.config[key] = float(value)
        ConfigManager.save_config(self.config)
        self._apply_config_to_client()

    def _on_deadzone(self, value: int):
        self.dead_value_lbl.setText(f"{value/1000:.3f}")
        self.config["deadzone"] = value / 1000.0
        ConfigManager.save_config(self.config)
        self._apply_config_to_client()

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
            name.setFixedWidth(58)
            name.setStyleSheet("font-size: 11px; color: #8b949e;")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 10)
            slider.setValue(int(values[i]))
            value_lbl = QLabel(str(slider.value()))
            value_lbl.setFixedWidth(20)
            value_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
            slider.valueChanged.connect(lambda v, l=value_lbl: l.setText(str(v)))
            # Cortex writes to the profile on every call, so only push when the
            # user lets go rather than on every pixel of drag.
            slider.sliderReleased.connect(self._push_mc_sensitivity)
            row.addWidget(name); row.addWidget(slider); row.addWidget(value_lbl)

            holder = QWidget()
            holder.setLayout(row)
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
                QTimer.singleShot(0, done)

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

        if status.startswith("PENDING_ACCESS:"):
            self._show_access_pending_ui(status[len("PENDING_ACCESS:"):])
            return

        if status.startswith("PROFILE_LOADED:"):
            msg = status[len("PROFILE_LOADED:"):]
            bind(self.bci_conn_status_lbl, "badge.profile_loaded",
                 profile=i18n.profile_name_from_loaded(msg))
            self.bci_conn_status_lbl.setStyleSheet("background-color: #1a4a2e; border: 1px solid #3fb950;")
            self._hide_access_pending_ui()
            self.p0_next_btn.setEnabled(True)
            self._override_action_for_test()
            # Re-enable the Load button so the user can switch profiles
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")
            bind(self.profile_status_lbl, "profile.selected",
                 profile=self.profile_combo.currentText())
            self.profile_status_lbl.setStyleSheet(
                "color: #3fb950; font-size: 11px; font-style: italic; padding: 0 2px;"
            )
            return

        bind(self.bci_conn_status_lbl, "badge.status", status=i18n.backend_status(status))
        if "Active" in status:
            bind(self.bci_conn_status_lbl, "badge.bci_active")
            self.bci_conn_status_lbl.setStyleSheet("background-color: #238636;")
            self._hide_access_pending_ui()
            self._override_action_for_test()
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
            bind(self.bci_conn_status_lbl, "badge.scan_finished")
            bind(self.connect_bci_btn, "auth.retry")
            self.connect_bci_btn.setEnabled(True)
            # Re-enable load button in case of profile load error
            self.load_profile_btn.setEnabled(True)
            bind(self.load_profile_btn, "profile.load")

    def _show_access_pending_ui(self, message: str):
        """Show a prominent inline banner asking the user to approve via EMOTIV Launcher."""
        bind(self.bci_conn_status_lbl, "badge.waiting_approval")
        self.bci_conn_status_lbl.setStyleSheet("background-color: #7d4e00; border: 1px solid #e3a01a;")

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
            # Insert banner right below the status badge in the page-0 container
            # The container's layout is c_layout (index 0 child of page 0)
            page0_container = self.stacked_widget.widget(0).findChild(QWidget)
            page0_c_layout = page0_container.layout() if page0_container else None
            if page0_c_layout:
                # Insert before the btn_row (second-to-last item) - just append for safety
                page0_c_layout.insertWidget(
                    page0_c_layout.indexOf(self.bci_conn_status_lbl) + 1,
                    banner
                )
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
            self.log(t("log.training_rejected", action=action))
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

    def _on_dev_data_update(self, signal: int, cq_list: list):
        """Update the EQ quality check screen with per-sensor contact quality."""
        # Only update when on the EQ check screen (index 3)
        if self.stacked_widget.currentIndex() != PAGE_EQ:
            return

        # Overall signal quality (0-4)
        signal_keys = {0: "quality.none", 1: "quality.very_bad", 2: "quality.poor",
                       3: "quality.fair", 4: "quality.good"}
        signal_colors = {0: "#da3633", 1: "#da3633", 2: "#e3a01a", 3: "#58a6ff", 4: "#3fb950"}
        key = signal_keys.get(signal)
        sig_text = t(key) if key else t("quality.unknown", value=signal)
        sig_color = signal_colors.get(signal, "#8b949e")
        bind(self.eq_overall_lbl, "eq.overall", quality=sig_text, value=signal)
        self.eq_overall_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {sig_color};"
            f"padding: 10px; background-color: #161b22; border: 1px solid {sig_color}; border-radius: 8px;"
        )

        # Per-sensor contact quality
        # CQ values: 0=No Signal, 1=Bad, 2=Poor, 3=Fair, 4=Good
        cq_colors = {0: "#da3633", 1: "#da3633", 2: "#e3a01a", 3: "#58a6ff", 4: "#3fb950"}
        cq_keys = {0: "quality.none", 1: "quality.bad", 2: "quality.poor",
                   3: "quality.fair", 4: "quality.good"}

        for i, cq_val in enumerate(cq_list):
            sensor_name = f"S{i}"
            cq_val_int = int(cq_val) if isinstance(cq_val, (int, float)) else 0
            color = cq_colors.get(cq_val_int, "#8b949e")
            cq_key = cq_keys.get(cq_val_int, "quality.short_unknown")

            if sensor_name not in self.eq_sensor_labels:
                name_lbl = QLabel(sensor_name)
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

        # Determine if quality is good enough to start training
        if cq_list:
            avg_cq = sum(int(v) if isinstance(v, (int, float)) else 0 for v in cq_list) / len(cq_list)
            good_enough = avg_cq >= 2.0 and signal >= 2
        else:
            good_enough = False

        if good_enough:
            bind(self.eq_status_lbl, "eq.ok")
            self.eq_status_lbl.setStyleSheet("font-size: 14px; color: #3fb950; margin-top: 10px;")
            self.eq_next_btn.setEnabled(True)
        else:
            bind(self.eq_status_lbl, "eq.bad")
            self.eq_status_lbl.setStyleSheet("font-size: 14px; color: #e3a01a; margin-top: 10px;")
            self.eq_next_btn.setEnabled(False)

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

    def _override_action_for_test(self):
        if not self.drone_client: return
        original_execute = self.drone_client.drone.execute_action
        
        def test_execute(action, auto_release_time=0.0):
            was_flying = self.drone_client.drone.is_flying
            original_execute(action, auto_release_time)
            is_flying = self.drone_client.drone.is_flying
            
            def _update_ui():
                ignored = (
                    (action == "TakeOff" and was_flying and is_flying)
                    or (action in ["Land", "EmergencyStop"] and not was_flying and not is_flying)
                    or (action.startswith("Flip") and not is_flying)
                )
                key = "test.last_command_ignored" if ignored else "test.last_command"
                bind(self.last_action_lbl, key, action=action)
                if is_flying and not was_flying:
                    bind(self.virtual_flight_state_lbl, "test.flying")
                    self.virtual_flight_state_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #3fb950;")
                elif not is_flying and was_flying:
                    bind(self.virtual_flight_state_lbl, "test.landed")
                    self.virtual_flight_state_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #8b949e;")
            QTimer.singleShot(0, _update_ui)
        self.drone_client.drone.execute_action = test_execute

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

    def update_telemetry(self):
        if self.drone_client and self.stacked_widget.currentIndex() in (PAGE_TEST, PAGE_DASHBOARD):
            if self.drone_client and self.drone_client.drone:
                lr, fb, ud, yaw = self.drone_client.drone.get_rc_values()
                self.rc_lbl.setText(f"RC: lr={lr:+4d}  fb={fb:+4d}  ud={ud:+4d}  yaw={yaw:+4d}")
                if self.stacked_widget.currentIndex() == PAGE_TEST:
                    self.drone_sim.update_rc(lr, fb, ud, yaw)
                    self.test_yaw_bar.setValue(yaw)
                    self.test_fb_bar.setValue(fb)
                
                # Update MC Dashboard Indicator
                action = getattr(self.drone_client.drone, 'last_executed_action', None)
                action_time = getattr(self.drone_client.drone, 'last_action_time', 0.0)
                now = time.time()
                if action and (now - action_time) < 2.0:
                    bind(self.dash_mc_lbl, "dash.mc", action=action)
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
            
            mot_str = self.drone_client.latest_raw_mot[:120] + "..." if len(self.drone_client.latest_raw_mot) > 120 else self.drone_client.latest_raw_mot
            self.raw_mot_lbl.setText(f"MOT: {mot_str}")
            self.raw_com_lbl.setText(f"COM: {self.drone_client.latest_raw_com}")

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

        self.stacked_widget.setCurrentIndex(PAGE_AUTH)
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
        self.client_id_input.setText(c.get("client_id", ""))
        self.client_secret_input.setText(c.get("client_secret", ""))
        self.simulate_cb.setChecked(c.get("simulate", False))
        self.auto_connect_cb.setChecked(c.get("auto_connect", True))
        # Profile combo is populated dynamically; just remember the saved name
        # so _populate_profiles can re-select it once the list arrives.

    def save_settings(self):
        self.config["client_id"] = self.client_id_input.text()
        self.config["client_secret"] = self.client_secret_input.text()
        self.config["language"] = i18n.get_lang()
        # profile_name is set automatically by _populate_profiles when profiles arrive
        self.config["simulate"] = self.simulate_cb.isChecked()
        self.config["auto_connect"] = self.auto_connect_cb.isChecked()
        ConfigManager.save_config(self.config)

    def _apply_config_to_client(self):
        if self.drone_client and self.drone_client.program:
            qp = self.drone_client.program.quaternion_processor
            qp.invert_yaw = self.config.get("invert_yaw", False)
            qp.sens_left = self.config.get("sens_left", 70.0)
            qp.sens_right = self.config.get("sens_right", 70.0)
            qp.sens_fwd = self.config.get("sens_fwd", 50.0)
            qp.sens_back = self.config.get("sens_back", 50.0)
            qp.movement_deadzone = self.config.get("deadzone", 0.02)
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

    def closeEvent(self, event):
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
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setStyleSheet("QDialog { background-color: rgba(2, 5, 10, 242); }")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_result(entry, rank, total, entries))
        self.stack.addWidget(self._build_board(entry, entries))
        outer.addWidget(self.stack)

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

        if rank == 1 and total > 1:
            rank_text, rank_colour = t("game.rank_first"), "#f1c40f"
        else:
            rank_text, rank_colour = t("game.rank", rank=rank, total=total), "#58a6ff"
        rank_lbl = QLabel(rank_text)
        rank_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rank_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {rank_colour}; padding: 6px;")
        box.addWidget(rank_lbl)

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
            sw = self.config.get("smoothing_window", 6)
            qp.SmoothingWindow = sw
            # Don't reset deque here, too disruptive during live tweaking
            
            app.drone_client.program.mental_processor.mappings = mappings

    def get_config(self):
        # We still return the config just in case
        return self.config

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = TelloControllerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
